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

# --- INICIALIZAÇÃO DE ESTADOS ---
if "input_counter" not in st.session_state:
    st.session_state.input_counter = 0

if "df_sms_preview" not in st.session_state:
    st.session_state.df_sms_preview = None

MAPA_SMS = {
    "CAIXA": "CARTÃO CAIXA",
    "ITAU": "CARTÃO ITAÚ",
    "NUBANK": "CARTÃO NUBANK",
    "BRADESCO": "CARTÃO BRADESCO",
    "SANTANDER": "CARTÃO SANTANDER",
    "AMAZON": "CARTÃO AMAZON"
}

# --- ENTRADA DE DADOS ---
uploaded_sms = st.file_uploader("Upload do arquivo .txt exportado", type="txt")
texto_copiado = st.text_area(
    "Ou cole o texto aqui:", 
    height=150, 
    key=f"sms_input_{st.session_state.input_counter}"
)

btn_processar = st.button("🔍 Processar SMS", type="primary", use_container_width=True)

# --------------------------------------------------
# 1. PROCESSAMENTO DO TEXTO
# --------------------------------------------------
if btn_processar:
    conteudo = uploaded_sms.getvalue().decode("utf-8") if uploaded_sms else texto_copiado
    
    if not conteudo:
        st.error("⚠️ Sem conteúdo para processar.")
    else:
        blocos = re.split(r"-{5,}", conteudo) 
        lista_transacoes = []
        
        if "transacao_parcelada" in st.session_state:
            del st.session_state.transacao_parcelada

        for bloco in blocos:
            bloco = bloco.strip()
            if not bloco: continue
            
            match_meta = re.search(r"(\d{2}:\d{2})", bloco)
            hora_min = match_meta.group(1) if match_meta else datetime.now().strftime("%H:%M")

            data_iso, valor_num, estabel, banco_ref, status = None, None, None, None, "APROVADA"

            # REGEX CAIXA SIMPLES - NOVO PADRÃO (compra sem parcelamento)
            m_caixa = re.search(r"CAIXA:\s+Compra aprovada em (.+?), R\$\s+([\d\.,]+),\s+(\d{2}/\d{2})\s+às\s+(\d{2}:\d{2})", bloco, re.IGNORECASE)
            # REGEX CAIXA PARCELADA - PADRÃO ANTIGO (mantido para compatibilidade)
            m_caixa_p = re.search(r"CAIXA:.*?Compra aprovada em (.*?) R\$\s*([\d\.,]+)\s+em\s+(\d+)\s+vezes,\s+(\d{2}/\d{2})", bloco, re.IGNORECASE | re.DOTALL)
            # REGEX BRADESCO
            m_bradesco = re.search(r"BRADESCO.*?:.*? (\d{2}/\d{2}/\d{4}).*? VALOR DE R\$ ([\d\.,]+) (.*?)\.", bloco, re.IGNORECASE)
            # REGEX PADRÃO GERAL
            m_geral = re.search(r"(\w+): Compra (aprovada|CANCELADA|no) (.*?) R\$\s*([\d\.,]+) (\d{2}/\d{2})", bloco, re.IGNORECASE)

            if m_caixa_p:
                banco_ref = "CAIXA"
                total_p = int(m_caixa_p.group(3))
                v_total = float(m_caixa_p.group(2).replace('.', '').replace(',', '.'))
                
                # Lógica de divisão com resto na primeira
                parcela_comum = round(v_total / total_p, 2)
                diferenca = round(v_total - (parcela_comum * total_p), 2)
                valor_primeira = round(parcela_comum + diferenca, 2)
                
                valor_num = valor_primeira
                estabel_limpo = m_caixa_p.group(1).strip().upper()
                estabel = f"{estabel_limpo} (1/{total_p})"
                dt_sms = m_caixa_p.group(4)
                data_iso = datetime.strptime(f"{dt_sms}/{datetime.now().year}", "%d/%m/%Y").strftime('%Y-%m-%d')
                
                st.session_state.transacao_parcelada = {
                    "data_origem": data_iso, 
                    "valor": valor_primeira,  # Valor da parcela atual (1ª)
                    "valor_comum": parcela_comum, # Valor das próximas
                    "desc": estabel_limpo,
                    "p_atual": 1, "p_total": total_p, "banco": MAPA_SMS["CAIXA"]
                }

            elif m_caixa:
                # NOVO PADRÃO - Compra CAIXA simples (sem parcelamento)
                banco_ref = "CAIXA"
                estabel_limpo = m_caixa.group(1).strip().upper()
                estabel = estabel_limpo
                valor_num = float(m_caixa.group(2).replace('.', '').replace(',', '.'))
                dt_sms = m_caixa.group(3)
                hora_min = m_caixa.group(4)  # Atualiza hora_min com a captura do regex
                data_iso = datetime.strptime(f"{dt_sms}/{datetime.now().year}", "%d/%m/%Y").strftime('%Y-%m-%d')

            elif m_bradesco:
                banco_ref = "BRADESCO"
                data_iso = datetime.strptime(m_bradesco.group(1), "%d/%m/%Y").strftime('%Y-%m-%d')
                valor_num = float(m_bradesco.group(2).replace('.', '').replace(',', '.'))
                estabel_raw = m_bradesco.group(3).strip().upper()
                m_p = re.search(r"AUT\*(\d{2})DE(\d{2})", estabel_raw)
                if m_p:
                    p_at, p_tot = int(m_p.group(1)), int(m_p.group(2))
                    estabel_limpo = re.sub(r'AUT\*\d{2}DE\d{2}', '', estabel_raw).strip()
                    estabel = f"{estabel_limpo} ({p_at}/{p_tot})"
                    st.session_state.transacao_parcelada = {
                        "data_origem": data_iso, "valor": valor_num, "desc": estabel_limpo,
                        "p_atual": p_at, "p_total": p_tot, "banco": MAPA_SMS["BRADESCO"]
                    }
                else:
                    estabel = estabel_raw

            elif m_geral:
                banco_ref = m_geral.group(1).upper()
                status = m_geral.group(2).upper()
                estabel = m_geral.group(3).strip().upper()
                valor_num = float(m_geral.group(4).replace('.', '').replace(',', '.'))
                dt_sms = m_geral.group(5)
                data_iso = datetime.strptime(f"{dt_sms}/{datetime.now().year}", "%d/%m/%Y").strftime('%Y-%m-%d')

            if data_iso:
                banco_final = MAPA_SMS.get(banco_ref, f"CARTÃO {banco_ref}")
                if status == "CANCELADA" or "ESTORNO" in bloco.upper():
                    valor_num = -abs(valor_num)
                
                h = hashlib.md5(f"{data_iso}{valor_num}{estabel}{hora_min}{banco_final}{usuario_atual}".encode()).hexdigest()
                lista_transacoes.append({
                    "data": data_iso, "data_obj": datetime.strptime(data_iso, '%Y-%m-%d').date(),
                    "descricao": estabel, "valor": valor_num, "banco": banco_final, "hash": h
                })

        if lista_transacoes:
            st.session_state.df_sms_preview = pd.DataFrame(lista_transacoes).sort_values("data", ascending=False)
            st.success(f"✅ {len(lista_transacoes)} transações processadas!")
        else:
            st.warning("⚠️ Nenhum padrão reconhecido.")

# --------------------------------------------------
# 2. AVISO DE PARCELAMENTO
# --------------------------------------------------
if "transacao_parcelada" in st.session_state:
    tp = st.session_state.transacao_parcelada
    with st.container(border=True):
        st.warning(f"💳 **Compra Parcelada:** {tp['desc']}")
        # Aqui corrigimos o erro: usamos .get() ou as chaves novas
        v_exibicao = tp.get('valor', 0)
        st.write(f"Valor da Parcela Atual: **R$ {v_exibicao:.2f}**")
        
        if st.button(f"⏩ Projetar as {tp['p_total'] - tp['p_atual']} parcelas restantes?"):
            novas = []
            base_dt = datetime.strptime(tp['data_origem'], '%Y-%m-%d')
            
            for i in range(1, tp['p_total'] - tp['p_atual'] + 1):
                dt_p = (base_dt + pd.DateOffset(months=i)).strftime('%Y-%m-%d')
                n_p = tp['p_atual'] + i
                desc_p = f"{tp['desc']} ({n_p}/{tp['p_total']})"
                
                # Se for Caixa, usa valor_comum. Se não (Bradesco), usa o valor padrão.
                v_prox = tp.get('valor_comum', tp['valor'])
                
                h_p = hashlib.md5(f"{dt_p}{v_prox}{desc_p}{tp['banco']}{usuario_atual}".encode()).hexdigest()
                novas.append({
                    "data": dt_p, "data_obj": datetime.strptime(dt_p, '%Y-%m-%d').date(),
                    "descricao": desc_p, "valor": v_prox, "banco": tp['banco'], "hash": h_p
                })
            
            st.session_state.df_sms_preview = pd.concat([st.session_state.df_sms_preview, pd.DataFrame(novas)], ignore_index=True)
            del st.session_state.transacao_parcelada
            st.rerun()

# --------------------------------------------------
# 3. VISUALIZAÇÃO E SALVAMENTO
# --------------------------------------------------
if st.session_state.df_sms_preview is not None:
    df_sms = st.session_state.df_sms_preview
    st.markdown("### Prévia das Transações")
    st.dataframe(df_sms[["data", "descricao", "valor", "banco"]].sort_values("data", ascending=False), use_container_width=True, hide_index=True)

    if st.button("💾 Salvar no Banco de Dados", use_container_width=True):
        regras_usuario = carregar_regras_db(usuario_atual)
        try:
            engine = get_engine()
            df_db = carregar_transacoes(usuario_atual)
            novos_para_inserir = []
            
            hashes_existentes = set(df_db['hash_fatura'].dropna().unique()) if not df_db.empty else set()
            db_keys = set((pd.to_datetime(r['data']).date(), round(float(r['valor']), 2), str(r['banco']).upper()) for _, r in df_db.iterrows()) if not df_db.empty else set()

            for _, row in df_sms.iterrows():
                if row['hash'] in hashes_existentes: continue
                if (row['data_obj'], round(float(row['valor']), 2), str(row['banco']).upper()) in db_keys: continue 

                novos_para_inserir.append({
                    "dat": row['data'], "des": row['descricao'], 
                    "cat": find_category(row['descricao'], regras_usuario), 
                    "val": row['valor'], "bnc": row['banco'], 
                    "uid": usuario_atual, "hsh": row['hash']
                })

            if novos_para_inserir:
                query = text("INSERT INTO transacoes (data, descricao, categoria, valor, banco, user_id, hash_fatura) VALUES (:dat, :des, :cat, :val, :bnc, :uid, :hsh)")
                with engine.begin() as conn:
                    conn.execute(query, novos_para_inserir)
                st.success(f"✅ {len(novos_para_inserir)} transações salvas!")
                st.session_state.df_sms_preview = None
                st.session_state.input_counter += 1
                st.rerun()
            else:
                st.warning("Todas as transações já existem no banco.")
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")