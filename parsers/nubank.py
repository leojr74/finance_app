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
    transactions = []
    meses = {
        'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
    }
    
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_all += (page.extract_text() or "") + "\n"
        
        # Localiza a seção de transações para evitar pegar o "Resumo" da página 4
        trans_pos = text_all.find("TRANSAÇÕES DE")
        if trans_pos < 0:
            return []
        
        # Define o fim da leitura para não pegar rodapés
        fim_pos = text_all.find("Em cumprimento à regulação", trans_pos)
        text_section = text_all[trans_pos:fim_pos] if fim_pos > 0 else text_all[trans_pos:]
        lines = text_section.split('\n')

        for line in lines:
            line = line.strip()
            if "R$" not in line:
                continue

            # REGEX UNIFICADA: 
            # 1. (\d{2})\s+(\w{3}) -> Data (Ex: 06 OUT)
            # 2. (.+?) -> Descrição
            # 3. ([−-]?\s?R\$) -> Captura R$ com ou sem sinal de menos (curto ou longo) antes
            # 4. (\d{1,3}(?:\.\d{3})*,\d{2}) -> O valor numérico brasileiro
            match = re.search(r'(\d{2})\s+(\w{3})\s+(.+?)\s+([−-]?\s?R\$)\s+(\d{1,3}(?:\.\d{3})*,\d{2})$', line)
            
            if match:
                dia, mes_str, desc, sinal_str, value_str = match.groups()
                mes_num = meses.get(mes_str.upper())
                if not mes_num:
                    continue

                # Se houver qualquer traço (curto ou longo) na string do cifrão, é CRÉDITO (valor negativo no sistema)
                # No cartão, o que diminui a conta entra como negativo para o seu saldo[cite: 82, 87, 90].
                is_credit = "−" in sinal_str or "-" in sinal_str
                
                try:
                    raw_value = float(value_str.replace(".", "").replace(",", "."))
                    value = -raw_value if is_credit else raw_value
                except ValueError:
                    continue

                # Filtro de segurança: ignorar pagamento da fatura anterior para não duplicar gastos 
                if "pagamento em" in desc.lower():
                    continue

                # Formata a data para o Router processar
                data_formatada = f"{int(dia):02d}/{mes_num:02d}"
                
                # Categorização básica inteligente
                desc_lower = desc.lower()
                if any(x in desc_lower for x in ['juros', 'mora']): cat = "Juros"
                elif 'iof' in desc_lower: cat = "Impostos"
                elif 'multa' in desc_lower: cat = "Multa"
                elif is_credit: cat = "Crédito/Estorno"
                else:
                    # Se não for nada óbvio, usa o seu categorizador automático
                    cat = find_category(desc, load_categories()) or "Sem categoria"

                transactions.append({
                    "data": data_formatada,
                    "descricao": desc.strip(),
                    "valor": value,
                    "categoria": cat
                })

        print(f"NUBANK: Extraídas {len(transactions)} operações.")
    
    except Exception as e:
        print(f"Erro na extração Nubank: {e}")
    
    return transactions