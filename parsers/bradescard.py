import pdfplumber
import re
from categorizer import load_categories, find_category

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
    Parser para Bradescard - extrai transações do cartão
    
    Estrutura do PDF:
    - Nacionais em Reais (seção de transações)
    - Padrão: DD/MM + DESCRIÇÃO + VALOR (com "-" no final = negativo)
    
    Exemplo:
    29/12 PAGAMENTO RECEBIDO - OBRIGADO 550,61-
    30/12 AMAZON BR SAO PAULO(01/10) 72,15
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
               
        # Procurar seção "Nacionais em Reais"
        nacionais_pos = text_all.find("Nacionais em Reais")
        if nacionais_pos < 0:
            return []
        
        # Procurar fim de forma mais cautelosa
        # Pode ser "Lançamentos Total parcelado" ou fim do arquivo/página
        limites_pos = text_all.find("Lançamentos", nacionais_pos + 50)  # Procura DEPOIS de Nacionais
        if limites_pos < 0:
            limites_pos = len(text_all)
        
        text_section = text_all[nacionais_pos:limites_pos]
        
        seen = {}
        extracted_count = 0
        
        # Padrão: DD/MM + descrição até PRIMEIRO valor + opcional "-"
        # Não usar lookahead - simplesmente capturar o que vem
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            has_minus = match.group(4)
            
            # Filtros básicos
            if not desc or len(desc) < 1:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            # Ignorar se descrição tem valor numérico grande (marca "demais" ou "próximo")
            # Também ignorar pagamentos já contabilizados
            if len(desc) > 100 or desc.count('R$') > 0 or 'PAGAMENTO' in desc.upper():  
                continue
            
            # Ignorar linhas que são títulos
            if any(x.upper() in desc.upper() for x in ['JOSE LEONARDO', 'PROXIMO', 'DEMAIS', 'NACIONAL']):
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Se tem "-" no final, é valor negativo
            if has_minus == "-":
                value = -value
            
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
        
        
    
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions
