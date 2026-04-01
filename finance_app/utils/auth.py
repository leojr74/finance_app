def check_login():
    import streamlit as st

    if not st.session_state.get("logged_in"):

        user_url = st.query_params.get("user")

        # 🔥 CORREÇÃO CRÍTICA
        if user_url:
            if isinstance(user_url, list):
                user_url = user_url[0]

            st.session_state["logged_in"] = True
            st.session_state["user"] = user_url
            st.session_state["user_name"] = user_url

    if not st.session_state.get("logged_in"):
        st.warning("Faça login para continuar")
        st.stop()

    return st.session_state["user"]