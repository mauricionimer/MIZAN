"""Estado e trilha da negociação, persistidos em agente_casos.dados.

Os IDs ligam a recomendação ao que foi de fato apresentado, aceito e pago.
O rastreio do orquestrador conserva os passos completos; aqui ficam os fatos
estruturados necessários para retomar a conversa e medir o funil.
"""
import uuid
from datetime import datetime

from agente import guardrails

ETAPAS = ("identidade", "entendimento", "capacidade", "oferta", "aceite", "retorno")
MAX_HISTORICO = 100


def estado(ctx) -> dict:
    dados = dict(ctx.caso.get("dados") or {})
    atual = dict(dados.get("negociacao") or {})
    atual.setdefault("id", uuid.uuid4().hex)
    atual.setdefault("etapa", "identidade" if not dados.get("identidade_ok") else "entendimento")
    dados["negociacao"] = atual
    ctx.caso["dados"] = dados
    return atual


def etapa(ctx, nova: str, *, retomar: bool = False) -> None:
    atual = estado(ctx)
    if nova not in ETAPAS:
        raise ValueError("etapa desconhecida")
    if not retomar and ETAPAS.index(nova) <= ETAPAS.index(atual["etapa"]):
        return
    if atual["etapa"] != nova:
        atual["etapa"] = nova
        atual["etapa_em"] = ctx.agora.isoformat()


def registrar(ctx, tipo: str, chave: str, **campos) -> bool:
    atual = estado(ctx)
    chaves = list(atual.get("chaves") or [])
    if chave in chaves:
        return False
    chaves.append(chave)
    atual["chaves"] = chaves
    totais = dict(atual.get("totais") or {})
    totais[tipo] = int(totais.get(tipo) or 0) + 1
    atual["totais"] = totais
    eventos = list(atual.get("eventos") or [])
    eventos.append({"tipo": tipo, "chave": chave, "em": ctx.agora.isoformat(),
                    "trace_id": ctx.rastreio.trace_id, **campos})
    atual["eventos"] = eventos[-MAX_HISTORICO:]
    return True


def apresentada(ctx, texto: str) -> list[str]:
    """Registra somente simulações cujas condições completas saíram na mensagem."""
    valores = guardrails.valores_do_texto(texto)
    divulgados = []
    vistos = set()

    def mostrou(valor):
        return any(abs(float(valor) - x) <= guardrails.TOLERANCIA for x in valores["dinheiro"])

    for sim in reversed((ctx.caso.get("dados") or {}).get("simulacoes") or []):
        if datetime.fromisoformat(sim["valida_ate"]) <= ctx.agora:
            continue
        cond, conta = sim["condicoes"], sim["conta"]
        n = int(cond["n_parcelas"])
        assinatura = (n, conta["total_pago"], conta["parcela"], conta.get("entrada"))
        if assinatura in vistos:
            continue
        quantidade = (n in valores["parcelas"]) or (
            n == 1 and ("à vista" in texto.lower() or "a vista" in texto.lower()))
        if not (quantidade and mostrou(conta["total_pago"]) and mostrou(conta["parcela"]) and
                (not conta.get("entrada") or mostrou(conta["entrada"]))):
            continue
        vistos.add(assinatura)
        chave = f"apresentada:{sim['id']}"
        if registrar(ctx, "oferta_apresentada", chave, simulacao_id=sim["id"],
                    decisao_id=sim.get("decisao_id"), familia=sim.get("familia"),
                    valor_total=conta["total_pago"]):
            divulgados.append(sim["id"])
    if divulgados:
        etapa(ctx, "oferta", retomar=True)
    return divulgados


def acordo(ctx, sim: dict, compromisso_id: str) -> None:
    registrar(ctx, "acordo_aceito", f"aceite:{sim['id']}", simulacao_id=sim["id"],
              decisao_id=sim.get("decisao_id"), familia=sim.get("familia"),
              compromisso_id=compromisso_id)
    etapa(ctx, "aceite", retomar=True)


def pagamento(ctx, promessas: list, valor: float) -> None:
    acordo_atual = (ctx.caso.get("dados") or {}).get("acordo") or {}
    compromisso_id = acordo_atual.get("compromisso_id")
    if compromisso_id and any(p.get("id") == compromisso_id for p in promessas):
        if registrar(ctx, "primeiro_pagamento_confirmado", f"pagamento:{compromisso_id}",
                     compromisso_id=compromisso_id, simulacao_id=acordo_atual.get("simulacao_id"),
                     decisao_id=acordo_atual.get("decisao_id"), valor=valor):
            estado(ctx)["primeiro_pagamento_valor"] = valor


def metricas(casos: list, pagos: dict) -> dict:
    """Funil descritivo; pagamentos vêm exclusivamente dos feedbacks confirmados."""
    r = {"casos": 0, "decisoes": 0, "ofertas_apresentadas": 0, "acordos_aceitos": 0,
         "primeiro_pagamento_confirmado": 0, "acordos_quebrados": 0,
         "retornos_cumpridos": 0, "transferencias_humanas": 0,
         "valor_primeiro_pagamento_confirmado": 0.0}
    for caso in casos:
        d = caso.get("dados") or {}
        n = d.get("negociacao") or {}
        if not n:
            continue
        r["casos"] += 1
        r["decisoes"] += bool((d.get("estrategia") or {}).get("decisao_id"))
        eventos = n.get("eventos") or []
        totais = n.get("totais") or {}
        contar = lambda tipo: int(totais.get(tipo, sum(e.get("tipo") == tipo for e in eventos)))
        r["ofertas_apresentadas"] += contar("oferta_apresentada")
        r["acordos_aceitos"] += contar("acordo_aceito")
        confirmado = caso["predicao_id"] in pagos and contar("primeiro_pagamento_confirmado") > 0
        r["primeiro_pagamento_confirmado"] += confirmado
        r["acordos_quebrados"] += max(contar("acordo_quebrado"), int(caso.get("situacao") == "quebrado"))
        r["retornos_cumpridos"] += contar("retorno_cumprido")
        r["transferencias_humanas"] += contar("transferencia_humana")
        if confirmado:
            primeiro = n.get("primeiro_pagamento_valor")
            if primeiro is None:
                primeiro = next((e.get("valor") for e in eventos if e.get("tipo") == "primeiro_pagamento_confirmado"), 0)
            r["valor_primeiro_pagamento_confirmado"] += float(primeiro or 0)
    r["valor_primeiro_pagamento_confirmado"] = round(r["valor_primeiro_pagamento_confirmado"], 2)
    return r
