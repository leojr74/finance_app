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
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        lancamentos_pos = text_all.find("Lançamentos: compras e saques")
        if lancamentos_pos < 0:
            return []
        
        compras_parceladas_pos = text_all.find("Compras parceladas - próximas faturas", lancamentos_pos)
        proxima_fatura_pos = text_all.find("Próxima fatura", lancamentos_pos)
        
        text_section = text_all[lancamentos_pos:]
        
        pattern = re.compile(r'(\d{2}/\d{2})\s+(.+?)(\d{1,3}(?:\.\d{3})*,\d{2})')
        all_matches_raw = list(pattern.finditer(text_section))
        
        # Filtrar metadados - têm padrão: MAIÚSCULAS + ESPAÇO + PONTO + cidade
        all_matches = []
        for match in all_matches_raw:
            desc = match.group(2).strip()
            # Metadado: MAIÚSCULAS + ESPAÇO + PONTO + palavra
            if re.match(r'^[A-ZÀ-Ÿ\s]+\s\.[A-Za-zÀ-Ÿ\s]+$', desc):
                continue
            all_matches.append(match)
        
        seen = {}
        transaction_index_after_compras = 0
        first_transaction_after_compras_idx = None
        extracted_count = 0
        
        pass  # removed debug print
        print(f"ITAÚ - DEBUG: Operações extraídas")
        print(f"{'='*120}")
        
        for match in all_matches:
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            
            if not desc or len(desc) < 1:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Se descrição termina com "-", é cancelamento/devolução (valor negativo)
            if desc.endswith("-"):
                value = -value
                desc = desc.rstrip("-").strip()
            
            # Calcular posições relativas
            compras_parceladas_rel_pos = -1
            if compras_parceladas_pos >= 0:
                compras_parceladas_rel_pos = compras_parceladas_pos - lancamentos_pos
            
            proxima_fatura_rel_pos = -1
            if proxima_fatura_pos >= 0:
                proxima_fatura_rel_pos = proxima_fatura_pos - lancamentos_pos
            
            # Determinar em qual seção está
            is_between_compras_and_proxima = (
                compras_parceladas_rel_pos >= 0 and 
                proxima_fatura_rel_pos >= 0 and
                match.start() >= compras_parceladas_rel_pos and 
                match.start() < proxima_fatura_rel_pos
            )
            
            # Aplicar filtro x+3n APENAS entre "Compras parceladas" e "Próxima fatura"
            if is_between_compras_and_proxima:
                # Aplicar filtro x+3n
                if first_transaction_after_compras_idx is None:
                    first_transaction_after_compras_idx = transaction_index_after_compras
                
                idx_relative_to_x = transaction_index_after_compras - first_transaction_after_compras_idx
                transaction_index_after_compras += 1
                
                # Descartar se NÃO for múltiplo de 3
                if idx_relative_to_x % 3 != 0:
                    continue
                
                status = f"[x+{idx_relative_to_x}]"
            else:
                # Antes de "Compras parceladas" OU depois de "Próxima fatura" - sem filtro
                status = ""
            
            # Adicionar transação
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
