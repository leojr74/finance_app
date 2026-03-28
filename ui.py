import streamlit as st

def apply_global_style():

    st.markdown("""
        <style>
        
        /* Espaçamento geral */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        /* Títulos */
        h1, h2, h3 {
            font-weight: 600;
        }

        /* Cards visuais */
        .card {
            background-color: #111;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #222;
        }

        /* Métricas */
        [data-testid="stMetric"] {
            background-color: #111;
            border: 1px solid #222;
            padding: 12px;
            border-radius: 10px;
        }

        /* Data editor */
        .stDataFrame, .stDataEditor {
            border-radius: 10px;
            border: 1px solid #222;
        }

        /* Botões */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
        }

        /* Tradução dos labels do streamlit-authenticator */
        /* Primeiro stTextInput do formulário = campo Username */
        div[data-testid="stTextInput"]:first-of-type label span p {
            visibility: hidden;
            position: relative;
        }
        div[data-testid="stTextInput"]:first-of-type label span p::after {
            content: "Email";
            visibility: visible;
            position: absolute;
            left: 0;
        }

        [data-testid="stTextInput"]:has(input[type="password"]) label span p {
            visibility: hidden;
            position: relative;
        }
        [data-testid="stTextInput"]:has(input[type="password"]) label span p::after {
            content: "Senha";
            visibility: visible;
            position: absolute;
            left: 0;
        }

        </style>
    """, unsafe_allow_html=True)