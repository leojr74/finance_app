import streamlit as st
import pandas as pd
import hashlib
import os
import tempfile
import calendar
from datetime import date
from ui import apply_global_style
from database import get_engine, get_authenticator, carregar_transacoes, verificar_duplicata
from sqlalchemy import text

st.set_page_config(
    page_title="Importação de Faturas",
    page_icon="📥",
    layout="wide"
)

authenticator = get_authenticator()
authenticator.login(location='unrendered')

if not st.session_state.get("authentication_status"):
    st.warning("Sessão expirada. Por favor, faça login na Home.")
    st.stop()

usuario_atual = st.session_state["username"]
apply_global_style()

from parser_router import extract_transactions_auto

st.title("📥 Importação de Faturas")

# --------------------------------------------------
# Período da fatura
# --------------------------------------------------
st.subheader("Período da fatura")
col1, col2 = st.columns(2)

with col1:
    data_inicio = st.date_input("Data inicial", value=date.today().replace(day=1))

with col2:
    data_fim = st.date_input("Data final", value=date.today())

if data_fim < data_inicio:
    st.error("Data final não pode ser anterior à data inicial")
    st.stop()

# --------------------------------------------------
# Upload PDF
# --------------------------------------------------
uploaded = st.file_uploader("Upload da fatura PDF", type="pdf")

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded.read())
        tmp_path = tmp_file.name

    try:
        result = extract_transactions_auto(
            pdf_path=tmp_path,
            data_inicio=data_inicio,
            data_fim=data_fim
        )

        if result and "transactions" in result:
            df = pd.DataFrame(result["transactions"])
            
            # Normalização inicial para exibição
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df["descricao"] = df["descricao"].astype(str).str.upper()
            
            df = df.sort_values("data").reset_index(drop=True)
            st.session_state.df_transacoes = df

            # Identificação do Banco
            id_tecnico = str(result.get("bank", "DESCONHECIDO")).lower()
            mapeamento_nomes = {
                "ca": "CARTÃO C&A",
                "caixa": "CARTÃO CAIXA",
                "bradescard": "CARTÃO AMAZON",
                "bradesco": "CARTÃO BRADESCO",
                "santander": "CARTÃO SANTANDER",
                "itau": "CARTÃO ITAÚ",
                "bb": "CARTÃO BB",
                "nubank": "CARTÃO NUBANK",
                "mercado_pago": "MERCADO PAGO"
            }
            banco_nome = mapeamento_nomes.get(id_tecnico, id_tecnico.upper())

            st.success(f"✅ {len(df)} transações extraídas de: **{banco_nome}**")

            st.dataframe(
                df[["data", "descricao", "valor"]], 
                width = 'stretch', 
                hide_index=True,
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "descricao": "Descrição",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
                }
            )

            total_fatura = df["valor"].sum()
            st.metric(label="Total Extraído", value=f"R$ {total_fatura:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            # --------------------------------------------------
            # Botão salvar 
            # --------------------------------------------------
            
        if st.button("💾 Salvar no Banco", key="save_db_btn"):
            try:
                engine = get_engine()
                
                # 1. Preparação para evitar duplicatas manuais
                df_existente = carregar_transacoes(usuario_atual)
                if not df_existente.empty:
                    df_existente['data'] = pd.to_datetime(df_existente['data']).apply(lambda x: x.date())
                    df_existente['valor'] = df_existente['valor'].astype(float)

                stats = {
                    "novas": 0, 
                    "duplicadas_manual": 0, 
                    "duplicadas_fatura": 0, 
                    "duplicadas_sms": 0
                }

                # 2. Busca hashes existentes via SQLAlchemy
                query_hashes = text("SELECT hash_fatura FROM transacoes WHERE user_id = :u AND hash_fatura IS NOT NULL")
                with engine.connect() as conn:
                    result_hashes = conn.execute(query_hashes, {"u": usuario_atual}).fetchall()
                    hashes_existentes = {row[0] for row in result_hashes}

                dados_para_inserir = []

                # 3. Processamento do DataFrame
                for _, row in df.iterrows():
                    if pd.isna(row['data']): continue

                    # --- LOGICA DE DATAS ---
                    data_orig_fatura = row['data'].date() if hasattr(row['data'], 'date') else row['data']
                    
                    if data_inicio <= data_orig_fatura <= data_fim:
                        data_ajustada = data_orig_fatura
                    else:
                        dia_transacao = data_orig_fatura.day
                        mes_alvo = data_inicio.month
                        ano_alvo = data_inicio.year

                        if dia_transacao < data_inicio.day:
                            if data_inicio.month == 12:
                                mes_alvo, ano_alvo = 1, data_inicio.year + 1
                            else:
                                mes_alvo = data_inicio.month + 1

                        try:
                            data_ajustada = date(ano_alvo, mes_alvo, dia_transacao)
                        except ValueError:
                            ultimo_dia = calendar.monthrange(ano_alvo, mes_alvo)[1]
                            data_ajustada = date(ano_alvo, mes_alvo, ultimo_dia)

                    data_final_str = data_ajustada.strftime('%Y-%m-%d')
                    desc_proc = str(row['descricao']).upper()
                    # Mantém o sinal original do parser (negativo = crédito/pagamento)
                    valor_proc = float(row['valor'])
                    cat_proc = row.get('categoria') if pd.notna(row.get('categoria')) else "Sem categoria"

                    # Hash Único baseado na data AJUSTADA para o orçamento
                    raw_str = f"{data_final_str}{valor_proc}{desc_proc}{banco_nome}{usuario_atual}"
                    h_fatura = hashlib.md5(raw_str.encode()).hexdigest()

                    # --- VALIDAÇÃO 1: HASH (Fatura já importada) ---
                    if h_fatura in hashes_existentes:
                        stats["duplicadas_fatura"] += 1
                        continue

                    # 2. VALIDAÇÃO PRIORIDADE 2 & 3: BUSCA POR SIMILARIDADE (Data + Valor + Banco)

                    is_dup = False
                    if not df_existente.empty:
                        matches = df_existente[
                            (df_existente['data'] == data_ajustada) & 
                            (df_existente['valor'].round(2) == round(valor_proc, 2)) & 
                            (df_existente['banco'] == banco_nome)
                        ]
                        if not matches.empty:
                            # VERIFICAÇÃO SE É SMS: 
                            # Se o match possuir um hash e esse hash NÃO for 'MANUAL_ENTRY', é SMS.
                            es_sms = matches['hash_fatura'].apply(
                                lambda x: x not in [None, '', 'MANUAL_ENTRY']
                            ).any()

                            if es_sms:
                                stats["duplicadas_sms"] += 1
                            else:
                                stats["duplicadas_manual"] += 1
                            is_dup = True

                    if is_dup:
                        continue # Pula a inserção para duplicatas de SMS ou Manual

                    stats["novas"] += 1
                    dados_para_inserir.append((
                        data_final_str, desc_proc, cat_proc, valor_proc, 
                        banco_nome, usuario_atual, h_fatura
                    ))

                        
                # 4. Execução do salvamento em lote
                if dados_para_inserir:
                    query_insert = text("""
                    INSERT INTO transacoes (data, descricao, categoria, valor, banco, user_id, hash_fatura)
                    VALUES (:d, :desc, :c, :v, :b, :u, :h)
                """)
                with engine.begin() as conn:
                    conn.execute(query_insert, dados_para_inserir)
                st.success(f"✅ {stats['novas']} novas transações importadas com sucesso!")

                # 5. Feedbacks 
                if stats["duplicadas_sms"] > 0:
                    st.info(f"📲 {stats['duplicadas_sms']} transações ignoradas: Já foram capturadas via SMS.")

                if stats["duplicadas_manual"] > 0:
                    st.info(f"📌 {stats['duplicadas_manual']} transações ignoradas (já existem lançamentos manuais no mesmo dia).")
                
                if stats["duplicadas_fatura"] > 0:
                    st.warning(f"🚫 {stats['duplicadas_fatura']} transações já constavam em importações anteriores.")

                if stats["novas"] == 0 and sum(v for k, v in stats.items() if k != "novas") == 0:
                    st.warning("Nenhuma transação encontrada no arquivo.")

                # Limpa cache para atualizar página de transações
                if 'df_transacoes' in st.session_state:
                    del st.session_state.df_transacoes

            except Exception as e:
                st.error(f"❌ Erro ao salvar no banco: {e}")
                                
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)