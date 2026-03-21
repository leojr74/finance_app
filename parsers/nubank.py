import fitz
import re


def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=20):
    if dia >= inicio_ciclo:
        mes = mes_fatura - 1
    else:
        mes = mes_fatura
    if mes <= 0:
        mes = 12
        ano = ano_fatura - 1
    else:
        ano = ano_fatura
    return f"{dia:02d}/{mes:02d}"


def extrair_linhas_por_coordenada(page, tolerancia=1.0):
    """
    Extrai spans via get_text("dict") e reconstrói linhas agrupando por
    range Y acumulado. O '01 FEV' tem top 0.4px maior que os demais spans
    da mesma linha — por isso usamos y_max + tolerancia em vez de bucketing.
    """
    data = page.get_text("dict")
    spans = []

    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                texto = span["text"].strip()
                if not texto:
                    continue
                spans.append({
                    "text": texto,
                    "x0": span["bbox"][0],
                    "top": span["bbox"][1]
                })

    if not spans:
        return []

    spans.sort(key=lambda s: s["top"])

    linhas = []
    linha_atual = [spans[0]]
    y_max = spans[0]["top"]

    for span in spans[1:]:
        if span["top"] <= y_max + tolerancia:
            linha_atual.append(span)
            y_max = max(y_max, span["top"])
        else:
            linha_atual.sort(key=lambda s: s["x0"])
            linhas.append(" ".join(s["text"] for s in linha_atual))
            linha_atual = [span]
            y_max = span["top"]

    if linha_atual:
        linha_atual.sort(key=lambda s: s["x0"])
        linhas.append(" ".join(s["text"] for s in linha_atual))

    return linhas


def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    transactions = []
    meses_abreviados = {
        'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
        'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12
    }

    try:
        doc = fitz.open(pdf_path)
        all_lines = []
        for page in doc:
            all_lines.extend(extrair_linhas_por_coordenada(page))

        text_all = "\n".join(all_lines)

        trans_pos = text_all.find("TRANSAÇÕES DE")
        if trans_pos < 0:
            return []

        fim_pos = text_all.find("Em cumprimento", trans_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)

        text_section = text_all[trans_pos:fim_pos]

        re_pos = re.compile(r'^(\d{2})\s+(\w{3})\s+(.+?)\s+R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})$')
        re_neg = re.compile(r'^(\d{2})\s+(\w{3})\s+(.+?)\s+\u2212R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})$')

        for line in text_section.split("\n"):
            line = line.strip()
            if not line:
                continue

            match_pos = re_pos.search(line)
            match_neg = re_neg.search(line)
            match = match_pos or match_neg

            if not match:
                continue

            dia_str, mes_str, desc, value_str = match.groups()

            if not meses_abreviados.get(mes_str.upper()):
                continue

            if desc.lower().startswith("pagamento em"):
                continue

            try:
                value = float(value_str.replace(".", "").replace(",", "."))
                if match_neg:
                    value = -value
            except ValueError:
                continue

            transactions.append({
                "data": ajustar_data_compra(int(dia_str), mes_fatura, ano_fatura),
                "descricao": desc.strip().upper(),
                "valor": value,
                "categoria": "Sem categoria"
            })

    except Exception as e:
        print(f"Erro no parser Nubank: {e}")

    return transactions
