import streamlit as st
import pandas as pd

from st_aggrid import AgGrid, GridOptionsBuilder

from database import carregar_transacoes
from categorizer import load_categories, add_rule, clean_description
from services.transaction_service import save_all_changes

st.title("📊 Transações")

# --------------------------------------------------
# carregar dados
# --------------------------------------------------

if "transacoes_original" not in st.session_state:

    df = carregar_transacoes()

    if df is None or len(df) == 0:
        st.warning("Nenhuma transação encontrada")
        st.stop()

    df["categoria"] = df["categoria"].fillna("Sem categoria")

    st.session_state.transacoes_original = df.copy()
    st.session_state.transacoes_df = df.copy()

df = st.session_state.transacoes_df.copy()

# --------------------------------------------------
# converter data
# --------------------------------------------------

df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")

# --------------------------------------------------
# categorias
# --------------------------------------------------

rules = load_categories()

categorias = sorted(set(rules.values()))
categorias.append("Sem categoria")

# --------------------------------------------------
# grid
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
    editable=True,
    type=["dateColumnFilter", "customDateTimeFormat"],
    custom_format_string="dd/MM/yyyy",
)

gb.configure_column(
    "valor",
    editable=True,
    type=["numericColumn"],
)

gb.configure_column(
    "descricao",
    editable=True,
)

gridOptions = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=gridOptions,
    update_on=["cellValueChanged", "selectionChanged"],
    height=500,
    fit_columns_on_grid_load=True,
)

edited_df = pd.DataFrame(grid_response["data"])
selected_rows = pd.DataFrame(grid_response["selected_rows"])

# --------------------------------------------------
# corrigir data
# --------------------------------------------------

edited_df["data"] = pd.to_datetime(
    edited_df["data"], errors="coerce"
).dt.strftime("%d/%m/%Y")

# --------------------------------------------------
# detectar mudança de categoria
# --------------------------------------------------

original = st.session_state.transacoes_original

merged = edited_df.merge(
    original[["id", "categoria"]],
    on="id",
    how="left",
    suffixes=("", "_original")
)

changed = merged[merged["categoria"] != merged["categoria_original"]]

# --------------------------------------------------
# popup aprendizado
# --------------------------------------------------

if len(changed) == 1 and not st.session_state.get("rule_prompted", False):

    row = changed.iloc[0]

    st.session_state.rule_prompted = True

    @st.dialog("Aprender regra?")
    def dialog_aprender(descricao, categoria):

        st.write(
            f"A categoria da transação **{descricao}** foi alterada para **{categoria}**."
        )

        st.write("Deseja aprender essa regra para futuras transações?")

        col1, col2 = st.columns(2)

        if col1.button("Sim"):

            regra = clean_description(descricao)
            add_rule(regra, categoria)

            mask = st.session_state.transacoes_df["descricao"] == descricao
            st.session_state.transacoes_df.loc[mask, "categoria"] = categoria

            st.session_state.rule_prompted = False

            st.session_state.transacoes_original = st.session_state.transacoes_df.copy()

            st.success("Regra aprendida")

            st.rerun()

        if col2.button("Não"):

            st.session_state.rule_prompted = False

            st.session_state.transacoes_original = st.session_state.transacoes_df.copy()

            st.rerun()

    dialog_aprender(row["descricao"], row["categoria"])

# --------------------------------------------------
# atualizar estado
# --------------------------------------------------

st.session_state.transacoes_df = edited_df

# --------------------------------------------------
# ações em massa
# --------------------------------------------------

if len(selected_rows) > 0:

    st.divider()

    st.subheader(f"{len(selected_rows)} transações selecionadas")

    categoria = st.selectbox("Escolher categoria", categorias)

    if st.button("🏷 Aplicar às selecionadas e aprender regra"):

        ids = selected_rows["id"].tolist()

        edited_df.loc[ids, "categoria"] = categoria

        descricoes = selected_rows["descricao"].unique()

        for desc in descricoes:

            regra = clean_description(desc)
            add_rule(regra, categoria)

            mask = edited_df["descricao"] == desc
            edited_df.loc[mask, "categoria"] = categoria

        st.session_state.transacoes_df = edited_df

        st.success("Categoria aplicada e regra aprendida")

        st.rerun()

    if st.button("🗑 Excluir selecionadas"):

        ids = selected_rows["id"].tolist()

        edited_df = edited_df.drop(ids).reset_index(drop=True)

        st.session_state.transacoes_df = edited_df

        st.success("Transações marcadas para exclusão")

        st.rerun()

# --------------------------------------------------
# salvar alterações
# --------------------------------------------------

st.divider()

if st.button("💾 Salvar alterações no banco de dados"):

    save_all_changes(st.session_state.transacoes_df)

    st.session_state.transacoes_original = st.session_state.transacoes_df.copy()

    st.success("Banco de dados atualizado")

# --------------------------------------------------
# total
# --------------------------------------------------

total = st.session_state.transacoes_df["valor"].sum()

st.success(
    f"{len(st.session_state.transacoes_df)} transações | Total: R$ {total:,.2f}"
    .replace(",", "X").replace(".", ",").replace("X", ".")
)