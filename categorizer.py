
import json
import os
import re
import unicodedata
import difflib

# =========================================================
# CONFIG FILES
# =========================================================

BASE_DIR = os.path.dirname(__file__)

CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")
ALIASES_FILE = os.path.join(BASE_DIR, "description_aliases.json")


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):
    """Remove acentos e coloca em maiúsculo"""
    if not text:
        return ""

    text = text.upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    return text


def normalize_category(name):
    """Capitaliza categoria"""
    if not name:
        return ""
    return name.strip().capitalize()


# =========================================================
# DESCRIPTION CLEANING
# =========================================================

def clean_description(desc):
    """
    Normaliza descrição removendo ruídos comuns.
    """
    if not desc:
        return ""

    desc = normalize_text(desc)

    # remove datas
    desc = re.sub(r'\d{2}/\d{2}', '', desc)

    # remove múltiplos espaços
    desc = re.sub(r'\s+', ' ', desc)

    return desc.strip()


# =========================================================
# KEYWORD EXTRACTION (melhoria importante)
# =========================================================

def extract_keyword(description):
    """
    Extrai palavra-chave principal da descrição.
    Exemplo:
    'Uber - NuPay' -> UBER
    'Pag*Steam Parcela 2/12' -> STEAM
    """

    desc = clean_description(description)

    # remove parcelamento
    desc = re.sub(r'PARCELA \d+/\d+', '', desc)

    words = desc.split()

    if not words:
        return desc

    # ignora prefixos comuns
    ignore = {"PAG", "MP", "COMPRA", "DEBITO"}

    for w in words:
        if w not in ignore and len(w) > 2:
            return w

    return words[0]


# =========================================================
# CATEGORY RULES
# =========================================================

def load_categories():
    """Carrega rules"""
    if not os.path.exists(CATEGORIES_FILE):
        return {}

    try:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_categories(categories):
    """Salva rules"""
    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)


# =========================================================
# ADD RULE
# =========================================================

def add_rule(keyword, category):

    rules = load_categories()

    keyword = normalize_text(keyword)
    category = normalize_category(category)

    if not keyword:
        return

    rules[keyword] = category

    save_categories(rules)


# =========================================================
# SAVE RULE (compatível com interface)
# =========================================================

def save_rule(description, category):
    """
    Aprende regra automaticamente a partir da descrição.
    """

    if not description or not category:
        return

    keyword = extract_keyword(description)

    if keyword:
        add_rule(keyword, category)


# =========================================================
# FIND CATEGORY
# =========================================================

def find_category(description, rules, similarity_threshold=0.75):

    if not description or not rules:
        return None

    desc = clean_description(description)

    best_match = None
    best_score = 0

    # -----------------------------
    # 1 substring match
    # -----------------------------
    for keyword, category in rules.items():

        keyword_clean = normalize_text(keyword)

        if keyword_clean and keyword_clean in desc:
            return category

    # -----------------------------
    # 2 wildcard match
    # -----------------------------
    for keyword, category in rules.items():

        if "*" not in keyword:
            continue

        pattern = normalize_text(keyword.replace("*", ""))

        if pattern and pattern in desc:
            return category

    # -----------------------------
    # 3 similarity
    # -----------------------------
    for keyword, category in rules.items():

        keyword_clean = normalize_text(keyword)

        score = difflib.SequenceMatcher(None, keyword_clean, desc).ratio()

        if score > best_score:
            best_score = score
            best_match = category

    if best_score >= similarity_threshold:
        return best_match

    return None


# =========================================================
# ALIASES
# =========================================================

def load_aliases():

    if not os.path.exists(ALIASES_FILE):
        return {}

    try:
        with open(ALIASES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_aliases(aliases):

    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, indent=2, ensure_ascii=False)


def add_alias(old_description, new_description):

    aliases = load_aliases()

    old_desc = normalize_text(old_description)
    new_desc = new_description.strip()

    if old_desc:
        aliases[old_desc] = new_desc
        save_aliases(aliases)


def apply_aliases(description):

    if not description:
        return description

    aliases = load_aliases()

    desc_normalized = normalize_text(description)

    if desc_normalized in aliases:
        return aliases[desc_normalized]

    return description
