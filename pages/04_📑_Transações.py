import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database import carregar_transacoes, get_authenticator, get_engine, save_all_changes, deletar_transacoes
from categorizer import load_categories, add_rule, clean_description, find_category
from ui import apply_global_style
from sqlalchemy import text
from utils.finance_tools import gerar_projeções_parcelas

st.set_page_config(
    page_title="Gerenciamento de Transações",
    page_icon="📑",
    layout="wide"
)

# --- 1. AUTENTICAÇÃO E SEGURANÇA ---
authenticator = get_authenticator()
authenticator.login(location='unrendered')

if not st.session_state.get("authentication_status"):
    st.warning("Sessão expirada. Por favor, faça login na Home.")
    st.stop()

usuario_atual = st.session_state["username"]
apply_global_style()

# --- 2. FUNÇÕES AUXILIARES ---
@st.cache_data
def limpar_descricao_cached(descricao):
    return clean_description(descricao)

def aplicar_inteligencia_json(df):
    df_copy = df.copy()
    rules = load_categories()
    mask = (df_copy["categoria"] == "Sem categoria") | (df_copy["categoria"].isna())
    
    if mask.any():
        df_copy.loc[mask, "categoria"] = df_copy.loc[mask, "descricao"].apply(
            lambda x: find_category(x, rules)
        )
    return df_copy

# --- 3. TÍTULO E CARREGAMENTO ---
st.title("📑 Transações")
st.subheader("Edição, exclusão, categorização e ações em massa")

if "df_transacoes" not in st.session_state:
    df = carregar_transacoes(usuario_atual) 
    
    if df is not None and not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors='coerce')
        df["valor"] = pd.to_numeric(df["valor"], errors='coerce')
        df = aplicar_inteligencia_json(df)
        df["SEL"] = False 
        st.session_state.df_transacoes = df.set_index("id")
        # Track original IDs for deletion detection
        st.session_state.original_transaction_ids = set(df["id"].tolist())
    else:
        df_vazio = pd.DataFrame(
            columns=["id", "SEL", "data", "descricao", "categoria", "valor", "banco", "hash_fatura", "user_id"]
        ).set_index("id")
        df_vazio["data"] = pd.to_datetime(df_vazio["data"])
        st.session_state.df_transacoes = df_vazio
        st.session_state.original_transaction_ids = set()
        st.info("📭 Nenhuma transação encontrada. Importe uma fatura, um SMS ou adicione um lançamento manual.")

# --- 4. FILTROS DE INTERFACE ---
st.write("---")
c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])

with c1:
    hoje = date.today()
    df_temp = st.session_state.df_transacoes
    tem_dados = not df_temp.empty and df_temp["data"].notna().any()
    
    # Menor data no banco para limitar o calendário no passado
    min_calendario = df_temp["data"].min().date() if tem_dados else hoje - timedelta(days=365)
    
    # Maior data no banco (pode ser uma projeção futura)
    max_calendario = df_temp["data"].max().date() if tem_dados else hoje
    
    # GARANTIA: Se a maior projeção for antes de hoje, o limite é hoje. 
    # Se houver projeções futuras, o calendário permite ir até lá.
    limite_final_calendario = max(hoje, max_calendario)

    # VALORES DEFAULT (O que aparece ao carregar a página)
    # Início: 30 dias atrás | Fim: Hoje (ignora projeções futuras no carregamento)
    data_inicio_default = hoje - timedelta(days=30)
    data_fim_default = hoje

    periodo = st.date_input(
        "📅 Período", 
        value=(data_inicio_default, data_fim_default), 
        min_value=min_calendario, 
        max_value=limite_final_calendario,
        format="DD/MM/YYYY"
    )

with c2:
    rules_filt = load_categories()
    cats_do_json = set(str(v) for v in rules_filt.values() if v)
    cats_no_df = set(st.session_state.df_transacoes["categoria"].unique())
    lista_filtro = sorted(cats_do_json.union(cats_no_df).union({"Sem categoria"}))
    categorias_sel = st.multiselect("📂 Categoria", options=lista_filtro)

with c3:
    if "banco" in st.session_state.df_transacoes.columns:
        lista_bancos = sorted(st.session_state.df_transacoes["banco"].dropna().unique().tolist())
        bancos_sel = st.multiselect("🏦 Banco", options=lista_bancos)
    else:
        bancos_sel = []

with c4:
    busca = st.text_input("🔍 Descrição", "").upper()

# --- 5. LÓGICA DE FILTRAGEM ---
df_display = st.session_state.df_transacoes.copy()
df_display["data"] = pd.to_datetime(df_display["data"], errors='coerce')

if isinstance(periodo, tuple) and len(periodo) == 2:
    start_date, end_date = periodo
    mask = (df_display["data"].dt.date >= start_date) & (df_display["data"].dt.date <= end_date)
    df_display = df_display[mask]

if categorias_sel:
    df_display = df_display[df_display["categoria"].isin(categorias_sel)]

if bancos_sel and "banco" in df_display.columns:
    df_display = df_display[df_display["banco"].isin(bancos_sel)]

if busca:
    df_display = df_display[df_display["descricao"].str.contains(busca, na=False, case=False)]

# --- 6. PREPARAÇÃO DO EDITOR ---
rules = load_categories()
categorias_do_json = set(str(v) for v in rules.values() if v)
categorias_no_df = set(st.session_state.df_transacoes["categoria"].unique()) if not st.session_state.df_transacoes.empty else set()
categorias_fixas = {"Alimentação", "Transporte", "Saúde", "Lazer", "Moradia", "Supermercado", "Sem categoria"}

lista_categorias = sorted(categorias_do_json.union(cats_no_df).union(categorias_fixas))
opcoes_dropdown = lista_categorias + ["➕ Adicionar nova..."]


# 1. Criamos a cópia para edição
df_para_editar = df_display.copy()

# 2. Transformamos o index (ID) em uma coluna real para que o editor a reconheça
df_para_editar = df_para_editar.reset_index()

# 3. Garantimos que a coluna SEL exista
if "SEL" not in df_para_editar.columns:
    df_para_editar.insert(0, "SEL", False)

# 4. REORDENAÇÃO CRUCIAL: Definimos a ordem exata das colunas.
# Colocamos 'SEL' primeiro e deixamos 'hash_fatura' e 'user_id' de fora da lista de visualização,
# mas elas continuam no DataFrame para não quebrar a lógica de salvamento.
cols_visiveis = ["SEL", "data", "descricao", "categoria", "valor", "banco", "id", "hash_fatura", "user_id"]
df_para_editar = df_para_editar[cols_visiveis]

# 5. RENDERIZAÇÃO DO EDITOR
df_editado = st.data_editor(
    df_para_editar,
    key="editor_v33", # Sugiro subir para v33 para resetar o layout no navegador
    width='stretch',
    num_rows="dynamic",
    column_config={
        "id": None,           # Oculta a coluna de ID
        "hash_fatura": None,  # Oculta a coluna de Hash
        "user_id": None,      # Oculta a coluna de User ID
        "SEL": st.column_config.CheckboxColumn("Sel", width="small", default=False),
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "descricao": st.column_config.TextColumn("Descrição"),
        "categoria": st.column_config.SelectboxColumn("Categoria", options=opcoes_dropdown),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
        "banco": st.column_config.TextColumn("Banco", disabled=True),
    },
    hide_index=True
)

# As edições são lidas diretamente de df_editado no botão salvar.

# --- 7. AÇÕES EM MASSA E PARCELAMENTO ---

st.write(f"Exibindo {len(df_para_editar)} transações.")

# Criamos colunas para os botões de seleção total
col_sel1, col_sel2, _ = st.columns([1, 1, 4])

with col_sel1:
    if st.button("✅ Selecionar Tudo", key="btn_sel_all"):
        st.session_state.df_transacoes.loc[df_display.index, "SEL"] = True
        st.rerun()

with col_sel2:
    if st.button("🔲 Desmarcar Tudo", key="btn_desel_all"):
        st.session_state.df_transacoes["SEL"] = False
        st.rerun()

# Identificação dos itens marcados
if df_editado is not None and not df_editado.empty:
    # Garante que usamos o ID como referência para não errar a linha
    df_massa = df_editado.set_index("id")
    ids_marcados = df_massa[df_massa["SEL"] == True].index.tolist()
else:
    ids_marcados = []

# LÓGICA DE INTERFACE DINÂMICA
if ids_marcados:
    # CASO 1: APENAS UMA TRANSAÇÃO SELECIONADA (Habilita Parcelamento)
    if len(ids_marcados) == 1:
        id_sel = ids_marcados[0]
        # Pegamos os dados da linha selecionada para exibir e processar
        transacao_para_parcelar = st.session_state.df_transacoes.loc[id_sel].to_dict()
        transacao_para_parcelar['id'] = id_sel

        with st.container(border=True):
            st.markdown("🗓️ **Desmembrar Compra Parcelada**")
            st.caption(f"Item: {transacao_para_parcelar['descricao']} | Valor: R$ {transacao_para_parcelar['valor']:.2f}")
            
            cp1, cp2, cp3 = st.columns([1, 1, 1])
            with cp1:
                x = st.number_input("Parcela Atual", min_value=1, value=1, key="p_atual_v32")
            with cp2:
                y = st.number_input("de Total", min_value=x, value=12, key="p_total_v32")
            with cp3:
                st.write("##") # Alinhamento vertical
                if st.button("🚀 Lançar Parcelas Futuras", width = 'stretch', key="btn_proj_v32"):
                    from utils.finance_tools import gerar_projeções_parcelas
                    from database import salvar_transacoes
                    
                    # 1. Gera as tuplas formatadas para o Postgres
                    projeções = gerar_projeções_parcelas(
                        transacao_para_parcelar, x, y, usuario_atual
                    )
                    
                    # 2. Salva no banco (Inteligência do database.py)
                    qtd_salva = salvar_transacoes(projeções, usuario_atual)
                    
                    if qtd_salva > 0:
                        st.success(f"✅ {qtd_salva} parcelas futuras lançadas!")
                        st.cache_data.clear()
                        if "df_transacoes" in st.session_state:
                            del st.session_state.df_transacoes
                        st.rerun()

    # CASO 2: AÇÕES EM MASSA (Uma ou mais transações)
    with st.container(border=True):
        st.markdown(f"⚡ **Ações em Massa:** {len(ids_marcados)} itens selecionados")
        c1, c2 = st.columns([2, 1])
        
        with c1:
            cat_massa = st.selectbox("Mudar categoria:", ["---"] + lista_categorias, key="cat_massa_v32")
            if cat_massa != "---" and st.button("Aplicar Categoria", key="btn_massa_v32"):
                st.session_state.df_transacoes.loc[ids_marcados, "categoria"] = cat_massa
                st.session_state.df_transacoes.loc[ids_marcados, "SEL"] = False
                st.rerun()
                
        with c2:
            st.write("##") 
            if st.button("🗑️ Excluir Selecionadas", type="secondary", key="btn_del_v32", width = 'stretch'):
                # Importamos a função de deletar do seu database.py
                from database import deletar_transacoes
                if deletar_transacoes(ids_marcados, usuario_atual):
                    st.session_state.df_transacoes.drop(ids_marcados, inplace=True)
                    st.success("Itens excluídos!")
                    st.rerun()

# --- 8. SALVAMENTO E REPLICAÇÃO ---
nova_cat_final = ""
if df_editado is not None and any(df_editado["categoria"] == "➕ Adicionar nova..."):
    with st.container(border=True):
        nova_cat_final = st.text_input("Nome da nova categoria:", key="new_cat_input").strip()

st.divider()
b1, b2 = st.columns(2)

with b1:
    if st.button("💾 Salvar Alterações", type="primary", key="save_v33"):
        try:
            with st.status("Sincronizando banco e propagando regras...") as status:
                # 1. PROCESSAR EDIÇÕES E PROPAGAR NA MEMÓRIA
                if df_editado is not None and not df_editado.empty:
                    df_editado_indexed = df_editado.set_index("id")
                    
                    for idx, row in df_editado_indexed.iterrows():
                        if idx in st.session_state.df_transacoes.index:
                            desc_atual = str(row["descricao"])
                            cat_selecionada = str(row["categoria"])
                            cat_anterior = str(st.session_state.df_transacoes.loc[idx, "categoria"])
                            
                            # Se você alterou a categoria para uma já existente
                            if cat_selecionada != "➕ Adicionar nova..." and cat_selecionada != cat_anterior:
                                # A) Aprende no JSON
                                add_rule(desc_atual, cat_selecionada)
                                
                                # B) PROPAGAÇÃO IMEDIATA NA TELA (Session State)
                                # Isso faz com que todos os "UBER" virem "Transporte" antes de salvar
                                mask = (st.session_state.df_transacoes["descricao"] == desc_atual) & \
                                       (st.session_state.df_transacoes["categoria"] == "Sem categoria")
                                st.session_state.df_transacoes.loc[mask, "categoria"] = cat_selecionada

                            # Atualiza a linha específica que você editou (Data, Valor, etc)
                            st.session_state.df_transacoes.loc[idx, "data"] = pd.to_datetime(row["data"])
                            st.session_state.df_transacoes.loc[idx, "descricao"] = desc_atual
                            st.session_state.df_transacoes.loc[idx, "categoria"] = cat_selecionada
                            st.session_state.df_transacoes.loc[idx, "valor"] = float(row["valor"])

                # 2. TRATAR NOVA CATEGORIA (Text Input)
                if nova_cat_final:
                    mask_nova = st.session_state.df_transacoes["categoria"] == "➕ Adicionar nova..."
                    descricoes_para_nova = st.session_state.df_transacoes.loc[mask_nova, "descricao"].unique()
                    
                    for d in descricoes_para_nova:
                        add_rule(d, nova_cat_final)
                    
                    # Aplica o nome da nova categoria em todas as linhas correspondentes
                    st.session_state.df_transacoes.loc[mask_nova, "categoria"] = nova_cat_final

                # 3. REMOVER TRANSAÇÕES EXCLUÍDAS
                current_ids = set(st.session_state.df_transacoes.index)
                original_ids = st.session_state.get("original_transaction_ids", set())
                deleted_ids = original_ids - current_ids
                if deleted_ids:
                    from database import deletar_transacoes
                    deletar_transacoes(list(deleted_ids), usuario_atual)

                # 4. SALVAR TUDO NO SQL (Incluindo as propagadas)
                df_para_sql = st.session_state.df_transacoes.reset_index()
                df_para_sql = df_para_sql.drop(columns=["SEL"], errors='ignore')
                df_para_sql["user_id"] = usuario_atual 
                
                from database import save_all_changes, get_engine
                n = save_all_changes(df_para_sql, usuario_atual)

                # 5. SQL DE PROPAGAÇÃO MASSIVA (Para o histórico fora da tela)
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE transacoes t SET categoria = m.categoria
                        FROM (
                            SELECT DISTINCT ON (descricao) descricao, categoria FROM transacoes
                            WHERE user_id = :u AND categoria != 'Sem categoria' AND categoria IS NOT NULL
                            ORDER BY descricao, id DESC
                        ) m
                        WHERE t.descricao = m.descricao AND t.user_id = :u AND t.categoria = 'Sem categoria';
                    """), {"u": usuario_atual})

                # 6. LIMPEZA FINAL
                st.cache_data.clear()
                if "df_transacoes" in st.session_state:
                    del st.session_state.df_transacoes
                
                status.update(label="✅ Salvo, JSON atualizado e categorias propagadas!", state="complete")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro: {e}")

with b2:
    if st.button("🔄 Recarregar Dados", key="reload_v32"):
        st.cache_data.clear()
        if "df_transacoes" in st.session_state: 
            del st.session_state.df_transacoes
        if "original_transaction_ids" in st.session_state:
            del st.session_state.original_transaction_ids
        st.rerun()