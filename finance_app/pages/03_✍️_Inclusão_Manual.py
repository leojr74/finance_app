import streamlit as st
import pandas as pd
from datetime import date
from categorizer import find_category
from ui import apply_global_style
from database import carregar_regras_db, get_engine
from sqlalchemy import text

st.set_page_config(
    page_title="Inclusão Manual de Transações",
    page_icon="✍️",
    layout="wide"
)

# 🔥 RESTAURA SESSÃO VIA URL (igual Home)
if not st.session_state.get("logged_in"):
    user_url = st.query_params.get("user")

    if user_url:
        st.session_state["logged_in"] = True
        st.session_state["user"] = user_url
        st.session_state["user_name"] = user_url  # fallback


# 🔐 PROTEÇÃO DE PÁGINA
if not st.session_state.get("logged_in"):
    st.warning("Faça login para continuar")
    st.stop()

usuario_atual = st.session_state["user"]

apply_global_style()


# --- CONFIGURAÇÃO DA PÁGINA ---
st.title("✍️ Inclusão Manual de Transações")
st.markdown(f"Registre gastos para a conta de **{st.session_state['user_name']}**.")

# --- 1. CARREGAMENTO DE OPÇÕES (BANCOS E CATEGORIAS) ---
regras_usuario = carregar_regras_db(usuario_atual)

# Busca bancos existentes no banco de dados FILTRADOS pelo usuário
try:
    engine = get_engine()
    query = text("""
        SELECT DISTINCT banco 
        FROM transacoes 
        WHERE banco IS NOT NULL 
          AND banco != '' 
          AND user_id = :u
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"u": usuario_atual})
        # No SQLAlchemy, acessamos a coluna pelo índice ou nome
        bancos_no_db = [row[0] for row in result.fetchall()]
except Exception as e:
    st.error(f"Erro ao carregar bancos: {e}")
    bancos_no_db = []

# Lista dinâmica de bancos
opcoes_banco = sorted(list(set(bancos_no_db))) + ["➕ Adicionar novo banco..."]

# Categorias (Unindo fixas + JSON)
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}
cats_do_usuario = set(regras_usuario.values())
lista_categorias = sorted(cats_do_usuario.union(categorias_fixas))

# --- 2. SELEÇÃO DE BANCO ---
st.subheader("🏦 Origem da Transação")
c_b1, c_b2 = st.columns([1, 1])

with c_b1:
    banco_sel = st.selectbox("Selecione o Banco", options=opcoes_banco)

novo_banco_nome = ""
if banco_sel == "➕ Adicionar novo banco...":
    with c_b2:
        novo_banco_nome = st.text_input("Nome do novo banco:", placeholder="Ex: DINHEIRO, PIX...").upper().strip()

# --- 3. FORMULÁRIO DE DETALHES DA TRANSAÇÃO ---
st.write("---")
st.subheader("📝 Detalhes do Gasto")

with st.container(border=True):
    with st.form("form_manual", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            data_ins = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            valor_ins = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        
        with col2:
            desc_ins = st.text_input("Descrição (Ex: Padaria da Esquina)").upper().strip()
            
            cat_sugerida = find_category(desc_ins, regras_usuario) if desc_ins else "Sem categoria"
            
            if cat_sugerida not in lista_categorias:
                lista_categorias.append(cat_sugerida)
                lista_categorias.sort()

            try:
                index_atual = lista_categorias.index(cat_sugerida)
            except (ValueError, KeyError):
                index_atual = 0

            categoria_ins = st.selectbox(
                "Categoria", 
                options=lista_categorias, 
                index=index_atual
            )

        submit = st.form_submit_button("💾 Salvar Transação", type="primary")

# --- 4. LÓGICA DE SALVAMENTO ---
if submit:
    banco_final = novo_banco_nome if banco_sel == "➕ Adicionar novo banco..." else banco_sel
    
    if not desc_ins or valor_ins <= 0:
        st.error("❌ Preencha a descrição e um valor maior que zero.")
    elif banco_sel == "➕ Adicionar novo banco..." and not novo_banco_nome:
        st.error("❌ Digite o nome do novo banco para continuar.")
    else:
        try:
            engine = get_engine()
            
            # Definimos a query com parâmetros nomeados (:nome)
            query = text("""
                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id)
                VALUES (:dat, :des, :val, :cat, :bnc, :hsh, :uid)
            """)
            
            # Criamos o dicionário de dados para a inserção
            dados = {
                "dat": data_ins.strftime("%Y-%m-%d"),
                "des": desc_ins,
                "val": valor_ins,
                "cat": categoria_ins,
                "bnc": banco_final,
                "hsh": "MANUAL_ENTRY",
                "uid": usuario_atual
            }
            
            # engine.begin() garante o commit automático ao final do bloco
            with engine.begin() as conn:
                conn.execute(query, dados)
            
            # Limpeza de cache para forçar a atualização dos gráficos/tabelas
            if "df_transacoes" in st.session_state:
                del st.session_state.df_transacoes
            
            st.success(f"✅ Transação salva com sucesso!")
            st.rerun()
            
        except Exception as e:
            st.error(f"⚠️ Erro ao acessar o banco de dados: {e}")
