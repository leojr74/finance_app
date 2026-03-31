import fitz
import re

def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser para Caixa - Corrigido para sinal de Débito/Crédito
    """
    transactions = []
    try:
        text_all = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                # Usamos extração em blocos para manter a relação linha/valor
                page_text = page.get_text("text") or ""
                text_all += page_text + "\n"
        
        # Regex melhorada para capturar o indicador D/C mesmo que haja espaços
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+([\s\S]+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*([DC]?)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_all):
            date = match.group(1)
            # Limpa quebras de linha no meio da descrição
            desc = match.group(2).replace('\n', ' ').strip().upper() 
            value_str = match.group(3)
            dc = match.group(4).upper() if match.group(4) else "D"
            
            # Filtros de ruído
            if not desc or len(desc) < 2:
                continue
            
            ignore_patterns = [
                'TOTAL DA FATURA ANTERIOR', 'OBRIGADO PELO PAGAMENTO',
                'TOTAL', 'DATA', 'VALOR', 'A.A', 'A.M', 'SALDO ANTERIOR'
            ]
            
            if any(p in desc for p in ignore_patterns):
                continue
            
            try:
                # Conversão numérica (valor absoluto inicial)
                value = float(value_str.replace(".", "").replace(",", "."))
                
                # LÓGICA DE SINAL CAIXA:
                # D (Débito) = Gasto real -> Mantemos POSITIVO para o sistema
                # C (Crédito) = Estorno/Pagamento -> Tornamos NEGATIVO para abater
                if dc == "C":
                    value = -value
                else:
                    # Garantimos que débito seja positivo
                    value = abs(value)
                    
            except ValueError:
                continue
            
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria"
            })
    
    except Exception as e:
        print(f"Erro no parser Caixa: {e}")
    
    return transactions