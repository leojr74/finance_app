import time

import streamlit as st
import streamlit_authenticator as stauth
from ui import apply_global_style
from database import (
    carregar_usuarios_db, 
    salvar_novo_usuario_db, 
    criar_tabela, 
    carregar_regras_db, 
    get_gastos_fixos, 
    salvar_config_categoria,
    get_authenticator,
    invalidar_cache_authenticator,
    cookie_rerun_pendente
)


st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

apply_global_style()
criar_tabela()

authenticator = get_authenticator()



# --- CONTROLE DE SESSÃO ---
if st.session_state.get("authentication_status"):
    st.session_state["logged_in"] = True
    st.session_state["user"] = st.session_state.get("username")

logado = st.session_state.get("logged_in", False)

# --- SE NÃO ESTIVER LOGADO ---
tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])

with tab_login:
    authenticator.login(location='main')

with tab_signup:
    try:
        resultado = authenticator.register_user(
            location='main',
            pre_authorized=None, 
            captcha=False,
            fields={
                'Form name': 'Criar Conta',
                'First name': 'Nome',
                'Last name': 'Sobrenome',
                'Email': 'Email',
                'Username': 'Usuário',
                'Password': 'Senha',
                'Repeat password': 'Repetir Senha',
                'Register': 'Cadastrar'
            }
        )

        # ✅ SÓ EXECUTA SE VEIO DO BOTÃO
        if resultado and resultado[0]:

            email_novo, username_novo, nome_novo = resultado

            user_data = None

            try:
                model = authenticator.authentication_controller.authentication_model

                for attr in ['user_dict', 'credentials', 'config']:
                    target = getattr(model, attr, {})
                    if isinstance(target, dict) and 'usernames' in target:
                        user_data = target['usernames'].get(username_novo)
                        if user_data:
                            break
            except Exception:
                pass

            # ✅ SÓ SALVA SE TIVER HASH
            if user_data and 'password' in user_data:

                sucesso_db = salvar_novo_usuario_db(
                    username=email_novo,
                    email=email_novo,
                    name=nome_novo,
                    password_hashed=user_data['password']
                )

                if sucesso_db:
                    invalidar_cache_authenticator()
                    st.success(f'✅ Conta criada com sucesso! Faça login para continuar.')
                    st.balloons()

                    time.sleep(1.5)  # ⏳ espera 1.5 segundos

                    st.rerun()

            else:
                st.error("Erro ao localizar hash da senha.")

    except Exception as e:
        if "NoneType" not in str(e):
            st.error(f"Erro no processo de cadastro: {e}")


# --- SE ESTIVER LOGADO ---
usuario_atual = st.session_state.get("user")

# --- CONTEÚDO LOGADO ---
if st.session_state.get("authentication_status"):
    authenticator.logout('Sair', 'sidebar')
    
    user_id = st.session_state["username"]
    st.session_state["user_id"] = user_id
    
    # REFORMA NA BUSCA DE INFO: Buscamos do DB em vez de config['credentials']
    try:
        credentials = carregar_usuarios_db()
        user_info = credentials['usernames'][user_id]
        st.session_state["user_name"] = user_info.get('name', 'Usuário')
    except KeyError:
        st.error("Erro ao recuperar dados da sessão. Por favor, faça login novamente.")
        st.stop()

    

    # --- CONTEÚDO DA HOME ---
    st.title("💰 Sistema de Gestão Financeira")
    st.markdown(f"### Bem-vindo, {st.session_state['user_name']}! 👋")
    st.write("---")

    st.markdown("### 🚀 Guia de Navegação")

    st.info("💡 **Dica Mobile:** Toque no ícone de menu ( **»** ) no canto superior esquerdo para navegar pelas páginas.")
    
    st.info("""
    **📥 Importação de faturas** - Envie PDFs de faturas. O sistema detecta o banco e evita duplicatas automaticamente.

    **📱 Importação de SMS** - Utilize SMS recebidos para manter as transações atualizadas. Suporte a upload de arquivos .txt e colagem direta.

    **✍️ Inclusão Manual** - Registre gastos em dinheiro ou extras. Ideal para saques, PIX avulsos ou taxas.
            
    **📑 Transações** - Gerencie e categorize seus dados. Valide as sugestões de nossa IA e replique regras.

    **📈 Dashboard** - Analise suas médias e totais. Visão macro com filtros específicos para Gastos Fixos.
    
    **📊 Orçamento** - Defina suas metas mensais. Acompanhe o planejado vs. realizado com alertas de teto.
    """)

    st.write("---")

    # --- CONFIGURAÇÃO DE CUSTOS FIXOS ---
    with st.expander("⚙️ Configurações do Sistema", expanded=True):
        st.subheader("Definição de Gastos Fixos")
        st.markdown("Marque as categorias que representam custos recorrentes:")

        # Identificador do usuário logado
        usuario_atual = st.session_state["username"]

        # 1. Categorias padrão do sistema
        categorias_base = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado"}

        # 2. BUSCA INDIVIDUALIZADA: Em vez de ler o JSON, lemos as regras do banco para este usuário
        try:
            regras_usuario = carregar_regras_db(usuario_atual)
            # Pegamos os nomes das categorias que o usuário já criou/personalizou
            cats_personalizadas = set(str(v) for v in regras_usuario.values() if v)
        except Exception as e:
            st.error(f"Erro ao carregar categorias: {e}")
            cats_personalizadas = set()

        # 3. Une as categorias base com as que o usuário criou no banco
        set_todas = categorias_base.union(cats_personalizadas)
        termos_proibidos = {"Sem categoria", "None", "nan", "", "---", "Descontos", "Outros", "Juros", "Multa", "Impostos", None}

        todas_as_categorias = sorted([
            str(cat) for cat in set_todas
            if cat and str(cat).strip() not in termos_proibidos
        ])

        # Carrega quais dessas categorias são consideradas "Gastos Fixos" para este usuário
        fixas_atuais = get_gastos_fixos(usuario_atual)

        if todas_as_categorias:
            cols_fixos = st.columns(4)
            for i, cat in enumerate(todas_as_categorias):
                with cols_fixos[i % 4]:
                    # Usamos um checkbox para cada categoria
                    checado = st.checkbox(cat, value=(cat in fixas_atuais), key=f"cfg_{cat}")
                    
                    # Se o usuário marcar/desmarcar, salvamos no banco vinculando ao ID dele
                    if checado != (cat in fixas_atuais):
                        salvar_config_categoria(cat, checado, usuario_atual)
                        st.rerun() 
        else:
            st.info("Nenhuma categoria encontrada no seu perfil.")

    st.write("---")
    st.caption("v2.5 | Sistema de Automação Financeira Pessoal")