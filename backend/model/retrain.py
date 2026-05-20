"""
Pipeline de retreinamento do modelo Mizan com dados reais de feedback.

Fluxo:
  1. Busca feedbacks confirmados + features das predicoes no Supabase
  2. Verifica se há dados reais suficientes (>= min_feedbacks)
  3. Treina KMeans + RandomForest com alvo real (pagou)
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
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
from db import get_db

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR     = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent
VERSIONS_FILE = MODEL_DIR / "versions.json"

MIN_FEEDBACKS_DEFAULT = 30
_BATCH = 1000  # paginação Supabase

FEATURES_CATEGORICAS = ["produto", "status", "uf"]
FEATURES_NUMERICAS = ["valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"]

_SCORE_PRODUTO = {"consignado": 100, "veiculo": 70, "pessoal": 40, "cartao": 20}


# ---------------------------------------------------------------------------
# Busca de dados no Supabase
# ---------------------------------------------------------------------------

def _buscar_feedbacks(db) -> list[dict]:
    """Retorna todos os feedbacks que possuem predicao_id (paginado)."""
    rows: list[dict] = []
    offset = 0
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
    """Busca predicoes pelos ids (em lotes de 500)."""
    pred_map: dict[str, dict] = {}
    for i in range(0, len(ids), 500):
        lote = ids[i: i + 500]
        res = (
            db.table("predicoes")
            .select("id, produto, uf, valor_divida, dias_em_atraso, renda_estimada, status")
            .in_("id", lote)
            .execute()
        )
        for p in res.data:
            pred_map[p["id"]] = p
    return pred_map


def _montar_dataset(feedbacks: list[dict], pred_map: dict[str, dict]) -> pd.DataFrame:
    """
    Junta feedbacks + features das predicoes.
    Campos ausentes (renda_estimada, status) recebem defaults conservadores:
      renda_estimada = 0  → comprometimento_renda = 1.0 (máximo conservador)
      status = "ativo"    → categoria mais comum
    """
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
# Pré-processamento (espelha train.py)
# ---------------------------------------------------------------------------

def _preprocessar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df.copy()
    # renda_estimada=0 → comprometimento conservador de 1.0 (dado não disponível)
    df["comprometimento_renda"] = (
        df["valor_divida"] / df["renda_estimada"].replace(0, np.nan)
    ).fillna(1.0).clip(0, 3)

    df_enc = pd.get_dummies(df[FEATURES_CATEGORICAS], drop_first=False)
    cat_cols = df_enc.columns.tolist()
    X = pd.concat([df[FEATURES_NUMERICAS], df_enc], axis=1)
    return X, cat_cols


# ---------------------------------------------------------------------------
# Clustering (espelha train.py)
# ---------------------------------------------------------------------------

def _escolher_k(X_scaled: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    k_max = min(k_max, len(X_scaled) - 1)
    if k_max < k_min:
        return k_min
    ks = list(range(k_min, k_max + 1))
    inercias = [KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled).inertia_ for k in ks]
    arr = np.array(inercias)
    deltas = arr[:-1] - arr[1:]
    total = arr[0] - arr[-1]
    if total == 0 or len(deltas) < 2:
        return k_min
    accel = deltas[:-1] - deltas[1:]
    return ks[int(np.argmax(accel)) + 1]


def _gerar_labels_clusters(df_com_cluster: pd.DataFrame, n_clusters: int) -> dict[int, str]:
    def _score_prod(val: str) -> float:
        val = str(val).lower()
        for chave, pts in _SCORE_PRODUTO.items():
            if chave in val:
                return pts
        return 30

    df = df_com_cluster.copy()
    df["_score_prod"] = df["produto"].map(_score_prod)
    resumo = df.groupby("cluster").agg(
        dias_medio=("dias_em_atraso", "mean"),
        comp_medio=("comprometimento_renda", "mean"),
        score_prod_medio=("_score_prod", "mean"),
    )
    labels: dict[int, str] = {}
    for cid, row in resumo.iterrows():
        partes = [
            "Recente" if row["dias_medio"] < 60 else "Intermediário" if row["dias_medio"] < 180 else "Crônico",
            "Baixo Comprometimento" if row["comp_medio"] < 0.3 else "Comprometimento Moderado" if row["comp_medio"] < 0.7 else "Alto Comprometimento",
            "Consignado" if row["score_prod_medio"] >= 80 else "Veículo" if row["score_prod_medio"] >= 60 else "Pessoal" if row["score_prod_medio"] >= 35 else "Cartão",
        ]
        labels[int(cid)] = " · ".join(partes)
    return labels


# ---------------------------------------------------------------------------
# Avaliação com cross-validation
# ---------------------------------------------------------------------------

def _avaliar(clf, X_rf: np.ndarray, y: np.ndarray) -> dict:
    n_splits = max(2, min(5, int(y.sum()), int(len(y) - y.sum())))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

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
            "versao": "v1_inicial",
            "criado_em": None,
            "n_amostras": None,
            "tipo_alvo": "simulado",
            "metricas": None,
            "promovido": True,
            "promovido_em": None,
        }],
        "versao_ativa": "v1_inicial",
    }


def _salvar_versoes(versoes: dict) -> None:
    with open(VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(versoes, f, indent=2, ensure_ascii=False)


def _proxima_versao(versoes: dict) -> str:
    n = len(versoes["versoes"]) + 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"v{n}_{ts}"


def _salvar_artefatos(versao: str, clf, kmeans, meta: dict) -> None:
    joblib.dump(clf,    MODEL_DIR / f"mizan_model_{versao}.pkl")
    joblib.dump(kmeans, MODEL_DIR / f"kmeans_{versao}.pkl")
    joblib.dump(meta,   MODEL_DIR / f"scaler_{versao}.pkl")


def _promover(versao: str, clf, kmeans, meta: dict) -> None:
    """Copia artefatos versionados para os arquivos ativos e invalida o cache."""
    joblib.dump(clf,    MODEL_DIR / "mizan_model.pkl")
    joblib.dump(kmeans, MODEL_DIR / "kmeans.pkl")
    joblib.dump(meta,   MODEL_DIR / "scaler.pkl")
    # Invalida o cache em memória do score.py quando rodando no mesmo processo
    try:
        import model.score as _score_mod
        _score_mod._cache.clear()
    except Exception:
        pass


def promover_versao(versao: str) -> None:
    """Promove uma versão específica como modelo ativo (uso manual ou via endpoint)."""
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
            v["promovido"] = True
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
    print("MIZAN — Pipeline de Retreinamento")
    print("=" * 60)

    # 1. Busca dados
    print("\n[1/6] Conectando ao Supabase e buscando feedbacks...")
    db = get_db()
    feedbacks = _buscar_feedbacks(db)
    n_feedbacks = len(feedbacks)
    print(f"      {n_feedbacks} feedbacks com predicao_id encontrados")

    if n_feedbacks < min_feedbacks:
        msg = (
            f"Dados insuficientes: {n_feedbacks} feedbacks (mínimo: {min_feedbacks}). "
            f"Registre mais resultados via POST /feedback ou use "
            f"--min-feedbacks {max(1, n_feedbacks)} para forçar com menos dados."
        )
        print(f"\n[ENCERRADO] {msg}")
        return {"ok": False, "motivo": msg, "n_feedbacks": n_feedbacks}

    # 2. Monta dataset
    print("\n[2/6] Buscando features das predicoes...")
    pred_ids = [f["predicao_id"] for f in feedbacks]
    pred_map = _buscar_predicoes(db, pred_ids)
    print(f"      {len(pred_map)} predicoes carregadas")

    df = _montar_dataset(feedbacks, pred_map)
    n_amostras = len(df)
    n_pagou = int(df["pagou"].sum())
    print(f"      Dataset: {n_amostras} amostras | pagaram={n_pagou} | não pagaram={n_amostras - n_pagou}")

    if len(df["pagou"].unique()) < 2:
        msg = "Alvo uniforme (todos pagaram ou nenhum pagou). Impossível treinar classificador binário."
        print(f"\n[ENCERRADO] {msg}")
        return {"ok": False, "motivo": msg, "n_feedbacks": n_feedbacks}

    # 3. Pré-processamento
    print("\n[3/6] Pré-processando features...")
    X, cat_cols = _preprocessar(df)
    df["comprometimento_renda"] = X["comprometimento_renda"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 4. Clustering
    print("\n[4/6] Selecionando número de clusters...")
    k_ideal = _escolher_k(X_scaled)
    print(f"      k={k_ideal}")
    kmeans = KMeans(n_clusters=k_ideal, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    df["cluster"] = clusters
    cluster_labels = _gerar_labels_clusters(df, k_ideal)
    for cid, label in sorted(cluster_labels.items()):
        print(f"        [{cid}] {label} (n={(clusters == cid).sum()})")

    # 5. Treina RandomForest com alvo real
    print("\n[5/6] Treinando RandomForestClassifier com alvo real (pagou)...")
    y = df["pagou"].values
    X_rf = np.column_stack([X_scaled, clusters])
    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_rf, y)

    feature_names = list(X.columns) + ["cluster"]
    clf.feature_names_in_ = np.array(feature_names)

    print("\n[5.5/6] Avaliando com cross-validation...")
    metricas = _avaliar(clf, X_rf, y)
    print(f"      Acurácia CV: {metricas['cv_acuracia_media']:.2%} ± {metricas['cv_acuracia_std']:.2%}")
    if "cv_auc_media" in metricas:
        print(f"      AUC-ROC CV: {metricas['cv_auc_media']:.3f} ± {metricas['cv_auc_std']:.3f}")

    if dry_run:
        print("\n[DRY RUN] Avaliação concluída. Nenhum arquivo salvo.")
        return {"ok": True, "dry_run": True, "metricas": metricas, "n_amostras": n_amostras}

    # 6. Versionamento e promoção
    print("\n[6/6] Salvando modelo versionado...")
    versoes = _carregar_versoes()
    versao = _proxima_versao(versoes)

    meta = {
        "scaler":         scaler,
        "cat_cols":       cat_cols,
        "feature_names":  feature_names,
        "cluster_labels": cluster_labels,
        "k":              k_ideal,
        "versao":         versao,
    }
    _salvar_artefatos(versao, clf, kmeans, meta)

    # Compara com versão ativa
    versao_ativa = versoes.get("versao_ativa", "v1_inicial")
    acuracia_nova = metricas["cv_acuracia_media"]
    acuracia_ativa = 0.0
    for v in versoes["versoes"]:
        if v["versao"] == versao_ativa and v.get("metricas"):
            acuracia_ativa = v["metricas"].get("cv_acuracia_media", 0.0)
            break

    melhorou = acuracia_nova > acuracia_ativa
    print(f"\n      Modelo ativo:  {versao_ativa} (acurácia={acuracia_ativa:.2%})")
    print(f"      Novo modelo:   {versao} (acurácia={acuracia_nova:.2%})")
    print(f"      {'↑ Melhora detectada' if melhorou else '= Sem melhora (novo modelo salvo mas não promovido)'}")

    entrada: dict = {
        "versao":             versao,
        "criado_em":          datetime.now(timezone.utc).isoformat(),
        "n_amostras":         n_amostras,
        "n_feedbacks_reais":  n_feedbacks,
        "tipo_alvo":          "real",
        "metricas":           metricas,
        "promovido":          False,
        "promovido_em":       None,
    }

    if auto_promover and melhorou:
        _promover(versao, clf, kmeans, meta)
        entrada["promovido"] = True
        entrada["promovido_em"] = datetime.now(timezone.utc).isoformat()
        versoes["versao_ativa"] = versao
        print(f"      ✓ Modelo {versao} promovido como ativo.")
    elif auto_promover and not melhorou:
        print("      Auto-promoção cancelada: novo modelo não supera o ativo.")
    else:
        print(f"      Para promover manualmente:")
        print(f"        python -m model.retrain --promover {versao}")
        print(f"        ou POST /admin/retreinar/promover com {{\"versao\": \"{versao}\"}}")

    versoes["versoes"].append(entrada)
    _salvar_versoes(versoes)

    print(f"\nConcluído. Artefatos salvos em: {MODEL_DIR}")
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
    parser = argparse.ArgumentParser(description="Retreina o modelo Mizan com dados reais de feedback.")
    parser.add_argument("--min-feedbacks", type=int, default=MIN_FEEDBACKS_DEFAULT,
                        help=f"Mínimo de feedbacks necessários (padrão: {MIN_FEEDBACKS_DEFAULT})")
    parser.add_argument("--auto-promover", action="store_true",
                        help="Promove automaticamente se acurácia melhorar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Avalia sem salvar nenhum arquivo")
    parser.add_argument("--promover", metavar="VERSAO",
                        help="Promove uma versão específica como modelo ativo")
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
