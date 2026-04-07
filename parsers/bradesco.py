import fitz
import re


def extract_transactions(pdf_path, mes_fatura, ano_fatura):
    """
    Parser para Bradesco - Layout novo (colunas: Data, Histórico, Cidade, US$, Cotação, R$).
    O PyMuPDF extrai cada coluna em linha separada, então processamos linha a linha.
    Estrutura por transação:
        DD/MM                  ← linha com a data
        DESCRIÇÃO              ← próxima linha de texto
        CIDADE (opcional)      ← ignorada
        VALOR [-]              ← linha com o valor
    """
    transactions = []

    IGNORAR = [
        'PAG BOLETO', 'PAGAMENTO', 'JOSE LEONARDO', 'TOTAL',
        'PROXIMO', 'DEMAIS', 'HISTORICO', 'COTACAO', 'LANCAMENTOS',
        'DATA ', 'CIDADE', 'US$', 'DO DOLAR', 'CARTAO'
    ]

    data_re = re.compile(r'^(\d{2}/\d{2})\s*(.*)')
    valor_re = re.compile(r'^(\d{1,3}(?:\.\d{3})*,\d{2})\s*(-?)\s*$')

    try:
        text_all = ""
        for page in fitz.open(pdf_path):
            text_all += (page.get_text() or "") + "\n"

        start = text_all.find("Lançamentos")
        if start == -1:
            return []

        end = text_all.find("Total para", start)
        if end == -1:
            end = text_all.find("Total da fatura", start)
        if end == -1:
            end = len(text_all)

        linhas = text_all[start:end].splitlines()

        pendente_data = None
        pendente_desc = None

        for linha in linhas:
            linha = linha.strip()

            m_data = data_re.match(linha)
            if m_data:
                pendente_data = m_data.group(1)
                resto = m_data.group(2).strip().upper()
                pendente_desc = resto if resto and not any(x in resto for x in IGNORAR) else None
                continue

            if pendente_data:
                m_valor = valor_re.match(linha)
                if m_valor:
                    valor_str = m_valor.group(1)
                    sinal = m_valor.group(2)
                    valor = float(valor_str.replace(".", "").replace(",", "."))
                    if sinal == "-":
                        valor = -valor

                    if pendente_desc and len(pendente_desc) >= 3:
                        if not any(x in pendente_desc for x in IGNORAR):
                            transactions.append({
                                "data": pendente_data,
                                "descricao": pendente_desc,
                                "valor": valor,
                                "categoria": "Sem categoria"
                            })

                    pendente_data = None
                    pendente_desc = None
                    continue

                # Linha de texto intermediária: primeira = descrição, demais = cidade (ignora)
                linha_upper = linha.upper()
                if linha and not any(x in linha_upper for x in IGNORAR):
                    if pendente_desc is None:
                        pendente_desc = linha_upper

    except Exception as e:
        print(f"Erro no parser Bradesco: {e}")

    return transactions
