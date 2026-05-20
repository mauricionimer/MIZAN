"""
Pipeline de retreinamento do modelo Mizan com dados reais de feedback.

Fluxo:
  1. Busca feedbacks confirmados + features das predicoes no Supabase
  2. Verifica se há dados reais suficientes (>= min_feedbacks)
  3. Treina KMeans + HistGradientBoostingClassifier com alvo real (pagou)
  4. Avalia com cross-validation estratificada (acurácia + AUC-ROC)
  5. Salva versão numerada; promove se melhor que o modelo ativo

Uso:
  python -m model.retrain
  python -m model.retrain --min-feedbacks 10 --auto-promover
  python -m model.retrain --dry-run
  python -m model.retrain --promover v2_20260519_143022
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import RobustScaler

_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
from db import get_db

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR     = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent
VERSIONS_FILE = MODEL_DIR / "versions.json"

MODEL_VERSION          = 2
MIN_FEEDBACKS_DEFAULT  = 30
_BATCH                 = 1000

FEATURES_CATEGORICAS = ["produto", "status", "uf"]
FEATURES_NUMERICAS   = [
    "valor_divida", "renda_estimada", "dias_em_atraso",
    "comprometimento_renda", "log_valor_divida", "log_renda", "valor_por_dia",
]

_SCORE_PRODUTO = {"consignado": 100, "veiculo": 70, "pessoal": 40, "cartao": 20}


# ---------------------------------------------------------------------------
# Busca de dados no Supabase
# ---------------------------------------------------------------------------

def _buscar_feedbacks(db) -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            db.table("feedbacks")
            .select("predicao_id, pagou, valor_recuperado")
            .not_.is_("predicao_id", "null")
            .range(offset, offset + _BATCH - 1)
            .execute()
        )
        rows.extend(res.data)
        if len(res.data) < _BATCH:
            break
        offset += _BATCH
    return rows


def _buscar_predicoes(db, ids: list[str]) -> dict[str, dict]:
    pred_map: dict[str, dict] = {}
    for i in range(0, len(ids), 500):
        res = (
            db.table("predicoes")
            .select("id, produto, uf, valor_divida, dias_em_atraso, renda_estimada, status")
            .in_("id", ids[i: i + 500])
            .execute()
        )
        for p in res.data:
            pred_map[p["id"]] = p
    return pred_map


def _montar_dataset(feedbacks: list[dict], pred_map: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for fb in feedbacks:
        pred = pred_map.get(fb["predicao_id"])
        if not pred:
            continue
        rows.append({
            "produto":        pred.get("produto") or "pessoal",
            "status":         pred.get("status") or "ativo",
            "uf":             pred.get("uf") or "SP",
            "valor_divida":   float(pred.get("valor_divida") or 0),
            "renda_estimada": float(pred.get("renda_estimada") or 0),
            "dias_em_atraso": int(pred.get("dias_em_atraso") or 0),
            "pagou":          int(bool(fb["pagou"])),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pré-processamento
# ---------------------------------------------------------------------------

def _preprocessar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(1.0).clip(0, 10)
    df["log_valor_divida"] = np.log1p(df["valor_divida"].clip(0))
    df["log_renda"]        = np.log1p(df["renda_estimada"].clip(0))
    df["valor_por_dia"]    = df["valor_divida"] / (df["dias_em_atraso"] + 1)

    df_enc   = pd.get_dummies(df[FEATURES_CATEGORICAS], drop_first=False)
    cat_cols = df_enc.columns.tolist()
    X        = pd.concat([df[FEATURES_NUMERICAS], df_enc], axis=1)
    return X, cat_cols


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _escolher_k(X_scaled: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    k_max = min(k_max, len(X_scaled) - 1)
    if k_max < k_min:
        return k_min
    ks       = list(range(k_min, k_max + 1))
    inercias = [KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled).inertia_ for k in ks]
    arr      = np.array(inercias)
    deltas   = arr[:-1] - arr[1:]
    total    = arr[0] - arr[-1]
    if total == 0 or len(deltas) < 2:
        return k_min
    accel = deltas[:-1] - deltas[1:]
    return ks[int(np.argmax(accel)) + 1]


def _gerar_labels_clusters(df_cl: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    def _score_prod(val: str) -> float:
        val = str(val).lower()
        for chave, pts in _SCORE_PRODUTO.items():
            if chave in val:
                return pts
        return 30

    df_cl = df_cl.copy()
    df_cl["_sp"] = df_cl["produto"].map(_score_prod)
    resumo = df_cl.groupby("cluster").agg(
        dias_medio=("dias_em_atraso",       "mean"),
        comp_medio=("comprometimento_renda", "mean"),
        sp_medio  =("_sp",                   "mean"),
    )
    labels: dict[int, str] = {}
    for cid, row in resumo.iterrows():
        partes = [
            "Recente"       if row["dias_medio"] < 60  else
            "Intermediário" if row["dias_medio"] < 180 else "Crônico",
            "Baixo Comprometimento"    if row["comp_medio"] < 0.3 else
            "Comprometimento Moderado" if row["comp_medio"] < 0.7 else "Alto Comprometimento",
            "Consignado" if row["sp_medio"] >= 80 else
            "Veículo"    if row["sp_medio"] >= 60 else
            "Pessoal"    if row["sp_medio"] >= 35 else "Cartão",
        ]
        labels[int(cid)] = " · ".join(partes)
    return labels


# ---------------------------------------------------------------------------
# Avaliação
# ---------------------------------------------------------------------------

def _avaliar(clf, X_rf: np.ndarray, y: np.ndarray) -> dict:
    n_splits = max(2, min(5, int(y.sum()), int(len(y) - y.sum())))
    cv  = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    acc = cross_val_score(clf, X_rf, y, cv=cv, scoring="accuracy")
    metricas: dict = {
        "cv_acuracia_media": round(float(acc.mean()), 4),
        "cv_acuracia_std":   round(float(acc.std()), 4),
        "n_splits":          n_splits,
    }
    if len(np.unique(y)) == 2:
        auc = cross_val_score(clf, X_rf, y, cv=cv, scoring="roc_auc")
        metricas["cv_auc_media"] = round(float(auc.mean()), 4)
        metricas["cv_auc_std"]   = round(float(auc.std()), 4)
    return metricas


# ---------------------------------------------------------------------------
# Versionamento
# ---------------------------------------------------------------------------

def _carregar_versoes() -> dict:
    if VERSIONS_FILE.exists():
        with open(VERSIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "versoes": [{
            "versao": "v1_inicial", "criado_em": None, "n_amostras": None,
            "tipo_alvo": "simulado", "metricas": None,
            "promovido": True, "promovido_em": None,
        }],
        "versao_ativa": "v1_inicial",
    }


def _salvar_versoes(versoes: dict) -> None:
    with open(VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(versoes, f, indent=2, ensure_ascii=False)


def _proxima_versao(versoes: dict) -> str:
    n  = len(versoes["versoes"]) + 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"v{n}_{ts}"


def _salvar_artefatos(versao: str, clf, kmeans, meta: dict) -> None:
    joblib.dump(clf,    MODEL_DIR / f"mizan_model_{versao}.pkl")
    joblib.dump(kmeans, MODEL_DIR / f"kmeans_{versao}.pkl")
    joblib.dump(meta,   MODEL_DIR / f"scaler_{versao}.pkl")


def _promover(versao: str, clf, kmeans, meta: dict) -> None:
    joblib.dump(clf,    MODEL_DIR / "mizan_model.pkl")
    joblib.dump(kmeans, MODEL_DIR / "kmeans.pkl")
    joblib.dump(meta,   MODEL_DIR / "scaler.pkl")
    try:
        import model.score as _score_mod
        _score_mod._cache.clear()
    except Exception:
        pass


def promover_versao(versao: str) -> None:
    paths = {
        "clf":    MODEL_DIR / f"mizan_model_{versao}.pkl",
        "kmeans": MODEL_DIR / f"kmeans_{versao}.pkl",
        "scaler": MODEL_DIR / f"scaler_{versao}.pkl",
    }
    ausentes = [str(p) for p in paths.values() if not p.exists()]
    if ausentes:
        raise FileNotFoundError(f"Artefatos não encontrados: {ausentes}")
    clf    = joblib.load(paths["clf"])
    kmeans = joblib.load(paths["kmeans"])
    meta   = joblib.load(paths["scaler"])
    _promover(versao, clf, kmeans, meta)
    versoes = _carregar_versoes()
    for v in versoes["versoes"]:
        if v["versao"] == versao:
            v["promovido"]    = True
            v["promovido_em"] = datetime.now(timezone.utc).isoformat()
    versoes["versao_ativa"] = versao
    _salvar_versoes(versoes)
    print(f"Modelo {versao} promovido com sucesso.")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def retreinar(
    min_feedbacks: int = MIN_FEEDBACKS_DEFAULT,
    auto_promover: bool = False,
    dry_run: bool = False,
) -> dict:
    print("=" * 60)
    print("MIZAN — Pipeline de Retreinamento v2")
    print("=" * 60)

    print("\n[1/6] Conectando ao Supabase e buscando feedbacks...")
    db         = get_db()
    feedbacks  = _buscar_feedbacks(db)
    n_feedbacks = len(feedbacks)
    print(f"      {n_feedbacks} feedbacks com predicao_id encontrados")

    if n_feedbacks < min_feedbacks:
        msg = (
            f"Dados insuficientes: {n_feedbacks} feedbacks (mínimo: {min_feedbacks}). "
            f"Use --min-feedbacks {max(1, n_feedbacks)} para forçar."
        )
        print(f"\n[ENCERRADO] {msg}")
        return {"ok": False, "motivo": msg, "n_feedbacks": n_feedbacks}

    print("\n[2/6] Buscando features das predicoes...")
    pred_ids = [f["predicao_id"] for f in feedbacks]
    pred_map = _buscar_predicoes(db, pred_ids)
    print(f"      {len(pred_map)} predicoes carregadas")

    df       = _montar_dataset(feedbacks, pred_map)
    n_amostras = len(df)
    n_pagou  = int(df["pagou"].sum())
    print(f"      Dataset: {n_amostras} amostras | pagaram={n_pagou} | não pagaram={n_amostras - n_pagou}")

    if len(df["pagou"].unique()) < 2:
        msg = "Alvo uniforme. Impossível treinar classificador binário."
        print(f"\n[ENCERRADO] {msg}")
        return {"ok": False, "motivo": msg, "n_feedbacks": n_feedbacks}

    print("\n[3/6] Pré-processando features (v2)...")
    X, cat_cols = _preprocessar(df)
    df["comprometimento_renda"] = X["comprometimento_renda"]
    scaler   = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    print("\n[4/6] Selecionando número de clusters...")
    k_ideal  = _escolher_k(X_scaled)
    print(f"      k={k_ideal}")
    kmeans   = KMeans(n_clusters=k_ideal, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df["cluster"]  = clusters
    cluster_labels = _gerar_labels_clusters(df, k_ideal)
    for cid, label in sorted(cluster_labels.items()):
        print(f"        [{cid}] {label} (n={(clusters == cid).sum()})")

    print("\n[5/6] Treinando HistGradientBoostingClassifier com alvo real (pagou)...")
    y     = df["pagou"].values
    X_clf = np.column_stack([X_scaled, clusters])
    min_leaf = max(5, n_amostras // 30)
    clf = HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, learning_rate=0.05,
        min_samples_leaf=min_leaf, l2_regularization=1.0, random_state=42,
    )
    clf.fit(X_clf, y)

    print("\n[5.5/6] Avaliando com cross-validation...")
    metricas = _avaliar(clf, X_clf, y)
    print(f"      Acurácia CV: {metricas['cv_acuracia_media']:.2%} ± {metricas['cv_acuracia_std']:.2%}")
    if "cv_auc_media" in metricas:
        print(f"      AUC-ROC CV: {metricas['cv_auc_media']:.3f} ± {metricas['cv_auc_std']:.3f}")

    if dry_run:
        print("\n[DRY RUN] Avaliação concluída. Nenhum arquivo salvo.")
        return {"ok": True, "dry_run": True, "metricas": metricas, "n_amostras": n_amostras}

    print("\n[6/6] Salvando modelo versionado...")
    versoes = _carregar_versoes()
    versao  = _proxima_versao(versoes)

    feature_names = list(X.columns) + ["cluster"]
    meta = {
        "scaler":         scaler,
        "cat_cols":       cat_cols,
        "feature_names":  feature_names,
        "cluster_labels": cluster_labels,
        "k":              k_ideal,
        "model_version":  MODEL_VERSION,
        "versao":         versao,
    }
    _salvar_artefatos(versao, clf, kmeans, meta)

    versao_ativa    = versoes.get("versao_ativa", "v1_inicial")
    acuracia_nova   = metricas["cv_acuracia_media"]
    acuracia_ativa  = 0.0
    for v in versoes["versoes"]:
        if v["versao"] == versao_ativa and v.get("metricas"):
            acuracia_ativa = v["metricas"].get("cv_acuracia_media", 0.0)
            break

    melhorou = acuracia_nova > acuracia_ativa
    print(f"\n      Ativo:  {versao_ativa} (acurácia={acuracia_ativa:.2%})")
    print(f"      Novo:   {versao} (acurácia={acuracia_nova:.2%})")
    print(f"      {'↑ Melhora detectada' if melhorou else '= Sem melhora'}")

    entrada: dict = {
        "versao":            versao,
        "criado_em":         datetime.now(timezone.utc).isoformat(),
        "n_amostras":        n_amostras,
        "n_feedbacks_reais": n_feedbacks,
        "tipo_alvo":         "real",
        "metricas":          metricas,
        "promovido":         False,
        "promovido_em":      None,
    }

    if auto_promover and melhorou:
        _promover(versao, clf, kmeans, meta)
        entrada["promovido"]    = True
        entrada["promovido_em"] = datetime.now(timezone.utc).isoformat()
        versoes["versao_ativa"] = versao
        print(f"      ✓ Modelo {versao} promovido como ativo.")
    elif auto_promover and not melhorou:
        print("      Auto-promoção cancelada: novo modelo não supera o ativo.")
    else:
        print(f"      Para promover: POST /admin/retreinar/promover {{\"versao\": \"{versao}\"}}")

    versoes["versoes"].append(entrada)
    _salvar_versoes(versoes)
    print(f"\nConcluído. Arquivos salvos em: {MODEL_DIR}")
    print("=" * 60)

    return {
        "ok":         True,
        "versao":     versao,
        "n_amostras": n_amostras,
        "metricas":   metricas,
        "promovido":  entrada["promovido"],
        "melhorou":   melhorou,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retreina o modelo Mizan com dados reais.")
    parser.add_argument("--min-feedbacks", type=int, default=MIN_FEEDBACKS_DEFAULT)
    parser.add_argument("--auto-promover", action="store_true")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--promover",      metavar="VERSAO")
    args = parser.parse_args()

    if args.promover:
        promover_versao(args.promover)
        sys.exit(0)

    resultado = retreinar(
        min_feedbacks=args.min_feedbacks,
        auto_promover=args.auto_promover,
        dry_run=args.dry_run,
    )
    sys.exit(0 if resultado.get("ok") else 1)
