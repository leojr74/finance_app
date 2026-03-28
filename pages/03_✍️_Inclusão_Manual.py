import streamlit as st
import pandas as pd
from datetime import date
from categorizer import load_categories, find_category
from ui import apply_global_style
from database import conectar, get_authenticator

st.set_page_config(
    page_title="Inclusão Manual de Transações",
    page_icon="✍️",
    layout="wide"
)

authenticator = get_authenticator()
authenticator.login(location='unrendered') 

if not st.session_state.get("authentication_status"):
    st.warning("Sessão expirada. Por favor, faça login na Home.")
    st.stop()

usuario_atual = st.session_state["username"] 
apply_global_style()

apply_global_style()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.title("✍️ Inclusão Manual de Transações")
st.markdown(f"Registre gastos para a conta de **{st.session_state['name']}**.")

# --- 1. CARREGAMENTO DE OPÇÕES (BANCOS E CATEGORIAS) ---
rules = load_categories()

# Busca bancos existentes no banco de dados FILTRADOS pelo usuário
try:
    conn = conectar()
    cursor = conn.cursor()
    # Adicionado filtro de user_id para não sugerir bancos de terceiros
    cursor.execute("""
        SELECT DISTINCT banco 
        FROM transacoes 
        WHERE banco IS NOT NULL AND banco != '' AND user_id = %s
    """, (usuario_atual,))
    bancos_no_db = [row[0] for row in cursor.fetchall()]
    conn.close()
except:
    bancos_no_db = []

# Lista dinâmica de bancos
opcoes_banco = sorted(list(set(bancos_no_db))) + ["➕ Adicionar novo banco..."]

# Categorias (Unindo fixas + JSON)
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}
try:
    cats_do_json = set(str(v) for v in rules.values() if v)
except:
    cats_do_json = set()
lista_categorias = sorted(cats_do_json.union(categorias_fixas))

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
            
            cat_sugerida = find_category(desc_ins, rules) if desc_ins else "Sem categoria"
            
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
            conn = conectar()
            cursor = conn.cursor()
            
            # INSERÇÃO INCLUINDO O USER_ID
            cursor.execute("""
                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data_ins.strftime("%Y-%m-%d"),
                desc_ins,
                valor_ins,
                categoria_ins,
                banco_final,
                "MANUAL_ENTRY",
                usuario_atual
            ))
            
            conn.commit()
            conn.close()
            
            if "df_transacoes" in st.session_state:
                del st.session_state.df_transacoes
            
            st.success(f"✅ Transação salva com sucesso!")
            st.rerun()
            
        except Exception as e:
            st.error(f"⚠️ Erro ao acessar o banco de dados: {e}")

# --- 5. VISUALIZAÇÃO DOS ÚLTIMOS LANÇAMENTOS ---
st.write("---")
st.subheader("📋 Seus Últimos Lançamentos Manuais")

try:
    conn = conectar()
    # FILTRO: Apenas transações manuais DESTE usuário
    df_recent = pd.read_sql_query("""
        SELECT data, descricao, valor, categoria, banco 
        FROM transacoes 
        WHERE hash_fatura = 'MANUAL_ENTRY' AND user_id = %s
        ORDER BY id DESC LIMIT 5
    """, conn, params=(usuario_atual,))
    conn.close()
    
    if not df_recent.empty:
        df_recent["data"] = pd.to_datetime(df_recent["data"])
        st.dataframe(
            df_recent, 
            width = 'stretch', 
            hide_index=True,
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
            }
        )
    else:
        st.info("Nenhuma transação manual encontrada para o seu usuário.")
except Exception as e:
    st.warning("Não foi possível carregar o histórico recente.")