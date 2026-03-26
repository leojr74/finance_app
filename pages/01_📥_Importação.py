import streamlit as st
import pandas as pd
import hashlib
import os
import tempfile
from datetime import date
from ui import apply_global_style
from database import conectar, get_authenticator

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
                conn = conectar()
                if conn:
                    # 1. Preparação para evitar duplicatas manuais
                    from database import carregar_transacoes
                    df_existente = carregar_transacoes(usuario_atual)
                    if not df_existente.empty:
                        df_existente['data'] = pd.to_datetime(df_existente['data'])

                    dados_para_inserir = []
                    stats = {"novas": 0, "duplicadas_manual": 0, "duplicadas_fatura": 0}

                    import calendar
                    with conn.cursor() as cursor:
                        # Iteramos sobre o DataFrame processado para garantir consistência
                        for _, row in df.iterrows():
                            if pd.isna(row['data']): continue

                            # --- AJUSTE DE DATA PARA COMPETÊNCIA (Mês do Orçamento) ---
                            dia_original = row['data'].day
                            try:
                                data_ajustada = date(data_inicio.year, data_inicio.month, dia_original)
                            except ValueError:
                                ultimo_dia = calendar.monthrange(data_inicio.year, data_inicio.month)[1]
                                data_ajustada = date(data_inicio.year, data_inicio.month, ultimo_dia)

                            data_final_str = data_ajustada.strftime('%Y-%m-%d')
                            desc_proc = str(row['descricao']).upper()
                            valor_proc = abs(float(row['valor']))
                            cat_proc = row.get('categoria') if pd.notna(row.get('categoria')) else "Sem categoria"

                            # Hash Único baseado na data AJUSTADA para o orçamento
                            raw_str = f"{data_final_str}{valor_proc}{desc_proc}{banco_nome}{usuario_atual}"
                            h = hashlib.md5(raw_str.encode()).hexdigest()

                            # --- VALIDAÇÃO 1: HASH (Fatura já importada) ---
                            from database import verificar_duplicata
                            if verificar_duplicata(h, usuario_atual):
                                stats["duplicadas_fatura"] += 1
                                continue

                            # --- VALIDAÇÃO 2: MANUAL (Mesmo dia, valor e banco) ---
                            is_manual_dup = False
                            if not df_existente.empty:
                                match = df_existente[
                                    (df_existente['data'].dt.date == data_ajustada) & 
                                    (df_existente['valor'] == valor_proc) & 
                                    (df_existente['banco'] == banco_nome)
                                ]
                                if not match.empty:
                                    is_manual_dup = True

                            if is_manual_dup:
                                stats["duplicadas_manual"] += 1
                            else:
                                stats["novas"] += 1
                                dados_para_inserir.append((
                                    data_final_str, desc_proc, cat_proc, valor_proc, 
                                    banco_nome, usuario_atual, h
                                ))

                        # 2. Execução do salvamento em lote
                        if dados_para_inserir:
                            from psycopg2.extras import execute_batch
                            query = '''
                                INSERT INTO transacoes (data, descricao, categoria, valor, banco, user_id, hash_fatura)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            '''
                            execute_batch(cursor, query, dados_para_inserir)
                            conn.commit()
                            st.success(f"✅ {stats['novas']} novas transações importadas com sucesso!")
                        
                        # 3. Feedbacks detalhados
                        if stats["duplicadas_manual"] > 0:
                            st.info(f"📌 {stats['duplicadas_manual']} transações ignoradas (já existem lançamentos manuais no mesmo dia).")
                        
                        if stats["duplicadas_fatura"] > 0:
                            st.warning(f"🚫 {stats['duplicadas_fatura']} transações já constavam em importações anteriores.")

                        if stats["novas"] == 0 and stats["duplicadas_manual"] == 0 and stats["duplicadas_fatura"] == 0:
                            st.warning("Nenhuma transação nova encontrada no PDF.")

                        # Limpa cache para atualizar página de transações
                        if 'df_transacoes' in st.session_state:
                            del st.session_state.df_transacoes

            except Exception as e:
                if conn: conn.rollback()
                st.error(f"Erro ao salvar no banco: {e}")
            finally:
                if conn: conn.close()
                    
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)