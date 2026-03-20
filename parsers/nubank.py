import fitz
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
    Parser para Nubank - Extração limpa e em MAIÚSCULAS
    """
    transactions = []
    meses_map = {
        'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
    }
    
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            text_all += (page.get_text() or "") + "\n"
        
        # Localiza a seção de transações para evitar capturar o "Resumo" ou rodapés
        trans_pos = text_all.find("TRANSAÇÕES DE")
        if trans_pos < 0:
            return []
        
        fim_pos = text_all.find("Em cumprimento à regulação", trans_pos)
        text_section = text_all[trans_pos:fim_pos] if fim_pos > 0 else text_all[trans_pos:]
        lines = text_section.split('\n')

        for line in lines:
            line = line.strip()
            if "R$" not in line:
                continue

            # REGEX: Data (06 OUT) + Descrição + Sinal/Cifrão + Valor (1.234,56)
            match = re.search(r'(\d{2})\s+(\w{3})\s+(.+?)\s+([−-]?\s?R\$)\s+(\d{1,3}(?:\.\d{3})*,\d{2})$', line)
            
            if match:
                dia, mes_str, desc, sinal_str, value_str = match.groups()
                mes_num = meses_map.get(mes_str.upper())
                
                if not mes_num:
                    continue

                # No Nubank, o sinal de menos (curto ou longo) indica um crédito/estorno
                is_credit = "−" in sinal_str or "-" in sinal_str
                
                try:
                    raw_value = float(value_str.replace(".", "").replace(",", "."))
                    # Se for crédito, o valor entra negativo (abate a fatura)
                    value = -raw_value if is_credit else raw_value
                except ValueError:
                    continue

                # Converte descrição para MAIÚSCULAS
                desc_upper = desc.strip().upper()

                # Filtro de segurança: ignora o pagamento da própria fatura
                if "PAGAMENTO EM" in desc_upper:
                    continue

                # Formata a data como DD/MM para o Router
                data_formatada = f"{int(dia):02d}/{mes_num:02d}"

                transactions.append({
                    "data": data_formatada,
                    "descricao": desc_upper,
                    "valor": value,
                    "categoria": "Sem categoria" # Centralizado no Router + JSON
                })

    except Exception as e:
        print(f"Erro na extração Nubank: {e}")
    
    return transactions