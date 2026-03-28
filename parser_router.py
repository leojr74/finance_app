
import datetime
import logging
import bank_detector
from categorizer import load_categories, find_category

from parsers import (
    bb,
    bradescard,
    bradesco,
    ca,
    caixa,
    itau,
    mercado_pago,
    nubank,
    santander
)



PARSERS = {
    "bb": bb.extract_transactions,
    "bradescard": bradescard.extract_transactions,
    "bradesco": bradesco.extract_transactions,
    "ca": ca.extract_transactions,
    "caixa": caixa.extract_transactions,
    "itau": itau.extract_transactions,
    "mercado_pago": mercado_pago.extract_transactions,
    "nubank": nubank.extract_transactions,
    "santander": santander.extract_transactions,
}


def reconstruir_data(data_raw, data_inicio, data_fim, descricao=""):
    try:
        # 1. Pega o que o banco disse (Ex: "23/02")
        dia, mes_pdf = map(int, data_raw.split("/"))
    except:
        return None

    # --- TESTE DE ANO ---
    
    # Tentativa A: Assumir que é o ano do início da fatura
    try:
        data_teste_a = datetime.date(data_inicio.year, mes_pdf, dia)
        if data_inicio <= data_teste_a <= data_fim:
            return data_teste_a
    except ValueError:
        pass

    # Tentativa B: Assumir que é o ano do fim da fatura (Importante para virada de ano)
    try:
        data_teste_b = datetime.date(data_fim.year, mes_pdf, dia)
        if data_inicio <= data_teste_b <= data_fim:
            return data_teste_b
    except ValueError:
        pass

    # --- CASO DE SEGURANÇA (O seu erro específico) ---
    # Se o dia/mês do PDF (Ex: 23/03) NÃO cabe no período (19/02 a 18/03)
    # mas o dia (23) sugere que deveria estar no mês de início (Fevereiro):
    
    if data_inicio.day <= dia <= 31:
        # Forçamos para o mês de início
        try:
            return datetime.date(data_inicio.year, data_inicio.month, dia)
        except: 
            return data_inicio
            
    # Se o dia for pequeno (Ex: dia 05), forçamos para o mês de fim
    try:
        return datetime.date(data_fim.year, data_fim.month, dia)
    except:
        return data_fim


def normalizar_transacoes(raw_transactions, data_inicio, data_fim):

    categorias = load_categories()
    normalizadas = []

    for t in raw_transactions:

        desc = t.get("descricao", "SEM DESCRICAO")
        valor = t.get("valor", 0.0)
        data_raw = t.get("data")

        if not data_raw or not desc:
            continue

        try:
            valor = float(valor)
        except:
            continue

        data_final = reconstruir_data(data_raw, data_inicio, data_fim, desc)

        
        if not data_final:
            continue

        categoria_inteligente = find_category(desc, categorias)
        
        if not categoria_inteligente:
            categoria_final = "Sem categoria"
        else:
            categoria_final = categoria_inteligente

        normalizadas.append({
            "data": data_final.strftime("%d/%m/%Y"),
            "descricao": desc,
            "valor": valor,
            "categoria": categoria_final # Agora garantimos que vem do seu JSON
        })

    return normalizadas


def extract_transactions_auto(pdf_path, data_inicio, data_fim):

    bank = bank_detector.detect_bank(pdf_path)
    
    if not bank:
        raise ValueError("Banco não detectado")

    parser = PARSERS.get(bank)

    if not parser:
        raise ValueError(f"Parser não encontrado para banco: {bank}")
    
    mes_fatura = data_fim.month
    ano_fatura = data_fim.year

    raw_transactions = parser(pdf_path, mes_fatura, ano_fatura)
    
    transactions = normalizar_transacoes(
        raw_transactions,
        data_inicio,
        data_fim
    )

    total = sum(t["valor"] for t in transactions)

    return {
        "bank": bank,
        "transactions": transactions,
        "count": len(transactions),
        "total": total
    }
