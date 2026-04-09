import fitz
import re


def extrair_linhas_por_coordenada(page, tolerancia=1.0):
    """Extrai linhas de texto organizadas por posição Y (vertical)"""
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

    # Agrupa spans por linha (mesmo Y)
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
    """
    Extrai transações da fatura PicPay
    
    Retorna data no formato DD/MM (sem ajuste de ano)
    O ajuste de data completo é feito na página de importação de faturas
    
    Args:
        pdf_path: Caminho do PDF
        mes_fatura: Mês da fatura (1-12)
        ano_fatura: Ano da fatura (YYYY)
    
    Returns:
        Lista de dicionários com transações
        Formato: {
            "data": "DD/MM",
            "descricao": "ESTABELECIMENTO",
            "valor": float,
            "categoria": "Sem categoria"
        }
    """
    transactions = []

    try:
        doc = fitz.open(pdf_path)
        all_lines = []
        
        # Extrai texto de todas as páginas
        for page in doc:
            all_lines.extend(extrair_linhas_por_coordenada(page))

        text_all = "\n".join(all_lines)

        # Procura pela seção de transações
        # Pattern: "Transações Nacionais" ou similar
        trans_pos = text_all.find("Transações Nacionais")
        if trans_pos < 0:
            # Tenta variação
            trans_pos = text_all.find("Transações")
            if trans_pos < 0:
                return []

        # Procura pelo final das transações (próximas seções)
        fim_pos = text_all.find("Picpay Card final", trans_pos)
        if fim_pos < 0:
            fim_pos = text_all.find("Total geral dos lançamentos", trans_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)

        text_section = text_all[trans_pos:fim_pos]

        # Padrão para encontrar transações:
        # Data (DD/MM) | Estabelecimento | Valor (R$)
        # Exemplo: 06/03 UBERPREPAGO 100,00
        
        # Regex adaptado para o formato PicPay:
        # Começa com data (DD/MM), segue estabelecimento, termina com valor
        pattern = re.compile(
            r'(\d{2})/(\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
            re.MULTILINE
        )

        for line in text_section.split("\n"):
            line = line.strip()
            if not line or line.lower() in ['data', 'estabelecimento', 'valor (r$)', 'picpay card']:
                continue

            match = pattern.search(line)
            if not match:
                continue

            dia_str, mes_str, desc, value_str = match.groups()

            # Converte valor (formato brasileiro)
            try:
                valor = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue

            # Retorna data no formato DD/MM
            # O ajuste de ano e mês será feito no parser_router.normalizar_transacoes()
            data_formatada = f"{dia_str}/{mes_str}"

            transactions.append({
                "data": data_formatada,
                "descricao": desc.strip().upper(),
                "valor": valor,
                "categoria": "Sem categoria"
            })

    except Exception as e:
        print(f"Erro no parser PicPay: {e}")

    return transactions
