"""Grafo de uma mensagem do devedor (docs/PLANO_EXECUCAO_AGENTES.md, 4.3).

    receber ─► (caso com pessoa/suspenso/contestado/quitado) ─► avisar equipe ─► FIM
           └─► triagem ─┬─ parar / pessoa errada ─► suspender ─┐
                        ├─ contestar ──────────────► contestar ─┤
                        ├─ pedir pessoa / sofrimento ► transferir┼─► resposta fixa ─► enviar ─► FIM
                        └─ o resto ─────────────────► negociar ──────────────────────► enviar ─► FIM

As decisões de segurança são código; só "negociar" usa a IA de conversa.
"""
from agente import estado, ferramentas, negociador, triagem
from agente.orquestrador import FIM, Grafo


def _executar_seguro(ctx, fonte, nome: str, args: dict) -> None:
    r = ferramentas.executar(ctx, fonte, nome, args)
    if not r.get("ok"):
        raise RuntimeError(f"{nome} não executou")


def grafo_mensagem(fonte) -> Grafo:
    def receber(ctx):
        texto = str((ctx.evento.get("dados") or {}).get("texto") or "")[:triagem.MAX_CARACTERES]
        ctx.saida["texto"] = texto
        if ctx.caso["situacao"] == "novo":
            ctx.mudar_situacao("em_contato")          # o devedor escreveu: a conversa começou
        ctx.repo.gravar_mensagem(ctx.caso["empresa_id"], ctx.caso["id"], "entrada", texto, ctx.rastreio.trace_id,
                             criado_em=ctx.agora)

    def depois_de_receber(ctx):
        s = ctx.caso["situacao"]
        return "avisar_equipe" if s in estado.SO_PESSOA_TIRA or s in estado.FINAIS else "triagem"

    def classificar(ctx):
        triagem.classificar(ctx, ctx.saida.get("texto") or ctx.evento["dados"].get("texto", ""))

    def rota(ctx):
        t = ctx.saida["triagem"]
        if t["intencao"] in ("parar_contato", "pessoa_errada"):
            return "suspender"
        if t["intencao"] == "contestar":
            return "contestar"
        if t["intencao"] == "pedir_pessoa" or "sofrimento_grave" in t["sinais_de_risco"]:
            return "transferir"
        return "negociar"

    def suspender(ctx):
        motivo = "pessoa_errada" if ctx.saida["triagem"]["intencao"] == "pessoa_errada" else "pediu_para_parar"
        _executar_seguro(ctx, fonte, "suspender_cobranca", {"motivo": motivo})

    def contestar(ctx):
        _executar_seguro(ctx, fonte, "abrir_contestacao", {"motivo": "Devedor não reconhece a dívida."})

    def transferir(ctx):
        grave = "sofrimento_grave" in ctx.saida["triagem"]["sinais_de_risco"]
        _executar_seguro(ctx, fonte, "transferir_para_humano", {
            "motivo": "dificuldade_grave" if grave else "pedido_do_devedor",
            "resumo": "Sinais de sofrimento grave na mensagem: atender com prioridade." if grave
                      else "O devedor pediu para falar com uma pessoa."})

    def resposta_fixa(ctx):
        ctx.saida["resposta"] = negociador.mensagem_fixa(ctx)

    def negociar(ctx):
        ctx.saida["resposta"] = negociador.conversar(ctx, fonte, ctx.saida.get("texto", ""))

    def enviar(ctx):
        texto = ctx.saida.get("resposta")
        if not texto:
            return
        anteriores = ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 50)
        if not any(m["direcao"] == "saida" for m in anteriores):
            # Transparência: a primeira mensagem diz que é um assistente virtual.
            dev = ctx.saida.get("_devedor") or {}
            nome = ferramentas._primeiro_nome(dev.get("nome"))
            texto = (f"Olá{', ' + nome if nome else ''}! Aqui é o assistente virtual de "
                     f"{fonte.nome_empresa(ctx.caso['empresa_id'])}. " + texto)
        ctx.repo.gravar_mensagem(ctx.caso["empresa_id"], ctx.caso["id"], "saida", texto, ctx.rastreio.trace_id,
                             criado_em=ctx.agora)
        ctx.saida["enviada"] = texto

    def avisar_equipe(ctx):
        dev = fonte.devedor(ctx.caso["empresa_id"], ctx.caso["predicao_id"])
        if dev is None:
            raise LookupError("devedor não encontrado nesta empresa")
        aviso = f"Nova mensagem do devedor (caso {ctx.caso['situacao']}): responder pela equipe."
        pendentes = fonte.agenda_pendente(ctx.caso["empresa_id"], dev["id"])
        if not any(aviso == (a.get("observacao") or "") for a in pendentes):
            hoje = ctx.agora.astimezone(negociador.auditor.BRASILIA).date().isoformat()
            fonte.criar_agenda(ctx.caso["empresa_id"], dev, "retorno", hoje, observacao=aviso)

    g = (Grafo("mensagem", "receber")
         .no("receber", receber, seguinte=depois_de_receber)
         .no("triagem", classificar, agente="triagem", seguinte=rota)
         .no("suspender", suspender, seguinte="resposta_fixa")
         .no("contestar", contestar, seguinte="resposta_fixa")
         .no("transferir", transferir, seguinte="resposta_fixa")
         .no("resposta_fixa", resposta_fixa, seguinte="enviar")
         .no("negociar", negociar, agente="negociador", seguinte="enviar")
         .no("enviar", enviar)
         .no("avisar_equipe", avisar_equipe))
    def ao_falhar(ctx):
        # Algo quebrou depois de receber a mensagem: o devedor não fica sem
        # resposta. Mensagem fixa, sem IA, só se nada foi enviado ainda.
        if ctx.saida.get("texto") and not ctx.saida.get("enviada") and ctx.caso["situacao"] == "com_pessoa":
            ctx.saida["resposta"] = negociador.FIXAS["com_pessoa"]
            enviar(ctx)

    g.ao_falhar = ao_falhar
    g.validar()
    return g
