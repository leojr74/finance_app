import fitz
import re

def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser C&A (C&A Pay) - Versão Robusta com PyMuPDF (fitz)
    """
    transactions = []

    try:
        text_all = ""
        # Usamos fitz para abrir o PDF
        with fitz.open(pdf_path) as doc:
            for page in doc:
                # O parâmetro "text" garante uma extração mais linear
                page_text = page.get_text("text") or ""
                text_all += page_text + "\n"

        # Localiza a seção de transações
        demo_pos = text_all.find("Demonstrativo")
        if demo_pos < 0:
            print("C&A: Seção Demonstrativo não encontrada.")
            return []

        # Define o fim da seção de leitura
        fim_pos = text_all.find("Apertou?", demo_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)

        text_section = text_all[demo_pos:fim_pos]

        # Regex Ajustada: 
        # 1. Permite espaços ou quebras de linha após a data
        # 2. Melhora a captura da descrição
        pattern = re.compile(
            r'(\d{2}/\d{2}(?:/\d{4})?)\s+([\s\S]+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)',
            re.MULTILINE
        )

        for match in pattern.finditer(text_section):
            date_raw = match.group(1)
            # Limpamos possíveis quebras de linha no meio da descrição
            desc = match.group(2).replace('\n', ' ').strip().upper()
            value_str = match.group(3)
            has_minus = match.group(4)

            # Filtros de ruído
            if not desc or len(desc) < 2:
                continue
            
            if any(x in desc for x in [
                'TOTAL', 'FATURA ANTERIOR', 'LIMITE', 
                'CRÉDITO', 'DÉBITO', 'PAGAMENTO', 'SALDO'
            ]):
                continue

            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                if has_minus == "-":
                    value = -value
            except ValueError:
                continue

            # Normalização da data para o formato DD/MM (O Router espera isso)
            # Se vier DD/MM/AAAA, cortamos o ano.
            parts = date_raw.split("/")
            data_normalizada = f"{parts[0]}/{parts[1]}"

            transactions.append({
                "data": data_normalizada, # Chave essencial para o parser_router
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" 
            })

    except Exception as e:
        print(f"Erro crítico no parser C&A: {e}")

    return transactions