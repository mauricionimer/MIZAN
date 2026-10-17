"""Etapa 6: Cientista — contas e selo em código, travas no texto, aprovação por pessoa."""
import json
import os
import random

from agente import ciencia, cientista
from agente import api as agente_api
from agente.bateria.motor import DIA, em
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria


def obs_sinteticas(n_a, n_s, pa, ps, semente=1, dias_s=95):
    rnd = random.Random(semente)
    o = []
    for g, n, p, dias in (("agente", n_a, pa, 95), ("sorteado", n_s, ps, dias_s)):
        for i in range(n):
            pagou = rnd.random() < p
            o.append({"grupo": g, "pagou": pagou, "recuperado": 900.0 if pagou else 0.0, "divida": 3000.0,
                      "chance": 0.1 + (i % 10) * 0.05, "dias": dias, "produto": "cartao",
                      "teve_acordo": pagou, "quebrou": False})
    return o


def test_wilson_e_newcombe():
    p, lo, hi = ciencia.wilson(10, 100)
    assert round(lo, 4) == 0.0552 and round(hi, 4) == 0.1744
    d, lo, hi = ciencia.diferenca_taxas(30, 100, 10, 100)
    assert round(d, 2) == 0.2 and 0.08 < lo < 0.10 and 0.30 < hi < 0.32


def test_selo_em_codigo():
    assert ciencia.comparar_grupos(obs_sinteticas(20, 20, 0.9, 0.1))["taxa_pagamento"]["selo"] == "sem evidência"  # n < 30
    assert ciencia.comparar_grupos(obs_sinteticas(200, 200, 0.30, 0.29))["taxa_pagamento"]["selo"] == "sem evidência"
    assert ciencia.comparar_grupos(obs_sinteticas(200, 200, 0.45, 0.15))["taxa_pagamento"]["selo"] == "evidência"
    c = ciencia.comparar_grupos(obs_sinteticas(200, 200, 0.45, 0.15, dias_s=300))       # composição diferente
    assert not c["composicao"]["comparaveis"] and c["taxa_pagamento"]["selo"] == "indício"


class Ctx:
    """Contexto mínimo com cliente falso por papel."""
    def __init__(self, roteiro):
        os.environ["MIZAN_IA_PAPEIS"] = "triagem,negociador,cientista"
        self.repo, self.fonte = RepoMemoria(), FonteMemoria([])
        from agente.orquestrador import Contexto
        from agente.rastreio import Rastreio
        self.c = Contexto(caso={"id": None, "empresa_id": "emp", "situacao": "novo", "dados": {}},
                          evento={"id": None, "tipo": "laboratorio", "dados": {}}, repo=self.repo,
                          rastreio=Rastreio("emp", self.repo.gravar_passo), cliente=ClienteFalso({"cientista": roteiro}),
                          hoje=em(DIA).date(), agora=em(DIA))


def rel(**kw):
    base = {"resumo": "Com 20 casos por grupo, ainda não dá para concluir.",
            "hipoteses": [{"hipotese": "O agente aumenta o pagamento", "metrica": "taxa_pagamento",
                           "resultado": "Ainda sem evidência: faltam casos.", "condicoes": "carteira de cartão",
                           "proximo_experimento": "Manter o sorteio até 30 casos por grupo."}],
            "recomendacao": "Manter a abordagem atual e o sorteio."}
    return json.dumps({**base, **kw})


def test_numero_inventado_reprova_e_vira_relatorio_de_codigo():
    obs = obs_sinteticas(20, 20, 0.5, 0.2)
    ctx = Ctx([rel(resumo="O agente subiu o pagamento em 37,9%."), rel(resumo="Melhora de 41%.")])
    try:
        r = cientista.analisar(ctx.c, obs, [])
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)
    assert r["origem"] == "codigo" and "Agente: 20 casos" in r["relatorio"]["resumo"]
    assert "30 casos por grupo" in r["relatorio"]["recomendacao"]


def test_causal_sem_evidencia_reprova_e_selo_ignora_a_ia():
    obs = obs_sinteticas(20, 20, 0.5, 0.2)
    ctx = Ctx([rel(recomendacao="Está comprovado que o agente funciona."),
               rel(hipoteses=[{"hipotese": "x", "metrica": "taxa_pagamento", "resultado": "y", "condicoes": "",
                               "proximo_experimento": "", "selo": "evidência"}])])
    try:
        r = cientista.analisar(ctx.c, obs, [])
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)
    assert r["origem"] == "ia" and r["relatorio"]["selo"] == "sem evidência"        # a IA disse evidência; vale o código
    pedido = json.dumps(ctx.c.cliente.chamadas[1]["mensagens"], ensure_ascii=False)
    assert "comprovado" in pedido and "sem selo de evidência" in pedido


def test_numero_dos_resultados_passa():
    obs = obs_sinteticas(200, 200, 0.45, 0.15)
    res = ciencia.analisar(obs, [])
    t = res["comparacao"]["taxa_pagamento"]
    frase = f"Agente {t['agente'] * 100:.1f}% contra {t['sorteado'] * 100:.1f}% no sorteado, com 200 casos por grupo."
    assert cientista.conferir(frase, cientista._numeros_permitidos(res), True) == []
    assert cientista.conferir("Agente 99,9% melhor.", cientista._numeros_permitidos(res), True)
    r = res["comparacao"]["recuperado_por_real"]
    assert cientista.conferir(f"R$ por real: {r['agente']} contra {r['sorteado']}.", cientista._numeros_permitidos(res), True) == []
    assert cientista._valor("3.000") == 3000.0 and cientista._valor("0.1365") == 0.1365


def test_negacao_passa_e_oferta_vira_bandit():
    perm = {30.0}
    assert cientista.conferir("Ainda não há evidência estatística: faltam casos.", perm, False) == []
    assert cientista.conferir("Sem evidência estatística definitiva por enquanto.", perm, False) == []
    assert cientista.conferir("O 12x demonstra os melhores resultados.", perm, False)
    obs = obs_sinteticas(200, 200, 0.45, 0.15)
    ctx = Ctx([rel(hipoteses=[{"hipotese": "O agente aumenta o pagamento", "metrica": "taxa_pagamento",
                               "resultado": "ok", "condicoes": "", "proximo_experimento": ""},
                              {"hipotese": "12x rende mais", "metrica": "bandit", "resultado": "sugestão do bandit",
                               "condicoes": "", "proximo_experimento": ""}],
                   recomendacao="Priorize o parcelamento em 12x, pois há evidência de maior retorno.",
                   recomendacao_metrica="taxa_pagamento", resumo="O agente teve efeito; o bandit sugere uma oferta."),
               rel(hipoteses=[{"hipotese": "O agente aumenta o pagamento", "metrica": "taxa_pagamento",
                               "resultado": "ok", "condicoes": "", "proximo_experimento": ""},
                              {"hipotese": "12x rende mais", "metrica": "bandit", "resultado": "sugestão do bandit",
                               "condicoes": "", "proximo_experimento": ""}],
                   recomendacao="Testar o parcelamento em 12x contra o desconto, mantendo o sorteio.",
                   recomendacao_metrica="taxa_pagamento", resumo="O agente teve efeito; o bandit sugere uma oferta.")])
    try:
        r = cientista.analisar(ctx.c, obs, [])
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)
    assert r["origem"] == "ia" and r["relatorio"]["recomendacao_metrica"] == "bandit"
    assert r["relatorio"]["selo"] == "sem evidência" and len(ctx.c.cliente.chamadas) == 2


def test_fluxo_completo_aprovar_e_orientar_o_estrategista():
    repo, fonte = RepoMemoria(), FonteMemoria([{"id": f"p{i}", "valor_divida": 3000.0, "dias_em_atraso": 95,
                                                "produto": "cartao", "probabilidade_pagamento": 0.3} for i in range(40)])
    for i in range(40):
        c = repo.obter_ou_criar_caso("emp", f"p{i}")
        repo.salvar_caso(c["id"], {"grupo": "contato", "grupo_controle": i % 2 == 1, "dados": {"chance": 0.3}})
    fonte.pagos = {f"p{i}": 900.0 for i in range(0, 40, 4)}
    antes = (agente_api.fabrica_repo, agente_api.fabrica_fonte, agente_api.fabrica_cliente)
    agente_api.fabrica_repo, agente_api.fabrica_fonte = (lambda: repo), (lambda: fonte)
    agente_api.fabrica_cliente = lambda: ClienteFalso({})
    try:
        rec = agente_api.analisar_laboratorio("emp", agora=em(DIA))        # cientista desligado: texto em código
        assert rec["status"] == "proposta" and rec["origem"] == "codigo" and rec["selo"] == "sem evidência"
        assert rec["resultados"]["comparacao"]["n"] == {"agente": 20, "sorteado": 20}
        assert agente_api.laboratorio("emp")["recomendacoes"][0]["versao"] == 1
        assert repo.recomendacao_aprovada("emp") is None
        agente_api.decidir_recomendacao("emp", rec["id"], "aprovada", "admin@demo")
        try:
            agente_api.decidir_recomendacao("emp", rec["id"], "recusada", "outro")
            raise AssertionError("decidiu duas vezes")
        except LookupError:
            pass
        assert cientista.orientacao(repo.recomendacao_aprovada("emp")).startswith("[sem evidência] Manter")
    finally:
        agente_api.fabrica_repo, agente_api.fabrica_fonte, agente_api.fabrica_cliente = antes


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
