import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from ui import apply_global_style
from categorizer import load_categories

# set_page_config DEVE ser chamado UMA SÓ VEZ
st.set_page_config(
    page_title="Finanças Pessoais",
    page_icon="💰",
    layout="wide"
)

# --- CARREGAR CONFIGURAÇÕES ---
try:
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.load(file, Loader=SafeLoader)
except Exception as e:
    st.error(f"Erro ao carregar config.yaml: {e}")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- INTERFACE DE ACESSO (LOGIN / CADASTRO) ---
if not st.session_state.get("authentication_status"):
    # Centraliza o formulário na tela
    _, col_central, _ = st.columns([1, 2, 1])
    
    with col_central:
        tab_login, tab_signup = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            authenticator.login(location='main')
            if st.session_state.get("authentication_status") is False:
                st.error('Usuário ou senha incorretos')
            elif st.session_state.get("authentication_status") is None:
                st.info('Por favor, faça login para acessar.')

        with tab_signup:
            try:
                # CORREÇÃO AQUI: Removemos o argumento pre_authorized. 
                # Sem ele, a biblioteca entende que o cadastro está aberto.
                resultado = authenticator.register_user(location='main')
                
                if resultado:
                    # Se o registro foi bem-sucedido, o 'config' na memória já tem os dados.
                    # Agora escrevemos isso no arquivo config.yaml
                    with open('config.yaml', 'w', encoding='utf-8') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success('Usuário registrado com sucesso! Agora clique na aba "Entrar".')
            except Exception as e:
                # Caso a sua instalação específica ainda peça um título, use: 
                # authenticator.register_user('Registrar', location='main')
                st.error(f"Erro no cadastro: {e}")

# --- CONTEÚDO LOGADO ---
if st.session_state.get("authentication_status"):
    authenticator.logout('Sair', 'sidebar')
    
    # Define o e-mail na sessão para usarmos no Supabase
    username = st.session_state["username"]
    st.session_state["user_email"] = config['credentials']['usernames'][username]['email']
    
    # Importação atrasada para evitar conflitos de banco de dados antes do login
    from database import criar_tabela, get_categorias_completas, get_gastos_fixos, salvar_config_categoria

    apply_global_style()
    criar_tabela()

    # --- CONTEÚDO DA HOME ---
    st.title("💰 Sistema de Gestão Financeira")
    st.markdown(f"### Bem-vindo, {st.session_state['name']}!")
    st.write("---")

    st.markdown("### 🚀 Guia de Navegação")
    
    st.info("""
    **📥 Importação** Envie PDFs de faturas. O sistema detecta o banco e evita duplicatas automaticamente.

    **✍️ Inclusão Manual** Registre gastos em dinheiro ou extras. Ideal para saques, PIX avulsos ou taxas.

    **📑 Transações** Gerencie e categorize seus dados. Valide as sugestões de nossa IA e replique regras.

    **📈 Dashboard** Analise suas médias e totais. Visão macro com filtros específicos para Gastos Fixos.
    
    **📊 Orçamento** Defina suas metas mensais. Acompanhe o planejado vs. realizado com alertas de teto.
    """)

    st.write("---")

    # --- CONFIGURAÇÃO DE CUSTOS FIXOS ---
    with st.expander("⚙️ Configurações do Sistema", expanded=True):
        st.subheader("Definição de Gastos Fixos")
        st.markdown("Marque as categorias que representam custos recorrentes:")

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
            mudancas = {}
            cols_fixos = st.columns(4)
            for i, cat in enumerate(todas_as_categorias):
                with cols_fixos[i % 4]:
                    checado = st.checkbox(cat, value=(cat in fixas_atuais), key=f"cfg_{cat}")
                    if checado != (cat in fixas_atuais):
                        mudancas[cat] = checado

            if mudancas:
                for cat, valor in mudancas.items():
                    salvar_config_categoria(cat, valor)
                st.rerun()
        else:
            st.info("Nenhuma categoria encontrada.")

    st.write("---")
    st.caption("v2.5 | Sistema de Automação Financeira Pessoal")