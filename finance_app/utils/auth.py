def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token

    cookie_manager = stx.CookieManager()
    token = cookie_manager.get("session_token")

    if not token:
        st.warning("Faça login para continuar")
        st.stop()

    user = buscar_usuario_por_token(token)

    if not user:
        st.warning("Sessão inválida. Faça login novamente.")
        st.stop()

    st.session_state["user"] = user.email
    st.session_state["user_name"] = user.name

    return user.email