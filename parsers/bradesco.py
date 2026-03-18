import pdfplumber
import re


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

        # seção onde começam os lançamentos
        start = text_all.find("Histórico de Lançamentos")

        if start == -1:
            return []

        text_section = text_all[start:]

        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)'
        )

        matches = pattern.finditer(text_section)

        print("\n" + "="*120)
        print("BRADESCO DEBUG")
        print("="*120)

        for m in matches:

            data = m.group(1)
            desc = m.group(2).strip()
            valor_str = m.group(3)
            sinal = m.group(4)

            # filtro pagamento da fatura
            if "PAG BOLETO" in desc.upper():
                continue

            if desc.startswith("Total"):
                continue

            try:
                valor = float(valor_str.replace(".", "").replace(",", "."))
            except:
                continue

            if sinal == "-":
                valor = -valor

            
            
            print(f"{data} | {desc} | {valor}")

            transactions.append({
                "data": data,
                "descricao": desc,
                "valor": valor
            })

        print("="*120)
        pass  # removed total print
        print("="*120)

    except Exception as e:

        print("Erro no parser Bradesco:", e)

    return transactions