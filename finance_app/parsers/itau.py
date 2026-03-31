import fitz
import re


def extrair_linhas_por_coordenada(page, tolerancia=1.0):
    """
    Extrai spans via get_text("dict") e reconstrói linhas agrupando por Y.
    O Itaú tem layout de duas colunas — spans da mesma linha têm top idêntico.
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

    try:
        doc = fitz.open(pdf_path)
        all_lines = []
        for page in doc:
            all_lines.extend(extrair_linhas_por_coordenada(page))

        text_all = "\n".join(all_lines)

        lancamentos_pos = text_all.find("Lançamentos: compras e saques")
        if lancamentos_pos < 0:
            return []

        compras_parceladas_pos = text_all.find("Compras parceladas - próximas faturas", lancamentos_pos)
        proxima_fatura_pos = text_all.find("Próxima fatura", lancamentos_pos)

        text_section = text_all[lancamentos_pos:]

        pattern = re.compile(r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(?:\s|$)')
        all_matches_raw = list(pattern.finditer(text_section))

        # Filtra metadados: MAIÚSCULAS + ESPAÇO + PONTO + cidade
        all_matches = []
        for match in all_matches_raw:
            desc = match.group(2).strip().upper()
            if re.match(r'^[A-ZÀ-Ÿ\s]+\s\.[A-Za-zÀ-Ÿ\s]+$', desc):
                continue
            all_matches.append(match)

        transaction_index_after_compras = 0
        first_transaction_after_compras_idx = None
        seen = {}

        for match in all_matches:
            date = match.group(1)
            desc = match.group(2).strip().upper()
            value_str = match.group(3)

            if not desc or len(desc) < 2:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue

            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            if desc.endswith("-"):
                value = -value
                desc = desc.rstrip("-").strip()

            # Lógica x+3n para parceladas
            c_parc_rel = compras_parceladas_pos - lancamentos_pos if compras_parceladas_pos >= 0 else -1
            p_fat_rel = proxima_fatura_pos - lancamentos_pos if proxima_fatura_pos >= 0 else -1

            is_between = (
                c_parc_rel >= 0 and p_fat_rel >= 0 and
                match.start() >= c_parc_rel and match.start() < p_fat_rel
            )

            if is_between:
                if first_transaction_after_compras_idx is None:
                    first_transaction_after_compras_idx = transaction_index_after_compras
                idx_rel = transaction_index_after_compras - first_transaction_after_compras_idx
                transaction_index_after_compras += 1
                if idx_rel % 3 != 0:
                    continue

            key = (date, ' '.join(desc.split()), value)
            if key not in seen:
                seen[key] = True
                transactions.append({
                    "data": date,
                    "descricao": desc,
                    "valor": value,
                    "categoria": "Sem categoria"
                })

    except Exception as e:
        print(f"Erro no parser Itaú: {e}")

    return transactions
