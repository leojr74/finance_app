def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token

    token = st.session_state.get("session_token")

    if not token:
        cookie_manager = stx.CookieManager(key="auth_check")
        token = cookie_manager.get("session_token")

        tentativas = st.session_state.get("_cookie_check_count", 0)
        
        # mostra o estado atual para debug
        st.info(f"Render #{tentativas + 1} | token do cookie: {token}")
        st.stop()

    st.session_state["session_token"] = token

    blacklist = st.session_state.get("token_blacklist", set())
    if not token or token in blacklist:
        # Redireciona para home sem mostrar nenhuma mensagem
        st.switch_page("00_🏠_Home.py")

    user = buscar_usuario_por_token(token)
    if not user:
        st.session_state.pop("session_token", None)
        st.switch_page("00_🏠_Home.py")

    st.session_state["user"] = user.email
    st.session_state["name"] = user.name
    st.session_state["user_name"] = user.name

    return user.email