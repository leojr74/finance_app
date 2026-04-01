def check_login():
    import streamlit as st
    from database import buscar_usuario_por_token

    # ✅ 1. já está logado → segue
    if st.session_state.get("logged_in"):
        return st.session_state["user"]

    # ✅ 2. tenta restaurar via token salvo
    token = st.session_state.get("token")

    if token:
        user = buscar_usuario_por_token(token)

        if user:
            st.session_state["logged_in"] = True
            st.session_state["user"] = user.email
            st.session_state["user_name"] = user.name
            return user.email

    # ❌ 3. bloqueia
    st.warning("Faça login para continuar")
    st.stop()