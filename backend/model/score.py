import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent

# Fallbacks para modelos antigos sem metadata de features
_FEATURES_V1 = ["valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"]
_FEATURES_V2 = [
    "valor_divida", "renda_estimada", "dias_em_atraso",
    "comprometimento_renda", "log_valor_divida", "log_renda", "valor_por_dia",
]
_CATS_V2 = ["produto", "status", "uf"]

_cache: dict = {}


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    from model.train import ALIASES
    rename = {col: ALIASES[col.lower().strip()] for col in df.columns if col.lower().strip() in ALIASES}
    return df.rename(columns=rename) if rename else df


def _adicionar_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Converte None (SQL NULL) para NaN antes de qualquer operação numérica
    for col in ['valor_divida', 'renda_estimada', 'dias_em_atraso']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'valor_divida' in df.columns and 'renda_estimada' in df.columns:
        df['comprometimento_renda'] = (
            df['valor_divida'] / df['renda_estimada'].replace(0, np.nan)
        ).fillna(0).clip(0, 10)
    if 'valor_divida' in df.columns:
        df['log_valor_divida'] = np.log1p(df['valor_divida'].clip(0))
    if 'renda_estimada' in df.columns:
        df['log_renda'] = np.log1p(df['renda_estimada'].clip(0))
    if 'valor_divida' in df.columns and 'dias_em_atraso' in df.columns:
        df['valor_por_dia'] = df['valor_divida'] / (df['dias_em_atraso'] + 1)
    return df


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
    df = _normalizar_colunas(df)
    df = _adicionar_derivadas(df)
    df = df.copy()

    features_numericas   = meta.get("features_numericas")
    features_categoricas = meta.get("features_categoricas")
    medians = meta.get("medians", {})
    modes   = meta.get("modes", {})
    cat_cols = meta["cat_cols"]

    # Retrocompatibilidade com modelos antigos
    if features_numericas is None:
        version = meta.get("model_version", 1)
        features_numericas   = _FEATURES_V2 if version >= 2 else _FEATURES_V1
        features_categoricas = _CATS_V2

    # Garante colunas numéricas: imputa com mediana de treino se ausente
    for col in features_numericas:
        if col not in df.columns:
            df[col] = medians.get(col, 0.0)
        else:
            df[col] = df[col].fillna(medians.get(col, 0.0))

    # Garante colunas categóricas: imputa com moda de treino se ausente
    for col in features_categoricas:
        if col not in df.columns:
            df[col] = modes.get(col, "outro")
        else:
            df[col] = df[col].fillna(modes.get(col, "outro")).astype(str)

    if features_categoricas:
        df_enc = pd.get_dummies(df[features_categoricas], drop_first=False)
    else:
        df_enc = pd.DataFrame(index=df.index)

    # Alinha exatamente às colunas do treino
    df_enc = df_enc.reindex(columns=cat_cols, fill_value=0)

    return pd.concat([df[features_numericas], df_enc], axis=1)


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
