import pandas as pd
import sqlite3

DB_PATH = "transacoes.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def delete_transactions(ids):

    if not ids:
        return

    conn = get_connection()

    placeholders = ",".join(["?"] * len(ids))

    query = f"""
    DELETE FROM transacoes
    WHERE id IN ({placeholders})
    """

    conn.execute(query, ids)

    conn.commit()
    conn.close()


def save_all_changes(df):

    conn = get_connection()
    cursor = conn.cursor()

    # pegar ids atuais no banco
    db_ids = pd.read_sql("SELECT id FROM transacoes", conn)["id"].tolist()

    # ids atuais no dataframe
    df_ids = df["id"].dropna().astype(int).tolist()

    # detectar deletados
    deleted_ids = list(set(db_ids) - set(df_ids))

    if deleted_ids:

        placeholders = ",".join(["?"] * len(deleted_ids))

        cursor.execute(
            f"""
            DELETE FROM transacoes
            WHERE id IN ({placeholders})
            """,
            deleted_ids
        )

    # atualizar registros existentes
    for _, row in df.iterrows():

        if pd.isna(row["id"]):
            continue

        cursor.execute(
            """
            UPDATE transacoes
            SET
                data=?,
                descricao=?,
                valor=?,
                categoria=?,
                banco=?
            WHERE id=?
            """,
            (
                row["data"],
                row["descricao"],
                float(row["valor"]),
                row["categoria"],
                row["banco"],
                int(row["id"]),
            )
        )

    conn.commit()
    conn.close()