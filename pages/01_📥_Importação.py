import streamlit as st
import pandas as pd
from datetime import date
import sqlite3
import hashlib
from ui import apply_global_style

apply_global_style()

from parser_router import extract_transactions_auto

st.title("📥 Importação de Faturas")

# --------------------------------------------------
# Período da fatura
# --------------------------------------------------
st.subheader("Período da fatura")
col1, col2 = st.columns(2)

with col1:
    data_inicio = st.date_input("Data inicial", value=date.today().replace(day=1))

with col2:
    data_fim = st.date_input("Data final", value=date.today())

if data_fim < data_inicio:
    st.error("Data final não pode ser anterior à data inicial")
    st.stop()

# --------------------------------------------------
# Upload PDF
# --------------------------------------------------
uploaded = st.file_uploader("Upload da fatura PDF", type="pdf")

if uploaded:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded.read())

    # O parser_router recebe o ID técnico (ex: 'ca') e extrai os dados
    result = extract_transactions_auto(
        pdf_path="temp.pdf",
        data_inicio=data_inicio,
        data_fim=data_fim
    )

    if result and "transactions" in result:
        df = pd.DataFrame(result["transactions"])

        # --------------------------------------------------
        # Normalizar dados
        # --------------------------------------------------
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        df = df.sort_values("data").reset_index(drop=True)

        # --------------------------------------------------
        # Mapeamento para nomes amigáveis
        # --------------------------------------------------
        id_tecnico = str(result.get("bank", "DESCONHECIDO")).lower()

        mapeamento_nomes = {
            "ca": "CARTÃO C&A",
            "caixa": "CARTÃO CAIXA",
            "bradescard": "CARTÃO AMAZON",
            "bradesco": "CARTÃO BRADESCO",
            "santander": "CARTÃO SANTANDER",
            "itau": "CARTÃO ITAÚ",
            "bb": "CARTÃO BB",
            "nubank": "CARTÃO NUBANK",
            "mercado_pago": "MERCADO PAGO"
        }

        banco = mapeamento_nomes.get(id_tecnico, id_tecnico.upper())

        # --------------------------------------------------
        # Dataframe apenas para exibição (Sem Categoria)
        # --------------------------------------------------
        colunas_desejadas = ["data", "descricao", "valor"]
        colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
        
        df_display = df[colunas_existentes].copy()

        st.success(f"{len(df)} transações extraídas de: **{banco}**")

        st.dataframe(
            df_display, 
            width='stretch', 
            hide_index=True,
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "descricao": "Descrição",
                "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
            }
        )

        total = df["valor"].sum()
        st.info(f"Total das transações: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Hash da fatura para controle de lote
        hash_base = f"{banco}_{data_inicio}_{data_fim}"
        hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

        # --------------------------------------------------
        # Botão salvar com Lógica de Conciliação Estrita
        # --------------------------------------------------
        if st.button("💾 Salvar no banco"):
            try:
                conn = sqlite3.connect("transacoes.db")
                cursor = conn.cursor()
                
                inseridas = 0
                ignoradas_manual = 0
                ignoradas_duplicadas = 0

                for _, row in df.iterrows():
                    data_str = row["data"].strftime("%Y-%m-%d")
                    valor = row["valor"]
                    descricao = row["descricao"]
                    
                    # --- REGRA CRÍTICA: MESMA DATA, MESMO VALOR, MESMO BANCO ---
                    # 1. Busca por lançamento MANUAL Prévio
                    cursor.execute("""
                        SELECT 1 FROM transacoes 
                        WHERE data = ? 
                          AND valor = ? 
                          AND banco = ? 
                          AND hash_fatura = 'MANUAL_ENTRY'
                    """, (data_str, valor, banco))
                    
                    if cursor.fetchone():
                        # Se já existe um manual para este banco/data/valor, priorizamos o manual
                        ignoradas_manual += 1
                        continue

                    # 2. Busca por importação de PDF já realizada (Evitar Re-importação)
                    cursor.execute("""
                        SELECT 1 FROM transacoes
                        WHERE data = ? 
                          AND descricao = ? 
                          AND valor = ? 
                          AND banco = ?
                    """, (data_str, descricao, valor, banco))

                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            data_str,
                            descricao,
                            valor,
                            row.get("categoria", "Sem categoria"),
                            banco,
                            hash_fatura
                        ))
                        inseridas += 1
                    else:
                        ignoradas_duplicadas += 1

                conn.commit()
                conn.close()

                # Limpa cache para atualizar as outras telas
                if "df_transacoes" in st.session_state:
                    del st.session_state.df_transacoes
                
                # Relatório final para o usuário
                st.success(f"✅ Processamento concluído: {inseridas} novas transações.")
                
                if ignoradas_manual > 0:
                    st.warning(f"📌 {ignoradas_manual} itens do PDF foram descartados pois você já os lançou manualmente no {banco}.")
                
                if ignoradas_duplicadas > 0:
                    st.info(f"ℹ️ {ignoradas_duplicadas} itens já constavam no histórico deste PDF.")
                
            except Exception as e:
                st.error(f"Erro ao acessar o banco de dados: {e}")