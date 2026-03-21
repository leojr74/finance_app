import streamlit as st
import psycopg2
import os
import hashlib
import pandas as pd
from datetime import datetime, timedelta

import psycopg2
import streamlit as st

def conectar():
    try:
        # Puxa a URL que você configurou nos Secrets
        conn_url = st.secrets["DATABASE_URL"]
        
        # Conectamos com um tempo de limite para não travar o app se o banco demorar
        return psycopg2.connect(conn_url, connect_timeout=10)
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None

def criar_tabela():
    conn = conectar()
    if conn is None:
        return

    try:
        with conn.cursor() as cursor:
            # TABELA TRANSACOES: Trocamos INTEGER PRIMARY KEY AUTOINCREMENT por SERIAL PRIMARY KEY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transacoes (
                    id SERIAL PRIMARY KEY,
                    data DATE, 
                    descricao TEXT, 
                    valor DECIMAL,
                    categoria TEXT, 
                    banco TEXT, 
                    hash_fatura TEXT
                )
            ''')
            
            # TABELA ORCAMENTOS: Trocamos REAL por DECIMAL e AUTOINCREMENT por SERIAL
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orcamentos (
                    id SERIAL PRIMARY KEY,
                    categoria TEXT, 
                    valor DECIMAL, 
                    mes INTEGER, 
                    ano INTEGER,
                    UNIQUE(categoria, mes, ano)
                )
            ''')
            
            # TABELA CONFIGURACOES
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_categorias (
                    categoria TEXT PRIMARY KEY,
                    is_fixo INTEGER DEFAULT 0
                )
            ''')
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao criar tabelas no Supabase: {e}")
    finally:
        conn.close()

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
    conn = conectar()
    if not conn: return pd.DataFrame()
    
    try:
        if dias:
            data_corte = (datetime.now() - timedelta(days=dias)).date()
            # No Postgres, usamos %s para passar parâmetros, mesmo no read_sql
            query = "SELECT * FROM transacoes WHERE data >= %s ORDER BY data DESC"
            return pd.read_sql_query(query, conn, params=(data_corte,))
        else:
            query = "SELECT * FROM transacoes ORDER BY data DESC"
            return pd.read_sql_query(query, conn)
    finally:
        conn.close()

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
    """Sincroniza o banco de dados com o estado atual do editor (Update e Delete)."""
    with conectar() as conn:
        if conn is None:
            return
            
        try:
            cursor = conn.cursor()
            
            # 1. Obter a lista de IDs que ainda existem no seu DataFrame
            ids_presentes = df['id'].tolist()
            
            # 2. DELETAR o que não está mais no DataFrame
            # Se a lista não estiver vazia, deletamos quem sumiu. 
            # Se estiver vazia, significa que você apagou tudo no editor.
            if ids_presentes:
                # O formato %s com uma tupla é a forma correta do psycopg2 para o "IN"
                cursor.execute("DELETE FROM transacoes WHERE id NOT IN %s", (tuple(ids_presentes),))
            else:
                cursor.execute("DELETE FROM transacoes")

            # 3. ATUALIZAR as categorias de quem sobrou
            for _, row in df.iterrows():
                cursor.execute('''
                    UPDATE transacoes 
                    SET categoria = %s 
                    WHERE id = %s
                ''', (row['categoria'], row['id']))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Erro ao salvar alterações no banco: {e}")