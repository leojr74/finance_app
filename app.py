import streamlit as st

st.set_page_config(
    page_title="Sistema de Gestão Financeira",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Finance Dashboard")

st.markdown("""
### Bem-vindo ao seu Gerenciador Financeiro Pessoal!

O sistema foi reorganizado para facilitar o seu fluxo de trabalho. Use o menu lateral para navegar entre as etapas:

---

#### 🛠️ Entrada de Dados (Input)
* **1_importacao**: Extração automática de transações a partir de faturas em PDF (Caixa, Nubank, etc).
* **2_inclusao_manual**: Registro de gastos avulsos, Pix, saques ou compras em dinheiro.

#### ⚙️ Processamento e Ajustes
* **3_transacoes**: Gerenciamento completo do banco de dados. Aqui você pode filtrar por banco, editar categorias em massa e validar a inteligência do sistema.

#### 📈 Análise (Output)
* **4_dashboard**: Visualização gráfica dos seus gastos, médias mensais e saúde financeira.

---
**Dica:** Sempre que realizar uma importação ou inclusão manual, os dados estarão disponíveis instantaneamente na página de Gerenciamento.
""")

# Rodapé informativo
st.sidebar.info("Selecione uma das etapas acima para começar.")