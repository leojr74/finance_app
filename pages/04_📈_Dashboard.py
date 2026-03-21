import streamlit as st
import pandas as pd
import altair as alt
import datetime
from database import carregar_transacoes, get_gastos_fixos
from ui import apply_global_style
from categorizer import load_categories

# 1. CONFIGURAÇÃO E ESTILO
apply_global_style()

def formatar(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.title("📈 Dashboard Financeiro")

# 2. CARREGAMENTO E LIMPEZA
df = carregar_transacoes()
if df is None or df.empty:
    st.warning("⚠️ Nenhuma transação encontrada.")
    st.stop()

# Conversão de tipos
df["data"] = pd.to_datetime(df["data"], dayfirst=True)
df["valor"] = pd.to_numeric(df["valor"], errors='coerce')

# 3. FILTRO DE CATEGORIAS (ANTI-LIXO + REMOVER DESCONTOS)
try:
    rules = load_categories()
    categorias_json = set(str(v) for v in rules.values() if v)
except:
    categorias_json = set()

categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}
termos_para_ignorar = {"Descontos", "Crédito", "Estorno", "Pagamento", "Ajuste"}

lista_permitida = categorias_json.union(categorias_base) - termos_para_ignorar

# Aplica o filtro global de categorias
df = df[df["categoria"].isin(lista_permitida)]

# 4. LÓGICA DE DATAS: ÚLTIMOS 30 DIAS
hoje = datetime.date.today()
trinta_dias_atras = hoje - datetime.timedelta(days=30)

limite_min = df["data"].min().date()
limite_max = df["data"].max().date()

# Garantir que o valor padrão esteja dentro dos limites do banco
data_inicio_padrao = max(trinta_dias_atras, limite_min)
data_fim_padrao = min(hoje, limite_max)

# 5. INTERFACE DE FILTROS
st.write("---")
c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    periodo = st.date_input(
        "Período Selecionado",
        value=(data_inicio_padrao, data_fim_padrao),
        min_value=limite_min,
        max_value=limite_max
    )

# Aplicação do filtro de período
if isinstance(periodo, tuple) and len(periodo) == 2:
    df_filtrado = df[(df["data"].dt.date >= periodo[0]) & (df["data"].dt.date <= periodo[1])].copy()
else:
    df_filtrado = df[df["data"].dt.date == periodo].copy()

# 6. MÉTRICAS
CATEGORIAS_FIXAS_DB = get_gastos_fixos()

st.write("---")
m1, m2, m3 = st.columns(3)

total = df_filtrado["valor"].sum()
df_fixo = df_filtrado[df_filtrado["categoria"].isin(CATEGORIAS_FIXAS_DB)]
fixo = df_fixo["valor"].sum()
var = total - fixo

m1.metric("Gasto Total (Período)", formatar(total))
m2.metric("Custos Fixos", formatar(fixo))
m3.metric("Custos Variáveis", formatar(var))

# 7. GRÁFICOS
st.write("---")
col_esq, col_dir = st.columns(2)

df_agrupado = df_filtrado.groupby("categoria")["valor"].sum().reset_index()

with col_esq:
    st.subheader("🍕 Distribuição por Categoria")
    pizza = alt.Chart(df_agrupado).mark_arc(innerRadius=50).encode(
        theta=alt.Theta(field="valor", type="quantitative"),
        color=alt.Color(field="categoria", type="nominal", scale=alt.Scale(scheme='tableau10')),
        tooltip=[alt.Tooltip("categoria"), alt.Tooltip("valor", format=",.2f")]
    ).properties(height=400)
    st.altair_chart(pizza, use_container_width=True)

with col_dir:
    st.subheader("📊 Maiores Gastos")
    df_barras = df_agrupado.sort_values("valor", ascending=False)
    barras = alt.Chart(df_barras).mark_bar().encode(
        x=alt.X("valor:Q", title="Total (R$)"),
        y=alt.Y("categoria:N", sort="-x", title=None),
        color=alt.Color("categoria:N", legend=None, scale=alt.Scale(scheme='tableau10')),
        tooltip=[alt.Tooltip("categoria"), alt.Tooltip("valor", format=",.2f")]
    ).properties(height=400)
    st.altair_chart(barras, width="stretch")

st.write("---")
st.caption("v2.5 | Dashboard Dinâmico (Últimos 30 dias)")