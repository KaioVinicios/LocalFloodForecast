# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Coastal-flood **event-detection** on ERA5 reanalysis. Fully unsupervised:
two anomaly detectors — **IsolationForest** and **Local Outlier Factor
(LOF)** — run in parallel and are each intersected with a **KMeans**
cluster-of-risk to produce two flags, `flood_risk_flag_iso` and
`flood_risk_flag_lof`. PCA is used only for 2D visualization. There are
no serialized models, no train/test split, and no supervised classifier.

Region: Mediterranean / Libyan coast (`longitude 19.25, latitude 31`),
2000-01-01 to 2026-03-17. After 6h resample: 38,292 rows.

For the user-facing overview see [README.md](README.md); for in-depth
material see [docs/](docs/) (start at [docs/README.md](docs/README.md)).

## Source layout

- [src/main.py](src/main.py) — **canonical entry point**. Orchestrates the
  pipeline, logs each step with timings + metrics, and writes all artifacts.
- [src/flood/](src/flood/) — pipeline as a modular package: `config.py`,
  `data.py`, `features.py`, `model.py`, `diagnostics.py`, `viz.py`. Each
  module has one isolated responsibility — see
  [docs/architecture.md](docs/architecture.md) for the dependency graph.
- [src/main.ipynb](src/main.ipynb) — **legacy reference only.** Do NOT
  edit it. Any pipeline evolution happens in `src/flood/` + `main.py`.
  Outputs (including base64 images) are committed, so the file is ~33 MB.
- [src/hooks/era5_api.py](src/hooks/era5_api.py) — one-off downloader
  via `cdsapi`.

## Commands

```bash
source .venv/bin/activate           # Python 3.14 venv in .venv/
pip install -r requirements.txt

python src/main.py                  # runs pipeline (~40s); outputs to src/graphics/<timestamp>/
python src/hooks/era5_api.py        # download fresh ERA5 (needs ~/.cdsapirc credentials)
```

`src/main.py` is **cwd-independent** (`PROJECT_ROOT` is derived from
`__file__`) — invoke from anywhere.

There are **no tests, linters, or build steps** configured. Don't invent
them; if you need one, ask.

## Pipeline at a glance

```
load_data (resample 6h) → engineer_features → scale_features
   │
   ├─ detect_anomalies_iso  → is_anomaly_iso  (IsolationForest, contamination=0.05)
   ├─ detect_anomalies_lof  → is_anomaly_lof  (LOF, contamination=0.05, n_neighbors=20)
   └─ cluster_regimes       → cluster + in_flood_cluster (KMeans, k=4 — silhouette-validated)
   │
flag_flood_risk → flood_risk_flag_{iso,lof} = is_anomaly_{iso,lof} & in_flood_cluster
project_pca     → pca1, pca2 (PC1+PC2 retain 54.9% variance — visualization only)
```

Cluster-of-risk is elected by `RISK_RANK_SPEC` in `config.py`: sum of
ranks across `tp` (high), `msl` (low), `fg10` (high); lowest-sum cluster
wins. Column names are raw ERA5 short codes: `tp`, `msl`, `fg10`,
`u10/v10/u100/v100`, `t2m`, `d2m`, `ssrd`, `strd`, `sp`, `sst`. Full
methodology in [docs/methods.md](docs/methods.md).

## Conventions (non-obvious from code)

- **`config.py` is the only place hyperparameters live.** Never hardcode
  them in other modules. Each constant carries a justification comment.
- **Parallel detector outputs use `_iso` / `_lof` suffix.** That includes
  `is_anomaly_*`, `anomaly_raw_*`, `anomaly_label_*`, `flood_risk_flag_*`.
  Consumers parameterize via `method="iso"|"lof"` (see
  `viz.fig_timeline`, `viz.fig_pca`, `viz.fig_seasonality`,
  `viz.save_flagged_csv`).
- **Outputs are timestamped.** Each run writes to
  `src/graphics/<YYYY-MM-DD_HHMMSS>/` with 9 figures + 2 CSVs (~3.3 MB
  total). Never overwrites previous runs. `src/graphics/` is git-ignored.
- **Figure format split.** PNG for dense plots (timeline, PCA,
  feature_explorer); SVG for sparse plots (cluster_profiles,
  seasonality, distributions, diagnostics). Controlled per-figure via
  `per_fig_fmt` in `viz.save_figures`.
- **`viz.py` never imports from `model.py`.** It receives the processed
  DataFrame and draws; this asymmetric dependency lets the model be
  exercised without matplotlib.
- **Diagnostics is independent and the slowest step** (~28s of ~40s
  total — trains KMeans 7× + IsolationForest 4× + LOF 4×). Can be
  commented out in `main.py` without breaking anything else.
- **Determinism via `RANDOM_STATE=42`.** Same CSV + same code = same
  outputs byte-for-byte (except the timestamp folder name).
- **Hardcoded data filename.** Both `config.py:DATA_PATH` and
  `era5_api.py` point at
  `reanalysis-era5-single-levels-timeseries-sfc6tkkiigw.csv`. Update
  when working with a different download.

## Data and outputs

- `data/` is git-ignored except the Drive marker
  [data/GoogleDriveDataExample.md](data/GoogleDriveDataExample.md);
  populate it from there or regenerate via `era5_api.py`.
- `src/graphics/` is git-ignored. Safe to `rm -rf src/graphics/*` at any
  time — everything regenerates from a `python src/main.py` run.
- See [docs/directories.md](docs/directories.md) for a table of every
  output file with typical size and how to read it.

## Roadmap

Three pending evolutions live in
[docs/TODO_evolucoes_analiticas.md](docs/TODO_evolucoes_analiticas.md),
to be implemented in order:

1. Group consecutive flagged timesteps into atomic events.
2. Fix `tp` aggregation in `data.py` (currently mean → should be sum
   after 6h resample).
3. Validate against curated real flood events.

Don't start these without explicit user approval — the user has chosen
to gate each phase.

## Documentation in docs/

`docs/` is curated, not auto-generated. Keep it in sync when changing
the pipeline. Contents:

- [docs/README.md](docs/README.md) — index.
- [docs/architecture.md](docs/architecture.md) — modules, dependency
  graph, full `main.py` flow.
- [docs/methods.md](docs/methods.md) — IsolationForest / LOF / KMeans /
  PCA / StandardScaler in detail, plus an Iso-vs-LOF comparison table.
- [docs/directories.md](docs/directories.md) — folder-by-folder guide.
- [docs/faq.md](docs/faq.md) — design decisions and how to adapt
  (change region, period, add a feature, add a third detector).
- [docs/TODO_evolucoes_analiticas.md](docs/TODO_evolucoes_analiticas.md)
  — roadmap.
