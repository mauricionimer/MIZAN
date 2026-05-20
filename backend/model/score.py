import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent

# Features v1 (RandomForest + StandardScaler — retrocompatível)
_FEATURES_V1 = ["valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"]
# Features v2 (HistGBM + RobustScaler — modelo atual)
_FEATURES_V2 = [
    "valor_divida", "renda_estimada", "dias_em_atraso",
    "comprometimento_renda", "log_valor_divida", "log_renda", "valor_por_dia",
]

_cache: dict = {}


def _carregar_modelos() -> tuple:
    if _cache:
        return _cache["clf"], _cache["kmeans"], _cache["meta"]

    arquivos = {
        "mizan_model.pkl": MODEL_DIR / "mizan_model.pkl",
        "kmeans.pkl":      MODEL_DIR / "kmeans.pkl",
        "scaler.pkl":      MODEL_DIR / "scaler.pkl",
    }
    ausentes = [nome for nome, path in arquivos.items() if not path.exists()]
    if ausentes:
        raise FileNotFoundError(2, "No such file or directory", str(MODEL_DIR / ausentes[0]))

    clf    = joblib.load(arquivos["mizan_model.pkl"])
    kmeans = joblib.load(arquivos["kmeans.pkl"])
    meta   = joblib.load(arquivos["scaler.pkl"])

    _cache["clf"]    = clf
    _cache["kmeans"] = kmeans
    _cache["meta"]   = meta
    return clf, kmeans, meta


def _preprocessar_para_score(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    df      = df.copy()
    version = meta.get("model_version", 1)

    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(0).clip(0, 10)

    if version >= 2:
        df["log_valor_divida"] = np.log1p(df["valor_divida"].clip(0))
        df["log_renda"]        = np.log1p(df["renda_estimada"].clip(0))
        df["valor_por_dia"]    = df["valor_divida"] / (df["dias_em_atraso"] + 1)
        num_features = _FEATURES_V2
    else:
        num_features = _FEATURES_V1

    cat_cols = meta["cat_cols"]
    df_enc   = pd.get_dummies(df[["produto", "status", "uf"]], drop_first=False)
    for col in cat_cols:
        if col not in df_enc.columns:
            df_enc[col] = 0
    df_enc = df_enc[cat_cols]

    return pd.concat([df[num_features], df_enc], axis=1)


def score_carteira(df: pd.DataFrame) -> pd.DataFrame:
    clf, kmeans, meta = _carregar_modelos()
    scaler = meta["scaler"]

    X        = _preprocessar_para_score(df, meta)
    X_scaled = scaler.transform(X)

    clusters         = kmeans.predict(X_scaled)
    X_clf            = np.column_stack([X_scaled, clusters])
    prob_pagamento   = clf.predict_proba(X_clf)[:, 1]
    score            = (prob_pagamento * 100).round(1)

    resultado                          = df.copy()
    resultado["score_recuperabilidade"] = score
    resultado["cluster_id"]             = clusters
    cluster_labels                      = meta.get("cluster_labels", {})
    resultado["perfil_cluster"]         = [
        cluster_labels.get(int(c), f"Cluster {c}") for c in clusters
    ]
    return resultado
