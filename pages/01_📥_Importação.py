import streamlit as st
import pandas as pd
from datetime import date
import sqlite3
import hashlib

from parser_router import extract_transactions_auto
# Removi a importação de salvar_transacoes pois estamos usando a lógica local de cursor

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
        # Mapeamento para nomes amigáveis (Exibição e Banco)
        # --------------------------------------------------
        # Aqui pegamos o ID técnico retornado pelo bank_detector (ex: 'ca')
        id_tecnico = str(result.get("bank", "DESCONHECIDO")).lower()

        mapeamento_nomes = {
            "ca": "CARTÃO C&A",
            "caixa": "CARTÃO CAIXA",
            "bradescard": "CARTÃO AMAZON",
            "bradesco": "CARTÃO BRADESCO",
            "santander": "CARTÃO SANTANDER",
            "itau": "CARTÃO ITAÚ",
            "bb": "CARTÃO BB",
            "nubank": "NUBANK",
            "mercado_pago": "MERCADO PAGO"
        }

        # Define o nome final. Se não estiver no mapa, usa o ID original em maiúsculo.
        banco = mapeamento_nomes.get(id_tecnico, id_tecnico.upper())

        # --------------------------------------------------
        # Dataframe apenas para exibição
        # --------------------------------------------------
        df_display = df.copy()
        df_display["data"] = df_display["data"].dt.strftime("%d/%m/%Y")
        df_display["valor"] = df_display["valor"].map(
            lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
        )

        st.success(f"{len(df)} transações extraídas de: **{banco}**")
        st.dataframe(df_display, use_container_width=True)

        # Total
        total = df["valor"].sum()
        st.info(f"Total das transações: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # --------------------------------------------------
        # Gerar hash da fatura
        # --------------------------------------------------
        hash_base = f"{banco}_{data_inicio}_{data_fim}"
        hash_fatura = hashlib.sha256(hash_base.encode()).hexdigest()

        # --------------------------------------------------
        # Botão salvar
        # --------------------------------------------------
        if st.button("💾 Salvar no banco"):
            try:
                conn = sqlite3.connect("transacoes.db")
                cursor = conn.cursor()
                inseridas = 0

                for _, row in df.iterrows():
                    # Verifica duplicata usando o nome amigável
                    cursor.execute("""
                        SELECT 1 FROM transacoes
                        WHERE data = ? AND descricao = ? AND valor = ? AND banco = ?
                    """, (
                        row["data"].strftime("%Y-%m-%d"),
                        row["descricao"],
                        row["valor"],
                        banco
                    ))

                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO transacoes (data, descricao, valor, categoria, banco, hash_fatura)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row["data"].strftime("%Y-%m-%d"),
                            row["descricao"],
                            row["valor"],
                            row.get("categoria", "Sem categoria"),
                            banco,
                            hash_fatura
                        ))
                        inseridas += 1

                conn.commit()
                conn.close()

                if "df_transacoes" in st.session_state:
                    del st.session_state.df_transacoes
                
                st.success(f"✅ {inseridas} novas transações salvas em '{banco}'!")
                
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")