"""Sinais observacionais da sala. Sem texto, prompts, documentos ou decisões.

Usa somente o JSON do evento já reservado pelo worker. Não cria eventos de
negócio e não muda o grafo. Histórico limitado; nenhuma migração necessária.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def observador(repo, evento, trace_id):
    dados = deepcopy(evento.get("dados") or {})
    sinais = []
    ultimo = None

    def publico(p):
        return {k: p.get(k) for k in ("no", "agente")} if p else None

    def observar(tipo, passo, atual):
        nonlocal ultimo
        t = datetime.now(timezone.utc).isoformat()
        p, ativo = publico(passo), publico(atual)
        if p and tipo in ("inicio", "fim", "erro"):
            sinais.append({"id": uuid4().hex, "t": t, "tipo": tipo, **p,
                           "resultado": passo.get("resultado") if tipo in ("fim", "erro") else None})
        if ativo and ultimo and ativo != ultimo:
            sinais.append({"id": uuid4().hex, "t": t, "tipo": "handoff", "de": ultimo, "para": ativo})
        if ativo:
            ultimo = ativo
        del sinais[:-80]
        dados["_escritorio"] = {"trace_id": trace_id, "atualizado_em": t,
                                "atual": {**ativo, "estado": "pensando" if tipo == "pensando" else "trabalhando"} if ativo else None,
                                "sinais": sinais[-80:]}
        repo.atualizar_evento(evento["id"], {"dados": deepcopy(dados)})
    return observar


def para_tela(eventos, quem, agora):
    ativos, sinais, casos = [], [], []
    sem_sinal = 0
    for e in eventos:
        base = {k: e.get(k) for k in ("id", "caso_id", "trace_id", "situacao", "tipo", "tentativas")}
        tele = e.get("escritorio") or {}
        try:
            idade = agora - datetime.fromisoformat(tele.get("atualizado_em", "").replace("Z", "+00:00"))
            recente = timedelta(seconds=-5) <= idade < timedelta(minutes=5)
        except (ValueError, TypeError):
            recente = False
        if e.get("situacao") == "processando":
            p = tele.get("atual")
            if p and recente:
                ativos.append({**base, "quem": quem(p), "no": p.get("no"), "estado": p.get("estado"),
                               "atualizado_em": tele.get("atualizado_em")})
            else:
                sem_sinal += 1
        etapas = []
        for s in tele.get("sinais", [])[-80:]:
            # Projeta campos conhecidos; nunca devolve o JSON de entrada do evento.
            item = {**base, "id": s.get("id"), "t": s.get("t"), "tipo": s.get("tipo"),
                    "quem": quem(s), "no": s.get("no"), "resultado": s.get("resultado")}
            if s.get("tipo") == "handoff" and s.get("de") and s.get("para"):
                item.update(de=quem(s["de"]), para=quem(s["para"]))
                if item["de"] == item["para"]:
                    continue
            if s.get("tipo") == "fim" and s.get("resultado") != "bloqueado":
                etapas.append(quem(s))
            sinais.append(item)
        if e.get("situacao") in ("pendente", "processando", "falhou"):
            casos.append({**base, "etapas": list(dict.fromkeys(etapas)),
                          "quem": quem(tele["atual"]) if tele.get("atual") and recente and e.get("situacao") == "processando" else None})
    sinais.sort(key=lambda s: s.get("t") or "", reverse=True)
    return {"executando": ativos, "sinais": sinais[:100], "casos": casos[:100], "limite_eventos": 500,
            "execucoes_sem_sinal": sem_sinal}
