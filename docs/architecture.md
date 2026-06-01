# Arquitetura

Visão do código por dentro. Cobre os módulos do pacote
[../src/flood/](../src/flood/), suas dependências e o fluxo de execução
disparado por [../src/main.py](../src/main.py).

## Visão de alto nível

```
src/main.py            (orquestrador, logs, persistência)
   │
   └──► src/flood/     (pacote modular do pipeline)
           ├── config.py       (constantes + caminhos)
           ├── data.py         (carga e reamostragem)
           ├── features.py     (engenharia + StandardScaler)
           ├── model.py        (Iso, LOF, KMeans, flag, PCA)
           ├── diagnostics.py  (validação empírica)
           └── viz.py          (matplotlib + escrita de CSVs)
```

`main.py` importa do pacote e delega; ele não conhece detalhes de
algoritmo. Cada módulo tem **uma responsabilidade isolada** e exporta
funções puras (entrada → saída), sem estado global.

## Grafo de dependências

```
config.py     ← (importado por todos os outros)
   ▲
   │
data.py     features.py     model.py     diagnostics.py     viz.py
                                                 ▲
                                                 │
                                            (não importa viz: por design,
                                             diagnostics produz a própria
                                             figura matplotlib)
```

Regras:
- Tudo lê de [config.py](../src/flood/config.py). Hiperparâmetros nunca
  ficam hardcoded em outros módulos.
- `data.py`, `features.py`, `model.py` não conhecem nada de viz — só
  manipulam DataFrames e arrays NumPy.
- `viz.py` não importa `model.py`. Ele recebe o DataFrame já processado
  e desenha. Inverter essa dependência facilita testar o modelo sem
  matplotlib instalado.
- `diagnostics.py` constrói sua própria figura matplotlib (não usa
  helpers de `viz.py`) para ficar autocontido.

## Módulos em detalhe

### [config.py](../src/flood/config.py)
Fonte única de hiperparâmetros (RESAMPLE_FREQ, ISO_*, LOF_*, N_CLUSTERS,
KMEANS_N_INIT, RISK_RANK_SPEC, PCA_N_COMPONENTS, RANDOM_STATE), caminhos
absolutos (PROJECT_ROOT, DATA_PATH, OUTPUT_DIR) e a lista FEATURES. Cada
constante carrega um comentário com a justificativa da escolha (ver
detalhamento em [methods.md](methods.md)).

### [data.py](../src/flood/data.py)
Função única `load_data(path, resample_freq)`: lê o CSV com
`parse_dates=["valid_time"]`, reamostra para janelas de 6h via
`resample("6h").mean()` (ressalva: `tp` vira taxa média, não soma — a
correção está pendente no [TODO](TODO_evolucoes_analiticas.md#2-corrigir-agregação-do-tp)).

### [features.py](../src/flood/features.py)
- `engineer_features(df)`: adiciona `wind_speed_10m`, `wind_speed_100m`
  (`hypot` de u/v), `dewpoint_depression` (`t2m - d2m`) e `msl_tendency`
  (`msl.diff()`).
- `scale_features(df, features=FEATURES)`: aplica `StandardScaler` e
  retorna `(X_scaled, scaler)`.

### [model.py](../src/flood/model.py)
Cinco funções, cada uma adicionando colunas ao DataFrame:

| Função | Adiciona |
|---|---|
| `detect_anomalies_iso(df, X)` | `anomaly_label_iso`, `anomaly_raw_iso`, `is_anomaly_iso` |
| `detect_anomalies_lof(df, X)` | `anomaly_label_lof`, `anomaly_raw_lof`, `is_anomaly_lof` |
| `cluster_regimes(df, X)` | `cluster`, `in_flood_cluster`; retorna também `stats`, `flood_cluster` |
| `flag_flood_risk(df)` | `flood_risk_flag_iso`, `flood_risk_flag_lof` |
| `project_pca(df, X)` | `pca1`, `pca2` (só visualização) |

O **sufixo `_iso`/`_lof`** é convenção para flags paralelas — ambos
detectores rodam e produzem colunas separadas; cabe ao consumidor
escolher qual usar. Visto em ação em
[fig_timeline](../src/flood/viz.py) (parametrizado por `method`).

### [diagnostics.py](../src/flood/diagnostics.py)
Função única `run_diagnostics(df, X_scaled, ks, contam_grid,
lof_neighbors_grid)` que faz três sweeps independentes:
1. KMeans para k ∈ [2,8] → inércia (elbow) + silhouette.
2. IsolationForest para contamination ∈ {1%, 2%, 5%, 10%} → contagem.
3. LOF para n_neighbors ∈ {10, 20, 30, 50} → contagem + Jaccard com Iso
   de referência.

Retorna uma figura matplotlib 2×3 + imprime um bloco `[diagnóstico]` no
console. **Não muta `df`** e é independente do resto do pipeline (pode
ser removido sem impacto funcional).

### [viz.py](../src/flood/viz.py)
- Tema dark via `apply_theme()` (rcParams matplotlib).
- Builders por figura: `fig_timeline(df, method)`, `fig_pca(df,
  flood_cluster, pca_var, method)`, `fig_method_comparison(df,
  flood_cluster)`, `fig_cluster_profiles`, `fig_feature_explorer`,
  `fig_seasonality(df, method)`, `fig_distributions`.
- Persistência: `save_figures(figs, out_dir, per_fig_fmt, dpi)` e
  `save_flagged_csv(df, out_path, method)`.

Cada `fig_*` retorna um `matplotlib.figure.Figure`; quem salva é o
`main.py`. Isso permite, em testes ou em notebooks, criar uma figura
sem tocar o disco.

## Fluxo de execução (`main.py`)

```
1. load_data                       → 38.292 linhas (resample 6h)
2. engineer_features                → 4 colunas derivadas
3. scale_features                   → X_scaled (38.292 × 11)
4. detect_anomalies_iso             → ~1.915 anomalias (5%)
5. detect_anomalies_lof             → ~1.915 anomalias (5%)
6. cluster_regimes                  → 4 clusters; identifica flood_cluster
7. flag_flood_risk                  → flood_risk_flag_iso (~293), _lof (~25)
8. project_pca                      → pca1, pca2 (54,9% da variância)
9. _comparison_metrics              → Jaccard, overlap, contagens
10. apply_theme + run_diagnostics    → diag_fig
11. build_figures                    → 9 matplotlib Figures
12. save_figures + save_flagged_csv  → 11 arquivos em src/graphics/<ts>/
```

Cada etapa é envolta no context manager `step(label)` em
[main.py](../src/main.py) que cronometra e loga começo/fim + métricas-chave.

## Padrões e convenções

- **Config como SSoT.** Mudar um hiperparâmetro = editar uma linha em
  `config.py` e re-executar. Nada disso fica espalhado por main/model/viz.
- **Sufixo `_iso` / `_lof`** para tudo que é paralelo entre detectores.
  Consumidores parametrizam via `method="iso"|"lof"`.
- **Saída carimbada por timestamp.** `OUTPUT_DIR / "<YYYY-MM-DD_HHMMSS>"`
  evita sobrescrever execuções anteriores e facilita comparações.
- **Tema dark consistente.** Constantes em `viz.py` (DARK_BG, CARD_BG,
  GRID, FG, COLORS, ACCENT, ANOMALY, RISK) — qualquer nova figura
  herda o look chamando `apply_theme()` antes.
- **PNG para denso, SVG para enxuto.** Configurado por `per_fig_fmt` no
  `save_figures`. Mantém timeline/PCA leves e perfis/heatmaps nítidos
  em qualquer zoom.
- **`run_diagnostics` é opcional.** Pode ser comentado em `main.py` sem
  quebrar o pipeline (a figura `diagnostics.svg` simplesmente some).

## O que NÃO está aqui

- Nenhum estado global, singleton ou cache entre execuções.
- Nenhum modelo serializado (`.pkl`, `.joblib`). Cada `main.py` re-treina.
- Nenhum servidor, banco de dados ou dependência externa em runtime
  além de leitura do CSV em `data/`.
- Nenhum teste automatizado configurado. Verificação é manual
  (inspecionar logs + figuras).
