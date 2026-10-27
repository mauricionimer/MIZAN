"""Telemetria observacional: execução real, isolamento, reconexão e privacidade."""
import json
from datetime import datetime, timedelta, timezone
from agente import api, orquestrador as orq
from agente.escritorio import observador, para_tela
from agente.llm import ClienteFalso
from agente.rastreio import Rastreio
from agente.repositorio import RepoMemoria


def test_sinais_de_inicio_fim_modelo_e_retorno_de_span_aninhado():
    repo = RepoMemoria()
    caso = repo.obter_ou_criar_caso("empresa", "predicao")
    ev, _ = orq.registrar_evento(repo, "empresa", caso["id"], "mensagem_devedor", "chave", {"texto": "CPF SEGREDO"})
    vistos = []
    def ler():
        return para_tela(repo.eventos_escritorio("empresa"), api._quem, datetime.now(timezone.utc))
    def receber(ctx):
        vistos.append(ler())
        ctx.mudar_situacao("em_contato")
    def negociar(ctx):
        vistos.append(ler())
        ctx.rastreio.observar("pensando")
        assert ler()["executando"][0]["estado"] == "pensando"
        ctx.rastreio.observar("trabalhando")
        with ctx.rastreio.span("auditor", "auditor"):
            assert ler()["executando"][0]["quem"] == "Auditor"
        assert ler()["executando"][0]["quem"] == "Negociador"
        ctx.mudar_situacao("negociando")
    grafo = (orq.Grafo("teste", "receber").no("receber", receber, seguinte="negociar")
             .no("negociar", negociar, agente="negociador"))
    r = orq.processar_proximo(repo, {"mensagem_devedor": grafo}, ClienteFalso())
    assert r["ok"] and repo.obter_caso(caso["id"])["situacao"] == "negociando", r
    assert [v["executando"][0]["quem"] for v in vistos] == ["Orquestrador", "Negociador"]
    tela = ler()
    assert tela["executando"] == []
    entregas = [s for s in tela["sinais"] if s["tipo"] == "handoff"]
    assert any(s["de"] == "Orquestrador" and s["para"] == "Negociador" for s in entregas)
    assert any(s["de"] == "Auditor" and s["para"] == "Negociador" for s in entregas)
    assert all(s["caso_id"] == caso["id"] and s["trace_id"] == r["trace_id"] for s in entregas)
    assert "SEGREDO" not in json.dumps(tela, default=str)
    assert para_tela(repo.eventos_escritorio("outra"), api._quem, datetime.now(timezone.utc))["sinais"] == []
    assert repo.eventos[ev["id"]]["dados"]["texto"] == "CPF SEGREDO"


def test_observacao_que_falha_nao_muda_o_grafo_nem_perde_os_passos():
    repo = RepoMemoria()
    caso = repo.obter_ou_criar_caso("empresa", "predicao")
    def quebrar(*_):
        raise RuntimeError("Sala indisponível")
    r = Rastreio("empresa", repo.gravar_passo, caso_id=caso["id"], observar=quebrar)
    with r.span("negociar", "negociador"):
        r.observar("pensando")
        with r.span("auditor", "auditor"):
            pass
        assert r.atual["no"] == "negociar"
    assert r.atual is None and len(repo.passos) == 2
    # Falha exclusivamente na persistência observacional também é isolada.
    ev, _ = orq.registrar_evento(repo, "empresa", caso["id"], "relogio", "chave")
    original = repo.atualizar_evento
    def atualizar(id, campos):
        if "dados" in campos:
            raise RuntimeError("Telemetria indisponível")
        return original(id, campos)
    repo.atualizar_evento = atualizar
    grafo = orq.Grafo("teste", "receber").no("receber", lambda ctx: ctx.mudar_situacao("em_contato"))
    assert orq.processar_proximo(repo, {"relogio": grafo}, ClienteFalso())["ok"]
    assert repo.eventos[ev["id"]]["situacao"] == "feito"


def test_sinal_antigo_ou_evento_finalizado_nao_fica_trabalhando():
    agora = datetime.now(timezone.utc)
    evento = {"id": "evento", "caso_id": "caso", "situacao": "processando", "escritorio": {
        "atualizado_em": (agora-timedelta(minutes=6)).isoformat(),
        "atual": {"no": "negociar", "agente": "negociador", "estado": "pensando"}, "sinais": []}}
    assert para_tela([evento], api._quem, agora)["executando"] == []
    evento["escritorio"]["atualizado_em"] = agora.isoformat()
    assert len(para_tela([evento], api._quem, agora)["executando"]) == 1
    evento["situacao"] = "feito"
    assert para_tela([evento], api._quem, agora)["executando"] == []


def test_sinais_limitados_e_tokens_da_janela():
    repo = RepoMemoria()
    caso = repo.obter_ou_criar_caso("empresa", "predicao")
    ev, _ = orq.registrar_evento(repo, "empresa", caso["id"], "relogio", "chave")
    r = Rastreio("empresa", repo.gravar_passo, observar=observador(repo, ev, "trace"))
    for _ in range(100):
        with r.span("triagem", "triagem") as p:
            p.update(tokens_entrada=10, tokens_saida=5)
    assert len(repo.eventos[ev["id"]]["dados"]["_escritorio"]["sinais"]) == 80
    assert api._resumo_agente("Triagem", repo.passos)["tokens"] == 1500


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok", nome)
