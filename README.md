# 💰 Sistema de Gestão Financeira Pessoal

Aplicativo web para controle de finanças pessoais com importação automática de faturas em PDF, captura de transações via SMS, lançamento manual e dashboard de análise. Desenvolvido com Streamlit e hospedado no Streamlit Cloud, com banco de dados PostgreSQL via Supabase.

---

## ✨ Funcionalidades

### 📥 Importação de Faturas
- Upload de faturas em PDF de múltiplos bancos
- Detecção automática do banco emissor
- Extração e normalização das transações
- Ajuste inteligente de datas para o período de competência (incluindo parcelas)
- Sistema de deduplicação em três camadas:
  - **Hash de fatura**: bloqueia reimportação da mesma fatura
  - **Duplicata SMS**: ignora transações já capturadas via SMS
  - **Duplicata manual**: ignora lançamentos manuais já existentes

### 📱 Importação de SMS
- Leitura de mensagens via arquivo `.txt` exportado ou texto colado diretamente
- Parser com regex para mensagens dos principais bancos brasileiros
- Captura em tempo real logo após a compra
- Deduplicação automática contra o banco de dados existente

### ✍️ Inclusão Manual
- Registro de gastos em dinheiro, PIX, saques e outros
- Seleção de banco, data, valor, descrição e categoria

### 📑 Gerenciamento de Transações
- Tabela editável com filtros por período, categoria, banco e descrição
- Edição inline de data, valor, descrição e categoria
- Ações em massa: alteração de categoria e exclusão de múltiplos registros
- Motor de categorização automática por regras (arquivo JSON)
- Propagação automática de regras: ao categorizar uma descrição, todas as ocorrências similares são atualizadas
- Suporte a nova categoria criada no momento da edição

### 📈 Dashboard
- Visão consolidada de gastos por período
- Filtros por banco e categoria
- Distinção entre gastos fixos e variáveis
- Gráficos de evolução e distribuição

### 📊 Orçamento
- Definição de metas mensais por categoria
- Acompanhamento de planejado vs. realizado
- Alertas de teto de gastos

---

## 🏗️ Arquitetura

```
finance_app/
├── 00_🏠_Home.py               # Página principal, autenticação e configurações
├── pages/
│   ├── 01_📥_Importação de faturas.py
│   ├── 02_📱_Importação de SMS.py
│   ├── 03_✍️_Inclusão_Manual.py
│   ├── 04_📑_Transações.py
│   ├── 05_📈_Dashboard.py
│   └── 06_📊_Orçamento.py
├── parsers/                    # Parser específico por banco
│   ├── bradescard.py
│   ├── bradesco.py
│   ├── caixa.py
│   ├── itau.py
│   ├── nubank.py
│   ├── santander.py
│   ├── bb.py
│   ├── mercado_pago.py
│   └── ca.py
├── bank_detector.py            # Detecção automática do banco pelo PDF
├── parser_router.py            # Orquestrador: detecção → parser → normalização
├── categorizer.py              # Motor de categorização por regras JSON
├── categories.json             # Base de regras de categorização
├── database.py                 # Camada de acesso ao banco de dados
├── ui.py                       # Estilos globais CSS
├── config.yaml                 # Configuração do sistema de autenticação
├── requirements.txt
└── runtime.txt
```

---

## 🏦 Bancos Suportados

| Banco | Parser |
|---|---|
| Bradescard (Amazon Mastercard) | `parsers/bradescard.py` |
| Bradesco | `parsers/bradesco.py` |
| Caixa Econômica Federal | `parsers/caixa.py` |
| Itaú | `parsers/itau.py` |
| Nubank | `parsers/nubank.py` |
| Santander | `parsers/santander.py` |
| Banco do Brasil | `parsers/bb.py` |
| Mercado Pago | `parsers/mercado_pago.py` |
| C&A Pay | `parsers/ca.py` |

Para SMS, os bancos suportados são: Caixa, Itaú, Nubank, Bradesco e Santander.

---

## 🛠️ Tecnologias

- **Frontend:** [Streamlit](https://streamlit.io/)
- **Banco de dados:** PostgreSQL via [Supabase](https://supabase.com/)
- **ORM/Query:** SQLAlchemy + psycopg2
- **Extração de PDF:** PyMuPDF (fitz)
- **Autenticação:** streamlit-authenticator
- **Análise de dados:** pandas, plotly

---

## 🚀 Como rodar localmente

### Pré-requisitos
- Python 3.12+
- Conta no Supabase com banco PostgreSQL configurado

### Instalação

```bash
git clone https://github.com/seu-usuario/finance_app.git
cd finance_app
pip install -r requirements.txt
```

### Configuração dos Secrets

Crie o arquivo `.streamlit/secrets.toml`:

```toml
[postgres]
url = "postgresql://usuario:senha@host:porta/banco"

[auth]
cookie_key = "sua_chave_secreta_aleatoria"
```

### Configuração do Streamlit

Crie ou edite `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#1D4ED8"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#262730"
textColor = "#fafafa"
font = "sans serif"

[server]
headless = true
```

### Executar

```bash
streamlit run 00_🏠_Home.py
```

Acesse em `http://localhost:8501`

---

## ☁️ Deploy no Streamlit Cloud

1. Faça o push do repositório para o GitHub (o arquivo `secrets.toml` **não** deve ser commitado — ele já está no `.gitignore`)
2. Acesse [share.streamlit.io](https://share.streamlit.io) e conecte seu repositório
3. Em **App settings → Secrets**, adicione o conteúdo do seu `secrets.toml`
4. Defina o arquivo principal como `00_🏠_Home.py`

---

## 🔒 Segurança

- Senhas armazenadas com hash bcrypt via streamlit-authenticator
- Autenticação baseada em cookies com chave secreta configurável
- Todas as queries parametrizadas (proteção contra SQL injection)
- Secrets nunca expostos no repositório (`.gitignore` configurado)
- Isolamento total por `user_id` em todas as queries

---

## 📋 Variáveis de ambiente necessárias

| Chave | Descrição |
|---|---|
| `postgres.url` | URL de conexão PostgreSQL completa |
| `auth.cookie_key` | Chave secreta para assinatura dos cookies de sessão |

---

## 🗄️ Estrutura do Banco de Dados

```sql
-- Usuários
CREATE TABLE usuarios (
    username TEXT PRIMARY KEY,
    email    TEXT UNIQUE,
    name     TEXT,
    password TEXT  -- hash bcrypt
);

-- Transações financeiras
CREATE TABLE transacoes (
    id          SERIAL PRIMARY KEY,
    data        DATE,
    descricao   TEXT,
    valor       NUMERIC,
    categoria   TEXT,
    banco       TEXT,
    hash_fatura TEXT,   -- NULL para lançamentos manuais
    user_id     TEXT
);

-- Metas de orçamento mensais
CREATE TABLE orcamentos (
    id        SERIAL PRIMARY KEY,
    categoria TEXT,
    valor     NUMERIC,
    mes       INTEGER,
    ano       INTEGER,
    user_id   TEXT
);

-- Configuração de categorias fixas
CREATE TABLE config_categorias (
    categoria TEXT,
    is_fixo   BOOLEAN,
    user_id   TEXT,
    PRIMARY KEY (categoria, user_id)
);
```

---

## 🤝 Contribuindo

Pull requests são bem-vindos. Para mudanças maiores, abra uma issue primeiro para discutir o que você gostaria de alterar.

---

## 📄 Licença

Uso pessoal. Sinta-se livre para adaptar para suas próprias necessidades.
