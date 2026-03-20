
import pdfplumber
import re


def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser C&A (C&A Pay) - Extração simplificada (Limpa)
    """
    transactions = []

    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"

        # Localiza a seção de transações
        demo_pos = text_all.find("Demonstrativo")
        if demo_pos < 0:
            return []

        # Define o fim da seção de leitura
        fim_pos = text_all.find("Apertou?", demo_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)

        text_section = text_all[demo_pos:fim_pos]

        # Padrão: Data (DD/MM ou DD/MM/AAAA) + Descrição + Valor + Sinal opcional "-"
        pattern = re.compile(
            r'(\d{2}/\d{2}(?:/\d{4})?)\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)',
            re.MULTILINE
        )

        for match in pattern.finditer(text_section):
            date_str = match.group(1)
            desc = match.group(2).strip().upper()
            value_str = match.group(3)
            has_minus = match.group(4)

            # Filtros de ruído
            desc_upper = desc.upper()
            if not desc or len(desc) < 2:
                continue
            
            # Ignora linhas de sistema e totais
            if any(x in desc_upper for x in [
                'TOTAL', 'FATURA ANTERIOR', 'LIMITE', 
                'CRÉDITO', 'DÉBITO', 'PAGAMENTO'
            ]):
                continue

            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                if has_minus == "-":
                    value = -value
            except ValueError:
                continue

            # Normalização da data para o formato DD/MM esperado pelo Router
            if date_str.count("/") == 2:
                dia, mes, _ = date_str.split("/")
                data_normalizada = f"{dia}/{mes}"
            else:
                data_normalizada = date_str

            # Monta o dicionário com categoria neutra
            transactions.append({
                "data": data_normalizada,
                "descricao": desc.strip(),
                "valor": value,
                "categoria": "Sem categoria" # O Router aplicará o seu JSON
            })

    except Exception as e:
        print(f"Erro no parser C&A: {e}")

    return transactions