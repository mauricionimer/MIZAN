"""Estrategista: quem cobrar e quem não cobrar (docs/PLANO_AGENTE.md, 3.1).

Código, sem IA. Separa a carteira em quatro grupos, sempre com o motivo escrito,
e sorteia o grupo de controle que segue sem o agente.

| Grupo | Para quem | O que acontece |
|---|---|---|
| so_lembrete | Tende a pagar sozinho, ou já tem acordo andando | Só lembrete (Acompanhamento) |
| contato | Paga se for procurado | Primeira mensagem pronta; o Negociador entra quando responder |
| nao_adianta | Chance muito baixa agora, ou acordo quebrado há pouco | Aguarda revisão |
| pessoa | Contestação, suspensão, caso com uma pessoa | Fica com a equipe |

Os limiares de chance (70% e 5%) são escolha de projeto para a demonstração,
não número medido: entram na política quando houver dado de um piloto.

Grupo sorteado: um sorteio fixo por devedor (hash de empresa + devedor), então
gerar o plano de novo não muda quem foi sorteado, e quem já tem caso mantém o
sorteio de quando entrou. Comparar quanto entrou em cada grupo, por real de
dívida, é o que prova o efeito do agente (e, com dado suficiente, mede quem só
paga se for cobrado).
"""
import hashlib

from datetime import datetime, timedelta, timezone

from agente import auditor, estado, estrategista_ia, ferramentas
from agente.llm import ia_ligada
from agente.orquestrador import Grafo, registrar_evento

LIMIAR_SO_LEMBRETE = 0.70
LIMIAR_NAO_ADIANTA = 0.05

GRUPOS = ("so_lembrete", "contato", "nao_adianta", "pessoa")


def sorteado(empresa_id: str, predicao_id: str, percentual: float) -> bool:
    h = hashlib.sha256(f"{empresa_id}:{predicao_id}:controle".encode()).hexdigest()
    return int(h[:8], 16) % 10_000 < percentual * 100


def chance(dev: dict) -> float | None:
    p = dev.get("probabilidade_pagamento")
    if p is not None:
        return float(p)
    s = dev.get("score_recuperabilidade")
    return None if s is None else max(0.0, min(1.0, float(s) / 100))


def classificar(dev: dict, caso: dict | None) -> tuple:
    """(grupo, motivo) de um devedor."""
    s = (caso or {}).get("situacao")
    if s in ("contestado", "com_pessoa"):
        return "pessoa", "contestou a dívida" if s == "contestado" else "o caso está com uma pessoa da equipe"
    if s == "suspenso":
        return "pessoa", "pediu para não ser contatado ou é pessoa errada"
    if s == "quitado":
        return "so_lembrete", "dívida quitada: nada a fazer"
    if s == "quebrado":
        return "nao_adianta", "acordo quebrado há pouco: aguarda revisão"
    if s in ("acordo_ativo", "atrasado", "pagamento_em_conferencia"):
        return "so_lembrete", "acordo em andamento: o Acompanhamento cuida das datas"
    p = chance(dev)
    if p is None:
        return "contato", "sem chance estimada: procurar para entender a situação"
    if p >= LIMIAR_SO_LEMBRETE:
        return "so_lembrete", f"chance de {p:.0%} de pagar: tende a pagar sem negociação"
    if p < LIMIAR_NAO_ADIANTA:
        return "nao_adianta", f"chance de {p:.0%} agora: contato custaria mais do que tende a trazer"
    return "contato", f"chance de {p:.0%}: paga se for procurado"


def plano(repo, fonte, empresa_id: str, aplicar: bool = False, agora=None) -> dict:
    """Plano do dia. Com aplicar=True, grava grupos e sorteio nos casos e põe a
    primeira mensagem do grupo 'contato' na fila."""
    achada = repo.politica_ativa(empresa_id)
    pol = auditor.validar_politica(achada["regras"]) if achada else None
    pct = pol["percentual_controle"] if pol else 0
    saida = {g: [] for g in GRUPOS}
    controle = []
    devedores = list(fonte.devedores(empresa_id))
    # Os casos de uma vez, em lotes (não uma consulta por devedor).
    casos = {str(c["predicao_id"]): c for c in repo.casos_por_predicoes(empresa_id, [d["id"] for d in devedores])}
    # Limite da IA por dia de Brasília (não por chamada do plano): conta quem já
    # passou pela IA hoje, anotado no caso.
    hoje = (agora or datetime.now(timezone.utc)).astimezone(auditor.BRASILIA).date().isoformat()
    com_ia = sum(1 for c in casos.values() if (c.get("dados") or {}).get("abordagem_ia_em") == hoje)
    novos_ia = 0                        # desta chamada: só eles entram nos lotes de 10 minutos
    for dev in devedores:
        caso = casos.get(str(dev["id"]))
        grupo, motivo = classificar(dev, caso)
        no_controle = caso["grupo_controle"] if caso else sorteado(empresa_id, dev["id"], pct)
        item = {"id": dev["id"], "nome": dev.get("nome"), "valor_divida": dev.get("valor_divida"),
                "chance": chance(dev), "motivo": motivo, "situacao": (caso or {}).get("situacao", "novo"),
                "estrategia": ((caso or {}).get("dados") or {}).get("estrategia")}
        if no_controle:
            controle.append({**item, "grupo": grupo})
        else:
            saida[grupo].append(item)
        if aplicar and grupo != "pessoa":
            c = caso or repo.obter_ou_criar_caso(empresa_id, dev["id"])
            dados = dict(c.get("dados") or {})
            if c.get("grupo") != grupo or dados.get("motivo_grupo") != motivo:
                # Só anota quando a decisão muda: o plano roda todo dia.
                rascunho = {"dados": dados}
                estado.anotar(rascunho, "estrategista", f"grupo:{grupo}" + (" (sorteado)" if no_controle else ""),
                              motivo, quando=agora)
                dados = rascunho["dados"]
            dados["motivo_grupo"] = motivo
            dados["chance"] = chance(dev)
            # O grupo de entrada não muda depois: quem fechou acordo vira "só lembrete",
            # mas continua contando para o Cientista como caso que o agente procurou.
            dados.setdefault("grupo_entrada", c.get("grupo") or grupo)
            campos = {"grupo": grupo, "dados": dados, "grupo_controle": bool(no_controle)}
            if c["situacao"] == "novo" and grupo == "so_lembrete" and not no_controle:
                campos["situacao"] = estado.mudar("novo", "so_lembrete")
            repo.salvar_caso(c["id"], campos)
            if grupo == "contato" and not no_controle and c["situacao"] == "novo":
                # Os primeiros do dia passam pelo Estrategista com IA, em lotes
                # (limite de chamadas por minuto): o lote seguinte sai no ciclo seguinte.
                analisar = ia_ligada("estrategista") and com_ia < estrategista_ia.max_por_dia()
                lote = novos_ia // estrategista_ia.POR_LOTE
                _, novo = registrar_evento(repo, empresa_id, c["id"], "abordagem", f"abordagem:{dev['id']}",
                                           {"com_ia": analisar}, origem="estrategista",
                                           disponivel_em=(agora + timedelta(minutes=10 * lote)) if (analisar and agora and lote) else None)
                if analisar and novo:
                    com_ia += 1
                    novos_ia += 1
                    dados["abordagem_ia_em"] = hoje
                    repo.salvar_caso(c["id"], {"dados": dados})
    return {"grupos": saida, "controle": controle, "percentual_controle": pct,
            "politica_versao": achada["versao"] if achada else None,
            "contagem": {**{g: len(v) for g, v in saida.items()}, "controle": len(controle)}}


def texto_abordagem(nome: str, empresa: str) -> str:
    return (f"Olá, {nome}! Aqui é o assistente virtual de {empresa}. Tudo bem? Antes de seguirmos, "
            "posso confirmar se estou falando com você? É só para proteger sua privacidade. "
            "Se preferir, uma pessoa da equipe pode continuar por aqui.")


def grafo_abordagem(fonte) -> Grafo:
    """Primeira mensagem para quem está no grupo 'contato'. Pronta, sem IA."""
    def abordar(ctx):
        if ctx.caso.get("grupo_controle") or ctx.caso["situacao"] != "novo":
            ctx.saida["pular"] = "sorteado ou já em atendimento"
            return
        dev = fonte.devedor(ctx.caso["empresa_id"], ctx.caso["predicao_id"])
        if dev is None:
            raise LookupError("devedor não encontrado nesta empresa")
        # O caso 'novo' ainda não fala: a abordagem é a mudança para 'em contato',
        # conferida pelo Auditor como uma mensagem iniciada pelo agente.
        ctx.mudar_situacao("em_contato")
        d = ctx.auditar({"tipo": "enviar_mensagem", "params": {}}, contatos_7d=0)
        if not d["permitida"]:
            ctx.caso["situacao"] = "novo"                   # volta: não houve contato
            regras, _ = ctx.politica()
            if d["regra"] == "R2_HORARIO" and regras:
                from agente.acompanhamento import proximo_horario
                ctx.saida["adiar_para"] = proximo_horario(regras, ctx.agora)
            return
        nome, empresa = ferramentas._primeiro_nome(dev.get("nome")), fonte.nome_empresa(ctx.caso["empresa_id"])
        dec = None
        if (ctx.evento.get("dados") or {}).get("com_ia"):
            rec = fonte.recomendacao_bandit(ctx.caso["empresa_id"], dev)
            with ctx.rastreio.span("estrategia", "estrategista") as p:
                dec = ctx.ia_ou_codigo("estrategista", lambda: estrategista_ia.decidir(ctx, dev, rec), lambda: None)
                if dec:
                    p["detalhe"] = {**p.get("detalhe", {}), "decisao": dec["decisao"], "tom": dec["tom"],
                                    "oferta": dec["oferta_inicial"], "concorda_bandit": dec["concorda_bandit"],
                                    "bandit": dec["bandit_oferta"]}
        if dec and dec["decisao"] == "adiar":
            ctx.caso["situacao"] = "novo"                       # não houve contato
            volta = estrategista_ia.quando_adiar(ctx.agora, dec["adiar_dias"])
            registrar_evento(ctx.repo, ctx.caso["empresa_id"], ctx.caso["id"], "abordagem",
                             f"abordagem:{dev['id']}:adiada:{volta.date().isoformat()}", {"com_ia": False},
                             origem="estrategista", disponivel_em=volta)
            ctx.anotar("estrategista", f"adiou {dec['adiar_dias']} dia(s)", dec["raciocinio"])
            ctx.saida["pular"] = "adiado pelo Estrategista"
            return
        if dec:
            dados = dict(ctx.caso.get("dados") or {})
            dados["estrategia"] = {k: dec[k] for k in ("tom", "oferta_inicial", "concorda_bandit", "bandit_oferta",
                                                       "raciocinio")}
            ctx.caso["dados"] = dados
            ctx.anotar("estrategista", f"abordar ({dec['tom']}" + (f", {dec['oferta_inicial']}" if dec["oferta_inicial"] else "")
                       + ")", dec["raciocinio"])
            # A primeira fala é sempre a abertura reservada escrita pelo sistema.
            # A estratégia de IA escolhe tom e primeiro degrau para o momento em
            # que a pessoa demonstrar querer conversar sobre a pendência; ela não
            # despeja uma oferta no primeiro contato.
            texto = texto_abordagem(nome, empresa)
        else:
            texto = texto_abordagem(nome, empresa)
        ctx.repo.gravar_mensagem(ctx.caso["empresa_id"], ctx.caso["id"], "saida", texto, ctx.rastreio.trace_id,
                                 criado_em=ctx.agora)

    g = Grafo("abordagem", "abordar").no("abordar", abordar, agente="estrategista")
    g.validar()
    return g
