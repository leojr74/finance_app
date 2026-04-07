def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token
    import time

    # 1. Tenta pegar do session_state (mais rápido)
    token = st.session_state.get("session_token")

    # 2. Se não estiver no session_state (caso do F5), tenta o Cookie
    if not token:
        cookie_manager = stx.CookieManager(key="auth_check")
        
        # O segredo está aqui: o componente de cookie precisa de alguns milissegundos 
        # para "acordar" após um F5. Tentamos 3 vezes antes de desistir.
        for _ in range(3):
            token = cookie_manager.get("session_token")
            if token:
                st.session_state["session_token"] = token
                break
            time.sleep(0.5) # Pequena pausa para o componente carregar

    # 3. Se após as tentativas ainda não houver token, aí sim redireciona
    if not token:
        # Verifica se estamos na Home. Se não estivermos, manda pra lá.
        # Isso evita o loop infinito em páginas internas.
        try:
            st.switch_page("00_🏠_Home.py") 
        except:
            # Se der erro no switch_page (ex: arquivo com nome diferente),
            # apenas mostra o aviso e para.
            st.error("Sessão expirada. Por favor, volte à página inicial.")
        st.stop()

    # 4. Verifica Blacklist
    blacklist = st.session_state.get("token_blacklist", set())
    if token in blacklist:
        st.warning("Acesso negado.")
        st.stop()

    # 5. Valida no Banco de Dados
    user = buscar_usuario_por_token(token)

    if not user:
        st.session_state.pop("session_token", None)
        st.error("Sessão inválida no banco de dados. Faça login novamente.")
        st.stop()

    # 6. Atualiza dados da sessão
    st.session_state["user"] = user.email
    st.session_state["name"] = user.name
    st.session_state["user_name"] = user.name

    return user.email