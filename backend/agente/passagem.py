"""Passagem para a equipe: a ficha que acompanha o caso quando ele vai para uma pessoa.

(docs/PLANO_PASSAGEM_EQUIPE.md)

- `montar_ficha`: junta o que o Supervisor escreveu (IA) com o que o código sabe
  de forma exata (valor que a pessoa disse, o que já foi oferecido, sugestão de
  proposta dentro da política, prioridade). Nada aqui chama a IA.
- `sugerir_proposta`: percorre as condições válidas da política com as mesmas
  contas do simulador e confere cada uma no Auditor.
- `prioridade`: número de 0 a 100 para a fila da equipe.
- `registrar_retorno`: o atendente diz se o resumo ajudou (nota do Supervisor).
- `sinais_da_equipe`: o que as passagens da semana dizem, para o Cientista.
"""
from datetime import datetime, timedelta, timezone
from statistics import median

from agente import auditor, guardrails
from model import oferta

EMOCOES = ("calmo", "ansioso", "irritado", "triste", "desesperado")
URGENCIAS = ("baixa", "media", "alta")
PESO_EMOCAO = {"desesperado": 40, "irritado": 30, "ansioso": 20, "triste": 15, "calmo": 0}
PESO_URGENCIA = {"alta": 30, "media": 15, "baixa": 0}
PARCELAS_CANDIDATAS = (1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 18, 24, 36, 48, 60)
MAX_PASSAGENS = 10
MAX_VALORES = 5


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _resumo(cond: dict, conta: dict) -> str:
    n = cond["n_parcelas"]
    if n == 1:
        txt = f"à vista {_brl(conta['total_pago'])}"
    else:
        txt = (f"entrada {_brl(conta['entrada'])} + " if conta["entrada"] > 0 else "") + f"{n}x de {_brl(conta['parcela'])}"
    return txt + (f", {cond['desconto_pct']:g}% de desconto" if cond["desconto_pct"] else "")


def _mensal(cond: dict, conta: dict) -> float:
    """O que pesa por mês: a parcela (ou o valor à vista)."""
    return conta["total_pago"] if cond["n_parcelas"] == 1 else conta["parcela"]


# ── valores ditos pela pessoa ────────────────────────────────────────────────

def anotar_valores(caso: dict, valores: list) -> None:
    """Guarda os valores em reais que a Triagem leu na mensagem (os últimos 5)."""
    divida = float((caso.get("dados") or {}).get("divida") or 0)
    bons = [round(float(v), 2) for v in valores or []
            if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= max(divida * 2, 1_000_000)]
    if not bons:
        return
    d = caso.setdefault("dados", {})
    d["valores_ditos"] = ((d.get("valores_ditos") or []) + bons)[-MAX_VALORES:]


def valor_dito(dados: dict) -> float | None:
    vs = dados.get("valores_ditos") or []
    return float(vs[-1]) if vs else None


# ── o que já foi oferecido e a sugestão ─────────────────────────────────────

def tentado(dados: dict) -> list:
    saida, vistos = [], set()
    for s in dados.get("simulacoes") or []:
        cond, conta = s.get("condicoes") or {}, s.get("conta") or {}
        if not cond or not conta:
            continue
        chave = (cond.get("n_parcelas"), cond.get("desconto_pct"), cond.get("entrada_pct"))
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append({"resumo": _resumo(cond, conta), "n_parcelas": cond["n_parcelas"],
                      "desconto_pct": cond["desconto_pct"], "mensal": round(_mensal(cond, conta), 2)})
    return saida


def _validas(caso: dict, regras: dict | None, versao, agora) -> list:
    """Todas as condições que o Auditor aceitaria, com as contas do simulador."""
    divida = float((caso.get("dados") or {}).get("divida") or 0)
    if not regras or divida <= 0:
        return []
    # A sugestão é para quem vai atender: confere só as regras da política, não a situação atual.
    caso_ok = {**caso, "situacao": "negociando", "dados": {**(caso.get("dados") or {}), "identidade_ok": True}}
    descontos = sorted({0.0, *[float(x) for x in range(5, int(regras["desconto_max_pct"]) + 1, 5)],
                        float(regras["desconto_max_pct"])})
    saida = []
    for n in [p for p in PARCELAS_CANDIDATAS if p <= int(regras["parcelas_max"])]:
        for desc in descontos:
            cond = oferta.condicoes({"desconto_pct": desc, "entrada_pct": 0 if n == 1 else regras["entrada_min_pct"],
                                     "n_parcelas": n, "juros_mensal_pct": 0})
            dec = auditor.auditar({"tipo": "propor_acordo", "params": cond}, caso_ok, regras, versao, agora)
            if dec["permitida"]:
                conta = oferta.calcular(divida, **cond)
                saida.append((cond, conta))
    return saida


def sugerir_proposta(caso: dict, regras: dict | None, versao=None, agora=None) -> dict | None:
    """A proposta que o atendente deve tentar primeiro (sempre dentro da política)."""
    d = caso.get("dados") or {}
    validas = _validas(caso, regras, versao, agora or datetime.now(timezone.utc))
    if not validas:
        return None
    valor = valor_dito(d)
    ja = {(t["n_parcelas"], t["desconto_pct"]) for t in tentado(d)}
    novas = [v for v in validas if (v[0]["n_parcelas"], v[0]["desconto_pct"]) not in ja] or validas

    def item(cond, conta, motivo, cabe):
        return {"resumo": _resumo(cond, conta), "n_parcelas": cond["n_parcelas"], "desconto_pct": cond["desconto_pct"],
                "entrada_pct": cond["entrada_pct"], "mensal": round(_mensal(cond, conta), 2),
                "valor_negociado": round(conta["valor_negociado"], 2), "motivo": motivo, "cabe": cabe}

    if valor:
        def cabe(v):                    # a parcela e a entrada cabem no que a pessoa disse
            return _mensal(*v) <= valor + 0.005 and float(v[1].get("entrada") or 0) <= valor + 0.005

        def mais_recupera(lista):       # a que mais recupera; empate: menos parcelas
            return max(lista, key=lambda v: (round(v[1]["valor_negociado"], 2), -v[0]["n_parcelas"]))
        cabem = [v for v in validas if cabe(v)]
        cabem_novas = [v for v in cabem if (v[0]["n_parcelas"], v[0]["desconto_pct"]) not in ja]
        if cabem_novas:
            cond, conta = mais_recupera(cabem_novas)
            return item(cond, conta, f"cabe nos {_brl(valor)} que a pessoa disse e é a que mais recupera", True)
        if cabem:
            cond, conta = mais_recupera(cabem)
            return item(cond, conta, f"cabe nos {_brl(valor)} que a pessoa disse, mas já foi oferecida", True)
        cond, conta = min(validas, key=lambda v: (_mensal(*v), -v[1]["valor_negociado"]))
        return item(cond, conta, f"nada cabe em {_brl(valor)}; esta é a menor parcela permitida", False)
    # Sem valor dito: o próximo degrau depois da última oferta (mais parcelas, mesmo desconto ou o menor acima).
    ultimo = tentado(d)[-1] if tentado(d) else None
    if ultimo:
        acima = [v for v in novas if v[0]["n_parcelas"] > ultimo["n_parcelas"] and v[0]["desconto_pct"] >= ultimo["desconto_pct"]]
        if acima:
            cond, conta = min(acima, key=lambda v: (v[0]["n_parcelas"], v[0]["desconto_pct"]))
            return item(cond, conta, "próximo degrau depois da última oferta (mais parcelas)", None)
    cond, conta = sorted(novas, key=lambda v: (v[0]["desconto_pct"], v[0]["n_parcelas"]))[len(novas) // 3]
    return item(cond, conta, "ponto de partida equilibrado (ainda sem valor dito pela pessoa)", None)


# ── prioridade da fila ───────────────────────────────────────────────────────

def prioridade(ficha: dict, agora: datetime | None = None) -> int:
    p = PESO_EMOCAO.get(ficha.get("emocao"), 0) + PESO_URGENCIA.get(ficha.get("urgencia"), 0)
    if ficha.get("motivo") == "dificuldade_grave":
        p += 30
    if (ficha.get("sugestao") or {}).get("cabe"):
        p += 10
    try:
        horas = ((agora or datetime.now(timezone.utc)) - datetime.fromisoformat(str(ficha.get("quando")))).total_seconds() / 3600
        p += max(0, min(20, int(horas)))
    except (TypeError, ValueError):
        pass
    return max(0, min(100, p))


def nivel(p: int) -> str:
    return "urgente" if p >= 60 else "alta" if p >= 35 else "normal"


# ── a ficha ──────────────────────────────────────────────────────────────────

def _leitura_da_triagem(caso: dict) -> tuple:
    """Emoção e urgência da última anotação da Triagem no caderno (reserva sem IA)."""
    for n in reversed((caso.get("dados") or {}).get("caderno") or []):
        if n.get("agente") == "triagem":
            m = n.get("motivo") or ""
            emo = next((e for e in EMOCOES if e in m), "calmo")
            return emo, "alta" if "urgência alta" in m else "baixa"
    return "calmo", "baixa"


def montar_ficha(caso: dict, motivo: str, ia: dict | None, regras: dict | None, versao=None,
                 agora: datetime | None = None, leitura: dict | None = None) -> dict:
    """A ficha da passagem. `ia` é o que o Supervisor devolveu (ou None); `leitura`
    é a Triagem da mensagem atual (reserva para emoção e urgência)."""
    agora = agora or datetime.now(timezone.utc)
    d = caso.get("dados") or {}
    emo_t, urg_t = _leitura_da_triagem(caso)
    if leitura:
        emo_t = leitura.get("emocao") if leitura.get("emocao") in EMOCOES else emo_t
        urg_t = leitura.get("urgencia") if leitura.get("urgencia") in URGENCIAS else urg_t
    ia = ia or {}
    ficha = {
        "quando": agora.isoformat(), "motivo": motivo,
        "situacao": guardrails.limpar_nota(str(ia.get("situacao") or ""), 200),
        "o_que_quer": guardrails.limpar_nota(str(ia.get("o_que_quer") or ""), 200),
        "proximo_passo": guardrails.limpar_nota(str(ia.get("proximo_passo") or ""), 200),
        "emocao": ia.get("emocao") if ia.get("emocao") in EMOCOES else emo_t,
        "urgencia": ia.get("urgencia") if ia.get("urgencia") in URGENCIAS else urg_t,
        "valor_dito": valor_dito(d),
        "tentado": tentado(d),
        "sugestao": sugerir_proposta(caso, regras, versao, agora),
        "origem": "ia" if ia else "codigo",
    }
    ficha["prioridade"] = prioridade(ficha, agora)
    ficha["nivel"] = nivel(ficha["prioridade"])
    return ficha


def guardar(caso: dict, ficha: dict) -> None:
    d = caso.setdefault("dados", {})
    d["passagem"] = ficha
    d["passagens"] = ((d.get("passagens") or []) + [ficha])[-MAX_PASSAGENS:]


def texto_para_agenda(ficha: dict, resumo_ia: str) -> str:
    """Observação da agenda: o resumo e, em código, o que já foi oferecido e a sugestão."""
    partes = [resumo_ia]
    if ficha.get("valor_dito"):
        partes.append(f"Disse que consegue: {_brl(ficha['valor_dito'])}")
    if ficha.get("tentado"):
        partes.append("Já oferecido: " + "; ".join(t["resumo"] for t in ficha["tentado"][-3:]))
    if ficha.get("sugestao"):
        partes.append(f"Sugestão: {ficha['sugestao']['resumo']} ({ficha['sugestao']['motivo']})")
    return " | ".join(p for p in partes if p)


def para_tela(ficha: dict | None, agora: datetime | None = None) -> dict | None:
    """Ficha com a prioridade recalculada (a espera aumenta com o tempo)."""
    if not ficha:
        return None
    f = dict(ficha)
    f["prioridade"] = prioridade(f, agora)
    f["nivel"] = nivel(f["prioridade"])
    return f


# ── retorno do atendente ────────────────────────────────────────────────────

def registrar_retorno(caso: dict, ajudou: bool, quem: str | None, comentario: str = "",
                      agora: datetime | None = None) -> dict:
    d = caso.setdefault("dados", {})
    ficha = d.get("passagem")
    if not ficha:
        raise LookupError("Este caso não tem passagem para a equipe.")
    retorno = {"ajudou": bool(ajudou), "por": quem, "quando": (agora or datetime.now(timezone.utc)).isoformat(),
               "comentario": guardrails.limpar_nota(comentario or "", 200)}
    ficha["retorno"] = retorno
    for p in reversed(d.get("passagens") or []):
        if p.get("quando") == ficha.get("quando"):
            p["retorno"] = retorno
            break
    return retorno


# ── o que as passagens dizem ────────────────────────────────────────────────

FAIXAS = ((0, 200, "até R$ 200"), (200, 300, "R$ 200 a 300"), (300, 500, "R$ 300 a 500"),
          (500, 1000, "R$ 500 a 1.000"), (1000, 10 ** 12, "acima de R$ 1.000"))


def sinais_da_equipe(casos: list, agora: datetime | None = None, dias: int = 7) -> dict:
    """Contagens em código das passagens recentes. Sinal para experimento, não prova."""
    agora = agora or datetime.now(timezone.utc)
    desde = agora - timedelta(days=dias)
    ps = []
    for c in casos:
        for p in (c.get("dados") or {}).get("passagens") or []:
            try:
                if datetime.fromisoformat(str(p.get("quando"))) >= desde:
                    ps.append(p)
            except (TypeError, ValueError):
                continue

    def contar(chave, opcoes=None):
        out = {}
        for p in ps:
            v = p.get(chave) or "—"
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))
    valores = [float(p["valor_dito"]) for p in ps if p.get("valor_dito")]
    nao_coube = [p for p in ps if p.get("valor_dito") and (p.get("sugestao") or {}).get("cabe") is False]
    retornos = [p["retorno"]["ajudou"] for p in ps if isinstance(p.get("retorno"), dict)]
    faixas = {nome: sum(1 for v in valores if ini < v <= fim or (ini == 0 and v <= fim)) for ini, fim, nome in FAIXAS}
    return {
        "dias": dias, "passagens": len(ps),
        "por_motivo": contar("motivo"), "por_emocao": contar("emocao"), "por_nivel": contar("nivel"),
        "com_valor_dito": len(valores),
        "valor_dito_por_faixa": {k: v for k, v in faixas.items() if v},
        "valor_dito_mediana": round(median(valores), 2) if valores else None,
        "nao_coube": len(nao_coube),
        "valor_pedido_quando_nao_coube": round(median([float(p["valor_dito"]) for p in nao_coube]), 2) if nao_coube else None,
        "menor_parcela_possivel": round(min((p["sugestao"]["mensal"] for p in nao_coube), default=0), 2) or None,
        "retornos": len(retornos), "resumo_ajudou": sum(retornos),
        "nota_supervisor": round(sum(retornos) / len(retornos), 4) if retornos else None,
    }
