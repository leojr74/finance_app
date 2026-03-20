import streamlit as st

# set_page_config DEVE ser chamado UMA SÓ VEZ, antes de qualquer outro comando st.*
st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

from ui import apply_global_style
from database import criar_tabela, get_categorias_completas, get_gastos_fixos, salvar_config_categoria
from categorizer import load_categories

apply_global_style()
criar_tabela()

# --- CONTEÚDO DA HOME ---
st.title("💰 Sistema de Gestão Financeira")
st.markdown("### Bem-vindo ao seu painel de controle pessoal.")
st.write("---")

st.markdown("### 🚀 Guia de Navegação")
c1, _ = st.columns([2, 1])

with c1:
    st.info("""
    **📥 Importação** - Envie PDFs de faturas. O sistema detecta o banco e evita duplicatas automaticamente.

    **✍️ Inclusão Manual** - Registre gastos em dinheiro ou extras. Ideal para saques, PIX avulsos ou taxas.

    **📑 Transações** - Gerencie e categorize seus dados. Valide as sugestões da Inteligência JSON e replique regras.

    **📈 Dashboard** - Analise suas médias e totais. Visão macro com filtros específicos para Gastos Fixos.
    
    **📊 Orçamento** - Defina suas metas mensais. Acompanhe o planejado vs. realizado com alertas de teto.
    """)

st.write("---")

# --- CONFIGURAÇÃO DE CUSTOS FIXOS ---
with st.expander("⚙️ Configurações do Sistema", expanded=True):
    st.subheader("Definição de Gastos Fixos")
    st.markdown("Marque as categorias que representam custos recorrentes para filtragem no Dashboard:")

    categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado"}

    try:
        rules = load_categories()
        cats_json = set(str(v) for v in rules.values() if v)
    except:
        cats_json = set()

    set_todas = categorias_base.union(cats_json)
    termos_proibidos = {"Sem categoria", "None", "nan", "", "---", "Descontos", "Outros", "Juros", "Multa", "Impostos", None}

    todas_as_categorias = sorted([
        str(cat) for cat in set_todas
        if cat and str(cat).strip() not in termos_proibidos
    ])

    fixas_atuais = get_gastos_fixos()

    if todas_as_categorias:
        # Coleta todas as mudanças ANTES de salvar qualquer coisa
        mudancas = {}
        cols_fixos = st.columns(4)
        for i, cat in enumerate(todas_as_categorias):
            with cols_fixos[i % 4]:
                checado = st.checkbox(cat, value=(cat in fixas_atuais), key=f"cfg_{cat}")
                if checado != (cat in fixas_atuais):
                    mudancas[cat] = checado

        # Salva tudo de uma vez e dá rerun APENAS se houve mudança
        if mudancas:
            for cat, valor in mudancas.items():
                salvar_config_categoria(cat, valor)
            st.rerun()
    else:
        st.info("Nenhuma categoria encontrada no JSON ou na base oficial.")

st.write("---")
st.caption("v2.3 | Sistema de Automação Financeira Pessoal")
