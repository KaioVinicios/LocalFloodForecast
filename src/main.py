"""Pipeline de detecção de eventos de cheia (ERA5) + gráficos estáticos.

Roda IsolationForest e LOF em paralelo (flags _iso/_lof), KMeans compartilhado.

Uso:
    python src/main.py

Cada execução cria um subdiretório `src/graphics/<YYYY-MM-DD_HHMMSS>/` com
as figuras (PNG p/ densos, SVG p/ enxutos) e os CSVs por método.
"""
import time
from contextlib import contextmanager
from datetime import datetime

from flood.config import OUTPUT_DIR, FIG_DPI, FEATURES, LOF_N_NEIGHBORS
from flood.data import load_data
from flood.features import engineer_features, scale_features
from flood.model import (detect_anomalies_iso, detect_anomalies_lof,
                         cluster_regimes, flag_flood_risk, project_pca)
from flood.diagnostics import run_diagnostics
from flood import viz


@contextmanager
def step(label):
    """Timer + log de uma etapa do pipeline."""
    t0 = time.perf_counter()
    print(f"\n[{label}] iniciando…")
    yield
    print(f"[{label}] concluído em {time.perf_counter() - t0:.2f}s")


def _comparison_metrics(df):
    """Stats de concordância Iso × LOF nas duas camadas (anomalia bruta e flag final)."""
    pairs = [("is_anomaly", "anomalias brutas"),
             ("flood_risk_flag", "flood_risk_flag (∩ cluster de risco)")]
    print("\n[comparação Iso × LOF]")
    for col_base, label in pairs:
        iso = df[f"{col_base}_iso"]
        lof = df[f"{col_base}_lof"]
        n_iso, n_lof = int(iso.sum()), int(lof.sum())
        inter = int((iso & lof).sum())
        union = n_iso + n_lof - inter
        only_iso, only_lof = n_iso - inter, n_lof - inter
        jaccard = inter / union if union else 0.0
        overlap_iso = inter / n_iso if n_iso else 0.0
        overlap_lof = inter / n_lof if n_lof else 0.0
        print(f"  {label}:")
        print(f"    Iso={n_iso}  LOF={n_lof}  ambos={inter}  "
              f"só_Iso={only_iso}  só_LOF={only_lof}  união={union}")
        print(f"    Jaccard={jaccard:.2%}  |  overlap/Iso={overlap_iso:.2%}  "
              f"overlap/LOF={overlap_lof:.2%}")


def run():
    t_total = time.perf_counter()
    print(f"=== Flood Risk Pipeline | início: {datetime.now():%Y-%m-%d %H:%M:%S} ===")

    with step("load_data"):
        df = load_data()
        print(f"  - {len(df):,} linhas após resample 6h "
              f"(de {df.valid_time.min():%Y-%m-%d} a {df.valid_time.max():%Y-%m-%d})")

    with step("engineer_features"):
        df = engineer_features(df)
        added = ["wind_speed_10m", "wind_speed_100m", "dewpoint_depression", "msl_tendency"]
        print(f"  - features adicionadas: {', '.join(added)}")

    with step("scale_features"):
        X_scaled, _ = scale_features(df)
        print(f"  - X_scaled: shape={X_scaled.shape} | {len(FEATURES)} features padronizadas")

    with step("detect_anomalies_iso (IsolationForest)"):
        df, _ = detect_anomalies_iso(df, X_scaled)
        n = int(df.is_anomaly_iso.sum())
        print(f"  - {n:,} anomalias ({n / len(df) * 100:.2f}%)")
        print(f"  - score: min={df.anomaly_raw_iso.min():.3f} | "
              f"mediana={df.anomaly_raw_iso.median():.3f} | max={df.anomaly_raw_iso.max():.3f}")

    with step(f"detect_anomalies_lof (LocalOutlierFactor, n_neighbors={LOF_N_NEIGHBORS})"):
        df, _ = detect_anomalies_lof(df, X_scaled)
        n = int(df.is_anomaly_lof.sum())
        print(f"  - {n:,} anomalias ({n / len(df) * 100:.2f}%)")
        print(f"  - score: min={df.anomaly_raw_lof.min():.3f} | "
              f"mediana={df.anomaly_raw_lof.median():.3f} | max={df.anomaly_raw_lof.max():.3f}")

    with step("cluster_regimes (KMeans)"):
        df, stats, flood_cluster = cluster_regimes(df, X_scaled)
        sizes = df.cluster.value_counts().sort_index().to_dict()
        print(f"  - tamanhos por cluster: {sizes}")
        print(f"  - cluster de risco identificado: {flood_cluster}")

    with step("flag_flood_risk (Iso & LOF interseccionados com cluster de risco)"):
        df = flag_flood_risk(df)
        n_iso = int(df.flood_risk_flag_iso.sum())
        n_lof = int(df.flood_risk_flag_lof.sum())
        print(f"  - flood_risk_flag_iso: {n_iso} eventos ({n_iso / len(df) * 100:.2f}%)")
        print(f"  - flood_risk_flag_lof: {n_lof} eventos ({n_lof / len(df) * 100:.2f}%)")

    with step("project_pca"):
        df, pca_var = project_pca(df, X_scaled)
        print(f"  - PC1+PC2 retêm {pca_var * 100:.1f}% da variância")

    _comparison_metrics(df)

    viz.apply_theme()

    with step("run_diagnostics (KMeans×7 + Iso×4 + LOF×4 — etapa mais pesada)"):
        diag_fig = run_diagnostics(df, X_scaled)

    with step("build figures"):
        figs = {
            "timeline_iso":      viz.fig_timeline(df, method="iso"),
            "timeline_lof":      viz.fig_timeline(df, method="lof"),
            "pca":               viz.fig_pca(df, flood_cluster, pca_var, method="iso"),
            "method_comparison": viz.fig_method_comparison(df, flood_cluster),
            "cluster_profiles":  viz.fig_cluster_profiles(df, flood_cluster),
            "feature_explorer":  viz.fig_feature_explorer(df),
            "seasonality":       viz.fig_seasonality(df, method="iso"),
            "distributions":     viz.fig_distributions(df, flood_cluster),
            "diagnostics":       diag_fig,
        }
        print(f"  - {len(figs)} figuras construídas")

    per_fig = {
        "timeline_iso": "png", "timeline_lof": "png",
        "pca": "png", "method_comparison": "png", "feature_explorer": "png",
        "cluster_profiles": "svg", "seasonality": "svg",
        "distributions": "svg", "diagnostics": "svg",
    }
    out_dir = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")

    with step(f"save outputs -> {out_dir.relative_to(OUTPUT_DIR.parent.parent)}"):
        paths = viz.save_figures(figs, out_dir, per_fig_fmt=per_fig, dpi=FIG_DPI)
        csv_iso = viz.save_flagged_csv(df, out_dir / "flagged_events_iso.csv", method="iso")
        csv_lof = viz.save_flagged_csv(df, out_dir / "flagged_events_lof.csv", method="lof")
        total_kb = 0
        for p in [*paths, csv_iso, csv_lof]:
            kb = p.stat().st_size / 1024
            total_kb += kb
            print(f"  - {p.name:<30} {kb:>8.1f} KB")
        print(f"  - total: {total_kb:.1f} KB")

    print(f"\n=== concluído em {time.perf_counter() - t_total:.2f}s | "
          f"saída: {out_dir} ===")


if __name__ == "__main__":
    run()
