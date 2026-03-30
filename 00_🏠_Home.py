import streamlit as st
import streamlit_authenticator as stauth
import os
import yaml
from ui import apply_global_style
from categorizer import load_categories
from database import carregar_usuarios_db, check_auth, salvar_novo_usuario_db, criar_tabela

st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, 'config.yaml')

apply_global_style()
criar_tabela()

# --- CARREGAR CONFIGURAÇÕES ---
try:
    with open(config_path) as file:
        config = yaml.load(file, Loader=yaml.SafeLoader)
except Exception as e:
    st.error(f"Erro ao carregar config.yaml: {e}")
    st.stop()

config['credentials'] = carregar_usuarios_db()
cookie_key = st.secrets["auth"]["cookie_key"]

authenticator = stauth.Authenticate(
    credentials=config['credentials'],
    cookie_name=config['cookie']['name'],
    cookie_key=cookie_key,
    cookie_expiry_days=config['cookie']['expiry_days'], # MUDOU: era cookie_expiry_days
    validator=None
)

# --- INTERFACE DE ACESSO (LOGIN / CADASTRO) ---
if not st.session_state.get("authentication_status"):
    # Centraliza o formulário na tela
    _, col_central, _ = st.columns([1, 2, 1])
    
    with col_central:
        tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            authenticator.login(
                location='main',
                fields={
                    'Form name': 'Acesso',
                    'Username': 'Email',    # Substitui "Username" por "Email"
                    'Password': 'Senha',    # Substitui "Password" por "Senha"
                    'Login': 'Entrar'       # Substitui o texto do botão "Login" por "Entrar"
                }
            )
            if st.session_state.get("authentication_status") is False:
                st.error('Usuário ou senha incorretos')
            elif st.session_state.get("authentication_status") is None:
                st.info('Por favor, faça login para acessar.')

        with tab_signup:
            try:
                resultado = authenticator.register_user(
                    location='main',
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

                if resultado and resultado[1]:
                    email_novo, username_novo, nome_novo = resultado

                    # O authenticator registra com username como chave temporariamente.
                    # Buscamos a senha por username, mas salvamos e logamos por email.
                    user_data = config['credentials']['usernames'].get(username_novo)

                    if user_data:
                        senha_para_salvar = user_data['password']

                        sucesso_db = salvar_novo_usuario_db(
                            username=email_novo,   # <-- salva o EMAIL no campo username do banco
                            email=email_novo,
                            name=nome_novo,
                            password_hashed=senha_para_salvar
                        )

                        if sucesso_db:
                            st.success(f'✅ Conta para {nome_novo} criada com sucesso!')
                            st.info("Acesse a aba 'Entrar' para começar.")
                            st.balloons()
                    else:
                        st.error("Erro ao recuperar senha. Tente novamente.")

            except Exception as e:
                if "NoneType" not in str(e):
                    st.error(f"Erro no processo de cadastro: {e}")

# --- CONTEÚDO LOGADO ---
if st.session_state.get("authentication_status"):
    authenticator.logout('Sair', 'sidebar')
    
    # O 'username' do session_state será o que o usuário digitou (apelido ou e-mail)
    user_id = st.session_state["username"]
    st.session_state["user_id"] = user_id
    
    # Buscamos os dados desse login no dicionário que carregamos do Supabase
    # Como mapeamos o e-mail e o username para o mesmo objeto, user_info será o mesmo
    try:
        user_info = config['credentials']['usernames'][user_id]
        st.session_state["user_name"] = user_info.get('name', 'Usuário')
        
    except KeyError:
        # Fallback de segurança caso algo falhe na busca do dicionário
        st.error("Erro ao recuperar dados da sessão. Por favor, faça login novamente.")
        st.stop()

    # Importação das funções do banco de dados
    from database import get_gastos_fixos, salvar_config_categoria

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

        # Identificador do usuário logado (usamos o username do config.yaml)
        usuario_atual = st.session_state["username"]

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

        # CORREÇÃO: Passando o usuario_atual para carregar apenas as configurações DELE
        fixas_atuais = get_gastos_fixos(usuario_atual)

        if todas_as_categorias:
            cols_fixos = st.columns(4)
            for i, cat in enumerate(todas_as_categorias):
                with cols_fixos[i % 4]:
                    # Usamos um checkbox para cada categoria
                    checado = st.checkbox(cat, value=(cat in fixas_atuais), key=f"cfg_{cat}")
                    
                    # Verificação de mudança: Se o estado do checkbox mudou em relação ao banco
                    if checado != (cat in fixas_atuais):
                        # CORREÇÃO: Passando os 3 argumentos: categoria, booleano e user_id
                        salvar_config_categoria(cat, checado, usuario_atual)
                        st.rerun() # Reinicia para atualizar a lista 'fixas_atuais'
        else:
            st.info("Nenhuma categoria encontrada.")

    st.write("---")
    st.caption("v2.5 | Sistema de Automação Financeira Pessoal")