import streamlit as st
import pandas as pd
import sqlite3

from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from database import carregar_transacoes, atualizar_categorias
from categorizer import load_categories, add_rule, clean_description

st.title("📊 Transações")

# --------------------------------------------------
# carregar dados
# --------------------------------------------------

if "transacoes_df" not in st.session_state:

    df = carregar_transacoes()

    if df is None or len(df) == 0:
        st.warning("Nenhuma transação encontrada")
        st.stop()

    df["categoria"] = df["categoria"].fillna("Sem categoria")

    st.session_state.transacoes_df = df

df = st.session_state.transacoes_df.copy()

# --------------------------------------------------
# converter data para datetime
# --------------------------------------------------

df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")

# --------------------------------------------------
# categorias
# --------------------------------------------------

rules = load_categories()

categorias = sorted(set(rules.values()))
categorias.append("Sem categoria")

# --------------------------------------------------
# configurar grid
# --------------------------------------------------

gb = GridOptionsBuilder.from_dataframe(df)

gb.configure_selection(
    selection_mode="multiple",
    use_checkbox=True
)

gb.configure_column(
    "categoria",
    editable=True,
    cellEditor="agSelectCellEditor",
    cellEditorParams={"values": categorias},
)

gb.configure_column(
    "data",
    type=["dateColumnFilter", "customDateTimeFormat"],
    custom_format_string="dd/MM/yyyy",
)

gb.configure_column(
    "valor",
    type=["numericColumn"],
)

gridOptions = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=gridOptions,
    update_mode=GridUpdateMode.VALUE_CHANGED,
    height=500,
    fit_columns_on_grid_load=True,
)

edited_df = pd.DataFrame(grid_response["data"])
selected_rows = pd.DataFrame(grid_response["selected_rows"])

# --------------------------------------------------
# corrigir formato da data
# --------------------------------------------------

edited_df["data"] = pd.to_datetime(
    edited_df["data"], errors="coerce"
).dt.strftime("%d/%m/%Y")

st.session_state.transacoes_df = edited_df

# --------------------------------------------------
# ações em massa
# --------------------------------------------------

if len(selected_rows) > 0:

    st.divider()

    st.subheader(f"{len(selected_rows)} transações selecionadas")

    categoria = st.selectbox("Escolher categoria", categorias)

    aplicar_outras = st.checkbox(
        "Aplicar regra às outras transações iguais",
        value=True
    )

    if st.button("🏷 Aplicar às selecionadas e aprender regra"):

        # corrigir índice vindo do grid
        idx = selected_rows.index.astype(int)

        edited_df.loc[idx, "categoria"] = categoria

        descricoes = selected_rows["descricao"].unique()

        for desc in descricoes:

            regra = clean_description(desc)
            add_rule(regra, categoria)

            if aplicar_outras:

                mask = edited_df["descricao"] == desc
                edited_df.loc[mask, "categoria"] = categoria

        st.session_state.transacoes_df = edited_df

        st.success("Categoria aplicada e regra aprendida")

        st.rerun()

    if st.button("🗑 Excluir selecionadas"):

        idx = selected_rows.index.astype(int)

        deletar = edited_df.loc[idx]

        edited_df = edited_df.drop(idx).reset_index(drop=True)

        st.session_state.transacoes_df = edited_df

        try:

            if "id" in deletar.columns:

                conn = sqlite3.connect("transacoes.db")
                cursor = conn.cursor()

                for i in deletar["id"]:
                    cursor.execute("DELETE FROM transacoes WHERE id=?", (int(i),))

                conn.commit()
                conn.close()

        except:
            pass

        st.success("Transações excluídas")

        st.rerun()

# --------------------------------------------------
# salvar alterações
# --------------------------------------------------

st.divider()

if st.button("💾 Salvar alterações de categoria"):

    atualizar_categorias(st.session_state.transacoes_df)

    st.success("Categorias atualizadas no banco")

# --------------------------------------------------
# total
# --------------------------------------------------

total = st.session_state.transacoes_df["valor"].sum()

st.success(
    f"{len(st.session_state.transacoes_df)} transações | Total: R$ {total:,.2f}"
    .replace(",", "X").replace(".", ",").replace("X", ".")
)