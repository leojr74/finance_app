# utils/finance_tools.py
from dateutil.relativedelta import relativedelta
import datetime
import pandas as pd

def gerar_projeções_parcelas(transacao_origem, parcela_atual, total_parcelas, user_id):
    """
    Gera as parcelas futuras formatadas para o database.salvar_transacoes.
    A ordem da tupla deve seguir: (data, descricao, valor, categoria, banco, hash_fatura, user_id)
    """
    projeções = []
    
    # 1. Tratamento da data original (garantindo formato datetime)
    try:
        # Tenta converter a data que vem do DataFrame/Dicionário
        data_base = pd.to_datetime(transacao_origem['data'])
    except:
        # Fallback caso a data esteja em string DD/MM/YYYY
        data_base = datetime.datetime.strptime(transacao_origem['data'], "%d/%m/%Y")
    
    faltam = total_parcelas - parcela_atual
    
    # 2. Loop para gerar os meses seguintes
    for i in range(1, faltam + 1):
        nova_data = data_base + relativedelta(months=i)
        
        # 3. Gerar um Hash Único para a projeção
        # Isso evita que o seu banco barre a inserção por achar que é duplicata
        hash_proj = f"PROJ-{transacao_origem['id']}-{parcela_atual + i}"
        
        # 4. Limpar a descrição (remove "(10/12)" antigo se houver e bota o novo)
        desc_limpa = transacao_origem['descricao'].split(' (')[0].split(' DE ')[0].strip()
        desc_nova = f"{desc_limpa} ({parcela_atual + i}/{total_parcelas})"
        
        # 5. Montar a TUPLA na ordem exata que o database.salvar_transacoes exige
        # Verificado no seu database.py: (data, descricao, valor, categoria, banco, hash_fatura, user_id)
        nova_tupla = (
            nova_data.strftime('%Y-%m-%d'), # Formato ISO para o Postgres
            desc_nova,
            float(transacao_origem['valor']),
            transacao_origem['categoria'],
            transacao_origem.get('banco', 'Projeção'),
            hash_proj,
            user_id
        )
        projeções.append(nova_tupla)
        
    return projeções