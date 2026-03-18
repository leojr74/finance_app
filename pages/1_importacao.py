import streamlit as st
import pandas as pd
from datetime import date
import sqlite3
import hashlib

from parser_router import extract_transactions_auto
from database import salvar_transacoes

st.title("📥 Importação de Faturas")

# --------------------------------------------------
# período da fatura
# --------------------------------------------------

st.subheader("Período da fatura")

col1, col2 = st.columns(2)

with col1:
    data_inicio = st.date_input(
        "Data inicial",
        value=date.today().replace(day=1)
    )

with col2:
    data_fim = st.date_input(
        "Data final",
        value=date.today()
    )

if data_fim < data_inicio:
    st.error("Data final não pode ser anterior à data inicial")
    st.stop()

# --------------------------------------------------
# upload PDF
# --------------------------------------------------

uploaded = st.file_uploader("Upload da fatura PDF", type="pdf")

if uploaded:

    with open("temp.pdf", "wb") as f:
        f.write(uploaded.read())

    result = extract_transactions_auto(
        pdf_path="temp.pdf",
        data_inicio=data_inicio,
        data_fim=data_fim
    )

    if result and "transactions" in result:

        df = pd.DataFrame(result["transactions"])
        
        

        # --------------------------------------------------
        # normalizar dados
        # --------------------------------------------------

        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

        df = df.sort_values("data").reset_index(drop=True)

        # --------------------------------------------------
        # dataframe apenas para exibição
        # --------------------------------------------------

        df_display = df.copy()

        df_display["data"] = df_display["data"].dt.strftime("%d/%m/%Y")

        df_display["valor"] = df_display["valor"].map(
            lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
        )

        st.success(f"{len(df)} transações extraídas")

        st.dataframe(df_display, width="stretch")

        # --------------------------------------------------
        # total
        # --------------------------------------------------

        total = df["valor"].sum()

        st.success(
            f"Total das transações extraídas: R$ {total:,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )

        # --------------------------------------------------
        # gerar hash da fatura
        # --------------------------------------------------

        banco = result.get("bank", "DESCONHECIDO")

        hash_base = f"{banco}_{data_inicio}_{data_fim}"
        hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

        conn = sqlite3.connect("transacoes.db")
        cursor = conn.cursor()

        
        # --------------------------------------------------
        # botão salvar
        # --------------------------------------------------

        if st.button("💾 Salvar no banco"):

            inseridas = 0

            for _, row in df.iterrows():

                cursor.execute("""
                    SELECT 1
                    FROM transacoes
                    WHERE data = ?
                    AND descricao = ?
                    AND valor = ?
                    AND banco = ?
                """, (
                    row["data"].strftime("%Y-%m-%d"),
                    row["descricao"],
                    row["valor"],
                    banco
                ))

                existe = cursor.fetchone()

                if not existe:

                    cursor.execute("""
                        INSERT INTO transacoes
                        (data, descricao, valor, categoria, banco, hash_fatura)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        row["data"].strftime("%Y-%m-%d"),
                        row["descricao"],
                        row["valor"],
                        row.get("categoria", "Sem categoria"),
                        banco,
                        hash_fatura
                    ))

                    inseridas += 1

            conn.commit()
            conn.close()

            # Se o cache da página de Gerenciamento existir, nós o deletamos.
            # Isso garante que a próxima vez que você mudar de aba, o sistema 
            # carregue as transações que acabamos de inserir.

            if "df_transacoes" in st.session_state:
                del st.session_state.df_transacoes
                
            # -------------------------------

            st.success(f"{inseridas} novas transações salvas")
            st.session_state.confirmar_duplicata = False