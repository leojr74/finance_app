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
    Parser para Caixa - extrai transações de múltiplos cartões
    
    Estratégia:
    1. Extrai operações do Demonstrativo (exceto TOTAL FATURA ANTERIOR e PAGAMENTO)
    2. Extrai COMPRAS (Cartão)
    3. Extrai COMPRAS PARCELADAS (Cartão)
    4. Procura por linhas contendo "DD/MM + DESCRIÇÃO + VALOR + D/C"
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        # Usar todo o texto (inclui Demonstrativo e Compras)
        text_section = text_all
        
        pass  # removed debug print
        print(f"CAIXA - DEBUG: Operações extraídas")
        print(f"{'='*120}")
        
        seen = {}
        extracted_count = 0
        
        # Padrão: qualquer coisa + DD/MM + descrição + valor + D/C
        # Pega tudo que tem DD/MM na linha e valor no final
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})([DC]?)(?:\s|$)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            dc = match.group(4) if match.group(4) else "D"
            
            # Filtros
            if not desc or len(desc) < 1:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            # Ignorar apenas operações administrativas: fatura anterior e pagamento
            # Manter ajustes de crédito, reembolsos, etc.
            ignore_patterns = [
                r'^TOTAL DA FATURA ANTERIOR',
                r'^OBRIGADO PELO PAGAMENTO',
                r'^Total ',  # Totalizadores de seção
                r'^TOTAL',   # Mais totalizadores
                r'^Data ',   # Cabeçalho
                r'^Crédito',
                r'^Valor ',
                r'a\.a(?:\s|$)',  # Linhas com percentual de taxa
                r'a\.m(?:\s|$)',  # Linhas com percentual de taxa
            ]
            
            if any(re.match(p, desc) for p in ignore_patterns):
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Caixa: D = débito (despesa), C = crédito (anulação/reembolso)
            # Manter AMBAS as operações - quando há anulação:
            # - Compra: +431,39 D
            # - Anulação: -431,39 C
            # Somadas = 0 (compra realmente não foi feita)
            if dc == "C":
                value = -value  # Crédito = negativo (abate a compra)
            
            desc_normalized = ' '.join(desc.split())
            key = (date, desc_normalized, value)
            
            if key not in seen:
                seen[key] = True
                extracted_count += 1
                pass  # removed transaction print
                
                categories = load_categories()
                category = find_category(desc, categories)
                if not category:
                    category = "Sem categoria"
                
                dia = int(date.split("/")[0])
                data_corrigida = date
                
                transactions.append({
                    "data": date,
                    "descricao": desc.strip(),
                    "valor": value,
                    "categoria": category
                })
        
        pass  # removed debug print
        pass  # removed total print
        print(f"{'='*120}\n")
    
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions
