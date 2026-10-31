"""Travas no texto que vai para o devedor (docs/PLANO_EXECUCAO_AGENTES.md, 8).

Conferido em código antes de enviar:
1. Valores: todo valor em reais, percentual e número de parcelas no texto
   precisa ter saído de uma ferramenta nesta conversa (simulação, conta,
   oferta, dívida ou compromissos). Vale também para valor sem "R$" perto de
   palavra de negociação ("fecho por 2500", "fica 1.500 no pix"), "$",
   valor por extenso ("dois mil") e fração do valor ("metade do valor").
2. Tom: nada de ameaça, constrangimento ou exposição ao ridículo — o Código de
   Defesa do Consumidor (art. 42) proíbe isso na cobrança. É uma primeira
   camada por palavras; a bateria de cenários mede o resto.
3. Segredos: nada de CPF, identificadores internos ou instruções do sistema.
4. Normas: lei, artigo, súmula, decreto, Código Penal ou Constituição citados
   no texto precisam ter vindo da base de conhecimento nesta conversa
   (ferramenta consultar_base). O agente não inventa valor nem lei.
5. Ações: o texto só diz que fez (agendou, transferiu, suspendeu, fechou o
   acordo) se a ferramenta fez nesta resposta; e nunca confirma pagamento.

Reprovou: o motivo (com o termo que pegou) volta para a IA reescrever; se
reprovar de novo, o Negociador pede para a pessoa dizer de outro jeito, e só na
segunda vez seguida uma pessoa da equipe assume.
"""
import re
import unicodedata

TOLERANCIA = 0.01
VALOR_SOLTO_MIN = 10                  # número solto abaixo disso não é valor ("fica 2 dias")

_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?"
# "R$ 1,5 mil" é 1.500 (quem lê é _DINHEIRO_MIL), não R$ 1,50; "R$ 15 000,00" vale 15.000.
_DINHEIRO = re.compile(r"(?:R|US)?\$\s*(\d{1,3}(?:[.\u00a0 ]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)(?!\d|,\d|\s*mil\b)"
                       r"|\b(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})\b")
_PERCENTUAL = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
# "6x", "6 parcelas", "em 6 vezes" contam; "falei com você 3 vezes" não.
_PARCELAS = re.compile(r"\b(\d{1,3})\s*(?:x\b|parcelas?\b|prestac)|\b(?:em|de)\s+(\d{1,3})\s*vezes\b", re.I)

# Os mesmos valores escritos de outro jeito (no texto já normalizado por _norm).
# Quem tenta manipular o agente pede justamente isso: "fecha em 2500 reais".
_DINHEIRO_REAIS = re.compile(r"\b(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s*(?:reais|real|contos?|pilas?)\b")
_DINHEIRO_MIL = re.compile(r"\b(\d+(?:[.,]\d{1,2})?)\s*(?:mil|k)\b")
_PERCENTUAL_EXTENSO = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*por\s*cento\b")
# Prazo de acordo ("divide em 24 meses"); "te procuro em 2 meses" não é parcela.
_VERBO_PRAZO = r"(?:parcel\w*|divid\w*|divide|pagar|paga|pague|quitar|financ\w*)\s+(?:\w+\s+){0,2}(?:em|por)\s+"
_PARCELAS_MESES = re.compile(rf"\b{_VERBO_PRAZO}(\d{{1,3}})\s*meses\b")
# Número sem "R$" perto de palavra de negociação: "fecho por 2500", "fica 1.500 no pix",
# "12 boletos de 250". Datas, horas, "12x", parcelas, meses e percentuais ficam de fora.
_GATILHO = (r"(?:por|fecho|fecha|fechar|fechamos|fica|ficam|ficaria|faco|sai por|sai a|entrada de|parcelas? de"
            r"|boletos? de|pix de|no pix de|pagar|paga|pague|pagaria|pagamento de|valor de|total de)")
_MESES_NOME = r"(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"
_NAO_E_VALOR = (rf"(?![\d.,]?\d)(?!\s*(?:%|x\b|vezes|parcelas?|prestac|meses|mes\b|dias?\b|horas?\b|h\b|hs\b|anos?\b"
                rf"|semanas?\b|/|:|por\s*cento|mil\b|k\b|reais|real\b|contos?|pilas?|de\s+{_MESES_NOME}|do\s+mes))")
_VALOR_SOLTO = re.compile(rf"\b{_GATILHO}\s+(?:so\s+|apenas\s+|uns\s+|ate\s+)?({_NUM}){_NAO_E_VALOR}"
                          rf"|\b({_NUM})\s*(?:a vista|no pix|de entrada|por mes)\b")
_FRACAO = re.compile(r"\b(metade|um terco|dois tercos|um quarto|tres quartos|o dobro)\s+(do|da|de)\s+"
                     r"(valor|divida|saldo|total|debito|parcela|conta)")
_NUM_EXTENSO = (r"(?:um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze"
                r"|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa"
                r"|cem|cento|duzent[oa]s|trezent[oa]s|quatrocent[oa]s|quinhent[oa]s|seiscent[oa]s|setecent[oa]s"
                r"|oitocent[oa]s|novecent[oa]s|mil)")
_SEQ_EXTENSO = rf"{_NUM_EXTENSO}(?:\s+(?:e\s+)?{_NUM_EXTENSO})*"
# Número por extenso seguido de unidade de dinheiro, percentual ou parcela.
# Não dá para conferir contra a simulação: a regra é escrever com algarismos.
_VALOR_EXTENSO = re.compile(rf"\b{_SEQ_EXTENSO}\s+(?:reais|real|por\s*cento|parcelas?|prestac\w*)\b"
                            rf"|\b(?:em|de)\s+{_SEQ_EXTENSO}\s+vezes\b|\b{_VERBO_PRAZO}{_SEQ_EXTENSO}\s+meses\b")
# Extenso com mil, cem, cento ou centenas é valor mesmo sem unidade ("fecho por dois
# mil", "fica mil e quinhentos"). "Mil desculpas" não conta.
_GRANDE = (r"(?:mil|cem|(?<!por )cento|duzent[oa]s|trezent[oa]s|quatrocent[oa]s|quinhent[oa]s|seiscent[oa]s|setecent[oa]s"
           r"|oitocent[oa]s|novecent[oa]s)")
# "R$ 1,5 mil" (com algarismo antes) já é lido como dinheiro; aqui só o extenso puro.
_EXTENSO_GRANDE = re.compile(rf"(?<![\d,.])(?<!\d )\b(?:{_NUM_EXTENSO}\s+(?:e\s+)?)*{_GRANDE}(?:\s+(?:e\s+)?{_NUM_EXTENSO})*\b"
                             r"(?!\s+(?:desculpas|perdoes|obrigad\w*|motivos|maneiras|formas|coisas|vezes|anos))")

# Citações de norma, no texto já sem acento e em minúsculas (_norm).
_REF_NUMERO = [
    ("art", re.compile(r"\bart(?:igo)?s?\.?\s*(\d{1,4}(?:-[a-z])?)\b")),
    ("sumula", re.compile(r"\bsumulas?\s*(?:n[o.]?\s*|numero\s*)?(\d{1,4})\b")),
    ("lei", re.compile(r"\blei\s*(?:n[o.]?\s*|numero\s*)?(\d{1,2}\.?\d{3})\b")),
    ("decreto", re.compile(r"\bdecreto\s*(?:n[o.]?\s*|numero\s*)?(\d{1,2}\.?\d{3})\b")),
]
_REF_NOME = [
    ("cdc", re.compile(r"\bcdc\b|codigo de defesa do consumidor")),
    ("lgpd", re.compile(r"\blgpd\b|lei geral de protecao de dados")),
    ("codigo_civil", re.compile(r"codigo civil")),
    ("codigo_penal", re.compile(r"codigo penal")),
    ("constituicao", re.compile(r"\bconstituicao\b|\bconstitucional\b|carta magna")),
    ("decreto", re.compile(r"\bdecreto\b")),
    ("stj", re.compile(r"\bstj\b|superior tribunal")),
    ("banco_central", re.compile(r"\bbanco central\b|\bbacen\b|\bbcb\b"
                                 r"|\bresoluc(ao|oes) (do |da )?(cmn|bcb|bacen|banco central|conselho monetario|n[o.]?\s*\d|numero|\d)")),
]
# "Pela lei...", "a lei garante...", "a lei do superendividamento": lei sem
# número. Só pode se a base foi consultada nesta conversa.
_LEI_GENERICA = re.compile(r"\b(pela|segundo a|conforme a|de acordo com a) lei\b"
                           r"|\ba lei (diz|permite|garante|determina|obriga|proibe|manda|exige|preve)\b"
                           r"|\blei (do|da|dos|das) [a-z]{4,}")

# Ameaça e constrangimento. Cada item é uma palavra ou um jeito de dizer; a
# reprovação devolve o trecho que pegou, para a IA saber o que trocar.
_TOM = [
    r"\bprocessar\b", r"\bprocessaremos\b", r"\b(um|abrir|entrar com|mover) (um )?processo\b", r"\bprocesso judicial\b",
    r"\bjustica\b", r"\bpolicia\b", r"\bpres[oa]\b", r"\bprisao\b", r"\bcadeia\b",
    r"\bcaloteir", r"(?<!ter )(?<!sentir )(?<!tenha )\bvergonha\b", r"\bvizinh", r"\bempregador\b", r"\bpatrao\b",
    r"\bseu chefe\b", r"\bsua familia (vai|vao) saber", r"\bvai se arrepender", r"\bultima chance\b", r"\bpenhor",
    r"\bconfisc", r"\bsujar (o )?seu nome para sempre", r"\bmentiros", r"\birresponsavel\b",
    r"\bjudicial", r"\bjuridic", r"\bprotest(o|ar|aremos|ado|ada)\b", r"\bcartorio\b",
    r"\b(nosso|nossos|nossa|o|os) advogad", r"\badvogad\w* (da empresa|do banco|da instituicao)",
    r"\b(acionar|chamar|encaminhar|passar)\w* (o |os |ao |aos |para o |para os |pro |pros )?advogad",
    # Falar com a família, o trabalho ou os vizinhos da pessoa. Citar a família
    # com carinho ("sinto muito pela sua mãe") não é ameaça.
    r"\b(ligar|ligaremos|ligamos|falar|falaremos|avisar|avisaremos|contar|contaremos|procurar|procuraremos|contatar"
    r"|contataremos|mandar mensagem|cobrar)\w* (para |pra |a |com |aos |as |ao )?(a |o |os |as )?"
    r"(sua|seu|seus|suas) (parentes|familiares|familia|filhos|filhas|esposa|marido|mae|pai|irmao|irma)",
    r"\bperde(r|ra|rao)? tudo\b", r"\bnunca mais (vai )?(conseguir|ter) credito\b", r"\bnao (vai )?ter mais acordo\b",
    r"\bdesonest", r"\bvagabund", r"\bsafad", r"\bpilantra", r"\bvigarist",
]
_SEGREDO = [
    (r"\b\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-.\s]?\d{2}\b", "número que parece CPF"),
    (r"simulacao_id|compromisso_id|trace_id|predicao_id", "identificador interno"),
    (r"system prompt|prompt do sistema|minhas instrucoes|ferramenta [a-z_]+\(", "instrução do sistema"),
    (r"desconto maximo|alcada|politica interna", "limite interno da política"),
]

# Números das ferramentas que podem aparecer no texto, pela chave do resultado:
# simulação e conta, oferta, dívida e compromissos. O resto (dias de atraso,
# versão, tentativas, limites da política) não vira valor citável.
_CHAVES_DINHEIRO = frozenset({"valor_negociado", "entrada", "saldo", "parcela", "total_pago", "economia",
                              "juros_total", "valor_divida", "primeiro_pagamento"})
_CHAVES_PCT = frozenset({"desconto_pct", "entrada_pct", "juros_mensal_pct"})
_CHAVES_COM_VALOR = frozenset({"compromissos"})        # {"valor": ...} dentro dessas listas


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _num_br(s: str) -> float:
    return float(s.replace(".", "").replace("\u00a0", "").replace(" ", "").replace(",", "."))


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
    parcelas = [int(a or b) for a, b in _PARCELAS.findall(texto)] + [int(n) for n in _PARCELAS_MESES.findall(t)]
    # Número solto perto de palavra de negociação; o texto com "R$" já foi lido acima.
    sem_rs = re.sub(r"(?:r|us)?\$\s*[\d.,\u00a0 ]+", " ", t)
    soltos = [x for x in (_num_br(a or b) for a, b in _VALOR_SOLTO.findall(sem_rs)) if x >= VALOR_SOLTO_MIN]
    extenso = {m.group(0) for m in _VALOR_EXTENSO.finditer(t)} | {m.group(0) for m in _EXTENSO_GRANDE.finditer(t)}
    return {"dinheiro": dinheiro, "percentuais": percentuais, "parcelas": parcelas, "soltos": soltos,
            "extenso": extenso, "fracao": [m.group(0) for m in _FRACAO.finditer(t)]}


def permitidos_de(resultados: list) -> dict:
    """Valores e normas que as ferramentas devolveram nesta conversa.

    Só contam os números de chaves conhecidas (simulação e conta, oferta,
    dívida, compromissos) e os que estão nos resumos e respostas da base.
    Limite da política, dias de atraso ou versão não viram valor citável."""
    dinheiro, percentuais, parcelas, referencias, extensos = set(), set(), {1}, set(), set()
    def andar(x, chave="", pai=""):
        if isinstance(x, dict):
            for k, v in x.items():
                andar(v, k, chave)
        elif isinstance(x, list):
            for v in x:
                andar(v, chave, pai)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            if chave in _CHAVES_PCT:
                percentuais.add(round(float(x), 2))
            elif chave == "n_parcelas":
                parcelas.add(int(x))
            elif chave in _CHAVES_DINHEIRO or (chave == "valor" and pai in _CHAVES_COM_VALOR):
                dinheiro.add(round(float(x), 2))
        elif isinstance(x, str) and chave in ("resumo", "resposta"):
            v = valores_do_texto(x)
            dinheiro.update(round(d, 2) for d in v["dinheiro"])
            percentuais.update(round(p, 2) for p in v["percentuais"])
            parcelas.update(v["parcelas"])
            dinheiro.update(round(d, 2) for d in v["soltos"])
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
_AGENDA = {"agendar_retorno", "remarcar_compromisso", "marcar_atendimento_humano", "registrar_aceite",
           "desmarcar_compromisso"}
_EQUIPE = {"transferir_para_humano", "marcar_atendimento_humano"}
_ACOES_AFIRMADAS = [
    ("agendamento", re.compile(r"\b(agendei|marquei|remarquei|reagendei|combinei)\b"
                               r"|\b(ja |esta |fica |ficou |foi |deixei )(tudo )?(agendad|marcad|remarcad|reagendad|combinad)\w*"
                               r"|\b(agendado|marcado|remarcado) (para|pra|com sucesso)\b"
                               r"|\b(te|lhe) (chamo|ligo|procuro|escrevo|mando mensagem|retorno) (no |na |em |dia |amanha|segunda"
                               r"|terca|quarta|quinta|sexta|sabado|as |semana)"), _AGENDA),
    ("transferência", re.compile(r"\b(transferi|encaminhei|repassei|avisei|acionei|chamei|notifiquei|comuniquei)\b"
                                 r"|\b(ja |foi |esta |fica )(transferid|encaminhad|repassad|avisad|acionad|notificad)\w*"
                                 r"|\bpassei (a |o |sua |seu |para |pra )"
                                 r"|\b(a equipe|um atendente|uma pessoa|alguem da equipe|nosso time) (ja )?(vai|vao|ira|irao) "
                                 r"(te |lhe )?(ligar|chamar|procurar|entrar em contato|falar com voce|retornar|atender)"),
     _EQUIPE | {"registrar_pagamento_informado", "abrir_contestacao"}),
    ("registro", re.compile(r"\b(registrei|anotei|cadastrei|lancei|abri (a |uma )?contestac)\w*"
                            r"|\b(ja |foi |esta |fica |ficou )(registrad|anotad|cadastrad)\w*|^\W*(anotado|registrado)\b"),
     _AGENDA | {"registrar_pagamento_informado", "abrir_contestacao", "registrar_contato", "suspender_cobranca",
                "transferir_para_humano", "marcar_promessa_quebrada"}),
    ("suspensão", re.compile(r"\b(suspendi|cancelei|pausei|interrompi|bloqueei|parei (a|as) cobranc)\w*"
                             r"|\b(cobranca|contato|cobrancas|mensagens|ligacoes) (ja |foi |foram |esta |estao |ficou |fica |ficara )?"
                             r"(suspens|cancelad|pausad|interrompid|bloquead|encerrad)\w*"),
     {"suspender_cobranca", "abrir_contestacao", "registrar_pagamento_informado", "transferir_para_humano",
      "marcar_atendimento_humano", "desmarcar_compromisso"}),
    ("desmarcação", re.compile(r"\b(desmarquei|desagendei)\b|\b(ja |foi |esta |ficou )(desmarcad|desagendad)\w*"),
     {"desmarcar_compromisso"}),
    ("acordo", re.compile(r"\bacordo (ja |foi |esta |ficou )?(fechado|registrado|confirmado|firmado|feito|aprovado|ativo"
                          r"|garantido|concluido|efetivado)\b"
                          r"|\b(fechamos|firmamos|registramos|aprovamos|efetivamos) (o |seu |nosso )?acordo"), {"registrar_aceite"}),
]
# Só o banco confirma pagamento (pela baixa). A IA nunca diz que confirmou.
_CONFIRMA_PAGAMENTO = re.compile(r"\bpagamento (ja |foi |esta |ficou )?(confirmado|aprovado|baixado|reconhecido|recebido|compensado"
                                 r"|identificado|creditado|processado|localizado)\b"
                                 r"|\b(confirmei|confirmamos|recebemos|identificamos|localizamos|compensamos) (o |seu |a sua |sua )?pagamento"
                                 r"|\b(sua|a sua|essa|esta) (divida|conta|pendencia) (ja |foi |esta |ficou )?(quitad|paga\b|liquidad|zerad"
                                 r"|encerrad|baixad|resolvid)"
                                 r"|\b(seu|o seu) nome (ja )?(esta |foi |ficou )?(limpo|limpa)\b|\bnao (deve|deves) mais nada\b")


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


# Chamada de ferramenta escrita como texto (o Gemini às vezes faz isso): nunca vai ao devedor.
_CODIGO_NO_TEXTO = re.compile(r'</?[a-z_]{2,20}>|```|"(tool|args|name|function_?call|parameters)"\s*:|\{\s*"[a-z_]+"\s*:', re.IGNORECASE)


def conferir(texto: str, permitidos: dict, feitas: set | None = None) -> list:
    """Motivos de reprovação (lista vazia = pode enviar). Cada motivo diz o termo
    que pegou, para a IA saber o que reescrever."""
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
    for d in v["soltos"]:
        # Número sem "R$" ("fecho por 2500"): vale se for um valor, parcela ou percentual das ferramentas.
        if not (any(abs(d - p) <= TOLERANCIA for p in permitidos["dinheiro"])
                or d in permitidos["parcelas"] or round(d, 2) in permitidos["percentuais"]):
            motivos.append(f"valor {d:g} sem R$ não veio de uma simulação: escreva o valor com R$, como veio da ferramenta")
    for f in v["fracao"]:
        motivos.append(f"“{f}” é um valor sem número: use o valor da simulação, com R$")
    extensos = sorted(v["extenso"] - permitidos.get("extensos", set()))
    if extensos:
        motivos.append(f"valor, percentual ou parcelas por extenso (“{extensos[0]}”): escreva com algarismos, "
                       "como veio da simulação")
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
    m = _CONFIRMA_PAGAMENTO.search(t)
    if m:
        motivos.append(f"diz que o pagamento foi confirmado (“{m.group(0)}”): só o banco confirma; "
                       "diga que a equipe vai conferir")
    if _LEI_GENERICA.search(t) and not permitidos.get("referencias"):
        motivos.append("fala da lei sem ter consultado a base de conhecimento: use consultar_base")
    for p in _TOM:
        m = re.search(p, t)
        if m:
            motivos.append(f"tom de ameaça ou constrangimento (“{m.group(0)}”): reescreva sem isso")
            break
    if _CODIGO_NO_TEXTO.search(texto):
        motivos.append("o texto tem código ou chamada de ferramenta: chame a ferramenta de verdade e escreva só a resposta")
    for p, tipo in _SEGREDO:
        if re.search(p, t):
            motivos.append(f"dado interno ou pessoal no texto ({tipo})")     # nunca repete o dado
            break
    if not texto.strip():
        motivos.append("resposta vazia")
    if len(texto) > 1200:
        motivos.append("resposta longa demais")
    return list(dict.fromkeys(motivos))
