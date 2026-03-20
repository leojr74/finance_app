import fitz
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
    Parser para Itaú - Extração limpa com suporte a parcelados e MAIÚSCULAS
    """
    transactions = []
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            page_text = page.get_text() or ""
            text_all += page_text + "\n"
        
        lancamentos_pos = text_all.find("Lançamentos: compras e saques")
        if lancamentos_pos < 0:
            return []
        
        compras_parceladas_pos = text_all.find("Compras parceladas - próximas faturas", lancamentos_pos)
        proxima_fatura_pos = text_all.find("Próxima fatura", lancamentos_pos)
        
        text_section = text_all[lancamentos_pos:]
        pattern = re.compile(r'(\d{2}/\d{2})\s+(.+?)(\d{1,3}(?:\.\d{3})*,\d{2})')
        all_matches_raw = list(pattern.finditer(text_section))
        
        # 1. Filtrar metadados específicos do PDF do Itaú
        all_matches = []
        for match in all_matches_raw:
            desc = match.group(2).strip().upper()
            if re.match(r'^[A-ZÀ-Ÿ\s]+\s\.[A-ZÀ-Ÿ\s]+$', desc):
                continue
            all_matches.append(match)
        
        transaction_index_after_compras = 0
        first_transaction_after_compras_idx = None
        
        # 2. Processar matches
        for match in all_matches:
            date = match.group(1)
            desc = match.group(2).strip().upper() # Forçar MAIÚSCULAS
            value_str = match.group(3)
            
            if not desc or len(desc) < 2:
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Tratar cancelamentos (Itaú coloca "-" no fim da descrição)
            if desc.endswith("-"):
                value = -value
                desc = desc.rstrip("-").strip()
            
            # 3. Lógica Especial Itaú: Filtro de parcelados (regra x+3n)
            # Esta lógica é mantida aqui pois é estrutural do PDF do Itaú
            rel_start = match.start()
            c_parc_rel = compras_parceladas_pos - lancamentos_pos if compras_parceladas_pos >= 0 else -1
            p_fat_rel = proxima_fatura_pos - lancamentos_pos if proxima_fatura_pos >= 0 else -1
            
            is_between = (c_parc_rel >= 0 and p_fat_rel >= 0 and 
                          rel_start >= c_parc_rel and rel_start < p_fat_rel)
            
            if is_between:
                if first_transaction_after_compras_idx is None:
                    first_transaction_after_compras_idx = transaction_index_after_compras
                
                idx_rel = transaction_index_after_compras - first_transaction_after_compras_idx
                transaction_index_after_compras += 1
                
                if idx_rel % 3 != 0:
                    continue

            # 4. Adicionar à lista final (Dados Brutos)
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # Router aplica o JSON depois
            })
            
    except Exception as e:
        print(f"Erro no parser Itaú: {e}")
    
    return transactions