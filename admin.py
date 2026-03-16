import sqlite3
import pandas as pd
from database import DB_PATH

def get_connection():
    """Obter conexão com banco de dados"""
    return sqlite3.connect(DB_PATH)

def encontrar_duplicatas():
    """
    Encontrar faturas que foram importadas mais de uma vez
    (mesmos transações aparecendo múltiplas vezes)
    """
    conn = get_connection()
    
    query = """
    SELECT hash_fatura, banco, COUNT(*) as transacoes, 
           GROUP_CONCAT(DISTINCT data) as datas,
           SUM(valor) as total
    FROM transacoes
    GROUP BY hash_fatura
    ORDER BY transacoes DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df

def obter_transacoes_por_hash(hash_fatura):
    """Obter todas as transações de um hash_fatura específico"""
    conn = get_connection()
    query = "SELECT * FROM transacoes WHERE hash_fatura = ? ORDER BY data DESC"
    df = pd.read_sql_query(query, conn, params=(hash_fatura,))
    conn.close()
    return df

def deletar_faturas_duplicadas(hash_fatura):
    """
    Deletar TODAS as transações de um hash_fatura
    (serve para remover fatura importada 2x)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM transacoes WHERE hash_fatura = ?", (hash_fatura,))
        conn.commit()
        count = cursor.rowcount
        return True, count
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0
    finally:
        conn.close()

def deletar_por_ids(ids):
    """Deletar transações por IDs (lista)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"DELETE FROM transacoes WHERE id IN ({placeholders})", ids)
        conn.commit()
        count = cursor.rowcount
        return True, count
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0
    finally:
        conn.close()

def deletar_por_banco(banco):
    """Deletar todas as transações de um banco específico"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM transacoes WHERE banco = ?", (banco,))
        conn.commit()
        count = cursor.rowcount
        return True, count
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0
    finally:
        conn.close()

def deletar_por_periodo(data_inicio, data_fim):
    """Deletar transações em um período (formato DD/MM/YYYY)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM transacoes WHERE data >= ? AND data <= ?",
            (data_inicio, data_fim)
        )
        conn.commit()
        count = cursor.rowcount
        return True, count
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0
    finally:
        conn.close()

def limpar_banco_completo():
    """Deletar TODAS as transações (irreversível!)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM transacoes")
        conn.commit()
        count = cursor.rowcount
        return True, count
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0
    finally:
        conn.close()

def obter_transacoes_completas():
    """Obter todas as transações com todos os campos"""
    conn = get_connection()
    query = "SELECT * FROM transacoes ORDER BY data DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def obter_estatisticas():
    """Obter estatísticas do banco"""
    conn = get_connection()
    
    stats = {}
    
    # Total de transações
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transacoes")
    stats['total_transacoes'] = cursor.fetchone()[0]
    
    # Total de despesas
    cursor.execute("SELECT SUM(valor) FROM transacoes")
    stats['total_despesas'] = cursor.fetchone()[0] or 0.0
    
    # Bancos únicos
    cursor.execute("SELECT COUNT(DISTINCT banco) FROM transacoes")
    stats['bancos_unicos'] = cursor.fetchone()[0]
    
    # Categorias únicas
    cursor.execute("SELECT COUNT(DISTINCT categoria) FROM transacoes")
    stats['categorias_unicas'] = cursor.fetchone()[0]
    
    # Data mais antiga
    cursor.execute("SELECT MIN(data) FROM transacoes")
    stats['data_inicio'] = cursor.fetchone()[0]
    
    # Data mais recente
    cursor.execute("SELECT MAX(data) FROM transacoes")
    stats['data_fim'] = cursor.fetchone()[0]
    
    conn.close()
    return stats

def obter_transacoes_por_banco(banco):
    """Obter transações de um banco específico"""
    conn = get_connection()
    query = "SELECT * FROM transacoes WHERE banco = ? ORDER BY data DESC"
    df = pd.read_sql_query(query, conn, params=(banco,))
    conn.close()
    return df

def obter_bancos_lista():
    """Obter lista de bancos com contagem"""
    conn = get_connection()
    query = "SELECT banco, COUNT(*) as qtd FROM transacoes GROUP BY banco ORDER BY qtd DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_admin_stats():
    """
    Obter estatísticas para a aba admin.
    Alias para obter_estatisticas()
    """
    stats = obter_estatisticas()
    
    # Contar períodos (meses únicos)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT substr(data, 4, 2) || '/' || substr(data, 7, 4))
        FROM transacoes
    """)
    periodos = cursor.fetchone()[0] or 0
    conn.close()
    
    return {
        'total_transacoes': stats.get('total_transacoes', 0),
        'periodos': periodos,
        'bancos_unicos': stats.get('bancos_unicos', 0),
        'total_despesas': stats.get('total_despesas', 0),
    }

def limpar_duplicatas():
    """
    Limpar duplicatas: se uma fatura foi importada 2x, manter apenas 1 cópia.
    Retorna o número de transações removidas.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Encontrar hashes que aparecem múltiplas vezes
    cursor.execute("""
        SELECT hash_fatura, COUNT(*) as qtd
        FROM transacoes
        GROUP BY hash_fatura
        HAVING qtd > 1
    """)
    
    duplicatas = cursor.fetchall()
    total_removidas = 0
    
    for hash_fatura, qtd in duplicatas:
        # Manter apenas 1, remover os outros (qtd-1)
        cursor.execute("""
            DELETE FROM transacoes
            WHERE hash_fatura = ? AND id NOT IN (
                SELECT id FROM transacoes WHERE hash_fatura = ? LIMIT 1
            )
        """, (hash_fatura, hash_fatura))
        total_removidas += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return total_removidas

def gerar_relatorio():
    """
    Gerar relatório resumido do banco de dados.
    Retorna uma string formatada.
    """
    stats = obter_estatisticas()
    
    relatorio = f"""
    📊 RELATÓRIO DO BANCO DE DADOS
    
    Total de transações: {stats.get('total_transacoes', 0)}
    Total de despesas: R$ {stats.get('total_despesas', 0):,.2f}
    Bancos únicos: {stats.get('bancos_unicos', 0)}
    Categorias únicas: {stats.get('categorias_unicas', 0)}
    
    Período: {stats.get('data_inicio', 'N/A')} a {stats.get('data_fim', 'N/A')}
    """
    
    return relatorio
