import pandas as pd
import bcrypt
import streamlit as st
from sqlalchemy import create_engine, text
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module='pandas')


# =========================
# CONEXÃO
# =========================
@st.cache_resource
def get_engine():
    if "postgres" not in st.secrets:
        st.error("Configuração 'postgres' não encontrada nas Secrets.")
        st.stop()

    db_url = st.secrets["postgres"]["url"]
    return create_engine(db_url, pool_pre_ping=True)


# =========================
# USUÁRIOS / AUTH
# =========================
def criar_tabela():
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


def salvar_novo_usuario_db(username, email, name, senha_plana):
    engine = get_engine()

    # 🔐 gera hash seguro
    senha_hash = bcrypt.hashpw(senha_plana.encode(), bcrypt.gensalt()).decode()

    query = text("""
        INSERT INTO usuarios (username, email, name, password)
        VALUES (:u, :e, :n, :p)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "u": username,
                "e": email,
                "n": name,
                "p": senha_hash
            })
        return True

    except Exception as e:
        import traceback
        st.error("Erro ao salvar usuário:")
        st.code(traceback.format_exc())
        return False


def verificar_login(email, senha_digitada):
    engine = get_engine()

    query = text("""
        SELECT email, name, password
        FROM usuarios
        WHERE email = :e
    """)

    with engine.connect() as conn:
        user = conn.execute(query, {"e": email}).fetchone()

    if not user:
        return None

    senha_hash = user.password

    if bcrypt.checkpw(senha_digitada.encode(), senha_hash.encode()):
        return {
            "email": user.email,
            "name": user.name
        }

    return None


# =========================
# TRANSAÇÕES
# =========================
def salvar_transacoes(lista_dados, user_id):
    if not lista_dados:
        return 0

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


def carregar_transacoes(user_id, dias=None):
    engine = get_engine()

    query = """
        SELECT id, data, descricao, valor, categoria, banco, hash_fatura, user_id
        FROM transacoes
        WHERE user_id = :u_id
    """

    params = {"u_id": user_id}

    if dias is not None:
        query += " AND data >= CURRENT_DATE - CAST(:intervalo AS INTERVAL)"
        params["intervalo"] = f"{dias} days"

    query += " ORDER BY data DESC, id DESC"

    try:
        return pd.read_sql_query(text(query), engine, params=params)

    except Exception as e:
        st.error(f"Erro ao carregar transações: {e}")
        return pd.DataFrame()


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

def save_all_changes(df_novo, user_id):
    """Atualiza apenas o que mudou comparando com o banco."""

    import pandas as pd
    from sqlalchemy import text

    engine = get_engine()

    # 🔥 busca estado atual no banco
    query_load = text("""
        SELECT id, data, descricao, valor, categoria
        FROM transacoes
        WHERE user_id = :u
    """)

    df_original = pd.read_sql_query(query_load, engine, params={"u": user_id})
    df_original = df_original.set_index("id")

    df_novo = df_novo.set_index("id")

    updates = []

    for idx in df_novo.index:
        if idx not in df_original.index:
            continue

        row_new = df_novo.loc[idx]
        row_old = df_original.loc[idx]

        if (
            str(row_new["categoria"]) != str(row_old["categoria"]) or
            float(row_new["valor"]) != float(row_old["valor"]) or
            pd.to_datetime(row_new["data"]) != pd.to_datetime(row_old["data"]) or
            str(row_new["descricao"]) != str(row_old["descricao"])
        ):
            updates.append({
                "cat": str(row_new["categoria"]),
                "val": float(row_new["valor"]),
                "dat": pd.to_datetime(row_new["data"]).date(),
                "desc": str(row_new["descricao"]),
                "id": int(idx),
                "u": user_id
            })

    if not updates:
        return 0

    query = text("""
        UPDATE transacoes 
        SET categoria = :cat, valor = :val, data = :dat, descricao = :desc
        WHERE id = :id AND user_id = :u
    """)

    with engine.begin() as conn:
        conn.execute(query, updates)

    return len(updates)

# =========================
# CONFIG / REGRAS
# =========================
def get_gastos_fixos(user_id):
    engine = get_engine()

    query = text("""
        SELECT categoria
        FROM config_categorias
        WHERE user_id = :u AND is_fixo = TRUE
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"u": user_id})
        return [row[0] for row in result]


def salvar_config_categoria(categoria, is_fixo, user_id):
    engine = get_engine()

    query = text('''
        INSERT INTO config_categorias (categoria, is_fixo, user_id)
        VALUES (:c, :f, :u)
        ON CONFLICT (categoria, user_id)
        DO UPDATE SET is_fixo = EXCLUDED.is_fixo
    ''')

    with engine.begin() as conn:
        conn.execute(query, {"c": categoria, "f": bool(is_fixo), "u": user_id})


def carregar_regras_db(user_id):
    engine = get_engine()

    query = text("""
        SELECT chave, categoria
        FROM categorias_regras
        WHERE user_id = :u
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"u": user_id}).fetchall()
            return {row[0]: row[1] for row in result}

    except Exception:
        return {}


def salvar_regra_db(chave, categoria, user_id):
    if not chave or not categoria or categoria == "Sem categoria":
        return

    engine = get_engine()

    query = text("""
        INSERT INTO categorias_regras (chave, categoria, user_id)
        VALUES (:ch, :ca, :u)
        ON CONFLICT (chave, user_id)
        DO UPDATE SET categoria = EXCLUDED.categoria
    """)

    with engine.begin() as conn:
        conn.execute(query, {
            "ch": chave.strip().upper(),
            "ca": categoria,
            "u": user_id
        })

# =========================
# ORÇAMENTO
# =========================

def salvar_orcamento(categoria, valor, mes, ano, user_id):
    engine = get_engine()

    with engine.begin() as conn:
        # verifica se já existe
        query_check = text("""
            SELECT id FROM orcamentos
            WHERE categoria = :c AND mes = :m AND ano = :a AND user_id = :u
        """)

        result = conn.execute(query_check, {
            "c": categoria,
            "m": mes,
            "a": ano,
            "u": user_id
        }).fetchone()

        if result:
            # update
            query_update = text("""
                UPDATE orcamentos
                SET valor = :v
                WHERE id = :id
            """)

            conn.execute(query_update, {
                "v": valor,
                "id": result[0]
            })

        else:
            # insert
            query_insert = text("""
                INSERT INTO orcamentos (categoria, valor, mes, ano, user_id)
                VALUES (:c, :v, :m, :a, :u)
            """)

            conn.execute(query_insert, {
                "c": categoria,
                "v": valor,
                "m": mes,
                "a": ano,
                "u": user_id
            })

def carregar_orcamentos(mes, ano, user_id):
    engine = get_engine()

    query = text("""
        SELECT *
        FROM orcamentos
        WHERE user_id = :u AND mes = :m AND ano = :a
    """)

    try:
        return pd.read_sql_query(query, engine, params={
            "u": user_id,
            "m": mes,
            "a": ano
        })
    except Exception as e:
        st.error(f"Erro ao carregar orçamentos: {e}")
        return pd.DataFrame()