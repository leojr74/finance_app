
import sqlite3
import hashlib
import pandas as pd

DB_PATH = "transacoes.db"


def conectar():
    return sqlite3.connect(DB_PATH)


def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            descricao TEXT,
            valor REAL,
            categoria TEXT,
            banco TEXT,
            hash_fatura TEXT
        )
        '''
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_data ON transacoes(data)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_banco ON transacoes(data, banco)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_categoria ON transacoes(categoria)")

    conn.commit()
    conn.close()


def gerar_hash_fatura(banco, mes, ano):
    texto = f"{banco}_{mes}_{ano}"
    return hashlib.sha256(texto.encode()).hexdigest()


def salvar_transacoes(df, banco, mes_fatura, ano_fatura):

    if df is None or len(df) == 0:
        return False, 0

    criar_tabela()

    conn = conectar()
    cursor = conn.cursor()

    hash_fatura = gerar_hash_fatura(banco, mes_fatura, ano_fatura)

    cursor.execute(
        "SELECT COUNT(*) FROM transacoes WHERE hash_fatura=?",
        (hash_fatura,)
    )

    if cursor.fetchone()[0] > 0:
        conn.close()
        return "duplicada", 0

    inseridas = 0

    try:

        for _, row in df.iterrows():

            data = row.get("data")
            descricao = row.get("descricao")
            valor = row.get("valor")
            categoria = row.get("categoria")

            if data is None or descricao is None or valor is None:
                continue

            try:
                valor = float(valor)
            except:
                continue

            cursor.execute(
                '''
                INSERT INTO transacoes
                (data, descricao, valor, categoria, banco, hash_fatura)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    data,
                    descricao,
                    valor,
                    categoria,
                    banco,
                    hash_fatura
                )
            )

            inseridas += 1

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        conn.close()

    return True, inseridas


def deletar_fatura(hash_fatura):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM transacoes WHERE hash_fatura=?",
        (hash_fatura,)
    )

    qtd = cursor.fetchone()[0]

    cursor.execute(
        "DELETE FROM transacoes WHERE hash_fatura=?",
        (hash_fatura,)
    )

    conn.commit()
    conn.close()

    return qtd


def carregar_transacoes():
    conn = conectar()

    try:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                data,
                descricao,
                valor,
                categoria,
                banco
            FROM transacoes
            ORDER BY data
            """,
            conn
        )
    finally:
        conn.close()

    return df


# -------- NOVA FUNÇÃO --------
def atualizar_categorias(df):

    if df is None or len(df) == 0:
        return 0

    conn = conectar()
    cursor = conn.cursor()

    atualizadas = 0

    for _, row in df.iterrows():

        data = row.get("data")
        descricao = row.get("descricao")
        valor = row.get("valor")
        categoria = row.get("categoria")

        if data is None or descricao is None or valor is None:
            continue

        try:
            valor = float(valor)
        except:
            continue

        cursor.execute(
            """
            UPDATE transacoes
            SET categoria = ?
            WHERE data = ? AND descricao = ? AND valor = ?
            """,
            (
                categoria,
                data,
                descricao,
                valor
            )
        )

        atualizadas += cursor.rowcount

    conn.commit()
    conn.close()

    return atualizadas

# -------- ORÇAMENTOS --------

def criar_tabela_orcamentos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT,
            valor REAL,
            mes INTEGER,
            ano INTEGER
        )
    """)

    conn.commit()
    conn.close()


def salvar_orcamento(categoria, valor, mes, ano):
    conn = conectar()
    cursor = conn.cursor()

    # remove antigo (evita duplicidade)
    cursor.execute("""
        DELETE FROM orcamentos
        WHERE categoria = ? AND mes = ? AND ano = ?
    """, (categoria, mes, ano))

    cursor.execute("""
        INSERT INTO orcamentos (categoria, valor, mes, ano)
        VALUES (?, ?, ?, ?)
    """, (categoria, valor, mes, ano))

    conn.commit()
    conn.close()


def carregar_orcamentos(mes, ano):
    conn = conectar()

    try:
        df = pd.read_sql_query("""
            SELECT categoria, valor
            FROM orcamentos
            WHERE mes = ? AND ano = ?
        """, conn, params=(mes, ano))
    except:
        # se tabela não existir ainda
        df = pd.DataFrame(columns=["categoria", "valor"])

    finally:
        conn.close()

    return df