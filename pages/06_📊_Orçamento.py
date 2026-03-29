import streamlit as st
import pandas as pd
from datetime import date
import altair as alt
from database import (
    carregar_transacoes,
    criar_tabela,
    get_authenticator,
    salvar_orcamento,
    get_gastos_fixos,
    carregar_orcamentos
)
from ui import apply_global_style

st.set_page_config(
    page_title="Planejamento de Orçamento",
    page_icon="📊",
    layout="wide"
)

from database import check_auth
usuario_atual = check_auth()
if usuario_atual is None:
    st.warning("Sessão expirada. Por favor, faça login na Home.")
    st.stop() 
apply_global_style()
st.title("📊 Planejamento de Orçamento")

# Garante a estrutura do banco
criar_tabela()

# Puxa categorias configuradas na Home (Passando o usuário atual)
CATEGORIAS_FIXAS = get_gastos_fixos(usuario_atual)

# -----------------------------
# 1. Seleção de Período
# -----------------------------
col1, col2 = st.columns(2)
with col1:
    mes = st.selectbox("Mês", list(range(1, 13)), index=date.today().month - 1)
with col2:
    ano = st.number_input("Ano", value=date.today().year)

# Botão de cópia (Filtrado por usuário)
if st.button("📅 Copiar orçamento do mês anterior"):
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    df_ant = carregar_orcamentos(mes_ant, ano_ant, usuario_atual)
    if not df_ant.empty:
        for _, row in df_ant.iterrows():
            # Salva associando ao usuário atual
            salvar_orcamento(row["categoria"], row["valor"], mes, ano, usuario_atual)
        st.success("Copiado com sucesso!")
        st.rerun()

# -----------------------------
# 2. Processamento de Dados (Fiel à sua lógica)
# -----------------------------
df_trans = carregar_transacoes(usuario_atual)
if df_trans is None:
    df_trans = pd.DataFrame(columns=["data", "categoria", "valor"])

df_trans = df_trans[df_trans["categoria"] != "Descontos"]
df_trans["data"] = pd.to_datetime(df_trans["data"], errors="coerce")

# Cálculo da Média Histórica
if not df_trans.empty:
    df_trans["mes_ref"] = df_trans["data"].dt.to_period("M")
    media_hist = df_trans.groupby(["categoria", "mes_ref"])["valor"].sum().reset_index()
    media_hist = media_hist.groupby("categoria")["valor"].mean().reset_index().rename(columns={"valor": "media"})
else:
    media_hist = pd.DataFrame(columns=["categoria", "media"])

# Gastos Reais do Mês Selecionado
df_mes = df_trans[(df_trans["data"].dt.month == mes) & (df_trans["data"].dt.year == ano)]
gastos_reais = df_mes.groupby("categoria")["valor"].sum().reset_index().rename(columns={"valor": "valor_real"})

# Orçamentos salvos no banco (Filtrado por usuário)
orc_salvos = carregar_orcamentos(mes, ano, usuario_atual).rename(columns={"valor": "valor_orc"})

# Unificação dos dados
df_final = pd.merge(gastos_reais, orc_salvos, on="categoria", how="outer")
df_final = pd.merge(df_final, media_hist, on="categoria", how="left")

# Limpeza de nulos e tipos
df_final = df_final.fillna(0)
df_final["valor_orc"] = pd.to_numeric(df_final["valor_orc"])
df_final["valor_real"] = pd.to_numeric(df_final["valor_real"])

# -----------------------------
# 3. Tabela de Edição
# -----------------------------
st.subheader("✏️ Ajustar Metas")
df_edit = st.data_editor(
    df_final[["categoria", "media", "valor_orc", "valor_real"]],
    column_config={
        "categoria": "Categoria",
        "media": st.column_config.NumberColumn("Média Histórica", format="R$ %.2f", disabled=True),
        "valor_orc": st.column_config.NumberColumn("Meta Orçada (R$)", format="%.2f", min_value=0.0),
        "valor_real": st.column_config.NumberColumn("Gasto Realizado", format="R$ %.2f", disabled=True),
    },
    hide_index=True,
    width = 'stretch',
    key="editor_orcamento"
)

if st.button("💾 Salvar Orçamento"):
    for _, row in df_edit.iterrows():
        salvar_orcamento(row["categoria"], row["valor_orc"], mes, ano, usuario_atual)
    st.success("✅ Salvo!")
    st.rerun()

# --------------------------------------------------
# 4. RESUMO POR TIPO (FIXO vs VARIÁVEL)
# --------------------------------------------------
st.divider()
st.subheader("📋 Previsão por Tipo de Custo")

# Recalcula tipos para o resumo baseado no df_editado
df_edit['tipo'] = df_edit['categoria'].apply(lambda x: 'Fixo' if x in CATEGORIAS_FIXAS else 'Variável')

resumo_tipo = df_edit.groupby('tipo').agg({
    'valor_orc': 'sum',
    'valor_real': 'sum'
}).reset_index()

col_f, col_v = st.columns(2)

def format_br(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with col_f:
    dados_fixo = resumo_tipo[resumo_tipo['tipo'] == 'Fixo']
    v_orc_f = dados_fixo['valor_orc'].iloc[0] if not dados_fixo.empty else 0
    v_real_f = dados_fixo['valor_real'].iloc[0] if not dados_fixo.empty else 0
    
    with st.container(border=True):
        st.markdown("**📌 Custos Fixos**")
        st.metric("Orçado", format_br(v_orc_f))
        st.write(f"Realizado: {format_br(v_real_f)}")
        prog_f = min(v_real_f / v_orc_f, 1.0) if v_orc_f > 0 else 0
        st.progress(prog_f, text=f"{int(prog_f*100)}% consumido")

with col_v:
    dados_var = resumo_tipo[resumo_tipo['tipo'] == 'Variável']
    v_orc_v = dados_var['valor_orc'].iloc[0] if not dados_var.empty else 0
    v_real_v = dados_var['valor_real'].iloc[0] if not dados_var.empty else 0
    
    with st.container(border=True):
        st.markdown("**💸 Custos Variáveis**")
        st.metric("Orçado", format_br(v_orc_v))
        st.write(f"Realizado: {format_br(v_real_v)}")
        prog_v = min(v_real_v / v_orc_v, 1.0) if v_orc_v > 0 else 0
        st.progress(prog_v, text=f"{int(prog_v*100)}% consumido")

# --------------------------------------------------
# 5. Confronto Visual (Altair)
# --------------------------------------------------
st.divider()
st.subheader("🎯 Confronto: Orçado vs Realizado")

if not df_edit.empty:
    df_plot = df_edit.copy()
    df_plot['cor_status'] = df_plot.apply(
        lambda x: '#FF4B4B' if x['valor_real'] > x['valor_orc'] else '#1F77B4', axis=1
    )

    base = alt.Chart(df_plot).encode(y=alt.Y("categoria:N", title=None, sort="-x"))

    bar_orc = base.mark_bar(size=24, color="#E6EAF1", cornerRadiusEnd=2).encode(
        x=alt.X("valor_orc:Q", title="Valor (R$)", stack=None)
    )

    bar_real = base.mark_bar(size=14, cornerRadiusEnd=2).encode(
        x=alt.X("valor_real:Q", stack=None),
        color=alt.Color('cor_status:N', scale=None),
        tooltip=[
            alt.Tooltip("categoria", title="Categoria"),
            alt.Tooltip("valor_orc", title="Meta Orçada", format=",.2f"),
            alt.Tooltip("valor_real", title="Gasto Real", format=",.2f")
        ]
    )

    text_alerta = base.mark_text(align='left', dx=10, color='#FF4B4B', fontWeight='bold').encode(
        x=alt.X("max(valor_real, valor_orc):Q"),
        text=alt.condition(
            alt.datum.valor_real > alt.datum.valor_orc,
            alt.value("⚠️ ESTOUROU"),
            alt.value("")
        )
    )

    chart_final = alt.layer(bar_orc, bar_real, text_alerta).properties(height=alt.Step(40))
    st.altair_chart(chart_final, width = 'stretch')

# -----------------------------
# 6. Métricas Finais
# -----------------------------
st.divider()
total_orc = df_edit["valor_orc"].sum()
total_real = df_edit["valor_real"].sum()
saldo = total_orc - total_real

c1, c2, c3 = st.columns(3)
c1.metric("🎯 Total Orçado", format_br(total_orc))
c2.metric("💸 Total Gasto", format_br(total_real), delta=format_br(-saldo), delta_color="inverse")
c3.metric("💰 Saldo", format_br(saldo), delta="Meta Mensal")