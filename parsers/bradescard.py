import fitz
import re

def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=14):
    """Ajustar data da compra ao mês da fatura"""
    if dia >= inicio_ciclo:
        mes = mes_fatura - 1
    else:
        mes = mes_fatura
    if mes == 0:
        mes = 12
        ano = ano_fatura - 1
    else:
        ano = ano_fatura
    return f"{dia:02d}/{mes:02d}/{ano}"

def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser para Bradescard - Extração simplificada (Limpa)
    """
    transactions = []
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            page_text = page.get_text() or ""
            text_all += page_text + "\n"
        
        # Procurar seção "Nacionais em Reais"
        nacionais_pos = text_all.find("Nacionais em Reais")
        if nacionais_pos < 0:
            return []
        
        # Procurar fim da seção de transações
        limites_pos = text_all.find("Lançamentos", nacionais_pos + 50)
        if limites_pos < 0:
            limites_pos = len(text_all)
        
        text_section = text_all[nacionais_pos:limites_pos]
        
        # Padrão: DD/MM + descrição + valor + sinal opcional "-"
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip().upper()
            value_str = match.group(3)
            has_minus = match.group(4)
            
            # Filtros de ruído e linhas de títulos/totais
            desc_upper = desc.upper()
            if not desc or len(desc) < 2:
                continue
            
            # Ignora pagamentos e linhas de sistema do Bradescard
            if any(x in desc_upper for x in ['PAGAMENTO', 'JOSE LEONARDO', 'PROXIMO', 'DEMAIS', 'NACIONAL']):
                continue

            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                
                # Bradescard coloca o "-" após o valor para créditos/pagamentos
                if has_minus == "-":
                    value = -value
                    
            except ValueError:
                continue
            
            # Retorna apenas os dados brutos
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # O centralizador (Router) aplicará o JSON
            })
    
    except Exception as e:
        print(f"Erro no parser Bradescard: {e}")
    
    return transactions
