import fitz
import re

def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser para Mercado Pago - Versão Robusta com PyMuPDF (fitz)
    """
    transactions = []
    try:
        text_all = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                # O modo "text" ajuda a manter a ordem visual das colunas
                page_text = page.get_text("text") or ""
                text_all += page_text + "\n"
        
        # 1. Localização da seção específica do cartão
        cartao_pos = text_all.find("Cartão Visa")
        if cartao_pos < 0:
            return []
        
        mov_pos = text_all.find("Movimentações", cartao_pos)
        if mov_pos < 0:
            return []
        
        fim_pos = text_all.find("Total R$", mov_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)
        
        text_section = text_all[mov_pos:fim_pos]
        
        # 2. Regex Flexível:
        # (\d{2}/\d{2}) -> Data
        # ([\s\S]+?)   -> Descrição (aceita múltiplas linhas/espaços)
        # (-?\s*R\$)   -> Sinal opcional + R$
        # (\d{1,3}...) -> Valor
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+([\s\S]+?)\s+(-?\s*R\$\s+)(\d{1,3}(?:\.\d{3})*,\d{2})',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            # Limpa quebras de linha que o fitz insere no meio de nomes longos
            desc = match.group(2).replace('\n', ' ').strip().upper() 
            sinal_str = match.group(3)
            value_str = match.group(4)
            
            # Filtros de ruído (Títulos e totalizadores)
            if not desc or len(desc) < 2:
                continue
                
            blacklist = ['CONSUMOS DE', 'PAGAMENTO DA FATURA', 'DATA MOVIMENTAÇÕES', 'CARTÃO VISA', 'TOTAL']
            if any(x in desc for x in blacklist):
                continue
            
            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                
                # No Mercado Pago, o "-" costuma vir colado ou antes do R$
                if "-" in sinal_str:
                    value = -value
            except ValueError:
                continue
            
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria"
            })
    
    except Exception as e:
        print(f"Erro no parser Mercado Pago: {e}")
    
    return transactions