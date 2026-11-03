"""Fluxo de retorno e vínculo entre proposta, aceite e pagamento confirmado.

Execute com `python3 test_agente_negociacao_integrada.py` dentro de backend.
"""
from datetime import datetime, timezone

from agente import acompanhamento, api, auditor, ferramentas, negociacao, orquestrador as orq
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.rastreio import Rastreio
from agente.repositorio import RepoMemoria

AGORA = datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc)
DEV = {"id": "p1", "empresa_id": "emp", "cpf": "12345678900", "nome": "Maria Silva",
       "valor_divida": 3000.0, "dias_em_atraso": 90, "produto": "cartao"}


def ambiente():
    repo, fonte = RepoMemoria(), FonteMemoria([DEV])
    repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    caso = repo.obter_ou_criar_caso("emp", DEV["id"])
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {"identidade_ok": True, "divida": 3000.0}})
    return repo, fonte, repo.obter_caso(caso["id"])


def testar_retorno():
    repo, fonte, caso = ambiente()
    compromisso = fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", hora="14:00",
                                    observacao=f"{ferramentas.PREFIXO_RETORNO}: a pedido")
    assert len(acompanhamento.planejar(repo, fonte, "emp", AGORA)) == 1
    assert not acompanhamento.planejar(repo, fonte, "emp", AGORA)
    orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=AGORA, empresa_id="emp")
    saidas = [m for m in repo.mensagens if m["direcao"] == "saida"]
    assert len(saidas) == 1 and "retornasse" in saidas[0]["texto"]
    assert fonte.compromisso("emp", "p1", compromisso["id"])["situacao"] == "cumprida"
    assert negociacao.metricas([repo.obter_caso(caso["id"])], {})["retornos_cumpridos"] == 1

    # A agenda de atendimento humano e as tarefas internas não disparam mensagens.
    fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", hora="14:00",
                       observacao=f"{ferramentas.PREFIXO_ATENDIMENTO}: pedido")
    fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", observacao="Conferir documento")
    assert not acompanhamento.planejar(repo, fonte, "emp", AGORA)


def testar_remarcacao():
    repo, fonte, caso = ambiente()
    compromisso = fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", hora="14:00",
                                    observacao=f"{ferramentas.PREFIXO_RETORNO}: a pedido")
    acompanhamento.planejar(repo, fonte, "emp", AGORA)
    fonte.atualizar_agenda("emp", "p1", compromisso["id"], {"data": "2026-11-04"})
    orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=AGORA, empresa_id="emp")
    assert not repo.mensagens
    assert fonte.compromisso("emp", "p1", compromisso["id"])["situacao"] == "pendente"
    # Mesmo com checkpoint do evento antigo, uma remarcação não pode gerar envio.
    amanha = datetime(2026, 11, 4, 17, 0, tzinfo=timezone.utc)
    assert len(acompanhamento.planejar(repo, fonte, "emp", amanha)) == 1
    orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=amanha, empresa_id="emp")
    assert len([m for m in repo.mensagens if m["direcao"] == "saida"]) == 1
    assert fonte.compromisso("emp", "p1", compromisso["id"])["situacao"] == "cumprida"

    repo, fonte, caso = ambiente()
    compromisso = fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", hora="14:00",
                                    observacao=f"{ferramentas.PREFIXO_RETORNO}: a pedido")
    acompanhamento.planejar(repo, fonte, "emp", AGORA)
    fonte.atualizar_agenda("emp", "p1", compromisso["id"], {"situacao": "cancelada"})
    orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=AGORA, empresa_id="emp")
    assert not repo.mensagens


def testar_frequencia():
    repo, fonte, caso = ambiente()
    repo.nova_versao_politica("emp", {**auditor.POLITICA_DEMONSTRACAO, "contatos_semana_max": 1})
    fonte.criar_agenda("emp", DEV, "retorno", "2026-11-03", hora="14:00",
                       observacao=f"{ferramentas.PREFIXO_RETORNO}: a pedido")
    repo.gravar_mensagem("emp", caso["id"], "saida", "Abordagem anterior", "anterior", criado_em=AGORA)
    acompanhamento.planejar(repo, fonte, "emp", AGORA)
    r = orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=AGORA, empresa_id="emp")
    assert r[0]["situacao_evento"] == "adiado", r
    assert len(repo.mensagens) == 1
    depois = datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)
    orq.processar_fila(repo, api.grafos(fonte), ClienteFalso([]), agora=depois, empresa_id="emp")
    assert len(repo.mensagens) == 2


def testar_trilha():
    repo, fonte, caso = ambiente()
    cliente = ClienteFalso([])
    ctx = orq.Contexto(caso=caso, evento={"id": "mensagem1", "tipo": "mensagem_devedor", "dados": {}},
                       repo=repo, rastreio=Rastreio("emp", repo.gravar_passo, caso_id=caso["id"]),
                       cliente=cliente, hoje=AGORA.date(), agora=AGORA)
    ctx.saida["_devedor"] = DEV
    r = ferramentas.executar(ctx, fonte, "simular_acordo", {"n_parcelas": 1, "desconto_pct": 10})
    assert r["dentro_da_politica"] and r["simulacao_id"]
    assert negociacao.metricas([ctx.caso], {})["ofertas_apresentadas"] == 0
    texto = f"À vista, valor total de R$ {r['total_pago']:,.2f}."
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    repo.gravar_mensagem("emp", caso["id"], "saida", texto, "trace1", criado_em=AGORA)
    assert negociacao.apresentada(ctx, texto) == [r["simulacao_id"]]
    ctx.saida["texto"] = "Aceito essa proposta."
    repo.gravar_mensagem("emp", caso["id"], "entrada", ctx.saida["texto"], "trace2", criado_em=AGORA)
    aceito = ferramentas.executar(ctx, fonte, "registrar_aceite",
                                  {"simulacao_id": r["simulacao_id"], "data_primeiro_pagamento": "2026-11-04"})
    assert aceito["ok"], aceito
    assert ctx.caso["dados"]["acordo"]["decisao_id"]
    assert ctx.caso["dados"]["acordo"]["compromisso_id"] == aceito["compromisso_id"]
    negociacao.pagamento(ctx, [{"id": aceito["compromisso_id"]}], r["total_pago"])
    fonte.pagos = {"p1": r["total_pago"]}
    m = negociacao.metricas([ctx.caso], fonte.pagamentos("emp", ["p1"]))
    assert (m["ofertas_apresentadas"], m["acordos_aceitos"], m["primeiro_pagamento_confirmado"]) == (1, 1, 1), m
    repo.salvar_caso(caso["id"], {"situacao": ctx.caso["situacao"], "dados": ctx.caso["dados"]})
    visto = api.ver_caso("emp", "p1", repo)
    assert visto["caso"]["negociacao"]["etapa"] == "aceite"
    assert any(e["tipo"] == "oferta_apresentada" for e in visto["caso"]["negociacao"]["eventos"])
    repo_original, fonte_original = api.fabrica_repo, api.fabrica_fonte
    api.fabrica_repo, api.fabrica_fonte = lambda: repo, lambda: fonte
    try:
        assert api.laboratorio("emp")["funil_negociacao"]["primeiro_pagamento_confirmado"] == 1
    finally:
        api.fabrica_repo, api.fabrica_fonte = repo_original, fonte_original


if __name__ == "__main__":
    original = orq.Contexto.consultar_juridico
    orq.Contexto.consultar_juridico = lambda self, *args, **kwargs: {"decisao": "liberado"}
    try:
        testar_retorno()
        testar_remarcacao()
        testar_frequencia()
        testar_trilha()
    finally:
        orq.Contexto.consultar_juridico = original
    print("ok: retorno, remarcação, apresentação, aceite e pagamento")
