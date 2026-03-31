import fitz
import re

def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=12):
    if dia >= inicio_ciclo:
        mes = mes_fatura - 1
    else:
        mes = mes_fatura
    if mes <= 0:
        mes = 12
        ano = ano_fatura - 1
    else:
        ano = ano_fatura
    return f"{dia:02d}/{mes:02d}/{ano}"

def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser Santander Corrigido: Captura compras parceladas e mantém integridade dos dados.
    """
    transactions = []
    ultima_data = None 

    try:
        text_all = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text_all += page.get_text() + "\n"

        detalhamento_pos = text_all.find("Detalhamento da Fatura")
        if detalhamento_pos < 0:
            return []

        text_section = text_all[detalhamento_pos:]

        # REGEX ATUALIZADA: 
        # 1. Captura Data (DD/MM)
        # 2. Captura TUDO até encontrar um valor no formato 0,00 ou 0.000,00 (aceita parcelas como 01/10)
        # 3. Captura o Valor
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.*?)\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s|$)',
            re.DOTALL # Permite que o '.' capture quebras de linha se a descrição for longa
        )

        matches = list(pattern.finditer(text_section))

        for m in matches:
            date = m.group(1)
            desc_raw = m.group(2).strip().upper()
            value_str = m.group(3)

            # --- HIGIENIZAÇÃO SEGURA DA DESCRIÇÃO ---
            # Remove o emoji de celular e outros caracteres não-ascii
            desc = re.sub(r'[^\x00-\x7F]+', ' ', desc_raw)
            
            # Remove indicadores de parcelas NO FINAL ou NO MEIO sem apagar a loja
            # Ex: "LOJA XPTO 01/10" -> "LOJA XPTO"
            desc = re.sub(r'\s*\d{1,2}/\d{1,2}\s*', ' ', desc)
            
            # Limpa espaços duplos resultantes da remoção
            desc = " ".join(desc.split()).strip()

            # --- FILTROS DE EXCLUSÃO ---
            if not desc or len(desc) < 2:
                continue
            # Ignora pagamentos de fatura e créditos de ajuste
            if 'PAGAMENTO' in desc and 'FATURA' in desc:
                continue
            if 'TOTAL ANTECIPADO' in desc or 'SALDO ANTERIOR' in desc:
                continue

            try:
                # Converte valor para float
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            ultima_data = date

            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria"
            })

        # --- TRATAMENTO DE IOF ---
        iof_pattern = re.compile(r'IOF DESPESA NO EXTERIOR\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})')
        iof_matches = iof_pattern.findall(text_all)

        for iof_val in iof_matches:
            try:
                val = float(iof_val.replace(".", "").replace(",", "."))
                transactions.append({
                    "data": ultima_data if ultima_data else f"01/{mes_fatura:02d}",
                    "descricao": "IOF DESPESA NO EXTERIOR",
                    "valor": val,
                    "categoria": "Impostos"
                })
            except ValueError:
                continue

    except Exception as e:
        print(f"Erro no parser Santander: {e}")

    return transactions