import streamlit as st
import pandas as pd
import hashlib
import os
import tempfile
from datetime import date
from ui import apply_global_style
from database import conectar

# --- PROTEÇÃO DE ACESSO ---
if not st.session_state.get("authentication_status"):
    st.warning("Por favor, faça login na Home para acessar esta página.")
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
            
            # Normalização
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

            # Hash da fatura
            hash_base = f"{banco_nome}_{data_inicio}_{data_fim}"
            hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

            # --------------------------------------------------
            # Botão salvar (MODIFICADO PARA USER_ID)
            # --------------------------------------------------
            if st.button("💾 Salvar no banco"):
                try:
                    conn = conectar()
                    if not conn:
                        st.error("Não foi possível conectar ao banco.")
                        st.stop()
                    
                    cursor = conn.cursor()
                    
                    # BUSCA APENAS O HISTÓRICO DESTE USUÁRIO
                    query_h = "SELECT data, valor, banco, hash_fatura, descricao FROM transacoes WHERE user_id = %s"
                    df_h = pd.read_sql_query(query_h, conn, params=(usuario_atual,))
                    
                    if not df_h.empty:
                        df_h['data'] = pd.to_datetime(df_h['data']).dt.date
                        df_h['valor'] = df_h['valor'].astype(float).round(2)
                        df_h['banco'] = df_h['banco'].astype(str)

                    inseridas = 0
                    ignoradas_manual = 0
                    
                    for _, row in st.session_state.df_transacoes.iterrows():
                        t_data = row['data'].date()
                        t_valor = round(float(row['valor']), 2)
                        t_desc = str(row['descricao'])
                        
                        # Filtro contra lançamentos manuais DESTE usuário
                        if not df_h.empty:
                            conflito_manual = df_h[
                                (df_h['data'] == t_data) & 
                                (df_h['valor'] == t_valor) & 
                                (df_h['banco'] == banco_nome) & 
                                (df_h['hash_fatura'] == 'MANUAL_ENTRY')
                            ]
                            
                            if not conflito_manual.empty:
                                ignoradas_manual += 1
                                continue

                        # INSERÇÃO INCLUINDO O USER_ID
                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (t_data, t_desc, t_valor, row.get("categoria", "Sem categoria"), banco_nome, hash_fatura, usuario_atual))
                        inseridas += 1

                    conn.commit()
                    st.success(f"✅ {inseridas} transações salvas para {usuario_atual}!")
                    
                    if ignoradas_manual > 0:
                        st.warning(f"📌 {ignoradas_manual} transações ignoradas por já existirem no lançamento manual.")
                    
                    del st.session_state.df_transacoes
                    
                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    if conn: conn.close()
                    
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)