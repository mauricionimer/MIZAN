"""
Treina o modelo de recuperabilidade de crédito do Mizan v2.

Algoritmo: HistGradientBoostingClassifier (análogo ao LightGBM) + KMeans
Scaler:    RobustScaler (mediana/IQR — robusto a outliers financeiros)
Features:  7 numéricas (originais + log-transforms + ratio diário) + categóricas

Uso sem dados reais:
    python -m model.train               # gera dados sintéticos automaticamente
    python -m model.train carteira.csv  # treina com CSV real
"""

import sys
from datetime import datetime as _dt
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import RobustScaler

MODEL_DIR     = Path(__file__).parent
MODEL_VERSION = 2

# Colunas obrigatórias mínimas
COLUNAS_MINIMAS = ["cpf", "valor_divida", "dias_em_atraso"]

# Aliases: nomes variantes → nome padrão (Serasa, bancos, ERPs, etc.)
ALIASES: dict[str, str] = {
    'dias_atraso':        'dias_em_atraso',
    'dias_inadimplente':  'dias_em_atraso',
    'dias_vencido':       'dias_em_atraso',
    'diasematraso':       'dias_em_atraso',
    'renda':              'renda_estimada',
    'renda_mensal':       'renda_estimada',
    'salario':            'renda_estimada',
    'renda_bruta':        'renda_estimada',
    'rendaestimada':      'renda_estimada',
    'valor':              'valor_divida',
    'saldo_devedor':      'valor_divida',
    'saldo':              'valor_divida',
    'divida':             'valor_divida',
    'valordivida':        'valor_divida',
    'estado':             'uf',
    'uf_devedor':         'uf',
    'estado_devedor':     'uf',
    'produto_financeiro': 'produto',
    'tipo_produto':       'produto',
    'tipo_divida':        'produto',
}

# Colunas que nunca devem ser features do modelo
_COLS_EXCLUIR = {
    'cpf', 'nome', 'pagou', 'rank', 'score_recuperabilidade',
    'cluster_id', 'perfil_cluster', 'recomendacao', 'abordagem',
    'motivo_prioridade', 'carteira_id', 'created_at', 'id',
}

# Limite de valores únicos para tratar coluna como categórica
_CAT_MAX_UNIQUE = 30

SCORE_PRODUTO = {"consignado": 100, "veiculo": 70, "pessoal": 40, "cartao": 20}


def _score_produto_s(serie: pd.Series) -> pd.Series:
    def _lookup(val: str) -> float:
        val = str(val).lower()
        for chave, pts in SCORE_PRODUTO.items():
            if chave in val:
                return pts
        return 30
    return serie.map(_lookup)


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas usando ALIASES (case-insensitive)."""
    rename = {col: ALIASES[col.lower().strip()] for col in df.columns if col.lower().strip() in ALIASES}
    return df.rename(columns=rename) if rename else df


def _adicionar_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona features derivadas quando as colunas base existem."""
    df = df.copy()
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
    # Sazonalidade: mês da análise (1-12) — cobrança é mais fácil em jan/fev, difícil em dez
    if 'mes_analise' not in df.columns:
        df['mes_analise'] = _dt.now().month
    return df


def _detectar_features(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Auto-detecta colunas numéricas e categóricas como features."""
    numericas, categoricas = [], []
    for col in df.columns:
        if col in _COLS_EXCLUIR:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            numericas.append(col)
        elif df[col].nunique() <= _CAT_MAX_UNIQUE:
            categoricas.append(col)
    return numericas, categoricas


def _preprocessar(df: pd.DataFrame):
    """Retorna (X, features_numericas, cat_cols, medians, modes)."""
    df = _normalizar_colunas(df)
    df = _adicionar_derivadas(df)

    numericas, categoricas = _detectar_features(df)

    medians: dict[str, float] = {}
    for col in numericas:
        med = float(df[col].median()) if not df[col].isna().all() else 0.0
        df[col] = df[col].fillna(med)
        medians[col] = med

    modes: dict[str, str] = {}
    for col in categoricas:
        mv = df[col].mode()
        mode = str(mv[0]) if len(mv) > 0 else 'outro'
        df[col] = df[col].fillna(mode).astype(str)
        modes[col] = mode

    df_enc = pd.get_dummies(df[categoricas], drop_first=False) if categoricas else pd.DataFrame(index=df.index)
    cat_cols = df_enc.columns.tolist()
    X = pd.concat([df[numericas], df_enc], axis=1)
    return X, numericas, cat_cols, medians, modes


def _criar_alvo_simulado(df: pd.DataFrame) -> np.ndarray:
    """Score ponderado de recuperabilidade (0-100) → binário. Usa colunas disponíveis."""
    s_dias = (
        (100 - (df["dias_em_atraso"].clip(0, 360) / 360) * 100).clip(0, 100) * 0.40
        if "dias_em_atraso" in df.columns
        else pd.Series(50.0 * 0.40, index=df.index)
    )
    s_comp = (
        (100 - (df["comprometimento_renda"].clip(0, 2) / 2) * 100).clip(0, 100) * 0.25
        if "comprometimento_renda" in df.columns
        else pd.Series(50.0 * 0.25, index=df.index)
    )
    s_prod = (
        _score_produto_s(df["produto"]) * 0.20
        if "produto" in df.columns
        else pd.Series(30.0 * 0.20, index=df.index)
    )

    if "tentativas_contato" in df.columns:
        tent = df["tentativas_contato"]
        s_tent = pd.Series(
            np.where(tent == 0, 80, np.where(tent <= 3, 60, 30)),
            index=df.index, dtype=float,
        ) * 0.15
    else:
        s_tent = pd.Series(50.0 * 0.15, index=df.index)

    # Bônus: score_serasa/bureau melhora a estimativa de alvo sintético
    s_bureau = pd.Series(0.0, index=df.index)
    for bureau_col in ('score_serasa', 'score_bureau', 'score_credito', 'credit_score'):
        if bureau_col in df.columns:
            s_bureau = ((df[bureau_col].clip(0, 1000) / 1000) * 100 - 50).clip(-20, 20)
            break

    score = (s_dias + s_comp + s_prod + s_tent + s_bureau).clip(0, 100)

    if "promessa_quebrada" in df.columns:
        quebrou = df["promessa_quebrada"].astype(str).str.lower().isin(
            ["true", "1", "sim", "yes", "s"]
        )
        score = (score - quebrou * 30).clip(0, 100)

    return (score >= 50).astype(int).values


def _escolher_k(X_scaled: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    ks      = list(range(k_min, k_max + 1))
    inercias = [KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled).inertia_ for k in ks]
    arr     = np.array(inercias)
    deltas  = arr[:-1] - arr[1:]
    total   = arr[0] - arr[-1]
    if total == 0 or len(deltas) < 2:
        return k_min
    accel   = deltas[:-1] - deltas[1:]
    k_ideal = ks[int(np.argmax(accel)) + 1]
    print(f"      k ideal: {k_ideal}")
    return k_ideal


def _gerar_labels_clusters(df_cl: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    df_cl = df_cl.copy()
    has_produto = "produto" in df_cl.columns
    has_comp    = "comprometimento_renda" in df_cl.columns
    has_dias    = "dias_em_atraso" in df_cl.columns

    if has_produto:
        df_cl["_sp"] = _score_produto_s(df_cl["produto"])

    agg_dict: dict = {}
    if has_dias:    agg_dict["dias_medio"] = ("dias_em_atraso",       "mean")
    if has_comp:    agg_dict["comp_medio"] = ("comprometimento_renda", "mean")
    if has_produto: agg_dict["sp_medio"]   = ("_sp",                   "mean")

    if not agg_dict:
        return {i: f"Cluster {i}" for i in range(n_clusters)}

    resumo = df_cl.groupby("cluster").agg(**agg_dict)
    labels: dict[int, str] = {}
    for cid, row in resumo.iterrows():
        partes = []
        if has_dias:
            partes.append(
                "Recente" if row["dias_medio"] < 60 else
                "Intermediário" if row["dias_medio"] < 180 else "Crônico"
            )
        if has_comp:
            partes.append(
                "Baixo Comprometimento" if row["comp_medio"] < 0.3 else
                "Comprometimento Moderado" if row["comp_medio"] < 0.7 else "Alto Comprometimento"
            )
        if has_produto:
            partes.append(
                "Consignado" if row["sp_medio"] >= 80 else
                "Veículo"    if row["sp_medio"] >= 60 else
                "Pessoal"    if row["sp_medio"] >= 35 else "Cartão"
            )
        labels[int(cid)] = " · ".join(partes) if partes else f"Cluster {cid}"
    return labels


def _gerar_dados_sinteticos(n: int = 3000, seed: int = 42) -> pd.DataFrame:
    """Gera carteira sintética com distribuições realistas para crédito brasileiro."""
    rng = np.random.default_rng(seed)

    produtos = rng.choice(
        ["consignado", "veiculo", "pessoal", "cartao"], n,
        p=[0.20, 0.15, 0.40, 0.25],
    )
    ufs = rng.choice(
        ["SP","RJ","MG","RS","PR","BA","SC","GO","PE","CE",
         "MA","PA","MT","MS","ES","DF","AL","PB","RN","PI"], n,
        p=[0.22,0.10,0.10,0.07,0.06,0.06,0.04,0.04,0.04,0.04,
           0.03,0.03,0.02,0.02,0.02,0.02,0.01,0.01,0.01,0.01],
    )
    status_vals = rng.choice(
        ["inadimplente", "em_atraso", "renegociado", "ativo"], n,
        p=[0.50, 0.25, 0.15, 0.10],
    )

    mu_vals = {"consignado": 9.5, "veiculo": 9.8, "pessoal": 8.8, "cartao": 8.2}
    valor_divida = np.array([
        np.exp(rng.normal(mu_vals[p], 1.0)) for p in produtos
    ]).clip(500, 300_000)

    renda_mu = {"consignado": 3800, "veiculo": 4500, "pessoal": 2200, "cartao": 1800}
    renda_estimada = np.array([
        max(700.0, rng.lognormal(np.log(renda_mu[p]), 0.5)) for p in produtos
    ])

    dias_exp = {"inadimplente": 200, "em_atraso": 40, "renegociado": 100, "ativo": 10}
    dias_em_atraso = np.array([
        max(1, int(rng.exponential(dias_exp[s]))) for s in status_vals
    ]).clip(1, 720)

    return pd.DataFrame({
        "cpf":            [f"{i:011d}" for i in range(n)],
        "nome":           [f"Cliente {i}" for i in range(n)],
        "produto":        produtos,
        "status":         status_vals,
        "uf":             ufs,
        "valor_divida":   valor_divida.astype(float),
        "renda_estimada": renda_estimada.astype(float),
        "dias_em_atraso": dias_em_atraso.astype(int),
        "mes_analise":    rng.integers(1, 13, n).astype(int),
    })


def _treinar_com_df(df: pd.DataFrame) -> None:
    print(f"      {len(df)} registros, {len(df.columns)} colunas")

    print("[2/6] Pré-processando features (auto-detect + RobustScaler)")
    X, features_numericas, cat_cols, medians, modes = _preprocessar(df)
    df_aug = df.copy()
    if "comprometimento_renda" in X.columns:
        df_aug["comprometimento_renda"] = X["comprometimento_renda"]
    print(f"      {len(features_numericas)} numéricas + {len(cat_cols)} categóricas (encoded)")

    scaler   = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    print("[3/6] Selecionando número de clusters (cotovelo, k=2..10)")
    k_ideal = _escolher_k(X_scaled)

    print(f"[4/6] KMeans (k={k_ideal})")
    kmeans   = KMeans(n_clusters=k_ideal, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df_aug["cluster"] = clusters
    cluster_labels    = _gerar_labels_clusters(df_aug, k_ideal)
    for cid, label in sorted(cluster_labels.items()):
        print(f"        [{cid}] {label}  (n={(clusters == cid).sum()})")

    print("[5/6] Treinando HistGradientBoostingClassifier (class_weight=balanced)")
    y     = _criar_alvo_simulado(df_aug)
    n_tot = len(y)
    print(f"      Alvo: recuperável={y.sum()} ({y.mean():.1%}) | não recuperável={n_tot-y.sum()}")

    X_clf    = np.column_stack([X_scaled, clusters])
    min_leaf = max(5, n_tot // 30)
    clf = HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, learning_rate=0.05,
        min_samples_leaf=min_leaf, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    )
    clf.fit(X_clf, y)

    # Cross-validation (StratifiedKFold para dados sintéticos)
    n_splits = max(2, min(5, int(y.sum()), int(n_tot - y.sum())))
    cv  = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    acc = cross_val_score(clf, X_clf, y, cv=cv, scoring="accuracy")
    print(f"      CV Acurácia: {acc.mean():.2%} ± {acc.std():.2%}")
    if len(np.unique(y)) == 2:
        auc = cross_val_score(clf, X_clf, y, cv=cv, scoring="roc_auc")
        print(f"      CV AUC-ROC:  {auc.mean():.3f} ± {auc.std():.3f}")

    # Calibração de probabilidade (Platt scaling) quando há dados suficientes
    clf_to_save = clf
    if n_tot >= 200 and len(np.unique(y)) == 2:
        try:
            X_tr, X_cal, y_tr, y_cal = train_test_split(
                X_clf, y, test_size=0.2, stratify=y, random_state=42,
            )
            clf_base = HistGradientBoostingClassifier(
                max_iter=200, max_depth=4, learning_rate=0.05,
                min_samples_leaf=min_leaf, l2_regularization=1.0,
                class_weight="balanced", random_state=42,
            )
            clf_base.fit(X_tr, y_tr)
            clf_to_save = CalibratedClassifierCV(clf_base, cv="prefit", method="sigmoid")
            clf_to_save.fit(X_cal, y_cal)
            print("      Calibração Platt aplicada.")
        except Exception as _ce:
            print(f"      Calibração ignorada: {_ce}")
            clf_to_save = clf

    feature_names = list(X.columns) + ["cluster"]

    print("[6/6] Salvando modelos")
    joblib.dump(clf_to_save, MODEL_DIR / "mizan_model.pkl")
    joblib.dump(kmeans, MODEL_DIR / "kmeans.pkl")
    joblib.dump({
        "scaler":               scaler,
        "cat_cols":             cat_cols,
        "features_numericas":   features_numericas,
        "features_categoricas": list(modes.keys()),
        "medians":              medians,
        "modes":                modes,
        "feature_names":        feature_names,
        "cluster_labels":       cluster_labels,
        "k":                    k_ideal,
        "model_version":        MODEL_VERSION,
    }, MODEL_DIR / "scaler.pkl")
    print(f"\nConcluído. Arquivos salvos em: {MODEL_DIR}")


def treinar(caminho: str) -> None:
    print(f"[1/6] Carregando dados: {caminho}")
    if caminho.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(caminho)
    else:
        df = pd.read_csv(caminho)
    df = _normalizar_colunas(df)
    faltantes = [c for c in COLUNAS_MINIMAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {faltantes}")
    _treinar_com_df(df)


def treinar_sintetico() -> None:
    """Treina com dados sintéticos realistas. Chamado automaticamente se modelos não existirem."""
    print("[1/6] Gerando dados sintéticos (3000 registros)...")
    _treinar_com_df(_gerar_dados_sinteticos(n=3000))


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    if csv_path:
        treinar(csv_path)
    else:
        treinar_sintetico()
