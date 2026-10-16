"""O que as telas do agente usam (rotas em main.py): conversa de um caso, a
simulação de mensagem do devedor na demonstração e a Central de orquestração.

Tudo escopado à empresa. As fábricas abaixo são trocadas nos testes.
"""
import os
import uuid
from collections import Counter
from datetime import datetime, timezone

from agente import auditor, llm, orquestrador as orq
from agente.fonte import FonteSupabase
from agente.grafos import grafo_mensagem
from agente.repositorio import RepoSupabase

fabrica_repo = RepoSupabase
fabrica_fonte = FonteSupabase
fabrica_cliente = llm.cliente

MAX_TEXTO = 2000


class AgenteDesligado(RuntimeError):
    pass


def ligado() -> bool:
    """Interruptor geral (variável MIZAN_AGENTE_ATIVO=1 no Render)."""
    return os.getenv("MIZAN_AGENTE_ATIVO", "").strip() == "1"


def _passo_publico(p: dict) -> dict:
    return {k: p.get(k) for k in ("no", "agente", "resultado", "duracao_ms", "regra", "versao_politica",
                                  "modelo", "versao_prompt", "tokens_entrada", "tokens_saida", "custo_usd",
                                  "detalhe", "criado_em")}


def ver_caso(empresa_id: str, predicao_id: str, repo=None) -> dict:
    repo = repo or fabrica_repo()
    caso = repo.caso_de(empresa_id, predicao_id)
    if caso is None:
        return {"caso": None, "mensagens": [], "passos": []}
    msgs = repo.ultimas_mensagens(empresa_id, caso["id"], 50)
    ultimo_trace = next((m.get("trace_id") for m in reversed(msgs) if m.get("trace_id")), None)
    passos = repo.passos_do_trace(empresa_id, ultimo_trace) if ultimo_trace else []
    d = caso.get("dados") or {}
    return {
        "caso": {"id": caso["id"], "situacao": caso["situacao"], "proxima_data": caso.get("proxima_data"),
                 "versao_politica": caso.get("versao_politica"), "resumo": caso.get("resumo"),
                 "identidade_confirmada": bool(d.get("identidade_ok")), "acordo": d.get("acordo")},
        "mensagens": [{"direcao": m["direcao"], "texto": m["texto"], "criado_em": m.get("criado_em"),
                       "trace_id": m.get("trace_id")} for m in msgs],
        "trace_id": ultimo_trace,
        "passos": [_passo_publico(p) for p in passos],
    }


def simular_mensagem(empresa_id: str, predicao_id: str, texto: str, agora: datetime | None = None) -> dict:
    """Demonstração: a tela faz o papel do devedor escrevendo pelo canal."""
    if not ligado():
        raise AgenteDesligado("O agente está desligado (MIZAN_AGENTE_ATIVO).")
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escreva a mensagem.")
    if len(texto) > MAX_TEXTO:
        raise ValueError(f"Mensagem com mais de {MAX_TEXTO} caracteres.")
    repo, fonte = fabrica_repo(), fabrica_fonte()
    if fonte.devedor(empresa_id, predicao_id) is None:
        raise LookupError("Devedor não encontrado nas carteiras da empresa.")
    caso = repo.obter_ou_criar_caso(empresa_id, predicao_id)
    ev, _ = orq.registrar_evento(repo, empresa_id, caso["id"], "mensagem_devedor", f"tela:{uuid.uuid4().hex}",
                                 {"texto": texto}, origem="tela")
    orq.processar_fila(repo, {"mensagem_devedor": grafo_mensagem(fonte)}, fabrica_cliente(), limite=5,
                       agora=agora or datetime.now(timezone.utc))
    r = ver_caso(empresa_id, predicao_id, repo)
    final = repo.evento_por_chave(empresa_id, ev["chave"]) or {}
    r["evento"] = {"situacao": final.get("situacao"), "erro": final.get("erro")}
    return r


def central(empresa_id: str, agora: datetime | None = None) -> dict:
    """Central de orquestração: fila, falhas, casos por situação e custo do dia."""
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    eventos = repo.eventos_recentes(empresa_id, 500)
    regras, versao = None, None
    achada = repo.politica_ativa(empresa_id)
    if achada:
        try:
            regras, versao = auditor.validar_politica(achada["regras"]), achada["versao"]
        except ValueError:
            pass
    return {
        "ligado": ligado(),
        "cliente": os.getenv("MIZAN_AGENTE_CLIENTE", "falso"),
        "modelos": {"triagem": llm.modelo_para("triagem"), "negociador": llm.modelo_para("negociador")},
        "custo_hoje_usd": repo.custo_do_dia(empresa_id, agora.date()),
        "teto_dia_usd": llm.teto_dia_usd(),
        "politica": {"versao": versao, "regras": regras},
        "eventos": dict(Counter(e["situacao"] for e in eventos)),
        "falhas": [{k: e.get(k) for k in ("id", "caso_id", "tipo", "erro", "tentativas", "criado_em", "trace_id")}
                   for e in eventos if e["situacao"] == "falhou"][:20],
        "recentes": [{k: e.get(k) for k in ("caso_id", "tipo", "origem", "situacao", "erro", "criado_em", "trace_id")}
                     for e in eventos[:20]],
        "casos": dict(Counter(repo.situacoes_dos_casos(empresa_id))),
    }


def passos(empresa_id: str, trace_id: str) -> list:
    return [_passo_publico(p) for p in fabrica_repo().passos_do_trace(empresa_id, trace_id)]
