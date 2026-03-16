
import streamlit as st
import pandas as pd
import altair as alt

from database import carregar_transacoes

st.title("📈 Dashboard Financeiro")

df = carregar_transacoes()

if df is None or len(df) == 0:
    st.warning("Sem dados")
    st.stop()

total = df["valor"].sum()

st.metric("Total gasto", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))

resumo = (
    df.groupby("categoria")["valor"]
    .sum()
    .reset_index()
    .sort_values("valor", ascending=False)
)

chart = alt.Chart(resumo).mark_arc().encode(
    theta="valor",
    color="categoria",
    tooltip=["categoria","valor"]
)

st.altair_chart(chart, width="stretch")

st.dataframe(df, width="stretch")
