import streamlit as st
import pandas as pd
from datetime import date
from ui import apply_global_style



from database import (
    carregar_transacoes,
    criar_tabela_orcamentos,
    salvar_orcamento,
    carregar_orcamentos
)

st.set_page_config(page_title="Orçamento", layout="wide")
apply_global_style()

st.title("📊 Planejamento de Orçamento")

# garante que a tabela existe
criar_tabela_orcamentos()

CATEGORIAS_FIXAS = [
    "Alimentação",
    "Assinaturas",
    "Moradia",
    "Saúde",
    "Supermercado",
    "Transporte",
    "Viagem"
]

# -----------------------------
# Seleção de período
# -----------------------------

col1, col2 = st.columns(2)

with col1:
    mes = st.selectbox("Mês", list(range(1, 13)), index=date.today().month - 1)

with col2:
    ano = st.number_input("Ano", value=date.today().year)

if st.button("📅 Copiar orçamento do mês anterior"):

    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1

    df_ant = carregar_orcamentos(mes_ant, ano_ant)

    if df_ant.empty:
        st.warning("Nenhum orçamento encontrado no mês anterior")
    else:
        for _, row in df_ant.iterrows():
            salvar_orcamento(
                row["categoria"],
                row["valor"],
                mes,
                ano
            )

        st.success("Orçamento copiado com sucesso!")
        st.rerun()

# -----------------------------
# Carregar transações
# -----------------------------
df = carregar_transacoes()
df = df[df["categoria"] != "Descontos"]

if df is None or df.empty:
    st.warning("⚠️ Nenhuma transação encontrada.")
    st.stop()

df["data"] = pd.to_datetime(df["data"])

df_mes = df[
    (df["data"].dt.month == mes) &
    (df["data"].dt.year == ano)
]

df["mes"] = df["data"].dt.to_period("M")
media_categoria = df.groupby(["categoria", "mes"])["valor"].sum().reset_index()
media_categoria = media_categoria.groupby("categoria")["valor"].mean().reset_index()
media_categoria.rename(columns={"valor": "media"}, inplace=True)
media_categoria["media"] = media_categoria["media"].round(2).astype(float)

# -----------------------------
# Gastos reais
# -----------------------------
gastos = df_mes.groupby("categoria")["valor"].sum().reset_index()

# -----------------------------
# Orçamentos salvos
# -----------------------------
orc = carregar_orcamentos(mes, ano)

# -----------------------------
# Merge
# -----------------------------
df_final = pd.merge(
    gastos,
    orc,
    on="categoria",
    how="outer",
    suffixes=("_real", "_orc")
)

# adiciona sugestão automática (média)
df_final = pd.merge(
    df_final,
    media_categoria,
    on="categoria",
    how="left"
)

df_final["valor_orc"] = pd.to_numeric(df_final["valor_orc"], errors="coerce")
df_final["valor_real"] = pd.to_numeric(df_final["valor_real"], errors="coerce")

df_final = df_final.assign(
    valor_orc=lambda x: x["valor_orc"].where(x["valor_orc"].notna(), 0),
    valor_real=lambda x: x["valor_real"].where(x["valor_real"].notna(), 0),
)

df_final["media"] = pd.to_numeric(df_final["media"], errors="coerce")

# ==============================
# TABELA PRINCIPAL
# ==============================

st.subheader("📊 Orçamento por Categoria")

# garante ordem das colunas
df_final = df_final[["categoria", "media", "valor_orc", "valor_real"]]

df_edit = st.data_editor(
    df_final,
    width="stretch",
    hide_index=True,
    column_config={
        "categoria": "Categoria",
        "media": st.column_config.NumberColumn("Média mensal (R$)", format="%.2f", disabled=True),
        "valor_orc": st.column_config.NumberColumn("Orçamento (R$)", format="%.2f"),
        "valor_real": st.column_config.NumberColumn("Gasto (R$)", format="%.2f", disabled=True),
    }
)

# ==============================
# TOTAIS
# ==============================

total_media = df_edit["media"].sum()
total_orc = df_edit["valor_orc"].sum()
total_real = df_edit["valor_real"].sum()

# ==============================
# FIXO vs VARIÁVEL
# ==============================

df_fixos = df_edit[df_edit["categoria"].isin(CATEGORIAS_FIXAS)]
df_variaveis = df_edit[~df_edit["categoria"].isin(CATEGORIAS_FIXAS)]

fixo_real = df_fixos["valor_real"].sum()
variavel_real = df_variaveis["valor_real"].sum()

fixo_orc = df_fixos["valor_orc"].sum()
variavel_orc = df_variaveis["valor_orc"].sum()

# ==============================
# MÉTRICAS (visual profissional)
# ==============================

st.divider()

col1, col2, col3 = st.columns(3)

def formatar(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

col1.metric("📊 Média Total", formatar(total_media))
col2.metric("🎯 Orçamento Total", formatar(total_orc))
col3.metric("💸 Gasto Total", formatar(total_real))

st.divider()
st.subheader("📊 Custos Fixos vs Variáveis")

col1, col2 = st.columns(2)

col1.metric("🏠 Fixos (Real)", formatar(fixo_real))
col1.metric("🎯 Fixos (Orçado)", formatar(fixo_orc))

col2.metric("📉 Variáveis (Real)", formatar(variavel_real))
col2.metric("🎯 Variáveis (Orçado)", formatar(variavel_orc))

# ==============================
# SALDO + ALERTA
# ==============================

saldo = total_orc - total_real

st.write("")

if saldo < 0:
    st.error(f"🚨 Orçamento estourado! Saldo: {formatar(saldo)}")
elif saldo < total_orc * 0.2:
    st.warning(f"⚠️ Atenção! Saldo restante: {formatar(saldo)}")
else:
    st.success(f"✅ Orçamento sob controle. Saldo: {formatar(saldo)}")

# -----------------------------
# Salvar
# -----------------------------
if st.button("💾 Salvar orçamento"):

    for _, row in df_edit.iterrows():

        categoria = row.get("categoria")
        valor = row.get("valor_orc")

        # validações
        if not categoria:
            continue

        try:
            valor = float(valor)
        except:
            valor = 0

        salvar_orcamento(
            categoria,
            valor,
            mes,
            ano
        )

    st.success("✅ Orçamento salvo com sucesso!")
    st.rerun()

# -----------------------------
# Comparação visual
# -----------------------------
st.write("---")
st.subheader("📈 Orçado vs Realizado")

for _, row in df_edit.iterrows():

    categoria = row["categoria"]
    real = row["valor_real"]
    orcamento = row["valor_orc"]

    if orcamento == 0:
        continue

    proporcao = real / orcamento

    if proporcao > 1:
        emoji = "🔴"
        status = "Estourado"
    elif proporcao > 0.8:
        emoji = "🟠"
        status = "Atenção"
    else:
        emoji = "🟢"
        status = "Ok"

    st.markdown(f"### {emoji} {categoria} — {status}")

    st.progress(min(proporcao, 1.0))

    st.caption(
        f"Gasto: R$ {real:,.2f} | Orçamento: R$ {orcamento:,.2f}"
        .replace(",", "X").replace(".", ",").replace("X", ".")
    )

import altair as alt

st.divider()
st.subheader("📊 Orçado vs Real por Categoria")

df_chart = df_edit.copy()

# garante tipos numéricos
df_chart["valor_real"] = pd.to_numeric(df_chart["valor_real"], errors="coerce")
df_chart["valor_orc"] = pd.to_numeric(df_chart["valor_orc"], errors="coerce")

# 🔥 transforma manualmente (sem transform_fold)
df_chart_long = pd.melt(
    df_chart,
    id_vars=["categoria"],
    value_vars=["valor_real", "valor_orc"],
    var_name="Tipo",
    value_name="Valor"
)

# deixa nomes mais bonitos
df_chart_long["Tipo"] = df_chart_long["Tipo"].map({
    "valor_real": "Gasto",
    "valor_orc": "Orçamento"
})

chart = alt.Chart(df_chart_long).mark_bar().encode(
    x=alt.X('categoria:N', sort='-y', title="Categoria"),
    y=alt.Y('Valor:Q', title="Valor (R$)"),
    color=alt.Color('Tipo:N', title="Tipo"),
    tooltip=['categoria:N', 'Tipo:N', 'Valor:Q']
).properties(height=400)

st.altair_chart(chart, width="stretch")