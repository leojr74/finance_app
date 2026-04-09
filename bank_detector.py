import fitz
import re


def detect_bank(pdf_path):
    """
    Detecta qual banco é o PDF baseado em padrões de texto
    
    Returns:
        str: Nome do banco ('itau', 'santander', 'bb', 'caixa', 'bradescard', 'cac', etc)
        None: Se não conseguir detectar
    """
    
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            page_text = page.get_text() or ""
            text_all += page_text + "\n"
    except Exception as e:
        return None
    
    # Converter para maiúsculas para comparação case-insensitive
    text_upper = text_all.upper()
    
    # MÉTODO 1: Procurar pelo NOME EXATO do banco (mais confiável)
    bank_names = {
        'ca': [
            'C&A PAY',
            'C&A CARTÕES',
            'C&A MODAS',
        ],
        'santander': [
            'BANCO SANTANDER',
            'SANTANDER BRASIL',
        ],
        'itau': [
            'BANCO ITAÚ',
            'ITAÚ UNIBANCO',
        ],
        'caixa': [
            'CAIXA ECONÔMICA',
            'CARTÕES CAIXA',
            'CAIXA EFATURA',
        ],
        'bb': [
            'BANCO DO BRASIL',
            'BB CARTÕES',
            'SMILES INFINITE VISA',  # Cartão BB
        ],
        'bradescard': [
            'BANCO BRADESCARD',
            'BRADESCARD',
            'AMAZON MASTERCARD PLATINUM',  # Cartão Bradescard
        ],
        'bradesco': [
            'BRADESCO',
            'Bradesco',  # Cartão Bradesco
        ],
        'mercado_pago': [
            'MERCADO PAGO',
            'mercado pago',
        ],
        'nubank': [
            'NUBANK',
            'Nu Pagamentos',
        ],
        'picpay': [
            'PICPAY',
            'PicPay Bank',
            'PicPay Mastercard',
        ],
        
    }
    
    # Procurar por nome de banco - tem prioridade máxima
    for bank, names in bank_names.items():
        for name in names:
            if name in text_upper:
                return bank
    
    # MÉTODO 2: Se não encontrar nome, usar padrões secundários
    bank_patterns = {
        'santander': [
            r'UNIQUE VISA',
            r'Detalhamento da Fatura',
        ],
        'itau': [
            r'Lançamentos: compras e saques',
            r'Compras parceladas - próximas faturas',
        ],
        'bb': [
            r'BB CARTÕES',
        ],
        'caixa': [
            r'CAIXA EFATURA',
        ],
        'bradescard': [
            r'BRADESCARD',
        ],
        'mercado_pago': [
            r'MERCADO PAGO',
            r'Movimentações na fatura',
        ],
        'nubank': [
            r'NUBANK',
            r'TRANSAÇÕES DE',
        ],
        'picpay': [
            r'PICPAY',
            r'Transações Nacionais',
        ],
    }
    
    scores = {}
    for bank, patterns in bank_patterns.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text_upper):
                score += 1
        if score > 0:
            scores[bank] = score
    
    if scores:
        detected_bank = max(scores, key=scores.get)
        return detected_bank
    
    return None


def get_total_amount(pdf_path):
    """
    Tenta extrair o valor total da fatura do PDF
    
    Returns:
        float: Valor total da fatura, ou None se não encontrar
    """
    
    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            page_text = page.get_text() or ""
            text_all += page_text + "\n"
        text_search = text_all[:1200]

    except Exception as e:
        return None
    
    # Padrões para encontrar valor total (ORDEM IMPORTA!)
    patterns = [
        # Mercado Pago
        r'Total a pagar[^\n]*\nR\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        # Bradescard / Bradesco
        r'Total da fatura[^\d]*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        # Itaú
        r'[=]?\s*Total desta fatura\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
        # Santander
        r'Total\s+a\s+Pagar[^\d]*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',

        r'Total desta fatura[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Lançamentos atuais[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Valor total:[^\d]*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',

        # Nubank
        r'Total a pagar\s+R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+Pagamento mínimo',

        # Mercado Pago
        r'Total a pagar\s+R\$\s+(\d{1,3}(?:\.\d{3})*,\d{2})',
        # Banco do Brasil
        r'Total\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Total da fatura[^\d]*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Total desta fatura[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Total da fatura[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Lançamentos atuais[:\s]+R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        # Caixa
        r'VALOR\s+TOTAL\s+DESTA\s+FATURA[\s\S]*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_search, re.IGNORECASE | re.DOTALL)
        if match:
            value_str = match.group(1)
            value = float(value_str.replace('.', '').replace(',', '.'))
            return value
    
    return None
