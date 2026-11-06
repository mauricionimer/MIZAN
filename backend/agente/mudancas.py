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
_U: dict = {}          # usuario_id -> contador das notificações dele (backend/notificacoes.py)


def marcar_usuario(usuario_id) -> None:
    """As notificações desta pessoa mudaram (aviso novo, lido ou resolvido)."""
    if not usuario_id:
        return
    with _LOCK:
        if len(_U) > 50000:
            _U.clear()                    # o _INICIO não muda, mas as telas recarregam no próximo aviso
        _U[str(usuario_id)] = _U.get(str(usuario_id), 0) + 1


def marcar(empresa_id, *topicos) -> None:
    """Algo mudou nesta empresa (sem empresa conhecida: vale para todas as telas)."""
    with _LOCK:
        for t in topicos or TOPICOS:
            chave = str(empresa_id) if empresa_id else "~"
            _N[(chave, t)] = _N.get((chave, t), 0) + 1
            _N[("*", t)] = _N.get(("*", t), 0) + 1


def versoes(empresa_id=None, usuario_id=None) -> dict:
    """{tópico: versão}. Com empresa: as mudanças dela e as sem empresa; sem empresa
    (COMANDO olhando várias): todas. Com a pessoa: também a versão das notificações dela."""
    with _LOCK:
        if not empresa_id:
            saida = {t: f"{_INICIO}:{_N.get(('*', t), 0)}" for t in TOPICOS}
        else:
            e = str(empresa_id)
            saida = {t: f"{_INICIO}:{_N.get((e, t), 0)}:{_N.get(('~', t), 0)}" for t in TOPICOS}
        if usuario_id:
            saida["notificacoes"] = f"{_INICIO}:{_U.get(str(usuario_id), 0)}"
        return saida
