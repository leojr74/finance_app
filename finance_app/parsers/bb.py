import fitz
import re

def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=24):
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
    Parser para Banco do Brasil - Extração simplificada (Limpa)
    """
    transactions = []
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            page_text = page.get_text() or ""
            text_all += page_text + "\n"
        
        # Localizar a seção de lançamentos
        lancamentos_pos = text_all.find("Lançamentos nesta fatura")
        if lancamentos_pos < 0:
            return []
        
        text_section = text_all[lancamentos_pos:]
        
        # Padrão: DD/MM + descrição + país (BR/US) + R$ valor
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(BR|US)\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip().upper()
            value_str = match.group(4)
            
            # Filtros de títulos e linhas irrelevantes
            desc_upper = desc.upper()
            if any(desc_upper.startswith(x) for x in [
                'SALDO FATURA ANTERIOR', 'PAGAMENTOS', 'OUTROS LANÇAMENTOS', 
                'COMPRAS PARCELADAS', 'SUBTOTAL', 'TOTAL DA FATURA'
            ]):
                continue
            
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                
                # Tratar créditos (pagamentos ou estornos no BB começam com "-")
                if desc.startswith('-') or value_str.startswith('-'):
                    value = abs(value) * -1
                    
            except ValueError:
                continue
            
            # Monta o dicionário sem tentar categorizar aqui
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # O Router resolverá isso via JSON
            })
            
    except Exception as e:
        print(f"Erro no parser BB: {e}")
    
    return transactions
