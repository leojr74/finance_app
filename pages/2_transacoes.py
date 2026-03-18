import streamlit as st
import pandas as pd
from database import carregar_transacoes
from categorizer import load_categories, add_rule, clean_description, find_category
from services.transaction_service import save_all_changes

# --- CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(page_title="Gerenciar Transações", layout="wide")

def aplicar_inteligencia_json(df):
    """Aplica categorias automáticas baseadas nas regras do arquivo JSON."""
    df_copy = df.copy()
    rules = load_categories()
    mask = (df_copy["categoria"] == "Sem categoria") | (df_copy["categoria"].isna())
    if mask.any():
        df_copy.loc[mask, "categoria"] = df_copy.loc[mask, "descricao"].apply(
            lambda x: find_category(x, rules)
        )
    return df_copy

st.title("📊 Gerenciar Transações")

# --- 1. CARREGAMENTO DOS DADOS ---
if "df_transacoes" not in st.session_state:
    df = carregar_transacoes()
    if df is not None and not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors='coerce')
        df["valor"] = pd.to_numeric(df["valor"], errors='coerce')
        df = aplicar_inteligencia_json(df)
        df["SEL"] = False 
        st.session_state.df_transacoes = df.set_index("id")
    else:
        st.info("O banco de dados está vazio.")
        st.stop()

# --- 2. FILTROS E CATEGORIAS ---
st.write("---")
c1, c2, c3 = st.columns([1.5, 1.5, 1])

with c1:
    datas_limite = (st.session_state.df_transacoes["data"].min(), 
                    st.session_state.df_transacoes["data"].max())
    periodo = st.date_input("📅 Filtrar por período", value=datas_limite, format="DD/MM/YYYY")

with c2:
    # Captura TUDO: o que está no banco + o que está no JSON
    rules_filt = load_categories()
    cats_do_json = set(str(v) for v in rules_filt.values() if v)
    cats_no_df = set(st.session_state.df_transacoes["categoria"].unique())
    lista_filtro = sorted(cats_do_json.union(cats_no_df).union({"Sem categoria"}))
    
    categorias_sel = st.multiselect("📂 Filtrar por categoria", options=lista_filtro, default=[])

with c3:
    busca = st.text_input("🔍 Buscar descrição", "").upper()

df_display = st.session_state.df_transacoes.copy()

if isinstance(periodo, tuple) and len(periodo) == 2:
    start_date, end_date = periodo
    df_display = df_display[(df_display["data"].dt.date >= start_date) & (df_display["data"].dt.date <= end_date)]

if categorias_sel:
    df_display = df_display[df_display["categoria"].isin(categorias_sel)]

if busca:
    df_display = df_display[df_display["descricao"].str.contains(busca, na=False)]

# --- 3. CATEGORIAS ---
# 1. Carrega as regras do JSON
rules = load_categories()

# 2. Extrai os nomes das categorias que estão no JSON (ex: Vestuário, Taxas, Assinaturas)
categorias_do_json = set(str(v) for v in rules.values() if v)

# 3. Pega categorias que já estão no Banco de Dados (para não sumir o que já foi salvo)
categorias_no_df = set(st.session_state.df_transacoes["categoria"].unique())

# 4. Categorias padrão que você sempre quer ver
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}

# UNE TUDO: O Streamlit agora "conhecerá" todas as suas categorias
lista_categorias = sorted(categorias_do_json.union(categorias_no_df).union(categorias_fixas))
opcoes_dropdown = lista_categorias + ["➕ Adicionar nova..."]

# --- 4. EDITOR DE DADOS (COLUNA S EM PRIMEIRO) ---
st.write(f"Exibindo {len(df_display)} transações.")
df_para_editar = df_display.reset_index()
cols = ["SEL", "data", "descricao", "categoria", "valor", "banco", "id"]
df_para_editar = df_para_editar[cols]

df_editado_raw = st.data_editor(
    df_para_editar,
    key="editor_v32", 
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "id": None, 
        "SEL": st.column_config.CheckboxColumn("S", help="Marcar"),
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_dropdown),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
        "banco": st.column_config.TextColumn("Banco", disabled=True),
    },
)

# --- 5. AÇÕES EM MASSA ---
df_editado = df_editado_raw.set_index("id")
ids_marcados = df_editado[df_editado["SEL"] == True].index.tolist()

if ids_marcados:
    with st.container(border=True):
        st.markdown(f"⚡ **Ações em Massa:** {len(ids_marcados)} itens")
        c1, c2 = st.columns([2, 1])
        with c1:
            cat_massa = st.selectbox("Mudar categoria:", ["---"] + lista_categorias, key="cat_massa_v32")
            if cat_massa != "---" and st.button("Aplicar Agora", key="btn_massa_v32"):
                st.session_state.df_transacoes.loc[ids_marcados, "categoria"] = cat_massa
                st.session_state.df_transacoes.loc[ids_marcados, "SEL"] = False
                st.rerun()
        with c2:
            st.write(" ") 
            if st.button("🗑️ Excluir Selecionadas", type="secondary", key="btn_del_v32"):
                st.session_state.df_transacoes.drop(ids_marcados, inplace=True)
                st.rerun()

# --- 6. NOVA CATEGORIA ---
nova_cat_final = ""
if any(df_editado["categoria"] == "➕ Adicionar nova..."):
    with st.container(border=True):
        nova_cat_final = st.text_input("Nome da nova categoria:", key="new_cat_v32").strip()

# --- 7. SALVAMENTO E REPLICAÇÃO ---
st.divider()
b1, b2 = st.columns(2)
with b1:
    if st.button("💾 Salvar e Replicar", type="primary", key="save_v32"):
        if any(df_editado["categoria"] == "➕ Adicionar nova...") and not nova_cat_final:
            st.error("Escreva o nome da categoria no campo acima antes de salvar.")
            st.stop()
            
        st.toast("Processando regras...")
        ids_vivos = set(df_editado.index)
        ids_originais = set(df_display.index)
        st.session_state.df_transacoes.drop(ids_originais - ids_vivos, inplace=True, errors='ignore')

        if nova_cat_final:
            df_editado["categoria"] = df_editado["categoria"].replace("➕ Adicionar nova...", nova_cat_final)

        st.session_state.df_transacoes.update(df_editado)

        desc_limpas_total = st.session_state.df_transacoes["descricao"].apply(clean_description)
        for idx, row in df_editado.iterrows():
            cat_row = row["categoria"]
            if cat_row and cat_row not in ["Sem categoria", "➕ Adicionar nova..."]:
                d_limpa = clean_description(row["descricao"])
                add_rule(d_limpa, cat_row)
                mask = (desc_limpas_total == d_limpa) & \
                       (st.session_state.df_transacoes["categoria"].fillna("Sem categoria") == "Sem categoria")
                st.session_state.df_transacoes.loc[mask, "categoria"] = cat_row

        st.session_state.df_transacoes["SEL"] = False
        df_sql = st.session_state.df_transacoes.reset_index().drop(columns=["SEL"], errors='ignore')
        df_sql["data"] = df_sql["data"].dt.strftime('%Y-%m-%d')
        save_all_changes(df_sql)
        
        # Limpa o cache para garantir que as novas categorias carreguem no próximo loop
        if "df_transacoes" in st.session_state:
            del st.session_state.df_transacoes
            
        st.success(f"Salvo com sucesso!")
        st.rerun()

with b2:
    if st.button("🔄 Recarregar Banco", key="reload_v32"):
        if "df_transacoes" in st.session_state: del st.session_state.df_transacoes
        st.rerun()

# --- FIM DO ARQUIVO (194 LINHAS REAIS NO VS CODE) ---