import json
import os
import re
import unicodedata
import difflib

BASE_DIR = os.path.dirname(__file__)
CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")

def normalize_text(text):
    if not text: return ""
    text = text.upper()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")

def clean_description(desc):
    """
    Versão simplificada: apenas normaliza para maiúsculas e remove espaços extras
    sem remover números ou trechos da descrição.
    """
    if not desc: return ""
    # Apenas garante que está em Caps e sem espaços duplos
    desc = normalize_text(desc)
    desc = " ".join(desc.split())
    return desc.upper()

def load_categories():
    if not os.path.exists(CATEGORIES_FILE):
        return {}
    try:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_categories(rules):
    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

def add_rule(description, category):
    rules = load_categories()
    # Usamos a descrição limpa como chave para garantir consistência
    rules[description] = category
    save_categories(rules)

def find_category(description, rules=None):
    if rules is None:
        rules = load_categories()
        
    desc_to_check = description.upper().strip()
    
    # 1. ORDENAÇÃO É A CHAVE: 
    # Ordenamos as regras pelas maiores chaves primeiro.
    # Assim, "*CARREFOUR DROGARIA*" (18 chars) será testada ANTES de "*CARREFOUR*" (9 chars).
    sorted_rules = sorted(rules.items(), key=lambda x: len(x[0].replace("*", "")), reverse=True)
    
    # --- PASSO 1: Match de Texto Contido (Prioridade Máxima) ---
    # Se "CARREFOUR DROGARIA" estiver na descrição, ele para aqui e não olha o resto.
    for keyword, category in sorted_rules:
        search_term = keyword.replace("*", "").strip().upper()
        if search_term in desc_to_check:
            return category

    # --- PASSO 2: Similaridade (Fuzzy Match) para casos como o da LIVELO ---
    # Se não houve match exato de nenhum trecho, procuramos o que é mais parecido.
    melhor_match = None
    maior_score = 0
    limite = 0.8  # 80% de similaridade
    
    for keyword, category in sorted_rules:
        search_term = keyword.replace("*", "").strip().upper()
        
        # O ratio do difflib lida bem com "Clube Live 07" vs "Clube Live 08"
        score = difflib.SequenceMatcher(None, search_term, desc_to_check).ratio()
        
        if score > maior_score and score >= limite:
            maior_score = score
            melhor_match = category
            
    if melhor_match:
        return melhor_match
            
    return "Sem categoria"