"""
Diagnóstico de qualidade do modelo de crédito Mizan.

Responde às perguntas que importam antes de mostrar o modelo pra um banco:
  - O modelo está decorando os dados de treino (overfitting) ou generaliza?
  - A probabilidade que ele dá é confiável (calibração), ou só "parece" score?
  - Tem dado suficiente pra sustentar a complexidade do modelo?
  - Onde ele erra mais: falso positivo (achou que pagava e não pagou) ou o contrário?

Reaproveita a mesma pipeline de dados do retrain.py (mesmos feedbacks reais),
mas nunca sobrescreve o modelo em produção — é só leitura/avaliação.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, brier_score_loss, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import RobustScaler

_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

MIN_AMOSTRAS_DIAGNOSTICO = 30

# Regra prática: gradient boosting raso (max_depth=4) pede >= ~20 amostras por
# feature codificada pra não decorar ruído. Abaixo disso, desconfie de qualquer métrica.
AMOSTRAS_POR_FEATURE_MINIMO = 20

# Gap (treino - validação cruzada) acima do qual chamamos de overfitting.
GAP_MODERADO = 0.10
GAP_SEVERO   = 0.20


def _preparar_dataset():
    """Busca feedbacks reais + features das predições, mesma lógica do retreinamento."""
    from db import get_db
    from model.retrain import _buscar_feedbacks, _buscar_predicoes, _montar_dataset, _preprocessar

    db = get_db()
    feedbacks = _buscar_feedbacks(db)
    if len(feedbacks) < MIN_AMOSTRAS_DIAGNOSTICO:
        return None, len(feedbacks)

    pred_ids = [f["predicao_id"] for f in feedbacks]
    pred_map = _buscar_predicoes(db, pred_ids)
    df = _montar_dataset(feedbacks, pred_map)
    df = df.drop(columns=["_created_at", "cpf"], errors="ignore")

    if df["pagou"].nunique() < 2:
        return None, len(df)

    X, features_numericas, cat_cols, medians, modes = _preprocessar(df)
    return {"df": df, "X": X, "features_numericas": features_numericas, "cat_cols": cat_cols}, len(df)


def _matriz_confusao_dict(y_true, y_pred) -> dict:
    """Confusão 2x2 nomeada — mais legível que uma matriz crua no front."""
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "verdadeiro_positivo":  int(tp),   # previu que pagava, pagou
        "falso_positivo":       int(fp),   # previu que pagava, não pagou (custo: esforço de cobrança desperdiçado)
        "verdadeiro_negativo":  int(tn),   # previu que não pagava, não pagou
        "falso_negativo":       int(fn),   # previu que não pagava, pagou (custo: oportunidade perdida)
    }


def _calibracao_por_faixa(y_true, y_proba, n_faixas: int = 5) -> list[dict]:
    """
    Reliability diagram simplificado: divide as previsões em faixas de probabilidade
    e compara a média prevista com a taxa real observada em cada faixa.
    Modelo bem calibrado: previsto ≈ observado em toda faixa.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_proba = np.asarray(y_proba, dtype=float)
    ordem = np.argsort(y_proba)
    faixas = np.array_split(ordem, min(n_faixas, len(ordem)))
    resultado = []
    for idx in faixas:
        if len(idx) == 0:
            continue
        resultado.append({
            "n":                 int(len(idx)),
            "prob_media_prevista": round(float(y_proba[idx].mean()), 3),
            "taxa_real_observada": round(float(y_true[idx].mean()), 3),
        })
    return resultado


def avaliar_qualidade() -> dict:
    dataset, n_disponivel = _preparar_dataset()
    if dataset is None:
        return {
            "ok": False,
            "motivo": (
                f"Dados insuficientes para diagnóstico: {n_disponivel} feedbacks reais "
                f"(mínimo: {MIN_AMOSTRAS_DIAGNOSTICO}), ou alvo sem as duas classes (pagou/não pagou)."
            ),
            "n_amostras": n_disponivel,
        }

    df, X = dataset["df"], dataset["X"]
    y = df["pagou"].values
    n_amostras = len(y)

    scaler   = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    k = min(4, max(2, n_amostras // 30))
    kmeans   = KMeans(n_clusters=k, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    X_clf    = np.column_stack([X_scaled, clusters])
    n_features = X_clf.shape[1]

    min_leaf = max(5, min(20, n_amostras // 50))
    params = dict(
        max_iter=200, max_depth=4, learning_rate=0.05,
        min_samples_leaf=min_leaf, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    )

    # ── 1. Treino no dataset inteiro (mede o quanto o modelo "decora" os próprios dados) ──
    clf_treino = HistGradientBoostingClassifier(**params).fit(X_clf, y)
    treino_acuracia = round(float(accuracy_score(y, clf_treino.predict(X_clf))), 4)
    treino_auc = round(float(roc_auc_score(y, clf_treino.predict_proba(X_clf)[:, 1])), 4)

    # ── 2. Validação cruzada (mede generalização) ──
    n_splits = max(2, min(5, int(y.sum()), int(n_amostras - y.sum())))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_acuracias = cross_val_score(HistGradientBoostingClassifier(**params), X_clf, y, cv=cv, scoring="accuracy")
    cv_aucs      = cross_val_score(HistGradientBoostingClassifier(**params), X_clf, y, cv=cv, scoring="roc_auc")
    cv_acuracia_media = round(float(cv_acuracias.mean()), 4)
    cv_auc_media      = round(float(cv_aucs.mean()), 4)

    # ── 3. Holdout real: 20% nunca visto pelo modelo que gera as métricas de erro ──
    X_tr, X_ho, y_tr, y_ho = train_test_split(X_clf, y, test_size=0.2, stratify=y, random_state=42)
    clf_ho = HistGradientBoostingClassifier(**params).fit(X_tr, y_tr)
    y_pred_ho  = clf_ho.predict(X_ho)
    y_proba_ho = clf_ho.predict_proba(X_ho)[:, 1]

    holdout_acuracia = round(float(accuracy_score(y_ho, y_pred_ho)), 4)
    holdout_auc       = round(float(roc_auc_score(y_ho, y_proba_ho)), 4) if len(np.unique(y_ho)) == 2 else None
    precisao, revocacao, f1, _ = precision_recall_fscore_support(
        y_ho, y_pred_ho, average="binary", zero_division=0,
    )
    brier = round(float(brier_score_loss(y_ho, y_proba_ho)), 4)

    # ── 4. Veredito de overfitting: gap entre acerto no treino e na validação cruzada ──
    gap = round(treino_acuracia - cv_acuracia_media, 4)
    if gap >= GAP_SEVERO:
        veredito = "overfitting_severo"
    elif gap >= GAP_MODERADO:
        veredito = "overfitting_moderado"
    else:
        veredito = "saudavel"

    # ── 5. Dados suficientes para a complexidade do modelo? ──
    amostras_por_feature = round(n_amostras / n_features, 1)
    complexidade_adequada = amostras_por_feature >= AMOSTRAS_POR_FEATURE_MINIMO

    return {
        "ok": True,
        "n_amostras": n_amostras,
        "n_features": n_features,
        "amostras_por_feature": amostras_por_feature,
        "complexidade_adequada": complexidade_adequada,
        "overfitting": {
            "veredito": veredito,
            "gap_treino_menos_cv": gap,
            "treino_acuracia": treino_acuracia,
            "treino_auc": treino_auc,
            "cv_acuracia_media": cv_acuracia_media,
            "cv_acuracia_std": round(float(cv_acuracias.std()), 4),
            "cv_auc_media": cv_auc_media,
            "cv_auc_std": round(float(cv_aucs.std()), 4),
        },
        "holdout": {
            "n_amostras": int(len(y_ho)),
            "acuracia": holdout_acuracia,
            "auc_roc": holdout_auc,
            "precisao": round(float(precisao), 4),
            "revocacao": round(float(revocacao), 4),
            "f1": round(float(f1), 4),
            "brier_score": brier,
            "matriz_confusao": _matriz_confusao_dict(y_ho, y_pred_ho),
        },
        "calibracao_por_faixa": _calibracao_por_faixa(y_ho, y_proba_ho),
    }
