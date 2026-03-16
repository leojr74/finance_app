
import pdfplumber
import re
from categorizer import load_categories, find_category


def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    '''
    Parser C&A (C&A Pay)

    Extrai transações do demonstrativo da fatura.
    Datas são padronizadas para DD/MM (sem ano) para que o
    parser_router reconstrua o ano correto usando o período da fatura.
    '''

    transactions = []

    try:

        text_all = ""

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"

        print("C&A - DEBUG: Operações extraídas")
        print("=" * 120)

        demo_pos = text_all.find("Demonstrativo")
        if demo_pos < 0:
            print("❌ Seção 'Demonstrativo' não encontrada")
            return []

        fim_pos = text_all.find("Apertou?", demo_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)

        text_section = text_all[demo_pos:fim_pos]

        seen = {}
        extracted_count = 0

        pattern = re.compile(
            r'(\d{2}/\d{2}(?:/\d{4})?)\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)',
            re.MULTILINE
        )

        for match in pattern.finditer(text_section):

            date_str = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            has_minus = match.group(4)

            if not desc:
                continue

            if not re.search(r'[A-Za-z0-9]', desc):
                continue

            if any(x in desc.upper() for x in [
                'TOTAL',
                'FATURA ANTERIOR',
                'LIMITE',
                'CRÉDITO',
                'DÉBITO',
                'PAGAMENTO'
            ]):
                continue

            if len(desc) > 80:
                continue

            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            if has_minus == "-":
                value = -value

            # normalizar data para DD/MM
            if date_str.count("/") == 2:
                dia, mes, _ = date_str.split("/")
                data_normalizada = f"{dia}/{mes}"
            else:
                data_normalizada = date_str

            desc_normalized = " ".join(desc.split())
            key = (data_normalizada, desc_normalized, value)

            if key not in seen:

                seen[key] = True
                extracted_count += 1

                print(f"{extracted_count:2d}. {data_normalizada} | {desc[:60]:60s} | R$ {value:8.2f}")

                categories = load_categories()
                category = find_category(desc, categories)

                if not category:
                    category = "Sem categoria"

                transactions.append({
                    "data": data_normalizada,
                    "descricao": desc.strip(),
                    "valor": value,
                    "categoria": category
                })

        print("=" * 120)
        print()

    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

    return transactions
