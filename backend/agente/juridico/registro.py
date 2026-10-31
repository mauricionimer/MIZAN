"""Registro interno das decisões jurídicas: o que se considerou, a conclusão, a justificativa,
os dispositivos e fontes, a data e as incertezas.

- Sem dado pessoal: guarda ids internos (empresa, caso, rastreio) e fatos estruturados.
  Os fatos ficam cifrados com a chave Fernet da Mizan, por garantia.
- Acesso: tabela com RLS (só o backend); a leitura é por rota de administrador
  (GET /agente/juridico/decisoes). O rastreio visível à operação só leva a ação e a decisão.
- Falha ao gravar não muda a decisão: o lado seguro já foi escolhido antes.
"""
import json
import time

from agente import cripto


def registrar(repo, empresa_id: str, caso_id, trace_id, decisao: dict) -> str | None:
    gravar = getattr(repo, "gravar_consulta_juridica", None)
    if gravar is None:
        return None
    try:
        linha = {
            "empresa_id": empresa_id, "caso_id": str(caso_id) if caso_id else None, "trace_id": trace_id,
            "acao": decisao.get("acao"), "decisao": decisao.get("decisao"),
            "condicoes": decisao.get("condicoes") or [], "justificativa": decisao.get("justificativa"),
            "dispositivos": decisao.get("dispositivos") or [], "fontes": decisao.get("fontes") or [],
            "incertezas": decisao.get("incertezas") or [], "indice_versao": decisao.get("indice_versao"),
            "consultado_em": decisao.get("consultado_em"),
            "contexto_cifrado": cripto.cifrar(json.dumps(decisao.get("fatos") or {}, ensure_ascii=False,
                                                         sort_keys=True, default=str)),
        }
        return gravar(linha)
    except Exception as e:                              # tabela ausente, banco fora: a decisão vale assim mesmo
        print(f"[Jurídico] decisão não registrada: {type(e).__name__}")
        return None


def listar(repo, empresa_id: str, caso_id=None, n: int = 50) -> list:
    """Para a rota de administrador: decisões com os fatos decifrados."""
    saida = []
    for r in repo.consultas_juridicas(empresa_id, caso_id=caso_id, n=n):
        r = dict(r)
        bruto = cripto.decifrar(r.pop("contexto_cifrado", None))
        try:
            r["fatos"] = json.loads(bruto) if bruto else None
        except ValueError:
            r["fatos"] = None
        saida.append(r)
    return saida


_CONFERENCIAS = {}                       # "banco" -> (até quando, resultado)
_CONFERENCIAS_S = 600                    # mudam só quando o administrador confere de novo


def conferencias(repo) -> dict:
    """Conferências oficiais feitas pelo servidor ({norma_id: resultado}), se houver.
    No banco real, guardadas por 10 minutos: toda decisão lê isso, e o banco não precisa
    ser lido a cada vez (o repositório em memória dos testes é lido direto)."""
    ler = getattr(repo, "conferencias_juridicas", None)
    if ler is None:
        return {}
    guardar = hasattr(repo, "db")
    agora = time.monotonic()
    achado = _CONFERENCIAS.get("banco") if guardar else None
    if achado and achado[0] > agora:
        return achado[1]
    try:
        res = ler() or {}
    except Exception as e:
        print(f"[Jurídico] conferências indisponíveis: {type(e).__name__}")
        return {}                         # sem guardar: tenta de novo na próxima
    if guardar:
        _CONFERENCIAS["banco"] = (agora + _CONFERENCIAS_S, res)
    return res


def esquecer_conferencias() -> None:
    _CONFERENCIAS.clear()
