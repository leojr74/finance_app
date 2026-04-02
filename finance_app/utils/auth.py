def check_login():
    import streamlit as st
    from database import buscar_usuario_por_token

    token = st.session_state.get("session_token")

    if not token:
        # lê o cookie nativamente — síncrono, sem delay
        token = st.context.cookies.get("session_token")
        if token:
            st.session_state["session_token"] = token

    if not token:
        st.warning("Faça login para continuar")
        st.stop()

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
