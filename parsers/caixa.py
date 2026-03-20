import pdfplumber
import re
from categorizer import load_categories, find_category

def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=12):
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
    Parser para Caixa - Extração simplificada e em MAIÚSCULAS (Limpa)
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        # Padrão: DD/MM + descrição + valor + indicador D/C (Débito/Crédito)
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})([DC]?)(?:\s|$)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_all):
            date = match.group(1)
            # AQUI: Forçamos a descrição para MAIÚSCULAS e removemos espaços extras
            desc = match.group(2).strip().upper() 
            value_str = match.group(3)
            dc = match.group(4) if match.group(4) else "D"
            
            # Filtros de ruído
            if not desc or len(desc) < 2:
                continue
            
            # Ignorar operações administrativas (Fatura anterior, pagamentos, totalizadores)
            ignore_patterns = [
                r'^TOTAL DA FATURA ANTERIOR',
                r'^OBRIGADO PELO PAGAMENTO',
                r'^TOTAL', 
                r'^DATA ', 
                r'^VALOR ',
                r'A\.A(?:\s|$)', 
                r'A\.M(?:\s|$)', 
            ]
            
            if any(re.match(p, desc) for p in ignore_patterns):
                continue
            
            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                
                # Caixa: D = débito (gasto), C = crédito (estorno/reembolso)
                if dc == "C":
                    value = -value
            except ValueError:
                continue
            
            # Retorna apenas os dados brutos estruturados
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # O Router fará a mágica com o JSON
            })
    
    except Exception as e:
        print(f"Erro no parser Caixa: {e}")
    
    return transactions
