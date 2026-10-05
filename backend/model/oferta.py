"""Ofertas da empresa: catálogo editável, contas e alçada (docs/PLANO_OFERTAS.md).

Uma conta só para o catálogo, as propostas da ficha e o simulador:

    valor negociado = dívida × (1 − desconto)
    entrada         = valor negociado × entrada%
    parcela         = tabela Price sobre o saldo (negociado − entrada) com os
                      juros do mês; sem juros, saldo ÷ parcelas
    total pago      = entrada + parcela × parcelas

Cada oferta pertence a uma FAMÍLIA do bandit (as 4 ofertas que ele aprende),
escolhida pela forma da oferta — assim uma oferta nova herda a chance de pagar
aprendida da mais parecida e ensina essa família.
"""
import re

MAX_OFERTAS = 20
LIMITE_DESCONTO_AVISTA_10 = 15.0     # até 15% à vista → família "avista_10pct"
LIMITE_PARCELAS_CURTO = 6            # até 6x → família "parcelado_4x"

LIMITES = {                          # campo: (mínimo, máximo)
    "desconto_pct": (0.0, 95.0),
    "entrada_pct": (0.0, 90.0),
    "n_parcelas": (1, 120),
    "juros_mensal_pct": (0.0, 20.0),
}


def familia(n_parcelas: int, desconto_pct: float) -> str:
    if int(n_parcelas) <= 1:
        return "avista_10pct" if float(desconto_pct) <= LIMITE_DESCONTO_AVISTA_10 else "desconto_30pct"
    return "parcelado_4x" if int(n_parcelas) <= LIMITE_PARCELAS_CURTO else "parcelado_12x"


def parcela_price(saldo: float, n: int, juros_mensal_pct: float) -> float:
    i = float(juros_mensal_pct) / 100
    if n <= 0:
        return 0.0
    if i <= 0:
        return saldo / n
    return saldo * i / (1 - (1 + i) ** -n)


def calcular(divida: float, desconto_pct: float = 0.0, entrada_pct: float = 0.0,
             n_parcelas: int = 1, juros_mensal_pct: float = 0.0) -> dict:
    divida = max(0.0, float(divida or 0))
    n = max(1, int(n_parcelas))
    negociado = divida * (1 - float(desconto_pct) / 100)
    if n == 1:
        # À vista: um pagamento só. Entrada e juros não se aplicam.
        entrada, saldo, parcela, total = 0.0, negociado, negociado, negociado
    else:
        entrada = negociado * float(entrada_pct) / 100
        saldo = negociado - entrada
        parcela = parcela_price(saldo, n, juros_mensal_pct)
        total = entrada + parcela * n
    return {
        "valor_negociado": round(negociado, 2),
        "entrada": round(entrada, 2),
        "saldo": round(saldo, 2),
        "parcela": round(parcela, 2),
        "total_pago": round(total, 2),
        "juros_total": round(max(0.0, total - negociado), 2),
        "economia": round(max(0.0, divida - total), 2),
    }


def _num(v, campo):
    if isinstance(v, bool) or v is None or v == "":
        raise ValueError(f"{campo}: informe um número")
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise ValueError(f"{campo}: informe um número")
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError(f"{campo}: informe um número")
    return x


_ROTULO = {"desconto_pct": "Desconto", "entrada_pct": "Entrada", "n_parcelas": "Parcelas",
           "juros_mensal_pct": "Juros ao mês"}


def condicoes(bruto: dict) -> dict:
    """Desconto, entrada, parcelas e juros limpos e dentro dos limites."""
    saida = {}
    for campo, (lo, hi) in LIMITES.items():
        v = bruto.get(campo, 0 if campo != "n_parcelas" else 1)
        x = _num(v if v not in (None, "") else (1 if campo == "n_parcelas" else 0), _ROTULO[campo])
        if campo == "n_parcelas":
            if x != int(x):
                raise ValueError("Parcelas: informe um número inteiro")
            x = int(x)
        if not lo <= x <= hi:
            raise ValueError(f"{_ROTULO[campo]}: de {lo:g} a {hi:g}")
        saida[campo] = x
    if saida["n_parcelas"] == 1:
        saida["entrada_pct"] = 0.0
        saida["juros_mensal_pct"] = 0.0
    return saida


def _slug(nome: str) -> str:
    import unicodedata
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return s[:40] or "oferta"


def validar_catalogo(itens) -> list:
    if not isinstance(itens, list) or not itens:
        raise ValueError("Cadastre pelo menos uma oferta.")
    if len(itens) > MAX_OFERTAS:
        raise ValueError(f"No máximo {MAX_OFERTAS} ofertas.")
    saida, ids = [], set()
    for k, it in enumerate(itens, start=1):
        if not isinstance(it, dict):
            raise ValueError(f"Oferta {k}: formato inválido")
        nome = str(it.get("nome") or "").strip()
        if not 2 <= len(nome) <= 60:
            raise ValueError(f"Oferta {k}: o nome precisa ter de 2 a 60 caracteres")
        try:
            c = condicoes(it)
        except ValueError as e:
            raise ValueError(f"{nome}: {e}")
        oid = str(it.get("id") or "").strip()[:60] or _slug(nome)
        base, n = oid, 2
        while oid in ids:
            oid, n = f"{base}-{n}", n + 1
        ids.add(oid)
        saida.append({"id": oid, "nome": nome, "descricao": str(it.get("descricao") or "").strip()[:160],
                      **c, "ativa": bool(it.get("ativa", True)),
                      "familia": familia(c["n_parcelas"], c["desconto_pct"])})
    if not any(o["ativa"] for o in saida):
        raise ValueError("Deixe pelo menos uma oferta ativa.")
    return saida


CAMPOS_ALCADA = {
    "desconto_max_pct": ("Desconto máximo", 0.0, 95.0),
    "parcelas_max": ("Parcelas máximas", 1, 120),
    "parcela_min": ("Parcela mínima (R$)", 0.0, 1_000_000.0),
    "juros_min_pct": ("Juros mínimos ao mês", 0.0, 20.0),
}


def validar_alcada(bruto) -> dict:
    """Limites do operador no simulador. Campo vazio = sem limite."""
    bruto = bruto or {}
    saida = {}
    for campo, (rot, lo, hi) in CAMPOS_ALCADA.items():
        v = bruto.get(campo)
        if v in (None, ""):
            continue
        x = _num(v, rot)
        if campo == "parcelas_max":
            if x != int(x):
                raise ValueError(f"{rot}: informe um número inteiro")
            x = int(x)
        if not lo <= x <= hi:
            raise ValueError(f"{rot}: de {lo:g} a {hi:g}")
        saida[campo] = x
    return saida


def fora_da_alcada(cond: dict, conta: dict, alcada: dict) -> list:
    """Motivos (em texto) pelos quais a oferta passa dos limites do operador."""
    motivos = []
    a = alcada or {}
    if "desconto_max_pct" in a and cond["desconto_pct"] > a["desconto_max_pct"]:
        motivos.append(f"Desconto acima do máximo de {a['desconto_max_pct']:g}%.")
    if "parcelas_max" in a and cond["n_parcelas"] > a["parcelas_max"]:
        motivos.append(f"Mais parcelas que o máximo de {a['parcelas_max']}.")
    if "parcela_min" in a and cond["n_parcelas"] > 1 and conta["parcela"] < a["parcela_min"]:
        motivos.append(f"Parcela abaixo do mínimo de R$ {a['parcela_min']:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    if "juros_min_pct" in a and cond["n_parcelas"] > 1 and cond["juros_mensal_pct"] < a["juros_min_pct"]:
        motivos.append(f"Juros abaixo do mínimo de {a['juros_min_pct']:g}% ao mês.")
    return motivos


def catalogo_padrao() -> list:
    """As 4 ofertas de sempre, no formato do catálogo."""
    from model.proposta import ARQUETIPOS_PADRAO
    return validar_catalogo([{"id": a["oferta"], "nome": a["rotulo"], "desconto_pct": a["desconto_pct"],
                              "n_parcelas": a["n_parcelas"], "entrada_pct": 0, "juros_mensal_pct": 0,
                              "ativa": True} for a in ARQUETIPOS_PADRAO])


def catalogo_da_empresa(extra: dict) -> tuple:
    """(catálogo, é_padrão). Catálogo gravado inválido cai no padrão."""
    bruto = (extra or {}).get("catalogo_ofertas")
    if bruto:
        try:
            return validar_catalogo(bruto), False
        except ValueError:
            pass
    return catalogo_padrao(), True


def alcada_da_empresa(extra: dict) -> dict:
    try:
        return validar_alcada((extra or {}).get("alcada_oferta"))
    except ValueError:
        return {}


def para_arquetipos(catalogo: list) -> list:
    """Ofertas ativas no formato que montar_propostas consome."""
    return [{"id": o["id"], "rotulo": o["nome"], "desconto_pct": o["desconto_pct"], "n_parcelas": o["n_parcelas"],
             "entrada_pct": o["entrada_pct"], "juros_mensal_pct": o["juros_mensal_pct"], "oferta": o["familia"]}
            for o in catalogo if o["ativa"]]
