"""Escritório dos agentes: a rota mostra só passos da empresa, sem texto do devedor."""
import json
from datetime import timedelta

from agente import api as agente_api
from agente.bateria.motor import ID_OK, Cenario, T, executar, tri
from agente.llm import ClienteFalso

FALA = "meu cpf é 123.456.789-00 e quero negociar"


def montar():
    c = Cenario("t", "t", "t", dados=dict(ID_OK), conferir=[], passos=[("mensagem", FALA)])
    r = executar(c, ClienteFalso({"triagem": [tri("pagar_negociar", emocao="ansioso")],
                                  "negociador": [T("Posso simular para você.")]}))
    return r


def com(repo, fn):
    antes = agente_api.fabrica_repo
    agente_api.fabrica_repo = lambda: repo
    try:
        return fn()
    finally:
        agente_api.fabrica_repo = antes


def test_passos_recentes_e_ultima_conversa_sem_texto():
    r = montar()
    agora = max(p["criado_em"] for p in r.repo.passos) + timedelta(seconds=1)
    e = com(r.repo, lambda: agente_api.estacao("emp", agora=agora))
    assert e["passos"] and e["ultima_conversa"], e
    quem = {p["quem"] for p in e["passos"]}
    assert {"Triagem", "Negociador", "Travas", "Auditor"} <= quem, quem
    txt = json.dumps(e, ensure_ascii=False, default=str)
    assert "123.456" not in txt and "quero negociar" not in txt
    assert e["ia"]["triagem"] is True and e["ia"]["cientista"] is False
    assert any("ansioso" in p["explicacao"] for p in e["passos"])


def test_janela_e_outra_empresa():
    r = montar()
    tarde = max(p["criado_em"] for p in r.repo.passos) + timedelta(minutes=agente_api.JANELA_ESTACAO_MIN + 1)
    e = com(r.repo, lambda: agente_api.estacao("emp", agora=tarde))
    assert e["passos"] == [] and e["ultima_conversa"]            # fora da janela, mas a última conversa fica
    outra = com(r.repo, lambda: agente_api.estacao("outra", agora=tarde))
    assert outra["passos"] == [] and outra["ultima_conversa"] == []


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
