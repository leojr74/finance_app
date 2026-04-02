def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token

    token = st.session_state.get("session_token")

    if not token:
        cookie_manager = stx.CookieManager(key="auth_check")
        token = cookie_manager.get("session_token")

        if token:
            st.session_state["session_token"] = token
        else:
            tentativas = st.session_state.get("_cookie_check_count", 0)
            if tentativas < 2:  # aguarda até 2 renders
                st.session_state["_cookie_check_count"] = tentativas + 1
                st.rerun()

            st.session_state.pop("_cookie_check_count", None)
            st.warning("Faça login para continuar")
            st.stop()

    st.session_state.pop("_cookie_check_count", None)

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
    st.session_state["name"] = user.name
    st.session_state["user_name"] = user.name

    return user.email
