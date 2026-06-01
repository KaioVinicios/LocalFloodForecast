"""Validação empírica dos hiperparâmetros (elbow/silhouette, contamination,
n_neighbors do LOF, PCA, e concordância Iso×LOF).

Não altera o pipeline; produz uma figura matplotlib + imprime os números-chave
no console que embasam os valores escolhidos em config.py.
"""
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score
from sklearn.neighbors import LocalOutlierFactor

from .config import (KMEANS_N_INIT, ISO_N_ESTIMATORS, N_CLUSTERS,
                     ISO_CONTAMINATION, LOF_N_NEIGHBORS, LOF_CONTAMINATION,
                     PCA_N_COMPONENTS, RANDOM_STATE)


def run_diagnostics(df, X_scaled, ks=range(2, 9),
                    contam_grid=(0.01, 0.02, 0.05, 0.10),
                    lof_neighbors_grid=(10, 20, 30, 50)):
    """Retorna uma figura matplotlib de diagnóstico e imprime os números-chave."""
    ks = list(ks)
    inertias, sils = [], []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=KMEANS_N_INIT, random_state=RANDOM_STATE).fit(X_scaled)
        inertias.append(km.inertia_)
        sils.append(silhouette_score(X_scaled, km.labels_, sample_size=5000,
                                     random_state=RANDOM_STATE))
    best_k = ks[int(np.argmax(sils))]

    contam_counts = [
        int((IsolationForest(n_estimators=ISO_N_ESTIMATORS, contamination=c,
                             random_state=RANDOM_STATE).fit_predict(X_scaled) == -1).sum())
        for c in contam_grid
    ]
    evr = PCA(n_components=5, random_state=RANDOM_STATE).fit(X_scaled).explained_variance_ratio_

    # IsolationForest de referência (mesma contaminação que o pipeline usa)
    iso_ref = IsolationForest(n_estimators=ISO_N_ESTIMATORS,
                              contamination=ISO_CONTAMINATION,
                              random_state=RANDOM_STATE).fit_predict(X_scaled) == -1

    lof_counts, lof_jaccards = [], []
    for nn in lof_neighbors_grid:
        lof_pred = LocalOutlierFactor(n_neighbors=nn,
                                      contamination=LOF_CONTAMINATION).fit_predict(X_scaled) == -1
        lof_counts.append(int(lof_pred.sum()))
        inter = int((iso_ref & lof_pred).sum())
        union = int((iso_ref | lof_pred).sum())
        lof_jaccards.append(inter / union if union else 0.0)

    print(f"[diagnóstico] k ótimo por silhouette: {best_k} (configurado = {N_CLUSTERS})")
    for c, n in zip(contam_grid, contam_counts):
        marker = "  <- configurado" if abs(c - ISO_CONTAMINATION) < 1e-9 else ""
        print(f"[diagnóstico] iso contamination={c:>5}: {n} anomalias ({n / len(df) * 100:.1f}%){marker}")
    for nn, n, j in zip(lof_neighbors_grid, lof_counts, lof_jaccards):
        marker = "  <- configurado" if nn == LOF_N_NEIGHBORS else ""
        print(f"[diagnóstico] lof n_neighbors={nn:>3}: {n} anomalias | Jaccard c/ Iso = {j:.2%}{marker}")
    print(f"[diagnóstico] PC1+PC2 retêm {evr[:PCA_N_COMPONENTS].sum() * 100:.1f}% da variância")

    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
    (a, b, c, d, e, f) = axes.flatten()

    a.plot(ks, inertias, "o-", color="#4361ee")
    a.axvline(N_CLUSTERS, color="crimson", linestyle="--", alpha=0.7)
    a.set_title("Elbow (inércia) por k"); a.set_xlabel("k"); a.set_ylabel("inércia")

    b.plot(ks, sils, "o-", color="#4cc9f0")
    b.axvline(N_CLUSTERS, color="crimson", linestyle="--", alpha=0.7)
    b.set_title("Silhouette por k"); b.set_xlabel("k"); b.set_ylabel("silhouette")

    c.bar([f"PC{i + 1}" for i in range(len(evr))], evr, color="#2a9d8f")
    c.set_title("PCA — variância explicada"); c.set_ylabel("razão")

    d.bar([f"{cc:.0%}" for cc in contam_grid], contam_counts, color="#ff6b35")
    d.set_title("Iso — sensibilidade do contamination"); d.set_ylabel("nº de anomalias")

    bars_lof = e.bar([str(n) for n in lof_neighbors_grid], lof_counts, color="#b298dc")
    e.set_title("LOF — sensibilidade do n_neighbors"); e.set_ylabel("nº de anomalias")
    e.set_xlabel("n_neighbors")
    for bar, nn in zip(bars_lof, lof_neighbors_grid):
        if nn == LOF_N_NEIGHBORS:
            bar.set_edgecolor("crimson"); bar.set_linewidth(2)

    bars_j = f.bar([str(n) for n in lof_neighbors_grid],
                   [j * 100 for j in lof_jaccards], color="#4cc9f0")
    f.set_title("Jaccard Iso × LOF por n_neighbors"); f.set_ylabel("Jaccard (%)")
    f.set_xlabel("n_neighbors"); f.set_ylim(0, 100)
    for bar, nn, j in zip(bars_j, lof_neighbors_grid, lof_jaccards):
        f.text(bar.get_x() + bar.get_width() / 2, j * 100 + 1.5,
               f"{j:.1%}", ha="center", fontsize=8, color="#c9d1d9")
        if nn == LOF_N_NEIGHBORS:
            bar.set_edgecolor("crimson"); bar.set_linewidth(2)

    fig.suptitle("Diagnóstico dos hiperparâmetros", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig
