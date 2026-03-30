import json
import os
import unicodedata
import difflib
# Importamos as funções que criamos para o database.py
from database import carregar_regras_db, salvar_regra_db

BASE_DIR = os.path.dirname(__file__)
CATEGORIES_FILE = os.path.join(BASE_DIR, "categories.json")


def clean_description(desc):
    """Garante que a descrição está em Caps, sem acentos e sem espaços extras."""
    if not desc: return ""
    desc = normalize_text(desc)
    desc = " ".join(desc.split())
    return desc.upper()

def get_all_rules(user_id):
    """Retorna o dicionário completo de regras (Globais + Usuário)."""
    regras_usuario = carregar_regras_db(user_id)
    regras_globais = load_categories_json()
    # Une as duas, com as do usuário mandando em caso de duplicata
    return {**regras_globais, **regras_usuario}

def normalize_text(text):
    if not text: return ""
    text = text.upper()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")

def load_categories_json():
    """Lê as regras globais do arquivo JSON (Backup)."""
    if not os.path.exists(CATEGORIES_FILE):
        return {}
    try:
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def find_category(description, user_id):
    """
    Busca a categoria com hierarquia:
    1. Regras personalizadas do usuário no Banco de Dados.
    2. Regras globais no arquivo JSON.
    """
    desc_to_check = description.upper().strip()
    
    # --- PASSO 0: Obter e Unificar Regras ---
    # Carregamos as do banco (específicas do user) e as do JSON (gerais)
    regras_usuario = carregar_regras_db(user_id)
    regras_globais = load_categories_json()
    
    # Unificamos priorizando as do usuário em caso de conflito
    all_rules = {**regras_globais, **regras_usuario}
    
    # Ordenamos por tamanho da chave (maiores primeiro para maior precisão)
    sorted_rules = sorted(all_rules.items(), key=lambda x: len(x[0].replace("*", "")), reverse=True)
    
    # --- PASSO 1: Match de Texto Contido (Prioridade Máxima) ---
    for keyword, category in sorted_rules:
        search_term = keyword.replace("*", "").strip().upper()
        if search_term in desc_to_check:
            return category

    # --- PASSO 2: Similaridade (Fuzzy Match) ---
    melhor_match = None
    maior_score = 0
    limite = 0.8 
    
    for keyword, category in sorted_rules:
        search_term = keyword.replace("*", "").strip().upper()
        score = difflib.SequenceMatcher(None, search_term, desc_to_check).ratio()
        
        if score > maior_score and score >= limite:
            maior_score = score
            melhor_match = category
            
    if melhor_match:
        return melhor_match
            
    return "Sem categoria"

def add_rule(description, category, user_id):
    """
    Agora salva a regra no BANCO DE DADOS vinculada ao usuário,
    em vez de alterar o arquivo JSON global.
    """
    # Usamos a função de upsert que criamos no database.py
    return salvar_regra_db(description.upper(), category, user_id)