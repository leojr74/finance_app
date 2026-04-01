def check_login():
    import streamlit as st
    from database import buscar_usuario_por_token

    token = st.query_params.get("token")

    if isinstance(token, list):
        token = token[0]

    if token:
        user = buscar_usuario_por_token(token)

        if user:
            st.session_state["logged_in"] = True
            st.session_state["user"] = user.email
            st.session_state["user_name"] = user.name
            return user.email

    st.warning("Faça login para continuar")
    st.stop()