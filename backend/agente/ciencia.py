"""Ferramentas estatísticas do Cientista (docs/PLANO_AGENTES_IA.md, etapa 6).

Toda conta é feita aqui, em código, e o selo de evidência também. A IA só lê os
resultados e escreve o relatório; ela não calcula nem decide se há evidência.

Cada observação é um caso do agente:
  {"grupo": "agente" | "sorteado", "pagou": bool, "recuperado": float, "divida": float,
   "chance": float | None, "dias": int, "produto": str, "quebrou": bool}

"agente": casos que o agente procurou. "sorteado": grupo de comparação, que o
Estrategista sorteia e não procura. Como o sorteio é de verdade, a diferença
entre os dois mede o efeito do agente, se os grupos forem comparáveis.
"""
import math
import random

N_MINIMO = 30              # por grupo, para qualquer conclusão
SMD_COMPARAVEL = 0.1       # diferença padronizada aceita mesmo em amostra grande
Z95 = 1.959964
FAIXAS_ATRASO = ((1, 90, "até 90 dias"), (91, 180, "91 a 180 dias"), (181, 360, "181 a 360 dias"),
                 (361, 10 ** 6, "mais de 360 dias"))

SEM_EVIDENCIA, INDICIO, EVIDENCIA = "sem evidência", "indício", "evidência"


def wilson(k: int, n: int) -> tuple:
    """Taxa e intervalo de 95% de Wilson."""
    if n == 0:
        return (None, None, None)
    p = k / n
    den = 1 + Z95 ** 2 / n
    centro = (p + Z95 ** 2 / (2 * n)) / den
    meia = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n)) / den
    return (p, max(0.0, centro - meia), min(1.0, centro + meia))


def diferenca_taxas(k1: int, n1: int, k2: int, n2: int) -> tuple:
    """Diferença p1 - p2 com intervalo de 95% de Newcombe (híbrido de Wilson)."""
    if not n1 or not n2:
        return (None, None, None)
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return (d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def _razao(obs: list) -> float | None:
    divida = sum(o["divida"] for o in obs)
    return sum(o["recuperado"] for o in obs) / divida if divida else None


def bootstrap_razao(a: list, s: list, n_rep: int = 2000, semente: int = 7) -> tuple:
    """R$ recebido por R$ de dívida: diferença agente - sorteado, intervalo de 95% por bootstrap."""
    if not a or not s or _razao(a) is None or _razao(s) is None:
        return (None, None, None)
    rnd = random.Random(semente)            # semente fixa: o mesmo dado dá o mesmo intervalo
    difs = []
    for _ in range(n_rep):
        ra = _razao([rnd.choice(a) for _ in a])
        rs = _razao([rnd.choice(s) for _ in s])
        if ra is not None and rs is not None:
            difs.append(ra - rs)
    difs.sort()
    return (_razao(a) - _razao(s), difs[int(0.025 * len(difs))], difs[int(0.975 * len(difs)) - 1])


def _media_dp(v: list) -> tuple:
    if not v:
        return (None, None)
    m = sum(v) / len(v)
    return (m, math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else 0.0)


def composicao(obs: list) -> dict:
    """Os grupos são parecidos? Diferença padronizada (SMD) de chance, valor e atraso."""
    a = [o for o in obs if o["grupo"] == "agente"]
    s = [o for o in obs if o["grupo"] == "sorteado"]
    campos = {}
    for campo in ("chance", "divida", "dias"):
        va = [float(o[campo]) for o in a if o.get(campo) is not None]
        vs = [float(o[campo]) for o in s if o.get(campo) is not None]
        (ma, da), (ms, ds) = _media_dp(va), _media_dp(vs)
        if ma is None or ms is None:
            campos[campo] = {"agente": ma, "sorteado": ms, "smd": None}
            continue
        dp = math.sqrt((da ** 2 + ds ** 2) / 2)
        campos[campo] = {"agente": round(ma, 4), "sorteado": round(ms, 4),
                         # sem variação nos grupos: iguais = 0; diferentes = não comparáveis
                         "smd": round(abs(ma - ms) / dp, 3) if dp else (0.0 if ma == ms else 99.0)}
    # O sorteio sozinho já cria alguma diferença. Só é "não comparável" a diferença
    # maior que 0,1 e maior do que o acaso explicaria (1,96·√(1/nA + 1/nS)).
    limite = round(max(SMD_COMPARAVEL, Z95 * math.sqrt(1 / len(a) + 1 / len(s))) if a and s else SMD_COMPARAVEL, 3)
    comparavel = bool(a and s) and all(c["smd"] is not None and c["smd"] <= limite for c in campos.values())
    return {"campos": campos, "comparaveis": comparavel, "limite_smd": limite}


MELHOR, PIOR, INCERTO = "melhor", "pior", "incerto"


def direcao(n_agente: int, n_sorteado: int, inf, sup) -> str:
    """Para que lado o agente está: intervalo todo acima de zero, todo abaixo ou cruzando."""
    if n_agente < N_MINIMO or n_sorteado < N_MINIMO or inf is None or sup is None:
        return INCERTO
    return MELHOR if inf > 0 else PIOR if sup < 0 else INCERTO


def selo(n_agente: int, n_sorteado: int, inf, sup, comparaveis: bool) -> str:
    """Decidido aqui, nunca pela IA. Selo é só de melhora: agente pior não ganha
    'evidência' (isso mandaria manter a abordagem); o lado fica em `direcao`."""
    if direcao(n_agente, n_sorteado, inf, sup) != MELHOR:
        return SEM_EVIDENCIA
    return EVIDENCIA if comparaveis else INDICIO


def comparar_grupos(obs: list) -> dict:
    """Agente vs. sorteado: taxa de pagamento, R$/R$ e quebra, com intervalos e selo."""
    a = [o for o in obs if o["grupo"] == "agente"]
    s = [o for o in obs if o["grupo"] == "sorteado"]
    ka, ks = sum(o["pagou"] for o in a), sum(o["pagou"] for o in s)
    comp = composicao(obs)
    d, inf, sup = diferenca_taxas(ka, len(a), ks, len(s))
    r, rinf, rsup = bootstrap_razao(a, s)
    acordos = [o for o in a if o.get("teve_acordo")]
    return {
        "n": {"agente": len(a), "sorteado": len(s)},
        "taxa_pagamento": {"agente": _r(wilson(ka, len(a))[0]), "sorteado": _r(wilson(ks, len(s))[0]),
                           "diferenca": _r(d), "ic95": [_r(inf), _r(sup)],
                           "selo": selo(len(a), len(s), inf, sup, comp["comparaveis"]),
                           "direcao": direcao(len(a), len(s), inf, sup)},
        "recuperado_por_real": {"agente": _r(_razao(a)), "sorteado": _r(_razao(s)), "diferenca": _r(r),
                                "ic95": [_r(rinf), _r(rsup)],
                                "selo": selo(len(a), len(s), rinf, rsup, comp["comparaveis"]),
                                "direcao": direcao(len(a), len(s), rinf, rsup)},
        "quebra_de_acordo": {"acordos": len(acordos),
                             "taxa": _r(sum(o["quebrou"] for o in acordos) / len(acordos)) if acordos else None},
        "composicao": comp,
    }


def _faixa(dias) -> str:
    d = int(dias or 0)
    if d <= 0:
        return "sem atraso"                    # ainda não venceu (dias zero ou negativos)
    for ini, fim, nome in FAIXAS_ATRASO:
        if ini <= d <= fim:
            return nome
    return FAIXAS_ATRASO[-1][2]


def segmentos(obs: list) -> list:
    """A mesma comparação por produto e por faixa de atraso, só com n mínimo nos dois grupos.

    Selo no máximo "indício": com vários segmentos olhados ao mesmo tempo, algum
    sai diferente por acaso; só a comparação geral pode dar "evidência"."""
    saida = []
    for nome, chave in (("produto", lambda o: o.get("produto") or "não informado"), ("atraso", lambda o: _faixa(o["dias"]))):
        grupos: dict = {}
        for o in obs:
            grupos.setdefault(chave(o), []).append(o)
        for valor, lista in sorted(grupos.items()):
            na = sum(o["grupo"] == "agente" for o in lista)
            ns = len(lista) - na
            if na < N_MINIMO or ns < N_MINIMO:
                continue
            c = comparar_grupos(lista)
            taxa = dict(c["taxa_pagamento"])
            if taxa["selo"] == EVIDENCIA:
                taxa["selo"] = INDICIO
            saida.append({"segmento": f"{nome}: {valor}", "n": c["n"], "taxa_pagamento": taxa})
    return saida


def bandit(stats: list) -> list:
    """Resumo do que o bandit aprendeu (model.bandit.convergencia_stats)."""
    return [{"acao": s.get("label") or s.get("acao_id"), "tentativas": s.get("n_tentativas"),
             "recompensa_media": s.get("recompensa_media"), "convergido": s.get("convergido")}
            for s in stats or [] if s.get("n_tentativas")]


def analisar(obs: list, stats_bandit: list | None = None) -> dict:
    return {"comparacao": comparar_grupos(obs), "segmentos": segmentos(obs), "bandit": bandit(stats_bandit),
            "n_minimo_por_grupo": N_MINIMO}


def _r(x, casas=4):
    return None if x is None else round(float(x), casas)
