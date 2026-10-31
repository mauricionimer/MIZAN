"""Texto para a base jurídica: normalização, radicais, sinônimos, remoção de dado pessoal
e detecção de conteúdo com cara de instrução.

Tudo local e determinístico: nada sai do servidor para buscar.
"""
import re
import unicodedata

# ── normalização e radicais ─────────────────────────────────────────────────

_STOP = set("""
a ao aos as ate com como da das de dela dele deles do dos e ela elas ele eles em entre essa esse esta este
eu foi for ha isso isto ja la lhe mais mas me mesmo meu minha muito na nas nao nem no nos nossa nosso num
numa o os ou para pela pelas pelo pelos por qual quando que quem se sem ser seu seus sua suas sao so
tambem te tem ter um uma umas uns voce voces sobre apos ante sob cada caso art arts inciso alinea paragrafo
lei artigo deste desta neste nesta destes dessas desses disso nisso aquele aquela qualquer quaisquer
""".split())


def sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in t if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, aspas e travessões padronizados, espaços simples."""
    t = sem_acento(texto).lower()
    t = (t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
         .replace("–", "-").replace("—", "-").replace("º", "o").replace("°", "o").replace("ª", "a"))
    return re.sub(r"\s+", " ", t).strip()


def _radical(p: str) -> str:
    """Radical simples para o português: tira plural e algumas terminações e corta em 6.

    Não é um analisador morfológico; é o bastante para "cobrança/cobrar/cobrado",
    "dados/dado", "eliminação/eliminar" caírem perto. A busca semântica cobre o resto.
    """
    for de, para in (("coes", "cao"), ("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"),
                     ("ois", "ol"), ("ns", "m")):
        if p.endswith(de) and len(p) > len(de) + 2:
            p = p[: -len(de)] + para
            break
    else:
        if p.endswith("es") and len(p) > 5 and p[-3] in "rzl":
            p = p[:-2]
        elif p.endswith("s") and len(p) > 4:
            p = p[:-1]
    if p.endswith("mente") and len(p) > 8:
        p = p[:-5]
    return p[:6]


def termos(texto: str) -> list:
    """Termos para busca: palavras normalizadas (exatas) e seus radicais."""
    saida = []
    for p in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalizar(texto)):
        if p in _STOP or (len(p) < 2 and not p.isdigit()):
            continue
        saida.append(p)
        r = _radical(p)
        if r != p:
            saida.append("~" + r)
    return saida


# ── sinônimos: como a operação fala → como a lei fala ──────────────────────
# Ajuda a busca a achar o dispositivo quando a pergunta usa palavras do dia a dia.
SINONIMOS = [
    (r"negativ|spc|serasa|nome sujo|restri[cç][aã]o no nome", "cadastro banco de dados consumidor inadimplente registro"),
    (r"\bscore\b|pontua[cç][aã]o|perfil de cr[eé]dito|nota de cr[eé]dito|modelo de risco",
     "decisao automatizada tratamento automatizado perfil credito"),
    (r"\bligar\b|liga[cç][aã]o|mensagem|whatsapp|telegram|\bsms\b|e-?mail|contato|abordagem|canal",
     "comunicacao cobranca consumidor informacao"),
    (r"hor[aá]rio|madrugada|domingo|feriado|fim de semana|[aà] noite|descanso",
     "descanso lazer trabalho interfira cobranca"),
    (r"amea[cç]|constrang|humilh|expor|exposi[cç]|vizinh|fam[ií]lia|parente|chefe|colega|terceir",
     "ameaca constrangimento ridiculo exposto cobranca dividas"),
    (r"(apagar|excluir|deletar|remover|esquecer).{0,20}dados|dados.{0,20}(apagad|exclu)",
     "eliminacao dados pessoais titular anonimizacao bloqueio"),
    (r"quais dados|que dados|acesso aos? (meus )?dados|de onde (veio|vieram|tiraram|conseguiram)",
     "confirmacao existencia tratamento acesso dados origem titular"),
    (r"corrigir|errad|desatualizad|incorret", "correcao dados incompletos inexatos desatualizados"),
    (r"compartilh|repass|vender dados|enviar (os )?dados|terceiros? (receb|acess)",
     "uso compartilhado compartilhamento transferencia dados terceiro"),
    (r"superendivid|m[ií]nimo existencial|n[aã]o (consigo|tenho como) pagar|sem renda|sal[aá]rio",
     "superendividamento minimo existencial renda consumidor"),
    (r"\bjuros\b|multa|encargo|corre[cç][aã]o monet", "juros mora encargos inadimplemento"),
    (r"prescri|d[ií]vida (velha|antiga)|caducou|cinco anos|5 anos", "prescricao pretensao prazo"),
    (r"j[aá] paguei|cobran[cç]a indevida|cobrar (de novo|duas vezes)|d[ií]vida paga",
     "cobranca indevida divida paga dobro repeticao"),
    (r"cess[aã]o|comprou a d[ií]vida|empresa de cobran|terceirizad|assessoria de cobran",
     "cessao de credito notificacao devedor cessionario"),
    (r"proposta|acordo|parcel|oferta|desconto|renegocia", "credito informacoes previas prestacoes total consumidor"),
    (r"consentimento|autoriza[cç]", "consentimento titular manifestacao livre informada"),
    (r"base legal|leg[ií]timo interesse|exerc[ií]cio (regular )?de direito|prote[cç][aã]o do cr[eé]dito",
     "hipoteses tratamento dados legitimo interesse exercicio regular direitos protecao credito"),
    (r"sens[ií]ve|sa[uú]de|religi|biometr|doen[cç]", "dados pessoais sensiveis"),
    (r"seguran[cç]a|vazament|incidente|invas", "seguranca incidente medidas tecnicas administrativas"),
    (r"encarregad|\bdpo\b", "encarregado tratamento dados pessoais canal comunicacao titulares"),
    (r"\brob[oô]\b|\bia\b|intelig[eê]ncia artificial|autom[aá]tic", "decisao automatizada tratamento automatizado revisao"),
    (r"revis[aã]o|revisar|contestar a an[aá]lise|por que (fui|eu fui)", "revisao decisao automatizada criterios"),
]


def expandir(pergunta: str) -> str:
    """A pergunta mais os termos jurídicos equivalentes ao que ela menciona."""
    t = normalizar(pergunta)
    extra = [alvo for padrao, alvo in SINONIMOS if re.search(padrao, t)]
    return pergunta + (" " + " ".join(extra) if extra else "")


# ── dado pessoal: fora da consulta, dos registros e dos logs ───────────────

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TELEFONE = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")
_DIGITOS = re.compile(r"\d(?:[\d.\-/ ]*\d){7,}")
MAX_CONSULTA = 600


def sanitizar(texto, nomes=()) -> str:
    """Tira CPF, CNPJ, e-mail, telefone, números longos e os nomes informados.

    A consulta jurídica recebe só o contexto mínimo da ação; quem chama passa
    fatos estruturados, e isto é a segunda barreira, para o caso de algum texto livre.
    """
    t = str(texto or "")
    t = _EMAIL.sub("[e-mail]", t)
    t = _CNPJ.sub("[documento]", t)
    t = _CPF.sub("[documento]", t)
    t = _TELEFONE.sub("[telefone]", t)
    t = _DIGITOS.sub("[número]", t)
    for nome in nomes or ():
        for parte in re.findall(r"[A-Za-zÀ-ÿ]{3,}", str(nome or "")):
            t = re.sub(rf"\b{re.escape(parte)}\b", "[nome]", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:MAX_CONSULTA]


# ── conteúdo com cara de instrução (no acervo ou na pergunta) ──────────────
# Texto de lei não manda o agente fazer nada. Um trecho que tenta dar ordem a um
# modelo, ou se passar por regra do sistema, é marcado e fica fora dos fundamentos.
_INSTRUCAO = re.compile(
    r"ignor(e|ar|em)\b.{0,40}(instru|regra|orienta|anterior|acima)"
    r"|desconsider(e|ar|em)\b.{0,40}(instru|regra|anterior|acima)"
    r"|esque[cç](a|er)\b.{0,30}(instru|regra|tudo)"
    r"|\b(voc[eê]|o agente|o assistente|a ia|o modelo)\s+(agora\s+)?(deve|precisa|tem que|est[aá] autorizad)"
    r"|aja como|finja (ser|que)|prompt (do )?sistema|system prompt|<\s*/?\s*(system|instru)"
    r"|\b(conceda|ofere[cç]a|aplique)\s+(um |o )?desconto\s+de\s+\d+"
    r"|sem (passar pela|consultar a) (revis[aã]o|aprova[cç][aã]o|equipe)",
    re.I)


def parece_instrucao(texto: str) -> bool:
    return bool(_INSTRUCAO.search(sem_acento(str(texto or ""))))
