
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
    ultima_data = None  # <- guardar última data válida para associar IOF

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

        pattern = re.compile(
            r'(\d{2}/\d{2})\s+((?:(?!-?\d{1,3}(?:\.\d{3})*,\d{2}).)*?)\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s|$)',
            re.MULTILINE
        )

        all_matches_raw = list(pattern.finditer(text_section))

        cleaned_matches = []
        for match in all_matches_raw:
            date = match.group(1)
            desc = match.group(2).strip()
            value = match.group(3)

            tem_parcela = bool(re.search(r'\s\d{2}/\d{2}(?:\s|$)', desc))

            desc = re.sub(r'(?<!\d)/(?!\d)\s*\d+\s*$', '', desc).strip()
            desc = re.sub(r'^\s*\d+\s*(?!/)', '', desc).strip()
            desc = re.sub(r'📳', '', desc).strip()

            cleaned_matches.append((match, date, desc, value, tem_parcela))

        class Match:
            def __init__(self, m, date, desc, val, parcela):
                self.m = m
                self._date = date
                self._desc = desc
                self._value = val
                self._tem_parcela = parcela
            def group(self, n):
                if n == 0: return self.m.group(0)
                if n == 1: return self._date
                if n == 2: return self._desc
                if n == 3: return self._value
            def start(self):
                return self.m.start()
            def tem_parcela(self):
                return self._tem_parcela

        all_matches_raw = [Match(m, d, ds, v, p) for m, d, ds, v, p in cleaned_matches]

        all_matches = []
        for match in all_matches_raw:
            desc = match.group(2).strip()
            if re.match(r'^[A-ZÀ-Ÿ\s]+\s\.[A-Za-zÀ-Ÿ\s]+$', desc):
                continue
            all_matches.append(match)

        occurrence_count = {}
        for match in all_matches:
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            value = float(value_str.replace(".", "").replace(",", "."))

            key = (date, desc, value)
            occurrence_count[key] = occurrence_count.get(key, 0) + 1

        for match in all_matches:
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)

            if not desc or len(desc) < 1:
                continue

            if not re.search(r'[A-Za-z0-9]', desc):
                continue

            if 'PAGAMENTO' in desc.upper() and 'FATURA' in desc.upper():
                continue

            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            # guardar última data válida
            ultima_data = date

            categories = load_categories()
            category = find_category(desc, categories)
            if not category:
                category = "Sem categoria"

            transactions.append({
                "data": date,
                "descricao": desc.strip(),
                "valor": value,
                "categoria": category
            })

        # --------------------------------------------------
        # EXTRAIR IOF DESPESA NO EXTERIOR
        # --------------------------------------------------

        iof_pattern = re.compile(r'IOF DESPESA NO EXTERIOR\s+(\d+,\d{2})')
        iof_matches = iof_pattern.findall(text_all)

        if iof_matches:
            for iof_value_str in iof_matches:
                try:
                    iof_value = float(iof_value_str.replace(".", "").replace(",", "."))

                    transactions.append({
                        "data": ultima_data if ultima_data else f"01/{mes_fatura:02d}",
                        "descricao": "IOF DESPESA NO EXTERIOR",
                        "valor": iof_value,
                        "categoria": "Taxas"
                    })

                except ValueError:
                    continue

    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

    return transactions
