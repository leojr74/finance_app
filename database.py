import pandas as pd
import streamlit as st
from streamlit import cursor
import yaml
import os
import streamlit_authenticator as stauth
from sqlalchemy import create_engine, text
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

@st.cache_resource
def get_engine():
    """Retorna o engine do SQLAlchemy usando a URL do secrets.toml"""
    db_url = st.secrets["postgres"]["url"]
    return create_engine(
        db_url, 
        pool_size=5, 
        max_overflow=10, 
        pool_recycle=3600,
        pool_pre_ping=True
    )

def get_authenticator():
    """Retorna o objeto de autenticação configurado para validar cookies."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(BASE_DIR, 'config.yaml')
    
    with open(config_path) as file:
        config = yaml.load(file, Loader=yaml.SafeLoader)
    
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
    if not engine:
        return
    
    with engine.begin() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                name TEXT,
                password TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id SERIAL PRIMARY KEY,
                data DATE,
                descricao TEXT,
                valor NUMERIC,
                categoria TEXT,
                banco TEXT,
                hash_fatura TEXT,
                user_id TEXT 
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orcamentos (
                id SERIAL PRIMARY KEY,
                categoria TEXT,
                valor NUMERIC,
                mes INTEGER,
                ano INTEGER,
                user_id TEXT
            )
        ''')
        conn.execute(''')
            CREATE TABLE IF NOT EXISTS config_categorias (
                categoria TEXT,
                is_fixo BOOLEAN,
                user_id TEXT,
                PRIMARY KEY (categoria, user_id)
            )
        ''')
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS categorias_regras (
                chave TEXT,
                categoria TEXT,
                user_id TEXT,
                PRIMARY KEY (chave, user_id)
            )
        '''))

# --- GESTÃO DE USUÁRIOS ---

def carregar_usuarios_db():
    """Busca credenciais usando o engine do SQLAlchemy."""
    engine = get_engine()
    query = text("SELECT email, username, name, password FROM usuarios")
    
    credentials = {'usernames': {}}
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
            for _, row in df.iterrows():
                credentials['usernames'][row['email']] = {
                    'username_original': row['username'],
                    'name': row['name'],
                    'password': row['password']
                }
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
    return credentials

def salvar_novo_usuario_db(username, email, name, password_hashed):
    """Salva novo usuário garantindo que a senha esteja em hash."""
    if not (isinstance(password_hashed, str) and password_hashed.startswith('$2')):
        st.error("Erro: Senha não criptografada.")
        return False

    engine = get_engine()
    query = text("""
        INSERT INTO usuarios (username, email, name, password) 
        VALUES (:u, :e, :n, :p)
    """)
    try:
        with engine.begin() as conn:
            conn.execute(query, {"u": username, "e": email, "n": name, "p": password_hashed})
            return True
    except Exception as e:
        st.error(f"Erro ao salvar usuário: {e}")
        return False

# --- SEÇÃO DE TRANSAÇÕES ---

def carregar_transacoes(user_id, dias=None):
    """Carrega transações filtradas por usuário e período."""
    engine = get_engine()
    query_str = "SELECT * FROM transacoes WHERE user_id = :u"
    params = {"u": user_id}

    if dias is not None:
        query_str += " AND data >= CURRENT_DATE - (:d || ' days')::interval"
        params["d"] = str(dias)

    query_str += " ORDER BY data DESC, id DESC"
    
    try:
        with engine.connect() as conn:
            return pd.read_sql_query(text(query_str), conn, params=params)
    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return pd.DataFrame()
    
def salvar_transacoes(lista_dados, user_id):
    """
    Substitui o antigo execute_values. 
    Recebe lista de tuplas e converte para dicionários para o SQLAlchemy.
    """
    if not lista_dados: return 0
    
    engine = get_engine()
    # Mapeia as tuplas para o formato que o SQLAlchemy espera (dicionários)
    dados_dict = [
        {
            "d": d, "desc": desc, "v": valor, "c": cat, 
            "b": banco, "h": h_fat, "u": user_id
        } 
        for d, desc, valor, cat, banco, h_fat, _ in lista_dados
    ]
    
    query = text("""
        INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id) 
        VALUES (:d, :desc, :v, :c, :b, :h, :u)
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, dados_dict)
            return len(lista_dados)
    except Exception as e:
        st.error(f"Erro no salvamento em lote: {e}")
        return 0

def save_all_changes(df, user_id):
    """Sincroniza edições em massa usando o engine."""
    engine = get_engine()
    updates = []
    for _, row in df.iterrows():
        updates.append({
            "cat": str(row['categoria']),
            "val": float(row['valor']),
            "dat": pd.to_datetime(row['data']).date(),
            "desc": str(row['descricao']),
            "idx": int(row['id']),
            "u": user_id
        })

    query = text("""
        UPDATE transacoes 
        SET categoria = :cat, valor = :val, data = :dat, descricao = :desc
        WHERE id = :idx AND user_id = :u
    """)
    
    try:
        with engine.begin() as conn:
            conn.execute(query, updates)
            return len(updates)
    except Exception as e:
        st.error(f"Erro ao atualizar transações: {e}")
        return 0

def deletar_transacoes(ids, user_id):
    """Remove múltiplas transações."""
    if not ids: return 0
    engine = get_engine()
    query = text("DELETE FROM transacoes WHERE id = :idx AND user_id = :u")
    params = [{"idx": i, "u": user_id} for i in ids]
    
    try:
        with engine.begin() as conn:
            conn.execute(query, params)
            return len(ids)
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return 0

def verificar_duplicata(hash_fatura, user_id):
    """Verifica se um hash já existe."""
    engine = get_engine()
    query = text("SELECT 1 FROM transacoes WHERE hash_fatura = :h AND user_id = :u LIMIT 1")
    with engine.connect() as conn:
        return conn.execute(query, {"h": hash_fatura, "u": user_id}).fetchone() is not None

# --- SEÇÃO DE CONFIGURAÇÕES ---

def get_gastos_fixos(user_id):
    """Retorna a lista de categorias marcadas como fixas pelo usuário usando SQLAlchemy."""
    engine = get_engine()
    query = text("SELECT categoria FROM config_categorias WHERE user_id = :u AND is_fixo = TRUE")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"u": user_id}).fetchall()
            return [row[0] for row in result]
    except Exception as e:
        st.error(f"Erro ao buscar gastos fixos: {e}")
        return []

def salvar_config_categoria(categoria, is_fixo, user_id):
    """Salva se a categoria é fixa (Upsert)."""
    engine = get_engine()
    query = text("""
        INSERT INTO config_categorias (categoria, is_fixo, user_id)
        VALUES (:c, :f, :u)
        ON CONFLICT (categoria, user_id) DO UPDATE SET is_fixo = EXCLUDED.is_fixo
    """)
    with engine.begin() as conn:
        conn.execute(query, {"c": categoria, "f": bool(is_fixo), "u": user_id})

# --- SEÇÃO DE ORÇAMENTO ---

def salvar_orcamento(categoria, valor, mes, ano, user_id):
    """Upsert de orçamento usando o engine."""
    engine = get_engine()
    with engine.begin() as conn:
        query_check = text("""
            SELECT id FROM orcamentos 
            WHERE categoria = :c AND mes = :m AND ano = :a AND user_id = :u
        """)
        res = conn.execute(query_check, {"c": categoria, "m": mes, "a": ano, "u": user_id}).fetchone()
        
        if res:
            conn.execute(text("UPDATE orcamentos SET valor = :v WHERE id = :id"), {"v": valor, "id": res[0]})
        else:
            conn.execute(text("""
                INSERT INTO orcamentos (categoria, valor, mes, ano, user_id)
                VALUES (:c, :v, :m, :a, :u)
            """), {"c": categoria, "v": valor, "m": mes, "a": ano, "u": user_id})

def carregar_orcamentos(mes, ano, user_id):
    engine = get_engine()
    query = text("SELECT * FROM orcamentos WHERE user_id = :u AND mes = :m AND ano = :a")
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"u": user_id, "m": mes, "a": ano})

# --- UTILITÁRIOS ---

def limpar_banco_usuario(user_id):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM transacoes WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM orcamentos WHERE user_id = :u"), {"u": user_id})
        conn.execute(text("DELETE FROM config_categorias WHERE user_id = :u"), {"u": user_id})

def carregar_regras_db(user_id):
    """Lê as regras de categorização do banco para o usuário atual"""
    engine = get_engine()
    query = text("SELECT chave, categoria FROM categorias_regras WHERE user_id = :u")
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"u": user_id}).fetchall()
            return {row[0]: row[1] for row in result}
    except Exception as e:
        # Se a tabela não existir ainda ou der erro, retorna dicionário vazio 
        # para não quebrar a lógica de categorização do resto do app
        return {}

def salvar_regra_db(chave, categoria, user_id):
    """Salva ou atualiza uma regra no banco"""
    engine = get_engine()
    with engine.begin() as conn:
        # Tenta dar update, se não existir, insert (Upsert)
        conn.execute(text("""
            INSERT INTO categorias_regras (chave, categoria, user_id)
            VALUES (:c, :cat, :u)
            ON CONFLICT (chave, user_id) DO UPDATE SET categoria = EXCLUDED.categoria
        """), {"c": chave, "cat": categoria, "u": user_id})
        