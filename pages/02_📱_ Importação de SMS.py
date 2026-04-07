import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime
from ui import apply_global_style
from database import get_engine, carregar_transacoes, carregar_regras_db
from sqlalchemy import text
from categorizer import find_category
from utils.auth import check_login

st.set_page_config(
    page_title="Importação de SMS",
    page_icon="📱",
    layout="wide"
)


usuario_atual = check_login()


apply_global_style()

st.title("📱 Importação de SMS")

# --- INICIALIZAÇÃO DE ESTADOS (O SEGREDO PARA LIMPAR O CAMPO) ---
if "input_counter" not in st.session_state:
    st.session_state.input_counter = 0

if "df_sms_preview" not in st.session_state:
    st.session_state.df_sms_preview = None

# Mapeamento de Bancos
MAPA_SMS = {
    "CAIXA": "CARTÃO CAIXA",
    "ITAU": "CARTÃO ITAÚ",
    "NUBANK": "CARTÃO NUBANK",
    "BRADESCO": "CARTÃO BRADESCO",
    "SANTANDER": "CARTÃO SANTANDER",
    "AMAZON": "CARTÃO AMAZON"
}

# --------------------------------------------------
# Entrada de Dados
# --------------------------------------------------
uploaded_sms = st.file_uploader("Upload do arquivo .txt exportado", type="txt")

# A chave (key) dinâmica para limpar o campo de texto
texto_copiado = st.text_area(
    "Ou cole o texto aqui (Mobile Friendly):", 
    height=150, 
    placeholder="Cole as mensagens aqui...",
    key=f"sms_input_{st.session_state.input_counter}"
)

btn_processar = st.button("🔍 Processar SMS", type="primary", width = 'stretch')

if "info_parcelamento" in st.session_state and st.session_state.info_parcelamento["ativa"]:
    p = st.session_state.info_parcelamento
    st.warning(f"💳 **Compra Parcelada Detectada:** {p['desc']} (Parcela {p['atual']} de {p['total']})")
    
    col1, col2 = st.columns(2)
    if col1.button("➕ Lançar todas as parcelas restantes"):
        novas_parcelas = []
        data_base = datetime.strptime(p['data_origem'], '%Y-%m-%d')
        
        # Loop para criar as parcelas que faltam (da próxima até a última)
        for i in range(1, p['total'] - p['atual'] + 1):
            # Adiciona 1 mês para cada parcela subsequente
            nova_data = (data_base + pd.DateOffset(months=i)).strftime('%Y-%m-%d')
            nova_p = p['atual'] + i
            
            # Gerar novo hash para cada parcela futura
            h_raw = f"{nova_data}{p['valor']}{p['desc']}{nova_p}{p['banco']}{usuario_atual}"
            h = hashlib.md5(h_raw.encode()).hexdigest()
            
            novas_parcelas.append({
                "data": nova_data,
                "data_obj": datetime.strptime(nova_data, '%Y-%m-%d').date(),
                "descricao": f"{p['desc']} ({nova_p}/{p['total']})",
                "valor": p['valor'],
                "banco": p['banco'],
                "hash": h
            })
        
        # Concatena com o que já estava no preview
        st.session_state.df_sms_preview = pd.concat([
            st.session_state.df_sms_preview, 
            pd.DataFrame(novas_parcelas)
        ]).sort_values("data")
        
        st.session_state.info_parcelamento["ativa"] = False
        st.rerun()

    if col2.button("🚫 Apenas esta parcela"):
        st.session_state.info_parcelamento["ativa"] = False
        st.rerun()
        
if btn_processar:
    conteudo = ""
    
    # --- LOGICA DE PRIORIDADE CORRIGIDA ---
    if uploaded_sms is not None:
        # Se houver arquivo, lê o conteúdo dele
        conteudo = uploaded_sms.getvalue().decode("utf-8")
    elif texto_copiado:
        # Se não houver arquivo, tenta o texto colado
        conteudo = texto_copiado

    if not conteudo:
        st.error("⚠️ Por favor, faça o upload de um arquivo ou cole o texto antes de processar.")
    else:
        # O split deve ser feito por uma regex que aceite variações de traços
        # Alguns sistemas exportam com mais ou menos traços
        blocos = re.split(r"-{10,}", conteudo) 
        lista_transacoes = []
        
        for bloco in blocos:
            if not bloco.strip(): continue
            
            # 1. Tenta metadados do arquivo (Data/Hora de recebimento)
            match_meta = re.search(r"Recebido de .+ em (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", bloco)
            
            # --- PADRÃO 1: CAIXA, ITAU, NUBANK (O que você já tinha) ---
            match_padrao = re.search(r"(\w+): Compra (aprovada|CANCELADA|no) (.*?) R\$ ([\d\.,]+) (\d{2}/\d{2})", bloco, re.IGNORECASE)
            
            # --- PADRÃO 2: CARTÃO AMAZON (NOVO) ---
            # Ex: CARTAO AMAZON: ... 31/03/2026 11:20. VALOR DE R$69,97, AMAZONMKTPLC*PURONUTRI.
            match_amazon = re.search(r"CARTAO (AMAZON):.*? (\d{2}/\d{2}/\d{4}).*? VALOR DE R\$([\d\.,]+), (.*?)\.", bloco, re.IGNORECASE)

            # --- PADRÃO 3: BRADESCO (NOVO) ---
            # Ex: BRADESCO CARTOES: COMPRA APROVADA NO CARTAO FINAL 9808 EM 06/04/2026 17:18. VALOR DE R$ 110,00 BRADESCO AUT*08DE10      RIO DE JANEI.
            match_bradesco = re.search(r"BRADESCO.*?:.*? (\d{2}/\d{2}/\d{4}).*? VALOR DE R\$ ([\d\.,]+) (.*?)\.", bloco, re.IGNORECASE)

            if match_padrao:
                banco_raw = match_padrao.group(1).upper()
                status = match_padrao.group(2).upper()
                estabelecimento = match_padrao.group(3).strip().upper()
                valor_str = match_padrao.group(4).replace('.', '').replace(',', '.')
                data_sms = match_padrao.group(5)
                # Lógica de data abreviada (DD/MM)
                ano_atual = datetime.now().year
                data_iso = datetime.strptime(f"{data_sms}/{ano_atual}", "%d/%m/%Y").strftime('%Y-%m-%d')
            
            elif match_amazon:
                banco_raw = match_amazon.group(1).upper()
                data_full = match_amazon.group(2) # 31/03/2026
                valor_str = match_amazon.group(3).replace('.', '').replace(',', '.')
                estabelecimento = match_amazon.group(4).strip().upper()
                status = "APROVADA"
                # Converte data completa (DD/MM/AAAA)
                data_iso = datetime.strptime(data_full, "%d/%m/%Y").strftime('%Y-%m-%d')
            
            elif match_bradesco:
                banco_raw = "BRADESCO"
                data_full = match_bradesco.group(1)
                valor_str = match_bradesco.group(2).replace('.', '').replace(',', '.')
                estabelecimento_raw = match_bradesco.group(3).strip().upper()
                data_iso = datetime.strptime(data_full, "%d/%m/%Y").strftime('%Y-%m-%d')
                
                # Identificar parcelas (ex: 08DE10)
                match_parcela = re.search(r"(\d{2})DE(\d{2})", estabelecimento_raw)
                
                if match_parcela:
                    p_atual = int(match_parcela.group(1))
                    p_total = int(match_parcela.group(2))
                    desc_limpa = re.sub(r"AUT\*\d{2}DE\d{2}", "", estabelecimento_raw).strip()
                    
                    # Guardamos metadados para o alerta na UI
                    st.session_state.info_parcelamento = {
                        "ativa": True,
                        "atual": p_atual,
                        "total": p_total,
                        "valor": float(valor_str),
                        "desc": desc_limpa,
                        "data_origem": data_iso,
                        "banco": MAPA_SMS.get(banco_raw)
                    }
                    estabelecimento = f"{desc_limpa} ({p_atual}/{p_total})"
                else:
                    estabelecimento = estabelecimento_raw

            else:
                continue # Pula se não bater com nenhum padrão

            # --- PROCESSAMENTO COMUM (A partir daqui o código segue igual para ambos) ---
            if match_meta:
                hora_min = match_meta.group(2)
            else:
                hora_min = datetime.now().strftime("%H:%M")

            banco_final = MAPA_SMS.get(banco_raw, f"CARTÃO {banco_raw}")
            valor_num = float(valor_str)
            
            if status == "CANCELADA" or "ESTORNO" in bloco.upper():
                valor_num = -abs(valor_num)
            
            h_raw = f"{data_iso}{valor_num}{estabelecimento}{hora_min}{banco_final}{usuario_atual}"
            h = hashlib.md5(h_raw.encode()).hexdigest()
            
            lista_transacoes.append({
                "data": data_iso,
                "data_obj": datetime.strptime(data_iso, '%Y-%m-%d').date(),
                "descricao": estabelecimento,
                "valor": valor_num,
                "banco": banco_final,
                "hash": h
            })

        if lista_transacoes:
            st.session_state.df_sms_preview = pd.DataFrame(lista_transacoes).sort_values("data", ascending=False)
            st.success(f"✅ {len(lista_transacoes)} transações processadas!")
        else:
            st.error("❌ Formato de SMS não reconhecido.")

# --------------------------------------------------
# Área de Visualização e Salvamento
# --------------------------------------------------
if st.session_state.df_sms_preview is not None:
    df_sms = st.session_state.df_sms_preview

    st.markdown("### Prévia das Transações")
    st.dataframe(
        df_sms[["data", "descricao", "valor", "banco"]],
        width = 'stretch',
        hide_index=True,
        column_config={
            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "valor": st.column_config.NumberColumn("R$", format="%.2f")
        }
    )
if st.button("💾 Salvar no Banco de Dados", use_container_width=True):
    regras_usuario = carregar_regras_db(usuario_atual)
    try:
        engine = get_engine()
        
        # 1. Carrega dados para comparação
        df_db = carregar_transacoes(usuario_atual)
        
        novos_para_inserir = []
        count_manual = 0
        count_hash = 0

        # Preparação de sets para comparação rápida
        if not df_db.empty:
            # Criamos uma chave única (Data, Valor, Banco) para detectar duplicatas manuais
            db_keys = set(
                (pd.to_datetime(r['data']).date(), round(float(r['valor']), 2), str(r['banco']).upper()) 
                for _, r in df_db.iterrows()
            )
            hashes_existentes = set(df_db['hash_fatura'].dropna().unique())
        else:
            db_keys = set()
            hashes_existentes = set()

        # 2. Loop de Validação
        for _, row in df_sms.iterrows():
            # Validação 1: Já importado via Hash?
            if row['hash'] in hashes_existentes:
                count_hash += 1
                continue
            
            # Validação 2: Similaridade (Manual/SMS)
            chave_atual = (row['data_obj'], round(float(row['valor']), 2), str(row['banco']).upper())
            if chave_atual in db_keys:
                count_manual += 1
                continue 

            # Adiciona à lista como DICIONÁRIO para o SQLAlchemy
            categoria_auto = find_category(row['descricao'], regras_usuario)

            novos_para_inserir.append({
                "dat": row['data'], 
                "des": row['descricao'], 
                "cat": categoria_auto, 
                "val": row['valor'], 
                "bnc": row['banco'], 
                "uid": usuario_atual, 
                "hsh": row['hash']
            })

        # 3. Execução Final com SQLAlchemy
        if novos_para_inserir:
            query = text('''
                INSERT INTO transacoes (data, descricao, categoria, valor, banco, user_id, hash_fatura) 
                VALUES (:dat, :des, :cat, :val, :bnc, :uid, :hsh)
            ''')
            
            with engine.begin() as conn_trans:
                conn_trans.execute(query, novos_para_inserir)
            
            st.success(f"✅ {len(novos_para_inserir)} novas transações salvas!")
            
            # --- LIMPEZA AUTOMÁTICA ---
            st.session_state.df_sms_preview = None
            st.session_state.input_counter += 1
            
            if 'df_transacoes' in st.session_state:
                del st.session_state.df_transacoes
            
            st.rerun()
        else:
            st.warning("Todas as transações já existem no banco.")

        # Feedbacks informativos
        if count_manual > 0: st.info(f"📌 {count_manual} já existiam (lançamento manual).")
        if count_hash > 0: st.warning(f"🚫 {count_hash} já foram importadas via SMS.")

    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")