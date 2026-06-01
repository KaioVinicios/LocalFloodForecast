"""Configuração central — variáveis, constantes e justificativas do pipeline.

Fonte única de verdade dos hiperparâmetros. Valores marcados [validado] são
confirmados empiricamente em diagnostics.py.
Dataset: ERA5 reanalysis, ponto único (lat 31.0, lon 19.25 — costa líbia /
Mediterrâneo), 2000-01-01 a 2026-03-17, 229.752 registros HORÁRIOS.
"""
from pathlib import Path

# --- Caminhos (resolvidos a partir da raiz do projeto; independente do cwd) ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH    = PROJECT_ROOT / "data" / "reanalysis-era5-single-levels-timeseries-sfc6tkkiigw.csv"
OUTPUT_DIR   = PROJECT_ROOT / "src" / "graphics"
# Cada execução cria um subdiretório <YYYY-MM-DD_HHMMSS>/ com PNG/SVG + CSV.

# --- Saída gráfica -----------------------------------------------------------
FIG_DPI = 170
# DPI para PNG. 170 dá nitidez em tela retina e mantém arquivo enxuto p/ os
# gráficos densos (timeline/PCA/feature_explorer).

# --- Agregação temporal ------------------------------------------------------
RESAMPLE_FREQ = "6h"
# 229.752 -> 38.292 linhas; suaviza ruído sub-horário e ciclo diurno, preservando
# a escala sinótica (00/06/12/18 UTC) em que sistemas de tempo severo evoluem.
# Ressalva: 'tp' (precip. acumulada horária) é agregada por MÉDIA -> vira taxa
#   média horária na janela, não soma acumulada de 6h.

RANDOM_STATE = 42
# Semente fixa -> reprodutibilidade determinística (IsolationForest/KMeans/PCA).

# --- Features ----------------------------------------------------------------
FEATURES = [
    "tp",                  # precipitação — indicador mais direto de cheia
    "msl",                 # pressão ao nível do mar — baixa -> tempestades
    "msl_tendency",        # queda rápida de pressão -> tempestade chegando
    "wind_speed_10m",      # vento forte acompanha tempo severo
    "wind_speed_100m",     # vento em nível mais alto (perfil da camada-limite)
    "fg10",                # rajada de vento a 10m
    "dewpoint_depression", # (t2m - d2m): baixa -> ar úmido, potencial de chuva
    "t2m",                 # contexto de temperatura
    "ssrd",                # radiação solar (baixa sob nebulosidade densa)
    "strd",                # radiação térmica descendente
    "sp",                  # pressão à superfície
]
# Excluídas de propósito:
#   u10/v10/u100/v100  -> substituídas pelas magnitudes (wind_speed_*);
#   d2m                -> já capturado via dewpoint_depression;
#   sst/skt            -> temp. de mar/superfície, vínculo indireto c/ gatilhos;
#   latitude/longitude -> constantes (ponto único), variância zero.

# --- Isolation Forest (detecção de anomalias) --------------------------------
ISO_N_ESTIMATORS  = 200
# Nº de árvores. Default sklearn=100; 200 estabiliza o anomaly score a custo
# baixo, com retorno decrescente acima disso para este tamanho de dados.

ISO_CONTAMINATION = 0.05
# Fração esperada de anomalias (~1.915 eventos em 26 anos ~ 74/ano). Chuva >
# 0,1 mm/h ocorre em ~3,7% dos passos; 5% é teto razoável p/ "tempo incomum".
# PRINCIPAL parâmetro a ajustar — sensibilidade testada em diagnostics.py.

# --- Local Outlier Factor (detecção de anomalias — alternativa) -------------
LOF_N_NEIGHBORS = 20
# Nº de vizinhos para estimar densidade local. Default sklearn=20; valores
# baixos (<10) ficam ruidosos, altos (>50) borram outliers locais. Validado
# em diagnostics.py via varredura {10, 20, 30, 50}.

LOF_CONTAMINATION = ISO_CONTAMINATION
# Mantido igual ao IsolationForest para que a COMPARAÇÃO entre os dois métodos
# seja justa (mesma fração esperada de anomalias).

# --- KMeans (regimes de tempo) -----------------------------------------------
N_CLUSTERS    = 4
# [validado] Silhouette máximo em k=4 (0,215) na varredura k=2..8 e região do
# cotovelo da inércia.

KMEANS_N_INIT = 20
# Nº de inicializações de centróides (k-means++). > default p/ reduzir risco de
# mínimo local ruim e estabilizar os clusters entre execuções.

# --- Ranking do cluster de risco (flood_risk_score) --------------------------
# Soma de postos IGUALMENTE ponderados das 3 assinaturas de tempestade
# (col -> ascending). Maior risco = mais chuva + menor pressão + rajadas fortes.
RISK_RANK_SPEC = {
    "tp":   False,  # ascending=False -> mais precipitação = maior risco
    "msl":  True,   # ascending=True  -> menor pressão     = maior risco
    "fg10": False,  # ascending=False -> rajada mais forte = maior risco
}

# --- PCA (apenas visualização) -----------------------------------------------
PCA_N_COMPONENTS = 2
# Projeção 2D para os scatters. NÃO entra na modelagem. PC1+PC2 retêm ~54,9%
# da variância — suficiente para inspeção visual dos regimes.
