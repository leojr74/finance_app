import streamlit as st
import pandas as pd
import altair as alt
from database import carregar_transacoes

# Configuração da página
st.set_page_config(page_title="Dashboard Financeiro", layout="wide")

st.title("📈 Dashboard Financeiro")

# 1. CARREGAMENTO DOS DADOS
df = carregar_transacoes()

if df is None or df.empty:
    st.warning("⚠️ Nenhuma transação encontrada no banco de dados.")
    st.stop()

# Garantir tipo datetime para os cálculos e filtros
df["data"] = pd.to_datetime(df["data"])

# --- ÁREA DE FILTROS (3 COLUNAS) ---
st.write("---")
c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    # Datas limites baseadas no que existe no banco
    datas_limite = (df["data"].min().date(), df["data"].max().date())
    periodo = st.date_input("📅 Filtrar por período", value=datas_limite, format="DD/MM/YYYY")

with c2:
    # Lista de categorias únicas
    lista_filtro = sorted(df["categoria"].unique().tolist())
    if "Sem categoria" not in lista_filtro:
        lista_filtro.append("Sem categoria")
    
    # Default vazio [] para manter o visual limpo como na página de transações
    categorias_sel = st.multiselect("📂 Filtrar por categoria", options=lista_filtro, default=[])

with c3:
    # Lista de bancos/cartões (já padronizados pelo bank_detector e importação)
    lista_bancos = sorted(df["banco"].unique().tolist())
    bancos_sel = st.multiselect("🏦 Filtrar por Banco/Cartão", options=lista_bancos, default=[])

# --- LÓGICA DE FILTRAGEM ---
df_filtrado = df.copy()

if isinstance(periodo, tuple) and len(periodo) == 2:
    start_date, end_date = periodo
    df_filtrado = df_filtrado[(df_filtrado["data"].dt.date >= start_date) & (df_filtrado["data"].dt.date <= end_date)]

if categorias_sel:
    df_filtrado = df_filtrado[df_filtrado["categoria"].isin(categorias_sel)]

if bancos_sel:
    df_filtrado = df_filtrado[df_filtrado["banco"].isin(bancos_sel)]

# --- VALIDAÇÃO ---
if df_filtrado.empty:
    st.info("🔎 Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# --- CÁLCULOS DE MÉTRICAS ---
total_gasto = df_filtrado["valor"].sum()
# Conta quantos meses únicos existem no recorte filtrado
n_meses = len(df_filtrado["data"].dt.to_period("M").unique())
media_geral = total_gasto / n_meses if n_meses > 0 else total_gasto

# --- EXIBIÇÃO DE MÉTRICAS ---
st.write("---")
m1, m2, m3 = st.columns(3)
# Formatação de moeda padrão brasileiro
m1.metric("Total Gasto", f"R$ {total_gasto:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
m2.metric("Média Mensal Geral", f"R$ {media_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
m3.metric("Meses Analisados", n_meses)

st.write("---")

# --- GRÁFICOS ---
col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("🍕 Distribuição por Categoria")
    resumo_pizza = df_filtrado.groupby("categoria")["valor"].sum().reset_index()
    pizza = alt.Chart(resumo_pizza).mark_arc(innerRadius=50).encode(
        theta="valor:Q", 
        color="categoria:N", 
        tooltip=["categoria", alt.Tooltip("valor", format=",.2f")]
    ).properties(height=350)
    st.altair_chart(pizza, use_container_width=True)

with col_dir:
    st.subheader("📊 Média Mensal por Categoria")
    resumo_categoria = df_filtrado.groupby("categoria")["valor"].sum().reset_index()
    resumo_categoria["media_mensal"] = resumo_categoria["valor"] / n_meses
    
    chart_media = alt.Chart(resumo_categoria).mark_bar().encode(
        x=alt.X("media_mensal:Q", title="Média Mensal (R$)"),
        y=alt.Y("categoria:N", sort="-x", title="Categoria"),
        color=alt.Color("categoria:N", legend=None),
        tooltip=[alt.Tooltip("categoria"), alt.Tooltip("media_mensal", format=",.2f")]
    ).properties(height=350)
    st.altair_chart(chart_media, use_container_width=True)

st.write("---")
st.subheader("📅 Evolução dos Gastos Totais (Mês a Mês)")
evolucao = df_filtrado.copy()
evolucao["mes"] = evolucao["data"].dt.to_period("M").astype(str)
resumo_mes = evolucao.groupby("mes")["valor"].sum().reset_index()

barras_mes = alt.Chart(resumo_mes).mark_bar(color="#0068c9").encode(
    x=alt.X("mes:N", title="Mês/Ano"),
    y=alt.Y("valor:Q", title="Soma das Transações (R$)"),
    tooltip=[alt.Tooltip("mes", title="Mês"), alt.Tooltip("valor", format=",.2f", title="Total")]
).properties(height=300)

st.altair_chart(barras_mes, use_container_width=True)