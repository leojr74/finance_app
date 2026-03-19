import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from categorizer import load_categories, find_category
from ui import apply_global_style

apply_global_style()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Inclusão Manual", layout="wide")

st.title("✍️ Inclusão Manual")
st.markdown("Registre gastos em dinheiro, Pix ou outras transações manuais.")

# --- 1. CARREGAMENTO DE OPÇÕES (BANCOS E CATEGORIAS) ---
rules = load_categories()

# Busca bancos existentes no banco de dados
try:
    conn = sqlite3.connect("transacoes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT banco FROM transacoes WHERE banco IS NOT NULL AND banco != ''")
    bancos_no_db = [row[0] for row in cursor.fetchall()]
    conn.close()
except:
    bancos_no_db = []

# Lista dinâmica de bancos
opcoes_banco = sorted(list(set(bancos_no_db))) + ["➕ Adicionar novo banco..."]

# Categorias (Unindo fixas + JSON)
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}
cats_do_json = set(str(v) for v in rules.values() if v)
lista_categorias = sorted(cats_do_json.union(categorias_fixas))

# --- 2. SELEÇÃO DE BANCO (FORA DO FORM PARA REATIVIDADE) ---
st.subheader("🏦 Origem da Transação")
c_b1, c_b2 = st.columns([1, 1])

with c_b1:
    banco_sel = st.selectbox("Selecione o Banco", options=opcoes_banco)

novo_banco_nome = ""
if banco_sel == "➕ Adicionar novo banco...":
    with c_b2:
        novo_banco_nome = st.text_input("Nome do novo banco:", placeholder="Ex: INTER, XP, DINHEIRO...").upper().strip()

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
            
            # 1. PROTEÇÃO: Só tenta buscar categoria se houver texto
            cat_sugerida = find_category(desc_ins, rules) if desc_ins else "Sem categoria"
            
            # Garante que a sugerida esteja na lista
            if cat_sugerida not in lista_categorias:
                lista_categorias.append(cat_sugerida)
                lista_categorias.sort()

            # 2. PROTEÇÃO: Cálculo de índice seguro para evitar o erro de milissegundos
            try:
                index_atual = lista_categorias.index(cat_sugerida)
            except (ValueError, KeyError):
                index_atual = 0 # Caso a categoria suma da lista por um instante, volta ao início

            categoria_ins = st.selectbox(
                "Categoria", 
                options=lista_categorias, 
                index=index_atual # Usa o índice seguro calculado acima
            )

        submit = st.form_submit_button("💾 Salvar Transação", type="primary")

# --- 4. LÓGICA DE SALVAMENTO ---
if submit:
    # Define qual nome de banco usar
    banco_final = novo_banco_nome if banco_sel == "➕ Adicionar novo banco..." else banco_sel
    
    # Validações básicas
    if not desc_ins or valor_ins <= 0:
        st.error("❌ Preencha a descrição e um valor maior que zero.")
    elif banco_sel == "➕ Adicionar novo banco..." and not novo_banco_nome:
        st.error("❌ Digite o nome do novo banco para continuar.")
    else:
        try:
            conn = sqlite3.connect("transacoes.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data_ins.strftime("%Y-%m-%d"),
                desc_ins,
                valor_ins,
                categoria_ins,
                banco_final,
                "MANUAL_ENTRY"
            ))
            
            conn.commit()
            conn.close()
            
            # Limpa cache do session_state para as outras páginas
            if "df_transacoes" in st.session_state:
                del st.session_state.df_transacoes
            
            st.success(f"✅ Transação '{desc_ins}' salva com sucesso!")
            st.rerun() # Recarrega para limpar campos e atualizar lista de bancos
            
        except Exception as e:
            st.error(f"⚠️ Erro ao acessar o banco de dados: {e}")

# --- 5. VISUALIZAÇÃO DOS ÚLTIMOS LANÇAMENTOS ---
st.write("---")
st.subheader("📋 Últimos Lançamentos Manuais")

try:
    conn = sqlite3.connect("transacoes.db")
    # Nota: Verifique se no seu INSERT você está usando 'MANUAL_ENTRY' ou 'MANUAL'
    df_recent = pd.read_sql_query("""
        SELECT data, descricao, valor, categoria, banco 
        FROM transacoes 
        WHERE hash_fatura = 'MANUAL_ENTRY'
        ORDER BY id DESC LIMIT 5
    """, conn)
    conn.close()
    
    if not df_recent.empty:
        # Garantimos que a data seja tratada como objeto de data para o formatador do Streamlit
        df_recent["data"] = pd.to_datetime(df_recent["data"])
        
        st.dataframe(
            df_recent, 
            width='stretch', 
            hide_index=True,
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "descricao": "Descrição",  # Ajuste do cabeçalho
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "categoria": "Categoria",
                "banco": "Banco/Cartão"
            }
        )
    else:
        st.info("Nenhuma transação manual encontrada até o momento.")
except Exception as e:
    # Mostramos o aviso, mas sem travar o app
    st.warning("Não foi possível carregar o histórico recente.")