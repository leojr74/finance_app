import streamlit as st
import time
import extra_streamlit_components as stx
import datetime
from ui import apply_global_style
from database import (
    criar_tabela,
    verificar_login,
    salvar_novo_usuario_db,
    carregar_regras_db,
    get_gastos_fixos,
    salvar_config_categoria,
    criar_session_token,
    buscar_usuario_por_token
)

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

apply_global_style()
criar_tabela()

cookie_manager = stx.CookieManager()

# ---------------------------
# 🔐 VERIFICA COOKIE
# ---------------------------
token = cookie_manager.get("session_token")

# fallback para session_state caso o cookie ainda não tenha persistido
if not token or token == "":
    token = st.session_state.get("session_token")

if not token or token == "":
    token = None

usuario = None

if token:
    user = buscar_usuario_por_token(token)
    if user:
        usuario = user

# ---------------------------
# 🔐 LOGIN / CADASTRO
# ---------------------------
if not usuario:

    st.title("💰 Sistema de Gestão Financeira")

    tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])

    # -------- LOGIN --------
    with tab_login:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):

            user = verificar_login(email, senha)

            if user:
                token = criar_session_token(user["email"])

                cookie_manager.set("session_token", token)
                st.session_state["session_token"] = token  # salva no session_state como fallback

                st.success("Login realizado com sucesso!")
                time.sleep(1)
                st.rerun()

            else:
                st.error("Email ou senha inválidos")

    # -------- CADASTRO --------
    with tab_signup:
        nome = st.text_input("Nome")
        email_novo = st.text_input("Email", key="cad_email")
        senha_nova = st.text_input("Senha", type="password", key="cad_senha")

        if st.button("Cadastrar"):

            if not nome or not email_novo or not senha_nova:
                st.warning("Preencha todos os campos")

            else:
                sucesso = salvar_novo_usuario_db(
                    username=email_novo,
                    email=email_novo,
                    name=nome,
                    senha_plana=senha_nova
                )

                if sucesso:
                    st.success("✅ Conta criada com sucesso! Faça login.")
                    time.sleep(1.5)
                    st.rerun()

    st.stop()

# ---------------------------
# 👤 USUÁRIO LOGADO
# ---------------------------
usuario_atual = usuario.email
nome_usuario = usuario.name

# -------- LOGOUT --------
if st.sidebar.button("🚪 Sair"):
    cookie_manager.delete("session_token")
    st.session_state.pop("session_token", None)
    time.sleep(0.5)
    st.rerun()

# ---------------------------
# 🏠 HOME
# ---------------------------
st.title("💰 Sistema de Gestão Financeira")
st.markdown(f"### Bem-vindo, {nome_usuario}! 👋")
st.write("---")

st.markdown("### 🚀 Guia de Navegação")

st.info("💡 Use o menu lateral para navegar entre as páginas.")

st.info("""
📥 Importação de faturas - Upload de PDFs.

📱 Importação de SMS - Atualização automática.

✍️ Inclusão Manual - Registre gastos.

📑 Transações - Gerencie e categorize.

📈 Dashboard - Visualize seus dados.

📊 Orçamento - Controle financeiro.
""")

st.write("---")

# ---------------------------
# ⚙️ CONFIGURAÇÕES
# ---------------------------
with st.expander("⚙️ Configurações do Sistema", expanded=True):

    st.subheader("Definição de Gastos Fixos")

    categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado"}

    try:
        regras_usuario = carregar_regras_db(usuario_atual)
        cats_personalizadas = set(str(v) for v in regras_usuario.values() if v)
    except:
        cats_personalizadas = set()

    set_todas = categorias_base.union(cats_personalizadas)

    termos_proibidos = {"Sem categoria", "None", "nan", "", "---"}

    todas_as_categorias = sorted([
        str(cat) for cat in set_todas
        if cat and str(cat).strip() not in termos_proibidos
    ])
