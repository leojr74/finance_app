import streamlit as st
import psycopg2
import os
import hashlib
import pandas as pd
from datetime import datetime, timedelta

def conectar():
    try:
        # Puxa a URL dos Secrets
        conn_url = st.secrets["DATABASE_URL"]
        
        # Criamos a conexão
        conn = psycopg2.connect(conn_url)
        
        # IMPORTANTE: No PostgreSQL, precisamos configurar o autocommit 
        # para comandos de criação de tabela (como o seu criar_tabela())
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")
        return None

def criar_tabela():
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT, descricao TEXT, valor REAL,
                categoria TEXT, banco TEXT, hash_fatura TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orcamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT, valor REAL, mes INTEGER, ano INTEGER,
                UNIQUE(categoria, mes, ano)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_categorias (
                categoria TEXT PRIMARY KEY,
                is_fixo INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

# --- COMPATIBILIDADE ---
def criar_tabela_orcamentos():
    criar_tabela()

def gerar_hash_fatura(banco, mes, ano):
    texto = f"{banco}_{mes}_{ano}"
    return hashlib.sha256(texto.encode()).hexdigest()

# --- GESTÃO DINÂMICA DE CATEGORIAS ---
def get_categorias_completas():
    """Retorna categorias padrão + categorias encontradas no banco de dados."""
    padrao = ["Alimentação", "Assinaturas", "Lazer", "Moradia", "Saúde", "Supermercado", "Transporte", "Viagem", "Outros", "Sem categoria"]
    try:
        with conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT categoria FROM transacoes WHERE categoria IS NOT NULL")
            do_banco = [row[0] for row in cursor.fetchall()]
        todas = list(set(padrao + do_banco))
        return sorted([c for c in todas if c and c != "None"])
    except:
        return sorted(padrao)

def salvar_config_categoria(categoria, is_fixo):
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO config_categorias (categoria, is_fixo)
            VALUES (%s, %s)
            ON CONFLICT(categoria) DO UPDATE SET is_fixo = excluded.is_fixo
        ''', (categoria, 1 if is_fixo else 0))
        conn.commit()

def get_gastos_fixos():
    with conectar() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT categoria FROM config_categorias WHERE is_fixo = 1")
            return [row[0] for row in cursor.fetchall()]
        except:
            return []

# --- CARREGAMENTO ---
def carregar_transacoes(dias=None):
    with conectar() as conn:
        try:
            if dias:
                # Calcula a data de corte (hoje - X dias)
                data_corte = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
                query = f"SELECT * FROM transacoes WHERE data >= '{data_corte}' ORDER BY data DESC"
            else:
                query = "SELECT * FROM transacoes ORDER BY data DESC"
            
            return pd.read_sql_query(query, conn)
        except:
            return pd.DataFrame()

def salvar_orcamento(categoria, valor, mes, ano):
    with conectar() as conn:
        cursor = conn.cursor()
        
        # Garante que a regra de unicidade existe (previne o erro OperationalError)
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_orcamento_unico 
            ON orcamentos(categoria, mes, ano)
        ''')
        
        # Agora o ON CONFLICT vai encontrar o alvo correto
        cursor.execute('''
            INSERT INTO orcamentos (categoria, valor, mes, ano)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(categoria, mes, ano) DO UPDATE SET valor = excluded.valor
        ''', (categoria, valor, mes, ano))
        conn.commit()

def carregar_orcamentos(mes, ano):
    with conectar() as conn:
        return pd.read_sql_query("SELECT categoria, valor FROM orcamentos WHERE mes = %s AND ano = %s", 
                                 conn, params=(mes, ano))
    
def save_all_changes(df):
    """Atualiza as categorias das transações no banco de dados."""
    with conectar() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute('''
                UPDATE transacoes 
                SET categoria = %s 
                WHERE id = %s
            ''', (row['categoria'], row['id']))
        conn.commit()