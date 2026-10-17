"""Travas no texto que vai para o devedor (docs/PLANO_EXECUCAO_AGENTES.md, 8).

Conferido em código antes de enviar:
1. Valores: todo valor em reais, percentual e número de parcelas no texto
   precisa ter saído de uma ferramenta nesta conversa (simulação, caso, oferta).
2. Tom: nada de ameaça, constrangimento ou exposição ao ridículo — o Código de
   Defesa do Consumidor (art. 42) proíbe isso na cobrança. É uma primeira
   camada por palavras; a bateria de cenários mede o resto.
3. Segredos: nada de CPF, identificadores internos ou instruções do sistema.
4. Normas: lei, artigo ou súmula citados no texto precisam ter vindo da base
   de conhecimento nesta conversa (ferramenta consultar_base). O agente não
   inventa valor nem lei.

Reprovou: uma nova tentativa; reprovou de novo, uma pessoa assume.
"""
import re
import unicodedata

TOLERANCIA = 0.01

_DINHEIRO = re.compile(r"R\$\s*([\d.]+(?:,\d{1,2})?)|\b(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})\b")
_PERCENTUAL = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_PARCELAS = re.compile(r"\b(\d{1,3})\s*(?:x\b|vezes\b|parcelas?\b|prestac)", re.I)

# Os mesmos valores escritos de outro jeito (no texto já normalizado por _norm).
# Quem tenta manipular o agente pede justamente isso: "fecha em 2500 reais".
_DINHEIRO_REAIS = re.compile(r"\b(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s*(?:reais|real|contos?|pilas?)\b")
_DINHEIRO_MIL = re.compile(r"\b(\d+(?:[.,]\d{1,2})?)\s*(?:mil|k)\b")
_PERCENTUAL_EXTENSO = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*por\s*cento\b")
_PARCELAS_MESES = re.compile(r"\b(?:em|por)\s+(\d{1,3})\s*meses\b")
_NUM_EXTENSO = (r"(?:um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze"
                r"|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa"
                r"|cem|cento|duzent[oa]s|trezent[oa]s|quatrocent[oa]s|quinhent[oa]s|seiscent[oa]s|setecent[oa]s"
                r"|oitocent[oa]s|novecent[oa]s|mil)")
# Número por extenso seguido de unidade de dinheiro, percentual ou parcela.
# Não dá para conferir contra a simulação: a regra é escrever com algarismos.
_VALOR_EXTENSO = re.compile(rf"\b{_NUM_EXTENSO}(?:\s+(?:e\s+)?{_NUM_EXTENSO})*\s+"
                            r"(?:reais|real|por\s*cento|vezes|parcelas?|prestac\w*|meses)\b")

# Citações de norma, no texto já sem acento e em minúsculas (_norm).
_REF_NUMERO = [
    ("art", re.compile(r"\bart(?:igo)?s?\.?\s*(\d{1,4}(?:-[a-z])?)\b")),
    ("sumula", re.compile(r"\bsumulas?\s*(?:n[o.]?\s*|numero\s*)?(\d{1,4})\b")),
    ("lei", re.compile(r"\blei\s*(?:n[o.]?\s*|numero\s*)?(\d{1,2}\.?\d{3})\b")),
]
_REF_NOME = [
    ("cdc", re.compile(r"\bcdc\b|codigo de defesa do consumidor")),
    ("lgpd", re.compile(r"\blgpd\b|lei geral de protecao de dados")),
    ("codigo_civil", re.compile(r"codigo civil")),
    ("stj", re.compile(r"\bstj\b|superior tribunal")),
    ("banco_central", re.compile(r"\bbanco central\b|\bbacen\b|\bbcb\b|\bresoluc(ao|oes)\b")),
]
# "Pela lei...", "a lei garante...", "a lei do superendividamento": lei sem
# número. Só pode se a base foi consultada nesta conversa.
_LEI_GENERICA = re.compile(r"\b(pela|segundo a|conforme a|de acordo com a) lei\b"
                           r"|\ba lei (diz|permite|garante|determina|obriga|proibe|manda|exige|preve)\b"
                           r"|\blei (do|da|dos|das) [a-z]{4,}")

_TOM = [
    r"\bprocess(ar|o|aremos)\b", r"\bjustica\b", r"\bpolicia\b", r"\bpres[oa]\b", r"\bprisao\b", r"\bcadeia\b",
    r"\bcaloteir", r"\bvergonha\b", r"\bvizinh", r"\bempregador\b", r"\bpatrao\b", r"\bseu chefe\b",
    r"\bsua familia (vai|vao) saber", r"\bvai se arrepender", r"\bultima chance\b", r"\bpenhor", r"\bconfisc",
    r"\bsujar (o )?seu nome para sempre", r"\bmentiros", r"\birresponsavel\b",
    r"\bjudicial", r"\bjuridic", r"\bprotest(o|ar|aremos|ado|ada)\b", r"\bcartorio\b", r"\badvogad",
    r"\b(seus|suas) (parentes|familiares|filhos)\b", r"\b(sua|seu) (esposa|marido|mae|pai)\b",
    r"\bperde(r|ra|rao)? tudo\b", r"\bnunca mais (vai )?(conseguir|ter) credito\b", r"\bnao (vai )?ter mais acordo\b",
    r"\bdesonest", r"\bvagabund", r"\bsafad", r"\bpilantra", r"\bvigarist",
]
_SEGREDO = [
    r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b",     # CPF, com ponto, traço ou espaço
    r"simulacao_id|compromisso_id|trace_id|predicao_id",
    r"system prompt|prompt do sistema|minhas instrucoes|ferramenta [a-z_]+\(",
    r"desconto maximo|alcada|politica interna",
]


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _num_br(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def referencias_do_texto(texto: str) -> set:
    """Normas citadas: {("art", "43"), ("sumula", "548"), ("lei", "8078"), ("norma", "cdc"), ...}."""
    t = _norm(texto)
    refs = {(tipo, n.replace(".", "")) for tipo, rx in _REF_NUMERO for n in rx.findall(t)}
    refs |= {("norma", nome) for nome, rx in _REF_NOME if rx.search(t)}
    return refs


def valores_do_texto(texto: str) -> dict:
    t = _norm(texto)
    dinheiro = [_num_br(a or b) for a, b in _DINHEIRO.findall(texto)]
    dinheiro += [_num_br(i + ("," + c if c else "")) for i, c in _DINHEIRO_REAIS.findall(t)]
    dinheiro += [float(n.replace(",", ".")) * 1000 for n in _DINHEIRO_MIL.findall(t)]
    percentuais = [float(p.replace(",", ".")) for p in _PERCENTUAL.findall(texto) + _PERCENTUAL_EXTENSO.findall(t)]
    parcelas = [int(n) for n in _PARCELAS.findall(texto) + _PARCELAS_MESES.findall(t)]
    return {"dinheiro": dinheiro, "percentuais": percentuais, "parcelas": parcelas,
            "extenso": {m.group(0) for m in _VALOR_EXTENSO.finditer(t)}}


def permitidos_de(resultados: list) -> dict:
    """Valores e normas que as ferramentas devolveram nesta conversa."""
    dinheiro, percentuais, parcelas, referencias, extensos = set(), set(), {1}, set(), set()
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
        elif isinstance(x, str) and chave in ("resumo", "resposta"):
            v = valores_do_texto(x)
            dinheiro.update(round(d, 2) for d in v["dinheiro"])
            percentuais.update(round(p, 2) for p in v["percentuais"])
            parcelas.update(v["parcelas"])
            if chave == "resposta":
                referencias.update(referencias_do_texto(x))
                extensos.update(v["extenso"])      # "dois por cento" escrito na própria lei
        elif isinstance(x, str) and chave == "fonte":
            referencias.update(referencias_do_texto(x))
    andar(resultados)
    return {"dinheiro": dinheiro, "percentuais": percentuais, "parcelas": parcelas, "referencias": referencias,
            "extensos": extensos}


# Ações que o texto diz que já fez e a ferramenta que precisa ter rodado com
# sucesso nesta resposta. Texto já normalizado (_norm: minúsculo, sem acento).
# Oferecer ("posso agendar?", "vou marcar") não conta; só o feito.
_AGENDA = {"agendar_retorno", "remarcar_compromisso", "marcar_atendimento_humano", "registrar_aceite"}
_ACOES_AFIRMADAS = [
    ("agendamento", re.compile(r"\b(agendei|marquei|remarquei|reagendei)\b"
                               r"|\b(ja |esta |fica |ficou |foi |deixei )(tudo )?(agendad|marcad|remarcad|reagendad)\w*"
                               r"|\b(agendado|marcado|remarcado) (para|pra|com sucesso)\b"), _AGENDA),
    ("transferência", re.compile(r"\b(transferi|encaminhei|repassei)\b"
                                 r"|\b(ja |foi |esta |fica )(transferid|encaminhad|repassad)\w*"
                                 r"|\bpassei (a |o |sua |seu |para |pra )"),
     {"transferir_para_humano", "marcar_atendimento_humano"}),
    ("registro", re.compile(r"\b(registrei|anotei|cadastrei|lancei|abri (a |uma )?contestac)\w*"
                            r"|\b(ja |foi |esta |fica |ficou )(registrad|anotad|cadastrad)\w*"),
     _AGENDA | {"registrar_pagamento_informado", "abrir_contestacao", "registrar_contato", "suspender_cobranca",
                "transferir_para_humano", "marcar_promessa_quebrada"}),
    ("suspensão", re.compile(r"\b(suspendi|cancelei|parei (a|as) cobranc)\w*"
                             r"|\b(cobranca|contato|cobrancas) (ja |foi |esta |ficou |fica |ficara )?(suspens|cancelad)\w*"),
     {"suspender_cobranca", "abrir_contestacao", "registrar_pagamento_informado", "transferir_para_humano",
      "marcar_atendimento_humano"}),
    ("acordo", re.compile(r"\bacordo (ja |foi |esta |ficou )?(fechado|registrado|confirmado|firmado|feito)\b"
                          r"|\b(fechamos|firmamos|registramos) (o |seu |nosso )?acordo"), {"registrar_aceite"}),
]
# Só o banco confirma pagamento (pela baixa). A IA nunca diz que confirmou.
_CONFIRMA_PAGAMENTO = re.compile(r"\bpagamento (ja |foi |esta |ficou )?(confirmado|aprovado|baixado|reconhecido)\b"
                                 r"|\b(confirmei|confirmamos|recebemos|identificamos|localizamos) (o |seu |a sua |sua )?pagamento"
                                 r"|\b(sua|a sua|essa|esta) (divida|conta|pendencia) (ja |foi |esta |ficou )?(quitad|paga\b|liquidad)")


# Sequência longa de dígitos (CPF, telefone, conta), com ou sem pontuação.
_DIGITOS_LONGOS = re.compile(r"\d(?:[\d.\-/]*\d){7,}")


def limpar_nota(texto, limite: int = 200) -> str:
    """Texto para o caderno do caso: sem sequência longa de dígitos e curto."""
    t = " ".join(str(texto or "").split())
    t = _DIGITOS_LONGOS.sub("[removido]", t)
    return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"


def acoes_afirmadas(texto: str) -> dict:
    """{nome da ação: ferramentas que a comprovariam} para cada ação dita como feita."""
    t = _norm(texto)
    return {nome: ferr for nome, rx, ferr in _ACOES_AFIRMADAS if rx.search(t)}


def conferir(texto: str, permitidos: dict, feitas: set | None = None) -> list:
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
    if v["extenso"] - permitidos.get("extensos", set()):
        motivos.append("valor, percentual ou parcelas por extenso: escreva com algarismos, como veio da simulação")
    soltas = referencias_do_texto(texto) - permitidos.get("referencias", set())
    if soltas:
        citadas = ", ".join(sorted(f"{a} {b}" for a, b in soltas))
        motivos.append(f"cita norma que não veio da base de conhecimento ({citadas}): use consultar_base")
    t = _norm(texto)
    if feitas is not None:
        for nome, ferr in acoes_afirmadas(texto).items():
            if not ferr & feitas:
                motivos.append(f"diz que fez ({nome}) sem a ferramenta ter feito nesta resposta: "
                               f"chame {' ou '.join(sorted(ferr))} antes, ou não afirme")
    if _CONFIRMA_PAGAMENTO.search(t):
        motivos.append("diz que o pagamento foi confirmado: só o banco confirma; diga que a equipe vai conferir")
    if _LEI_GENERICA.search(t) and not permitidos.get("referencias"):
        motivos.append("fala da lei sem ter consultado a base de conhecimento: use consultar_base")
    if any(re.search(p, t) for p in _TOM):
        motivos.append("tom de ameaça ou constrangimento")
    if any(re.search(p, t) for p in _SEGREDO):
        motivos.append("dado interno ou pessoal no texto")
    if not texto.strip():
        motivos.append("resposta vazia")
    if len(texto) > 1200:
        motivos.append("resposta longa demais")
    return motivos
