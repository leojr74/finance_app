import pdfplumber
import re
from categorizer import load_categories, find_category


def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=20):
    """Ajustar data da compra ao mês da fatura - Nubank começa em 20"""
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
    Parser para Nubank - exclui apenas o pagamento da fatura anterior.
    
    Puxa todas as operações. O usuário decide depois quais quer manter
    ou excluir para categorização de fluxo de caixa.
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        pass  # removed debug print
        print(f"NUBANK - DEBUG: TODAS as operações")
        print(f"{'='*120}")
        
        # Procurar seção "TRANSAÇÕES DE"
        trans_pos = text_all.find("TRANSAÇÕES DE")
        if trans_pos < 0:
            return []
        
        fim_pos = text_all.find("Em cumprimento à regulação", trans_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)
        
        text_section = text_all[trans_pos:fim_pos]
        lines = text_section.split('\n')
        
        extracted_count = 0
        meses = {
            'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # ===== LINHAS COM NEGATIVO (−R$) =====
            match = re.match(r'(\d{2})\s+(\w{3})\s+(.+?)\s+−R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})$', line)
            if match:
                dia, mes_str, desc, value_str = match.groups()
                mes_num = meses.get(mes_str.upper())
                if not mes_num:
                    continue
                # FILTRO: remover pagamento da fatura anterior
                if desc.lower().startswith("pagamento em"):
                    continue
                try:
                    value = -float(value_str.replace(".", "").replace(",", "."))
                except ValueError:
                    continue
                
                key = (f"{dia}/{mes_str}", desc.strip(), value)
                
                extracted_count += 1
                data = ajustar_data_compra(int(dia), mes_fatura, ano_fatura)
                
                cat = "Sem categoria"
                if 'pagamento' in desc.lower():
                    cat = "Pagamento"
                elif 'desconto' in desc.lower():
                    cat = "Desconto"
                elif 'crédito' in desc.lower():
                    cat = "Crédito"
                elif 'encerramento' in desc.lower():
                    cat = "Encerramento"
                
                print(f"{extracted_count:2d}. {data} | {desc.strip():50s} | R$ {value:8.2f}")
                transactions.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": value,
                    "categoria": cat
                })
                
            
            # ===== LINHAS COM POSITIVO (R$) =====
            match = re.match(r'(\d{2})\s+(\w{3})\s+(.+?)\s+R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})$', line)
            if match:
                dia, mes_str, desc, value_str = match.groups()
                mes_num = meses.get(mes_str.upper())
                if not mes_num:
                    continue
                
                try:
                    value = float(value_str.replace(".", "").replace(",", "."))
                except ValueError:
                    continue
                
                key = (f"{dia}/{mes_str}", desc.strip(), value)
                
                extracted_count += 1
                data = ajustar_data_compra(int(dia), mes_fatura, ano_fatura)
                
                desc_lower = desc.lower()
                cat = "Sem categoria"
                
                if 'juros de atraso' in desc_lower:
                    cat = "Juros"
                elif 'iof de atraso' in desc_lower:
                    cat = "Impostos"
                elif 'multa de atraso' in desc_lower:
                    cat = "Multa"
                elif 'saldo em' in desc_lower:
                    cat = "Saldo"
                elif 'juros de dívida' in desc_lower:
                    cat = "Juros"
                else:
                    # Tenta classificar como compra
                    categories = load_categories()
                    cat = find_category(desc, categories) or "Sem categoria"
                
                print(f"{extracted_count:2d}. {data} | {desc.strip():50s} | R$ {value:8.2f}")
                transactions.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": value,
                    "categoria": cat
                })
        
        pass  # removed debug print
        print(f"Total: {len(transactions)} operações - R$ {sum(t['valor'] for t in transactions):.2f}")
        print(f"{'='*120}\n")
    
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions
