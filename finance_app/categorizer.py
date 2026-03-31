import unicodedata
import difflib

def normalize_text(text):
    if not text: return ""
    text = text.upper()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")

def clean_description(desc):
    if not desc: return ""
    desc = normalize_text(desc)
    desc = " ".join(desc.split())
    return desc.upper()

def find_category(description, rules):
    """
    Agora recebe obrigatoriamente o dicionário 'rules' vindo do banco de dados.
    """
    if not rules:
        return "Sem categoria"
        
    desc_to_check = clean_description(description)
    
    # Ordena as regras pelas maiores chaves para evitar matches parciais errados
    sorted_rules = sorted(rules.items(), key=lambda x: len(x[0].replace("*", "")), reverse=True)
    
    # 1. Match de Texto Contido
    for keyword, category in sorted_rules:
        search_term = clean_description(keyword.replace("*", ""))
        if search_term in desc_to_check:
            return category

    # 2. Similaridade (Fuzzy Match)
    melhor_match = None
    maior_score = 0
    limite = 0.8 
    
    for keyword, category in sorted_rules:
        search_term = clean_description(keyword.replace("*", ""))
        score = difflib.SequenceMatcher(None, search_term, desc_to_check).ratio()
        if score > maior_score:
            maior_score = score
            melhor_match = category

    if maior_score >= limite:
        return melhor_match

    return "Sem categoria"