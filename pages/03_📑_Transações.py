import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database import carregar_transacoes, save_all_changes 
from categorizer import load_categories, add_rule, clean_description, find_category
from ui import apply_global_style

apply_global_style()

# --- CONFIGURAÇÃO DE INTERFACE ---
st.set_page_config(page_title="Gerenciar Transações", layout="wide")

# --- FUNÇÕES COM CACHE PARA ESCALABILIDADE ---
@st.cache_data
def limpar_descricao_cached(descricao):
    """Garante que a limpeza de texto seja feita apenas uma vez por descrição."""
    return clean_description(descricao)

def aplicar_inteligencia_json(df):
    """Aplica categorias automáticas baseadas nas regras do arquivo JSON."""
    df_copy = df.copy()
    rules = load_categories()
    
    # Identifica o que precisa de categoria
    mask = (df_copy["categoria"] == "Sem categoria") | (df_copy["categoria"].isna())
    
    if mask.any():
        # Aplicamos a busca apenas onde necessário, usando a função original
        df_copy.loc[mask, "categoria"] = df_copy.loc[mask, "descricao"].apply(
            lambda x: find_category(x, rules)
        )
    return df_copy

st.title("📑 Gerenciamento de Transações")

# --- 1. CONFIGURAÇÃO DO FILTRO INICIAL (30 DIAS) ---
hoje = date.today()
trinta_dias_atras = hoje - timedelta(days=30)

# --- 2. CARREGAMENTO DOS DADOS ---
if "df_transacoes" not in st.session_state:
    # Carregamos do banco (você pode futuramente passar o limite para o SQL)
    df = carregar_transacoes() 
    
    if df is not None and not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors='coerce')
        df["valor"] = pd.to_numeric(df["valor"], errors='coerce')
        
        # Inteligência aplicada no carregamento inicial
        df = aplicar_inteligencia_json(df)
        
        df["SEL"] = False 
        st.session_state.df_transacoes = df.set_index("id")
    else:
        st.info("O banco de dados está vazio.")
        st.stop()

# --- 3. FILTROS E CATEGORIAS ---
st.write("---")
c1, c2, c3, c4 = st.columns([1, 1, 1, 1])

with c1:
    # Definindo limites do calendário baseados no banco
    min_banco = st.session_state.df_transacoes["data"].min().date()
    max_banco = st.session_state.df_transacoes["data"].max().date()
    
    # Define o início como 30 dias atrás, respeitando o limite do banco
    data_inicio_default = max(min_banco, trinta_dias_atras)
    
    periodo = st.date_input(
        "📅 Filtrar por período", 
        value=(data_inicio_default, max_banco), 
        min_value=min_banco, 
        max_value=max_banco,
        format="DD/MM/YYYY"
    )

with c2:
    rules_filt = load_categories()
    cats_do_json = set(str(v) for v in rules_filt.values() if v)
    cats_no_df = set(st.session_state.df_transacoes["categoria"].unique())
    lista_filtro = sorted(cats_do_json.union(cats_no_df).union({"Sem categoria"}))
    categorias_sel = st.multiselect("📂 Filtrar por categoria", options=lista_filtro, default=[])

with c3:
    lista_bancos = sorted(st.session_state.df_transacoes["banco"].unique().tolist())
    bancos_sel = st.multiselect("🏦 Banco", options=lista_bancos, default=[])

with c4:
    busca = st.text_input("🔍 Buscar descrição", "").upper()

# --- 4. APLICAÇÃO DOS FILTROS NO DISPLAY ---
df_display = st.session_state.df_transacoes.copy()

# Filtro de Data dinâmico (Default 30 dias na inicialização)
if isinstance(periodo, tuple) and len(periodo) == 2:
    start_date, end_date = periodo
    df_display = df_display[(df_display["data"].dt.date >= start_date) & (df_display["data"].dt.date <= end_date)]

if categorias_sel:
    df_display = df_display[df_display["categoria"].isin(categorias_sel)]

if bancos_sel:
    df_display = df_display[df_display["banco"].isin(bancos_sel)]

if busca:
    df_display = df_display[df_display["descricao"].str.contains(busca, na=False)]

# --- 5. PREPARAÇÃO DO EDITOR ---
rules = load_categories()
categorias_do_json = set(str(v) for v in rules.values() if v)
categorias_no_df = set(st.session_state.df_transacoes["categoria"].unique())
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}

lista_categorias = sorted(categorias_do_json.union(categorias_no_df).union(categorias_fixas))
opcoes_dropdown = lista_categorias + ["➕ Adicionar nova..."]

st.write(f"Exibindo {len(df_display)} transações.")
df_para_editar = df_display.reset_index()
cols = ["SEL", "data", "descricao", "categoria", "valor", "banco", "id"]
df_para_editar = df_para_editar[cols]

df_editado_raw = st.data_editor(
    df_para_editar,
    key="editor_v32", 
    width='stretch',
    num_rows="dynamic",
    column_config={
        "id": None, 
        "SEL": st.column_config.CheckboxColumn("Sel", help="Marcar"),
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "descricao": st.column_config.TextColumn("Descrição"), 
        "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_dropdown),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
        "banco": st.column_config.TextColumn("Banco", disabled=True),
    },
)

# --- 6. AÇÕES EM MASSA ---
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

# --- 7. NOVA CATEGORIA ---
nova_cat_final = ""
if any(df_editado["categoria"] == "➕ Adicionar nova..."):
    with st.container(border=True):
        nova_cat_final = st.text_input("Nome da nova categoria:", key="new_cat_v32").strip()

# --- 8. SALVAMENTO E REPLICAÇÃO ---
st.divider()
b1, b2 = st.columns(2)
with b1:
    if st.button("💾 Salvar e Replicar", type="primary", key="save_v32"):
        if any(df_editado["categoria"] == "➕ Adicionar nova...") and not nova_cat_final:
            st.error("Escreva o nome da categoria no campo acima antes de salvar.")
            st.stop()
            
        st.toast("Processando regras...")
        
        # 1. Limpa cache de processamento de texto pois as regras vão mudar
        st.cache_data.clear()

        # 2. Sincroniza exclusões
        ids_vivos = set(df_editado.index)
        ids_originais = set(df_display.index)
        st.session_state.df_transacoes.drop(ids_originais - ids_vivos, inplace=True, errors='ignore')

        # 3. Trata nova categoria se existir
        if nova_cat_final:
            df_editado["categoria"] = df_editado["categoria"].replace("➕ Adicionar nova...", nova_cat_final)

        # 4. Atualiza o estado global com as edições da tabela
        st.session_state.df_transacoes.update(df_editado)

        # 5. REPLICAÇÃO E REGRAS (Onde estava o erro)
        # Geramos as descrições limpas para comparar em massa
        desc_limpas_total = st.session_state.df_transacoes["descricao"].apply(limpar_descricao_cached)
        
        for idx, row in df_editado.iterrows():
            # Definimos cat_row pegando o valor da coluna 'categoria' da linha atual
            cat_row = row["categoria"] 
            
            # Só criamos regra se houver uma categoria válida
            if pd.notna(cat_row) and cat_row not in ["Sem categoria", "➕ Adicionar nova...", "---"]:
                d_limpa = limpar_descricao_cached(row["descricao"])
                
                # Adiciona ao seu arquivo JSON de inteligência
                add_rule(d_limpa, cat_row)
                
                # Réplica automática: procura quem tem a mesma descrição limpa e está sem categoria
                mask = (desc_limpas_total == d_limpa) & \
                       (st.session_state.df_transacoes["categoria"].fillna("Sem categoria") == "Sem categoria")
                
                st.session_state.df_transacoes.loc[mask, "categoria"] = cat_row

        # 6. Salva no Banco de Dados SQL
        st.session_state.df_transacoes["SEL"] = False
        df_sql = st.session_state.df_transacoes.reset_index().drop(columns=["SEL"], errors='ignore')
        
        # Converte data para string para o SQLite aceitar
        df_sql["data"] = pd.to_datetime(df_sql["data"]).dt.strftime('%Y-%m-%d')
        
        save_all_changes(df_sql)
        
        # Limpa o estado para forçar recarregamento limpo no próximo rerun
        if "df_transacoes" in st.session_state:
            del st.session_state.df_transacoes
            
        st.success("✅ Salvo e Categorias Replicadas!")
        st.rerun()

with b2:
    if st.button("🔄 Recarregar Banco", key="reload_v32"):
        st.cache_data.clear() # Limpa caches ao recarregar manualmente
        if "df_transacoes" in st.session_state: 
            del st.session_state.df_transacoes
        st.rerun()