import streamlit as st
from importlib.metadata import version, PackageNotFoundError

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
        v = version(p)
        st.write(f"**{p}**: `{v}`")
    except PackageNotFoundError:
        st.warning(f"{p}: não encontrado")
