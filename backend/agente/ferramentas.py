"""As 16 ferramentas do Negociador (docs/PLANO_AGENTE.md, 3.2).

Toda chamada segue o mesmo caminho:

    nome e argumentos validados → Auditor decide → executa → passo no rastreio

- A IA nunca recebe CPF, renda nem dados de outro devedor: só primeiro nome,
  valores da dívida (depois de confirmar a identidade), datas e situação.
- Todo valor que a IA vai dizer sai de `simular_acordo`; o aceite só vale para
  uma simulação feita aqui (o Auditor confere).
- Toda lei ou súmula que a IA vai citar sai de `consultar_base` (a base de
  conhecimento do devedor, agente/conhecimento.py).
- Erros de uso voltam como resultado ({"ok": false, "erro": ...}) para a IA
  corrigir; falha de verdade (banco fora) sobe e o orquestrador trata.
"""
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from agente import auditor, conhecimento, estado
from model import oferta

VALIDADE_SIMULACAO = timedelta(minutes=30)
MAX_SIMULACOES = 5
MAX_TENTATIVAS_IDENTIDADE = 3
MAX_FONTES_GUARDADAS = 10


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict          # propriedades do JSON Schema
    obrigatorios: tuple
    acao: str                 # tipo de ação para o Auditor
    executar: object          # (ctx, fonte, devedor, args) -> dict
    exige_identidade: bool = False

    def definicao(self) -> dict:
        """Formato de ferramenta da API da Anthropic."""
        return {"name": self.nome, "description": self.descricao,
                "input_schema": {"type": "object", "properties": self.parametros,
                                 "required": list(self.obrigatorios)}}


# ── validação dos argumentos ────────────────────────────────────────────────

def _validar(f: Ferramenta, args) -> str | None:
    if not isinstance(args, dict):
        return "argumentos precisam ser um objeto"
    for campo in f.obrigatorios:
        if args.get(campo) in (None, ""):
            return f"falta {campo}"
    for campo, v in args.items():
        regra = f.parametros.get(campo)
        if regra is None:
            return f"argumento desconhecido: {campo}"
        if v is None:
            continue
        tipo = regra["type"]
        if tipo == "string":
            if not isinstance(v, str):
                return f"{campo}: texto"
            if len(v) > regra.get("maxLength", 500):
                return f"{campo}: texto longo demais"
            if "enum" in regra and v not in regra["enum"]:
                return f"{campo}: use {', '.join(regra['enum'])}"
            if "pattern" in regra and not re.fullmatch(regra["pattern"], v):
                return f"{campo}: {regra.get('description') or 'formato inválido'}"
            if regra.get("format") == "date":
                try:
                    date.fromisoformat(v)
                except ValueError:
                    return f"{campo}: data no formato AAAA-MM-DD"
        elif tipo in ("number", "integer"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return f"{campo}: número"
            if tipo == "integer" and v != int(v):
                return f"{campo}: número inteiro"
            if not regra.get("minimum", float("-inf")) <= v <= regra.get("maximum", float("inf")):
                return f"{campo}: fora da faixa"
    return None


# ── apoio ───────────────────────────────────────────────────────────────────

def _hoje(ctx) -> date:
    return ctx.agora.astimezone(auditor.BRASILIA).date()


def _dados(ctx) -> dict:
    ctx.caso["dados"] = dict(ctx.caso.get("dados") or {})
    return ctx.caso["dados"]


def _ir_para(ctx, nova: str) -> None:
    """Muda a situação; acordo a partir de 'em contato' passa por 'negociando'."""
    atual = ctx.caso["situacao"]
    if atual == nova:
        return
    if nova == "acordo_ativo" and atual in ("em_contato", "so_lembrete", "quebrado"):
        ctx.mudar_situacao("negociando")
    ctx.mudar_situacao(nova)


def _primeiro_nome(nome) -> str:
    return (str(nome or "").strip().split() or [""])[0].title()


def _resumo_conta(cond: dict, conta: dict) -> str:
    n = cond["n_parcelas"]
    if n == 1:
        txt = f"à vista {_brl(conta['total_pago'])}"
    else:
        txt = (f"entrada {_brl(conta['entrada'])} + " if conta["entrada"] > 0 else "") \
              + f"{n}x de {_brl(conta['parcela'])}"
    return txt + (f", {cond['desconto_pct']:g}% de desconto" if cond["desconto_pct"] else "")


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _primeiro_pagamento(cond: dict, conta: dict) -> float:
    return conta["entrada"] if cond["n_parcelas"] > 1 and conta["entrada"] > 0 else conta["parcela"]


def _cond_de(args: dict) -> dict:
    return oferta.condicoes({"desconto_pct": args.get("desconto_pct") or 0,
                             "entrada_pct": args.get("entrada_pct") or 0,
                             "n_parcelas": args.get("n_parcelas") or 1,
                             "juros_mensal_pct": 0})


def _simulacao(ctx, sim_id) -> dict | None:
    for s in _dados(ctx).get("simulacoes") or []:
        if s["id"] == sim_id:
            return {**s, "valida_ate": datetime.fromisoformat(s["valida_ate"])}
    return None


# ── as ferramentas ──────────────────────────────────────────────────────────

def _consultar_caso(ctx, fonte, dev, args):
    d = _dados(ctx)
    r = {"ok": True, "primeiro_nome": _primeiro_nome(dev.get("nome")), "situacao": ctx.caso["situacao"],
         "identidade_confirmada": bool(d.get("identidade_ok"))}
    if d.get("identidade_ok"):
        r.update({"valor_divida": float(dev.get("valor_divida") or 0),
                  "dias_em_atraso": int(dev.get("dias_em_atraso") or 0),
                  "produto": dev.get("produto"),
                  "compromissos": [{"id": a["id"], "tipo": a["tipo"], "data": str(a["data"])[:10],
                                    "valor": a.get("valor")}
                                   for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])]})
    return r


def _verificar_identidade(ctx, fonte, dev, args):
    d = _dados(ctx)
    if d.get("identidade_ok"):
        return {"ok": True, "confirmada": True}
    falhas = int(d.get("falhas_identidade") or 0)
    if falhas >= MAX_TENTATIVAS_IDENTIDADE:
        return {"ok": False, "erro": "limite de tentativas: transfira para uma pessoa"}
    certos = "".join(ch for ch in str(dev.get("cpf") or "") if ch.isdigit())[:3]
    dados = "".join(ch for ch in args["tres_primeiros_digitos_cpf"] if ch.isdigit())
    if len(dados) == 11:
        dados = dados[:3]                    # a pessoa mandou o CPF inteiro: valem os 3 primeiros
    if len(certos) == 3 and dados == certos:
        d["identidade_ok"] = True
        d["divida"] = float(dev.get("valor_divida") or 0)
        return {"ok": True, "confirmada": True}
    d["falhas_identidade"] = falhas + 1
    return {"ok": True, "confirmada": False, "tentativas_restantes": MAX_TENTATIVAS_IDENTIDADE - falhas - 1}


def _listar_ofertas(ctx, fonte, dev, args):
    regras, versao = ctx.politica()
    divida = _dados(ctx)["divida"]
    saida = []
    for o in fonte.catalogo(ctx.caso["empresa_id"]):
        if not o.get("ativa", True) or o.get("juros_mensal_pct"):
            continue
        cond = _cond_de(o)
        # Parcelado do catálogo com entrada abaixo do mínimo da política: a
        # entrada sobe até o mínimo, e a oferta vai marcada como ajustada.
        ajustada = bool(regras) and cond["n_parcelas"] > 1 and cond["entrada_pct"] < regras["entrada_min_pct"]
        if ajustada:
            cond = _cond_de({**cond, "entrada_pct": regras["entrada_min_pct"]})
        dec = auditor.auditar({"tipo": "propor_acordo", "params": cond}, ctx.caso, regras, versao, ctx.agora)
        if dec["permitida"]:
            conta = oferta.calcular(divida, **cond)
            saida.append({"nome": o["nome"], **{k: cond[k] for k in ("desconto_pct", "entrada_pct", "n_parcelas")},
                          "resumo": _resumo_conta(cond, conta), "entrada_ajustada": ajustada})
    return {"ok": True, "ofertas": saida}


def _simular_acordo(ctx, fonte, dev, args):
    try:
        cond = _cond_de(args)
    except ValueError as e:
        return {"ok": False, "erro": str(e)}
    regras, versao = ctx.politica()
    conta = oferta.calcular(_dados(ctx)["divida"], **cond)
    dec = auditor.auditar({"tipo": "propor_acordo", "params": cond}, ctx.caso, regras, versao, ctx.agora)
    sim = {"id": uuid.uuid4().hex[:12], "caso_id": ctx.caso["id"], "condicoes": cond, "conta": conta,
           "valida_ate": (ctx.agora + VALIDADE_SIMULACAO).isoformat()}
    if dec["permitida"]:
        d = _dados(ctx)
        d["simulacoes"] = ((d.get("simulacoes") or []) + [sim])[-MAX_SIMULACOES:]
    r = {"ok": True, "dentro_da_politica": dec["permitida"], "resumo": _resumo_conta(cond, conta),
         "valor_negociado": conta["valor_negociado"], "entrada": conta["entrada"], "parcela": conta["parcela"],
         "n_parcelas": cond["n_parcelas"], "total_pago": conta["total_pago"], "economia": conta["economia"]}
    if dec["permitida"]:
        r["simulacao_id"] = sim["id"]
    else:
        r["motivo"] = dec["motivo"]
    cabe = args.get("cabe_por_mes")
    if cabe is not None:
        r["cabe_no_bolso"] = _primeiro_pagamento(cond, conta) <= cabe and (cond["n_parcelas"] == 1 or conta["parcela"] <= cabe)
    return r


def _params_aceite(ctx, args):
    sim = _simulacao(ctx, args["simulacao_id"])
    cond = sim["condicoes"] if sim else {}
    return {**cond, "simulacao_id": args["simulacao_id"], "data": args["data_primeiro_pagamento"]}, sim


def _registrar_aceite(ctx, fonte, dev, args):
    sim = _simulacao(ctx, args["simulacao_id"])
    cond, conta = sim["condicoes"], sim["conta"]
    data = args["data_primeiro_pagamento"]
    emp = ctx.caso["empresa_id"]
    primeiro = round(_primeiro_pagamento(cond, conta), 2)
    obs = f"Acordo pelo assistente: {_resumo_conta(cond, conta)}."
    item = fonte.criar_agenda(emp, dev, "promessa", data, valor=primeiro, observacao=obs)
    fonte.registrar_oferta(emp, dev, {
        "canal": "whatsapp", "resposta": "aceitou", "familia": oferta.familia(cond["n_parcelas"], cond["desconto_pct"]),
        **cond, "valor_divida": _dados(ctx)["divida"], "valor_negociado": conta["valor_negociado"],
        "entrada": conta["entrada"], "parcela": conta["parcela"], "total_pago": conta["total_pago"],
        "agenda_data": data, "observacao": f"Simulação {sim['id']}"})
    d = _dados(ctx)
    d["simulacoes"] = [s for s in d.get("simulacoes") or [] if s["id"] != sim["id"]]   # usa uma vez só
    d["acordo"] = {"simulacao_id": sim["id"], "condicoes": cond, "primeiro_pagamento": primeiro, "data": data}
    _ir_para(ctx, "acordo_ativo")
    ctx.caso["proxima_data"] = data
    return {"ok": True, "registrado": True, "resumo": _resumo_conta(cond, conta),
            "primeiro_pagamento": primeiro, "data": data, "compromisso_id": item["id"]}


def _agendar_retorno(ctx, fonte, dev, args):
    item = fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", args["data"], hora=args.get("hora"),
                              observacao=f"Retorno combinado pelo assistente: {args['motivo']}")
    ctx.caso["proxima_data"] = args["data"]
    return {"ok": True, "compromisso_id": item["id"], "data": args["data"], "hora": args.get("hora"),
            "_rastreio": {"compromisso": "retorno", "data": args["data"], "hora": args.get("hora")}}


def _marcar_atendimento_humano(ctx, fonte, dev, args):
    """O devedor quer falar com uma pessoa num dia e horário: vai para a agenda de
    quem cuida dele; sem responsável, para o administrador escolher o operador."""
    from agente.fonte import NOME_A_DEFINIR, OPERADOR_A_DEFINIR
    if dev.get("responsavel_id"):
        operador = (dev["responsavel_id"], dev.get("responsavel_nome") or "")
    else:
        operador = (OPERADOR_A_DEFINIR, NOME_A_DEFINIR)
    from agente import supervisor
    resumo = supervisor.resumo_para_pessoa(ctx, f"atendimento marcado ({args['motivo']})", args["resumo"],
                                           motivo_codigo="atendimento_marcado")
    item = fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", args["data"], hora=args["hora"],
                              operador=operador,
                              observacao=f"Atendimento com pessoa pedido pelo devedor ({args['motivo']}): {resumo}")
    d = _dados(ctx)
    d["atendimento"] = {"data": args["data"], "hora": args["hora"], "compromisso_id": item["id"],
                        "atendente": operador[1] if operador[0] != OPERADOR_A_DEFINIR else None}
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "com_pessoa")
    ctx.caso["resumo"] = resumo
    ctx.caso["proxima_data"] = args["data"]
    return {"ok": True, "marcado": True, "data": args["data"], "hora": args["hora"],
            "atendente": d["atendimento"]["atendente"] or "uma pessoa da equipe",
            "_rastreio": {"compromisso": "atendimento", "data": args["data"], "hora": args["hora"],
                          "a_definir": operador[0] == OPERADOR_A_DEFINIR}}


def _registrar_contato(ctx, fonte, dev, args):
    fonte.registrar_contato(ctx.caso["empresa_id"], dev, args["resultado"],
                            f"Assistente: {args.get('observacao') or ''}".strip())
    return {"ok": True}


def _consultar_politica(ctx, fonte, dev, args):
    regras, versao = ctx.politica()
    if regras is None:
        return {"ok": False, "erro": "a empresa não tem política ativa"}
    return {"ok": True, "versao": versao, "regras": regras,
            "aviso": "limites internos: não ofereça o máximo de saída"}


def _consultar_base(ctx, fonte, dev, args):
    """Busca na base do devedor. Não precisa de identidade: é informação geral."""
    achado = conhecimento.consultar(args["pergunta"])
    t = achado["trecho"]
    if t is None:
        return {"ok": True, "certeza": False,
                "orientacao": "A base não tem resposta segura para isso. Diga que não tem essa informação "
                              "e ofereça falar com uma pessoa da equipe. Não responda de memória.",
                "_rastreio": {"certeza": False}}
    # O trecho fica guardado no caso: numa mensagem seguinte o agente ainda
    # pode citar a mesma fonte sem consultar de novo.
    d = _dados(ctx)
    d["base_consultada"] = ([i for i in d.get("base_consultada") or [] if i != t.id] + [t.id])[-MAX_FONTES_GUARDADAS:]
    return {"ok": True, "certeza": True, "resposta": t.resposta, "fonte": t.fonte, "trecho_oficial": t.trecho,
            "_rastreio": {"certeza": True, "trecho_id": t.id, "fontes": [t.fonte]}}


def _abrir_contestacao(ctx, fonte, dev, args):
    if ctx.caso["situacao"] != "contestado":
        fonte.abrir_contestacao(ctx.caso["empresa_id"], ctx.caso["id"], args["motivo"])
        _ir_para(ctx, "contestado")
    return {"ok": True, "cobranca_suspensa": True}


def _suspender_cobranca(ctx, fonte, dev, args):
    _dados(ctx)["suspensao"] = {"motivo": args["motivo"], "detalhe": args.get("detalhe")}
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "suspenso")
    return {"ok": True, "cobranca_suspensa": True}


def _transferir_para_humano(ctx, fonte, dev, args):
    from agente import supervisor
    resumo = supervisor.resumo_para_pessoa(ctx, f"transferido ({args['motivo']})", args["resumo"],
                                           motivo_codigo=args["motivo"])
    fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", _hoje(ctx).isoformat(),
                       observacao=f"Transferido pelo assistente ({args['motivo']}): {resumo}")
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "com_pessoa")
    ctx.caso["resumo"] = resumo
    return {"ok": True, "transferido": True}


def _remarcar_compromisso(ctx, fonte, dev, args):
    ok = fonte.atualizar_agenda(ctx.caso["empresa_id"], dev["id"], args["compromisso_id"],
                                {"data": args["data"], "observacao": f"Remarcado pelo assistente: {args['motivo']}"})
    if not ok:
        return {"ok": False, "erro": "compromisso não encontrado ou já resolvido"}
    d = _dados(ctx)
    d["remarcacoes"] = int(d.get("remarcacoes") or 0) + 1
    ctx.caso["proxima_data"] = args["data"]
    return {"ok": True, "data": args["data"]}


def _registrar_pagamento_informado(ctx, fonte, dev, args):
    _dados(ctx)["pagamento_informado"] = {"data": args["data"], "valor": args.get("valor")}
    valor = f" de {_brl(args['valor'])}" if args.get("valor") else ""
    fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", _hoje(ctx).isoformat(),
                       observacao=f"Devedor informa pagamento{valor} em {args['data']}: conferir")
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "pagamento_em_conferencia")
    return {"ok": True, "em_conferencia": True}


def _marcar_promessa_quebrada(ctx, fonte, dev, args):
    ok = fonte.atualizar_agenda(ctx.caso["empresa_id"], dev["id"], args["compromisso_id"],
                                {"situacao": "quebrada", "resolvido_em": ctx.agora.isoformat(),
                                 "resolvido_por": f"assistente: {args['motivo']}"[:120]})
    return {"ok": True} if ok else {"ok": False, "erro": "compromisso não encontrado ou já resolvido"}


_DATA = {"type": "string", "format": "date", "maxLength": 10, "description": "AAAA-MM-DD"}
_TEXTO = {"type": "string", "maxLength": 300}
_HORA = {"type": "string", "maxLength": 5, "pattern": r"([01]\d|2[0-3]):[0-5]\d", "description": "HH:MM, 24 horas"}

FERRAMENTAS = {f.nome: f for f in (
    Ferramenta("consultar_caso", "Situação do caso. Valores e compromissos só depois de confirmar a identidade.",
               {}, (), "consultar_caso", _consultar_caso),
    Ferramenta("verificar_identidade", "Confere os três primeiros dígitos do CPF informados pelo devedor.",
               {"tres_primeiros_digitos_cpf": {"type": "string", "maxLength": 20}},
               ("tres_primeiros_digitos_cpf",), "verificar_identidade", _verificar_identidade),
    Ferramenta("listar_ofertas", "Ofertas do catálogo da empresa que cabem na política, com valores.",
               {}, (), "listar_ofertas", _listar_ofertas, exige_identidade=True),
    Ferramenta("simular_acordo", "Calcula os valores exatos de um acordo e diz se está na política e se cabe "
               "no que o devedor disse que pode pagar por mês. Use antes de dizer qualquer valor.",
               {"desconto_pct": {"type": "number", "minimum": 0, "maximum": 95},
                "n_parcelas": {"type": "integer", "minimum": 1, "maximum": 120},
                "entrada_pct": {"type": "number", "minimum": 0, "maximum": 90},
                "cabe_por_mes": {"type": "number", "minimum": 0, "maximum": 10_000_000}},
               ("n_parcelas",), "simular_acordo", _simular_acordo, exige_identidade=True),
    Ferramenta("registrar_aceite", "Registra o acordo aceito pelo devedor, a partir de uma simulação.",
               {"simulacao_id": {"type": "string", "maxLength": 40}, "data_primeiro_pagamento": _DATA},
               ("simulacao_id", "data_primeiro_pagamento"), "registrar_aceite", _registrar_aceite,
               exige_identidade=True),
    Ferramenta("agendar_retorno", "Marca na agenda um novo contato do assistente com o devedor, numa data (e hora, "
               "se combinada). Só diga que agendou depois que esta ferramenta devolver ok.",
               {"data": _DATA, "hora": _HORA, "motivo": _TEXTO}, ("data", "motivo"), "agendar_retorno", _agendar_retorno),
    Ferramenta("marcar_atendimento_humano", "O devedor aceitou falar com uma pessoa da equipe num dia e horário: "
               "marca o atendimento na agenda da equipe, com resumo, e a pessoa assume o caso. Pergunte o dia e a "
               "hora antes. Para atendimento imediato, use transferir_para_humano.",
               {"data": _DATA, "hora": _HORA,
                "motivo": {"type": "string", "enum": ["pedido_do_devedor", "reuniao", "duvida", "dificuldade"]},
                "resumo": _TEXTO}, ("data", "hora", "motivo", "resumo"), "marcar_atendimento", _marcar_atendimento_humano),
    Ferramenta("registrar_contato", "Registra um contato sem acordo.",
               {"resultado": {"type": "string", "enum": ["contactado", "sem_resposta", "nao_quis"]},
                "observacao": _TEXTO}, ("resultado",), "registrar_contato", _registrar_contato),
    Ferramenta("consultar_base", "Base de conhecimento com lei e súmula para dúvidas do devedor: quanto tempo o nome "
               "fica negativado, quando sai depois de pagar, comprovante, cobrança indevida, multa, pagamento "
               "antecipado, dados pessoais, revisão de decisão automática, superendividamento. Devolve a resposta "
               "com a fonte, ou certeza=false quando não sabe. Use antes de citar qualquer lei ou súmula.",
               {"pergunta": {"type": "string", "maxLength": 300,
                             "description": "A dúvida do devedor, em poucas palavras"}},
               ("pergunta",), "consultar_base", _consultar_base),
    Ferramenta("consultar_politica", "Limites da empresa para negociar (uso interno, não divulgar de saída).",
               {}, (), "consultar_politica", _consultar_politica),
    Ferramenta("abrir_contestacao", "O devedor não reconhece a dívida: suspende a cobrança e abre contestação.",
               {"motivo": _TEXTO}, ("motivo",), "registrar_contestacao", _abrir_contestacao),
    Ferramenta("suspender_cobranca", "Pessoa errada ou pedido para não ser mais contatado.",
               {"motivo": {"type": "string", "enum": ["pessoa_errada", "pediu_para_parar", "outro"]},
                "detalhe": _TEXTO}, ("motivo",), "suspender_contato", _suspender_cobranca),
    Ferramenta("transferir_para_humano", "Passa o caso para uma pessoa da equipe, com resumo.",
               {"motivo": {"type": "string", "enum": ["pedido_do_devedor", "fora_da_politica", "dificuldade_grave",
                                                      "duvida", "falha"]},
                "resumo": _TEXTO}, ("motivo", "resumo"), "transferir_para_pessoa", _transferir_para_humano),
    Ferramenta("remarcar_compromisso", "Nova data para uma promessa ou retorno, dentro da política.",
               {"compromisso_id": {"type": "string", "maxLength": 40}, "data": _DATA, "motivo": _TEXTO},
               ("compromisso_id", "data", "motivo"), "remarcar_compromisso", _remarcar_compromisso,
               exige_identidade=True),
    Ferramenta("registrar_pagamento_informado", "O devedor diz que já pagou: anota o aviso, suspende a cobrança e pede "
               "conferência à equipe. Não confirma pagamento: só o banco confirma.",
               {"data": _DATA, "valor": {"type": "number", "minimum": 0, "maximum": 100_000_000}},
               ("data",), "registrar_pagamento_informado", _registrar_pagamento_informado),
    Ferramenta("marcar_promessa_quebrada", "A promessa venceu sem pagamento e sem nova data.",
               {"compromisso_id": {"type": "string", "maxLength": 40}, "motivo": _TEXTO},
               ("compromisso_id", "motivo"), "marcar_promessa_quebrada", _marcar_promessa_quebrada,
               exige_identidade=True),
)}


def definicoes() -> list:
    return [f.definicao() for f in FERRAMENTAS.values()]


def executar(ctx, fonte, nome: str, args) -> dict:
    """Valida, passa pelo Auditor, executa e registra. Devolve o resultado para a IA."""
    f = FERRAMENTAS.get(nome)
    if f is None:
        ctx.auditar({"tipo": f"ferramenta_desconhecida:{str(nome)[:40]}", "params": {}})
        return {"ok": False, "erro": f"ferramenta desconhecida: {nome}"}
    erro = _validar(f, args)
    if erro:
        return {"ok": False, "erro": erro}
    if "_devedor" not in ctx.saida:
        ctx.saida["_devedor"] = fonte.devedor(ctx.caso["empresa_id"], ctx.caso["predicao_id"])
    dev = ctx.saida["_devedor"]
    if dev is None:
        return {"ok": False, "erro": "devedor não encontrado nesta empresa"}
    if f.exige_identidade and not _dados(ctx).get("identidade_ok"):
        return {"ok": False, "erro": "confirme a identidade antes (verificar_identidade)"}

    params, extra = dict(args), {}
    if nome == "registrar_aceite":
        params, extra["simulacao"] = _params_aceite(ctx, args)
        extra["ironia"] = bool((ctx.saida.get("triagem") or {}).get("ironia"))
    decisao = ctx.auditar({"tipo": f.acao, "params": params}, **extra)
    if not decisao["permitida"]:
        return {"ok": False, "bloqueado": True, "regra": decisao["regra"], "motivo": decisao["motivo"]}
    with ctx.rastreio.span(f"ferramenta:{nome}", "ferramenta") as p:
        r = f.executar(ctx, fonte, dev, args)
        # `_rastreio` é só para o passo (fontes, ids); não volta para a IA.
        p["detalhe"] = {"ok": bool(r.get("ok")), **r.pop("_rastreio", {})}
    return r
