"""Etapa 0 dos agentes com IA: fila por agente na IA simulada, botão por agente
(MIZAN_IA_PAPEIS) e o caminho em código quando a IA não está disponível."""
import os

from agente import llm
from agente.orquestrador import Contexto
from agente.rastreio import Rastreio
from agente.repositorio import RepoMemoria


def test_lista_antiga_continua_igual():
    c = llm.ClienteFalso(["a", "b"])
    assert c.gerar(sistema="", mensagens=[], papel="triagem").texto == "a"
    assert c.gerar(sistema="", mensagens=[], papel="negociador").texto == "b"
    assert c.gerar(sistema="", mensagens=[], papel="negociador").texto == ""      # acabou: vazio, como antes


def test_agente_novo_nao_consome_a_fila_antiga():
    c = llm.ClienteFalso(["triagem"])
    try:
        c.gerar(sistema="", mensagens=[], papel="supervisor")
        raise AssertionError("deveria levantar SemRoteiro")
    except llm.SemRoteiro:
        pass
    assert c.gerar(sistema="", mensagens=[], papel="triagem").texto == "triagem"


def test_fila_por_agente():
    c = llm.ClienteFalso({"triagem": ["t1"], "acompanhamento": ["a1", "a2"]})
    assert c.gerar(sistema="", mensagens=[], papel="acompanhamento").texto == "a1"
    assert c.gerar(sistema="", mensagens=[], papel="triagem").texto == "t1"
    assert c.gerar(sistema="", mensagens=[], papel="acompanhamento").texto == "a2"
    assert c.chamadas[0]["papel"] == "acompanhamento"


def test_botao_por_agente():
    antes = os.environ.pop("MIZAN_IA_PAPEIS", None)
    try:
        assert llm.ia_ligada("triagem") and llm.ia_ligada("negociador")
        assert not llm.ia_ligada("acompanhamento") and not llm.ia_ligada("supervisor")
        os.environ["MIZAN_IA_PAPEIS"] = "triagem, negociador ,Acompanhamento"
        assert llm.ia_ligada("acompanhamento") and not llm.ia_ligada("estrategista")
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)
        if antes is not None:
            os.environ["MIZAN_IA_PAPEIS"] = antes


def test_modelo_dos_agentes_novos_usa_o_da_triagem():
    salvo = {k: os.environ.pop(k, None) for k in ("MIZAN_MODELO_TRIAGEM", "MIZAN_MODELO_SUPERVISOR")}
    try:
        assert llm.modelo_para("supervisor") == llm.MODELO_FALSO
        os.environ["MIZAN_MODELO_TRIAGEM"] = "m-barato"
        assert llm.modelo_para("supervisor") == "m-barato"
        os.environ["MIZAN_MODELO_SUPERVISOR"] = "m-proprio"
        assert llm.modelo_para("supervisor") == "m-proprio"
    finally:
        for k, v in salvo.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def _ctx(cliente):
    from datetime import date, datetime, timezone
    repo = RepoMemoria()
    caso = repo.obter_ou_criar_caso("emp", "p1")
    return Contexto(caso=caso, evento={"id": "e1", "dados": {}}, repo=repo,
                    rastreio=Rastreio("emp", repo.gravar_passo, caso["id"], "e1", "t1"), cliente=cliente,
                    hoje=date(2026, 10, 16), agora=datetime(2026, 10, 16, 17, tzinfo=timezone.utc))


def test_ia_ou_codigo():
    os.environ["MIZAN_IA_PAPEIS"] = "triagem,negociador,acompanhamento"
    try:
        ctx = _ctx(llm.ClienteFalso({"acompanhamento": ["da IA"]}))
        gerar = lambda: ctx.ia("acompanhamento", "s", []).texto                      # noqa: E731
        with ctx.rastreio.span("decidir", "acompanhamento") as p:
            assert ctx.ia_ou_codigo("acompanhamento", gerar, lambda: "pronto") == "da IA"
            assert p["detalhe"]["origem"] == "ia"
        with ctx.rastreio.span("decidir", "acompanhamento") as p:                   # fila acabou
            assert ctx.ia_ou_codigo("acompanhamento", gerar, lambda: "pronto") == "pronto"
            assert p["detalhe"] == {"origem": "codigo", "sem_ia": "SemRoteiro"}
        def ruim():
            raise ValueError("JSON inválido")
        assert ctx.ia_ou_codigo("acompanhamento", ruim, lambda: "pronto") == "pronto"
        ctx2 = _ctx(llm.ClienteFalso({"supervisor": ["nunca"]}))
        with ctx2.rastreio.span("revisar", "supervisor") as p:                      # desligado: nem chama
            assert ctx2.ia_ou_codigo("supervisor", lambda: ctx2.ia("supervisor", "s", []).texto,
                                     lambda: "sem IA") == "sem IA"
            assert p["detalhe"]["sem_ia"] == "desligado" and not ctx2.cliente.chamadas
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
