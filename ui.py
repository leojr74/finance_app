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

        </style>
    """, unsafe_allow_html=True)