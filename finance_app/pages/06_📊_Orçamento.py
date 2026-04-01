import streamlit as st
import pandas as pd
from datetime import date, timedelta
import altair as alt
from database import (
    carregar_transacoes,
    criar_tabela,
    get_authenticator,
    cookie_rerun_pendente,
    salvar_orcamento,
    get_gastos_fixos,
    carregar_orcamentos,
    carregar_regras_db
)
from ui import apply_global_style
from fpdf import FPDF
import io

st.set_page_config(
    page_title="Planejamento de Orçamento",
    page_icon="📊",
    layout="wide"
)

authenticator = get_authenticator()
authenticator.login(location='unrendered')

auth_status = st.session_state.get("authentication_status", None)

# ⏳ AINDA CARREGANDO (não decide nada ainda)
if auth_status is None:
    st.stop()

# ❌ NÃO AUTENTICADO
if auth_status is False:
    st.warning("Sessão expirada. Faça login novamente.")
    st.stop()

usuario_atual = st.session_state["username"]
apply_global_style()
st.title("📊 Planejamento de Orçamento")

# Garante a estrutura do banco
criar_tabela()

# -----------------------------
# 1. Seleção de Período
# -----------------------------
col1, col2 = st.columns(2)
with col1:
    mes = st.selectbox("Mês", list(range(1, 13)), index=date.today().month - 1)
with col2:
    ano = st.number_input("Ano", value=date.today().year)

# Botão de cópia
if st.button("📅 Copiar orçamento do mês anterior"):
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    df_ant = carregar_orcamentos(mes_ant, ano_ant, usuario_atual)
    if not df_ant.empty:
        for _, row in df_ant.iterrows():
            salvar_orcamento(row["categoria"], row["valor"], mes, ano, usuario_atual)
        st.success("Copiado com sucesso!")
        st.rerun()

# -----------------------------
# 2. Processamento de Dados (CATEGORIAS UNIFICADAS)
# -----------------------------
# A. Definir Lista de Categorias (Igual à Home)
categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado"}
regras_usuario = carregar_regras_db(usuario_atual)
cats_personalizadas = set(str(v) for v in regras_usuario.values() if v)

termos_proibidos = {"Sem categoria", "None", "nan", "", "---", "Descontos", "Outros", "Juros", "Multa", "Impostos", None}
todas_as_categorias = sorted([
    str(cat) for cat in categorias_base.union(cats_personalizadas)
    if cat and str(cat).strip() not in termos_proibidos
])

# Criamos o DataFrame mestre com todas as categorias
df_final = pd.DataFrame({"categoria": todas_as_categorias})

# B. Carregar Transações
df_trans = carregar_transacoes(usuario_atual)
if df_trans is None:
    df_trans = pd.DataFrame(columns=["data", "categoria", "valor"])

df_trans["data"] = pd.to_datetime(df_trans["data"], errors="coerce")

# C. Cálculo de Média (Últimos 5 Meses Fechados)
if not df_trans.empty:
    primeiro_dia_mes_atual = pd.Timestamp(date.today().replace(day=1))
    data_corte = (primeiro_dia_mes_atual - pd.DateOffset(months=5))
    
    df_recent = df_trans[
        (df_trans["data"] >= data_corte) & 
        (df_trans["data"] < primeiro_dia_mes_atual)
    ].copy()
    
    if not df_recent.empty:
        df_recent["mes_ref"] = df_recent["data"].dt.to_period("M")
        media_hist = df_recent.groupby(["categoria", "mes_ref"])["valor"].sum().reset_index()
        media_hist = media_hist.groupby("categoria")["valor"].mean().reset_index().rename(columns={"valor": "media"})
    else:
        media_hist = pd.DataFrame(columns=["categoria", "media"])
else:
    media_hist = pd.DataFrame(columns=["categoria", "media"])

# D. Gastos Reais e Orçamentos
df_mes = df_trans[(df_trans["data"].dt.month == mes) & (df_trans["data"].dt.year == ano)]
gastos_reais = df_mes.groupby("categoria")["valor"].sum().reset_index().rename(columns={"valor": "valor_real"})
orc_salvos = carregar_orcamentos(mes, ano, usuario_atual).rename(columns={"valor": "valor_orc"})

# E. Merge Final (Partindo da lista de categorias completa)
df_final = pd.merge(df_final, orc_salvos, on="categoria", how="left")
df_final = pd.merge(df_final, gastos_reais, on="categoria", how="left")
df_final = pd.merge(df_final, media_hist, on="categoria", how="left")

df_final = df_final.fillna(0)

# -----------------------------
# 3. Tabela de Edição
# -----------------------------
st.subheader("✏️ Ajustar Metas")
df_edit = st.data_editor(
    df_final[["categoria", "media", "valor_orc", "valor_real"]],
    column_config={
        "categoria": "Categoria",
        "media": st.column_config.NumberColumn("Média (5 meses)", format="R$ %.2f", disabled=True),
        "valor_orc": st.column_config.NumberColumn("Meta Orçada (R$)", format="%.2f", min_value=0.0),
        "valor_real": st.column_config.NumberColumn("Gasto Realizado", format="R$ %.2f", disabled=True),
    },
    hide_index=True,
    width='stretch',
    key="editor_orcamento"
)

if st.button("💾 Salvar Orçamento"):
    for _, row in df_edit.iterrows():
        salvar_orcamento(row["categoria"], row["valor_orc"], mes, ano, usuario_atual)
    st.success("✅ Salvo!")
    st.rerun()

# -----------------------------
# 4. Exportação de Relatório (PDF)
# -----------------------------
st.divider()
st.subheader("📥 Exportar Planejamento")

def gerar_pdf(df, usuario, mes_ref, ano_ref):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Título
    pdf.cell(190, 10, f"Planejamento de Orçamento - {usuario}", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(190, 10, f"Referência: {mes_ref}/{ano_ref}", ln=True, align="C")
    pdf.ln(10)
    
    # Cabeçalho da Tabela
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(45, 10, "Categoria", 1, 0, "C", True)
    pdf.cell(35, 10, "Média (5m)", 1, 0, "C", True)
    pdf.cell(35, 10, "Meta (R$)", 1, 0, "C", True)
    pdf.cell(35, 10, "Real (R$)", 1, 0, "C", True)
    pdf.cell(40, 10, "Status", 1, 1, "C", True)
    
    # Linhas da Tabela
    pdf.set_font("Arial", "", 9)
    for _, row in df.iterrows():
        status = "No Limite" if row["valor_orc"] >= row["valor_real"] else "ESTOUROU"
        
        pdf.cell(45, 8, str(row["categoria"]), 1)
        pdf.cell(35, 8, f"R$ {row['media']:,.2f}", 1)
        pdf.cell(35, 8, f"R$ {row['valor_orc']:,.2f}", 1)
        pdf.cell(35, 8, f"R$ {row['valor_real']:,.2f}", 1)
        
        # Cor de alerta para estouro
        if status == "ESTOUROU":
            pdf.set_text_color(255, 0, 0)
        pdf.cell(40, 8, status, 1, 1, "C")
        pdf.set_text_color(0, 0, 0)
        
    # Totais
    pdf.ln(5)
    pdf.set_font("Arial", "B", 11)
    total_orc = df["valor_orc"].sum()
    total_real = df["valor_real"].sum()
    pdf.cell(190, 10, f"Total Orçado: R$ {total_orc:,.2f} | Total Realizado: R$ {total_real:,.2f}", ln=True, align="R")
    
    return pdf.output(dest='S').encode('latin-1')

# Botão de Download PDF
try:
    pdf_bytes = gerar_pdf(df_edit, st.session_state.get("name", usuario_atual), mes, ano)
    
    st.download_button(
        label="📑 Baixar Orçamento em PDF",
        data=pdf_bytes,
        file_name=f"Orcamento_{mes}_{ano}.pdf",
        mime="application/pdf",
        help="Gera um relatório formatado em PDF para impressão."
    )
except Exception as e:
    st.error(f"Erro ao gerar PDF: {e}. Verifique se há caracteres especiais nas categorias.")

# --------------------------------------------------
# 5. RESUMO POR TIPO (FIXO vs VARIÁVEL)
# --------------------------------------------------
st.divider()
st.subheader("📋 Previsão por Tipo de Custo")

CATEGORIAS_FIXAS = get_gastos_fixos(usuario_atual)
df_edit['tipo'] = df_edit['categoria'].apply(lambda x: 'Fixo' if x in CATEGORIAS_FIXAS else 'Variável')

resumo_tipo = df_edit.groupby('tipo').agg({
    'valor_orc': 'sum',
    'valor_real': 'sum'
}).reset_index()

def format_br(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

col_f, col_v = st.columns(2)

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
# 6. Confronto Visual (Altair)
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
    chart_final = alt.layer(bar_orc, bar_real).properties(height=alt.Step(40))
    st.altair_chart(chart_final, width='stretch')

# -----------------------------
# 7. Métricas Finais
# -----------------------------
st.divider()
total_orc = df_edit["valor_orc"].sum()
total_real = df_edit["valor_real"].sum()
saldo = total_orc - total_real

c1, c2, c3 = st.columns(3)
c1.metric("🎯 Total Orçado", format_br(total_orc))
c2.metric("💸 Total Gasto", format_br(total_real), delta=format_br(-saldo), delta_color="inverse")
c3.metric("💰 Saldo", format_br(saldo), delta="Meta Mensal")