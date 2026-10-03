"""
Modelos por empresa.

Cada cliente pode ter o seu próprio modelo, treinado só com a carteira dele. A
empresa que não treinou continua no modelo global, sem nenhuma mudança: o
global é o piso, o próprio é uma promoção explícita.

Por que por empresa e não um modelo só: o que a carteira de um banco ensina ao
modelo não é de outro banco. Misturar mudaria a nota de todos os clientes a cada
treino, e levaria dados de uma empresa para dentro da decisão sobre outra.

Disco: `model/empresas/<slug>/` com os mesmos três arquivos do global
(mizan_model.pkl, kmeans.pkl, scaler.pkl), cópias versionadas e versions.json.
O `empresa_id` nunca vira caminho cru: passa por `slug()`.

Instâncias: cada instância tem o seu disco. O cache vence depois de TTL_S e, ao
vencer, confere no Supabase Storage se a versão ativa mudou — é assim que uma
ativação feita numa instância chega às outras.
"""

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent
EMPRESAS_DIR = MODEL_DIR / "empresas"

ATIVOS = ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl")
PRECO = "price_model.pkl"        # opcional: só versões treinadas com os pagamentos têm
TTL_S = 120

_cache: dict = {}          # slug -> (expira, (clf, kmeans, meta) | None)
_trava = threading.Lock()


def slug(empresa_id: str) -> str:
    """Nome de pasta seguro e estável para um empresa_id qualquer."""
    bruto = str(empresa_id or "").strip()
    if not bruto:
        raise ValueError("empresa_id vazio")
    limpo = re.sub(r"[^a-z0-9_-]+", "-", bruto.lower()).strip("-")[:48]
    # Se a limpeza mudou algo (ou zerou), o hash separa ids que colidiriam
    # ("Banco A" e "banco-a" não podem dividir pasta; "../x" não escapa dela).
    if limpo != bruto or not limpo:
        limpo = f"{limpo or 'e'}-{hashlib.sha1(bruto.encode()).hexdigest()[:8]}"
    return limpo


def pasta(empresa_id: str) -> Path:
    destino = (EMPRESAS_DIR / slug(empresa_id)).resolve()
    if EMPRESAS_DIR.resolve() not in destino.parents:     # cinto e suspensório
        raise ValueError("empresa_id inválido")
    return destino


# ── versões ──────────────────────────────────────────────────────────────

def carregar_versoes(empresa_id: str) -> dict:
    arq = pasta(empresa_id) / "versions.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"versoes": [], "versao_ativa": None}


def salvar_versoes(empresa_id: str, dados: dict) -> None:
    p = pasta(empresa_id)
    p.mkdir(parents=True, exist_ok=True)
    tmp = p / "versions.json.tmp"
    tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p / "versions.json")           # troca atômica


def proxima_versao(empresa_id: str) -> str:
    n = len(carregar_versoes(empresa_id)["versoes"]) + 1
    return f"e{n}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def salvar_artefatos(empresa_id: str, versao: str, clf, kmeans, meta: dict) -> None:
    p = pasta(empresa_id)
    p.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf,    p / f"mizan_model_{versao}.pkl")
    joblib.dump(kmeans, p / f"kmeans_{versao}.pkl")
    joblib.dump(meta,   p / f"scaler_{versao}.pkl")


# ── ativação ─────────────────────────────────────────────────────────────

def ativar(empresa_id: str, versao: str) -> None:
    """Torna `versao` o modelo desta empresa. Levanta KeyError se não existir."""
    p = pasta(empresa_id)
    dados = carregar_versoes(empresa_id)
    if not any(v.get("versao") == versao for v in dados["versoes"]):
        raise KeyError(versao)
    origem = {n: p / f"{n.rsplit('.', 1)[0]}_{versao}.pkl" for n in ATIVOS}
    faltam = [n for n, o in origem.items() if not o.exists()]
    if faltam:
        raise FileNotFoundError(f"Arquivos da versão {versao} ausentes: {faltam}")
    for nome, o in origem.items():
        tmp = p / (nome + ".tmp")
        tmp.write_bytes(o.read_bytes())
        os.replace(tmp, p / nome)
    # O modelo de preço vai junto com a versão: só as treinadas com os pagamentos
    # têm um. Ativar uma que não tem tira o da versão anterior (vale a premissa).
    preco = p / f"price_model_{versao}.pkl"
    if preco.exists():
        tmp = p / "price_model.pkl.tmp"
        tmp.write_bytes(preco.read_bytes())
        os.replace(tmp, p / PRECO)
    else:
        (p / PRECO).unlink(missing_ok=True)
    agora = datetime.now(timezone.utc).isoformat()
    for v in dados["versoes"]:
        if v.get("versao") == versao:
            v["promovido"], v["promovido_em"] = True, agora
    dados["versao_ativa"] = versao
    salvar_versoes(empresa_id, dados)
    invalidar(empresa_id)


def desativar(empresa_id: str) -> None:
    """Volta a empresa ao modelo global. Os arquivos da empresa ficam guardados."""
    p = pasta(empresa_id)
    for nome in ATIVOS + (PRECO,):
        (p / nome).unlink(missing_ok=True)
    dados = carregar_versoes(empresa_id)
    dados["versao_ativa"] = None
    salvar_versoes(empresa_id, dados)
    invalidar(empresa_id)


def invalidar(empresa_id: str) -> None:
    with _trava:
        _cache.pop(slug(empresa_id), None)


# ── carga para pontuar ───────────────────────────────────────────────────

def _ler(empresa_id: str):
    p = pasta(empresa_id)
    if not all((p / n).exists() for n in ATIVOS):
        return None
    return (joblib.load(p / "mizan_model.pkl"), joblib.load(p / "kmeans.pkl"),
            joblib.load(p / "scaler.pkl"))


def carregar_ativo(empresa_id: str):
    """(clf, kmeans, meta) do modelo próprio da empresa, ou None se não tiver."""
    if not empresa_id:
        return None
    chave = slug(empresa_id)
    agora = time.monotonic()
    entrada = _cache.get(chave)
    if entrada and entrada[0] > agora:
        return entrada[1]
    with _trava:
        entrada = _cache.get(chave)
        if entrada and entrada[0] > agora:
            return entrada[1]
        try:
            from storage_ml import sincronizar_empresa
            sincronizar_empresa(chave, pasta(empresa_id))
        except Exception:
            pass                        # sem Storage, vale o que há no disco
        try:
            modelos = _ler(empresa_id)
        except Exception as e:           # arquivo corrompido: cai no global, não derruba a análise
            print(f"[ModeloEmpresa] {chave}: falha ao carregar ({e}); usando o modelo global.")
            modelos = None
        _cache[chave] = (agora + TTL_S, modelos)
        return modelos


def tem_modelo_proprio(empresa_id: str) -> bool:
    return carregar_ativo(empresa_id) is not None


def versao_ativa(empresa_id: str) -> "str | None":
    return carregar_versoes(empresa_id).get("versao_ativa") if empresa_id else None
