import psycopg2
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

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
            # Transações
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
            # Orçamentos
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
            # Categorias Fixas (Configuração)
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

# --- SEÇÃO DE TRANSAÇÕES ---

def salvar_transacoes(df, user_id):
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            for _, row in df.iterrows():
                cursor.execute("SELECT 1 FROM transacoes WHERE hash_fatura = %s AND user_id = %s", 
                               (row['hash_fatura'], user_id))
                if not cursor.fetchone():
                    query = '''
                        INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    '''
                    cursor.execute(query, (row['data'], row['descricao'], row['valor'], 
                                         row['categoria'], row['banco'], row['hash_fatura'], user_id))
            conn.commit()
    finally:
        conn.close()

def save_all_changes(df, user_id):
    """Sincroniza edições em massa do st.data_editor."""
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            for _, row in df.iterrows():
                query = '''
                    UPDATE transacoes 
                    SET categoria = %s, valor = %s, data = %s 
                    WHERE id = %s AND user_id = %s
                '''
                cursor.execute(query, (row['categoria'], row['valor'], row['data'], row['id'], user_id))
            conn.commit()
    finally:
        conn.close()

def carregar_transacoes(user_id, dias=None):
    conn = conectar()
    if not conn: return pd.DataFrame()
    try:
        if dias:
            data_corte = (datetime.now() - timedelta(days=dias)).date()
            query = "SELECT * FROM transacoes WHERE user_id = %s AND data >= %s ORDER BY data DESC"
            params = (user_id, data_corte)
        else:
            query = "SELECT * FROM transacoes WHERE user_id = %s ORDER BY data DESC"
            params = (user_id,)
        
        df = pd.read_sql_query(query, conn, params=params)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
        return df
    finally:
        conn.close()

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
            cursor.execute("DELETE FROM transacoes WHERE id = %s AND user_id = %s", (id_transacao, user_id))
            conn.commit()
    finally:
        conn.close()

# --- SEÇÃO DE CATEGORIAS E CONFIGURAÇÕES ---

def get_categorias_completas(user_id):
    conn = conectar()
    if not conn: return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT categoria FROM transacoes WHERE user_id = %s", (user_id,))
            cats_trans = [row[0] for row in cursor.fetchall() if row[0]]
            cursor.execute("SELECT DISTINCT categoria FROM config_categorias WHERE user_id = %s", (user_id,))
            cats_config = [row[0] for row in cursor.fetchall() if row[0]]
            
            padrao = {"Alimentação", "Transporte", "Lazer", "Moradia", "Saúde", "Supermercado", "Sem categoria"}
            todas = sorted(list(set(cats_trans) | set(cats_config) | padrao))
            return todas
    finally:
        conn.close()

def salvar_config_categoria(categoria, is_fixo, user_id):
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
    finally:
        conn.close()

def get_gastos_fixos(user_id):
    conn = conectar()
    if not conn: return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT categoria FROM config_categorias WHERE user_id = %s AND is_fixo = TRUE", (user_id,))
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

# --- SEÇÃO DE ORÇAMENTO ---

def salvar_orcamento(categoria, valor, mes, ano, user_id):
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id FROM orcamentos 
                WHERE categoria = %s AND mes = %s AND ano = %s AND user_id = %s
            ''', (categoria, mes, ano, user_id))
            
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE orcamentos SET valor = %s WHERE id = %s", (valor, row[0]))
            else:
                cursor.execute('''
                    INSERT INTO orcamentos (categoria, valor, mes, ano, user_id)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (categoria, valor, mes, ano, user_id))
            conn.commit()
    finally:
        conn.close()

def carregar_orcamentos(mes, ano, user_id):
    conn = conectar()
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM orcamentos WHERE user_id = %s AND mes = %s AND ano = %s"
        return pd.read_sql_query(query, conn, params=(user_id, mes, ano))
    finally:
        conn.close()

# --- UTILITÁRIOS ---

def limpar_banco_usuario(user_id):
    conn = conectar()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM transacoes WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM orcamentos WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM config_categorias WHERE user_id = %s", (user_id,))
            conn.commit()
    finally:
        conn.close()