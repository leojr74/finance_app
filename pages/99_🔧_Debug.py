import streamlit as st
import pkg_resources

st.title("🔧 Diagnóstico de Versões")

pacotes = [
    "streamlit",
    "streamlit-authenticator",
    "PyYAML",
    "sqlalchemy",
    "pandas",
    "numpy",
    "psycopg2-binary",
    "fpdf",
    "altair",
    "pymupdf",
    "python-dateutil",
    "plotly",
]

for p in pacotes:
    try:
        v = pkg_resources.get_distribution(p).version
        st.write(f"**{p}**: `{v}`")
    except Exception:
        st.warning(f"{p}: não encontrado")
