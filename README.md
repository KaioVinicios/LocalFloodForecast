# LocalFloodForecast

> Detecção não supervisionada de eventos de cheia costeira em séries de
> reanálise climática ERA5. Projeto da disciplina de Inteligência
> Artificial / Machine Learning.

---

## Visão geral

O pipeline identifica, em uma série temporal de variáveis meteorológicas,
os instantes cujas condições são **anômalas e típicas de cheia costeira**.
A abordagem é **inteiramente não supervisionada** e combina dois
detectores de anomalia rodando em paralelo com um clustering de regimes:

- **IsolationForest** — isola os ~5% de instantes globalmente mais atípicos.
- **Local Outlier Factor (LOF)** — isola os ~5% de instantes anômalos em
  relação à densidade local da vizinhança.
- **KMeans** — agrupa os instantes em 4 regimes meteorológicos e elege o
  cluster de risco por ranking de assinaturas de tempestade (alta
  precipitação + baixa pressão + rajadas fortes).

Para cada detector, `flood_risk_flag = is_anomaly & in_flood_cluster`. Os
dois flags são mantidos em paralelo (`flood_risk_flag_iso` /
`flood_risk_flag_lof`) e comparados via Jaccard, overlap por método e
categorias mutuamente exclusivas (só Iso, só LOF, ambos).

Não há classificador supervisionado, train/test split, predição com
antecedência nem modelo serializado — o foco é **detecção sobre o
histórico**. A evolução do projeto (agrupamento de timesteps em eventos,
correção da agregação de `tp`, validação contra cheias reais) está
trackada em [docs/TODO_evolucoes_analiticas.md](docs/TODO_evolucoes_analiticas.md).

---

## Arquitetura

O ponto de entrada é o script [src/main.py](src/main.py), que orquestra um
**pacote modular** em [src/flood/](src/flood/). Cada módulo tem uma
responsabilidade isolada:

| Módulo | Responsabilidade |
|---|---|
| [config.py](src/flood/config.py) | Fonte única de hiperparâmetros e caminhos, com justificativas em comentário |
| [data.py](src/flood/data.py) | Carga do CSV ERA5 + reamostragem 6h |
| [features.py](src/flood/features.py) | Engenharia de features (`wind_speed_*`, `dewpoint_depression`, `msl_tendency`) + padronização |
| [model.py](src/flood/model.py) | `detect_anomalies_iso`, `detect_anomalies_lof`, `cluster_regimes`, `flag_flood_risk`, `project_pca` |
| [diagnostics.py](src/flood/diagnostics.py) | Validação empírica dos hiperparâmetros (elbow, silhouette, sensibilidade de `contamination` e `n_neighbors`, Jaccard Iso×LOF, variância PCA) |
| [viz.py](src/flood/viz.py) | Tema dark + builders de figuras estáticas (matplotlib) + escrita de CSVs |

A saída de cada execução vai para um diretório carimbado pelo timestamp
em [src/graphics/](src/graphics/) (git-ignored).

> O notebook [src/main.ipynb](src/main.ipynb) é mantido **apenas como
> material de referência histórico** e não acompanha mais a evolução do
> pipeline — toda execução acontece via `src/main.py`.

---

## Estrutura do repositório

```
LocalFloodForecast
├── data/                      # CSVs do ERA5 (não versionados — ver Drive)
├── docs/                      # Artigo de referência + TODO de evoluções
├── src/
│   ├── main.py                # Entry-point: roda pipeline + gera saídas
│   ├── main.ipynb             # Notebook de referência (legado, não editar)
│   ├── flood/                 # Pacote do pipeline (config/data/features/model/diagnostics/viz)
│   ├── graphics/              # Saídas por execução (git-ignored)
│   └── hooks/
│       └── era5_api.py        # Download dos dados ERA5 via cdsapi
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Dados

### ERA5 — ECMWF Reanalysis v5

Reanálise climática de quinta geração do ECMWF, disponibilizada pelo
**Copernicus Climate Data Store (CDS)**.

- **Conjunto:** [ERA5 Single Levels Time Series — Copernicus CDS](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries?tab=overview)
- **Local:** ponto único `longitude 19.25, latitude 31` — Mar Mediterrâneo,
  ao largo da costa da Líbia. *(Ajuste em [src/hooks/era5_api.py](src/hooks/era5_api.py)
  para outra região.)*
- **Período:** `2000-01-01` a `2026-03-17`
- **Granularidade bruta:** horária → ~229.752 registros
- **Reamostragem do pipeline:** janelas de **6 horas** → **38.292 linhas**
- **Formato:** CSV (lido direto com `pandas`, sem NetCDF/`xarray`)
- **Distribuição dos arquivos:** ver [data/GoogleDriveDataExample.md](data/GoogleDriveDataExample.md)

### Variáveis e features

O download traz 17 variáveis brutas; o pipeline usa 11 após engenharia
de features:

| Coluna | Origem | Significado |
|---|---|---|
| `tp` | ERA5 bruta | Precipitação total |
| `msl` | ERA5 bruta | Pressão ao nível do mar |
| `msl_tendency` | derivada (`msl.diff`) | Queda rápida → tempestade chegando |
| `wind_speed_10m` | derivada (`hypot(u10, v10)`) | Magnitude do vento a 10 m |
| `wind_speed_100m` | derivada (`hypot(u100, v100)`) | Magnitude do vento a 100 m |
| `fg10` | ERA5 bruta | Rajada de vento a 10 m |
| `dewpoint_depression` | derivada (`t2m − d2m`) | Baixa → ar úmido, potencial de chuva |
| `t2m` | ERA5 bruta | Temperatura a 2 m |
| `ssrd` | ERA5 bruta | Radiação solar descendente |
| `strd` | ERA5 bruta | Radiação térmica descendente |
| `sp` | ERA5 bruta | Pressão à superfície |

Excluídas de propósito: componentes brutas `u10/v10/u100/v100` (substituídas
pelas magnitudes), `d2m` (já capturado via `dewpoint_depression`), `sst`/`skt`
(vínculo indireto), `latitude`/`longitude` (constantes — ponto único).

---

## Pipeline

```
ERA5 CSV
   │
   ▼
load_data        → resample 6h (mean) → 38.292 linhas
   │
   ▼
engineer_features → wind_speed_10m/100m, dewpoint_depression, msl_tendency
   │
   ▼
scale_features    → StandardScaler sobre as 11 features
   │
   ├──► detect_anomalies_iso  → is_anomaly_iso  (IsolationForest, 5%)
   ├──► detect_anomalies_lof  → is_anomaly_lof  (LOF, 5%, k=20)
   └──► cluster_regimes       → cluster (KMeans, k=4) + in_flood_cluster
   │
   ▼
flag_flood_risk
   ├──► flood_risk_flag_iso = is_anomaly_iso & in_flood_cluster
   └──► flood_risk_flag_lof = is_anomaly_lof & in_flood_cluster
   │
   ▼
project_pca (2 componentes) — só para visualização
   │
   ▼
run_diagnostics + builders de figuras → src/graphics/<timestamp>/
```

### Hiperparâmetros (justificados em [config.py](src/flood/config.py))

| Parâmetro | Valor | Como foi escolhido |
|---|---|---|
| `RESAMPLE_FREQ` | `"6h"` | Suaviza ruído sub-horário, preserva escala sinótica (00/06/12/18 UTC) |
| `ISO_N_ESTIMATORS` | `200` | Estabiliza o anomaly score; retorno decrescente acima disso |
| `ISO_CONTAMINATION` | `0.05` | ~5% dos timesteps → ~1.915 anomalias (~74/ano); validado em diagnostics |
| `LOF_N_NEIGHBORS` | `20` | Default sklearn; varredura {10, 20, 30, 50} no diagnostics mostra Jaccard com Iso variando só 8,99%→11,30% |
| `LOF_CONTAMINATION` | igual ao Iso | Mantido para comparação justa |
| `N_CLUSTERS` | `4` | **Validado**: silhouette máximo em k=4 (0,215) na varredura k=2..8 |
| `KMEANS_N_INIT` | `20` | Acima do default p/ estabilizar clusters entre execuções |
| `PCA_N_COMPONENTS` | `2` | Visualização apenas; PC1+PC2 retêm 54,9% da variância |
| `RANDOM_STATE` | `42` | Reprodutibilidade determinística |

O **cluster de risco** é eleito por `flood_risk_score = soma de postos`
das 3 assinaturas: alta `tp` + baixa `msl` + rajada `fg10` forte. Definido
em [model.py:cluster_regimes](src/flood/model.py).

---

## Saídas

Cada execução grava em `src/graphics/<YYYY-MM-DD_HHMMSS>/`:

| Arquivo | Conteúdo | Formato |
|---|---|---|
| `timeline_iso.png` | Densidade rolante 30d de anomalias + flood risk + precip suavizada (IsolationForest) | PNG |
| `timeline_lof.png` | Idem para LOF | PNG |
| `pca.png` | Scatter PCA dos 4 clusters + flags Iso sobrepostas | PNG |
| `method_comparison.png` | Barras (só Iso / só LOF / ambos) + PCA 4-categorias | PNG |
| `cluster_profiles.svg` | Médias de precip/vento/rajada por cluster | SVG |
| `feature_explorer.png` | Grid 3×4 de séries temporais das 11 features brutas | PNG |
| `seasonality.svg` | Heatmap ano × mês de eventos sinalizados | SVG |
| `distributions.svg` | Box plots das features por cluster | SVG |
| `diagnostics.svg` | 2×3: elbow, silhouette, PCA evr, sensibilidade contamination (Iso), sensibilidade n_neighbors (LOF), Jaccard Iso×LOF | SVG |
| `flagged_events_iso.csv` | Timesteps sinalizados pelo Iso (data, tp, vento, rajada, pressão, score, cluster) | CSV |
| `flagged_events_lof.csv` | Idem para LOF | CSV |

Tamanho total típico: **~3,3 MB / execução**. Diretório git-ignored.

### Logs de execução

O script registra timing por etapa, contagens-chave e um bloco
`[comparação Iso × LOF]` com Jaccard, overlap por método e contagens das
4 categorias mutuamente exclusivas — tanto na camada de anomalia bruta
quanto após interseção com o cluster de risco.

---

## Como executar

### 1. Clone o repositório
```bash
git clone https://github.com/KaioVinicios/LocalFloodForecast.git
cd LocalFloodForecast
```

### 2. Crie o ambiente e instale as dependências
```bash
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
.venv\Scripts\activate             # Windows

pip install -r requirements.txt
```

### 3. (Opcional) Configure credenciais do Copernicus CDS

Necessário **apenas** se for baixar dados novos com
[src/hooks/era5_api.py](src/hooks/era5_api.py). Cadastro gratuito em
[cds.climate.copernicus.eu](https://cds.climate.copernicus.eu). Crie
`~/.cdsapirc`:
```
url: https://cds.climate.copernicus.eu/api/v2
key: SUA-API-KEY
```

### 4. Obtenha os dados
Baixe o CSV do Drive (ver [data/GoogleDriveDataExample.md](data/GoogleDriveDataExample.md))
para a pasta `data/`, **ou** gere o seu próprio:
```bash
python src/hooks/era5_api.py
```

### 5. Rode o pipeline
```bash
python src/main.py
```

Tempo típico: **~40s** em laptop moderno (a etapa mais cara é o
`run_diagnostics`, que treina KMeans 7× + IsolationForest 4× + LOF 4×
para a varredura de hiperparâmetros). Saída final aparece em
`src/graphics/<timestamp>/`.

---

## Ferramentas

| Categoria | Ferramenta |
|---|---|
| Editor | VSCode |
| Versionamento | Git + GitHub |
| Python | 3.14 em `.venv/` |
| Acesso aos dados | `cdsapi` (API Copernicus) |
| Manipulação | `pandas`, `numpy` |
| Machine Learning | `scikit-learn` (IsolationForest, LocalOutlierFactor, KMeans, PCA, StandardScaler) |
| Visualização | `matplotlib` (saída estática PNG/SVG) |

---

## Roadmap

As próximas evoluções estão trackadas em
[docs/TODO_evolucoes_analiticas.md](docs/TODO_evolucoes_analiticas.md):

1. **Agrupar timesteps em eventos atômicos** — colapsar runs consecutivos
   de `flood_risk_flag_*` num único evento (com início, fim, duração, pico).
2. **Corrigir agregação de `tp`** — passar de média para soma no resample
   6h (semanticamente correto para precipitação acumulada).
3. **Validação contra cheias reais** — cruzar as datas sinalizadas com
   eventos documentados (curadoria manual em `data/known_floods.csv`) e
   calcular precision/recall por método.

Mais distante (não planejado em detalhe):

- Modelo preditivo com 24h de antecedência (lag features, `TimeSeriesSplit`,
  classificador supervisionado).
- Algoritmos adicionais de clustering (DBSCAN, hierárquico).
- Análise multi-ponto / regional.

---

## Equipe

| Nome | GitHub |
|---|---|
| João Victor Lyra | [@joaovictorlyra](https://github.com/joaovictorlyra) |
| William Andrade Santana | [@williamandradesantana](https://github.com/williamandradesantana) |
| Kaio Vinícios da Silva Gois | [@KaioVinicios](https://github.com/KaioVinicios) |

---

## Licença

Projeto desenvolvido para fins acadêmicos. Os dados do ERA5 são
distribuídos sob a [Licença Copernicus](https://cds.climate.copernicus.eu/api/v2/terms/static/licence-to-use-copernicus-products.pdf).
