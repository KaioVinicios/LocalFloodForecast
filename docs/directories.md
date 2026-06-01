# Diretórios

Guia pasta-por-pasta do que vai onde, o que é versionado e por quê.

## Raiz

```
LocalFloodForecast/
├── README.md              versionado  — visão geral do projeto
├── CLAUDE.md              versionado  — instruções p/ Claude Code (gitignored? não — checked in)
├── requirements.txt       versionado  — pip freeze do .venv
├── .gitignore             versionado
├── .venv/                 NÃO versionado — ambiente Python local
├── data/                  parcialmente versionado (só o marker do Drive)
├── docs/                  versionado — documentação + artigo
└── src/                   versionado — código
```

## data/

CSVs do ERA5. **Os CSVs em si não são versionados** (volumosos e
distribuídos via Drive). Único arquivo versionado: o marcador
explicando onde baixar.

```
data/
├── GoogleDriveDataExample.md            versionado — link e instruções
└── reanalysis-era5-single-levels-…csv   NÃO versionado — ~50 MB típico
```

Para popular esta pasta:
- **Opção A** (rápida): baixe do Drive citado em
  [GoogleDriveDataExample.md](../data/GoogleDriveDataExample.md).
- **Opção B** (do zero): rode `python src/hooks/era5_api.py` (precisa de
  credencial Copernicus em `~/.cdsapirc`).

O nome do arquivo está hardcoded em
[config.py:DATA_PATH](../src/flood/config.py); ajuste se baixar com
outro nome.

## docs/

Materiais de apoio. Tudo versionado.

```
docs/
├── README.md                        índice da documentação
├── architecture.md                  módulos + dependências + fluxo
├── methods.md                       ML/stats em detalhe
├── directories.md                   este arquivo
├── faq.md                           perguntas comuns
├── TODO_evolucoes_analiticas.md     roadmap das 3 evoluções pendentes
└── artigo_v1.pdf                    artigo de referência (binário OK aqui)
```

Convenções:
- Markdown puro, sem frontmatter ou geradores estáticos.
- `.pdf` é OK aqui (volume baixo, material de referência estável).
- Não colocar diagramas binários grandes (>500 KB) — preferir SVG
  inline ou ASCII art como nos outros docs.

## src/

Todo o código do projeto. Tudo versionado.

```
src/
├── main.py             entry-point: roda o pipeline completo
├── main.ipynb          LEGADO — referência histórica, não editar
├── flood/              pacote modular do pipeline
├── hooks/              scripts auxiliares one-off
└── graphics/           NÃO versionado — saída das execuções
```

### src/main.py
Único entry-point. Não importa de `main.ipynb` nem vice-versa. Rode com
`python src/main.py`. Logs no console + saída em `src/graphics/<ts>/`.

### src/main.ipynb
Notebook original do projeto, mantido como **referência histórica
apenas**. Não é executado pelo pipeline e não deve receber novas
mudanças — qualquer evolução acontece em `src/main.py` + `src/flood/`.
Se um dia ele atrapalhar, pode ser removido sem perda funcional.

### src/flood/
Pacote do pipeline. Cada módulo tem uma responsabilidade isolada. Ver
[architecture.md](architecture.md) para o detalhamento.

```
src/flood/
├── __init__.py        marca pacote (essencialmente vazio)
├── config.py          hiperparâmetros + caminhos + justificativas
├── data.py            load_data + resample 6h
├── features.py        engineer_features + scale_features
├── model.py           detect_anomalies_iso/lof + cluster_regimes + flag + pca
├── diagnostics.py     run_diagnostics (sweeps + figura matplotlib)
└── viz.py             tema dark + builders de figuras + escrita de CSVs
```

### src/hooks/
Scripts auxiliares **one-off** (não fazem parte do pipeline). Rodam
sozinhos, não importam do pacote `flood/`.

```
src/hooks/
└── era5_api.py        download de dados ERA5 via cdsapi (precisa de credencial)
```

Convenção: scripts aqui são executados manualmente, gravam em `data/`
e não têm dependência circular com o resto do código.

### src/graphics/
Saída das execuções. **Git-ignored** — cada `python src/main.py` cria um
novo subdiretório carimbado pelo timestamp. Nada aqui é commitado.

```
src/graphics/
├── 2026-06-01_094230/   uma execução
├── 2026-06-01_101246/   outra
└── …
```

## src/graphics/&lt;timestamp&gt;/

Cada subdiretório tem 9 figuras + 2 CSVs gerados por uma execução do
`main.py`.

| Arquivo | Tamanho típico | O que mostra |
|---|---|---|
| `timeline_iso.png` | ~360 KB | Densidade rolante de anomalias + flood risk (Iso) + precip suavizada, com top-5 eventos anotados. |
| `timeline_lof.png` | ~350 KB | Idem para LOF. |
| `pca.png` | ~1,2 MB | Scatter PCA dos 4 clusters; estrelas laranja = flood_risk_flag_iso. |
| `method_comparison.png` | ~620 KB | Esquerda: barra (só Iso / só LOF / ambos). Direita: scatter PCA por categoria. Título mostra Jaccard. |
| `cluster_profiles.svg` | ~50 KB | Médias de precip, vento e rajada por cluster. Cluster de risco em laranja. |
| `feature_explorer.png` | ~430 KB | Grid 3×4 com a série temporal de cada uma das 11 features brutas. |
| `seasonality.svg` | ~80 KB | Heatmap ano × mês de eventos sinalizados (Iso), com contagens sobrepostas. |
| `distributions.svg` | ~120 KB | Box plots das 6 features mais relevantes por cluster. |
| `diagnostics.svg` | ~130 KB | Grid 2×3: elbow, silhouette, PCA evr, sensibilidade Iso, sensibilidade LOF, Jaccard Iso×LOF. |
| `flagged_events_iso.csv` | ~15 KB | 293 linhas: cada timestep sinalizado pelo Iso (data, tp, t, vento, rajada, pressão, score, cluster). |
| `flagged_events_lof.csv` | ~1,3 KB | 25 linhas, mesmo schema, para LOF. |

Total por execução: **~3,3 MB**.

Como inspecionar:
- Macro-tendência: abra `timeline_iso.png` e `timeline_lof.png` lado a
  lado.
- Concordância entre métodos: `method_comparison.png`.
- Estrutura dos clusters: `pca.png` + `cluster_profiles.svg`.
- Hiperparâmetros: `diagnostics.svg`.
- Lista de eventos para investigação: `flagged_events_*.csv`.

Como limpar:
```bash
rm -rf src/graphics/*    # apaga todas as execuções
```

Nada importante mora aqui — sempre regenerável rodando `main.py` de novo.
