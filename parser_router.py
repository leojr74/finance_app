
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

logging.basicConfig(
    filename="parser_debug.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
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
    """
    Reconstrói data garantindo que fique dentro do período da fatura.
    Corrige também casos de parcelas onde o banco mostra a data da compra original.
    """
    try:
        parts = data_raw.split("/")
        dia = int(parts[0])
        mes = int(parts[1])
    except:
        return None

    anos = [data_inicio.year, data_fim.year]

    for ano in anos:
        try:
            data = datetime.date(ano, mes, dia)

            if data_inicio <= data <= data_fim:
                return data
        except:
            pass

    # tratamento especial para parcelas
    if "PARCELA" in descricao.upper():
        try:
            return datetime.date(data_fim.year, data_fim.month, dia)
        except:
            pass

    try:
        return datetime.date(data_fim.year, mes, dia)
    except:
        return None


def normalizar_transacoes(transactions, data_inicio, data_fim):

    categorias = load_categories()
    normalizadas = []

    for t in transactions:

        data_raw = t.get("data")
        desc = (t.get("descricao") or "").strip()
        valor = t.get("valor")

        if not data_raw or not desc:
            continue

        try:
            valor = float(valor)
        except:
            continue

        data_final = reconstruir_data(data_raw, data_inicio, data_fim, desc)

        if not data_final:
            continue

        categoria = t.get("categoria")

        if not categoria or categoria == "Sem categoria":
            categoria = find_category(desc, categorias) or "Sem categoria"

        normalizadas.append({
            "data": data_final.strftime("%d/%m/%Y"),
            "descricao": desc,
            "valor": valor,
            "categoria": categoria
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
