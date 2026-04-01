import streamlit as st
import pandas as pd
import altair as alt
import datetime
from fpdf import FPDF
import io
from database import carregar_transacoes, get_gastos_fixos, carregar_regras_db
from ui import apply_global_style
from utils.auth import check_login


st.set_page_config(
    page_title="Dashboard Financeiro",
    page_icon="📈",
    layout="wide"
)

usuario_atual = check_login()
apply_global_style()

# --- FUNÇÕES DE APOIO ---
def formatar(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_pdf(df_resumo, usuario, periodo):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "Relatorio de Gastos por Categoria", ln=True, align="C")
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 10, f"Usuario: {usuario} | Periodo: {periodo}", ln=True, align="C")
    pdf.ln(10)
    
    # Tabela - Cabeçalho
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 10, "Categoria", border=1, fill=True)
    pdf.cell(50, 10, "Valor (R$)", border=1, fill=True)
    pdf.cell(50, 10, "% do Total", border=1, fill=True, ln=True)
    
    # Dados
    pdf.set_font("Arial", "", 11)
    total_geral = df_resumo["valor"].sum()
    
    for _, row in df_resumo.iterrows():
        percentual = (row["valor"] / total_geral) * 100
        pdf.cell(90, 10, str(row["categoria"]), border=1)
        pdf.cell(50, 10, f"{row['valor']:,.2f}", border=1)
        pdf.cell(50, 10, f"{percentual:.1f}%", border=1, ln=True)
    
    # Total Final
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 10, "TOTAL GERAL", border=1)
    pdf.cell(100, 10, f"R$ {total_geral:,.2f}", border=1, ln=True, align="C")
    
    return pdf.output(dest='S').encode('latin-1')

st.title("📈 Dashboard Financeiro")

# 2. CARREGAMENTO E LIMPEZA
df = carregar_transacoes(usuario_atual)
if df is None or df.empty:
    st.warning(f"⚠️ Nenhuma transação encontrada para {usuario_atual}.")
    st.stop()

df["data"] = pd.to_datetime(df["data"], dayfirst=True)
df["valor"] = pd.to_numeric(df["valor"], errors='coerce')

# 3. FILTRO DE CATEGORIAS
try:
    # 1. Busca as regras que o Leonardo (ou usuário logado) criou no banco
    regras_usuario = carregar_regras_db(usuario_atual)
    categorias_do_usuario = set(str(v) for v in regras_usuario.values() if v)
except Exception as e:
    st.error(f"Erro ao carregar regras: {e}")
    categorias_do_usuario = set()

# 2. Categorias que sempre devem ser consideradas
categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}

# 3. Categorias que já existem nos lançamentos (mesmo que não tenham regra ainda)
categorias_nos_dados = set(df["categoria"].unique())

# 4. Termos que não devem aparecer no gráfico de gastos
termos_para_ignorar = {"Descontos", "Crédito", "Estorno", "Pagamento", "Ajuste", None, "nan", ""}

# 5. Criamos a lista final permitida
lista_permitida = (categorias_base.union(categorias_do_usuario).union(categorias_nos_dados)) - termos_para_ignorar

# 6. Aplicamos o filtro no DataFrame do Dashboard
df = df[df["categoria"].isin(lista_permitida)]

# 4. LÓGICA DE DATAS
hoje = datetime.date.today()
trinta_dias_atras = hoje - datetime.timedelta(days=30)
limite_min = df["data"].min().date()
limite_max = df["data"].max().date()
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

if isinstance(periodo, tuple):
    if len(periodo) == 2 and periodo[0] and periodo[1]:
        # Intervalo completo
        data_inicio, data_fim = periodo

        df_filtrado = df[
            (df["data"].dt.date >= data_inicio) &
            (df["data"].dt.date <= data_fim)
        ].copy()

        txt_periodo_pdf = f"{data_inicio.strftime('%d/%m/%Y')} ate {data_fim.strftime('%d/%m/%Y')}"

    elif len(periodo) == 1 or (len(periodo) == 2 and periodo[0] and not periodo[1]):
        # Só data inicial selecionada (ou no meio da seleção)
        data_sel = periodo[0]

        df_filtrado = df[df["data"].dt.date == data_sel].copy()

        txt_periodo_pdf = data_sel.strftime('%d/%m/%Y')

    else:
        st.stop()

else:
    # Caso venha como data única (segurança extra)
    data_sel = periodo

    df_filtrado = df[df["data"].dt.date == data_sel].copy()
    txt_periodo_pdf = data_sel.strftime('%d/%m/%Y')

# 6. MÉTRICAS
CATEGORIAS_FIXAS_DB = get_gastos_fixos(usuario_atual)
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

# Agrupamento e Seleção permanecem iguais
df_agrupado = df_filtrado.groupby("categoria")["valor"].sum().reset_index()
selecao = alt.selection_point(fields=["categoria"], name="sel")

# Removemos st.columns e o bloco 'with col_dir'
st.subheader("🍕 Distribuição por Categoria")

pizza = alt.Chart(df_agrupado).mark_arc(innerRadius=50).encode(
    theta=alt.Theta(field="valor", type="quantitative"),
    color=alt.Color(field="categoria", type="nominal", scale=alt.Scale(scheme='tableau10')),
    opacity=alt.condition(selecao, alt.value(1.0), alt.value(0.4)),
    tooltip=[alt.Tooltip("categoria"), alt.Tooltip("valor", format=",.2f")]
).add_params(selecao).properties(height=500) # Aumentei um pouco a altura para preencher melhor a tela

# Exibe o gráfico ocupando a largura disponível
evento_pizza = st.altair_chart(pizza, width='stretch', on_select="rerun")
# --- TABELA DE DETALHES ---
categoria_selecionada = None

# Verificamos apenas a seleção do gráfico de pizza
sel_pizza = evento_pizza.get("selection", {}).get("sel", [])

if sel_pizza and len(sel_pizza) > 0:
    # Ajuste conforme o retorno do Altair (algumas versões retornam o valor direto, outras um dicionário)
    # Se 'sel_pizza[0]' for um dicionário:
    if isinstance(sel_pizza[0], dict):
        categoria_selecionada = sel_pizza[0].get("categoria")
    # Caso seja o valor direto (comum em seleções de campo único):
    else:
        categoria_selecionada = sel_pizza[0]

if categoria_selecionada:
    st.write("---")
    st.subheader(f"📋 Transações — {categoria_selecionada}")
    
    # Filtragem dos detalhes
    df_detalhe = df_filtrado[df_filtrado["categoria"] == categoria_selecionada].copy()
    df_detalhe = df_detalhe[["data", "descricao", "valor", "banco"]].sort_values("data", ascending=False)
    
    st.dataframe(
        df_detalhe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
            "descricao": "Descrição",
            "banco": "Banco"
        }
    )
    st.caption(f"Total: {formatar(df_detalhe['valor'].sum())}")
# --- BOTÃO DE RELATÓRIO (PDF) ---
st.write("---")
col_rel, _ = st.columns([1, 1])
with col_rel:
    try:
        df_pdf = df_filtrado.groupby("categoria")["valor"].sum().reset_index().sort_values("valor", ascending=False)
        pdf_bytes = gerar_pdf(df_pdf, st.session_state['name'], txt_periodo_pdf)
        
        st.download_button(
            label="📥 Baixar Relatório (PDF)",
            data=pdf_bytes,
            file_name=f"Relatorio_{datetime.date.today()}.pdf",
            mime="application/pdf",
            width='stretch'
        )
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")

st.write("---")
st.caption(f"v2.5 | Dashboard para {st.session_state['name']} | Dados filtrados por user_id: {usuario_atual}")