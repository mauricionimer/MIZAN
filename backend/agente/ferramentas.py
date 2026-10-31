"""As 17 ferramentas do Negociador (docs/PLANO_AGENTE.md, 3.2).

Toda chamada segue o mesmo caminho:

    nome e argumentos validados → Auditor decide → executa → passo no rastreio

- A IA nunca recebe CPF, renda nem dados de outro devedor: só primeiro nome,
  valores da dívida (depois de confirmar a identidade), datas e situação.
- Todo valor que a IA vai dizer sai de `simular_acordo`; o aceite só vale para
  uma simulação feita aqui (o Auditor confere).
- Toda lei ou súmula que a IA vai citar sai de `consultar_base` (a base de
  conhecimento do devedor, agente/conhecimento.py), e só quando a pessoa pede a lei.
- Ações com impacto jurídico (aceite de acordo, contestação, pedido sobre os próprios
  dados) passam antes pela base jurídica interna (agente/juridico, via
  ctx.consultar_juridico). A análise fica no registro interno; a IA recebe só o que
  fazer, sem lei e sem a análise.
- Erros de uso voltam como resultado ({"ok": false, "erro": ...}) para a IA
  corrigir; falha de verdade (banco fora) sobe e o orquestrador trata.
"""
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from agente import auditor, conhecimento, estado, guardrails, juridico_orq
from agente.juridico import sinais
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
        r["cabe_no_bolso"] = oferta.cabe(cond, conta, cabe)
    return r


def _params_aceite(ctx, args):
    sim = _simulacao(ctx, args["simulacao_id"])
    cond = sim["condicoes"] if sim else {}
    return {**cond, "simulacao_id": args["simulacao_id"], "data": args["data_primeiro_pagamento"]}, sim


def _fatos_oferta(ctx, sim: dict) -> dict:
    """Fatos mínimos do aceite, conferidos em código no que já foi dito na conversa."""
    cond, conta = sim["condicoes"], sim["conta"]
    msgs = estado.conversa_atual(ctx.caso, ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 30))
    ditos, do_agente, do_devedor = set(), [], [ctx.saida.get("texto") or ""]
    for m in msgs:
        if m.get("direcao") == "saida":
            ditos |= set(guardrails.valores_do_texto(m.get("texto") or "")["dinheiro"])
            do_agente.append(m.get("texto") or "")
        else:
            do_devedor.append(m.get("texto") or "")

    def mostrou(v):
        return any(abs(float(v) - x) <= guardrails.TOLERANCIA for x in ditos)
    n = int(cond["n_parcelas"])
    return {"informa_total": mostrou(conta["total_pago"]), "informa_parcelas": n == 1 or mostrou(conta["parcela"]),
            "sinais_superendividamento": any(sinais.superendividamento(t) for t in do_devedor),
            "pressao": any(sinais.pressao(t) for t in do_agente), "n_parcelas": n}


def _conferir_aceite(ctx, fonte, sim: dict, data: str) -> dict | None:
    """Base jurídica antes de registrar o acordo. None = pode registrar."""
    fatos = _fatos_oferta(ctx, sim)
    j = ctx.consultar_juridico("oferta_credito", fatos)
    if j["decisao"] not in juridico_orq.BLOQUEIA:
        return None
    cond, conta = sim["condicoes"], sim["conta"]
    resumo = _resumo_conta(cond, conta)
    if not (fatos["informa_total"] and fatos["informa_parcelas"]) and not fatos["pressao"]:
        # O que falta a IA consegue corrigir: mostrar a conta inteira e pedir a confirmação.
        return {"ok": False, "bloqueado": True,
                "motivo": f"antes de registrar, mostre à pessoa o valor total ({_brl(conta['total_pago'])}), o número "
                          f"de parcelas e o valor de cada uma ({resumo}) e peça que ela confirme"}
    # O resto (sinais de superendividamento, fonte por conferir, pressão) é com uma pessoa.
    motivo = "dificuldade_grave" if fatos["sinais_superendividamento"] else "duvida"
    conferir = ("se o acordo cabe no orçamento dela (ela relatou dificuldade com as contas)"
                if fatos["sinais_superendividamento"] else "as condições com ela")
    r = executar(ctx, fonte, "transferir_para_humano", {"motivo": motivo, "resumo":
        f"A pessoa aceitou {resumo}, 1º pagamento em {_dia(data)}. O acordo ainda não foi registrado: uma pessoa "
        f"da equipe confere antes {conferir}."})
    return {"ok": False, "bloqueado": True, "com_pessoa": bool(r.get("ok")),
            "motivo": "uma pessoa da equipe vai confirmar o acordo com ela"}


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


# ── compromissos combinados com o devedor ──────────────────────────────────
# Uma pessoa tem no máximo UM compromisso ativo de cada tipo com o agente: um retorno
# (o assistente volta a falar) e um atendimento (uma pessoa da equipe). Marcar de novo
# move o que existe; repetir a mesma marcação não cria outra (a IA pode chamar de novo,
# e a rodada pode ser refeita depois de uma falha). Promessa de pagamento é outra coisa:
# nasce do acordo e só muda por remarcar_compromisso, com identidade confirmada.
PREFIXO_RETORNO = "Retorno combinado pelo assistente"
PREFIXO_ATENDIMENTO = "Atendimento com pessoa pedido pelo devedor"
_O_QUE = {"retorno": "retorno do assistente", "atendimento": "atendimento com uma pessoa da equipe",
          "promessa": "promessa de pagamento"}


def tipo_do_compromisso(a: dict) -> str:
    """retorno, atendimento, promessa ou outro (tarefa interna da equipe: não é combinado com o devedor)."""
    obs = a.get("observacao") or ""
    if a.get("tipo") == "promessa":
        return "promessa"
    if obs.startswith(PREFIXO_ATENDIMENTO):
        return "atendimento"
    if a.get("tipo") == "retorno" and (obs.startswith(PREFIXO_RETORNO) or obs.startswith("Remarcado pelo assistente")):
        return "retorno"
    return "outro"


def compromissos_combinados(pendentes: list, identidade_ok: bool) -> list:
    """O que está marcado com a pessoa, para o briefing (com o id, para remarcar ou desmarcar)."""
    saida = []
    for a in sorted(pendentes or [], key=lambda a: (str(a.get("data")), str(a.get("hora") or ""))):
        t = tipo_do_compromisso(a)
        if t == "outro":
            continue
        item = {"compromisso_id": a["id"], "o_que": _O_QUE[t], "data": str(a.get("data"))[:10], "hora": a.get("hora")}
        if t == "atendimento" and a.get("operador_id") == _a_definir():
            item["situacao"] = "aguardando aprovação da equipe"
        if t == "promessa" and identidade_ok and a.get("valor") is not None:
            item["valor"] = a.get("valor")
        saida.append(item)
    return saida


def _a_definir():
    from agente.fonte import OPERADOR_A_DEFINIR
    return OPERADOR_A_DEFINIR


def _meus(ctx, fonte, dev, tipo: str) -> list:
    """Compromissos ativos deste tipo com a pessoa, do mais antigo para o mais novo."""
    itens = [a for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"]) if tipo_do_compromisso(a) == tipo]
    return sorted(itens, key=lambda a: (str(a.get("data")), str(a.get("hora") or "")))


def _dia(iso) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m")
    except ValueError:
        return str(iso)


def _mover(ctx, fonte, dev, item: dict, data: str, hora, motivo: str) -> bool:
    """Leva o compromisso para outro dia (e hora). A hora antiga fica se não vier outra."""
    hora = hora or item.get("hora")
    obs = (item.get("observacao") or "").split(" · Remarcado")[0]
    campos = {"data": data, "hora": hora,
              "observacao": f"{obs} · Remarcado pelo assistente (era {_dia(item.get('data'))}"
                            f"{' às ' + item['hora'] if item.get('hora') else ''}): {motivo}"[:500]}
    if tipo_do_compromisso(item) == "atendimento" and item.get("operador_id") not in (None, _a_definir()):
        # Já aprovado para um horário: o novo horário volta para a aprovação da equipe.
        from agente.fonte import NOME_A_DEFINIR
        campos.update(operador_id=_a_definir(), operador_nome=NOME_A_DEFINIR)
    return fonte.atualizar_agenda(ctx.caso["empresa_id"], dev["id"], item["id"], campos)


def _fechar_sobras(ctx, fonte, dev, sobras: list) -> None:
    """Duplicatas de antes desta regra: ficam canceladas, sobra um compromisso só."""
    for a in sobras:
        fonte.atualizar_agenda(ctx.caso["empresa_id"], dev["id"], a["id"],
                               {"situacao": "cancelada", "resolvido_em": ctx.agora.isoformat(),
                                "resolvido_por": "assistente: compromisso repetido"})


def _marcar_ou_mover(ctx, fonte, dev, tipo: str, data: str, hora, motivo: str, criar) -> dict:
    """Marca o compromisso do tipo; se já há um, move (ou devolve o mesmo, se nada mudou)."""
    existentes = _meus(ctx, fonte, dev, tipo)
    if not existentes:
        item = criar()
        return {"compromisso_id": item["id"], "data": data, "hora": hora, "novo": True}
    alvo, sobras = existentes[-1], existentes[:-1]
    _fechar_sobras(ctx, fonte, dev, sobras)
    if str(alvo.get("data"))[:10] == data and (not hora or str(alvo.get("hora") or "")[:5] == str(hora)[:5]):
        return {"compromisso_id": alvo["id"], "data": data, "hora": alvo.get("hora"), "ja_estava_marcado": True}
    if not _mover(ctx, fonte, dev, alvo, data, hora, motivo):
        item = criar()                                  # sumiu entre a leitura e a mudança: marca de novo
        return {"compromisso_id": item["id"], "data": data, "hora": hora, "novo": True}
    return {"compromisso_id": alvo["id"], "data": data, "hora": hora or alvo.get("hora"),
            "remarcado_de": {"data": str(alvo.get("data"))[:10], "hora": alvo.get("hora")}}


def _agendar_retorno(ctx, fonte, dev, args):
    r = _marcar_ou_mover(ctx, fonte, dev, "retorno", args["data"], args.get("hora"), args["motivo"],
                         lambda: fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", args["data"],
                                                    hora=args.get("hora"),
                                                    observacao=f"{PREFIXO_RETORNO}: {args['motivo']}"))
    ctx.caso["proxima_data"] = r["data"]
    return {"ok": True, **{k: v for k, v in r.items() if k != "novo"},
            "_rastreio": {"compromisso": "retorno", "data": r["data"], "hora": r.get("hora"),
                          "remarcado": bool(r.get("remarcado_de")), "repetido": bool(r.get("ja_estava_marcado"))}}


def _marcar_atendimento_humano(ctx, fonte, dev, args):
    """Solicita uma reunião; só o administrador aprova e define quem atende."""
    from agente.fonte import NOME_A_DEFINIR, OPERADOR_A_DEFINIR
    operador = (OPERADOR_A_DEFINIR, NOME_A_DEFINIR)
    from agente import supervisor
    resumo = supervisor.resumo_para_pessoa(ctx, f"atendimento marcado ({args['motivo']})", args["resumo"],
                                           motivo_codigo="atendimento_marcado", usar_ia=False)
    r = _marcar_ou_mover(ctx, fonte, dev, "atendimento", args["data"], args["hora"], args["resumo"],
                         lambda: fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", args["data"],
                                                    hora=args["hora"], operador=operador,
                                                    observacao=f"{PREFIXO_ATENDIMENTO} ({args['motivo']}): {resumo}"))
    d = _dados(ctx)
    d["atendimento"] = {"data": r["data"], "hora": r["hora"], "compromisso_id": r["compromisso_id"],
                        "atendente": None, "aprovacao": "pendente",
                        "operador_sugerido_id": dev.get("responsavel_id")}
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "com_pessoa")
    ctx.caso["resumo"] = resumo
    ctx.caso["proxima_data"] = args["data"]
    return {"ok": True, "marcado": False, "aguardando_aprovacao": True, "data": r["data"], "hora": r["hora"],
            "compromisso_id": r["compromisso_id"],
            **({"remarcado_de": r["remarcado_de"]} if r.get("remarcado_de") else {}),
            **({"ja_estava_marcado": True} if r.get("ja_estava_marcado") else {}),
            "atendente": d["atendimento"]["atendente"] or "uma pessoa da equipe",
            "_rastreio": {"compromisso": "atendimento", "data": r["data"], "hora": r["hora"],
                          "a_definir": operador[0] == OPERADOR_A_DEFINIR,
                          "remarcado": bool(r.get("remarcado_de")), "repetido": bool(r.get("ja_estava_marcado"))}}


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
    # Só a resposta e a fonte: o texto literal da lei (t.trecho) fica na base para
    # conferência, mas a IA não recebe o que não pode citar. A norma só vai quando a
    # pessoa pediu a lei ou o fundamento; senão, o direito em palavras simples.
    rastreio = {"certeza": True, "trecho_id": t.id, "fontes": [t.fonte]}
    if sinais.pediu_fundamento(ctx.saida.get("texto") or ""):
        return {"ok": True, "certeza": True, "resposta": t.resposta, "fonte": t.fonte, "_rastreio": rastreio}
    return {"ok": True, "certeza": True, "resposta": conhecimento.sem_citacao(t.resposta),
            "orientacao": "Responda com essas palavras, sem citar lei, artigo, súmula ou tribunal. Se a pessoa "
                          "pedir a lei ou o fundamento, consulte de novo e diga a fonte.",
            "_rastreio": rastreio}


def _abrir_contestacao(ctx, fonte, dev, args):
    if hasattr(ctx, "consultar_juridico"):
        # Registro interno: a contestação suspende a cobrança e vai para análise humana.
        # Ação de segurança: a consulta registra, nunca impede a contestação.
        ctx.consultar_juridico("contestacao", {"motivo": "devedor_nao_reconhece"})
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
                                           motivo_codigo=args["motivo"], usar_ia=False)
    item = next((a for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])
                 if (a.get("observacao") or "").startswith("Transferido pelo assistente (")), None)
    if item is None:
        item = fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", _hoje(ctx).isoformat(),
                                  observacao=f"Transferido pelo assistente ({args['motivo']}): {resumo}")
    if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA:
        _ir_para(ctx, "com_pessoa")
    ctx.caso["resumo"] = resumo
    return {"ok": True, "transferido": True, "compromisso_id": item["id"]}


def _alvo(ctx, fonte, dev, compromisso_id: str | None, tipos=("retorno", "atendimento", "promessa")):
    """(compromisso, erro). Sem id: o único compromisso ativo do agente com a pessoa."""
    pendentes = [a for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])
                 if tipo_do_compromisso(a) in tipos]
    if compromisso_id:
        achado = next((a for a in pendentes if a["id"] == compromisso_id), None)
        return (achado, None) if achado else (None, "compromisso não encontrado ou já resolvido")
    if not pendentes:
        return None, "não há compromisso marcado com a pessoa"
    # Sem id: o retorno ou atendimento marcado; se não houver, a única promessa.
    candidatos = [a for a in pendentes if tipo_do_compromisso(a) in ("retorno", "atendimento")] or pendentes
    if len({tipo_do_compromisso(a) for a in candidatos}) == 1:
        return sorted(candidatos, key=lambda a: str(a.get("data")))[-1], None
    return None, ("há mais de um compromisso marcado: diga qual pelo compromisso_id (" +
                  ", ".join(f"{a['id']} = {_O_QUE.get(tipo_do_compromisso(a))} em {_dia(a.get('data'))}"
                            for a in pendentes) + ")")


def _params_remarcar(ctx, fonte, dev, args) -> tuple:
    """Parâmetros para o Auditor: o tipo decide se vale o limite de remarcações (só promessa)."""
    alvo, erro = _alvo(ctx, fonte, dev, args.get("compromisso_id"))
    tipo = tipo_do_compromisso(alvo) if alvo else None
    params = {**args, "tipo_compromisso": tipo}
    if not args.get("hora") and alvo and alvo.get("hora"):
        params["hora"] = str(alvo["hora"])[:5]           # a hora que fica também precisa valer no dia novo
    return params, alvo, erro


def _remarcar_compromisso(ctx, fonte, dev, args):
    alvo, erro = ctx.saida.pop("_alvo_remarcar", (None, None))
    if alvo is None:
        alvo, erro = _alvo(ctx, fonte, dev, args.get("compromisso_id"))
    if alvo is None:
        return {"ok": False, "erro": erro}
    tipo = tipo_do_compromisso(alvo)
    if tipo == "promessa" and not _dados(ctx).get("identidade_ok"):
        return {"ok": False, "erro": "confirme a identidade antes (verificar_identidade)"}
    if not _mover(ctx, fonte, dev, alvo, args["data"], args.get("hora"), args["motivo"]):
        return {"ok": False, "erro": "compromisso não encontrado ou já resolvido"}
    d = _dados(ctx)
    if tipo == "promessa":
        d["remarcacoes"] = int(d.get("remarcacoes") or 0) + 1       # o limite da política é para pagamento
    hora = args.get("hora") or alvo.get("hora")
    if tipo == "atendimento" and d.get("atendimento"):
        d["atendimento"] = {**d["atendimento"], "data": args["data"], "hora": hora, "aprovacao": "pendente",
                            "atendente": None}             # horário novo: a equipe aprova e escolhe de novo
    ctx.caso["proxima_data"] = args["data"]
    return {"ok": True, "compromisso_id": alvo["id"], "o_que": _O_QUE.get(tipo), "data": args["data"], "hora": hora,
            "remarcado_de": {"data": str(alvo.get("data"))[:10], "hora": alvo.get("hora")}}


def _desmarcar_compromisso(ctx, fonte, dev, args):
    alvo, erro = _alvo(ctx, fonte, dev, args.get("compromisso_id"), tipos=("retorno", "atendimento"))
    if alvo is None:
        if args.get("compromisso_id") and any(a["id"] == args["compromisso_id"] and tipo_do_compromisso(a) == "promessa"
                                              for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])):
            return {"ok": False, "erro": "promessa de pagamento não se desmarca: remarque a data ou fale com a equipe"}
        return {"ok": False, "erro": erro}
    ok = fonte.atualizar_agenda(ctx.caso["empresa_id"], dev["id"], alvo["id"],
                                {"situacao": "cancelada", "resolvido_em": ctx.agora.isoformat(),
                                 "resolvido_por": f"assistente: {args['motivo']}"[:120]})
    if not ok:
        return {"ok": False, "erro": "compromisso não encontrado ou já resolvido"}
    tipo = tipo_do_compromisso(alvo)
    d = _dados(ctx)
    if tipo == "atendimento" and (d.get("atendimento") or {}).get("compromisso_id") == alvo["id"]:
        d.pop("atendimento", None)
    return {"ok": True, "desmarcado": True, "compromisso_id": alvo["id"], "o_que": _O_QUE.get(tipo),
            "era": {"data": str(alvo.get("data"))[:10], "hora": alvo.get("hora")}}


# ── pedido do titular sobre os próprios dados ───────────────────────────────
# O direito é da pessoa e não depende da cobrança: o pedido é registrado sempre, para a
# pessoa responsável pelos dados responder. Apagar, opor-se, revogar o consentimento ou
# pedir revisão de decisão automatizada tira a conversa do automático (uma pessoa assume).
PREFIXO_PEDIDO_TITULAR = "Pedido sobre os dados pessoais"
TIPOS_PEDIDO = tuple(sinais.ROTULO_PEDIDO)
PEDIDO_COM_PESSOA = frozenset({"eliminacao", "oposicao", "revogacao", "revisao_decisao"})
# O que a pessoa tem direito de saber, em palavras simples (sem citar lei). Conferido
# com a LGPD (arts. 18 a 20) no acervo jurídico; quem responde o pedido é uma pessoa.
O_QUE_DIZER_PEDIDO = {
    "acesso": "Ela pode saber se a empresa trata dados dela e receber o que a empresa tem sobre ela. O pedido foi "
              "registrado; a resposta completa sai em até 15 dias.",
    "origem": "Ela pode saber de onde vieram os dados dela. O pedido foi registrado; a resposta completa sai em até "
              "15 dias.",
    "informacao": "Ela pode saber para que os dados dela são usados e com quem foram compartilhados. O pedido foi "
                  "registrado para a pessoa responsável pelos dados responder.",
    "correcao": "Ela pode pedir a correção de dados incompletos, errados ou desatualizados. O pedido foi registrado; "
                "a pessoa responsável confere e corrige.",
    "portabilidade": "O pedido de portabilidade dos dados foi registrado; a pessoa responsável analisa e responde.",
    "eliminacao": "O pedido de eliminação dos dados foi registrado. A pessoa responsável analisa e responde; se algum "
                  "dado precisar ser mantido (por exemplo, o registro da dívida e dos pagamentos), a resposta explica o motivo.",
    "oposicao": "Ficou registrado que ela se opõe ao uso dos dados. A pessoa responsável analisa e responde.",
    "revogacao": "Ficou registrada a revogação do consentimento. A pessoa responsável analisa o que muda e responde.",
    "revisao_decisao": "Ela pode pedir a revisão de uma decisão tomada só pelo sistema e saber os critérios usados. "
                       "O pedido foi registrado e uma pessoa da equipe vai revisar.",
}


def _registrar_pedido_titular(ctx, fonte, dev, args):
    tipo = args["tipo"]
    rotulo = sinais.ROTULO_PEDIDO[tipo]
    d = _dados(ctx)
    ja = (ctx.saida.get("_pedido_titular") or {}).get("tipo") == tipo      # mesmo pedido nesta rodada
    if not ja:
        j = ctx.consultar_juridico("pedido_titular", {"tipo": tipo}) if hasattr(ctx, "consultar_juridico") else {}
        obs = f"{PREFIXO_PEDIDO_TITULAR} ({rotulo}): registrado pelo assistente. A pessoa responsável pelos dados " \
              "analisa e responde" + (" em até 15 dias" if tipo in ("acesso", "origem") else "") + "."
        item = next((a for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])
                     if (a.get("observacao") or "") == obs), None)
        if item is None:
            item = fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", _hoje(ctx).isoformat(), observacao=obs)
        d["pedidos_titular"] = ((d.get("pedidos_titular") or []) + [
            {"tipo": tipo, "em": ctx.agora.isoformat(), "compromisso_id": item["id"],
             "registro_juridico": j.get("registro_id"), "decisao": j.get("decisao")}])[-10:]
        ctx.saida["_pedido_titular"] = {"tipo": tipo, "rotulo": rotulo}
    transferido = False
    if tipo in PEDIDO_COM_PESSOA and ctx.pode_falar:
        r = executar(ctx, fonte, "transferir_para_humano", {
            "motivo": "pedido_do_devedor",
            "resumo": f"Pedido sobre os dados pessoais ({rotulo}). Uma pessoa responsável analisa e responde."})
        transferido = bool(r.get("ok"))
    return {"ok": True, "registrado": True, "tipo": tipo, "o_que_dizer": O_QUE_DIZER_PEDIDO[tipo],
            "com_pessoa": transferido, "_rastreio": {"pedido_titular": tipo, "repetido": ja}}


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
               "registra uma solicitação na agenda do administrador, que aprova e escolhe o operador. Não confirme a reunião antes da aprovação. Pergunte o dia e a "
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
    Ferramenta("remarcar_compromisso", "Muda o dia (e a hora, se combinada) de um compromisso já marcado: retorno, "
               "atendimento ou promessa de pagamento (promessa exige identidade confirmada). Use o compromisso_id de "
               "compromissos_marcados; sem ele, vale o único retorno ou atendimento marcado. Não marque outro.",
               {"compromisso_id": {"type": "string", "maxLength": 40}, "data": _DATA, "hora": _HORA, "motivo": _TEXTO},
               ("data", "motivo"), "remarcar_compromisso", _remarcar_compromisso),
    Ferramenta("desmarcar_compromisso", "Desmarca um retorno ou atendimento quando a pessoa não quer mais. Se ela só "
               "não pode naquele dia, pergunte o novo dia e use remarcar_compromisso.",
               {"compromisso_id": {"type": "string", "maxLength": 40}, "motivo": _TEXTO},
               ("motivo",), "desmarcar_compromisso", _desmarcar_compromisso),
    Ferramenta("registrar_pedido_titular", "A pessoa pede algo sobre os próprios dados pessoais: saber quais dados "
               "a empresa tem (acesso), de onde vieram (origem), para que são usados ou com quem foram compartilhados "
               "(informacao), corrigir (correcao), apagar (eliminacao), não permitir o uso (oposicao), revogar o "
               "consentimento (revogacao), revisar uma decisão automática (revisao_decisao) ou portabilidade. Registra "
               "o pedido para a pessoa responsável pelos dados. Depois diga o que vai acontecer, como veio em o_que_dizer.",
               {"tipo": {"type": "string", "enum": list(TIPOS_PEDIDO)}}, ("tipo",), "registrar_pedido_titular",
               _registrar_pedido_titular),
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
    if nome == "remarcar_compromisso":
        params, alvo, erro = _params_remarcar(ctx, fonte, dev, args)
        if alvo is None:
            return {"ok": False, "erro": erro}
        ctx.saida["_alvo_remarcar"] = (alvo, None)
    if nome == "registrar_aceite":
        params, extra["simulacao"] = _params_aceite(ctx, args)
        extra["ironia"] = bool((ctx.saida.get("triagem") or {}).get("ironia"))
    decisao = ctx.auditar({"tipo": f.acao, "params": params}, **extra)
    if not decisao["permitida"]:
        return {"ok": False, "bloqueado": True, "regra": decisao["regra"], "motivo": decisao["motivo"]}
    if nome == "registrar_aceite" and extra.get("simulacao") and hasattr(ctx, "consultar_juridico"):
        barrado = _conferir_aceite(ctx, fonte, extra["simulacao"], args["data_primeiro_pagamento"])
        if barrado:
            return barrado
    with ctx.rastreio.span(f"ferramenta:{nome}", "ferramenta") as p:
        r = f.executar(ctx, fonte, dev, args)
        # `_rastreio` é só para o passo (fontes, ids); não volta para a IA.
        p["detalhe"] = {"ok": bool(r.get("ok")), **r.pop("_rastreio", {})}
    return r
