import psycopg2
import pandas as pd
import streamlit as st
import yaml
import os
import streamlit_authenticator as stauth
from psycopg2.extras import execute_batch, execute_values
from sqlalchemy import create_engine, text

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

def get_engine():
    """Retorna o engine do SQLAlchemy usando a URL do secrets.toml"""
    db_url = st.secrets["postgres"]["url"]
    return create_engine(db_url)

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

def conectar():
    """Estabelece conexão com o Supabase usando st.secrets."""
    try:
        if "postgres" in st.secrets:
            conn_url = st.secrets["postgres"]["url"]
            return psycopg2.connect(conn_url)
        else:
            st.error("Configuração 'postgres' não encontrada nas Secrets.")
            return None
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None

def criar_tabela():
    """Cria ou atualiza a estrutura das tabelas no Supabase."""
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    name TEXT,
                    password TEXT
                )
            ''')
            cursor.execute('''
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orcamentos (
                    id SERIAL PRIMARY KEY,
                    categoria TEXT,
                    valor NUMERIC,
                    mes INTEGER,
                    ano INTEGER,
                    user_id TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_categorias (
                    categoria TEXT,
                    is_fixo BOOLEAN,
                    user_id TEXT,
                    PRIMARY KEY (categoria, user_id)
                )
            ''')
            conn.commit()
    finally:
        conn.close()

def carregar_usuarios_db():
    """Busca usuários no banco usando o e-mail como chave principal de login."""
    conn = conectar()
    if not conn: return {'usernames': {}}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT email, username, name, password FROM usuarios")
            rows = cursor.fetchall()
            
            credentials = {'usernames': {}}
            for row in rows:
                credentials['usernames'][row[0]] = {
                    'username_original': row[1],
                    'name': row[2],
                    'password': row[3]
                }
            return credentials
    finally:
        conn.close()

def salvar_novo_usuario_db(username, email, name, password_hashed):
    is_valid_hash = (
        isinstance(password_hashed, str) and 
        password_hashed.startswith('$2') and 
        len(password_hashed) >= 50
    )

    if not is_valid_hash:
        st.error("Erro Crítico: Tentativa de salvar senha sem criptografia detectada.")
        return False

    conn = conectar()
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (username, email, name, password) VALUES (%s, %s, %s, %s)",
                (username, email, name, password_hashed)
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False
    finally:
        conn.close()

def check_auth():
    if st.session_state.get("authentication_status"):
        return st.session_state.get("username")

    if "config" in st.session_state:
        config = st.session_state["config"]
        authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            st.secrets["auth"]["cookie_key"],
            config['cookie']['expiry_days']
        )
        authenticator.login(location='main', key='reauth')
        if st.session_state.get("authentication_status"):
            return st.session_state.get("username")
    return None

# --- SEÇÃO DE TRANSAÇÕES ---

def salvar_transacoes(lista_dados, user_id):
    """Insere uma lista de transações em lote (Bulk Insert) no banco."""
    if not lista_dados:
        return 0

    conn = conectar()
    if not conn: return 0
        
    try:
        with conn.cursor() as cursor:
            query = """
                INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id) 
                VALUES %s
            """
            execute_values(cursor, query, lista_dados)
            conn.commit()
            return len(lista_dados)
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro ao salvar transações em lote: {e}")
        return 0
    finally:
        conn.close()

def save_all_changes(df, user_id):
    """Sincroniza edições em massa incluindo descrição e categoria."""
    conn = conectar()
    if not conn: return 0
    try:
        updates = []
        for _, row in df.iterrows():
            # Conversão explícita para evitar erros de tipo do banco
            try:
                idx = int(row['id'])
                val = float(row['valor'])
                cat = str(row['categoria'])
                desc = str(row['descricao'])
                dat = pd.to_datetime(row['data']).strftime('%Y-%m-%d')
                updates.append((cat, val, dat, desc, idx, user_id))
            except Exception as e:
                st.warning(f"Erro na linha {row['id']}: {e}")
                continue

        if updates:
            with conn.cursor() as cursor:
                # Adicionado 'descricao = %s' para persistência total
                query = '''
                    UPDATE transacoes 
                    SET categoria = %s, valor = %s, data = %s, descricao = %s
                    WHERE id = %s AND user_id = %s
                '''
                execute_batch(cursor, query, updates, page_size=100)
            conn.commit()
        return len(updates)
    finally:
        conn.close()

def deletar_transacoes(ids, user_id):
    """Remove transações do banco de dados."""
    conn = conectar()
    if not conn: return 0
    try:
        if ids:
            with conn.cursor() as cursor:
                query = "DELETE FROM transacoes WHERE id = %s AND user_id = %s"
                execute_batch(cursor, query, [(id_val, user_id) for id_val in ids], page_size=100)
            conn.commit()
        return len(ids)
    finally:
        conn.close()

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
    conn = conectar()
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM transacoes WHERE hash_fatura = %s AND user_id = %s", (hash_fatura, user_id))
            return cursor.fetchone() is not None
    finally:
        conn.close()

def deletar_transacao(id_transacao, user_id):
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            # Aqui estava o erro: faltava fechar a aspa e o parêntese
            cursor.execute("DELETE FROM transacoes WHERE id = %s AND user_id = %s", (id_transacao, user_id))
            conn.commit()
    finally:
        conn.close()

def get_gastos_fixos(user_id):
    """Retorna a lista de categorias marcadas como fixas pelo usuário."""
    conn = conectar()
    if not conn: return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT categoria FROM config_categorias WHERE user_id = %s AND is_fixo = TRUE", (user_id,))
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Erro ao buscar gastos fixos: {e}")
        return []
    finally:
        conn.close()

def salvar_config_categoria(categoria, is_fixo, user_id):
    """Salva ou atualiza se uma categoria é um gasto fixo."""
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            query = '''
                INSERT INTO config_categorias (categoria, is_fixo, user_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (categoria, user_id) 
                DO UPDATE SET is_fixo = EXCLUDED.is_fixo
            '''
            cursor.execute(query, (categoria, bool(is_fixo), user_id))
            conn.commit()
    except Exception as e:
        print(f"Erro ao salvar config de categoria: {e}")
    finally:
        conn.close()