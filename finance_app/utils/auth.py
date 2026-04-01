def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token

    cookie_manager = stx.CookieManager()

    # prioriza session_state (imediato)
    token = st.session_state.get("session_token")

    # só busca cookie se não tiver no session_state
    if not token:
        token = cookie_manager.get("session_token")
        if token:
            st.session_state["session_token"] = token

    if not token:
        st.warning("Faça login para continuar")
        st.stop()

    # verifica blacklist (logout recente)
    blacklist = st.session_state.get("token_blacklist", set())
    if token in blacklist:
        st.warning("Faça login para continuar")
        st.stop()

    user = buscar_usuario_por_token(token)

    if not user:
        st.session_state.pop("session_token", None)
        st.warning("Sessão inválida. Faça login novamente.")
        st.stop()

    st.session_state["user"] = user.email
    st.session_state["user_name"] = user.name

    return user.email