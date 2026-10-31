"""Monta (ou atualiza) o índice jurídico a partir do acervo.

    # simulação (não grava): mostra o que mudaria
    python -m agente.juridico.ingestao --acervo /caminho/para/leis
    # grava o índice e o manifesto
    python -m agente.juridico.ingestao --acervo /caminho/para/leis --aplicar
    # e tenta conferir na fonte oficial (precisa de internet)
    python -m agente.juridico.ingestao --acervo /caminho/para/leis --aplicar --conferir

`--acervo` pode ser um clone git do ctresb/leis (lê os arquivos direto do commit, sem
precisar extrair os 17 GB) ou uma pasta com os mesmos caminhos.

Atualização incremental: norma cujo arquivo, recorte, alterações conhecidas e versão do
parser não mudaram fica como estava (com as datas originais). Mudou: só ela é relida, e o
relatório diz quais dispositivos entraram, mudaram ou saíram.

Deduplicação: o mesmo dispositivo duas vezes na mesma norma com textos diferentes vira
conflito (ver estrutura.py); texto longo idêntico em duas normas fica só na de maior
prioridade (a outra aponta para ela em `duplicado_de` e sai da busca).

O índice contém só texto público das normas. Nada de devedor ou cliente entra aqui.
"""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agente.juridico import estrutura
from agente.juridico.catalogo import ACERVO_URL, CATALOGO, DESCARTADAS

DADOS = Path(__file__).resolve().parent / "dados"
ARQ_INDICE = "indice.jsonl.gz"
ARQ_MANIFESTO = "manifesto.json"
MIN_DUPLICADO = 120          # só texto longo idêntico conta como duplicado entre normas


class Acervo:
    """Lê arquivos do acervo: de um clone git (pelo commit) ou de uma pasta."""

    def __init__(self, caminho: str, commit: str = "HEAD"):
        self.caminho = Path(caminho)
        self.git = (self.caminho / ".git").exists()
        self.commit, self.data_commit = None, None
        if self.git:
            saida = subprocess.run(["git", "-C", str(self.caminho), "log", "-1", "--format=%H %cI", commit],
                                   capture_output=True, text=True, check=True).stdout.split()
            self.commit, self.data_commit = saida[0], saida[1]

    def ler(self, rel: str) -> str | None:
        if self.git:
            r = subprocess.run(["git", "-C", str(self.caminho), "show", f"{self.commit}:{rel}"],
                               capture_output=True)
            return r.stdout.decode("utf-8") if r.returncode == 0 else None
        p = self.caminho / rel
        return p.read_text(encoding="utf-8") if p.exists() else None


def carregar(dados: Path = DADOS) -> tuple:
    """(registros, manifesto) gravados; vazios se ainda não houver índice."""
    indice, manifesto = [], {}
    if (dados / ARQ_INDICE).exists():
        with gzip.open(dados / ARQ_INDICE, "rt", encoding="utf-8") as f:
            indice = [json.loads(l) for l in f if l.strip()]
    if (dados / ARQ_MANIFESTO).exists():
        manifesto = json.loads((dados / ARQ_MANIFESTO).read_text(encoding="utf-8"))
    return indice, manifesto


def _assinatura(norma, sha_arquivo: str) -> str:
    base = json.dumps([sha_arquivo, list(norma.recorte), list(norma.alteracoes), norma.sigla,
                       estrutura.VERSAO_PARSER], ensure_ascii=False)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def montar(acervo: Acervo, anterior: list, manifesto_ant: dict, agora: datetime | None = None,
           catalogo=CATALOGO) -> tuple:
    """(registros, manifesto, relatório). Não grava nada."""
    agora = agora or datetime.now(timezone.utc)
    ant_por_norma = {}
    for r in anterior:
        ant_por_norma.setdefault(r["norma_id"], []).append(r)
    normas_ant = (manifesto_ant or {}).get("normas", {})
    registros, normas, relatorio = [], {}, {"normas": {}, "faltando": []}

    for norma in catalogo:
        texto = acervo.ler(norma.caminho)
        if texto is None:
            relatorio["faltando"].append(norma.caminho)
            if norma.id in normas_ant:                     # some do acervo: fica a cópia anterior, sinalizada
                normas[norma.id] = {**normas_ant[norma.id], "ausente_no_acervo_em": agora.isoformat()}
                registros += ant_por_norma.get(norma.id, [])
            continue
        sha = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        assinatura = _assinatura(norma, sha)
        meta, _ = estrutura.ler_cabecalho(texto)
        anterior_m = normas_ant.get(norma.id) or {}
        if anterior_m.get("assinatura") == assinatura and ant_por_norma.get(norma.id):
            registros += ant_por_norma[norma.id]
            normas[norma.id] = {**anterior_m, "commit": acervo.commit or anterior_m.get("commit"),
                                "verificado_no_acervo_em": agora.isoformat()}
            relatorio["normas"][norma.id] = {"situacao": "sem mudança", "dispositivos": len(ant_por_norma[norma.id])}
            continue

        novos = estrutura.dispositivos(texto, norma.id, norma.sigla, norma.recorte)
        alteradas = {a: desc for a, desc in norma.alteracoes}
        antigos = {r["id"]: r for r in ant_por_norma.get(norma.id, [])}
        mudancas = {"novos": 0, "alterados": 0, "iguais": 0, "removidos": 0}
        for d in novos:
            if d["artigo"] in alteradas and d["situacao"] == "vigente":
                d["situacao"] = "desatualizado"
                d["notas"] = d["notas"] + [alteradas[d["artigo"]]]
            velho = antigos.pop(d["id"], None)
            if velho is None:
                mudancas["novos"] += 1
                d["ingerido_em"] = agora.isoformat()
            elif velho["hash"] == d["hash"] and velho.get("situacao") == d["situacao"]:
                mudancas["iguais"] += 1
                d["ingerido_em"] = velho.get("ingerido_em") or agora.isoformat()
            else:
                mudancas["alterados"] += 1
                d["ingerido_em"] = agora.isoformat()
                d["hash_anterior"] = velho["hash"]
        mudancas["removidos"] = len(antigos)
        registros += novos
        normas[norma.id] = {
            "id": norma.id, "sigla": norma.sigla, "titulo": meta.get("titulo"), "tipo": meta.get("tipo"),
            "numero": meta.get("numero"), "data": meta.get("data"), "ementa": meta.get("ementa"),
            "versao_texto": meta.get("versao_texto"), "revogada": meta.get("revogada"),
            "situacao_fonte": meta.get("situacao"), "fonte_original": meta.get("fonte"),
            "baixado_em_pelo_acervo": meta.get("baixado_em"), "arquivo": norma.caminho, "sha256_arquivo": sha,
            "commit": acervo.commit, "data_commit": acervo.data_commit,
            "url_repositorio": (f"{ACERVO_URL}/blob/{acervo.commit}/{norma.caminho}" if acervo.commit
                                else f"{ACERVO_URL}/blob/main/{norma.caminho}"),
            "url_oficial": norma.url_oficial, "motivo": norma.motivo, "recorte": [list(r) for r in norma.recorte],
            "aplica_se": norma.aplica_se, "observacoes": list(norma.observacoes),
            "alteracoes_conhecidas": [{"artigo": a, "descricao": d} for a, d in norma.alteracoes],
            "prioridade": norma.prioridade, "assinatura": assinatura, "ingerido_em": agora.isoformat(),
            # A conferência anterior só vale se o texto não mudou.
            "conferencia": (anterior_m.get("conferencia") if anterior_m.get("sha256_arquivo") == sha
                            else {"status": "nao_conferida", "em": None,
                                  "detalhe": "ainda não conferido na fonte oficial"}),
            "dispositivos": len(novos),
        }
        relatorio["normas"][norma.id] = {"situacao": "relida", **mudancas, "dispositivos": len(novos)}

    _deduplicar(registros, {n.id: n.prioridade for n in catalogo})
    versao = hashlib.sha1("".join(sorted(f"{r['id']}={r['hash']}={r['situacao']}" for r in registros))
                          .encode("utf-8")).hexdigest()[:12]
    manifesto = {
        "acervo": ACERVO_URL, "commit": acervo.commit or (manifesto_ant or {}).get("commit"),
        "data_commit": acervo.data_commit, "versao_indice": versao, "gerado_em": agora.isoformat(),
        "versao_parser": estrutura.VERSAO_PARSER, "normas": normas,
        "descartadas": [{"caminho": c, "motivo": m} for c, m in DESCARTADAS],
        "aviso": ("Cópia de consulta de um acervo convertido automaticamente: pode conter erros ou estar "
                  "desatualizada. Redação e vigência se confirmam na fonte oficial (conferencia)."),
    }
    relatorio["versao_indice"] = versao
    relatorio["total"] = len(registros)
    return registros, manifesto, relatorio


def _deduplicar(registros: list, prioridade: dict) -> None:
    por_hash = {}
    for r in registros:
        r.pop("duplicado_de", None)
        if r["situacao"] in ("vigente", "desatualizado") and len(r["texto"]) >= MIN_DUPLICADO:
            por_hash.setdefault(r["hash"], []).append(r)
    for grupo in por_hash.values():
        normas = {r["norma_id"] for r in grupo}
        if len(normas) < 2:
            continue
        grupo.sort(key=lambda r: (prioridade.get(r["norma_id"], 9), r["id"]))
        for r in grupo[1:]:
            if r["norma_id"] != grupo[0]["norma_id"]:
                r["duplicado_de"] = grupo[0]["id"]


def gravar(registros: list, manifesto: dict, dados: Path = DADOS) -> None:
    dados.mkdir(parents=True, exist_ok=True)
    tmp = dados / (ARQ_INDICE + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as f:
        for r in sorted(registros, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, dados / ARQ_INDICE)
    (dados / ARQ_MANIFESTO).write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True),
                                       encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--acervo", required=True, help="clone git do ctresb/leis ou pasta com os mesmos caminhos")
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--dados", default=str(DADOS))
    ap.add_argument("--aplicar", action="store_true", help="grava o índice e o manifesto")
    ap.add_argument("--conferir", action="store_true", help="confere cada norma na fonte oficial (internet)")
    a = ap.parse_args(argv)
    dados = Path(a.dados)
    anterior, manifesto_ant = carregar(dados)
    registros, manifesto, rel = montar(Acervo(a.acervo, a.commit), anterior, manifesto_ant)
    if a.conferir:
        from agente.juridico import conferencia
        for nid, m in manifesto["normas"].items():
            m["conferencia"] = conferencia.conferir(m, [r for r in registros if r["norma_id"] == nid])
    print(json.dumps(rel, ensure_ascii=False, indent=2))
    if a.aplicar:
        gravar(registros, manifesto, dados)
        print(f"gravado em {dados} (versão {manifesto['versao_indice']})")
    else:
        print("simulação: nada gravado (use --aplicar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
