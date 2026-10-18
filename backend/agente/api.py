"""O que as telas do agente usam (rotas em main.py): conversa de um caso, a
simulação de mensagem do devedor na demonstração e a Central de orquestração.

Tudo escopado à empresa. As fábricas abaixo são trocadas nos testes.
"""
import os
import uuid
from collections import Counter
from datetime import datetime, timezone

from agente import auditor, estado, llm, orquestrador as orq
from agente.rastreio import Rastreio
from agente.fonte import FonteSupabase
from agente.acompanhamento import grafo_pagamento, grafo_vencimento, planejar
from agente.estrategista import grafo_abordagem, plano as _plano
from agente.grafos import grafo_mensagem
from agente.repositorio import RepoSupabase

fabrica_repo = RepoSupabase
fabrica_fonte = FonteSupabase
fabrica_cliente = llm.cliente

MAX_TEXTO = 2000


class AgenteDesligado(RuntimeError):
    pass


class CasoOcupado(RuntimeError):
    pass


def ligado() -> bool:
    """Interruptor geral (variável MIZAN_AGENTE_ATIVO=1 no Render)."""
    return os.getenv("MIZAN_AGENTE_ATIVO", "").strip() == "1"


# Quem fez cada passo, em português, para a tela mostrar os vários agentes.
QUEM = {"triagem": "Triagem", "negociador": "Negociador", "auditor": "Auditor", "ferramenta": "Ferramenta",
        "codigo": "Travas", "orquestrador": "Orquestrador", "estrategista": "Estrategista",
        "acompanhamento": "Acompanhamento", "supervisor": "Supervisor", "cientista": "Cientista", "pessoa": "Equipe"}
_INTENCAO = {"pagar_negociar": "quer negociar", "ja_paguei": "diz que já pagou", "contestar": "contesta a dívida",
             "parar_contato": "pede para parar", "pessoa_errada": "pessoa errada", "pedir_pessoa": "pede uma pessoa",
             "duvida": "tem uma dúvida", "outro": "conversa"}


def _quem(p: dict) -> str:
    no = p.get("no") or ""
    if no.startswith("ferramenta:"):
        return "Ferramenta"
    if no in ("receber", "enviar", "resposta_fixa", "avisar_equipe", "transferir"):
        return "Orquestrador"                     # passos do grafo, não das travas
    if no in ("triagem", "negociar", "guardrails", "auditor"):
        return {"negociar": "Negociador", "guardrails": "Travas"}.get(no, QUEM.get(no, no))
    return QUEM.get(p.get("agente") or "", "Orquestrador")


def _explicar(p: dict) -> str:
    """Uma frase do que o passo fez. Só código e classificação: nunca o texto do devedor."""
    no, d = p.get("no") or "", p.get("detalhe") or {}
    if no == "resumo":
        return f"resumiu o caso para a equipe ({d.get('motivo') or 'passagem'})" + (" · texto de hoje" if d.get("origem") == "codigo" else "")
    if no == "revisao":
        if d.get("origem") == "codigo" or d.get("aprovado") is None:
            return f"não revisou (sem IA) · sinal: {d.get('sinal')}"
        return f"revisou o tom ({d.get('sinal')}): " + ("aprovado" if d.get("aprovado") else "pediu reescrita")
    if no == "estrategia":
        if d.get("origem") != "ia":
            return "abordagem padrão (sem IA)"
        txt = f"decidiu {d.get('decisao')} · tom {d.get('tom')}"
        if d.get("oferta"):
            txt += f" · começa por {d['oferta']}"
        return txt + (" · discorda do bandit" if d.get("concorda_bandit") is False else "")
    if no == "triagem":
        txt = f"leu a mensagem: {_INTENCAO.get(d.get('intencao'), d.get('intencao') or '?')}"
        if d.get("sinais"):
            txt += " · alerta: " + ", ".join(s.replace("_", " ") for s in d["sinais"])
        leitura = [x for x in (d.get("emocao") if d.get("emocao") not in (None, "calmo") else None,
                               "urgência alta" if d.get("urgencia") == "alta" else None,
                               "ironia" if d.get("ironia") else None) if x]
        if leitura:
            txt += " · " + ", ".join(leitura)
        return txt + (" (regra, sem IA)" if d.get("origem") == "regra" else "")
    if no == "auditor":
        acao = str(d.get("acao") or "").replace("_", " ")
        if d.get("permitida"):
            return f"aprovou: {acao}"
        return f"bloqueou: {acao} — {d.get('motivo') or p.get('regra')}"
    if no == "guardrails":
        return "barrou a resposta e pediu outra" if d.get("reprovado") else "conferiu valores, leis e tom"
    if no.startswith("ferramenta:"):
        nome = no.split(":", 1)[1].replace("_", " ")
        return f"{nome}: {'feito' if d.get('ok') else 'não feito'}"
    if no == "negociar":
        return "escreveu a resposta" if p.get("resultado") == "ok" else f"falhou ({d.get('erro') or p.get('resultado')})"
    return {"receber": "recebeu o evento", "enviar": "enviou a mensagem", "transferir": "passou para a equipe",
            "resposta_fixa": "mandou a resposta padrão", "avisar_equipe": "avisou a equipe (caso com pessoa)",
            "abordar": "mandou a primeira mensagem"}.get(no, no.replace("_", " "))


def _passo_publico(p: dict) -> dict:
    saida = {k: p.get(k) for k in ("no", "agente", "resultado", "duracao_ms", "regra", "versao_politica",
                                   "modelo", "versao_prompt", "tokens_entrada", "tokens_saida", "custo_usd",
                                   "detalhe", "criado_em")}
    saida["quem"], saida["explicacao"] = _quem(p), _explicar(p)
    return saida


def _por_que_calou(passos: list) -> str:
    """A última rodada não mandou mensagem: o motivo, em uma frase."""
    for p in passos:
        if p.get("no") == "auditor" and not (p.get("detalhe") or {}).get("permitida", True):
            return f"O Auditor bloqueou ({p.get('regra')}): {(p.get('detalhe') or {}).get('motivo') or 'fora da política'}."
    for p in passos:
        if p.get("resultado") == "erro":
            return f"Falha em {_quem(p)} ({(p.get('detalhe') or {}).get('erro') or 'erro'}): o evento será tentado de novo."
    if any(p.get("no") == "avisar_equipe" for p in passos):
        return "O caso está com uma pessoa da equipe: o agente não responde."
    return "O agente não mandou mensagem nesta rodada."


def grafos(fonte) -> dict:
    return {"mensagem_devedor": grafo_mensagem(fonte), "vencimento": grafo_vencimento(fonte),
            "pagamento": grafo_pagamento(fonte), "abordagem": grafo_abordagem(fonte)}


def ver_caso(empresa_id: str, predicao_id: str, repo=None) -> dict:
    repo = repo or fabrica_repo()
    caso = repo.caso_de(empresa_id, predicao_id)
    if caso is None:
        return {"caso": None, "mensagens": [], "passos": []}
    msgs = repo.ultimas_mensagens(empresa_id, caso["id"], 50)
    # A última rodada do caso, mesmo que não tenha virado mensagem (bloqueio,
    # falha): é aí que a tela precisa explicar por que o agente ficou calado.
    ev = next((e for e in repo.eventos_recentes(empresa_id, 300) if e.get("caso_id") == caso["id"] and e.get("trace_id")),
              None)
    ultimo_trace = (ev or {}).get("trace_id") or next((m.get("trace_id") for m in reversed(msgs) if m.get("trace_id")), None)
    passos = repo.passos_do_trace(empresa_id, ultimo_trace) if ultimo_trace else []
    d = caso.get("dados") or {}
    return {
        "caso": {"id": caso["id"], "situacao": caso["situacao"], "proxima_data": caso.get("proxima_data"),
                 "versao_politica": caso.get("versao_politica"), "resumo": caso.get("resumo"),
                 "identidade_confirmada": bool(d.get("identidade_ok")), "acordo": d.get("acordo")},
        "mensagens": [{"direcao": m["direcao"], "texto": m["texto"], "criado_em": m.get("criado_em"),
                       "trace_id": m.get("trace_id")} for m in msgs],
        "trace_id": ultimo_trace,
        "passos": [_passo_publico(p) for p in passos],
        # Rodada sem mensagem de saída: a tela explica o silêncio.
        "silencio": (_por_que_calou(passos) if passos and not any(
            m.get("trace_id") == ultimo_trace and m["direcao"] == "saida" for m in msgs) else None),
        "atendimento": d.get("atendimento"),
        "caderno": list(reversed(estado.caderno(caso))),
    }


def simular_mensagem(empresa_id: str, predicao_id: str, texto: str, agora: datetime | None = None) -> dict:
    """Demonstração: a tela faz o papel do devedor escrevendo pelo canal."""
    if not ligado():
        raise AgenteDesligado("O agente está desligado (MIZAN_AGENTE_ATIVO).")
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escreva a mensagem.")
    if len(texto) > MAX_TEXTO:
        raise ValueError(f"Mensagem com mais de {MAX_TEXTO} caracteres.")
    repo, fonte = fabrica_repo(), fabrica_fonte()
    if fonte.devedor(empresa_id, predicao_id) is None:
        raise LookupError("Devedor não encontrado nas carteiras da empresa.")
    caso = repo.obter_ou_criar_caso(empresa_id, predicao_id)
    ev, _ = orq.registrar_evento(repo, empresa_id, caso["id"], "mensagem_devedor", f"tela:{uuid.uuid4().hex}",
                                 {"texto": texto}, origem="tela")
    # TODO junção: empresa_id=empresa_id
    orq.processar_fila(repo, grafos(fonte), fabrica_cliente(), limite=5,
                       agora=agora or datetime.now(timezone.utc))
    r = ver_caso(empresa_id, predicao_id, repo)
    final = repo.evento_por_chave(empresa_id, ev["chave"]) or {}
    r["evento"] = {"situacao": final.get("situacao"), "erro": final.get("erro")}
    return r


def central(empresa_id: str, agora: datetime | None = None) -> dict:
    """Central de orquestração: fila, falhas, casos por situação e custo do dia."""
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    eventos = repo.eventos_recentes(empresa_id, 500)
    regras, versao = None, None
    achada = repo.politica_ativa(empresa_id)
    if achada:
        try:
            regras, versao = auditor.validar_politica(achada["regras"]), achada["versao"]
        except ValueError:
            pass
    return {
        "ligado": ligado(),
        "cliente": os.getenv("MIZAN_AGENTE_CLIENTE", "falso"),
        "modelos": {"triagem": llm.modelo_para("triagem"), "negociador": llm.modelo_para("negociador")},
        "custo_hoje_usd": repo.custo_do_dia(empresa_id, agora.astimezone(auditor.BRASILIA).date()),
        "teto_dia_usd": llm.teto_dia_usd(),
        "politica": {"versao": versao, "regras": regras},
        "eventos": dict(Counter(e["situacao"] for e in eventos)),
        "falhas": [{k: e.get(k) for k in ("id", "caso_id", "tipo", "erro", "tentativas", "criado_em", "trace_id")}
                   for e in eventos if e["situacao"] == "falhou"][:20],
        "recentes": [{k: e.get(k) for k in ("caso_id", "tipo", "origem", "situacao", "erro", "criado_em", "trace_id")}
                     for e in eventos[:20]],
        "casos": dict(Counter(repo.situacoes_dos_casos(empresa_id))),
    }


JANELA_ESTACAO_MIN = 15


def estacao(empresa_id: str, agora: datetime | None = None) -> dict:
    """Escritório dos agentes: o que cada um fez nos últimos minutos e a última
    conversa inteira, para a tela reproduzir. Só passos (nunca texto do devedor)."""
    from datetime import timedelta
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    recentes = repo.passos_recentes(empresa_id, agora - timedelta(minutes=JANELA_ESTACAO_MIN))
    ultimo = []
    for e in repo.eventos_recentes(empresa_id, 20):
        if e.get("trace_id") and e.get("situacao") == "feito":
            ultimo = repo.passos_do_trace(empresa_id, e["trace_id"])
            if ultimo:
                break

    def publico(p):
        return {**_passo_publico(p), "trace_id": p.get("trace_id")}
    return {"agora": agora.isoformat(), "janela_min": JANELA_ESTACAO_MIN, "ligado": ligado(),
            "ia": {papel: llm.ia_ligada(papel) for papel in llm.PAPEIS},
            "passos": [publico(p) for p in recentes],
            "ultima_conversa": [publico(p) for p in ultimo]}


# ── Passagem para a equipe (docs/PLANO_PASSAGEM_EQUIPE.md) ───────────────────

def passagens_da_fila(empresa_id: str, predicao_ids: list, agora: datetime | None = None) -> dict:
    """{predicao_id: ficha} dos casos com passagem para a equipe, com a prioridade de agora."""
    from agente import passagem
    ids = {str(p) for p in predicao_ids if p}
    if not ids:
        return {}
    saida = {}
    for c in fabrica_repo().casos_por_predicoes(empresa_id, ids):
        f = passagem.para_tela((c.get("dados") or {}).get("passagem"), agora)
        if f:
            saida[str(c["predicao_id"])] = f
    return saida


def registrar_retorno_passagem(empresa_id: str, predicao_id: str, ajudou: bool, quem: str | None,
                               comentario: str = "", agora: datetime | None = None) -> dict:
    """O atendente diz se o resumo da passagem ajudou (nota do Supervisor).

    Trava o caso como o agente faz: sem isso, o retorno e uma rodada do agente
    gravando o mesmo caso ao mesmo tempo apagam um ao outro."""
    from agente import passagem
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    caso = repo.caso_de(empresa_id, predicao_id)
    if caso is None:
        raise LookupError("Caso não encontrado.")
    dono = f"retorno:{quem or ''}"
    if not repo.travar_caso(caso["id"], dono, agora + orq.DURACAO_TRAVA, agora):
        raise CasoOcupado("O agente está processando este caso agora. Tente de novo em instantes.")
    try:
        caso = repo.obter_caso(caso["id"]) or caso             # relê já com a trava: dados atuais
        retorno = passagem.registrar_retorno(caso, ajudou, quem, comentario, agora)
        if not repo.salvar_caso(caso["id"], {"dados": caso["dados"]}, dono=dono):
            raise CasoOcupado("O caso mudou de mãos durante a gravação. Tente de novo.")
    finally:
        repo.soltar_caso(caso["id"], dono)
    return retorno


def sinais_equipe(empresa_id: str, agora: datetime | None = None, dias: int = 7) -> dict:
    from agente import passagem
    return passagem.sinais_da_equipe(fabrica_repo().casos_da_empresa(empresa_id), agora, dias)


# Agentes que aparecem na tela e o papel de IA de cada um (None = código).
AGENTES_TELA = {"Orquestrador": None, "Triagem": "triagem", "Negociador": "negociador", "Estrategista": "estrategista",
                "Acompanhamento": "acompanhamento", "Supervisor": "supervisor", "Cientista": "cientista",
                "Auditor": None, "Travas": None, "Ferramenta": None}


def _resumo_agente(nome: str, passos: list) -> dict:
    meus = [p for p in passos if _quem(p) == nome]
    duracoes = [int(p.get("duracao_ms") or 0) for p in meus if p.get("duracao_ms")]
    com_ia = [p for p in meus if p.get("modelo")]
    papel = AGENTES_TELA.get(nome)
    return {"nome": nome, "papel": papel, "ia_ligada": llm.ia_ligada(papel) if papel else None,
            "acoes": len(meus),
            "bloqueios": sum(1 for p in meus if p.get("resultado") == "bloqueado"),
            "erros": sum(1 for p in meus if p.get("resultado") == "erro"),
            "sem_ia": sum(1 for p in meus if (p.get("detalhe") or {}).get("origem") == "codigo"),
            "custo_usd": round(sum(float(p.get("custo_usd") or 0) for p in meus), 6),
            "tempo_medio_ms": round(sum(duracoes) / len(duracoes)) if duracoes else None,
            "modelo": com_ia[-1].get("modelo") if com_ia else (llm.modelo_para(papel) if papel and llm.ia_ligada(papel) else None),
            "versao_prompt": next((p.get("versao_prompt") for p in reversed(meus) if p.get("versao_prompt")), None),
            "ultimo_em": meus[-1].get("criado_em") if meus else None}


def agentes(empresa_id: str, agora: datetime | None = None) -> dict:
    """Resumo das últimas 24 h de cada agente e os números do dia, para a área Agentes."""
    from datetime import timedelta
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    passos = repo.passos_recentes(empresa_id, agora - timedelta(hours=24), 5000)
    return {"agora": agora.isoformat(), "ligado": ligado(),
            "agentes": [_resumo_agente(n, passos) for n in AGENTES_TELA],
            "numeros": {
                "respostas": sum(1 for p in passos if p.get("no") == "negociar" and p.get("resultado") == "ok"),
                "conversas": len({p.get("caso_id") for p in passos if p.get("no") == "triagem" and p.get("caso_id")}),
                "acordos": sum(1 for p in passos if p.get("no") == "ferramenta:registrar_aceite"
                               and (p.get("detalhe") or {}).get("ok")),
                "bloqueios": sum(1 for p in passos if p.get("resultado") == "bloqueado"),
                "custo_hoje_usd": repo.custo_do_dia(empresa_id, agora.astimezone(auditor.BRASILIA).date()),
                "teto_dia_usd": llm.teto_dia_usd()}}


def agente_perfil(empresa_id: str, nome: str, agora: datetime | None = None) -> dict:
    """Perfil de um agente: resumo de 24 h e as últimas 20 decisões (sem texto do devedor)."""
    from datetime import timedelta
    if nome not in AGENTES_TELA:
        raise LookupError("Agente não encontrado.")
    agora = agora or datetime.now(timezone.utc)
    passos = fabrica_repo().passos_recentes(empresa_id, agora - timedelta(hours=24), 5000)
    meus = [p for p in passos if _quem(p) == nome]
    extra = {}
    if nome == "Supervisor":
        try:
            extra["sinais_equipe"] = sinais_equipe(empresa_id, agora, 30)
        except Exception as e:
            print(f"[Agente] sinais da equipe: {type(e).__name__}")
    return {**_resumo_agente(nome, passos), **extra,
            "ultimas": [{**_passo_publico(p), "trace_id": p.get("trace_id"), "caso_id": p.get("caso_id")}
                        for p in reversed(meus[-20:])]}


def _agenda_do_agente(empresa_id: str, repo, fonte) -> list:
    """Compromissos pendentes dos devedores que têm caso com o agente (só ids; sem ler os casos)."""
    return fonte.agenda_dos_casos(empresa_id, repo.predicoes_dos_casos(empresa_id))


def agenda(empresa_id: str) -> dict:
    """Compromissos pendentes dos devedores que estão com o agente, e os
    operadores para o administrador atribuir atendimentos."""
    from agente import passagem
    from agente.fonte import OPERADORES_DO_AGENTE, OPERADOR_A_DEFINIR
    repo, fonte = fabrica_repo(), fabrica_fonte()
    pendentes = _agenda_do_agente(empresa_id, repo, fonte)
    # Só os casos que aparecem na agenda, em lotes (não a carteira inteira).
    casos = {str(c["predicao_id"]): c for c in repo.casos_por_predicoes(empresa_id, [a.get("predicao_id") for a in pendentes])}
    itens = []
    for a in pendentes:
        c = casos.get(str(a.get("predicao_id"))) or {}
        obs = a.get("observacao") or ""
        tipo = ("atendimento" if obs.startswith("Atendimento com pessoa") else
                "transferencia" if obs.startswith("Transferido") else
                "conferencia" if "conferir" in obs.lower() else a.get("tipo"))
        itens.append({"id": a["id"], "predicao_id": a.get("predicao_id"), "nome": a.get("nome"),
                      "tipo": tipo, "data": a.get("data"), "hora": a.get("hora"), "valor": a.get("valor"),
                      "observacao": obs, "operador_id": a.get("operador_id"), "operador_nome": a.get("operador_nome"),
                      "a_definir": a.get("operador_id") == OPERADOR_A_DEFINIR,
                      "do_agente": a.get("operador_id") in OPERADORES_DO_AGENTE,
                      "situacao_caso": c.get("situacao"),
                      "passagem": passagem.para_tela((c.get("dados") or {}).get("passagem"))
                      if tipo in ("atendimento", "transferencia") else None})
    # No mesmo dia, a fila vem por prioridade da passagem (docs/PLANO_PASSAGEM_EQUIPE.md).
    itens.sort(key=lambda i: (str(i["data"] or ""), -((i["passagem"] or {}).get("prioridade") or 0), i["hora"] or "99:99"))
    return {"itens": itens, "operadores": fonte.operadores(empresa_id)}


def atribuir(empresa_id: str, item_id: str, operador_id: str) -> dict:
    """O administrador escolhe quem atende um compromisso que está com o agente."""
    from agente.fonte import OPERADORES_DO_AGENTE
    repo, fonte = fabrica_repo(), fabrica_fonte()
    op = next((o for o in fonte.operadores(empresa_id) if o["id"] == operador_id), None)
    if op is None:
        raise LookupError("Operador não encontrado ou inativo nesta empresa.")
    # Confere o item na agenda do agente sem montar a tela inteira (fichas, casos).
    item = next((a for a in _agenda_do_agente(empresa_id, repo, fonte) if a["id"] == item_id), None)
    if item is None or item["operador_id"] not in OPERADORES_DO_AGENTE:
        raise LookupError("Compromisso não encontrado, já atribuído ou já resolvido.")
    novo = fonte.atribuir_agenda(empresa_id, item_id, op["id"], op["nome"])
    if not novo:
        raise LookupError("Compromisso não encontrado, já atribuído ou já resolvido.")
    return {"ok": True, "item_id": item_id, "operador": op}


def passos(empresa_id: str, trace_id: str) -> list:
    return [_passo_publico(p) for p in fabrica_repo().passos_do_trace(empresa_id, trace_id)]


def _exigir_ligado():
    if not ligado():
        raise AgenteDesligado("O agente está desligado (MIZAN_AGENTE_ATIVO).")


def rodar_relogio(empresa_id: str, agora: datetime | None = None) -> dict:
    """Relógio de datas de uma empresa e processamento da fila (também por botão, na demo)."""
    _exigir_ligado()
    agora = agora or datetime.now(timezone.utc)
    repo, fonte = fabrica_repo(), fabrica_fonte()
    criados = planejar(repo, fonte, empresa_id, agora)
    # TODO junção: empresa_id=empresa_id
    feitos = orq.processar_fila(repo, grafos(fonte), fabrica_cliente(), limite=50, agora=agora)
    return {"eventos_criados": len(criados), "processados": len(feitos)}


def avisar_pagamento(empresa_id: str, predicao_id: str, valor: float, promessas: list,
                     agora: datetime | None = None, processar: bool = False, origem: str = "banco") -> bool:
    """Pagamento confirmado: põe o evento na fila do caso, se o devedor estiver com o agente."""
    repo = fabrica_repo()
    caso = repo.caso_de(empresa_id, predicao_id)
    if caso is None:
        return False
    agora = agora or datetime.now(timezone.utc)
    orq.registrar_evento(repo, empresa_id, caso["id"], "pagamento", f"pagamento:{uuid.uuid4().hex}",
                         {"valor": valor, "data": agora.astimezone(auditor.BRASILIA).date().isoformat(),
                          "promessas": promessas}, origem=origem)
    if processar:
        # TODO junção: empresa_id=empresa_id
        orq.processar_fila(repo, grafos(fabrica_fonte()), fabrica_cliente(), limite=5, agora=agora)
    return True


def simular_pagamento(empresa_id: str, predicao_id: str, valor: float, agora: datetime | None = None) -> dict:
    """Demonstração: o botão faz o papel do banco confirmando um pagamento.

    Não grava pagamento em feedbacks (isso continua com a baixa de verdade): só
    cumpre a promessa na agenda, como a baixa faria, e avisa o agente.
    """
    _exigir_ligado()
    if not valor or valor <= 0:
        raise ValueError("Informe o valor pago.")
    fonte = fabrica_fonte()
    dev = fonte.devedor(empresa_id, predicao_id)
    if dev is None:
        raise LookupError("Devedor não encontrado nas carteiras da empresa.")
    agora = agora or datetime.now(timezone.utc)
    promessas = [a for a in fonte.agenda_pendente(empresa_id, dev["id"]) if a.get("tipo") == "promessa"]
    for a in promessas:
        fonte.atualizar_agenda(empresa_id, dev["id"], a["id"], {"situacao": "cumprida", "resolvido_em": agora.isoformat(),
                                                                 "resolvido_por": "pagamento simulado (demonstração)"})
    if not avisar_pagamento(empresa_id, predicao_id, float(valor),
                            [{"id": a["id"], "valor": a.get("valor"), "data": str(a.get("data"))[:10]} for a in promessas],
                            agora, processar=True, origem="tela"):
        raise LookupError("Este devedor ainda não tem conversa com o agente.")
    return ver_caso(empresa_id, predicao_id)


def ciclo_agendado(agora: datetime | None = None) -> dict:
    """O que o agendador do servidor roda: relógio de cada empresa com política e a fila."""
    if not ligado():
        return {"ligado": False}
    agora = agora or datetime.now(timezone.utc)
    repo, fonte = fabrica_repo(), fabrica_fonte()
    criados = sum(len(planejar(repo, fonte, e, agora)) for e in repo.empresas_com_politica())
    feitos = orq.processar_fila(repo, grafos(fonte), fabrica_cliente(), limite=50, agora=agora)
    return {"ligado": True, "eventos_criados": criados, "processados": len(feitos)}


# ── Laboratório (Agente Cientista) ───────────────────────────────────────────

ERRO_TABELA = ("Falta a tabela das recomendações: rode backend/sql/migracao_recomendacoes.sql "
               "no SQL Editor do Supabase.")


def laboratorio(empresa_id: str) -> dict:
    """Recomendações do Cientista, da mais nova para a mais antiga."""
    try:
        recs = fabrica_repo().recomendacoes(empresa_id, 10)
    except Exception as e:
        print(f"[Agente] laboratório: {type(e).__name__}")
        return {"recomendacoes": [], "erro": ERRO_TABELA}
    return {"recomendacoes": recs, "ia_ligada": llm.ia_ligada("cientista")}


def analisar_laboratorio(empresa_id: str, agora: datetime | None = None) -> dict:
    """Roda as ferramentas estatísticas e o Cientista; grava a recomendação como proposta."""
    from agente import cientista
    from agente.rastreio import Rastreio
    agora = agora or datetime.now(timezone.utc)
    repo, fonte = fabrica_repo(), fabrica_fonte()
    obs = cientista.observacoes(repo, fonte, empresa_id)
    try:
        from model import bandit
        stats = bandit.convergencia_stats(empresa_id)
    except Exception as e:
        print(f"[Agente] bandit indisponível no laboratório: {type(e).__name__}")
        stats = []
    rt = Rastreio(empresa_id, repo.gravar_passo)
    ctx = orq.Contexto(caso={"id": None, "empresa_id": empresa_id, "situacao": "novo", "dados": {}},
                       evento={"id": None, "tipo": "laboratorio", "dados": {}}, repo=repo, rastreio=rt,
                       cliente=fabrica_cliente(), hoje=agora.date(), agora=agora)
    try:
        sinais = sinais_equipe(empresa_id, agora)
    except Exception as e:
        print(f"[Agente] sinais da equipe: {type(e).__name__}")
        sinais = None
    r = cientista.analisar(ctx, obs, stats, sinais)
    rel = r["relatorio"]
    try:
        return repo.gravar_recomendacao(empresa_id, {"texto": rel["recomendacao"], "selo": rel["selo"],
                                                     "origem": r["origem"], "relatorio": rel,
                                                     "resultados": r["resultados"]})
    except Exception as e:
        print(f"[Agente] gravar recomendação: {type(e).__name__}")
        raise RuntimeError(ERRO_TABELA) from e


def decidir_recomendacao(empresa_id: str, rec_id: str, status: str, quem: str | None) -> dict:
    if status not in ("aprovada", "recusada"):
        raise ValueError("Escolha aprovar ou recusar.")
    r = fabrica_repo().decidir_recomendacao(empresa_id, rec_id, status, quem)
    if r is None:
        raise LookupError("Essa recomendação já foi decidida ou não existe.")
    return r


def plano_do_dia(empresa_id: str) -> dict:
    """Prévia do plano do Estrategista (não grava nada)."""
    return _plano(fabrica_repo(), fabrica_fonte(), empresa_id, aplicar=False)


def aplicar_plano(empresa_id: str, agora: datetime | None = None) -> dict:
    """Grava grupos e sorteio, e envia a primeira mensagem do grupo 'contato'."""
    _exigir_ligado()
    agora = agora or datetime.now(timezone.utc)
    repo, fonte = fabrica_repo(), fabrica_fonte()
    r = _plano(repo, fonte, empresa_id, aplicar=True, agora=agora)
    # TODO junção: empresa_id=empresa_id
    r["processados"] = len(orq.processar_fila(repo, grafos(fonte), fabrica_cliente(), limite=200, agora=agora))
    return r


def politicas(empresa_id: str) -> dict:
    return {"versoes": fabrica_repo().politicas_da_empresa(empresa_id),
            "demonstracao": auditor.POLITICA_DEMONSTRACAO}


def salvar_politica(empresa_id: str, regras: dict, quem: str | None) -> dict:
    """Versão nova da política (validada). O agente obedece a partir do próximo evento."""
    limpa = auditor.validar_politica(regras)                 # ValueError com o motivo
    versao = fabrica_repo().nova_versao_politica(empresa_id, limpa, quem)
    return {"versao": versao, "regras": limpa}


def controle_do_gestor(empresa_id: str, predicao_id: str, acao: str, quem: str | None,
                       agora: datetime | None = None) -> dict:
    """Assumir (o agente para neste caso) ou devolver ao agente. Fica no rastreio."""
    nova = {"assumir": "com_pessoa", "devolver": "em_contato"}.get(acao)
    if nova is None:
        raise ValueError("Ação inválida: use assumir ou devolver.")
    agora = agora or datetime.now(timezone.utc)
    repo = fabrica_repo()
    caso = repo.caso_de(empresa_id, predicao_id)
    if caso is None:
        raise LookupError("Este devedor ainda não tem caso com o agente.")
    dono = f"gestor:{quem or ''}"
    if not repo.travar_caso(caso["id"], dono, agora + orq.DURACAO_TRAVA, agora):
        raise CasoOcupado("O agente está processando este caso agora. Tente de novo em instantes.")
    try:
        situacao = caso["situacao"] if caso["situacao"] == nova else estado.mudar(caso["situacao"], nova, por="pessoa")
        estado.anotar(caso, "equipe", "assumiu" if acao == "assumir" else "devolveu ao agente",
                      "o agente para neste caso" if acao == "assumir" else "o agente volta a responder", quando=agora)
        repo.salvar_caso(caso["id"], {"situacao": situacao, "dados": caso["dados"]}, dono=dono)
        rt = Rastreio(empresa_id, repo.gravar_passo, caso_id=caso["id"])
        with rt.span("controle_do_gestor", "pessoa") as p:
            p["detalhe"] = {"acao": acao, "de": caso["situacao"], "para": situacao}
    finally:
        repo.soltar_caso(caso["id"], dono)
    return ver_caso(empresa_id, predicao_id, repo)
