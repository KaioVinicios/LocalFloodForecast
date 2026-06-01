"""Detecção de anomalias (IsolationForest + LOF), regimes (KMeans), flags e PCA.

Iso e LOF rodam em paralelo e produzem colunas/flags separadas com sufixo
`_iso`/`_lof`; o ranking do cluster de risco (KMeans) é compartilhado.
"""
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

from .config import (ISO_N_ESTIMATORS, ISO_CONTAMINATION, LOF_N_NEIGHBORS,
                     LOF_CONTAMINATION, N_CLUSTERS, KMEANS_N_INIT,
                     RISK_RANK_SPEC, PCA_N_COMPONENTS, RANDOM_STATE)


def detect_anomalies_iso(df, X_scaled):
    """IsolationForest -> anomaly_label_iso (-1/1), anomaly_raw_iso, is_anomaly_iso."""
    iso = IsolationForest(n_estimators=ISO_N_ESTIMATORS,
                          contamination=ISO_CONTAMINATION, random_state=RANDOM_STATE)
    df["anomaly_label_iso"] = iso.fit_predict(X_scaled)         # -1 = anomalia
    df["anomaly_raw_iso"]   = iso.decision_function(X_scaled)   # menor = mais anômalo
    df["is_anomaly_iso"]    = df["anomaly_label_iso"] == -1
    return df, iso


def detect_anomalies_lof(df, X_scaled):
    """LocalOutlierFactor -> anomaly_label_lof, anomaly_raw_lof, is_anomaly_lof.

    LOF compara a densidade local de cada ponto com a dos seus k vizinhos:
    pontos em regiões muito menos densas que a vizinhança são marcados como
    outliers. `negative_outlier_factor_` é o score (menor = mais anômalo),
    análogo ao `decision_function` do IsolationForest.
    """
    lof = LocalOutlierFactor(n_neighbors=LOF_N_NEIGHBORS,
                             contamination=LOF_CONTAMINATION)
    df["anomaly_label_lof"] = lof.fit_predict(X_scaled)        # -1 = anomalia
    df["anomaly_raw_lof"]   = lof.negative_outlier_factor_     # menor = mais anômalo
    df["is_anomaly_lof"]    = df["anomaly_label_lof"] == -1
    return df, lof


def cluster_regimes(df, X_scaled):
    """KMeans -> cluster; identifica o cluster de risco por soma de postos."""
    df["cluster"] = KMeans(n_clusters=N_CLUSTERS, n_init=KMEANS_N_INIT,
                           random_state=RANDOM_STATE).fit_predict(X_scaled)
    stats = df.groupby("cluster")[["tp", "msl", "fg10", "wind_speed_10m"]].mean()
    stats["flood_risk_score"] = sum(
        stats[col].rank(ascending=asc) for col, asc in RISK_RANK_SPEC.items()
    )
    flood_cluster = stats["flood_risk_score"].idxmin()
    df["in_flood_cluster"] = df["cluster"] == flood_cluster
    return df, stats, flood_cluster


def flag_flood_risk(df):
    """Cria duas flags paralelas: flood_risk_flag_iso e flood_risk_flag_lof."""
    df["flood_risk_flag_iso"] = df["is_anomaly_iso"] & df["in_flood_cluster"]
    df["flood_risk_flag_lof"] = df["is_anomaly_lof"] & df["in_flood_cluster"]
    return df


def project_pca(df, X_scaled):
    """Projeção PCA (só visualização) -> colunas pca1..pcaN + variância retida."""
    pca = PCA(n_components=PCA_N_COMPONENTS, random_state=RANDOM_STATE).fit(X_scaled)
    coords = pca.transform(X_scaled)
    for i in range(PCA_N_COMPONENTS):
        df[f"pca{i + 1}"] = coords[:, i]
    return df, float(pca.explained_variance_ratio_.sum())
