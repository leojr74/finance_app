import streamlit as st
import pandas as pd
from datetime import date
from categorizer import get_all_rules, find_category
from ui import apply_global_style
from database import get_engine, get_authenticator
from sqlalchemy import text

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


# --- CONFIGURAÇÃO DA PÁGINA ---
st.title("✍️ Inclusão Manual de Transações")
st.markdown(f"Registre gastos para a conta de **{st.session_state['name']}**.")

# --- 1. CARREGAMENTO DE OPÇÕES (BANCOS E CATEGORIAS) ---
rules = get_all_rules(usuario_atual)

# Busca bancos existentes no banco de dados FILTRADOS pelo usuário
try:
    engine = get_engine()
    # Usamos connect() pois é uma operação de leitura simples (SELECT)
    with engine.connect() as conn:
        query = text("""
            SELECT DISTINCT banco 
            FROM transacoes 
            WHERE banco IS NOT NULL 
              AND banco != '' 
              AND user_id = :u
        """)
        result = conn.execute(query, {"u": usuario_atual}).fetchall()
        # O row[0] continua acessando a primeira (e única) coluna da query
        bancos_no_db = [row[0] for row in result]
except Exception as e:
    # Em caso de erro (ex: tabela não existe ainda), retornamos lista vazia
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

# --- 4. LÓGICA DE SALVAMENTO (MANUAL) ---
if submit:
    banco_final = novo_banco_nome if banco_sel == "➕ Adicionar novo banco..." else banco_sel
    
    if not desc_ins or valor_ins <= 0:
        st.error("❌ Preencha a descrição e um valor maior que zero.")
    elif banco_sel == "➕ Adicionar novo banco..." and not novo_banco_nome:
        st.error("❌ Digite o nome do novo banco para continuar.")
    else:
        try:
            from database import get_engine
            from sqlalchemy import text
            
            engine = get_engine()
            
            # Preparamos a query com parâmetros nomeados (:)
            query = text("""
                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id)
                VALUES (:data, :desc, :valor, :cat, :banco, :hash, :user)
            """)
            
            # O dicionário de dados para a inserção
            dados_manual = {
                "data": data_ins.strftime("%Y-%m-%d"),
                "desc": desc_ins,
                "valor": valor_ins,
                "cat": categoria_ins,
                "banco": banco_final,
                "hash": "MANUAL_ENTRY",
                "user": usuario_atual
            }
            
            # Executa com commit automático via engine.begin()
            with engine.begin() as conn:
                conn.execute(query, dados_manual)
            
            # Limpa o cache para forçar a atualização da tabela de visualização
            if "df_transacoes" in st.session_state:
                del st.session_state.df_transacoes
            
            st.success("✅ Transação salva com sucesso!")
            st.rerun()
            
        except Exception as e:
            st.error(f"⚠️ Erro ao acessar o banco de dados: {e}")
# --- 5. VISUALIZAÇÃO DOS ÚLTIMOS LANÇAMENTOS ---
st.write("---")
st.subheader("📋 Seus Últimos Lançamentos Manuais")

try:
    from database import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    
    # Query adaptada para o padrão SQLAlchemy (:u em vez de %s)
    query_recente = text("""
        SELECT data, descricao, valor, categoria, banco 
        FROM transacoes 
        WHERE hash_fatura = 'MANUAL_ENTRY' AND user_id = :u
        ORDER BY id DESC LIMIT 5
    """)
    
    # Com SQLAlchemy, o pandas precisa que a conexão seja aberta explicitamente
    with engine.connect() as conn:
        df_recent = pd.read_sql_query(query_recente, conn, params={"u": usuario_atual})
    
    if not df_recent.empty:
        # Garante que a coluna de data seja tratada corretamente pelo pandas
        df_recent["data"] = pd.to_datetime(df_recent["data"])
        
        st.dataframe(
            df_recent, 
            use_container_width=True, # Atualizado de 'stretch' para o padrão moderno
            hide_index=True,
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "descricao": st.column_config.TextColumn("Descrição"),
                "categoria": st.column_config.TextColumn("Categoria"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                "banco": st.column_config.TextColumn("Banco", disabled=True),
            }
        )
    else:
        st.info("Nenhuma transação manual encontrada para o seu usuário.")

except Exception as e:
    st.warning(f"Não foi possível carregar o histórico recente. Erro: {e}")