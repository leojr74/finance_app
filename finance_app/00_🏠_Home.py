import streamlit as st
import time
from ui import apply_global_style
from database import (
    criar_tabela,
    verificar_login,
    salvar_novo_usuario_db,
    carregar_regras_db,
    get_gastos_fixos,
    salvar_config_categoria
)

st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

apply_global_style()
criar_tabela()

# =========================
# 🔐 LOGIN / CADASTRO
# =========================
if not st.session_state.get("logged_in"):

    st.title("💰 Sistema de Gestão Financeira")

    tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])

    # -------- LOGIN --------
    with tab_login:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):

            user = verificar_login(email, senha)

            if user:
                from database import criar_session_token

                token = criar_session_token(user["email"])

                st.session_state["logged_in"] = True
                st.session_state["user"] = user["email"]
                st.session_state["user_name"] = user["name"]

                # 🔥 salva token na URL
                st.query_params["token"] = token

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


# =========================
# 👤 USUÁRIO LOGADO
# =========================
usuario_atual = st.session_state["user"]

# -------- LOGOUT --------
if st.sidebar.button("🚪 Sair"):
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()


# =========================
# 🏠 CONTEÚDO DA HOME
# =========================
st.title("💰 Sistema de Gestão Financeira")
st.markdown(f"### Bem-vindo, {st.session_state['user_name']}! 👋")
st.write("---")

st.markdown("### 🚀 Guia de Navegação")

st.info("💡 **Dica Mobile:** Toque no menu ( **»** ) no canto superior esquerdo.")

st.info("""
📥 Importação de faturas - Upload de PDFs com detecção automática.

📱 Importação de SMS - Atualize transações via SMS.

✍️ Inclusão Manual - Registre gastos fora do cartão.

📑 Transações - Gerencie e categorize.

📈 Dashboard - Analise seus gastos.

📊 Orçamento - Controle metas mensais.
""")

st.write("---")


# =========================
# ⚙️ CONFIGURAÇÕES
# =========================
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

    fixas_atuais = get_gastos_fixos(usuario_atual)

    if todas_as_categorias:
        cols = st.columns(4)

        for i, cat in enumerate(todas_as_categorias):
            with cols[i % 4]:
                checado = st.checkbox(cat, value=(cat in fixas_atuais))

                if checado != (cat in fixas_atuais):
                    salvar_config_categoria(cat, checado, usuario_atual)
                    st.rerun()
    else:
        st.info("Nenhuma categoria encontrada.")

st.write("---")
st.caption("v3.1 | Sistema Financeiro (login persistente 🚀)")