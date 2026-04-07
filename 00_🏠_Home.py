import streamlit as st
import time
import extra_streamlit_components as stx
from ui import apply_global_style
from database import (
    criar_tabela,
    verificar_login,
    salvar_novo_usuario_db,
    carregar_regras_db,
    get_gastos_fixos,
    salvar_config_categoria,
    criar_session_token,
    buscar_usuario_por_token,
    invalidar_session_token
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
# 🔐 VERIFICA SESSÃO
# ---------------------------
usuario = None
token = None

try:
    blacklist = st.session_state.get("token_blacklist", set())

    token = st.session_state.get("session_token")

    if not token:
        token = cookie_manager.get("session_token")
        if token:
            st.session_state["session_token"] = token

    if not token or token in blacklist:
        token = None

    if token:
        user = buscar_usuario_por_token(token)
        if user:
            usuario = user
        else:
            st.session_state.pop("session_token", None)
            token = None

except Exception:
    st.session_state.clear()
    token = None
    usuario = None

# ---------------------------
# 🔐 LOGIN / CADASTRO
# ---------------------------
if not usuario:

    st.title("💰 Sistema de Gestão Financeira")

    # cadastro concluído — mostra mensagem no lugar do formulário
    if st.session_state.get("_cadastro_ok"):
        st.session_state.pop("_cadastro_ok", None)
        st.success("✅ Conta criada com sucesso!")
        st.info("Faça login na aba **Entrar**.")
        st.stop()

    tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])

    # -------- LOGIN --------
    with tab_login:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            user = verificar_login(email, senha)

            if user:
                token = criar_session_token(user["email"])
                st.session_state["session_token"] = token
                cookie_manager.set("session_token", token)

                st.success("Login realizado com sucesso!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Email ou senha inválidos")

    # -------- CADASTRO --------
    with tab_signup:
        cad_key = st.session_state.get("_cad_key", 0)
        nome = st.text_input("Nome", key=f"cad_nome_{cad_key}")
        email_novo = st.text_input("Email", key=f"cad_email_{cad_key}")
        senha_nova = st.text_input("Senha", type="password", key=f"cad_senha_{cad_key}")
        senha_nova2 = st.text_input("Confirme a senha", type="password", key=f"cad_senha2_{cad_key}")

        if st.button("Cadastrar"):
            if not nome or not email_novo or not senha_nova or not senha_nova2:
                st.warning("Preencha todos os campos")
            elif senha_nova != senha_nova2:
                st.error("As senhas não coincidem")
            else:
                sucesso = salvar_novo_usuario_db(
                    username=email_novo,
                    email=email_novo,
                    name=nome,
                    senha_plana=senha_nova
                )
                if sucesso:
                    st.session_state["_cad_key"] = cad_key + 1
                    st.session_state["_cadastro_ok"] = True
                    st.rerun()
                else:
                    st.error("Erro ao cadastrar. Tente novamente.")

    st.stop()

# ---------------------------
# 👤 USUÁRIO LOGADO
# ---------------------------
usuario_atual = usuario.email
nome_usuario = usuario.name

# -------- LOGOUT --------
if st.sidebar.button("🚪 Sair"):
    token_atual = st.session_state.get("session_token")
    invalidar_session_token(usuario_atual)
    st.session_state.clear()
    st.session_state["token_blacklist"] = {token_atual}
    cookie_manager.delete("session_token")
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