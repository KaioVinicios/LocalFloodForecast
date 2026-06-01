"""Engenharia de features e padronização."""
import numpy as np
from sklearn.preprocessing import StandardScaler

from .config import FEATURES


def engineer_features(df):
    """Adiciona magnitudes de vento, dewpoint_depression e tendência de pressão."""
    df = df.sort_values("valid_time").reset_index(drop=True)
    df["wind_speed_10m"]  = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)
    df["wind_speed_100m"] = np.sqrt(df["u100"] ** 2 + df["v100"] ** 2)
    df["dewpoint_depression"] = df["t2m"] - df["d2m"]
    df["msl_tendency"] = df["msl"].diff().fillna(0)
    return df


def scale_features(df, features=FEATURES):
    """Retorna (X_scaled, scaler) da padronização StandardScaler das `features`."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[features])
    return X_scaled, scaler
