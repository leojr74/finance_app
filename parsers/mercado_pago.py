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
    Parser para Mercado Pago - extrai transações parceladas do cartão
    
    Estrutura do PDF:
    - Movimentações na fatura (seção com histórico)
    - Padrão: DD/MM + DESCRIÇÃO + VALOR (sem negativo, só compras)
    
    Ignora:
    - "Pagamento da fatura" (já contabilizado)
    - "Consumos de" (linha totalizadora)
    
    Exemplo:
    03/10 MERCADOLIVRE*EBAZARCOMBRL Parcela 5 de 21 R$ 245,21
    09/01 MERCADOLIVRE*PLANETADOBEB Parcela 2 de 21 R$ 61,94
    """
    transactions = []
    try:
        text_all = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_all += page_text + "\n"
        
        pass  # removed debug print
        print(f"MERCADO PAGO - DEBUG: Operações extraídas")
        print(f"{'='*120}")
        
        # Procurar segunda seção "Movimentações na fatura" (após "Cartão Visa")
        cartao_pos = text_all.find("Cartão Visa")
        if cartao_pos < 0:
            print("❌ Seção 'Cartão Visa' não encontrada")
            return []
        
        # Agora procurar "Movimentações" APÓS "Cartão Visa"
        mov_pos = text_all.find("Movimentações", cartao_pos)
        if mov_pos < 0:
            print("❌ Segunda seção 'Movimentações' não encontrada")
            return []
        
        # Procurar fim da seção (próxima seção importante)
        fim_pos = text_all.find("Total R$", mov_pos)
        if fim_pos < 0:
            fim_pos = len(text_all)
        
        text_section = text_all[mov_pos:fim_pos]
        
        seen = {}
        extracted_count = 0
        
        # Padrão: DD/MM + descrição + "R$" + valor
        # Mercado Pago tem "Cartão Visa" como seção separadora
        pattern = re.compile(
            r'(\d{2}/\d{2})\s+(.+?)\s+R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})',
            re.MULTILINE
        )
        
        for match in pattern.finditer(text_section):
            date = match.group(1)
            desc = match.group(2).strip()
            value_str = match.group(3)
            
            # Filtros básicos
            if not desc or len(desc) < 1:
                continue
            if not re.search(r'[A-Za-z0-9]', desc):
                continue
            
            # Ignorar linhas que são títulos ou totalizadores
            if any(x in desc.upper() for x in ['CONSUMOS DE', 'PAGAMENTO DA FATURA', 'DATA MOVIMENTAÇÕES', 'CARTÃO VISA']):
                continue
            
            # Ignorar descrições muito longas (marca dados misturados)
            if len(desc) > 100:
                continue
            
            try:
                value = float(value_str.replace(".", "").replace(",", "."))
            except ValueError:
                continue
            
            # Extrair dia para ajuste
            dia = int(date.split("/")[0])
            data_corrigida = date
            
            desc_normalized = ' '.join(desc.split())
            key = (date, desc_normalized, value)
            
            if key not in seen:
                seen[key] = True
                extracted_count += 1
                pass  # removed transaction print
                
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
        
        pass  # removed debug print
        pass  # removed total print
        print(f"{'='*120}\n")
    
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions
