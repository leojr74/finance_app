import streamlit as st
from ui import apply_global_style

apply_global_style()

# Configuração da página (deve ser a primeira linha de comando Streamlit)
st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

# --- CONTEÚDO DA HOME ---
st.title("💰 Sistema de Gestão Financeira")
st.markdown(f"### Olá! Bem-vindo ao seu painel de controle pessoal.")

st.write("---")

# Colunas para dar um ar de "Dashboard de Boas-Vindas"
col1, col2 = st.columns(2)

with col1:
    st.info("""
    ### 🚀 Atalhos Rápidos
    * **📥 Importação:** Envie seus PDFs de faturas.
    * **✍️ Inclusão Manual:** Registre gastos em dinheiro ou extras.
    * **📑 Transações:** Gerencie e categorize seus dados.
    * **📈 Dashboard:** Analise suas médias e totais.
    """)

with col2:
    st.success("""
    ### 💡 Dica do Dia
    Mantenha suas categorias padronizadas para que o gráfico de **Média Mensal** no Dashboard seja o mais preciso possível!
    """)

st.write("---")

# Rodapé discreto
st.caption("Desenvolvido para automação de dados financeiros e organização pessoal.")