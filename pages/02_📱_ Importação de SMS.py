import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime
from ui import apply_global_style
from database import get_engine, get_authenticator, carregar_transacoes, verificar_duplicata
from sqlalchemy import text

st.set_page_config(
    page_title="Importação de SMS",
    page_icon="📱",
    layout="wide"
)

# --------------------------------------------------
# Autenticação e Estilo
# --------------------------------------------------
authenticator = get_authenticator()
authenticator.login(location='unrendered')

if not st.session_state.get("authentication_status"):
    st.warning("Sessão expirada. Por favor, faça login na Home.")
    st.stop()

usuario_atual = st.session_state["username"]
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
    "SANTANDER": "CARTÃO SANTANDER"
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
            

            # Regex Híbrido: Tenta metadados (arquivo) ou data direta (texto colado)
            match_meta = re.search(r"Recebido de .+ em (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", bloco)
            match_compra = re.search(r"(\w+): Compra (aprovada|CANCELADA|no) (.*?) R\$ ([\d\.,]+) (\d{2}/\d{2})", bloco, re.IGNORECASE)
            
            if match_compra:
                banco_raw = match_compra.group(1).upper()
                status = match_compra.group(2).upper()
                estabelecimento = match_compra.group(3).strip().upper()
                valor_str = match_compra.group(4).replace('.', '').replace(',', '.')
                data_sms = match_compra.group(5) # DD/MM
                
                # Define a data e hora
                if match_meta:
                    data_iso = match_meta.group(1)
                    hora_min = match_meta.group(2)
                else:
                    ano_atual = datetime.now().year
                    data_iso = datetime.strptime(f"{data_sms}/{ano_atual}", "%d/%m/%Y").strftime('%Y-%m-%d')
                    hora_min = datetime.now().strftime("%H:%M") # Hora atual se colado

                banco_final = MAPA_SMS.get(banco_raw, f"CARTÃO {banco_raw}")
                valor_num = float(valor_str)
                
                # Lógica de Estorno
                if status == "CANCELADA" or "ESTORNO" in bloco.upper():
                    valor_num = -abs(valor_num)
                
                # Hash único para evitar duplicatas de importação
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
    if st.button("💾 Salvar no Banco de Dados", width = 'stretch'):
        try:
            engine = get_engine()

            # 1. Carrega transações existentes para comparação
            df_db = carregar_transacoes(usuario_atual)
            
            novos_para_inserir = []
            count_manual = 0
            count_hash = 0

            # Preparação de sets para comparação rápida (Otimização)
            if not df_db.empty:
                db_keys = set(
                    (pd.to_datetime(r['data']).date(), round(float(r['valor']), 2), str(r['banco']).upper()) 
                    for _, r in df_db.iterrows()
                )
                hashes_existentes = set(df_db['hash_fatura'].dropna().unique())
            else:
                db_keys = set()
                hashes_existentes = set()

                
            # 2. Processamento dos dados do SMS
            for _, row in df_sms.iterrows():
                # Validação 1: Hash único (Já importado via SMS anteriormente)
                if row['hash'] in hashes_existentes:
                    count_hash += 1
                    continue
                
                # Validação 2: Similaridade (Evita duplicar o que foi lançado manual ou noutra fatura)
                chave_atual = (row['data_obj'], round(float(row['valor']), 2), str(row['banco']).upper())
                if chave_atual in db_keys:
                    count_manual += 1
                    continue 

                # Adiciona à lista no formato de dicionário para o SQLAlchemy
                novos_para_inserir.append({
                    "data": row['data'],
                    "desc": row['descricao'],
                    "cat": "Sem categoria",
                    "val": row['valor'],
                    "bnc": row['banco'],
                    "uid": usuario_atual,
                    "hsh": row['hash']
                })

            # 3. Execução do INSERT em lote
            if novos_para_inserir:
                query = text("""
                    INSERT INTO transacoes (data, descricao, categoria, valor, banco, user_id, hash_fatura) 
                    VALUES (:data, :desc, :cat, :val, :bnc, :uid, :hsh)
                """)
                
                with engine.begin() as conn:
                    conn.execute(query, novos_para_inserir)
                
                st.success(f"✅ {len(novos_para_inserir)} novas transações salvas!")
                
                # --- LIMPEZA AUTOMÁTICA (Sessão) ---
                st.session_state.df_sms_preview = None 
                if 'input_counter' in st.session_state:
                    st.session_state.input_counter += 1
                
                if 'df_transacoes' in st.session_state:
                    del st.session_state.df_transacoes
                
                st.rerun()
            else:
                st.warning("Todas as transações já existem no banco.")

            # Feedbacks de duplicatas
            if count_manual > 0: st.info(f"📌 {count_manual} já existiam (lançamento manual/fatura).")
            if count_hash > 0: st.warning(f"🚫 {count_hash} já foram importadas via SMS anteriormente.")

        except Exception as e:
            st.error(f"❌ Erro crítico ao salvar: {e}")
        
        finally:
            if conn is not None: 
                conn.close()