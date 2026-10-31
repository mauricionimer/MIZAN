"""Decisão interna sobre ações com impacto jurídico.

Para cada tipo de ação há um perfil: o que se avalia, os fatos mínimos necessários, os
dispositivos que fundamentam a regra e a regra em si (código, não IA). A consulta à base
jurídica traz os dispositivos e diz se as fontes são suficientes, atuais e conferidas.

Resultado: prosseguir, prosseguir com condições, não prosseguir ou revisão humana.
- Falta de resultado NÃO é permissão: fundamento ausente, conflitante, desatualizado ou
  divergente da fonte oficial, ou fato essencial faltando → revisão humana.
- Proibição clara da regra vale mesmo com a fonte por conferir (é o lado seguro).
- O texto recuperado nunca decide nem dá instrução: só se verifica que o fundamento existe.
- Esta decisão não substitui avaliação jurídica humana; é um limite operacional.
"""
from dataclasses import dataclass, field
from datetime import datetime

from agente.juridico.consulta import consultar_legislacao

PROSSEGUIR = "prosseguir"
CONDICOES = "prosseguir_com_condicoes"
NAO_PROSSEGUIR = "nao_prosseguir"
REVISAO = "revisao_humana"
BLOQUEIA = frozenset({NAO_PROSSEGUIR, REVISAO})
_ORDEM = {PROSSEGUIR: 0, CONDICOES: 1, REVISAO: 2, NAO_PROSSEGUIR: 3}


@dataclass(frozen=True)
class Perfil:
    nome: str
    descricao: str              # a ação considerada, para o registro
    pergunta: str               # o que se busca na base (sem dado pessoal)
    fatos: tuple                # fatos aceitos (o resto é descartado: minimização)
    obrigatorios: tuple         # sem eles não dá para avaliar → revisão humana
    fundamentos: tuple          # ((norma_id, artigo, fato_que_ativa ou None), ...)
    regra: object               # fatos -> (decisao, condicoes, motivo)
    exige_conferencia: object = False   # bool, ou fatos -> bool: fonte não conferida → revisão
    normas: tuple = field(default=())   # restringe a busca livre (vazio = todas)


# ── regras ───────────────────────────────────────────────────────────────────

def _r_uso_dados(f):
    if f.get("sensiveis"):
        return REVISAO, [], "envolve dado pessoal sensível, que exige hipótese legal específica"
    if f.get("compartilhamento"):
        return REVISAO, [], "prevê compartilhar dados com terceiros"
    if str(f.get("finalidade") or "") not in ("cobranca", "atendimento", "negociacao"):
        return REVISAO, [], "finalidade diferente da cobrança e do atendimento da dívida"
    return CONDICOES, ["usar os dados só para a cobrança e o atendimento desta dívida",
                       "coletar e guardar só o necessário para isso",
                       "manter o acesso restrito e os dados protegidos"], \
        "uso compatível com a finalidade de cobrança, sem dado sensível e sem compartilhamento"


def _r_compartilhamento(f):
    dest = str(f.get("destinatario") or "")
    if dest == "credor" and str(f.get("finalidade") or "") == "cobranca":
        return CONDICOES, ["compartilhar só o necessário para a cobrança", "registrar o compartilhamento",
                           "informar ao titular, se ele pedir, com quem os dados foram compartilhados"], \
            "repasse ao próprio credor, para a mesma finalidade"
    if dest == "cadastro_inadimplentes":
        return REVISAO, [], "inclusão em cadastro de inadimplentes tem exigências próprias (comunicação prévia)"
    return NAO_PROSSEGUIR, [], "compartilhamento com terceiro sem finalidade e base legal identificadas"


def _r_decisao_automatizada(f):
    if f.get("usa_dado_sensivel"):
        return REVISAO, [], "a decisão automatizada usaria dado sensível"
    if not f.get("revisao_humana_disponivel"):
        return NAO_PROSSEGUIR, [], "não há como a pessoa pedir revisão humana da decisão automatizada"
    if not f.get("criterios_explicaveis"):
        return REVISAO, [], "os critérios da decisão não podem ser explicados à pessoa"
    return CONDICOES, ["a pessoa pode pedir que uma pessoa da equipe revise a decisão",
                       "explicar os critérios em termos simples quando ela pedir"], \
        "decisão automatizada com revisão humana disponível e critérios explicáveis"


def _r_estrategia(f):
    if f.get("contata_terceiros"):
        return NAO_PROSSEGUIR, [], "a estratégia prevê falar da dívida com terceiros (exposição do devedor)"
    if f.get("conteudo_com_ameaca"):
        return NAO_PROSSEGUIR, [], "o conteúdo previsto tem ameaça ou constrangimento"
    ini, fim, dias = f.get("horario_inicio"), f.get("horario_fim"), f.get("dias_semana") or []
    if ini is None or fim is None or int(ini) < 8 or int(fim) > 20 or 6 in [int(d) for d in dias]:
        return REVISAO, [], ("contato fora do horário comercial ou aos domingos pode interferir no descanso "
                             "e no lazer do devedor: avaliar")
    condicoes = ["sem ameaça, constrangimento ou exposição do devedor",
                 "não tratar da dívida com outras pessoas",
                 "identificar a empresa credora em toda cobrança",
                 "respeitar o horário e o limite de contatos da política"]
    if not f.get("identifica_credor", True):
        return REVISAO, [], "as mensagens de cobrança não identificam o credor"
    return CONDICOES, condicoes, "estratégia dentro do horário comercial, sem terceiros e sem conteúdo abusivo"


def _r_comunicacao(f):
    if f.get("envolve_terceiros"):
        return NAO_PROSSEGUIR, [], "o canal ou o conteúdo envolve terceiros"
    if str(f.get("canal") or "") not in ("telegram", "chat", "whatsapp", "sms", "email"):
        return REVISAO, [], "canal de comunicação ainda não avaliado"
    return CONDICOES, ["usar o canal só para este atendimento",
                       "a pessoa pode pedir para parar o contato a qualquer momento",
                       "confirmar a identidade antes de falar de valores"], \
        "canal individual, sem terceiros, iniciado ou aceito pela pessoa" if f.get("iniciativa") == "devedor" \
        else "canal individual, sem terceiros"


def _r_oferta(f):
    if f.get("pressao"):
        return NAO_PROSSEGUIR, [], "a oferta foi feita com pressão para aceitar"
    if not (f.get("informa_total") and f.get("informa_parcelas")):
        return NAO_PROSSEGUIR, [], "faltam informações essenciais da oferta (valor total, número e valor das parcelas)"
    if f.get("sinais_superendividamento"):
        return REVISAO, [], "há sinais de superendividamento: preservar o mínimo existencial exige avaliação humana"
    return CONDICOES, ["mostrar o valor total, o número e o valor das parcelas antes do aceite",
                       "sem pressa nem pressão para aceitar"], \
        "oferta com as informações essenciais e sem sinais de superendividamento"


def _r_pedido_titular(f):
    tipo = str(f.get("tipo") or "")
    condicoes = ["registrar o pedido agora e confirmar o recebimento à pessoa",
                 "a pessoa responsável pelos dados analisa e responde"]
    if tipo in ("acesso", "informacao", "origem"):
        condicoes.append("resposta completa sobre os dados em até 15 dias")
    if tipo == "revisao_decisao":
        condicoes.append("uma pessoa da equipe revisa a decisão e explica os critérios")
    return REVISAO, condicoes, "pedido do titular dos dados: o atendimento é de uma pessoa responsável, não automático"


def _r_contestacao(f):
    return CONDICOES, ["suspender a cobrança enquanto a equipe analisa",
                       "não manter registro negativo de dívida contestada sem análise"], \
        "contestação registrada; a cobrança fica suspensa até a análise humana"


PERFIS = {p.nome: p for p in (
    Perfil("uso_dados_pessoais", "usar ou armazenar dados pessoais do devedor",
           "tratamento de dados pessoais para cobrança hipóteses legais finalidade necessidade segurança",
           ("finalidade", "dados", "sensiveis", "compartilhamento", "canal"), ("finalidade", "sensiveis"),
           (("lgpd", "6", None), ("lgpd", "7", None), ("lgpd", "46", None), ("lgpd", "11", "sensiveis")),
           _r_uso_dados, normas=("lgpd", "marco_civil", "cmn_4949")),
    Perfil("compartilhamento_dados", "compartilhar dados pessoais do devedor",
           "uso compartilhado de dados pessoais com terceiros transferência cadastro de consumidores",
           ("destinatario", "finalidade", "dados"), ("destinatario", "finalidade"),
           (("lgpd", "7", None), ("lgpd", "18", None), ("cdc", "43", None)),
           _r_compartilhamento, exige_conferencia=True),
    Perfil("decisao_automatizada_credito", "decidir de forma automatizada sobre crédito e cobrança (perfil, grupo, oferta)",
           "revisão de decisão automatizada perfil de crédito critérios tratamento automatizado",
           ("revisao_humana_disponivel", "criterios_explicaveis", "usa_dado_sensivel", "uso"),
           ("revisao_humana_disponivel", "criterios_explicaveis", "usa_dado_sensivel"),
           (("lgpd", "20", None), ("cadastro_positivo", "5", None)),
           _r_decisao_automatizada),
    Perfil("estrategia_cobranca", "definir a estratégia de cobrança (quem, quando e como contatar)",
           "cobrança de dívidas ameaça constrangimento exposição descanso lazer identificação do credor",
           ("contata_terceiros", "conteudo_com_ameaca", "horario_inicio", "horario_fim", "dias_semana",
            "frequencia_semanal_max", "identifica_credor", "canais"),
           ("contata_terceiros", "horario_inicio", "horario_fim", "dias_semana"),
           (("cdc", "42", None), ("cdc", "42-A", None), ("cdc", "71", None), ("cmn_4949", "7", None)),
           _r_estrategia),
    Perfil("comunicacao_devedor", "escolher o canal e falar com o devedor por ele",
           "comunicação com o consumidor cobrança canal dados pessoais internet",
           ("canal", "iniciativa", "envolve_terceiros"), ("canal", "envolve_terceiros"),
           (("cdc", "42", None), ("cdc", "71", None), ("lgpd", "6", None), ("marco_civil", "7", None)),
           _r_comunicacao),
    Perfil("oferta_credito", "registrar um acordo (oferta de crédito ao consumidor)",
           "informações prévias crédito prestações total superendividamento mínimo existencial assédio pressão",
           ("informa_total", "informa_parcelas", "sinais_superendividamento", "pressao", "n_parcelas"),
           ("informa_total", "informa_parcelas", "sinais_superendividamento"),
           (("cdc", "52", None), ("cdc", "54-B", None), ("cdc", "54-C", None),
            ("decreto_11150", "3", "sinais_superendividamento")),
           _r_oferta, exige_conferencia=lambda f: bool(f.get("sinais_superendividamento"))),
    Perfil("pedido_titular", "atender pedido do titular sobre os próprios dados",
           "direitos do titular confirmação acesso correção eliminação revisão decisão automatizada encarregado prazo",
           ("tipo",), ("tipo",),
           (("lgpd", "18", None), ("lgpd", "19", None), ("lgpd", "41", None), ("lgpd", "20", None), ("cdc", "43", None)),
           _r_pedido_titular),
    Perfil("contestacao", "tratar contestação da dívida pelo devedor",
           "consumidor contesta a dívida cobrança indevida correção de cadastro",
           ("motivo",), (),
           (("cdc", "42", None), ("cdc", "43", None)),
           _r_contestacao),
)}


def _mais_restritiva(*decisoes) -> str:
    return max((d for d in decisoes if d), key=lambda d: _ORDEM[d])


def avaliar(acao: str, fatos: dict | None = None, *, indice=None, conferencias=None,
            agora: datetime | None = None) -> dict:
    """Consulta a base e devolve a decisão interna (nada é executado aqui)."""
    perfil = PERFIS.get(acao)
    if perfil is None:
        return {"acao": acao, "decisao": REVISAO, "condicoes": [], "dispositivos": [], "fontes": [],
                "justificativa": "ação sem perfil jurídico definido: encaminhar para revisão humana",
                "incertezas": ["ação não mapeada"], "fatos": {}, "consultado_em": None}
    f = {k: v for k, v in (fatos or {}).items() if k in perfil.fatos}
    faltam = [k for k in perfil.obrigatorios if f.get(k) is None]
    fundamentos = [(n, a) for n, a, quando in perfil.fundamentos if not quando or f.get(quando)]
    res = consultar_legislacao(perfil.pergunta, f, fundamentos=fundamentos, normas=perfil.normas or None,
                               indice=indice, conferencias=conferencias, agora=agora)

    problemas = []
    if res["fundamentos_ausentes"]:
        problemas.append("fontes insuficientes: faltam no índice " + ", ".join(res["fundamentos_ausentes"]))
    exige = perfil.exige_conferencia(f) if callable(perfil.exige_conferencia) else perfil.exige_conferencia
    capitais = [d for d in res["dispositivos"] if d["origem"] == "fundamento" and d["id"].endswith(":caput")]
    for d in [d for d in res["dispositivos"] if d["origem"] == "fundamento"]:
        if d["situacao"] == "desatualizado":
            problemas.append(f"{d['rotulo']} está desatualizado no acervo")
        if d["conflito"]:
            problemas.append(f"{d['rotulo']} tem versões conflitantes")
        if d["conferencia"] == "divergente":
            problemas.append(f"{d['rotulo']} diverge da fonte oficial")
    if exige and any(d["conferencia"] == "nao_conferida" for d in capitais):
        problemas.append("esta ação exige texto conferido na fonte oficial, e a conferência não foi feita")
    problemas = list(dict.fromkeys(problemas))

    if faltam:
        base, condicoes, motivo = REVISAO, [], "faltam fatos essenciais para avaliar: " + ", ".join(faltam)
    else:
        base, condicoes, motivo = perfil.regra(f)
    decisao = _mais_restritiva(base, REVISAO if problemas else None)
    rotulos = [d["rotulo"] for d in capitais]
    justificativa = motivo + "."
    if problemas and decisao != base:
        justificativa += " Encaminhado para revisão humana: " + "; ".join(problemas) + "."
    if rotulos:
        justificativa += " Fundamentos consultados: " + "; ".join(rotulos) + "."
    return {"acao": acao, "acao_descricao": perfil.descricao, "decisao": decisao,
            "condicoes": condicoes if decisao in (PROSSEGUIR, CONDICOES, REVISAO) else [],
            "justificativa": justificativa,
            "dispositivos": [{k: d[k] for k in ("id", "rotulo", "situacao", "conferencia", "origem")}
                             for d in res["dispositivos"]],
            "fontes": res["fontes"], "incertezas": problemas + res["limitacoes"], "fatos": f,
            "consultado_em": res["consultado_em"], "indice_versao": res["indice"]["versao"],
            "commit_acervo": res["indice"]["commit"]}


def avaliar_e_registrar(repo, empresa_id: str, caso_id, acao: str, fatos: dict | None = None, *,
                        trace_id=None, indice=None, agora: datetime | None = None) -> dict:
    """Avalia e grava o registro interno (falha no registro não muda a decisão)."""
    from agente.juridico import registro
    conferencias = registro.conferencias(repo)
    d = avaliar(acao, fatos, indice=indice, conferencias=conferencias, agora=agora)
    d["registro_id"] = registro.registrar(repo, empresa_id, caso_id, trace_id, d)
    return d
