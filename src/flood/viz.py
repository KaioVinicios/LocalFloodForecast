"""Figuras estáticas (matplotlib) para o pipeline de detecção de cheias.

Cada `fig_*` retorna `matplotlib.figure.Figure`. `save_figures` grava o
conjunto em disco no formato escolhido por figura (PNG p/ densos, SVG p/ enxutos).
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import dates as mdates

DARK_BG = "#0f1117"
CARD_BG = "#1a1d27"
GRID    = "#2a2d3a"
FG      = "#c9d1d9"
TITLE   = "#e6edf3"
ACCENT  = "#4cc9f0"
ANOMALY = "#f72585"
RISK    = "#ff6b35"
COLORS  = ["#4361ee", "#4cc9f0", "#2a9d8f", "#ff6b35", "#f72585",
           "#b298dc", "#ffd166", "#06d6a0"]


def apply_theme():
    """Tema escuro consistente. Chamar uma vez antes de construir figuras."""
    plt.rcParams.update({
        "figure.facecolor": CARD_BG, "axes.facecolor": DARK_BG,
        "savefig.facecolor": CARD_BG, "savefig.edgecolor": "none",
        "axes.edgecolor": GRID, "axes.labelcolor": FG,
        "axes.titlecolor": TITLE, "axes.titlesize": 12, "axes.titleweight": "600",
        "text.color": FG, "xtick.color": FG, "ytick.color": FG,
        "grid.color": GRID, "grid.linestyle": "-", "grid.linewidth": 0.5, "grid.alpha": 0.6,
        "axes.grid": True, "axes.spines.top": False, "axes.spines.right": False,
        "legend.facecolor": CARD_BG, "legend.edgecolor": GRID, "legend.labelcolor": FG,
        "font.family": "sans-serif", "font.size": 10,
    })


def _format_year_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.YearLocator())


_METHOD_LABEL = {"iso": "IsolationForest", "lof": "LOF"}


def fig_timeline(df, method="iso", top_n=5):
    """Densidade rolante de eventos + precip suavizada para um método específico.

    `method` ∈ {"iso", "lof"}. Em vez de plotar os 38k scores brutos (vira parede),
    usa a contagem em janela rolante de 30 dias.
    """
    anom_col = f"is_anomaly_{method}"
    flag_col = f"flood_risk_flag_{method}"
    raw_col  = f"anomaly_raw_{method}"
    label    = _METHOD_LABEL[method]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 8.5), sharex=True,
                                 gridspec_kw={"height_ratios": [0.6, 0.4]})

    s = df.set_index("valid_time")
    daily_anom = s[anom_col].astype(int).resample("D").sum()
    daily_flag = s[flag_col].astype(int).resample("D").sum()
    anom_30d = daily_anom.rolling(30, min_periods=1).sum()
    flag_30d = daily_flag.rolling(30, min_periods=1).sum()
    n_anom, n_flag = int(df[anom_col].sum()), int(df[flag_col].sum())

    a1.fill_between(anom_30d.index, anom_30d.values, color=ACCENT, alpha=0.30,
                    linewidth=0, label=f"anomalias (total {n_anom})")
    a1.plot(anom_30d.index, anom_30d.values, color=ACCENT, linewidth=0.6, alpha=0.7)
    a1.plot(flag_30d.index, flag_30d.values, color=RISK, linewidth=1.4,
            label=f"flood risk (total {n_flag})")
    a1.fill_between(flag_30d.index, flag_30d.values, color=RISK, alpha=0.25, linewidth=0)

    mf = df[df[flag_col]]
    top = mf.nsmallest(top_n, raw_col).copy()
    top["y"] = flag_30d.reindex(top.valid_time.dt.normalize(), method="nearest").values
    a1.scatter(top.valid_time, top.y, c=RISK, marker="*", s=200,
               edgecolors="white", linewidths=0.7, zorder=5)
    for _, r in top.iterrows():
        a1.annotate(f"{r.valid_time:%Y-%m-%d}\nscore {r[raw_col]:+.2f}",
                    xy=(r.valid_time, r.y), xytext=(0, 24),
                    textcoords="offset points", ha="center", fontsize=8.5,
                    color=RISK, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=RISK,
                                    lw=0.7, shrinkA=2, shrinkB=4))

    a1.set_ylabel("Eventos numa janela de 30 dias")
    a1.set_title(f"Densidade temporal — {label}")
    a1.legend(loc="upper left", framealpha=0.9, fontsize=9)
    a1.margins(y=0.18)

    precip30 = (s.tp.rolling("30D", min_periods=1).mean() * 1000)
    a2.fill_between(precip30.index, precip30.values, color="#4361ee", alpha=0.55,
                    linewidth=0, rasterized=True)
    a2.plot(precip30.index, precip30.values, color=ACCENT, linewidth=0.6)
    for t in mf.valid_time:
        a2.axvline(t, color=RISK, alpha=0.18, linewidth=0.4)
    a2.set_ylabel("Precip (média rolada 30d, mm)")
    a2.set_xlabel("Data")
    a2.set_title("Precipitação suavizada + eventos sinalizados (linhas verticais)")
    _format_year_axis(a2)

    fig.suptitle(f"Timeline ({label}) — anomalias e precipitação",
                 fontsize=14, color=TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def fig_pca(df, flood_cluster, pca_var, method="iso"):
    """Scatter PCA dos clusters com as flags de risco do `method` sobrepostas."""
    flag_col = f"flood_risk_flag_{method}"
    label    = _METHOD_LABEL[method]
    fig, ax = plt.subplots(figsize=(10, 8))
    for cid in sorted(df.cluster.unique()):
        m = df[df.cluster == cid]
        marker = "D" if cid == flood_cluster else "o"
        leg = f"Cluster {cid}" + (" (risco)" if cid == flood_cluster else "")
        ax.scatter(m.pca1, m.pca2, c=COLORS[cid % len(COLORS)], s=14, alpha=0.55,
                   marker=marker, edgecolors="none", rasterized=True, label=leg)
    mf = df[df[flag_col]]
    ax.scatter(mf.pca1, mf.pca2, c=RISK, marker="*", s=160, edgecolors="white",
               linewidths=0.6, label=f"Flood Risk ({label})", zorder=5)
    ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
    ax.set_title(f"PCA — regimes de tempo (PC1+PC2 = {pca_var * 100:.1f}% da variância)")
    ax.legend(loc="best", framealpha=0.85)
    fig.tight_layout()
    return fig


def fig_method_comparison(df, flood_cluster):
    """Compara IsolationForest x LOF: contagens mutuamente exclusivas + PCA por categoria."""
    iso = df.flood_risk_flag_iso
    lof = df.flood_risk_flag_lof
    both     = iso & lof
    only_iso = iso & ~lof
    only_lof = ~iso & lof
    neither  = ~iso & ~lof
    n_both, n_only_iso, n_only_lof = int(both.sum()), int(only_iso.sum()), int(only_lof.sum())
    n_iso, n_lof = int(iso.sum()), int(lof.sum())
    union = n_iso + n_lof - n_both
    jaccard = n_both / union if union else 0.0

    fig = plt.figure(figsize=(16, 6.5))
    gs = fig.add_gridspec(1, 5)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_pca = fig.add_subplot(gs[0, 1:])

    cats = ["Só Iso", "Só LOF", "Ambos"]
    vals = [n_only_iso, n_only_lof, n_both]
    bcolors = [ACCENT, "#b298dc", RISK]
    bars = ax_bar.bar(cats, vals, color=bcolors)
    ax_bar.bar_label(bars, fmt="%d", padding=3, color=FG, fontsize=10)
    ax_bar.set_title(f"Eventos flagged (Iso={n_iso}, LOF={n_lof})\n"
                     f"Jaccard={jaccard:.2%} | união={union}")
    ax_bar.set_ylabel("nº de eventos")
    ax_bar.margins(y=0.18)

    # PCA por categoria — "sem flag" como fundo sutil; categorias destacadas.
    bg = df[neither]
    ax_pca.scatter(bg.pca1, bg.pca2, c="#2a2d3a", s=4, alpha=0.4, linewidths=0,
                   rasterized=True, label=f"sem flag (n={int(neither.sum())})")
    oi = df[only_iso]
    ax_pca.scatter(oi.pca1, oi.pca2, c=ACCENT, s=42, alpha=0.85, marker="o",
                   edgecolors="white", linewidths=0.4, rasterized=True,
                   label=f"só Iso (n={n_only_iso})")
    ol = df[only_lof]
    ax_pca.scatter(ol.pca1, ol.pca2, c="#b298dc", s=42, alpha=0.85, marker="s",
                   edgecolors="white", linewidths=0.4, rasterized=True,
                   label=f"só LOF (n={n_only_lof})")
    bo = df[both]
    ax_pca.scatter(bo.pca1, bo.pca2, c=RISK, s=130, marker="*",
                   edgecolors="white", linewidths=0.6,
                   label=f"ambos (n={n_both})", zorder=5)
    ax_pca.set_xlabel("PC1"); ax_pca.set_ylabel("PC2")
    ax_pca.set_title(f"PCA — flags por método (cluster de risco = {flood_cluster})")
    ax_pca.legend(loc="best", framealpha=0.9, fontsize=9)

    fig.suptitle("Comparação IsolationForest × LOF (flood_risk_flag)",
                 fontsize=14, color=TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def fig_cluster_profiles(df, flood_cluster):
    """Médias por cluster (precipitação, vento, rajada), destacando o de risco."""
    cs = df.groupby("cluster")[["tp", "wind_speed_10m", "fg10"]].mean().reset_index()
    cs["tp_mm"] = cs.tp * 1000
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
    bar_colors = [RISK if c == flood_cluster else "#4361ee" for c in cs.cluster]
    bars = a1.bar(cs.cluster.astype(str), cs.tp_mm, color=bar_colors)
    a1.bar_label(bars, fmt="%.4f", padding=3, fontsize=9, color=FG)
    a1.set_title("Precip média por cluster (mm)"); a1.set_xlabel("Cluster")

    x = np.arange(len(cs))
    a2.bar(x - 0.2, cs.wind_speed_10m, 0.4, color="#4cc9f0", label="Vento 10m")
    a2.bar(x + 0.2, cs.fg10, 0.4, color="#2a9d8f", label="Rajada 10m")
    a2.set_xticks(x); a2.set_xticklabels(cs.cluster.astype(str))
    a2.set_title("Vento & rajada médios (m/s)"); a2.set_xlabel("Cluster")
    a2.legend(framealpha=0.85)
    fig.tight_layout()
    return fig


def fig_feature_explorer(df, variables=None):
    """Grid de séries temporais das features brutas (substitui o dropdown)."""
    variables = variables or ["tp", "msl", "msl_tendency", "wind_speed_10m",
                              "wind_speed_100m", "fg10", "dewpoint_depression",
                              "t2m", "ssrd", "strd", "sp"]
    cols = 3
    rows = (len(variables) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(16, 2.6 * rows), sharex=True)
    axes = axes.flatten()
    for ax, v in zip(axes, variables):
        ax.plot(df.valid_time, df[v], color=ACCENT, linewidth=0.5, rasterized=True)
        ax.set_title(v, fontsize=10)
        ax.tick_params(labelsize=8)
    for ax in axes[len(variables):]:
        ax.set_visible(False)
    for ax in axes[-cols:]:
        if ax.get_visible():
            _format_year_axis(ax)
    fig.suptitle("Séries temporais das features brutas", fontsize=14, color=TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def fig_seasonality(df, method="iso"):
    """Heatmap do nº de eventos sinalizados por ano × mês para `method`."""
    flag_col = f"flood_risk_flag_{method}"
    piv = (df.assign(ano=df.valid_time.dt.year, mes=df.valid_time.dt.month)
             .groupby(["ano", "mes"])[flag_col].sum()
             .unstack("mes").reindex(columns=range(1, 13)).fillna(0))
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(piv.values, cmap="inferno", aspect="auto")
    ax.set_xticks(range(12)); ax.set_xticklabels([f"{m:02d}" for m in range(1, 13)])
    ax.set_yticks(range(len(piv.index))); ax.set_yticklabels(piv.index.astype(str))
    ax.set_xlabel("Mês"); ax.set_ylabel("Ano")
    ax.set_title(f"Eventos sinalizados por ano × mês ({_METHOD_LABEL[method]})")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="eventos")
    vmax = max(piv.values.max(), 1)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if v > 0:
                ax.text(j, i, int(v), ha="center", va="center", fontsize=7,
                        color="white" if v < vmax * 0.6 else "black")
    fig.tight_layout()
    return fig


def fig_distributions(df, flood_cluster, variables=None):
    """Box plots por cluster, um subplot por variável."""
    variables = variables or ["tp", "msl", "wind_speed_10m", "fg10",
                              "dewpoint_depression", "t2m"]
    clusters = sorted(df.cluster.unique())
    cols = 3
    rows = (len(variables) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(14, 4 * rows))
    axes = axes.flatten()
    for ax, v in zip(axes, variables):
        data = [df.loc[df.cluster == c, v].values for c in clusters]
        bp = ax.boxplot(data, tick_labels=[f"C{c}" for c in clusters],
                        patch_artist=True, showfliers=False,
                        medianprops=dict(color="white"))
        for patch, c in zip(bp["boxes"], clusters):
            patch.set_facecolor(RISK if c == flood_cluster else COLORS[c % len(COLORS)])
            patch.set_alpha(0.85)
        ax.set_title(v); ax.set_xlabel("Cluster")
    for ax in axes[len(variables):]:
        ax.set_visible(False)
    fig.suptitle("Distribuição das features por cluster", fontsize=14, color=TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def save_flagged_csv(df, out_path, method="iso"):
    """Tabela dos eventos sinalizados (por `method`) em CSV."""
    flag_col = f"flood_risk_flag_{method}"
    raw_col  = f"anomaly_raw_{method}"
    ft = df[df[flag_col]].assign(
        date=lambda x: x.valid_time.dt.strftime("%Y-%m-%d %H:%M"),
        tp_mm=lambda x: (x.tp * 1000).round(3),
        t_c=lambda x: (x.t2m - 273.15).round(1),
        wind_10m=lambda x: x.wind_speed_10m.round(1),
        gust=lambda x: x.fg10.round(1),
        pressure_hpa=lambda x: (x.msl / 100).round(1),
        score=lambda x: x[raw_col].round(3),
        cluster_id=lambda x: x.cluster.astype(int),
    )[["date", "tp_mm", "t_c", "wind_10m", "gust", "pressure_hpa", "score", "cluster_id"]]
    ft.to_csv(out_path, index=False)
    return out_path


def save_figures(figs, out_dir, default_fmt="png", per_fig_fmt=None, dpi=170):
    """Salva cada figura em out_dir; `per_fig_fmt` permite override por chave."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_fig_fmt = per_fig_fmt or {}
    paths = []
    for name, fig in figs.items():
        fmt = per_fig_fmt.get(name, default_fmt)
        p = out_dir / f"{name}.{fmt}"
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)
    return paths
