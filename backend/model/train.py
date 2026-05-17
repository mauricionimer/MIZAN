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

FEATURES_CATEGORICAS = ["produto", "status", "uf"]
FEATURES_NUMERICAS = [
    "valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"
]

SCORE_PRODUTO = {
    "consignado": 100,
    "veiculo":    70,
    "pessoal":    40,
    "cartao":     20,
}


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


# ---------------------------------------------------------------------------
# Alvo simulado ponderado
# ---------------------------------------------------------------------------

def _score_produto(serie: pd.Series) -> pd.Series:
    """Mapeia produto para score 0-100 (case-insensitive, partial match)."""
    def _lookup(val: str) -> float:
        val = str(val).lower()
        for chave, pts in SCORE_PRODUTO.items():
            if chave in val:
                return pts
        return 30  # produto desconhecido recebe pontuação conservadora
    return serie.map(_lookup)


def _score_dias_atraso(dias: pd.Series) -> pd.Series:
    """Converte dias em atraso em score 0-100 (decaimento linear até 360 dias)."""
    return (100 - (dias.clip(0, 360) / 360) * 100).clip(0, 100)


def _score_comprometimento(comp: pd.Series) -> pd.Series:
    """Comprometimento de renda 0-1+ → score 0-100 (quanto menor, melhor)."""
    return (100 - (comp.clip(0, 2) / 2) * 100).clip(0, 100)


def _score_tentativas(tentativas: pd.Series) -> pd.Series:
    """Zero tentativas recebe score alto (devedor ainda não alcançado = oportunidade)."""
    score = np.where(tentativas == 0, 80, np.where(tentativas <= 3, 60, 30))
    return pd.Series(score, index=tentativas.index, dtype=float)


def _criar_alvo_simulado(df: pd.DataFrame) -> np.ndarray:
    """
    Score ponderado de recuperabilidade (0-100):
      40% dias_em_atraso    – menos dias = melhor
      25% comprometimento   – menor comprometimento = melhor
      20% produto           – consignado > veiculo > pessoal > cartao
      15% tentativas_contato – zero tentativas = ainda há janela de contato

    promessa_quebrada (se existir) reduz o score final em 30 pontos.
    Threshold de 50 pontos define alvo binário (1 = recuperável).
    """
    s_dias   = _score_dias_atraso(df["dias_em_atraso"]) * 0.40
    s_comp   = _score_comprometimento(df["comprometimento_renda"]) * 0.25
    s_prod   = _score_produto(df["produto"]) * 0.20

    if "tentativas_contato" in df.columns:
        s_tent = _score_tentativas(df["tentativas_contato"]) * 0.15
    else:
        s_tent = pd.Series(50.0 * 0.15, index=df.index)

    score = s_dias + s_comp + s_prod + s_tent

    if "promessa_quebrada" in df.columns:
        quebrou = df["promessa_quebrada"].astype(str).str.lower().isin(
            ["true", "1", "sim", "yes", "s"]
        )
        score = score - quebrou * 30

    score = score.clip(0, 100)
    y = (score >= 50).astype(int).values
    return y


# ---------------------------------------------------------------------------
# Número de clusters automático – método do cotovelo
# ---------------------------------------------------------------------------

def _escolher_k(X_scaled: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    """
    Testa KMeans de k_min a k_max e escolha o k no ponto de maior
    variação relativa de queda de inércia (cotovelo).
    """
    ks = list(range(k_min, k_max + 1))
    inercias = []
    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inercias.append(km.inertia_)

    # Diferença de primeira ordem normalizada pela queda total
    inercias = np.array(inercias)
    deltas = inercias[:-1] - inercias[1:]        # queda absoluta
    total_queda = inercias[0] - inercias[-1]
    if total_queda == 0:
        return k_min

    # Segundo derivada: onde a taxa de queda desacelera mais (cotovelo)
    accel = deltas[:-1] - deltas[1:]             # variação da variação
    k_ideal = ks[np.argmax(accel) + 1]           # +1 porque accel tem k_min+1 como base

    print(f"      Inércias testadas (k={k_min}..{k_max}): {[f'{v:.0f}' for v in inercias]}")
    print(f"      k ideal pelo cotovelo: {k_ideal}")
    return k_ideal


# ---------------------------------------------------------------------------
# Labels dinâmicos por características médias do cluster
# ---------------------------------------------------------------------------

def _gerar_labels_clusters(df_com_cluster: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    """
    Atribui labels descritivos a cada cluster com base nas médias de:
      - dias_em_atraso  → risco temporal
      - comprometimento_renda → pressão financeira
      - score do produto (proxy de garantia)
    """
    resumo = (
        df_com_cluster.groupby("cluster")
        .agg(
            dias_medio=("dias_em_atraso", "mean"),
            comp_medio=("comprometimento_renda", "mean"),
            score_prod_medio=("_score_prod", "mean"),
        )
    )

    labels: dict[int, str] = {}
    for cluster_id, row in resumo.iterrows():
        partes = []

        # Dimensão temporal
        if row["dias_medio"] < 60:
            partes.append("Recente")
        elif row["dias_medio"] < 180:
            partes.append("Intermediário")
        else:
            partes.append("Crônico")

        # Dimensão financeira
        if row["comp_medio"] < 0.3:
            partes.append("Baixo Comprometimento")
        elif row["comp_medio"] < 0.7:
            partes.append("Comprometimento Moderado")
        else:
            partes.append("Alto Comprometimento")

        # Dimensão de produto
        if row["score_prod_medio"] >= 80:
            partes.append("Consignado")
        elif row["score_prod_medio"] >= 60:
            partes.append("Veículo")
        elif row["score_prod_medio"] >= 35:
            partes.append("Pessoal")
        else:
            partes.append("Cartão")

        labels[int(cluster_id)] = " · ".join(partes)

    return labels


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------

def treinar(caminho_csv: str) -> None:
    print(f"[1/6] Carregando dados: {caminho_csv}")
    df = _carregar_csv(caminho_csv)
    print(f"      {len(df)} registros, {len(df.columns)} colunas")

    print("[2/6] Pré-processando features")
    X, cat_cols = _preprocessar(df)
    df["comprometimento_renda"] = X["comprometimento_renda"]
    df["_score_prod"] = _score_produto(df["produto"])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("[3/6] Selecionando número de clusters (método do cotovelo, k=2..10)")
    k_ideal = _escolher_k(X_scaled)

    print(f"[4/6] Criando clusters KMeans (k={k_ideal})")
    kmeans = KMeans(n_clusters=k_ideal, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df["cluster"] = clusters

    cluster_labels = _gerar_labels_clusters(df, k_ideal)
    print("      Labels gerados:")
    for cid, label in sorted(cluster_labels.items()):
        n = (clusters == cid).sum()
        print(f"        [{cid}] {label}  (n={n})")

    print("[5/6] Treinando RandomForestClassifier")
    y = _criar_alvo_simulado(df)
    print(f"      Distribuição do alvo: recuperável={y.sum()} ({y.mean():.1%}) | não recuperável={len(y)-y.sum()}")

    X_rf = np.column_stack([X_scaled, clusters])
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_rf, y)

    feature_names = list(X.columns) + ["cluster"]
    clf.feature_names_in_ = np.array(feature_names)

    print("[6/6] Salvando modelos")
    joblib.dump(clf, MODEL_DIR / "mizan_model.pkl")
    joblib.dump(kmeans, MODEL_DIR / "kmeans.pkl")
    joblib.dump(
        {
            "scaler": scaler,
            "cat_cols": cat_cols,
            "feature_names": feature_names,
            "cluster_labels": cluster_labels,
            "k": k_ideal,
        },
        MODEL_DIR / "scaler.pkl",
    )

    acc_treino = clf.score(X_rf, y)
    print(f"\nConcluído. Acurácia no treino: {acc_treino:.2%}")
    print(f"Arquivos salvos em: {MODEL_DIR}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "carteira_mizan.csv"
    treinar(csv_path)
