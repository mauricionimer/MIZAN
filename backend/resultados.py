"""A1 — painel de resultados do admin (docs/PLANO_ADMIN.md).

Cruza o que foi registrado em Pagamentos. Duas naturezas de corte:

- COM taxa de pagamento (pagou ÷ registros): canal de cobrança e fase de atraso.
  Os dois existem tanto no "pagou" quanto no "não pagou".
- SÓ composição do que entrou: à vista × parcelado, faixa de desconto e forma de
  pagamento. Essas condições só são registradas quando o devedor paga; uma
  "taxa" aqui daria 100% em tudo e enganaria.

O que veio sem a informação fica em "Não informado" — nunca é redistribuído.
"""
AMOSTRA_MINIMA = 30          # abaixo disso o grupo leva o selo "amostra pequena"

NAO_INFORMADO = "nao_informado"

FAIXAS_DESCONTO = (          # (chave, rótulo, limite superior inclusivo)
    ("sem_desconto", "Sem desconto", 0.0),
    ("ate_10", "Até 10%", 10.0),
    ("10_20", "10% a 20%", 20.0),
    ("20_30", "20% a 30%", 30.0),
    ("acima_30", "Acima de 30%", 100.0),
)

ORDEM_FASE = ("0-30 dias", "31-60 dias", "61-90 dias", "91-180 dias", "181+ dias")


def faixa_desconto(pct) -> str:
    if pct is None:
        return NAO_INFORMADO
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return NAO_INFORMADO
    for chave, _, teto in FAIXAS_DESCONTO:
        if v <= teto:
            return chave
    return FAIXAS_DESCONTO[-1][0]


def modalidade(parcelas) -> str:
    try:
        n = int(parcelas)
    except (TypeError, ValueError):
        return NAO_INFORMADO
    return "parcelado" if n > 1 else "a_vista"


def _grupo_vazio(chave: str) -> dict:
    return {"chave": chave, "registros": 0, "pagos": 0, "recuperado": 0.0}


def _fechar(g: dict, com_taxa: bool) -> dict:
    g["recuperado"] = round(g["recuperado"], 2)
    g["ticket_medio"] = round(g["recuperado"] / g["pagos"], 2) if g["pagos"] else None
    base = g["registros"] if com_taxa else g["pagos"]
    g["amostra_pequena"] = base < AMOSTRA_MINIMA
    if com_taxa:
        g["taxa_pagamento"] = round(g["pagos"] / g["registros"], 4) if g["registros"] else None
    else:
        g.pop("registros")
    return g


def agrupar(feedbacks: list, chave_de, com_taxa: bool, ordem: "tuple | None" = None) -> list:
    """Um grupo por valor de `chave_de(feedback)`.

    Com taxa: conta todos os registros. Sem taxa: só os pagos entram.
    """
    grupos: dict = {}
    for f in feedbacks:
        pagou = bool(f.get("pagou"))
        if not com_taxa and not pagou:
            continue
        k = chave_de(f) or NAO_INFORMADO
        g = grupos.setdefault(k, _grupo_vazio(k))
        g["registros"] += 1
        if pagou:
            g["pagos"] += 1
            g["recuperado"] += float(f.get("valor_recuperado") or 0)
    saida = [_fechar(g, com_taxa) for g in grupos.values()]
    if ordem:
        pos = {k: i for i, k in enumerate(ordem)}
        saida.sort(key=lambda g: (g["chave"] == NAO_INFORMADO, pos.get(g["chave"], len(pos)), g["chave"]))
    else:
        saida.sort(key=lambda g: (g["chave"] == NAO_INFORMADO, -g["pagos"], g["chave"]))
    return saida


def melhor(grupos: list) -> "dict | None":
    """Grupo de maior taxa entre os informados com amostra suficiente."""
    validos = [g for g in grupos if g["chave"] != NAO_INFORMADO and not g["amostra_pequena"]
               and g.get("taxa_pagamento") is not None]
    return max(validos, key=lambda g: (g["taxa_pagamento"], g["registros"])) if validos else None


def contatos_por_canal(contatos: list) -> list:
    grupos: dict = {}
    for c in contatos:
        k = c.get("canal") or NAO_INFORMADO
        g = grupos.setdefault(k, {"chave": k, "contatos": 0, "efetivos": 0, "promessas": 0})
        g["contatos"] += 1
        r = c.get("resultado")
        if r and r != "sem_resposta":
            g["efetivos"] += 1
        if r == "prometeu_pagar":
            g["promessas"] += 1
    saida = []
    for g in grupos.values():
        n = g["contatos"]
        g["taxa_efetivo"] = round(g["efetivos"] / n, 4) if n else None
        g["taxa_promessa"] = round(g["promessas"] / n, 4) if n else None
        g["amostra_pequena"] = n < AMOSTRA_MINIMA
        saida.append(g)
    saida.sort(key=lambda g: (g["chave"] == NAO_INFORMADO, -g["contatos"]))
    return saida


def totais(feedbacks: list) -> dict:
    n = len(feedbacks)
    pagos = [f for f in feedbacks if f.get("pagou")]
    rec = round(sum(float(f.get("valor_recuperado") or 0) for f in pagos), 2)
    return {"registros": n, "pagos": len(pagos), "taxa_pagamento": round(len(pagos) / n, 4) if n else None,
            "recuperado": rec, "ticket_medio": round(rec / len(pagos), 2) if pagos else None}
