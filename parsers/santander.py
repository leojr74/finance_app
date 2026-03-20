
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
    Parser para Santander - Extração limpa com limpeza de descrição e MAIÚSCULAS
    """
    transactions = []
    ultima_data = None 

    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"

        detalhamento_pos = text_all.find("Detalhamento da Fatura")
        if detalhamento_pos < 0:
            return []

        text_section = text_all[detalhamento_pos:]

        # Regex para capturar: Data | Descrição | Valor
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+((?:(?!-?\d{1,3}(?:\.\d{3})*,\d{2}).)*?)\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s|$)',
            re.MULTILINE
        )

        matches = list(pattern.finditer(text_section))

        for m in matches:
            date = m.group(1)
            desc = m.group(2).strip().upper() # Padronização para MAIÚSCULAS
            value_str = m.group(3)

            # 1. Limpeza de ruídos específicos do Santander na descrição
            # Remove indicadores de parcelas (ex: /10) e números isolados no fim
            desc = re.sub(r'(?<!\d)/(?!\d)\s*\d+\s*$', '', desc).strip()
            desc = re.sub(r'^\s*\d+\s*(?!/)', '', desc).strip()
            desc = re.sub(r'📳', '', desc).strip() # Remove emoji de notificação

            # 2. Filtros de segurança
            if not desc or len(desc) < 2:
                continue
            if 'PAGAMENTO' in desc and 'FATURA' in desc:
                continue
            if re.match(r'^[A-ZÀ-Ÿ\s]+\s\.[A-ZÀ-Ÿ\s]+$', desc): # Filtro de metadados/cidades
                continue

            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            ultima_data = date

            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # Router + JSON resolvem agora
            })

        # --------------------------------------------------
        # TRATAMENTO ESPECIAL: IOF EXTERIOR
        # --------------------------------------------------
        iof_pattern = re.compile(r'IOF DESPESA NO EXTERIOR\s+(\d+,\d{2})')
        iof_matches = iof_pattern.findall(text_all)

        for iof_val in iof_matches:
            try:
                val = float(iof_val.replace(".", "").replace(",", "."))
                transactions.append({
                    "data": ultima_data if ultima_data else f"01/{mes_fatura:02d}",
                    "descricao": "IOF DESPESA NO EXTERIOR",
                    "valor": val,
                    "categoria": "Sem categoria"
                })
            except ValueError:
                continue

    except Exception as e:
        print(f"Erro no parser Santander: {e}")

    return transactions
