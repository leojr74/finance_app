import pdfplumber
import re
from categorizer import load_categories, find_category


def ajustar_data_compra(dia, mes_fatura, ano_fatura, inicio_ciclo=13):
    """Ajustar data da compra ao mês da fatura"""
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
    """
    Parser para Mercado Pago - Extração limpa e em MAIÚSCULAS
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        # Localiza a seção específica do cartão para evitar capturar pagamentos da conta corrente
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
        
        # Padrão: DD/MM + descrição + sinal opcional + R$ + valor
        # O sinal "-" pode vir antes do "R$" em caso de estornos
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+(-?)\s*R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip().upper() # Padronização para MAIÚSCULAS
            sinal = match.group(3)
            value_str = match.group(4)
            
            # Filtros de ruído (Títulos e totalizadores do Mercado Pago)
            if not desc or len(desc) < 2:
                continue
                
            if any(x in desc for x in ['CONSUMOS DE', 'PAGAMENTO DA FATURA', 'DATA MOVIMENTAÇÕES', 'CARTÃO VISA']):
                continue
            
            try:
                # Conversão numérica
                value = float(value_str.replace(".", "").replace(",", "."))
                if sinal == "-":
                    value = -value
            except ValueError:
                continue
            
            # Monta o dicionário simplificado para o Router
            transactions.append({
                "data": date,
                "descricao": desc,
                "valor": value,
                "categoria": "Sem categoria" # O Router aplicará o seu JSON centralizado
            })
    
    except Exception as e:
        print(f"Erro no parser Mercado Pago: {e}")
    
    return transactions
