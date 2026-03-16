import pdfplumber
import re
from categorizer import load_categories, find_category

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
    Parser para Banco do Brasil - extrai transações do cartão
    
    Estrutura do PDF:
    - SALDO FATURA ANTERIOR (IGNORAR - é do mês anterior)
    - Pagamentos/Créditos (incluir - são movimentações)
    - Outros lançamentos (incluir - despesas reais)
    - Compras parceladas (incluir - despesas parceladas)
    
    Padrão: DD/MM + DESCRIÇÃO + PAÍS + R$ VALOR
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        pass  # removed debug print
        print(f"BANCO DO BRASIL - DEBUG: Operações extraídas")
        print(f"{'='*120}")
        
        # Procurar seção "Lançamentos nesta fatura"
        lancamentos_pos = text_all.find("Lançamentos nesta fatura")
        if lancamentos_pos < 0:
            return []
        
        text_section = text_all[lancamentos_pos:]
        
        seen = {}
        extracted_count = 0
        
        # Padrão: DD/MM + descrição + país (BR/US) + R$ valor
        # Descrição pode conter números, "-", parenteses, etc
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(BR|US)\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip()
            country = match.group(3)
            value_str = match.group(4)
            
            # Filtros básicos
            if not desc or len(desc) < 1:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            # Ignorar linhas que são títulos
            if desc.upper().startswith('SALDO FATURA ANTERIOR') or \
               desc.upper().startswith('PAGAMENTOS') or \
               desc.upper().startswith('OUTROS LANÇAMENTOS') or \
               desc.upper().startswith('COMPRAS PARCELADAS') or \
               desc.upper().startswith('SUBTOTAL') or \
               desc.upper().startswith('TOTAL DA FATURA'):
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Se descrição começa com "-", é crédito (valor negativo já)
            # Pagamentos já vêm como negativo no PDF (PGTO. COBRANCA R$ -120,00)
            if desc.startswith('-') or value_str.startswith('-'):
                value = abs(value) * -1
            
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
