from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_DIR = Path(__file__).parent

CLUSTER_LABELS = {
    0: "Alto Risco",
    1: "Risco Moderado",
    2: "Potencial de Recuperação",
    3: "Baixo Risco",
    4: "Consignado Prioritário",
}

FEATURES_NUMERICAS = [
    "valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"
]

_cache: dict = {}


def _carregar_modelos() -> tuple:
    if _cache:
        return _cache["clf"], _cache["kmeans"], _cache["meta"]

    clf = joblib.load(MODEL_DIR / "mizan_model.pkl")
    kmeans = joblib.load(MODEL_DIR / "kmeans.pkl")
    meta = joblib.load(MODEL_DIR / "scaler.pkl")

    _cache["clf"] = clf
    _cache["kmeans"] = kmeans
    _cache["meta"] = meta
    return clf, kmeans, meta


def _preprocessar_para_score(df: pd.DataFrame, cat_cols: list[str]) -> np.ndarray:
    df = df.copy()
    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(0)

    df_enc = pd.get_dummies(df[["produto", "status", "uf"]], drop_first=False)

    # Garante que todas as colunas do treino estão presentes (mesmo que ausentes no CSV)
    for col in cat_cols:
        if col not in df_enc.columns:
            df_enc[col] = 0
    df_enc = df_enc[cat_cols]

    X = pd.concat([df[FEATURES_NUMERICAS], df_enc], axis=1)
    return X


def score_carteira(df: pd.DataFrame) -> pd.DataFrame:
    clf, kmeans, meta = _carregar_modelos()
    scaler = meta["scaler"]
    cat_cols = meta["cat_cols"]

    X = _preprocessar_para_score(df, cat_cols)
    X_scaled = scaler.transform(X)

    clusters = kmeans.predict(X_scaled)
    X_rf = np.column_stack([X_scaled, clusters])

    prob_pagamento = clf.predict_proba(X_rf)[:, 1]
    score = (prob_pagamento * 100).round(1)

    resultado = df.copy()
    resultado["score_recuperabilidade"] = score
    resultado["cluster_id"] = clusters
    resultado["perfil_cluster"] = [CLUSTER_LABELS.get(c, "Indefinido") for c in clusters]

    return resultado
