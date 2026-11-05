"""Estado da plataforma (tela de Ajuda): o que está funcionando, medido de verdade.

Cada serviço vem de uma fonte real. Sem dado na janela, o serviço aparece como
"sem medição", nunca como "ok": a tela não pode afirmar o que não mediu.

  agentes   passos gravados pelos agentes (agente_passos): erros e tempo de resposta
  email     resultado dos envios feitos por este servidor (email_utils), desde que ligou
  pagamentos tempo entre o pagamento e o registro dele na MIZAN (feedbacks)
  servidor  esta própria resposta: se chegou aqui, o servidor está respondendo

Funções puras: recebem as linhas e o "agora", devolvem o resumo. Testadas em
test_estado_plataforma.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# Nós que respondem ao devedor: o tempo deles é o que a pessoa sente.
NOS_DE_RESPOSTA = ("triagem", "negociar")
LIMITE_LENTO_MS = 8000          # resposta acima disso é lenta para uma conversa
LIMITE_ATRASO_DIAS = 3          # pagamento registrado depois disso está atrasado


def _p95(valores: list) -> int | None:
    if not valores:
        return None
    v = sorted(valores)
    return int(v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))])


def _estado(nivel: float | None) -> str:
    if nivel is None:
        return "sem_medicao"
    return "ok" if nivel >= 90 else "atencao" if nivel >= 70 else "problema"


def _servico(id_, nome, nivel, frase, amostra, janela):
    return {"id": id_, "nome": nome, "estado": _estado(nivel),
            "nivel": None if nivel is None else round(max(0.0, min(100.0, nivel)), 1),
            "frase": frase, "amostra": amostra, "janela": janela}


def agentes(passos: list) -> dict:
    """Saúde das respostas dos agentes: parte sem erro, com o p95 do tempo."""
    resp = [p for p in passos if p.get("no") in NOS_DE_RESPOSTA]
    if not resp:
        return _servico("agentes", "Agentes de conversa", None, "Nenhuma resposta de agente nas últimas 24 h.", 0, "24 h")
    erros = sum(1 for p in resp if p.get("resultado") == "erro")
    duracoes = [int(p.get("duracao_ms") or 0) for p in resp if p.get("duracao_ms") is not None]
    p95 = _p95(duracoes)
    lentos = sum(1 for d in duracoes if d > LIMITE_LENTO_MS)
    nivel = 100 * (len(resp) - erros - lentos) / len(resp)
    seg = f"{p95 / 1000:.1f}".replace(".", ",") if p95 is not None else "—"
    frase = (f"{len(resp) - erros} de {len(resp)} respostas sem erro; 95% saíram em até {seg} s."
             if erros else f"Todas as {len(resp)} respostas sem erro; 95% saíram em até {seg} s.")
    return {**_servico("agentes", "Agentes de conversa", nivel, frase, len(resp), "24 h"), "p95_ms": p95, "erros": erros}


def email(envios: list, agora: datetime) -> dict:
    """Envios de e-mail (convites, redefinição de senha, avisos) nas últimas 24 h."""
    desde = agora - timedelta(hours=24)
    recentes = [e for e in envios if e.get("em") and e["em"] >= desde]
    if not recentes:
        return _servico("email", "Envio de e-mail", None,
                        "Nenhum e-mail enviado nas últimas 24 h desde que o servidor ligou.", 0, "24 h")
    ok = sum(1 for e in recentes if e.get("ok"))
    frase = (f"Todos os {ok} e-mails saíram." if ok == len(recentes)
             else f"{ok} de {len(recentes)} e-mails saíram; os outros falharam no envio.")
    return _servico("email", "Envio de e-mail", 100 * ok / len(recentes), frase, len(recentes), "24 h")


def pagamentos(feedbacks: list) -> dict:
    """Quanto tempo um pagamento leva para ser registrado (últimos 30 dias)."""
    atrasos = []
    for f in feedbacks:
        try:
            pago = datetime.fromisoformat(str(f["data_pagamento"])[:10]).date()
            registrado = datetime.fromisoformat(str(f["created_at"]).replace("Z", "+00:00")).date()
        except (KeyError, TypeError, ValueError):
            continue
        atrasos.append(max(0, (registrado - pago).days))
    if not atrasos:
        return _servico("pagamentos", "Registro de pagamentos", None,
                        "Nenhum pagamento com data registrado nos últimos 30 dias.", 0, "30 dias")
    no_prazo = sum(1 for d in atrasos if d <= LIMITE_ATRASO_DIAS)
    mediana = sorted(atrasos)[len(atrasos) // 2]
    frase = (f"{no_prazo} de {len(atrasos)} pagamentos registrados em até {LIMITE_ATRASO_DIAS} dias; "
             f"metade em até {mediana} {'dia' if mediana == 1 else 'dias'}.")
    return _servico("pagamentos", "Registro de pagamentos", 100 * no_prazo / len(atrasos), frase, len(atrasos), "30 dias")


def servidor() -> dict:
    return _servico("servidor", "Servidor da MIZAN", 100.0, "Respondendo agora.", 1, "agora")


def resumo(servicos: list) -> dict:
    medidos = [s for s in servicos if s["estado"] != "sem_medicao"]
    pior = ("problema" if any(s["estado"] == "problema" for s in medidos) else
            "atencao" if any(s["estado"] == "atencao" for s in medidos) else "ok")
    frase = {"ok": "Tudo funcionando.", "atencao": "Funcionando, com um ponto de atenção.",
             "problema": "Há um serviço com problema."}[pior]
    return {"estado": pior, "frase": frase, "servicos": servicos,
            "sem_medicao": sum(1 for s in servicos if s["estado"] == "sem_medicao")}
