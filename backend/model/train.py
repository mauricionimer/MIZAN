"""
Treina o modelo de recuperabilidade de crédito do Mizan.

Entrada: carteira_mizan.csv no diretório atual ou caminho passado como argumento.
Saída:   mizan_model.pkl, kmeans.pkl, scaler.pkl no mesmo diretório deste script.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

MODEL_DIR = Path(__file__).parent

COLUNAS_ESPERADAS = [
    "cpf", "nome", "produto", "status", "uf",
    "valor_divida", "renda_estimada", "dias_em_atraso",
]

CLUSTER_LABELS = {
    0: "Alto Risco",
    1: "Risco Moderado",
    2: "Potencial de Recuperação",
    3: "Baixo Risco",
    4: "Consignado Prioritário",
}

FEATURES_CATEGORICAS = ["produto", "status", "uf"]
FEATURES_NUMERICAS = [
    "valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"
]


def _carregar_csv(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    faltantes = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Colunas ausentes no CSV: {faltantes}")
    return df


def _preprocessar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(0)

    df_enc = pd.get_dummies(df[FEATURES_CATEGORICAS], drop_first=False)
    cat_cols = df_enc.columns.tolist()

    X = pd.concat([df[FEATURES_NUMERICAS], df_enc], axis=1)
    return X, cat_cols


def _criar_alvo_simulado(df: pd.DataFrame) -> np.ndarray:
    """Probabilidade de pagamento com componente aleatório controlado."""
    rng = np.random.default_rng(42)

    p_base = np.where(df["dias_em_atraso"] < 90, 0.65, 0.25)

    is_consignado = df["produto"].str.lower().str.contains("consig", na=False)
    p_base = np.where(is_consignado, p_base + 0.20, p_base)

    alta_divida = df["comprometimento_renda"] > 0.5
    p_base = np.where(alta_divida, p_base - 0.10, p_base)

    p_base = np.clip(p_base, 0.05, 0.95)
    y = (rng.uniform(size=len(df)) < p_base).astype(int)
    return y


def treinar(caminho_csv: str) -> None:
    print(f"[1/5] Carregando dados: {caminho_csv}")
    df = _carregar_csv(caminho_csv)
    print(f"      {len(df)} registros, {len(df.columns)} colunas")

    print("[2/5] Pré-processando features")
    X, cat_cols = _preprocessar(df)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("[3/5] Criando clusters KMeans (k=5)")
    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df["cluster"] = clusters

    print("[4/5] Treinando RandomForestClassifier")
    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(0)
    y = _criar_alvo_simulado(df)

    X_rf = np.column_stack([X_scaled, clusters])
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_rf, y)

    feature_names = list(X.columns) + ["cluster"]
    clf.feature_names_in_ = np.array(feature_names)

    print("[5/5] Salvando modelos")
    joblib.dump(clf, MODEL_DIR / "mizan_model.pkl")
    joblib.dump(kmeans, MODEL_DIR / "kmeans.pkl")
    joblib.dump(
        {"scaler": scaler, "cat_cols": cat_cols, "feature_names": feature_names},
        MODEL_DIR / "scaler.pkl",
    )

    acc_treino = clf.score(X_rf, y)
    print(f"\nConcluído. Acurácia no treino: {acc_treino:.2%}")
    print(f"Distribuição de clusters:\n{pd.Series(clusters).value_counts().sort_index()}")
    print(f"Arquivos salvos em: {MODEL_DIR}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "carteira_mizan.csv"
    treinar(csv_path)
