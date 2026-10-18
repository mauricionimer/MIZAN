"""Revisão da frente dos agentes analíticos (Estrategista, Acompanhamento,
Supervisor, passagem, Cientista e api). Um teste por correção, com dados fictícios."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

for _v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_IA_PAPEIS",
           "MIZAN_ESTRATEGISTA_MAX"):
    os.environ.pop(_v, None)

from agente import api, auditor, ciencia, cientista, estrategista, passagem
from agente import orquestrador as orq
from agente.bateria.motor import DIA, devedor, em
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria

REGRAS = auditor.POLITICA_DEMONSTRACAO
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
falhas = 0


def checar(cond, texto, extra=""):
    global falhas
    print(("ok    " if cond else "FALHA ") + texto + (f" ({extra})" if extra and not cond else ""))
    if not cond:
        falhas += 1


def com_papeis(papeis):
    os.environ["MIZAN_IA_PAPEIS"] = ",".join(("triagem", "negociador") + tuple(papeis))


def sem_papeis():
    os.environ.pop("MIZAN_IA_PAPEIS", None)


# ── 1. grupo de entrada fixo: quem fechou acordo não some do Cientista ──────

def t_grupo_entrada():
    repo, fonte = RepoMemoria(), FonteMemoria([devedor(id="p1", probabilidade_pagamento=0.4)])
    repo.gravar_politica("emp", 1, {**REGRAS, "percentual_controle": 0})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "contato" and c["dados"]["grupo_entrada"] == "contato", "1. primeiro plano grava grupo_entrada")
    repo.salvar_caso(c["id"], {"situacao": "acordo_ativo"})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA + timedelta(days=1)))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "so_lembrete" and c["dados"]["grupo_entrada"] == "contato",
           "1. plano seguinte muda o grupo, mas não o de entrada", str((c["grupo"], c["dados"].get("grupo_entrada"))))
    checar(len(cientista.observacoes(repo, fonte, "emp")) == 1, "1. caso com acordo continua na conta do Cientista")


# ── 2. selo com direção: agente pior não ganha "evidência" ──────────────────

def _obs(n, p, grupo, dias=95, produto="cartao"):
    o = []
    for i in range(n):
        pagou = (i % 100) < p * 100
        o.append({"grupo": grupo, "pagou": pagou, "recuperado": 900.0 if pagou else 0.0, "divida": 3000.0,
                  "chance": 0.1 + (i % 10) * 0.05, "dias": dias, "produto": produto, "teve_acordo": pagou,
                  "quebrou": False})
    return o


def t_selo_com_direcao():
    pior = ciencia.analisar(_obs(200, 0.15, "agente") + _obs(200, 0.45, "sorteado"))
    t = pior["comparacao"]["taxa_pagamento"]
    checar(t["selo"] == ciencia.SEM_EVIDENCIA and t["direcao"] == ciencia.PIOR,
           "2. agente pior: sem evidência e direcao 'pior'", str(t))
    rc = cientista.relatorio_codigo(pior)
    checar("rever a abordagem" in rc["recomendacao"] and "Manter" not in rc["recomendacao"]
           and rc["direcao"] == ciencia.PIOR, "2. relatório em código recomenda rever a abordagem", rc["recomendacao"])
    melhor = ciencia.analisar(_obs(200, 0.45, "agente") + _obs(200, 0.15, "sorteado"))
    t = melhor["comparacao"]["taxa_pagamento"]
    checar(t["selo"] == ciencia.EVIDENCIA and t["direcao"] == ciencia.MELHOR, "2. agente melhor continua com evidência")
    checar(ciencia.selo(200, 200, -0.3, -0.2, True) == ciencia.SEM_EVIDENCIA, "2. selo() nunca dá evidência abaixo de zero")
    # IA que manda manter com o agente pior é reprovada nas travas e vale o relatório em código
    rel = json.dumps({"resumo": "O agente ainda não mostra resultado.", "hipoteses": [
        {"hipotese": "Procurar ajuda", "metrica": "taxa_pagamento", "resultado": "Ainda incerto.",
         "condicoes": "Carteira atual.", "proximo_experimento": "Seguir o sorteio."}],
        "recomendacao": "Manter a abordagem atual.", "recomendacao_metrica": "taxa_pagamento"})
    com_papeis(("cientista",))
    r = cientista.analisar(_ctx(ClienteFalso({"cientista": [rel, rel]})), _obs(200, 0.15, "agente")
                           + _obs(200, 0.45, "sorteado"), [])
    checar(r["origem"] == "codigo" and "rever a abordagem" in r["relatorio"]["recomendacao"],
           "2. IA que manda manter com agente pior cai na reserva", r["relatorio"]["recomendacao"])


def _ctx(cliente, caso=None, agora=None):
    from agente.rastreio import Rastreio
    repo = RepoMemoria()
    repo.gravar_politica("emp", 1, REGRAS)
    agora = agora or AGORA
    return orq.Contexto(caso=caso or {"id": None, "empresa_id": "emp", "situacao": "novo", "dados": {}},
                        evento={"id": None, "tipo": "laboratorio", "dados": {}}, repo=repo,
                        rastreio=Rastreio("emp", repo.gravar_passo), cliente=cliente, hoje=agora.date(), agora=agora)


# ── 7. Cientista: travas e hipóteses ────────────────────────────────────────

def t_cientista_travas():
    res = ciencia.analisar(_obs(40, 0.3, "agente") + _obs(40, 0.25, "sorteado"))
    perm = cientista._numeros_permitidos(res)
    for txt in ("Não há dúvida de que o agente causou a alta.", "Não resta dúvida: isso garante mais pagamentos.",
                "O agente aumentou a taxa de pagamento.", "O agente elevou o recebimento.",
                "O efeito do agente é claro.", "Sem dúvida o agente funciona."):
        checar(cientista.conferir(txt, perm, False), f"7. trava causal barra: {txt}")
    for txt in ("Ainda não há evidência de efeito do agente.", "Sem selo, não dá para dizer que o agente aumentou a taxa."):
        checar(not cientista.conferir(txt, perm, False), f"7. ressalva honesta passa: {txt}",
               str(cientista.conferir(txt, perm, False)))
    for txt, oferta in (("Manter o agente ligado nesta carteira.", False), ("Uma parcela dos devedores responde melhor.", False),
                        ("Testar parcelado_12x primeiro.", True), ("Começar pelo WhatsApp.", True),
                        ("Oferecer 30% de desconto.", True), ("Testar o parcelamento em 12x.", True)):
        checar(bool(cientista._OFERTA.search(txt)) == oferta, f"7. _OFERTA {'pega' if oferta else 'não pega'}: {txt}")


def t_cientista_segmentos_e_faixa():
    obs = _obs(200, 0.45, "agente") + _obs(200, 0.15, "sorteado")
    segs = ciencia.segmentos(obs)
    checar(segs and all(s["taxa_pagamento"]["selo"] != ciencia.EVIDENCIA for s in segs),
           "7. segmento tem no máximo 'indício'", str([s["taxa_pagamento"]["selo"] for s in segs]))
    checar(ciencia._faixa(-5) == "sem atraso" and ciencia._faixa(0) == "sem atraso"
           and ciencia._faixa(1) == "até 90 dias" and ciencia._faixa(400) == "mais de 360 dias",
           "7. _faixa: dias <= 0 é 'sem atraso', não 'mais de 360'")


def t_cientista_hipotese_passagens():
    sinais_motivo = {"dias": 7, "passagens": 4, "nao_coube": 0, "por_motivo": {"pedido_do_devedor": 3, "falha": 1}}
    h = cientista._hipotese_passagens(sinais_motivo)[0]
    checar("deixa de fora" not in h["hipotese"] and "pedido_do_devedor" in h["hipotese"],
           "7. hipótese das passagens sem 'não coube' tem título próprio", h["hipotese"])
    sinais_nc = {"dias": 7, "passagens": 4, "nao_coube": 2, "valor_pedido_quando_nao_coube": 200.0,
                 "menor_parcela_possivel": 787.5, "por_motivo": {"pedido_do_devedor": 4}}
    checar("deixa de fora" in cientista._hipotese_passagens(sinais_nc)[0]["hipotese"], "7. com 'não coube' o título fala da política")
    hip = {"hipotese": "H", "resultado": "Ainda não dá para concluir.", "condicoes": "Carteira atual.",
           "proximo_experimento": "Seguir o sorteio."}
    rel = json.dumps({"resumo": "Ainda não dá para concluir.", "hipoteses": [
        {**hip, "metrica": "taxa_pagamento"}, {**hip, "metrica": "recuperado_por_real"}, {**hip, "metrica": "bandit"}],
        "recomendacao": "Seguir o sorteio do grupo de comparação.", "recomendacao_metrica": "taxa_pagamento"})
    com_papeis(("cientista",))
    r = cientista.analisar(_ctx(ClienteFalso({"cientista": [rel]})), _obs(10, 0.3, "agente") + _obs(10, 0.3, "sorteado"),
                           [], sinais_nc)
    hips = r["relatorio"]["hipoteses"]
    checar(r["origem"] == "ia" and len(hips) == cientista.MAX_HIPOTESES and hips[-1]["metrica"] == "passagens"
           and hips[0]["metrica"] == "taxa_pagamento", "7. hipótese das passagens entra sem passar de MAX_HIPOTESES",
           str([h["metrica"] for h in hips]))


# ── 4. passagem: "cabe" exige entrada e parcela no valor dito ───────────────

def _caso_pass(divida, valores, simulacoes=None):
    return {"id": "c1", "empresa_id": "emp", "situacao": "negociando",
            "dados": {"divida": divida, "identidade_ok": True, "valores_ditos": valores, "simulacoes": simulacoes or []}}


def t_passagem_cabe():
    s = passagem.sugerir_proposta(_caso_pass(15000.0, [800.0]), REGRAS, 1, AGORA)
    checar(s["cabe"] is False, "4. entrada de R$ 1.050 não cabe em R$ 800: não é 'cabe'", str(s))
    s = passagem.sugerir_proposta(_caso_pass(3000.0, [300.0]), REGRAS, 1, AGORA)
    validas = passagem._validas(_caso_pass(3000.0, []), REGRAS, 1, AGORA)
    conta = next(v[1] for v in validas if v[0]["n_parcelas"] == s["n_parcelas"] and v[0]["desconto_pct"] == s["desconto_pct"])
    checar(s["cabe"] is True and s["mensal"] <= 300 and conta["entrada"] <= 300, "4. 'cabe' com parcela e entrada <= valor dito")
    # A única que cabe já foi oferecida: continua "cabe", com o aviso.
    cabem = [v for v in validas if passagem._mensal(*v) <= 300 and v[1]["entrada"] <= 300]
    sims = [{"condicoes": c, "conta": k} for c, k in cabem]
    s = passagem.sugerir_proposta(_caso_pass(3000.0, [300.0], sims), REGRAS, 1, AGORA)
    checar(s["cabe"] is True and "já foi oferecida" in s["motivo"], "4. 'cabe, mas já foi oferecida'", str(s))
    f = passagem.montar_ficha(_caso_pass(3000.0, [300.0], sims), "pedido_do_devedor", None, REGRAS, 1, AGORA)
    c = _caso_pass(3000.0, [300.0], sims)
    passagem.guardar(c, f)
    checar(passagem.sinais_da_equipe([c], AGORA)["nao_coube"] == 0, "4. já oferecida que cabe não conta como 'não coube'")


# ── 5. Supervisor: "Oferecido" do código, números conferidos, sem IA não aprova ──

def _resumo_ia(**d):
    base = {"situacao": "Quer negociar.", "o_que_quer": "Parcelar.", "emocao": "Calmo.",
            "proximo_passo": "Oferecer a sugestão do sistema.", "emocao_nivel": "calmo", "urgencia": "baixa"}
    return json.dumps({**base, **d})


def _ctx_sup(cliente, dados=None):
    from agente.rastreio import Rastreio
    repo = RepoMemoria()
    repo.gravar_politica("emp", 1, REGRAS)
    caso = repo.obter_ou_criar_caso("emp", "p9")
    caso["situacao"] = "negociando"
    caso["dados"] = dados or {"divida": 3000.0, "identidade_ok": True}
    return orq.Contexto(caso=caso, evento={"id": None, "tipo": "mensagem_devedor", "dados": {}}, repo=repo,
                        rastreio=Rastreio("emp", repo.gravar_passo), cliente=cliente, hoje=AGORA.date(), agora=AGORA)


def t_supervisor():
    from agente import supervisor
    com_papeis(("supervisor",))
    # A IA diz que ofereceu 24x (nada foi simulado): "Oferecido" é do código.
    ctx = _ctx_sup(ClienteFalso({"supervisor": [_resumo_ia(oferecido="Já ofereci 24x de R$ 50,00.")]}))
    txt = supervisor.resumo_para_pessoa(ctx, "transferido (pedido_do_devedor)", "Pediu pessoa.", "pedido_do_devedor")
    checar("Oferecido: nada ainda" in txt and "24x" not in txt, "5. 'Oferecido' montado em código", txt)
    # Próximo passo com número inventado: vale a reserva.
    ctx = _ctx_sup(ClienteFalso({"supervisor": [_resumo_ia(proximo_passo="Fechar 24x de R$ 50,00.")]}))
    txt = supervisor.resumo_para_pessoa(ctx, "transferido (pedido_do_devedor)", "Pediu pessoa.", "pedido_do_devedor")
    checar(txt.startswith("Pediu pessoa.") and "24x" not in txt, "5. número fora de tentado/sugestão: reserva", txt)
    # Próximo passo com os números da sugestão: passa.
    sug = passagem.sugerir_proposta({"dados": {"divida": 3000.0}}, REGRAS, 1, AGORA)
    ctx = _ctx_sup(ClienteFalso({"supervisor": [_resumo_ia(proximo_passo=f"Oferecer {sug['resumo']}.")]}))
    txt = supervisor.resumo_para_pessoa(ctx, "transferido (pedido_do_devedor)", "Pediu pessoa.", "pedido_do_devedor")
    checar("Próximo passo: Oferecer" in txt, "5. números da sugestão passam", txt)
    # Revisão sem IA não é "aprovado".
    sem_papeis()
    ctx = _ctx_sup(ClienteFalso({}))
    checar(supervisor.revisar(ctx, "Pague logo.", "irritado") is None, "5. sem IA a revisão não pede reescrita")
    p = ctx.repo.passos[-1]
    checar(p["no"] == "revisao" and p["detalhe"].get("aprovado") is None, "5. sem IA não grava 'aprovado'", str(p["detalhe"]))
    checar(api._explicar(p).startswith("não revisou (sem IA)"), "5. tela mostra 'não revisou (sem IA)'", api._explicar(p))
    com_papeis(("supervisor",))
    ctx = _ctx_sup(ClienteFalso({"supervisor": [json.dumps({"aprovado": True, "problema": ""})]}))
    supervisor.revisar(ctx, "Entendo, vamos ver juntos.", "irritado")
    p = ctx.repo.passos[-1]
    checar(p["detalhe"].get("aprovado") is True and "aprovado" in api._explicar(p), "5. com IA continua 'aprovado'")


# ── 8 e 9. api: leitura em lote, retorno com trava, dia de Brasília ─────────

class RepoContado(RepoMemoria):
    """RepoMemoria que conta as leituras da carteira inteira."""
    def __init__(self):
        super().__init__()
        self.leituras = {"casos_da_empresa": 0, "caso_de": 0, "casos_por_predicoes": 0}

    def casos_da_empresa(self, *a, **k):
        self.leituras["casos_da_empresa"] += 1
        return super().casos_da_empresa(*a, **k)

    def caso_de(self, *a, **k):
        self.leituras["caso_de"] += 1
        return super().caso_de(*a, **k)

    def casos_por_predicoes(self, *a, **k):
        self.leituras["casos_por_predicoes"] += 1
        return super().casos_por_predicoes(*a, **k)


def t_api_lotes():
    repo, fonte = RepoContado(), FonteMemoria([devedor(id=f"p{i}") for i in range(5)])
    for i in range(5):
        repo.obter_ou_criar_caso("emp", f"p{i}")
    c = repo.caso_de("emp", "p1")
    repo.salvar_caso(c["id"], {"dados": {"passagem": {"quando": AGORA.isoformat(), "motivo": "falha", "emocao": "calmo",
                                                      "urgencia": "baixa"}}})
    fonte.criar_agenda("emp", devedor(id="p1"), "retorno", "2026-10-20",
                       observacao="Transferido pelo assistente (falha): resumo", operador=("a-definir", "A definir"))
    fonte._operadores = [{"id": "op9", "nome": "Ana"}]
    antes = api.fabrica_repo, api.fabrica_fonte
    api.fabrica_repo, api.fabrica_fonte = (lambda: repo), (lambda: fonte)
    try:
        repo.leituras = dict.fromkeys(repo.leituras, 0)
        f = api.passagens_da_fila("emp", ["p1", "p3"], AGORA)
        a = api.agenda("emp")
        item = a["itens"][0]
        r = api.atribuir("emp", item["id"], "op9")
        checar(set(f) == {"p1"} and a["itens"][0]["passagem"] and r["ok"], "8. fila, agenda e atribuir funcionam em lote")
        checar(repo.leituras["casos_da_empresa"] == 0 and repo.leituras["casos_por_predicoes"] == 2,
               "8. sem ler a carteira inteira de casos", str(repo.leituras))
        # Retorno do atendente: trava o caso e grava com dono.
        rr = api.registrar_retorno_passagem("emp", "p1", True, "ana@x", "ajudou", agora=AGORA)
        c = repo.caso_de("emp", "p1")
        checar(rr["ajudou"] and c["dados"]["passagem"]["retorno"]["por"] == "ana@x" and c["trava_dono"] is None,
               "8. retorno grava e solta a trava")
        repo.travar_caso(c["id"], "agente", AGORA + timedelta(minutes=5), AGORA)
        try:
            api.registrar_retorno_passagem("emp", "p1", False, "ana@x", agora=AGORA)
            checar(False, "8. caso travado pelo agente: retorno espera (CasoOcupado)")
        except api.CasoOcupado:
            checar(repo.caso_de("emp", "p1")["dados"]["passagem"]["retorno"]["ajudou"] is True,
                   "8. caso travado pelo agente: retorno espera (CasoOcupado)")
    finally:
        api.fabrica_repo, api.fabrica_fonte = antes


def t_plano_sem_consulta_por_devedor():
    repo, fonte = RepoContado(), FonteMemoria([devedor(id=f"p{i}") for i in range(30)])
    repo.gravar_politica("emp", 1, {**REGRAS, "percentual_controle": 0})
    estrategista.plano(repo, fonte, "emp", aplicar=False)
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    checar(repo.leituras["caso_de"] == 0 and repo.leituras["casos_por_predicoes"] <= 2,
           "8. plano não faz uma consulta por devedor", str(repo.leituras))


def t_custo_do_dia_brasilia():
    repo = RepoMemoria()
    dias = []
    repo.custo_do_dia = lambda emp, dia: dias.append(dia) or 0.0
    antes = api.fabrica_repo
    api.fabrica_repo = lambda: repo
    try:
        noite = datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc)          # 22h30 do dia 19 em Brasília
        api.central("emp", noite)
        api.agentes("emp", noite)
    finally:
        api.fabrica_repo = antes
    checar(dias == [date(2026, 10, 19)] * 2, "9. custo do dia usa o dia de Brasília", str(dias))
    import inspect
    fonte_api = inspect.getsource(api)
    checar(fonte_api.count("empresa_id=empresa_id)") >= 4 and "TODO junção" not in fonte_api,
           "9. as 4 chamadas de processar_fila só processam a fila da própria empresa")


# ── 6. Estrategista com IA ──────────────────────────────────────────────────

BANDIT = {"oferta": "desconto_30pct", "modo": "calibrado", "total_interacoes": 12, "canal": "whatsapp",
          "n_tentativas_acao": 4}


def _dec_est(**d):
    base = {"decisao": "abordar", "tom": "acolhedor", "oferta_inicial": "parcelado_12x", "concorda_bandit": True,
            "raciocinio": "sigo o modelo", "mensagem": "Temos condições para regularizar a sua pendência. Podemos conversar?"}
    return json.dumps({**base, **d})


def _mundo_est(ids, bandit=None, politica=None):
    repo, fonte = RepoMemoria(), FonteMemoria([devedor(id=i, probabilidade_pagamento=0.3) for i in ids])
    fonte._bandit = dict(bandit or BANDIT)
    repo.gravar_politica("emp", 1, {**REGRAS, "percentual_controle": 0, **(politica or {})})
    return repo, fonte


def t_estrategista_ia():
    from agente import estrategista_ia
    com_papeis(("estrategista",))
    # concorda_bandit é conta do código, não palavra da IA
    repo, fonte = _mundo_est(["p0"])
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    cli = ClienteFalso({"estrategista": [_dec_est()]})
    orq.processar_fila(repo, api.grafos(fonte), cli, limite=50, agora=em(DIA))
    est = repo.caso_de("emp", "p0")["dados"]["estrategia"]
    checar(est["oferta_inicial"] == "parcelado_12x" and est["concorda_bandit"] is False,
           "6. IA diz que concorda, mas a oferta é outra: concorda_bandit False", str(est))
    ficha = json.loads(cli.chamadas[0]["mensagens"][0]["content"].removeprefix("<ficha>").removesuffix("</ficha>"))
    checar(ficha["bandit"]["resultados_desta_oferta"] == 4 and ficha["bandit"]["dentro_da_politica"] is True,
           "6. ficha traz nº de resultados da oferta e se ela cabe na política", str(ficha["bandit"]))
    checar("centenas" not in estrategista_ia.SISTEMA and "pelo menos 3" in estrategista_ia.SISTEMA
           and estrategista_ia.VERSAO_PROMPT == "estrategista-v2", "6. prompt honesto sobre 'calibrado' (estrategista-v2)")
    # bandit com oferta fora da política
    repo, fonte = _mundo_est(["p0"], politica={"desconto_max_pct": 20.0})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    cli = ClienteFalso({"estrategista": [_dec_est()]})
    orq.processar_fila(repo, api.grafos(fonte), cli, limite=50, agora=em(DIA))
    ficha = json.loads(cli.chamadas[0]["mensagens"][0]["content"].removeprefix("<ficha>").removesuffix("</ficha>"))
    checar(ficha["bandit"]["dentro_da_politica"] is False, "6. oferta do bandit fora da política aparece como tal")
    # limite por dia, não por chamada do plano
    os.environ["MIZAN_ESTRATEGISTA_MAX"] = "1"
    try:
        repo, fonte = _mundo_est(["q0"])
        estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
        orq.processar_fila(repo, api.grafos(fonte), ClienteFalso({"estrategista": [_dec_est(), _dec_est()]}),
                           limite=50, agora=em(DIA))
        fonte._devedores["q1"] = devedor(id="q1", probabilidade_pagamento=0.3)
        estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA) + timedelta(hours=2))
        com_ia = {e["chave"]: e["dados"].get("com_ia") for e in repo.eventos.values()}
        checar(com_ia == {"abordagem:q0": True, "abordagem:q1": False}, "6. limite diário vale para o dia, não por chamada",
               str(com_ia))
        fonte._devedores["q2"] = devedor(id="q2", probabilidade_pagamento=0.3)
        estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA + timedelta(days=3)))     # outro dia
        checar(repo.evento_por_chave("emp", "abordagem:q2")["dados"]["com_ia"] is True, "6. no dia seguinte o limite recomeça")
    finally:
        os.environ.pop("MIZAN_ESTRATEGISTA_MAX", None)


# ── 3. Acompanhamento ───────────────────────────────────────────────────────

def _acomp(passos, roteiro=None, venc="2026-10-20"):
    from agente.bateria.motor import ID_OK, Cenario, executar
    acordo = {**ID_OK, "acordo": {"condicoes": {"n_parcelas": 6, "desconto_pct": 10, "entrada_pct": 10},
                                  "primeiro_pagamento": 270.0, "data": venc}}
    c = Cenario("t", "t", "t", passos=passos, conferir=[], situacao="acordo_ativo", dados=acordo,
                agenda=[("promessa", venc, 270.0)])
    if roteiro is not None:
        com_papeis(("acompanhamento",))
    try:
        r = executar(c, ClienteFalso({"acompanhamento": list(roteiro or [])}))
    finally:
        sem_papeis()
    if r.erro_inesperado:
        raise RuntimeError(r.erro_inesperado)
    return r


def _ia_acomp(**d):
    return json.dumps({"motivo": "teste", "mensagem": "", **d})


def t_acompanhamento_relogio_parado():
    # Vence 20/10; o relógio só volta em 03/11 (servidor dormiu): atraso e "sem resposta" na mesma rodada.
    r = _acomp([("relogio", None, em(date(2026, 11, 3)))])
    caso = r.repo.casos[r.caso["id"]]
    prom = [a for a in r.fonte.agenda if a["tipo"] == "promessa"][0]
    checar(caso["situacao"] == "atrasado" and len(r.saidas) == 1 and prom["situacao"] == "pendente",
           "3. relógio parado: cobra o atraso e não quebra a promessa na mesma rodada",
           f"{caso['situacao']} {len(r.saidas)} {prom['situacao']}")
    r = _acomp([("relogio", None, em(date(2026, 11, 3))), ("relogio", None, em(date(2026, 11, 5)))])
    checar(r.repo.casos[r.caso["id"]]["situacao"] == "atrasado", "3. antes dos dias úteis de espera, não passa para a equipe")
    r = _acomp([("relogio", None, em(date(2026, 11, 3))), ("relogio", None, em(date(2026, 11, 6), 10))])
    caso = r.repo.casos[r.caso["id"]]
    prom = [a for a in r.fonte.agenda if a["tipo"] == "promessa"][0]
    checar(caso["situacao"] == "com_pessoa" and prom["situacao"] == "quebrada",
           "3. depois de 3 dias úteis da cobrança: promessa quebrada e equipe", caso["situacao"])


def t_acompanhamento_lembrete_segunda():
    # Vence segunda 26/10: o lembrete de domingo é adiado para segunda e o de segunda não repete.
    r = _acomp([("relogio", None, em(date(2026, 10, 25), 10)), ("relogio", None, em(date(2026, 10, 26), 9))],
               venc="2026-10-26")
    checar(len(r.saidas) == 1, "3. vencimento na segunda: um lembrete só", str(r.saidas))
    chaves = sorted(e["chave"].split(":")[0] + ":" + e["chave"].split(":")[-1] for e in r.repo.eventos.values())
    checar(chaves == ["lembrete:2026-10-26"], "3. chave do lembrete é compromisso + vencimento (não o dia de hoje)", str(chaves))


def t_acompanhamento_esperar_no_atraso():
    sex = em(date(2026, 10, 23))
    r = _acomp([("relogio", None, sex)], [_ia_acomp(acao="esperar", motivo="disse que paga segunda")])
    caso = r.repo.casos[r.caso["id"]]
    ev = next(e for e in r.repo.eventos.values() if e["chave"].startswith("venceu:"))
    checar(caso["situacao"] == "acordo_ativo" and "atraso" not in caso["dados"] and not r.saidas,
           "3. 'esperar' no atraso não grava atraso.desde nem muda a situação", str(caso["dados"].get("atraso")))
    checar(ev["situacao"] == "pendente" and ev["disponivel_em"] == em(date(2026, 10, 26)),
           "3. 'esperar' reagenda para o próximo dia útil, mesma hora", str(ev["disponivel_em"]))
    r = _acomp([("relogio", None, sex), ("relogio", None, em(date(2026, 10, 26)))],
               [_ia_acomp(acao="esperar", motivo="de novo"), _ia_acomp(acao="esperar", motivo="de novo")])
    caso = r.repo.casos[r.caso["id"]]
    checar(caso["situacao"] == "atrasado" and caso["dados"].get("atraso") and len(r.saidas) == 1
           and "Aconteceu alguma coisa?" in r.saidas[0], "3. segunda espera não vale: cobra com o texto pronto")


def t_acompanhamento_chamar_pessoa_motivo():
    r = _acomp([("relogio", None, em(date(2026, 10, 23)))], [_ia_acomp(acao="chamar_pessoa", motivo="já quebrou antes")])
    caso = r.repo.casos[r.caso["id"]]
    checar(caso["situacao"] == "com_pessoa" and caso["dados"]["passagem"]["motivo"] == "falha",
           "3. chamar_pessoa no atraso vai como 'falha', não 'dificuldade_grave'", caso["dados"].get("passagem", {}).get("motivo"))
    from agente import acompanhamento
    checar(acompanhamento.VERSAO_PROMPT == "acompanhamento-v2", "3. acompanhamento-v2")


def t_acompanhamento_esperar_mais_brasilia():
    noite = em(date(2026, 10, 28), 22)                        # 22h em Brasília = 01h UTC do dia 29
    r = _acomp([("relogio", None, em(date(2026, 10, 23))), ("relogio", None, noite)],
               [_ia_acomp(acao="procurar", mensagem="Oi, Maria. A parcela de 20/10 ficou pendente. Aconteceu algo?"),
                _ia_acomp(acao="esperar_mais", motivo="disse que recebe dia 29")])
    ev = next((e for e in r.repo.eventos.values() if e["chave"].startswith("sem_resposta2:")), None)
    checar(ev is not None and ev["disponivel_em"] == em(date(2026, 10, 30), 22),
           "3. esperar_mais volta em 2 dias úteis na mesma hora de Brasília", str(ev and ev["disponivel_em"]))


TESTES = [t_grupo_entrada, t_selo_com_direcao, t_cientista_travas, t_cientista_segmentos_e_faixa,
          t_cientista_hipotese_passagens, t_passagem_cabe, t_supervisor, t_api_lotes, t_plano_sem_consulta_por_devedor,
          t_custo_do_dia_brasilia, t_estrategista_ia, t_acompanhamento_relogio_parado, t_acompanhamento_lembrete_segunda,
          t_acompanhamento_esperar_no_atraso, t_acompanhamento_chamar_pessoa_motivo, t_acompanhamento_esperar_mais_brasilia]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception as e:                          # um teste quebrado não esconde os outros
            import traceback
            traceback.print_exc()
            checar(False, f"{t.__name__} levantou {type(e).__name__}: {e}")
        finally:
            sem_papeis()
    print(f"\n{'TUDO OK' if not falhas else f'{falhas} falha(s)'}")
    sys.exit(falhas)
