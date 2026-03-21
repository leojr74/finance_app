import streamlit as st
import pandas as pd
import hashlib
import os
import psycopg2
import tempfile
from datetime import date
from ui import apply_global_style
from database import conectar

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
    # Criamos um arquivo temporário com nome único e aleatório
    # delete=False permite que o arquivo seja fechado e aberto pelo parser_router
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded.read())
        tmp_path = tmp_file.name # Caminho único gerado pelo sistema (ex: C:\Temp\tmpxyz.pdf)

    try:
        # O parser_router agora recebe o caminho ÚNICO e SEGURO
        result = extract_transactions_auto(
            pdf_path=tmp_path,
            data_inicio=data_inicio,
            data_fim=data_fim
        )

        if result and "transactions" in result:
            df = pd.DataFrame(result["transactions"])

            # --------------------------------------------------
            # Normalizar dados
            # --------------------------------------------------
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df = df.sort_values("data").reset_index(drop=True)

            # --------------------------------------------------
            # Mapeamento para nomes amigáveis
            # --------------------------------------------------
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

            banco = mapeamento_nomes.get(id_tecnico, id_tecnico.upper())

            # --------------------------------------------------
            # Dataframe apenas para exibição
            # --------------------------------------------------
            colunas_desejadas = ["data", "descricao", "valor"]
            colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
            
            df_display = df[colunas_existentes].copy()

            st.success(f"{len(df)} transações extraídas de: **{banco}**")

            st.dataframe(
                df_display, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "descricao": "Descrição",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
                }
            )

            total = df["valor"].sum()
            st.info(f"Total das transações: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # Hash da fatura para controle de lote
            hash_base = f"{banco}_{data_inicio}_{data_fim}"
            hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

            # --------------------------------------------------
            # Botão salvar
            # --------------------------------------------------
            if st.button("💾 Salvar no banco"):
                try:
                    conn = conectar()
                    cursor = conn.cursor()
                    
                    # 1. CARREGA O HISTÓRICO DO BANCO (Para evitar o erro 'not defined')
                    # Buscamos tudo o que já existe para comparar
                    df_historico = pd.read_sql_query("SELECT data, descricao, valor, hash_fatura FROM transacoes", conn)
                    df_historico['data'] = pd.to_datetime(df_historico['data']).dt.date

                    inseridas = 0
                    ignoradas_manual = 0
                    ignoradas_duplicadas = 0

                    # 2. LOOP DE PROCESSAMENTO (df_transacoes vem do st.session_state)
                    df_para_salvar = st.session_state.df_transacoes
                    
                    for _, row in df_para_salvar.iterrows():
                        transacao_data = pd.to_datetime(row['data'], dayfirst=True).date()
                        descricao = str(row['descricao'])
                        valor = float(row['valor'])
                        
                        # Verificação de duplicidade
                        existe_manual = False
                        existe_neste_pdf = False

                        if not df_historico.empty:
                            # Regra 1: Prioridade Manual (Mesma data, banco e valor com hash 'MANUAL_ENTRY')
                            # Nota: Adicionei a verificação de banco se você tiver essa coluna no df_historico
                            mask_manual = (df_historico['data'] == transacao_data) & \
                                          (df_historico['valor'] == valor) & \
                                          (df_historico['hash_fatura'] == 'MANUAL_ENTRY')
                            
                            if mask_manual.any():
                                existe_manual = True

                            # Regra 2: Evitar re-importar o mesmo PDF (Mesmo hash_fatura)
                            mask_pdf = (df_historico['data'] == transacao_data) & \
                                       (df_historico['descricao'] == descricao) & \
                                       (df_historico['valor'] == valor) & \
                                       (df_historico['hash_fatura'] == hash_fatura)
                            
                            if mask_pdf.any():
                                existe_neste_pdf = True

                        # 3. TOMADA DE DECISÃO
                        if existe_manual:
                            ignoradas_manual += 1
                            continue
                        
                        if existe_neste_pdf:
                            ignoradas_duplicadas += 1
                            continue

                        # Se chegou aqui, é uma transação nova ou uma das 4 iguais do mesmo PDF
                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            transacao_data,
                            descricao,
                            valor,
                            row.get("categoria", "Sem categoria"),
                            banco,
                            hash_fatura
                        ))
                        inseridas += 1

                    conn.commit()
                    st.success(f"✅ Processamento concluído: {inseridas} novas transações.")
                    
                    if ignoradas_manual > 0:
                        st.warning(f"📌 {ignoradas_manual} itens descartados (lançamento manual detectado).")
                    
                    if "df_transacoes" in st.session_state:
                        del st.session_state.df_transacoes

                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"Erro ao acessar o banco de dados: {e}")
                finally:
                    if conn: conn.close()
                    

    finally:
        # LIMPEZA OBRIGATÓRIA: Deleta o arquivo temporário após o uso, 
        # mesmo que ocorra um erro no processamento.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)