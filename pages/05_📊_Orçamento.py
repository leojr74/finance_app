import streamlit as st
import pandas as pd
from datetime import date
import altair as alt
from database import (
    carregar_transacoes,
    criar_tabela,
    salvar_orcamento,
    get_gastos_fixos,
    carregar_orcamentos
)
from ui import apply_global_style

st.set_page_config(page_title="Orçamento", layout="wide")
apply_global_style()

st.title("📊 Planejamento de Orçamento")

# Garante a estrutura do banco
criar_tabela()

# Puxa categorias configuradas na Home (Fixas)
CATEGORIAS_FIXAS = get_gastos_fixos()

# -----------------------------
# 1. Seleção de Período
# -----------------------------
col1, col2 = st.columns(2)
with col1:
    mes = st.selectbox("Mês", list(range(1, 13)), index=date.today().month - 1)
with col2:
    ano = st.number_input("Ano", value=date.today().year)

# Botão de cópia (Lógica mantida)
if st.button("📅 Copiar orçamento do mês anterior"):
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    df_ant = carregar_orcamentos(mes_ant, ano_ant)
    if not df_ant.empty:
        for _, row in df_ant.iterrows():
            salvar_orcamento(row["categoria"], row["valor"], mes, ano)
        st.success("Copiado com sucesso!")
        st.rerun()

# -----------------------------
# 2. Processamento de Dados (Sem Duplicidade)
# -----------------------------
df_trans = carregar_transacoes()
df_trans = df_trans[df_trans["categoria"] != "Descontos"]

# Cálculo da Média Histórica (Para sugestão)
if not df_trans.empty:
    df_trans["data"] = pd.to_datetime(df_trans["data"])
    df_trans["mes_ref"] = df_trans["data"].dt.to_period("M")
    media_hist = df_trans.groupby(["categoria", "mes_ref"])["valor"].sum().reset_index()
    media_hist = media_hist.groupby("categoria")["valor"].mean().reset_index().rename(columns={"valor": "media"})
else:
    media_hist = pd.DataFrame(columns=["categoria", "media"])

# Gastos Reais do Mês Selecionado
df_mes = df_trans[(df_trans["data"].dt.month == mes) & (df_trans["data"].dt.year == ano)]
gastos_reais = df_mes.groupby("categoria")["valor"].sum().reset_index().rename(columns={"valor": "valor_real"})

# Orçamentos salvos no banco
orc_salvos = carregar_orcamentos(mes, ano).rename(columns={"valor": "valor_orc"})

# Unificação dos dados (Merge único para evitar duplicidade)
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
    use_container_width=True
)

if st.button("💾 Salvar Orçamento"):
    for _, row in df_edit.iterrows():
        salvar_orcamento(row["categoria"], row["valor_orc"], mes, ano)
    st.success("✅ Salvo!")
    st.rerun()

# Unificação dos dados
df_final = pd.merge(gastos_reais, orc_salvos, on="categoria", how="outer")
df_final = pd.merge(df_final, media_hist, on="categoria", how="left")
df_final = df_final.fillna(0)

# --------------------------------------------------
# 4. RESUMO POR TIPO (FIXO vs VARIÁVEL) - NOVO BLOCO
# --------------------------------------------------
st.divider()
st.subheader("📋 Previsão por Tipo de Custo")

# Criamos uma coluna temporária para identificar o tipo baseado no que vem do banco (CATEGORIAS_FIXAS)
df_final['tipo'] = df_final['categoria'].apply(lambda x: 'Fixo' if x in CATEGORIAS_FIXAS else 'Variável')

# Agrupamos os valores orçados e reais por tipo
resumo_tipo = df_final.groupby('tipo').agg({
    'valor_orc': 'sum',
    'valor_real': 'sum'
}).reset_index()

col_f, col_v = st.columns(2)

with col_f:
    # Filtra os dados de Fixos
    dados_fixo = resumo_tipo[resumo_tipo['tipo'] == 'Fixo']
    v_orc_f = dados_fixo['valor_orc'].iloc[0] if not dados_fixo.empty else 0
    v_real_f = dados_fixo['valor_real'].iloc[0] if not dados_fixo.empty else 0
    
    with st.container(border=True):
        st.markdown("**📌 Custos Fixos**")
        st.metric("Orçado", f"R$ {v_orc_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.write(f"Realizado: R$ {v_real_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        # Barra de progresso do orçamento fixo
        prog_f = min(v_real_f / v_orc_f, 1.0) if v_orc_f > 0 else 0
        st.progress(prog_f, text=f"{int(prog_f*100)}% consumido")

with col_v:
    # Filtra os dados de Variáveis
    dados_var = resumo_tipo[resumo_tipo['tipo'] == 'Variável']
    v_orc_v = dados_var['valor_orc'].iloc[0] if not dados_var.empty else 0
    v_real_v = dados_var['valor_real'].iloc[0] if not dados_var.empty else 0
    
    with st.container(border=True):
        st.markdown("**💸 Custos Variáveis**")
        st.metric("Orçado", f"R$ {v_orc_v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.write(f"Realizado: R$ {v_real_v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        # Barra de progresso do orçamento variável
        prog_v = min(v_real_v / v_orc_v, 1.0) if v_orc_v > 0 else 0
        st.progress(prog_v, text=f"{int(prog_v*100)}% consumido")
# --------------------------------------------------
# Comparação visual (Orçado vs Realizado)
# --------------------------------------------------
import altair as alt

st.divider()
st.subheader("🎯 Confronto: Orçado vs Realizado")

if not df_edit.empty:
    # 1. Preparar os dados (Garantir que são números)
    df_plot = df_edit.copy()
    df_plot["valor_real"] = pd.to_numeric(df_plot["valor_real"], errors="coerce").fillna(0)
    df_plot["valor_orc"] = pd.to_numeric(df_plot["valor_orc"], errors="coerce").fillna(0)

    # 2. Definir a cor da barra de gasto (Vermelho se estourar, Azul se OK)
    df_plot['cor_status'] = df_plot.apply(
        lambda x: '#FF4B4B' if x['valor_real'] > x['valor_orc'] else '#1F77B4', axis=1
    )

    # 3. Criar o gráfico de sobreposição
    base = alt.Chart(df_plot).encode(
        y=alt.Y("categoria:N", title=None, sort="-x")
    )

    # Camada de Fundo: Orçamento (Barra cinza mais larga)
    # stack=None impede que o Altair some os valores
    bar_orc = base.mark_bar(size=24, color="#E6EAF1", cornerRadiusEnd=2).encode(
        x=alt.X("valor_orc:Q", title="Valor (R$)", stack=None)
    )

    # Camada de Frente: Gasto Real (Barra colorida mais fina)
    bar_real = base.mark_bar(size=14, cornerRadiusEnd=2).encode(
        x=alt.X("valor_real:Q", stack=None),
        color=alt.Color('cor_status:N', scale=None),
        tooltip=[
            alt.Tooltip("categoria", title="Categoria"),
            alt.Tooltip("valor_orc", title="Meta Orçada", format=",.2f"),
            alt.Tooltip("valor_real", title="Gasto Real", format=",.2f")
        ]
    )

    # Camada de Texto: Alerta de Estouro
    text_alerta = base.mark_text(align='left', dx=10, color='#FF4B4B', fontWeight='bold').encode(
        x=alt.X("max(valor_real, valor_orc):Q"),
        text=alt.condition(
            alt.datum.valor_real > alt.datum.valor_orc,
            alt.value("⚠️ ESTOUROU"),
            alt.value("")
        )
    )

    # Juntar as camadas
    chart_final = alt.layer(bar_orc, bar_real, text_alerta).properties(height=alt.Step(40))

    st.altair_chart(chart_final, use_container_width=True)

# -----------------------------
# 5. Métricas Finais
# -----------------------------
st.divider()
total_orc = df_edit["valor_orc"].sum()
total_real = df_edit["valor_real"].sum()
saldo = total_orc - total_real

c1, c2, c3 = st.columns(3)
def fmt(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

c1.metric("🎯 Total Orçado", fmt(total_orc))
c2.metric("💸 Total Gasto", fmt(total_real), delta=fmt(-saldo), delta_color="inverse")
c3.metric("💰 Saldo", fmt(saldo), delta="Meta Mensal")