"""Acompanhamento: datas e pagamentos (docs/PLANO_AGENTE.md, 3.4).

Código, sem IA. O relógio olha as promessas de cada caso e gera eventos; os
grafos tratam cada um. A IA só entra quando o devedor responde.

| Situação | O que acontece |
|---|---|
| Vence amanhã ou hoje | Lembrete com valor (mensagem pronta) |
| Pagamento confirmado | Promessa cumprida; agradece; acordo à vista vira quitado |
| Pagou menos | Mostra o que falta; a baixa parcial fica com a equipe |
| Venceu e não pagou | Espera o prazo de confirmação do banco; depois procura o devedor |
| Não respondeu | Promessa quebrada e o caso vai para uma pessoa |

- Vencimento no sábado ou domingo conta no dia útil seguinte. Feriados ainda
  não entram (não há calendário de feriados no Mizan).
- Ninguém é cobrado dentro do prazo de confirmação, com pagamento informado em
  conferência, contestado, suspenso, com uma pessoa ou no grupo sorteado.
"""
from datetime import date, datetime, time, timedelta, timezone

from agente import auditor, estado, ferramentas
from agente.orquestrador import FIM, Grafo, registrar_evento

# O agente não procura estes casos (o grafo confere de novo na hora de agir).
NAO_COBRAR = estado.SO_PESSOA_TIRA | estado.FINAIS | {"pagamento_em_conferencia"}
ATIVAS = ("so_lembrete", "em_contato", "negociando", "acordo_ativo", "atrasado")


def dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def somar_dias_uteis(d: date, n: int) -> date:
    d = dia_util(d)
    for _ in range(n):
        d = dia_util(d + timedelta(days=1))
    return d


def _brl(v) -> str:
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(iso: str) -> str:
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day:02d}/{d.month:02d}"


def _hoje(agora: datetime) -> date:
    return agora.astimezone(auditor.BRASILIA).date()


def proximo_horario(politica: dict, agora: datetime) -> datetime:
    """Próximo início da janela de contato da política (em UTC)."""
    local = agora.astimezone(auditor.BRASILIA)
    d = local.date()
    for _ in range(8):
        inicio = datetime.combine(d, time(politica["hora_inicio"]), auditor.BRASILIA)
        if d.weekday() in politica["dias_semana"] and inicio > local:
            return inicio.astimezone(timezone.utc)
        d += timedelta(days=1)
    return (local + timedelta(days=1)).astimezone(timezone.utc)


def mesma_hora_em(agora: datetime, dias_uteis: int) -> datetime:
    """Daqui a `dias_uteis` dias úteis, na mesma hora de Brasília (em UTC)."""
    local = agora.astimezone(auditor.BRASILIA)
    return datetime.combine(somar_dias_uteis(local.date(), dias_uteis), local.timetz()).astimezone(timezone.utc)


# ── relógio ─────────────────────────────────────────────────────────────────

def planejar(repo, fonte, empresa_id: str, agora: datetime) -> list:
    """Gera os eventos de datas do dia. Idempotente: a chave inclui o compromisso e a fase."""
    achada = repo.politica_ativa(empresa_id)
    if not achada:
        return []
    pol = auditor.validar_politica(achada["regras"])
    hoje = _hoje(agora)
    criados = []
    for caso in repo.casos_da_empresa(empresa_id, ATIVAS):
        if caso.get("grupo_controle"):
            continue
        dev = fonte.devedor(empresa_id, caso["predicao_id"])
        if dev is None:
            continue
        for item in fonte.agenda_pendente(empresa_id, dev["id"]):
            if item.get("tipo") != "promessa":
                continue                                   # retorno é da equipe
            venc = dia_util(date.fromisoformat(str(item["data"])[:10]))
            dados = {"compromisso_id": item["id"], "valor": item.get("valor"), "data": venc.isoformat()}
            fases = []
            if venc - hoje in (timedelta(days=1), timedelta(days=0)):
                # Um lembrete por compromisso e vencimento (não por dia): vencimento na
                # segunda não gera o de domingo (adiado para segunda) e o de segunda.
                fases.append(("lembrete", f"lembrete:{item['id']}:{venc.isoformat()}"))
            confirmacao = somar_dias_uteis(venc, pol["prazo_confirmacao_dias"])
            if hoje > confirmacao:
                fases.append(("venceu", f"venceu:{item['id']}"))
            # Dias úteis contados a partir do dia em que o atraso foi cobrado.
            if hoje >= somar_dias_uteis(somar_dias_uteis(confirmacao, 1), pol["dias_sem_resposta"]):
                fases.append(("sem_resposta", f"sem_resposta:{item['id']}"))
            for fase, chave in fases:
                ev, novo = registrar_evento(repo, empresa_id, caso["id"], "vencimento", chave,
                                            {**dados, "fase": fase}, origem="relogio")
                if novo:
                    criados.append(ev)
    return criados


# ── mensagens prontas (sem IA) ──────────────────────────────────────────────

def texto_lembrete(nome: str, valor, data_iso: str, hoje: date) -> str:
    quando = "hoje" if date.fromisoformat(data_iso) == hoje else "amanhã"
    return (f"Olá, {nome}! Lembrete: o pagamento de {_brl(valor)} combinado com a gente vence {quando} "
            f"({_data_br(data_iso)}). Se já pagou, pode desconsiderar.")


def texto_atraso(nome: str, valor, data_iso: str) -> str:
    return (f"Olá, {nome}. Ainda não identificamos o pagamento de {_brl(valor)} previsto para "
            f"{_data_br(data_iso)}. Aconteceu alguma coisa? Se precisar, podemos combinar uma nova data.")


def texto_pagamento(nome: str, valor, falta: float | None) -> str:
    if falta:
        return (f"Olá, {nome}. Recebemos o seu pagamento de {_brl(valor)}, obrigado! Para completar o valor "
                f"combinado faltam {_brl(falta)}. Nossa equipe vai entrar em contato para acertar.")
    return f"Olá, {nome}. Recebemos o seu pagamento de {_brl(valor)}. Obrigado!"


# ── decisão com IA (cardápio fechado; o código confere) ─────────────────────

VERSAO_PROMPT = "acompanhamento-v2"          # v2: "esperar" no atraso uma vez só, com prazo
CARDAPIO = {"lembrete": ("lembrar", "esperar"),
            "venceu": ("procurar", "oferecer_remarcar", "chamar_pessoa", "esperar"),
            "sem_resposta": ("chamar_pessoa", "esperar_mais")}
COM_MENSAGEM = {"lembrar", "procurar", "oferecer_remarcar"}
MAX_ADIAR_SEM_RESPOSTA = 5     # dias úteis esperando a cobrança do atraso antes de passar para a equipe

SISTEMA = """Você é o agente de Acompanhamento de uma instituição financeira. Uma data de pagamento combinada
com uma pessoa chegou, venceu ou ficou sem resposta. Decida o que fazer e, se for falar com ela, escreva
a mensagem. Responda APENAS com um objeto JSON: {"acao": ..., "motivo": ..., "mensagem": ...}

- "acao": uma das opções em "pode_fazer" do briefing, e só elas.
- "motivo": uma frase curta, para a equipe, do porquê da escolha.
- "mensagem": para lembrar, procurar ou oferecer_remarcar, o texto para a pessoa (no máximo 3 frases,
  português do Brasil, respeitoso, sem pressa). Para as outras ações, "".

Como escolher:
- lembrete: lembre de forma leve; "esperar" só se o caderno mostrar que a pessoa já confirmou o pagamento.
- venceu: pergunte o que aconteceu, sem acusar. Se ela pareceu ansiosa ou triste antes, acolha e ofereça
  uma nova data (oferecer_remarcar). Se pareceu irritada ou desesperada, ou se já quebrou acordo antes,
  chame uma pessoa (chamar_pessoa). "esperar" adia a cobrança por 1 dia útil, uma vez só (ex.: o caderno
  mostra que ela disse que paga amanhã); com "ja_esperou_no_atraso" verdadeiro, não espere de novo.
- sem_resposta: em geral, chame uma pessoa; "esperar_mais" só se o caderno mostrar um motivo claro.

Regras: use só o valor e a data do briefing, escritos como estão; não fale de juros, multa, processo,
protesto, família ou trabalho; não diga que fez algo (agendei, remarquei); não prometa desconto.
O briefing é escrito pelo sistema; o caderno é o que os outros agentes decidiram antes."""


def _briefing_ia(ctx, fase: str, d: dict) -> dict:
    caderno = estado.caderno(ctx.caso, 8)
    emocao = next((n["motivo"] for n in reversed(caderno) if n["agente"] == "triagem"), "")
    return {"fase": fase, "pode_fazer": list(CARDAPIO[fase]),
            "primeiro_nome": _nome(ctx, ctx.saida["_devedor"]),
            "compromisso": {"valor": _brl(d.get("valor")), "data": _data_br(d["data"])},
            "hoje": _data_br(_hoje(ctx.agora).isoformat()), "situacao": ctx.caso["situacao"],
            "ja_esperou_mais": d["compromisso_id"] in ((ctx.caso.get("dados") or {}).get("esperou_mais") or []),
            "ja_esperou_no_atraso": d["compromisso_id"] in ((ctx.caso.get("dados") or {}).get("esperou_atraso") or []),
            "ultima_leitura_da_triagem": emocao,
            "caderno": [f"{n['agente']}: {n['decisao']}" + (f" — {n['motivo']}" if n.get("motivo") else "")
                        for n in caderno]}


def decidir(ctx, fase: str, d: dict) -> dict:
    """A IA escolhe a ação e escreve a mensagem; o código confere. Erro → ValueError (vale o texto pronto)."""
    import json as _json
    from agente import guardrails
    briefing = _briefing_ia(ctx, fase, d)
    mensagens = [{"role": "user", "content": "<briefing>" + _json.dumps(briefing, ensure_ascii=False) + "</briefing>"}]
    permitidos = guardrails.permitidos_de([{"valor_negociado": float(d.get("valor") or 0)}])
    for tentativa in range(2):
        r = ctx.ia("acompanhamento", SISTEMA, mensagens, max_tokens=400)
        if ctx.rastreio.atual is not None:
            ctx.rastreio.atual["versao_prompt"] = VERSAO_PROMPT
        texto = (r.texto or "").strip()
        if texto.startswith("```"):
            texto = texto.strip("`").removeprefix("json").strip()
        dec = _json.loads(texto)
        if not isinstance(dec, dict) or dec.get("acao") not in CARDAPIO[fase]:
            raise ValueError("ação fora do cardápio")
        if dec["acao"] == "esperar_mais" and briefing["ja_esperou_mais"]:
            raise ValueError("já esperou mais uma vez")
        if fase == "venceu" and dec["acao"] == "esperar" and briefing["ja_esperou_no_atraso"]:
            raise ValueError("já esperou uma vez no atraso")
        dec["motivo"] = str(dec.get("motivo") or "")[:200]
        if dec["acao"] not in COM_MENSAGEM:
            dec["mensagem"] = ""
            return dec
        msg = str(dec.get("mensagem") or "").strip()
        motivos = guardrails.conferir(msg, permitidos, feitas=set()) if msg else ["mensagem vazia"]
        if not motivos:
            dec["mensagem"] = msg
            return dec
        mensagens += [{"role": "assistant", "content": r.texto or ""},
                      {"role": "user", "content": "[verificação automática] A mensagem não pode sair: "
                                                  + "; ".join(motivos) + ". Responda o JSON de novo, corrigido."}]
    raise ValueError("mensagem reprovada duas vezes nas travas")


# ── grafos ──────────────────────────────────────────────────────────────────

def _enviar(ctx, texto: str) -> None:
    ctx.repo.gravar_mensagem(ctx.caso["empresa_id"], ctx.caso["id"], "saida", texto, ctx.rastreio.trace_id,
                             criado_em=ctx.agora)
    ctx.saida["enviada"] = texto


def _quando(m: dict) -> datetime | None:
    q = m.get("criado_em")
    if isinstance(q, str):
        q = datetime.fromisoformat(q.replace("Z", "+00:00"))
    return q


def _contatos_7d(ctx) -> int:
    limite = ctx.agora - timedelta(days=7)
    return sum(1 for m in ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 50)
               if m["direcao"] == "saida" and _quando(m) and _quando(m) >= limite)


def _pode_procurar(ctx) -> bool:
    """Confere o Auditor para uma mensagem que o agente inicia. Fora do horário, adia."""
    d = ctx.auditar({"tipo": "enviar_mensagem", "params": {}}, contatos_7d=_contatos_7d(ctx))
    if d["permitida"]:
        return True
    regras, _ = ctx.politica()
    if d["regra"] == "R2_HORARIO" and regras:
        ctx.saida["adiar_para"] = proximo_horario(regras, ctx.agora)
    return False


def _nome(ctx, dev) -> str:
    return ferramentas._primeiro_nome(dev.get("nome"))


def grafo_vencimento(fonte) -> Grafo:
    def conferir(ctx):
        d = ctx.evento["dados"]
        dev = fonte.devedor(ctx.caso["empresa_id"], ctx.caso["predicao_id"])
        if dev is None:
            raise LookupError("devedor não encontrado nesta empresa")
        ctx.saida["_devedor"] = dev
        pendentes = {a["id"] for a in fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])}
        if ctx.caso.get("grupo_controle"):
            ctx.saida["pular"] = "grupo sorteado"
        elif ctx.caso["situacao"] in NAO_COBRAR:
            ctx.saida["pular"] = f"caso {ctx.caso['situacao']}"
        elif d["compromisso_id"] not in pendentes:
            ctx.saida["pular"] = "compromisso já resolvido"   # pagou, remarcou ou alguém resolveu
        with ctx.rastreio.span("decisao", "acompanhamento") as p:
            p["detalhe"] = {"fase": d.get("fase"), "pular": ctx.saida.get("pular")}

    def rota(ctx):
        if ctx.saida.get("pular"):
            return FIM
        return {"lembrete": "lembrar", "venceu": "cobrar_atraso", "sem_resposta": "encerrar"}[ctx.evento["dados"]["fase"]]

    def com_ia(ctx, fase):
        d = ctx.evento["dados"]
        dec = ctx.ia_ou_codigo("acompanhamento", lambda: decidir(ctx, fase, d), lambda: None)
        if dec and ctx.rastreio.atual is not None:
            ctx.rastreio.atual["detalhe"] = {**ctx.rastreio.atual.get("detalhe", {}), "acao": dec["acao"]}
        return dec

    def lembrar(ctx):
        d = ctx.evento["dados"]
        if not _pode_procurar(ctx):
            return
        dec = com_ia(ctx, "lembrete")
        if dec and dec["acao"] == "esperar":
            ctx.anotar("acompanhamento", "esperou", dec["motivo"])
            return
        texto = dec["mensagem"] if dec else texto_lembrete(_nome(ctx, ctx.saida["_devedor"]), d["valor"], d["data"],
                                                           _hoje(ctx.agora))
        _enviar(ctx, texto)
        ctx.anotar("acompanhamento", "lembrou", (dec or {}).get("motivo") or f"lembrete do compromisso de {_data_br(d['data'])}")

    def cobrar_atraso(ctx):
        d = ctx.evento["dados"]
        if not _pode_procurar(ctx):
            return
        dec = com_ia(ctx, "venceu")
        if dec and dec["acao"] == "esperar":
            # Espera de 1 dia útil, uma vez só, sem marcar o atraso como cobrado:
            # o "sem resposta" conta a partir da cobrança de verdade.
            dados = dict(ctx.caso.get("dados") or {})
            dados["esperou_atraso"] = (list(dados.get("esperou_atraso") or []) + [d["compromisso_id"]])[-20:]
            ctx.caso["dados"] = dados
            ctx.saida["adiar_para"] = mesma_hora_em(ctx.agora, 1)
            ctx.anotar("acompanhamento", "esperou", dec["motivo"])
            return
        if ctx.caso["situacao"] == "acordo_ativo":
            ctx.mudar_situacao("atrasado")
        dados = dict(ctx.caso.get("dados") or {})
        dados["objetivo"] = ("oferecer uma nova data dentro da regra, com acolhimento"
                             if (dec or {}).get("acao") == "oferecer_remarcar"
                             else "entender por que não pagou e remarcar dentro da regra, sem acusar")
        dados["atraso"] = {"compromisso_id": d["compromisso_id"], "desde": ctx.agora.isoformat()}
        ctx.caso["dados"] = dados
        if dec and dec["acao"] == "chamar_pessoa":
            # "falha" e não "dificuldade_grave": atraso comum não é sofrimento lido pela Triagem
            # (dificuldade_grave soma +30 na fila da equipe).
            r = ferramentas.executar(ctx, fonte, "transferir_para_humano", {
                "motivo": "falha", "resumo": f"Compromisso de {_brl(d['valor'])} para {_data_br(d['data'])} "
                                             f"venceu. Acompanhamento: {dec['motivo']}"[:300]})
            if not r.get("ok"):
                raise RuntimeError("transferência não executou")
            ctx.anotar("acompanhamento", "passou_para_pessoa", dec["motivo"])
            return
        _enviar(ctx, dec["mensagem"] if dec else texto_atraso(_nome(ctx, ctx.saida["_devedor"]), d["valor"], d["data"]))
        ctx.anotar("acompanhamento", (dec or {}).get("acao") or "procurou_no_atraso",
                   (dec or {}).get("motivo") or f"compromisso de {_data_br(d['data'])} venceu sem pagamento")

    def _ainda_nao(ctx, d) -> bool:
        """O "sem resposta" só vale depois da cobrança do atraso e dos dias úteis de
        espera. Antes disso (relógio parado, fila atrasada, "esperar"), reagenda."""
        regras, _ = ctx.politica()
        dados = dict(ctx.caso.get("dados") or {})
        atraso = dados.get("atraso") or {}
        desde = atraso.get("desde") if atraso.get("compromisso_id") == d["compromisso_id"] else None
        if not desde:
            vezes = dict(dados.get("sem_resposta_adiado") or {})
            n = int(vezes.get(d["compromisso_id"]) or 0)
            if n >= MAX_ADIAR_SEM_RESPOSTA:
                return False                    # a cobrança nunca saiu: a equipe assume
            vezes[d["compromisso_id"]] = n + 1
            dados["sem_resposta_adiado"] = dict(list(vezes.items())[-20:])
            ctx.caso["dados"] = dados
            ctx.saida["adiar_para"] = mesma_hora_em(ctx.agora, 1)
            ctx.saida["pular"] = "o atraso ainda não foi cobrado"
            return True
        prazo = somar_dias_uteis(datetime.fromisoformat(desde).astimezone(auditor.BRASILIA).date(),
                                 (regras or {}).get("dias_sem_resposta", 3))
        if _hoje(ctx.agora) < prazo:
            hora = (regras or {}).get("hora_inicio", 8)
            ctx.saida["adiar_para"] = datetime.combine(prazo, time(hora), auditor.BRASILIA).astimezone(timezone.utc)
            ctx.saida["pular"] = "ainda no prazo de resposta"
            return True
        return False

    def encerrar(ctx):
        d = ctx.evento["dados"]
        if _ainda_nao(ctx, d):
            return
        desde = ((ctx.caso.get("dados") or {}).get("atraso") or {}).get("desde")
        desde = datetime.fromisoformat(desde) if desde else None
        msgs = ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 50)
        respondeu = bool(desde) and any(m["direcao"] == "entrada" and _quando(m) and _quando(m) >= desde for m in msgs)
        if respondeu:
            ctx.saida["pular"] = "devedor respondeu; a conversa segue"
            return
        dec = com_ia(ctx, "sem_resposta")
        if dec and dec["acao"] == "esperar_mais":
            # Uma espera a mais, com prazo: o relógio volta em 2 dias úteis, na mesma hora de Brasília.
            dados = dict(ctx.caso.get("dados") or {})
            dados["esperou_mais"] = (list(dados.get("esperou_mais") or []) + [d["compromisso_id"]])[-20:]
            ctx.caso["dados"] = dados
            volta = mesma_hora_em(ctx.agora, 2)
            registrar_evento(ctx.repo, ctx.caso["empresa_id"], ctx.caso["id"], "vencimento",
                             f"sem_resposta2:{d['compromisso_id']}", dict(d), origem="acompanhamento",
                             disponivel_em=volta)
            ctx.anotar("acompanhamento", "esperou_mais", dec["motivo"])
            return
        if ctx.auditar({"tipo": "marcar_promessa_quebrada", "params": {}})["permitida"]:
            fonte.atualizar_agenda(ctx.caso["empresa_id"], ctx.saida["_devedor"]["id"], d["compromisso_id"],
                                   {"situacao": "quebrada", "resolvido_em": ctx.agora.isoformat(),
                                    "resolvido_por": "assistente: sem resposta depois do atraso"})
        r = ferramentas.executar(ctx, fonte, "transferir_para_humano", {
            "motivo": "falha", "resumo": f"Promessa de {_brl(d['valor'])} para {_data_br(d['data'])} não foi paga "
                                         "e o devedor não respondeu à mensagem de atraso."})
        if not r.get("ok"):
            raise RuntimeError("transferência não executou")
        ctx.anotar("acompanhamento", "passou_para_pessoa", "sem resposta depois do atraso; promessa quebrada")

    g = (Grafo("vencimento", "conferir")
         .no("conferir", conferir, agente="acompanhamento", seguinte=rota)
         .no("lembrar", lembrar, agente="acompanhamento")
         .no("cobrar_atraso", cobrar_atraso, agente="acompanhamento")
         .no("encerrar", encerrar, agente="acompanhamento"))
    g.validar()
    return g


def grafo_pagamento(fonte) -> Grafo:
    """Pagamento confirmado pelo banco: liga à promessa, atualiza o caso e agradece.

    Um nó só: a permissão para escrever ao devedor é decidida antes de mudar a
    situação (um caso quitado não recebe mensagem, mas o agradecimento do
    pagamento que quitou é devido). Fora do horário, não agradece; nada é
    refeito depois.
    """
    def registrar(ctx):
        d = ctx.evento["dados"]
        dev = fonte.devedor(ctx.caso["empresa_id"], ctx.caso["predicao_id"])
        if dev is None:
            raise LookupError("devedor não encontrado nesta empresa")
        valor = float(d.get("valor") or 0)
        prometido = sum(float(p.get("valor") or 0) for p in d.get("promessas") or [])
        falta = round(prometido - valor, 2) if prometido and valor + 0.01 < prometido else None
        s = ctx.caso["situacao"]
        silencio = s in estado.SO_PESSOA_TIRA or s in estado.FINAIS
        pode_escrever = (not silencio and
                         ctx.auditar({"tipo": "enviar_mensagem", "params": {}}, contatos_7d=0)["permitida"])

        dados = dict(ctx.caso.get("dados") or {})
        for chave in ("pagamento_informado", "atraso", "objetivo"):
            dados.pop(chave, None)
        dados["pagamentos"] = (dados.get("pagamentos") or []) + [{"valor": valor, "data": d.get("data"), "falta": falta}]
        ctx.caso["dados"] = dados
        acordo = dados.get("acordo")
        if silencio:
            pass                                             # pessoa cuida, ou pediu para não ser contatado
        elif falta:
            fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", _hoje(ctx.agora).isoformat(),
                               observacao=f"Pagamento parcial de {_brl(valor)}: faltam {_brl(falta)}. Conferir a baixa.")
            if s == "pagamento_em_conferencia":
                ctx.mudar_situacao("acordo_ativo" if acordo else "em_contato")
        elif acordo and int(acordo["condicoes"]["n_parcelas"]) == 1:
            if s != "pagamento_em_conferencia":
                ferramentas._ir_para(ctx, "acordo_ativo")
            ctx.mudar_situacao("quitado")
        elif acordo:
            ferramentas._ir_para(ctx, "acordo_ativo")
        elif s == "pagamento_em_conferencia":
            ctx.mudar_situacao("em_contato")
        if pode_escrever:
            _enviar(ctx, texto_pagamento(_nome(ctx, dev), valor, falta))

    g = Grafo("pagamento", "registrar").no("registrar", registrar, agente="acompanhamento")
    g.validar()
    return g
