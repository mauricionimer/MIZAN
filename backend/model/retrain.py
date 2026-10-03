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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, cross_val_score
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
_ITENS_IN              = 100   # tamanho de lista em in_(); ver nota em _buscar_predicoes

_SCORE_PRODUTO = {"consignado": 100, "veiculo": 70, "pessoal": 40, "cartao": 20}


# ---------------------------------------------------------------------------
# Busca de dados no Supabase
# ---------------------------------------------------------------------------

def _buscar_feedbacks(db) -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            db.table("feedbacks")
            .select("predicao_id, pagou, valor_recuperado, created_at")
            .not_.is_("predicao_id", "null")
            .order("created_at", desc=True)  # mais recente primeiro para dedup
            .range(offset, offset + _BATCH - 1)
            .execute()
        )
        rows.extend(res.data)
        if len(res.data) < _BATCH:
            break
        offset += _BATCH

    # Deduplicar por predicao_id: evita que a mesma análise entre múltiplas vezes no treino.
    # Quando há conflito, feedback positivo (pagou=True) tem prioridade sobre negativo.
    seen: dict[str, dict] = {}
    for fb in rows:
        pid = fb["predicao_id"]
        if pid not in seen:
            seen[pid] = fb
        elif fb.get("pagou") and not seen[pid].get("pagou"):
            seen[pid] = fb
    return list(seen.values())


def _buscar_predicoes(db, ids: list[str]) -> dict[str, dict]:
    pred_map: dict[str, dict] = {}
    # 100 ids por consulta: a URL do Supabase recusou 800 UUIDs numa lista
    # (medido), e 500 nunca foi medido.
    for i in range(0, len(ids), _ITENS_IN):
        res = (
            db.table("predicoes")
            .select("id, cpf, produto, uf, valor_divida, dias_em_atraso, renda_estimada, status, created_at")
            .in_("id", ids[i: i + _ITENS_IN])
            .execute()
        )
        for p in res.data:
            pred_map[p["id"]] = p
    return pred_map


def _buscar_historico_contatos(db, cpfs: list[str]) -> dict[str, dict]:
    """Retorna histórico agregado de contatos por CPF para enriquecer o dataset de treino."""
    hist: dict[str, dict] = {}
    for i in range(0, len(cpfs), 500):
        try:
            res = db.table("contatos").select("cpf, resultado, created_at").in_("cpf", cpfs[i:i+500]).execute()
            for ct in (res.data or []):
                cpf = str(ct["cpf"])
                if cpf not in hist:
                    hist[cpf] = {"n": 0, "positivo": 0}
                hist[cpf]["n"] += 1
                if ct.get("resultado", "").lower() in ("pagamento_confirmado", "acordo_fechado"):
                    hist[cpf]["positivo"] += 1
        except Exception:
            pass
    return hist


def _montar_dataset(feedbacks: list[dict], pred_map: dict[str, dict], hist_contatos: dict | None = None) -> pd.DataFrame:
    rows = []
    for fb in feedbacks:
        pred = pred_map.get(fb["predicao_id"])
        if not pred:
            continue
        cpf = str(pred.get("cpf") or "")
        row = {
            "cpf":            cpf,
            "produto":        pred.get("produto") or "pessoal",
            "status":         pred.get("status") or "ativo",
            "uf":             pred.get("uf") or "SP",
            "valor_divida":   float(pred.get("valor_divida") or 0),
            "renda_estimada": float(pred.get("renda_estimada") or 0),
            "dias_em_atraso": int(pred.get("dias_em_atraso") or 0),
            "pagou":          int(bool(fb["pagou"])),
            "_created_at":    pred.get("created_at") or "",
        }
        if hist_contatos and cpf in hist_contatos:
            h = hist_contatos[cpf]
            row["hist_n_contatos"] = h["n"]
            row["hist_positivo"]   = int(h["positivo"] > 0)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pré-processamento
# ---------------------------------------------------------------------------

def _preprocessar(df: pd.DataFrame):
    """Reutiliza a lógica de train.py: auto-detect + derivadas + imputation."""
    from model.train import _normalizar_colunas, _adicionar_derivadas, _detectar_features
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
    has_produto = "produto" in df_cl.columns
    has_comp    = "comprometimento_renda" in df_cl.columns
    has_dias    = "dias_em_atraso" in df_cl.columns

    if has_produto:
        df_cl["_sp"] = df_cl["produto"].map(_score_prod)

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


# ---------------------------------------------------------------------------
# Avaliação
# ---------------------------------------------------------------------------

def _avaliar(clf, X_rf: np.ndarray, y: np.ndarray, temporal: bool = False) -> dict:
    n_splits = max(2, min(5, int(y.sum()), int(len(y) - y.sum())))
    if temporal and len(y) >= 30:
        # Validação temporal: treina no passado, valida no futuro (sem vazamento de dados)
        cv = TimeSeriesSplit(n_splits=n_splits)
        print(f"      Usando TimeSeriesSplit (validação temporal, k={n_splits})")
    else:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    acc = cross_val_score(clf, X_rf, y, cv=cv, scoring="accuracy")
    metricas: dict = {
        "cv_acuracia_media": round(float(acc.mean()), 4),
        "cv_acuracia_std":   round(float(acc.std()), 4),
        "n_splits":          n_splits,
        "validacao_temporal": temporal and len(y) >= 30,
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


class VersaoInsuficiente(Exception):
    """Versão existe, mas não tem amostras suficientes para virar modelo ativo."""


def _amostras_da_versao(versao: str) -> int | None:
    """Nº de amostras reais com que a versão foi treinada, ou None se desconhecido."""
    for v in _carregar_versoes().get("versoes", []):
        if v.get("versao") == versao:
            n = v.get("n_feedbacks_reais")
            if n is None:
                n = v.get("n_amostras")
            return int(n) if n is not None else None
    return None


def promover_versao(versao: str, forcar: bool = False) -> None:
    """Torna `versao` o modelo ativo.

    O retreino automático já exige MIN_FEEDBACKS_DEFAULT amostras, mas esta
    função — usada pelo botão "Promover" da tela de Aprendizado — não exigia
    nada além dos arquivos existirem. Dava para promover um modelo treinado em
    dez linhas e ele virava o que decide a fila de cobrança em produção.
    Agora vale o mesmo mínimo, e furar exige `forcar=True` de forma explícita.
    """
    n = _amostras_da_versao(versao)
    if not forcar and n is not None and n < MIN_FEEDBACKS_DEFAULT:
        raise VersaoInsuficiente(
            f"A versão {versao} foi treinada com {n} amostra(s); o mínimo para "
            f"virar modelo ativo é {MIN_FEEDBACKS_DEFAULT}. Abaixo disso as "
            f"métricas não têm significado estatístico."
        )

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
    try:
        from storage_ml import upload_modelos
        upload_modelos()
    except Exception as _ue:
        print(f"[Storage] Aviso: upload pós-promoção falhou: {_ue}")


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

    print("\n[2/6] Buscando features das predicoes e histórico de contatos...")
    pred_ids = [f["predicao_id"] for f in feedbacks]
    pred_map = _buscar_predicoes(db, pred_ids)
    print(f"      {len(pred_map)} predicoes carregadas")

    cpfs_unicos = list({str(p.get("cpf", "")) for p in pred_map.values() if p.get("cpf")})
    hist_contatos = _buscar_historico_contatos(db, cpfs_unicos) if cpfs_unicos else {}
    print(f"      {len(hist_contatos)} CPFs com histórico de contatos")

    df       = _montar_dataset(feedbacks, pred_map, hist_contatos)
    n_amostras = len(df)
    n_pagou  = int(df["pagou"].sum())
    print(f"      Dataset: {n_amostras} amostras | pagaram={n_pagou} | não pagaram={n_amostras - n_pagou}")

    # Verificação de balanceamento extremo
    taxa_pos = n_pagou / n_amostras if n_amostras > 0 else 0.0
    if taxa_pos < 0.05:
        print(f"      AVISO: apenas {taxa_pos:.1%} positivos — dataset muito desbalanceado.")
    elif taxa_pos > 0.95:
        print(f"      AVISO: {taxa_pos:.1%} positivos — verifique se feedbacks negativos estão sendo registrados.")

    # Ordena por data para validação temporal correta (evita vazamento futuro→passado)
    temporal = False
    if "_created_at" in df.columns and df["_created_at"].ne("").any():
        df["_created_at"] = pd.to_datetime(df["_created_at"], errors="coerce", utc=True)
        df = df.sort_values("_created_at").reset_index(drop=True)
        temporal = True
        print("      Dataset ordenado por data — validação temporal ativa")
    df = df.drop(columns=["_created_at", "cpf"], errors="ignore")

    if len(df["pagou"].unique()) < 2:
        msg = "Alvo uniforme. Impossível treinar classificador binário."
        print(f"\n[ENCERRADO] {msg}")
        return {"ok": False, "motivo": msg, "n_feedbacks": n_feedbacks}

    print("\n[3/6] Pré-processando features (auto-detect)...")
    X, features_numericas, cat_cols, medians, modes = _preprocessar(df)
    if "comprometimento_renda" in X.columns:
        df["comprometimento_renda"] = X["comprometimento_renda"]
    print(f"      {len(features_numericas)} numéricas + {len(cat_cols)} categóricas (encoded)")
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

    print("\n[5/6] Treinando HistGradientBoostingClassifier (class_weight=balanced, alvo real)...")
    y     = df["pagou"].values
    X_clf = np.column_stack([X_scaled, clusters])
    # min_leaf conservador: evita overfitting em datasets pequenos
    min_leaf = max(5, min(20, n_amostras // 50))
    params_clf = dict(

        max_iter=200, max_depth=4, learning_rate=0.05,

        min_samples_leaf=min_leaf, l2_regularization=1.0,

        class_weight="balanced", random_state=42,

    )

    clf = HistGradientBoostingClassifier(**params_clf)
    clf.fit(X_clf, y)

    print("\n[5.5/6] Avaliando com cross-validation + holdout real...")
    metricas = _avaliar(clf, X_clf, y, temporal=temporal)
    print(f"      Acurácia CV: {metricas['cv_acuracia_media']:.2%} ± {metricas['cv_acuracia_std']:.2%}")
    if "cv_auc_media" in metricas:
        print(f"      AUC-ROC CV: {metricas['cv_auc_media']:.3f} ± {metricas['cv_auc_std']:.3f}")

    # Holdout real (20% final do dataset, respeitando ordem temporal)
    holdout_acuracia = None
    if n_amostras >= 50:
        try:
            split = int(n_amostras * 0.8)
            X_ho, y_ho = X_clf[split:], y[split:]
            clf_ho = HistGradientBoostingClassifier(
                max_iter=200, max_depth=4, learning_rate=0.05,
                min_samples_leaf=min_leaf, l2_regularization=1.0,
                class_weight="balanced", random_state=42,
            )
            clf_ho.fit(X_clf[:split], y[:split])
            holdout_acuracia = round(float((clf_ho.predict(X_ho) == y_ho).mean()), 4)
            metricas["holdout_acuracia"] = holdout_acuracia
            print(f"      Holdout real (20%): {holdout_acuracia:.2%}")
        except Exception as _he:
            print(f"      Holdout ignorado: {_he}")

    if dry_run:
        print("\n[DRY RUN] Avaliação concluída. Nenhum arquivo salvo.")
        return {"ok": True, "dry_run": True, "metricas": metricas, "n_amostras": n_amostras}

    # Calibração de probabilidade (Platt scaling) quando há dados suficientes.
    #
    # Usa validação cruzada em vez de separar um holdout. A calibração é
    # monotônica — não muda ordenação —, então o custo de calibrar não está no
    # Platt, está em treinar o modelo base com menos dados. Medido na base
    # pública German Credit (validacao/validar_pipeline.py), guardar 20% para
    # calibrar custava 6,2 pontos de KS; com cv=5 o modelo aprende de tudo e
    # calibra por cross-fitting. Em base grande as duas empatam; em base
    # pequena, que é a situação de um cliente nos primeiros meses, o cv ganha.
    clf_to_save = clf
    if n_amostras >= 150 and len(np.unique(y)) == 2:
        try:
            n_folds = max(2, min(5, int(y.sum()), int(n_amostras - y.sum())))
            clf_to_save = CalibratedClassifierCV(
                HistGradientBoostingClassifier(**params_clf),
                method="sigmoid", cv=n_folds,
            )
            clf_to_save.fit(X_clf, y)
            print(f"      Calibração Platt aplicada (cv={n_folds}).")
        except Exception as _ce:
            print(f"      Calibração ignorada: {_ce}")
            clf_to_save = clf
    print("\n[6/6] Salvando modelo versionado...")
    versoes = _carregar_versoes()
    versao  = _proxima_versao(versoes)

    feature_names = list(X.columns) + ["cluster"]
    meta = {
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
        "versao":               versao,
    }
    _salvar_artefatos(versao, clf_to_save, kmeans, meta)

    versao_ativa   = versoes.get("versao_ativa", "v1_inicial")
    # Usa holdout real para comparação quando disponível; fallback para CV
    acuracia_nova  = metricas.get("holdout_acuracia") or metricas["cv_acuracia_media"]
    acuracia_ativa = 0.0
    for v in versoes["versoes"]:
        if v["versao"] == versao_ativa and v.get("metricas"):
            m = v["metricas"]
            acuracia_ativa = m.get("holdout_acuracia") or m.get("cv_acuracia_media", 0.0)
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
        _promover(versao, clf_to_save, kmeans, meta)
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

    if entrada["promovido"]:
        try:
            from storage_ml import upload_modelos
            upload_modelos()
        except Exception as _ue:
            print(f"[Storage] Aviso: upload pós-promoção falhou: {_ue}")

    # Treina price model de regressão com os mesmos dados (independente de promoção)
    print("\n[+] Treinando price model (regressão de taxa real de recuperação)...")
    price_result: dict = {}
    try:
        from model.price_model import treinar as _treinar_price
        price_result = _treinar_price(feedbacks, pred_map)
    except Exception as _pe:
        print(f"[PriceModel] Erro no treino: {_pe}")
        price_result = {"ok": False, "motivo": str(_pe)}

    print(f"\nConcluído. Arquivos salvos em: {MODEL_DIR}")
    print("=" * 60)

    return {
        "ok":          True,
        "versao":      versao,
        "n_amostras":  n_amostras,
        "metricas":    metricas,
        "promovido":   entrada["promovido"],
        "melhorou":    melhorou,
        "price_model": price_result,
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
