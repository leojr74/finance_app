import streamlit as st
from importlib.metadata import version, PackageNotFoundError
import yaml, os
import inspect
import streamlit_authenticator as stauth
src = inspect.getsource(stauth.Authenticate.register_user)
st.code(src)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, '..', 'config.yaml')
with open(config_path) as f:
    config = yaml.safe_load(f)
st.write("config.yaml carregado:", config)
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
