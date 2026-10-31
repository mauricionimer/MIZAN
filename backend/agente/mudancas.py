"""Contadores de mudança por empresa, para as telas se atualizarem sozinhas.

Toda vez que algo muda (o agente mexe na agenda, termina uma rodada de um caso,
alguém salva algo pelo sistema), o contador do tópico sobe. As telas perguntam
os contadores a cada poucos segundos (GET /mudancas, sem ir ao banco) e só
recarregam os dados quando um deles mudou.

Fica em memória: o servidor roda um processo só. Reiniciou, o `_INICIO` muda e
as telas recarregam uma vez. Não guarda nada além de números.
"""
import threading
import uuid

TOPICOS = ("agenda", "casos")
_INICIO = uuid.uuid4().hex[:8]
_LOCK = threading.Lock()
_N: dict = {}          # (chave, tópico) -> contador. chave: empresa_id, "~" (sem empresa) ou "*" (todas)


def marcar(empresa_id, *topicos) -> None:
    """Algo mudou nesta empresa (sem empresa conhecida: vale para todas as telas)."""
    with _LOCK:
        for t in topicos or TOPICOS:
            chave = str(empresa_id) if empresa_id else "~"
            _N[(chave, t)] = _N.get((chave, t), 0) + 1
            _N[("*", t)] = _N.get(("*", t), 0) + 1


def versoes(empresa_id=None) -> dict:
    """{tópico: versão}. Com empresa: as mudanças dela e as sem empresa; sem empresa
    (COMANDO olhando várias): todas."""
    with _LOCK:
        if not empresa_id:
            return {t: f"{_INICIO}:{_N.get(('*', t), 0)}" for t in TOPICOS}
        e = str(empresa_id)
        return {t: f"{_INICIO}:{_N.get((e, t), 0)}:{_N.get(('~', t), 0)}" for t in TOPICOS}
