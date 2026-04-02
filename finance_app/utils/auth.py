def check_login():
    import streamlit as st
    import extra_streamlit_components as stx
    from database import buscar_usuario_por_token

    # Se já tem token no session_state, usa direto (sem precisar do cookie)
    token = st.session_state.get("session_token")

    if not token:
        # Tenta ler o cookie
        cookie_manager = stx.CookieManager(key="auth_check")
        token = cookie_manager.get("session_token")

        if token:
            # Sincroniza com session_state para próximas páginas
            st.session_state["session_token"] = token
        else:
            # Cookie ainda não carregou — aguarda mais um render silencioso
            if not st.session_state.get("_cookie_checked"):
                st.session_state["_cookie_checked"] = True
                st.rerun()

            # Segundo render sem token = não está logado
            st.session_state.pop("_cookie_checked", None)
            st.warning("Faça login para continuar")
            st.stop()

    # Limpa flag de verificação
    st.session_state.pop("_cookie_checked", None)

    # Verifica blacklist (logout recente)
    blacklist = st.session_state.get("token_blacklist", set())
    if token in blacklist:
        st.warning("Faça login para continuar")
        st.stop()

    # Valida token no banco
    user = buscar_usuario_por_token(token)

    if not user:
        st.session_state.pop("session_token", None)
        st.warning("Sessão inválida. Faça login novamente.")
        st.stop()

    st.session_state["user"] = user.email
    st.session_state["name"] = user.name
    st.session_state["user_name"] = user.name

    return user.email
