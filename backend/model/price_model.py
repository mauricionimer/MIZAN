"""
Modelo de precificação de carteira — Mizan.

Prevê a taxa de recuperação esperada (valor_recuperado / valor_divida) usando
regressão calibrada com feedbacks reais. Substitui a premissa declarada na
fórmula VER = Σ(valor_divida × taxa) por uma estimativa baseada em dados.

IMPORTANTE — o alvo é INCONDICIONAL. Em `treinar`, quem não pagou entra na
amostra com taxa 0.0, não é descartado. Ou seja, a previsão já embute a
probabilidade de pagamento:

    taxa_prevista ≈ P(paga) × E[recuperado / dívida | paga]

Logo `valor_divida × taxa_prevista` é o valor esperado de recuperação, e
multiplicar de novo pela probabilidade do classificador contaria duas vezes.

Em termos de Basileia: `valor_divida` é o EAD, `taxa_prevista` é a taxa de
recuperação (1 − LGD) e `valor_divida × (1 − taxa_prevista)` é a perda
esperada sobre essa dívida.

POR EMPRESA. O modelo de preço é treinado com os pagamentos de uma empresa,
junto com a versão do modelo de score dela (model/treino_feedbacks.py), e só
vale para ela, depois que o COMANDO ativa a versão. O antigo arquivo único
(model/price_model.pkl) era treinado com os pagamentos de todas as empresas e
valia para todas, inclusive as que têm modelo próprio (achado D10); ele não é
mais lido. Empresa sem modelo de preço usa a premissa declarada.
"""

import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR        = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent
PRICE_MODEL_FILE = MODEL_DIR / "price_model.pkl"

MIN_AMOSTRAS  = 15   # mínimo total de feedbacks com predicao mapeada
MIN_PAGAMENTOS = 5   # mínimo de pagamentos reais (taxa > 0) para ter sinal

_UF_REGIAO: dict[str, str] = {
    "AC": "norte",  "AM": "norte",  "AP": "norte",  "PA": "norte",
    "RO": "norte",  "RR": "norte",  "TO": "norte",
    "AL": "nordeste", "BA": "nordeste", "CE": "nordeste", "MA": "nordeste",
    "PB": "nordeste", "PE": "nordeste", "PI": "nordeste", "RN": "nordeste",
    "SE": "nordeste",
    "DF": "centro_oeste", "GO": "centro_oeste", "MS": "centro_oeste", "MT": "centro_oeste",
    "ES": "sudeste", "MG": "sudeste", "RJ": "sudeste", "SP": "sudeste",
    "PR": "sul", "RS": "sul", "SC": "sul",
}
_PRODUTOS = ["consignado", "veiculo", "pessoal", "cartao"]
_REGIOES  = ["norte", "nordeste", "centro_oeste", "sudeste", "sul"]


def _safe(val, default=0.0) -> float:
    try:
        v = float(val) if val is not None else default
        return default if v != v else v  # NaN check
    except (TypeError, ValueError):
        return default


def _features(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        valor = max(0.0, _safe(r.get("valor_divida")))
        score = max(0.0, min(100.0, _safe(r.get("score_recuperabilidade"), 50.0))) / 100.0
        dias  = min(_safe(r.get("dias_em_atraso")), 720.0) / 720.0
        renda = max(0.0, _safe(r.get("renda_estimada")))
        comp  = min((valor / renda) if renda > 0 else 1.0, 10.0) / 10.0

        produto = str(r.get("produto") or "").lower()
        regiao  = _UF_REGIAO.get(str(r.get("uf") or "").upper(), "sudeste")

        row: dict = {
            "score":           score,
            "log_valor":       np.log1p(valor) / np.log1p(1_000_000),
            "dias":            dias,
            "comprometimento": comp,
            "log_renda":       min(np.log1p(renda) / np.log1p(10_000), 1.0),
        }
        for p in _PRODUTOS:
            row[f"prod_{p}"] = 1.0 if p in produto else 0.0
        for reg in _REGIOES:
            row[f"reg_{reg}"] = 1.0 if regiao == reg else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def treinar(feedbacks: list[dict], pred_map: dict[str, dict], destino: "Path | None" = None) -> dict:
    """
    Treina regressão de taxa de recuperação real e grava em `destino`.

    feedbacks : [{"predicao_id", "pagou", "valor_recuperado"}]
    pred_map  : {id -> {"score_recuperabilidade", "valor_divida", ...}}
    """
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import KFold, cross_val_score
    from sklearn.preprocessing import RobustScaler

    registros: list[dict] = []
    taxas: list[float]    = []

    for fb in feedbacks:
        pred = pred_map.get(fb.get("predicao_id") or "")
        if not pred:
            continue
        valor_divida = max(0.0, _safe(pred.get("valor_divida")))
        if valor_divida <= 0:
            continue
        if fb.get("pagou"):
            taxa = min(_safe(fb.get("valor_recuperado")) / valor_divida, 1.0)
        else:
            taxa = 0.0
        registros.append(pred)
        taxas.append(taxa)

    n_total     = len(registros)
    n_pagamentos = sum(1 for t in taxas if t > 0)

    if n_total < MIN_AMOSTRAS or n_pagamentos < MIN_PAGAMENTOS:
        msg = (
            f"Dados insuficientes para price model: {n_total} amostras, "
            f"{n_pagamentos} pagamentos reais "
            f"(mínimos: {MIN_AMOSTRAS} amostras, {MIN_PAGAMENTOS} pagamentos)."
        )
        print(f"[PriceModel] {msg}")
        return {"ok": False, "motivo": msg, "n_amostras": n_total, "n_pagamentos": n_pagamentos}

    X = _features(registros)
    y = np.array(taxas, dtype=float)

    scaler   = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    reg = HistGradientBoostingRegressor(
        max_iter=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=max(3, n_total // 20),
        l2_regularization=1.0, random_state=42,
    )
    reg.fit(X_scaled, y)

    n_splits = min(5, max(2, n_pagamentos // 3))
    cv       = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    r2_scores  = cross_val_score(reg, X_scaled, y, cv=cv, scoring="r2")
    mae_scores = cross_val_score(reg, X_scaled, y, cv=cv, scoring="neg_mean_absolute_error")

    r2_medio  = round(float(r2_scores.mean()), 3)
    mae_medio = round(float(-mae_scores.mean()), 3)

    meta = {
        "scaler":       scaler,
        "regressor":    reg,
        "feature_cols": list(X.columns),
        "n_amostras":   n_total,
        "n_pagamentos": n_pagamentos,
        "r2_medio":     r2_medio,
        "mae_medio":    mae_medio,
    }
    joblib.dump(meta, destino or PRICE_MODEL_FILE)
    print(
        f"[PriceModel] Treinado — {n_total} amostras, {n_pagamentos} pagamentos | "
        f"R²={r2_medio:.3f}, MAE={mae_medio:.3f}"
    )
    return {"ok": True, "n_amostras": n_total, "n_pagamentos": n_pagamentos,
            "r2_medio": r2_medio, "mae_medio": mae_medio}


def _arquivo_ativo(empresa_id: "str | None") -> "Path | None":
    """O modelo de preço ATIVO da empresa (o da versão ativa dela), ou None."""
    if not empresa_id:
        return None
    from model import modelos_empresa as me
    me.carregar_ativo(empresa_id)                 # traz do Storage a versão ativa, se mudou
    arq = me.pasta(empresa_id) / "price_model.pkl"
    return arq if arq.exists() else None


def prever(records: list[dict], empresa_id: "str | None" = None) -> np.ndarray | None:
    """
    Retorna array de taxas previstas (0.0–1.0) para cada devedor, com o modelo
    de preço da empresa. Retorna None se ela não tiver um (vale a premissa).
    """
    arq = _arquivo_ativo(empresa_id)
    if arq is None:
        return None
    try:
        meta    = joblib.load(arq)
        X       = _features(records)
        for col in meta["feature_cols"]:
            if col not in X.columns:
                X[col] = 0.0
        X       = X[meta["feature_cols"]]
        X_scaled = meta["scaler"].transform(X)
        return np.clip(meta["regressor"].predict(X_scaled), 0.0, 1.0)
    except Exception as e:
        print(f"[PriceModel] Erro ao prever: {type(e).__name__}")
        return None


def stats(empresa_id: "str | None" = None) -> dict | None:
    """Metadados do modelo de preço ativo da empresa."""
    arq = _arquivo_ativo(empresa_id)
    if arq is None:
        return None
    try:
        meta = joblib.load(arq)
        return {
            "disponivel":   True,
            "n_amostras":   meta.get("n_amostras"),
            "n_pagamentos": meta.get("n_pagamentos"),
            "r2_medio":     meta.get("r2_medio"),
            "mae_medio":    meta.get("mae_medio"),
        }
    except Exception:
        return None
