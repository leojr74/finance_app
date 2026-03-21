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
                    
                    inseridas = 0
                    ignoradas_manual = 0
                    ignoradas_duplicadas = 0

                    for _, row in df.iterrows():
                        data_str = row["data"].strftime("%Y-%m-%d")
                        valor = row["valor"]
                        descricao = row["descricao"]
                        
                        # 1. Busca por lançamento MANUAL Prévio
                        cursor.execute("""
                            SELECT 1 FROM transacoes 
                            WHERE data = %s 
                              AND valor = %s 
                              AND banco = %s 
                              AND hash_fatura = 'MANUAL_ENTRY'
                        """, (data_str, valor, banco))
                        
                        if cursor.fetchone():
                            ignoradas_manual += 1
                            continue

                        # 2. Busca por importação de PDF já realizada
                        cursor.execute("""
                            SELECT 1 FROM transacoes
                            WHERE data = %s 
                              AND descricao = %s 
                              AND valor = %s 
                              AND banco = %s
                        """, (data_str, descricao, valor, banco))

                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                data_str,
                                descricao,
                                valor,
                                row.get("categoria", "Sem categoria"),
                                banco,
                                hash_fatura
                            ))
                            inseridas += 1
                        else:
                            ignoradas_duplicadas += 1

                    conn.commit()
                    conn.close()

                    if "df_transacoes" in st.session_state:
                        del st.session_state.df_transacoes
                    
                    st.success(f"✅ Processamento concluído: {inseridas} novas transações.")
                    
                    if ignoradas_manual > 0:
                        st.warning(f"📌 {ignoradas_manual} itens descartados (lançamento manual detectado).")
                    
                    if ignoradas_duplicadas > 0:
                        st.info(f"ℹ️ {ignoradas_duplicadas} itens já constavam no histórico.")
                    
                except psycopg2.errors.UniqueViolation:
                    # Se o erro for de "Chave Duplicada", avisamos o usuário com calma
                    st.warning("⚠️ Esta fatura já foi importada anteriormente (Hash duplicado).")
                    conn.rollback() # Cancela a transação que deu erro
                except Exception as e:
                    st.error(f"Erro ao acessar o banco de dados: {e}")
                finally:
                    conn.close()
                    

    finally:
        # LIMPEZA OBRIGATÓRIA: Deleta o arquivo temporário após o uso, 
        # mesmo que ocorra um erro no processamento.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)