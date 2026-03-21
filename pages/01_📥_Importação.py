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
            # Criamos o DataFrame e garantimos as colunas IMEDIATAMENTE
            df = pd.DataFrame(result["transactions"])
            
            # Normalização crítica
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            df["descricao"] = df["descricao"].astype(str).str.upper()
            
            df = df.sort_values("data").reset_index(drop=True)
            
            # SALVAMOS NO STATE PARA O BOTÃO ENCONTRAR
            st.session_state.df_transacoes = df

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

            st.success(f"{len(df)} transações extraídas de: **{banco_nome}**")

            st.dataframe(
                df[["data", "descricao", "valor"]], 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "descricao": "Descrição",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
                }
            )

            hash_base = f"{banco_nome}_{data_inicio}_{data_fim}"
            hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

            if st.button("💾 Salvar no banco"):
                try:
                    conn = conectar()
                    cursor = conn.cursor()
                    
                    # 1. Busca histórico para cruzamento (incluindo descrição e banco)
                    df_h = pd.read_sql_query("SELECT data, valor, banco, hash_fatura, descricao FROM transacoes", conn)
                    
                    if not df_h.empty:
                        df_h['data'] = pd.to_datetime(df_h['data']).dt.date
                        df_h['valor'] = df_h['valor'].astype(float).round(2)
                        df_h['banco'] = df_h['banco'].astype(str)
                        df_h['descricao'] = df_h['descricao'].astype(str).str.upper()

                    inseridas = 0
                    ignoradas_manual = 0
                    ignoradas_duplicadas = 0

                    # Pegamos os dados que salvamos lá em cima
                    dados_para_salvar = st.session_state.df_transacoes

                    for _, row in dados_para_salvar.iterrows():
                        t_data = row['data'].date()
                        t_valor = round(float(row['valor']), 2)
                        t_desc = str(row['descricao'])
                        
                        if not df_h.empty:
                            # Filtro Manual: Precisa bater DATA + VALOR + BANCO
                            conflito_manual = df_h[
                                (df_h['data'] == t_data) & 
                                (df_h['valor'] == t_valor) & 
                                (df_h['banco'] == banco_nome) & 
                                (df_h['hash_fatura'] == 'MANUAL_ENTRY')
                            ]
                            
                            # Filtro Duplicado: Já existe neste PDF?
                            conflito_pdf = df_h[
                                (df_h['hash_fatura'] == hash_fatura) & 
                                (df_h['descricao'] == t_desc) &
                                (df_h['valor'] == t_valor)
                            ]
                            
                            if not conflito_manual.empty:
                                ignoradas_manual += 1
                                continue
                                
                            if not conflito_pdf.empty:
                                ignoradas_duplicadas += 1
                                continue

                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (t_data, t_desc, t_valor, row.get("categoria", "Sem categoria"), banco_nome, hash_fatura))
                        inseridas += 1

                    conn.commit()
                    st.success(f"✅ Processamento concluído: {inseridas} novas transações.")
                    
                    if ignoradas_manual > 0:
                        st.warning(f"📌 {ignoradas_manual} itens ignorados por já existirem como Manual.")
                    
                    if "df_transacoes" in st.session_state:
                        del st.session_state.df_transacoes

                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    if conn: conn.close()
                    
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)