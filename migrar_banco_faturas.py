
import sqlite3

DB_PATH = "transacoes.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("ALTER TABLE transacoes RENAME TO transacoes_old")

cur.execute("""
CREATE TABLE faturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    banco TEXT,
    mes INTEGER,
    ano INTEGER,
    hash TEXT UNIQUE
)
""")

cur.execute("""
CREATE TABLE transacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fatura_id INTEGER,
    data TEXT,
    descricao TEXT,
    valor REAL,
    categoria TEXT,
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("Migração concluída. Agora reimporte suas faturas.")
