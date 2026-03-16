
import streamlit as st
import pandas as pd
from parser_router import extract_transactions_auto
from database import salvar_transacoes

st.title("📥 Importação de Faturas")

uploaded = st.file_uploader("Upload da fatura PDF", type="pdf")

mes = st.number_input("Mês da fatura", min_value=1, max_value=12, value=1)
ano = st.number_input("Ano da fatura", min_value=2020, max_value=2035, value=2026)

if uploaded:

    with open("temp.pdf", "wb") as f:
        f.write(uploaded.read())

    result = extract_transactions_auto(
        pdf_path="temp.pdf",
        mes_fatura=mes,
        ano_fatura=ano
    )

    if result and "transactions" in result:

        df = pd.DataFrame(result["transactions"])

        st.success(f"{len(df)} transações extraídas")

        st.dataframe(df, width="stretch")

        if st.button("💾 Salvar no banco"):
            ok, qtd = salvar_transacoes(
                df,
                banco=result.get("bank","DESCONHECIDO"),
                mes_fatura=mes,
                ano_fatura=ano
            )

            if ok:
                st.success(f"{qtd} transações salvas")
            else:
                st.error("Erro ao salvar")
