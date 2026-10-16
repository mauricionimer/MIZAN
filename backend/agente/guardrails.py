"""Travas no texto que vai para o devedor (docs/PLANO_EXECUCAO_AGENTES.md, 8).

Conferido em código antes de enviar:
1. Valores: todo valor em reais, percentual e número de parcelas no texto
   precisa ter saído de uma ferramenta nesta conversa (simulação, caso, oferta).
2. Tom: nada de ameaça, constrangimento ou exposição ao ridículo — o Código de
   Defesa do Consumidor (art. 42) proíbe isso na cobrança. É uma primeira
   camada por palavras; a bateria de cenários mede o resto.
3. Segredos: nada de CPF, identificadores internos ou instruções do sistema.

Reprovou: uma nova tentativa; reprovou de novo, uma pessoa assume.
"""
import re
import unicodedata

TOLERANCIA = 0.01

_DINHEIRO = re.compile(r"R\$\s*([\d.]+(?:,\d{1,2})?)|\b(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})\b")
_PERCENTUAL = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_PARCELAS = re.compile(r"\b(\d{1,3})\s*(?:x\b|vezes\b|parcelas?\b|prestac)", re.I)

_TOM = [
    r"\bprocess(ar|o|aremos)\b", r"\bjustica\b", r"\bpolicia\b", r"\bpres[oa]\b", r"\bprisao\b", r"\bcadeia\b",
    r"\bcaloteir", r"\bvergonha\b", r"\bvizinh", r"\bempregador\b", r"\bpatrao\b", r"\bseu chefe\b",
    r"\bsua familia (vai|vao) saber", r"\bvai se arrepender", r"\bultima chance\b", r"\bpenhor", r"\bconfisc",
    r"\bsujar (o )?seu nome para sempre", r"\bmentiros", r"\birresponsavel\b",
]
_SEGREDO = [
    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",              # CPF
    r"simulacao_id|compromisso_id|trace_id|predicao_id",
    r"system prompt|prompt do sistema|minhas instrucoes|ferramenta [a-z_]+\(",
    r"desconto maximo|alcada|politica interna",
]


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _num_br(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def valores_do_texto(texto: str) -> dict:
    dinheiro = [_num_br(a or b) for a, b in _DINHEIRO.findall(texto)]
    percentuais = [float(p.replace(",", ".")) for p in _PERCENTUAL.findall(texto)]
    parcelas = [int(n) for n in _PARCELAS.findall(texto)]
    return {"dinheiro": dinheiro, "percentuais": percentuais, "parcelas": parcelas}


def permitidos_de(resultados: list) -> dict:
    """Valores que as ferramentas devolveram nesta conversa."""
    dinheiro, percentuais, parcelas = set(), set(), {1}
    def andar(x, chave=""):
        if isinstance(x, dict):
            for k, v in x.items():
                andar(v, k)
        elif isinstance(x, list):
            for v in x:
                andar(v, chave)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            if chave.endswith("_pct"):
                percentuais.add(round(float(x), 2))
            elif chave == "n_parcelas":
                parcelas.add(int(x))
            else:
                dinheiro.add(round(float(x), 2))
        elif isinstance(x, str) and chave == "resumo":
            v = valores_do_texto(x)
            dinheiro.update(round(d, 2) for d in v["dinheiro"])
            percentuais.update(round(p, 2) for p in v["percentuais"])
            parcelas.update(v["parcelas"])
    andar(resultados)
    return {"dinheiro": dinheiro, "percentuais": percentuais, "parcelas": parcelas}


def conferir(texto: str, permitidos: dict) -> list:
    """Motivos de reprovação (lista vazia = pode enviar)."""
    motivos = []
    v = valores_do_texto(texto)
    for d in v["dinheiro"]:
        if not any(abs(d - p) <= TOLERANCIA for p in permitidos["dinheiro"]):
            motivos.append(f"valor R$ {d:.2f} não veio de uma simulação ou do caso")
    for p in v["percentuais"]:
        if round(p, 2) not in permitidos["percentuais"]:
            motivos.append(f"percentual {p:g}% não veio de uma simulação")
    for n in v["parcelas"]:
        if n not in permitidos["parcelas"]:
            motivos.append(f"{n} parcelas não veio de uma simulação")
    t = _norm(texto)
    if any(re.search(p, t) for p in _TOM):
        motivos.append("tom de ameaça ou constrangimento")
    if any(re.search(p, t) for p in _SEGREDO):
        motivos.append("dado interno ou pessoal no texto")
    if not texto.strip():
        motivos.append("resposta vazia")
    if len(texto) > 1200:
        motivos.append("resposta longa demais")
    return motivos
