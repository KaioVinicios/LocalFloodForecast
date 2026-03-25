# 🌊 Modelo Preditivo de Inundações Costeiras

> Projeto desenvolvido para a disciplina de Inteligência Artificial / Machine Learning  
> Previsão de inundações marítimas com **24 horas de antecedência** utilizando dados climáticos do ERA5

---

## 📋 Descrição do Projeto

Este projeto tem como objetivo desenvolver um modelo preditivo capaz de identificar condições climáticas que precedem eventos de inundação costeira, emitindo alertas com até **24 horas de antecedência**.

A abordagem combina técnicas de **aprendizado não supervisionado** (clustering) e **aprendizado supervisionado** (classificação), formando um pipeline completo de Machine Learning aplicado a dados oceanográficos e meteorológicos históricos.

O problema é tratado como uma série temporal: o modelo aprende padrões que **antecedem** eventos de inundação, e não apenas os descrevem no momento em que ocorrem. Para isso, são utilizadas *lag features* — representações defasadas no tempo das variáveis climáticas — que permitem ao modelo "enxergar o passado" para prever o futuro.

---

## 🗂️ Estrutura do Repositório

```
📦 coastal-flood-prediction
├── 📁 data/               # Dados brutos e processados (não versionados)
├── 📁 notebooks/          # Notebooks Jupyter de exploração e modelagem
│   ├── 01_download_era5.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_feature_engineering.ipynb
│   ├── 04_clustering.ipynb
│   └── 05_model_training.ipynb
├── 📁 src/                # Módulos Python reutilizáveis
│   ├── download.py
│   ├── features.py
│   └── model.py
├── 📁 models/             # Modelos treinados serializados
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📡 Dados Utilizados

### ERA5 — ECMWF Reanalysis v5

Os dados utilizados neste projeto são provenientes do **ERA5**, o conjunto de reanálise climática de quinta geração do Centro Europeu de Previsão de Tempo a Médio Prazo (ECMWF), disponibilizado gratuitamente pelo **Copernicus Climate Data Store (CDS)**.

🔗 **Link para os dados:** [ERA5 Single Levels Time Series — Copernicus CDS](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries?tab=overview)

### Variáveis Selecionadas

| Variável | Descrição | Relevância |
|---|---|---|
| `mean_sea_level_pressure` | Pressão ao nível do mar | Baixa pressão eleva o nível do mar (*storm surge*) |
| `10m_u_component_of_wind` | Componente zonal do vento | Empurra massa d'água em direção à costa |
| `10m_v_component_of_wind` | Componente meridional do vento | Idem ao acima, em outra direção |
| `significant_height_of_combined_wind_waves_and_swell` | Altura significativa das ondas | Indicador direto de risco costeiro |
| `total_precipitation` | Precipitação total | Contribui para inundação combinada (costeira + pluvial) |
| `sea_surface_temperature` | Temperatura da superfície do mar | Influencia a intensidade de sistemas de tempestade |

### Período e Resolução

- **Período:** 2000 – 2023
- **Resolução temporal:** 6 horas (00h, 06h, 12h, 18h UTC)
- **Resolução espacial:** 0.25° × 0.25° (~28 km)
- **Formato:** NetCDF (`.nc`), lido com a biblioteca `xarray`

### Por que NetCDF e não CSV?

O ERA5 é um dataset **multidimensional**: cada arquivo contém simultaneamente múltiplas variáveis, múltiplos pontos geográficos (latitude × longitude) e múltiplos instantes de tempo — formando um cubo de dados 3D `(tempo × latitude × longitude)`. Um CSV é uma tabela plana 2D e não representa bem essa estrutura.

O `xarray` é utilizado para manipular esse cubo de forma eficiente. O CSV entra apenas **após o processamento**, quando o cubo é reduzido a uma série temporal simples (média espacial da região) para alimentar o modelo:

```
NetCDF (cubo 3D) → xarray → média espacial → DataFrame → CSV (para o modelo de ML)
```

### Escopo Regional e Desempenho Computacional

O ERA5 global possui cerca de **1 milhão de células geográficas** por instante de tempo, totalizando centenas de GB de dados. Para viabilizar o projeto em máquinas convencionais, **não são utilizados dados globais** — o recorte espacial é feito diretamente na requisição da API via bounding box:

```python
'area': [-5, -40, -15, -30],  # [N, W, S, E] — apenas a região de interesse
```

Isso garante que o arquivo baixado tenha poucos GB (ou até MB), e que o DataFrame final de features tenha na ordem de ~35.000 linhas × ~30 colunas — processável em segundos pelo scikit-learn em qualquer máquina convencional.

> ⚠️ **Ajuste o bounding box** para a região costeira que o seu projeto está modelando antes de executar o download.

---

## ⚙️ Pipeline de Machine Learning

O projeto segue uma arquitetura em etapas, indo da coleta dos dados brutos até a geração de alertas:

```
ERA5 API (cdsapi)
      ↓
Dados NetCDF (xarray)
      ↓
Engenharia de Features Temporais
  → Lag features: t-6h, t-12h, t-18h, t-24h
  → Janelas deslizantes (médias móveis)
      ↓
Clustering Não Supervisionado
  → Identificação de padrões climáticos
  → Geração de rótulos (risco alto / baixo)
      ↓
Modelo Supervisionado de Classificação
  → Treinado com TimeSeriesSplit
  → Predição 24h à frente
      ↓
🚨 Alerta de Inundação Costeira
```

---

## 🤖 Técnicas Utilizadas

### 1. Engenharia de Features Temporais (*Lag Features*)
Transformação dos dados brutos em representações defasadas no tempo. O modelo recebe como entrada as condições climáticas das últimas 24 horas para prever o risco nas próximas 24 horas, evitando o vazamento de dados (*data leakage*).

### 2. Clustering Não Supervisionado
Como os dados históricos não possuem rótulos de "inundação", algoritmos de clustering são utilizados para descobrir padrões naturais nos dados e criar rótulos artificiais.

- **K-Means** — ponto de partida, rápido e interpretável
- **DBSCAN** — detecta outliers e padrões de geometria arbitrária, ideal para dados geoespaciais
- **Hierarchical Clustering** — análise exploratória da estrutura dos dados via dendrograma
- **Métricas de avaliação:** Silhouette Score, Davies-Bouldin Index

### 3. Classificação Supervisionada
Com os rótulos gerados pelo clustering e validados com registros históricos, um classificador é treinado para prever eventos futuros.

- **Random Forest** — modelo principal, robusto a ruído e interpretável via importância de features
- **Gradient Boosting (XGBoost)** — modelo alternativo de alta performance
- **Regressão Logística** — baseline para comparação

### 4. Validação Temporal
Uso obrigatório de **TimeSeriesSplit** em vez de KFold convencional, respeitando a ordem cronológica dos dados e evitando contaminação entre treino e teste.

---

## 🛠️ Ferramentas e Ambiente

| Categoria | Ferramenta |
|---|---|
| **Editor** | VSCode + extensão Jupyter |
| **Versionamento** | Git + GitHub |
| **Ambiente Python** | `conda` ou `venv` |
| **Acesso aos dados** | `cdsapi` (API Copernicus) |
| **Leitura de dados** | `xarray`, `netCDF4` |
| **Manipulação** | `pandas`, `numpy` |
| **Visualização** | `matplotlib`, `seaborn`, `folium` |
| **Machine Learning** | `scikit-learn`, `xgboost` |
| **Limpeza de notebooks** | `nbstripout` (para commits no Git) |

---

## 🚀 Como Executar

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/coastal-flood-prediction.git
cd coastal-flood-prediction
```

### 2. Crie o ambiente virtual e instale as dependências
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. Configure as credenciais do Copernicus CDS
Crie o arquivo `~/.cdsapirc` com suas credenciais (cadastro gratuito em [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu)):

```
url: https://cds.climate.copernicus.eu/api/v2
key: SEU-UID:SUA-API-KEY
```

### 4. Execute os notebooks na ordem
```
01 → Download dos dados ERA5
02 → Análise exploratória
03 → Engenharia de features
04 → Clustering e rotulagem
05 → Treinamento e avaliação do modelo
```

---

## 📦 Dependências (`requirements.txt`)

```
cdsapi
xarray
netCDF4
pandas
numpy
matplotlib
seaborn
folium
scikit-learn
xgboost
jupyter
nbstripout
```

---

## 👥 Equipe

| Nome | GitHub |
|---|---|
| João Victor Lyra | [@joaovictorlyra](https://github.com/joaovictorlyra) |
| William Andrade Santana | [@williamandradesantana](https://github.com/williamandradesantana) |
| Kaio Vinícios da Silva Gois | [@KaioVinicios](https://github.com/KaioVinicios) |

---

## 📄 Licença

Este projeto é desenvolvido para fins acadêmicos.  
Os dados do ERA5 são disponibilizados sob a [Licença Copernicus](https://cds.climate.copernicus.eu/api/v2/terms/static/licence-to-use-copernicus-products.pdf).
