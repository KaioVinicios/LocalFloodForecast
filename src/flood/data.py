"""Carga e agregação temporal dos dados ERA5."""
import pandas as pd

from .config import DATA_PATH, RESAMPLE_FREQ


def load_data(path=DATA_PATH, resample_freq=RESAMPLE_FREQ):
    """Lê o CSV ERA5 e agrega em janelas de `resample_freq` (média)."""
    df = pd.read_csv(path, parse_dates=["valid_time"])
    df = df.resample(resample_freq, on="valid_time").mean().reset_index()
    return df
