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
                    
                    # 1. Carrega o histórico de forma limpa
                    df_h = pd.read_sql_query("SELECT data, valor, banco, hash_fatura FROM transacoes", conn)
                    
                    # Normalização crítica de tipos
                    if not df_h.empty:
                        df_h['data'] = pd.to_datetime(df_h['data']).dt.date
                        df_h['valor'] = df_h['valor'].astype(float).round(2)
                        df_h['banco'] = df_h['banco'].astype(str)

                    inseridas = 0
                    ignoradas_manual = 0
                    ignoradas_duplicadas = 0

                    df_para_salvar = st.session_state.df_transacoes
                    banco_atual = result.get('bank', 'Desconhecido')

                    for _, row in df_para_salvar.iterrows():
                        t_data = pd.to_datetime(row['data'], dayfirst=True).date()
                        t_valor = round(float(row['valor']), 2)
                        t_desc = str(row['descricao'])
                        
                        # 2. COMPARAÇÃO DIRETA (Sem .any() genérico)
                        # Criamos um sub-dataframe apenas com o que coincide EXATAMENTE
                        if not df_h.empty:
                            # Filtro para Manual: Data + Valor + Banco + Flag Manual
                            conflito_manual = df_h[
                                (df_h['data'] == t_data) & 
                                (df_h['valor'] == t_valor) & 
                                (df_h['banco'] == banco_atual) & 
                                (df_h['hash_fatura'] == 'MANUAL_ENTRY')
                            ]
                            
                            # Filtro para Mesma Fatura: Data + Descrição + Valor + Mesmo Hash
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

                        # 3. Se passou pelos filtros, insere
                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (t_data, t_desc, t_valor, row.get("categoria", "Sem categoria"), banco_atual, hash_fatura))
                        inseridas += 1

                    conn.commit()
                    st.success(f"✅ Concluído! {inseridas} inseridas.")
                    if ignoradas_manual > 0:
                        st.warning(f"📌 {ignoradas_manual} bloqueadas por regra manual.")
                    
                    if "df_transacoes" in st.session_state:
                        del st.session_state.df_transacoes
                
                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"Erro: {e}")
                finally:
                    if conn: conn.close()
                    

    finally:
        # LIMPEZA OBRIGATÓRIA: Deleta o arquivo temporário após o uso, 
        # mesmo que ocorra um erro no processamento.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)