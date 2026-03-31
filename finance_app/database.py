import pandas as pd
import streamlit as st
import yaml
import os
import streamlit_authenticator as stauth
from sqlalchemy import create_engine, text
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

def get_engine():
    """Retorna o engine do SQLAlchemy com pool de conexões configurado."""
    if "postgres" not in st.secrets:
        st.error("Configuração 'postgres' não encontrada nas Secrets.")
        st.stop()
    db_url = st.secrets["postgres"]["url"]
    # pool_pre_ping=True ajuda a evitar erros de conexão ociosa (comum no Streamlit/Supabase)
    return create_engine(db_url, pool_pre_ping=True)

def get_authenticator():
    """Retorna o objeto de autenticação configurado para validar cookies."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(BASE_DIR, 'config.yaml')
    
    with open(config_path) as file:
        config = yaml.load(file, Loader=yaml.SafeLoader)
    
    from database import carregar_usuarios_db
    config['credentials'] = carregar_usuarios_db()
    
    return stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        st.secrets["auth"]["cookie_key"],
        config['cookie']['expiry_days']
    )

def criar_tabela():
    """Cria ou atualiza a estrutura das tabelas no Supabase."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                name TEXT,
                password TEXT
            );
            CREATE TABLE IF NOT EXISTS transacoes (
                id SERIAL PRIMARY KEY,
                data DATE,
                descricao TEXT,
                valor NUMERIC,
                categoria TEXT,
                banco TEXT,
                hash_fatura TEXT,
                user_id TEXT 
            );
            CREATE TABLE IF NOT EXISTS orcamentos (
                id SERIAL PRIMARY KEY,
                categoria TEXT,
                valor NUMERIC,
                mes INTEGER,
                ano INTEGER,
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS config_categorias (
                categoria TEXT,
                is_fixo BOOLEAN,
                user_id TEXT,
                PRIMARY KEY (categoria, user_id)
            );
            CREATE TABLE IF NOT EXISTS categorias_regras (
                chave TEXT,
                categoria TEXT,
                user_id TEXT,
                PRIMARY KEY (chave, user_id)
            );
        '''))

def carregar_usuarios_db():
    """Busca usuários no banco usando SQLAlchemy."""
    engine = get_engine()
    credentials = {'usernames': {}}
    query = text("SELECT email, username, name, password FROM usuarios")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            credentials['usernames'][row.email] = {
                'username_original': row.username,
                'name': row.name,
                'password': row.password
            }
    return credentials

def salvar_novo_usuario_db(username, email, name, password_hashed):
    engine = get_engine()
    query = text("INSERT INTO usuarios (username, email, name, password) VALUES (:u, :e, :n, :p)")
    try:
        with engine.begin() as conn:
            conn.execute(query, {"u": username, "e": email, "n": name, "p": password_hashed})
            return True
    except Exception as e:
        st.error(f"Erro ao salvar usuário: {e}")
        return False

# --- SEÇÃO DE TRANSAÇÕES ---

def salvar_transacoes(lista_dados, user_id):
    """Bulk Insert usando SQLAlchemy (lista_dados deve ser lista de dicionários)."""
    if not lista_dados: return 0
    
    # Converter tuplas para dicionários para o SQLAlchemy mapear as colunas
    colunas = ["data", "descricao", "valor", "categoria", "banco", "hash_fatura", "user_id"]
    dicts = [dict(zip(colunas, list(d) + [user_id])) for d in lista_dados]
    
    engine = get_engine()
    query = text("""
        INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id) 
        VALUES (:data, :descricao, :valor, :categoria, :banco, :hash_fatura, :user_id)
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, dicts)
            return len(lista_dados)
    except Exception as e:
        st.error(f"Erro no bulk insert: {e}")
        return 0

def save_all_changes(df, user_id):
    """Sincroniza edições do DataFrame usando o engine."""
    engine = get_engine()
    query = text("""
        UPDATE transacoes 
        SET categoria = :cat, valor = :val, data = :dat, descricao = :desc
        WHERE id = :id AND user_id = :u
    """)
    
    updates = []
    for _, row in df.iterrows():
        updates.append({
            "cat": str(row['categoria']),
            "val": float(row['valor']),
            "dat": pd.to_datetime(row['data']).date(),
            "desc": str(row['descricao']),
            "id": int(row['id']),
            "u": user_id
        })

    try:
        with engine.begin() as conn:
            conn.execute(query, updates)
        return len(updates)
    except Exception as e:
        st.error(f"Erro ao atualizar transações: {e}")
        return 0

def deletar_transacoes(ids, user_id):
    engine = get_engine()
    query = text("DELETE FROM transacoes WHERE id = :id AND user_id = :u")
    try:
        with engine.begin() as conn:
            conn.execute(query, [{"id": i, "u": user_id} for i in ids])
        return len(ids)
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return 0

def carregar_transacoes(user_id, dias=None): 
    engine = get_engine() 
    query_str = """
        SELECT id, data, descricao, valor, categoria, banco, hash_fatura, user_id 
        FROM transacoes 
        WHERE user_id = :u_id
    """
    params = {"u_id": user_id}

    try:
        if dias is not None:
            query_str += " AND data >= CURRENT_DATE - CAST(:intervalo AS INTERVAL)"
            params["intervalo"] = f"{dias} days"
            
        query_str += " ORDER BY data DESC, id DESC"
        
        df = pd.read_sql_query(text(query_str), engine, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return pd.DataFrame()

def verificar_duplicata(hash_fatura, user_id):
    engine = get_engine()
    query = text("SELECT 1 FROM transacoes WHERE hash_fatura = :h AND user_id = :u LIMIT 1")
    with engine.connect() as conn:
        return conn.execute(query, {"h": hash_fatura, "u": user_id}).fetchone() is not None
    
def deletar_transacao(id_transacao, user_id):
    """Remove uma única transação do banco de dados usando SQLAlchemy."""
    engine = get_engine()
    # Usamos :id e :u para parâmetros nomeados (mais seguro e legível)
    query = text("DELETE FROM transacoes WHERE id = :id AND user_id = :u")
    
    try:
        # O 'with engine.begin()' abre a conexão, inicia a transação,
        # faz o commit ao final ou rollback se der erro, e fecha tudo sozinho.
        with engine.begin() as conn:
            conn.execute(query, {"id": id_transacao, "u": user_id})
    except Exception as e:
        st.error(f"Erro ao deletar transação {id_transacao}: {e}")

def get_gastos_fixos(user_id):
    engine = get_engine()
    query = text("SELECT categoria FROM config_categorias WHERE user_id = :u AND is_fixo = TRUE")
    with engine.connect() as conn:
        result = conn.execute(query, {"u": user_id})
        return [row[0] for row in result]

def salvar_config_categoria(categoria, is_fixo, user_id):
    engine = get_engine()
    query = text('''
        INSERT INTO config_categorias (categoria, is_fixo, user_id)
        VALUES (:c, :f, :u)
        ON CONFLICT (categoria, user_id) DO UPDATE SET is_fixo = EXCLUDED.is_fixo
    ''')
    with engine.begin() as conn:
        conn.execute(query, {"c": categoria, "f": bool(is_fixo), "u": user_id})

# --- SEÇÃO DE ORÇAMENTO (RESTAURADA) ---

def salvar_orcamento(categoria, valor, mes, ano, user_id):
    engine = get_engine()
    with engine.begin() as conn:
        # 1. Busca se já existe o registro
        # Corrigido: text() recebe apenas a string, os parâmetros vão no execute()
        query_check = text('''
            SELECT id FROM orcamentos 
            WHERE categoria = :c AND mes = :m AND ano = :a AND user_id = :u
        ''')
        
        result = conn.execute(query_check, {
            "c": categoria, 
            "m": mes, 
            "a": ano, 
            "u": user_id
        }).fetchone()
        
        if result:
            # 2. Update
            query_update = text("UPDATE orcamentos SET valor = :v WHERE id = :id")
            conn.execute(query_update, {"v": valor, "id": result[0]})
        else:
            # 3. Insert
            query_insert = text('''
                INSERT INTO orcamentos (categoria, valor, mes, ano, user_id)
                VALUES (:c, :v, :m, :a, :u)
            ''')
            conn.execute(query_insert, {
                "c": categoria, 
                "v": valor, 
                "m": mes, 
                "a": ano, 
                "u": user_id
            })

def carregar_orcamentos(mes, ano, user_id):
    engine = get_engine()
    query = "SELECT * FROM orcamentos WHERE user_id = :u AND mes = :m AND ano = :a"
    return pd.read_sql_query(text(query), engine, params={"u": user_id, "m": mes, "a": ano})

# --- UTILITÁRIOS ---

def limpar_banco_usuario(user_id):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM transacoes WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM orcamentos WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM config_categorias WHERE user_id = :u"), {"u": user_id})

# --- REGRA DE CATEGORIZAÇÃO ---

def carregar_regras_db(user_id):
    """Busca todas as regras de categorização de um usuário específico."""
    engine = get_engine()
    query = text("SELECT chave, categoria FROM categorias_regras WHERE user_id = :u")
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"u": user_id}).fetchall()
            # Transforma a lista de tuplas em um dicionário { 'chave': 'categoria' }
            return {row[0]: row[1] for row in result}
    except Exception as e:
        print(f"Erro ao carregar regras: {e}")
        return {}
    
def salvar_regra_db(chave, categoria, user_id):
    """Salva ou atualiza uma regra de categorização individualizada."""
    if not chave or not categoria or categoria == "Sem categoria":
        return

    engine = get_engine()
    # O segredo aqui é o 'ON CONFLICT': se a chave já existir para aquele user_id, ele apenas atualiza a categoria
    query = text("""
        INSERT INTO categorias_regras (chave, categoria, user_id)
        VALUES (:ch, :ca, :u)
        ON CONFLICT (chave, user_id) 
        DO UPDATE SET categoria = EXCLUDED.categoria
    """)
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "ch": chave.strip().upper(), 
                "ca": categoria, 
                "u": user_id
            })
    except Exception as e:
        print(f"Erro ao salvar regra: {e}")
