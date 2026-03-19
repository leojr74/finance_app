import sqlite3

def atualizar_nomes_bancos():
    try:
        conn = sqlite3.connect("transacoes.db")
        cursor = conn.cursor()

        # Dicionário de De -> Para
        mapeamento = {
            "CAIXA": "CARTÃO CAIXA",
            "BRADESCARD": "CARTÃO AMAZON",
            "BRADESCO": "CARTÃO BRADESCO",
            "SANTANDER": "CARTÃO SANTANDER"
        }

        print("Iniciando atualização dos nomes dos bancos...")
        
        for antigo, novo in mapeamento.items():
            # O UPPER garante que pegaremos variações de caixa/CAIXA
            cursor.execute("""
                UPDATE transacoes 
                SET banco = ? 
                WHERE UPPER(banco) = ?
            """, (novo, antigo))
            
            print(f"Linhas alteradas de '{antigo}' para '{novo}': {cursor.rowcount}")

        conn.commit()
        conn.close()
        print("\n✅ Atualização concluída com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao atualizar: {e}")

if __name__ == "__main__":
    atualizar_nomes_bancos()