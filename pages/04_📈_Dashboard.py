import streamlit as st
import pandas as pd
import altair as alt
from database import carregar_transacoes, get_gastos_fixos
from ui import apply_global_style

apply_global_style()

def formatar(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📈 Dashboard Financeiro")

# 1. CARREGAMENTO E LIMPEZA
df = carregar_transacoes()
if df is None or df.empty:
    st.warning("⚠️ Nenhuma transação encontrada.")
    st.stop()

df = df[df["categoria"] != "Descontos"]
df["data"] = pd.to_datetime(df["data"])

# 2. FILTROS
st.write("---")
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    min_d, max_d = df["data"].min().date(), df["data"].max().date()
    periodo = st.date_input("Período", value=(min_d, max_d), min_value=min_d, max_value=max_d)

if isinstance(periodo, tuple) and len(periodo) == 2:
    df_filtrado = df[(df["data"].dt.date >= periodo[0]) & (df["data"].dt.date <= periodo[1])]
else:
    df_filtrado = df

# 3. MÉTRICAS
CATEGORIAS_FIXAS = get_gastos_fixos()
m1, m2, m3 = st.columns(3)
total = df_filtrado["valor"].sum()
fixo = df_filtrado[df_filtrado["categoria"].isin(CATEGORIAS_FIXAS)]["valor"].sum()
var = total - fixo

m1.metric("Gasto Total", formatar(total))
m2.metric("Custos Fixos", formatar(fixo))
m3.metric("Custos Variáveis", formatar(var))

# --- 4. GRÁFICOS (A PARTE QUE ESTAVA "ZOADA") ---
st.write("---")
col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("🍕 Distribuição por Categoria")
    
    # 🔥 A CORREÇÃO: Agrupar por categoria e somar os valores antes de mandar para o gráfico
    df_pizza = df_filtrado.groupby("categoria")["valor"].sum().reset_index()
    
    pizza = alt.Chart(df_pizza).mark_arc(innerRadius=50).encode(
        theta=alt.Theta(field="valor", type="quantitative"),
        color=alt.Color(field="categoria", type="nominal", legend=alt.Legend(title="Categorias")),
        tooltip=[
            alt.Tooltip("categoria", title="Categoria"),
            alt.Tooltip("valor", title="Total (R$)", format=",.2f")
        ]
    ).properties(height=400)
    
    st.altair_chart(pizza, use_container_width=True)

with col_dir:
    st.subheader("📊 Maiores Gastos")
    # Agrupa também para o gráfico de barras para evitar repetições
    df_barras = df_filtrado.groupby("categoria")["valor"].sum().reset_index().sort_values("valor", ascending=False)
    
    barras = alt.Chart(df_barras).mark_bar().encode(
        x=alt.X("valor:Q", title="Total Gasto (R$)"),
        y=alt.Y("categoria:N", sort="-x", title="Categoria"),
        color=alt.Color("categoria:N", legend=None),
        tooltip=["categoria", alt.Tooltip("valor", format=",.2f")]
    ).properties(height=400)
    
    st.altair_chart(barras, use_container_width=True)