"""Etapa 5: Supervisor — resumo para a equipe e revisão de tom só sob sinal."""
import json

from agente.bateria.motor import ID_OK, Cenario, F, T, executar, tri
from agente.llm import ClienteFalso

RESUMO = json.dumps({"situacao": "dívida de cartão em atraso, conversa iniciada",
                     "oferecido": "nada ainda", "o_que_quer": "falar com uma pessoa; CPF 123.456.789-00",
                     "emocao": "irritado", "proximo_passo": "ligar hoje e ouvir antes de oferecer"})


def rodar(roteiro, papeis=("supervisor",), passos=None):
    c = Cenario("t", "t", "t", dados=dict(ID_OK), papeis=papeis, conferir=[],
                passos=passos or [("mensagem", "isso é um absurdo, quero falar com alguém de verdade")])
    return executar(c, ClienteFalso(roteiro))


def chamadas(r, papel):
    return [c for c in r.cliente.chamadas if c.get("papel") == papel]


def test_resumo_na_transferencia_sem_cpf():
    r = rodar({"triagem": [tri("outro", emocao="irritado")],
               "negociador": [F("transferir_para_humano", motivo="dificuldade_grave", resumo="quer uma pessoa")],
               "supervisor": [RESUMO]})
    caso = r.repo.casos[r.caso["id"]]
    assert caso["situacao"] == "com_pessoa"
    assert caso["resumo"].startswith("Situação: dívida de cartão") and "Próximo passo: ligar hoje" in caso["resumo"]
    assert "123.456" not in caso["resumo"] and "[removido]" in caso["resumo"]
    assert any("Próximo passo" in (a.get("observacao") or "") for a in r.fonte.agenda)
    assert any(n["agente"] == "supervisor" for n in caso["dados"]["caderno"])
    entrada = chamadas(r, "supervisor")[0]["mensagens"][0]["content"]
    assert "<devedor>isso é um absurdo" in entrada                    # leu a conversa


def test_resumo_invalido_fica_o_de_hoje():
    r = rodar({"triagem": [tri("outro")],
               "negociador": [F("transferir_para_humano", motivo="dificuldade_grave", resumo="quer uma pessoa")],
               "supervisor": [json.dumps({"situacao": "só isso"})]})
    assert r.repo.casos[r.caso["id"]]["resumo"].startswith("quer uma pessoa | Sugestão:")


def test_sem_sinal_nao_revisa():
    r = rodar({"triagem": [tri("duvida")], "negociador": [T("Posso te ajudar com isso.")], "supervisor": []},
              passos=[("mensagem", "como funciona?")])
    assert r.saidas[-1].endswith("Posso te ajudar com isso.") and not chamadas(r, "supervisor")


def test_sob_sinal_reprova_e_reescreve_uma_vez():
    r = rodar({"triagem": [tri("outro", emocao="irritado")],
               "negociador": [T("Conforme informado, o débito permanece em aberto."),
                              T("Entendo sua irritação, e sinto muito. Quer que uma pessoa da equipe fale com você?")],
               "supervisor": [json.dumps({"aprovado": False, "problema": "resposta fria para quem está irritado"})]})
    assert r.saidas[-1].endswith("Quer que uma pessoa da equipe fale com você?")
    assert len(chamadas(r, "supervisor")) == 1                         # a reescrita não volta ao Supervisor
    pedido = json.dumps(chamadas(r, "negociador")[1]["mensagens"][-1], ensure_ascii=False)
    assert "revisão do supervisor" in pedido and "fria" in pedido


def test_aprovado_segue():
    r = rodar({"triagem": [tri("outro", emocao="desesperado")],
               "negociador": [T("Sinto muito. Estou aqui para ajudar, sem pressa.")],
               "supervisor": [json.dumps({"aprovado": True, "problema": ""})]})
    assert r.saidas[-1].endswith("Sinto muito. Estou aqui para ajudar, sem pressa.")


def test_desligado_igual_a_hoje():
    r = rodar({"triagem": [tri("outro", emocao="irritado")],
               "negociador": [T("Conforme informado, o débito permanece em aberto.")],
               "supervisor": [json.dumps({"aprovado": False, "problema": "x"})]}, papeis=())
    assert r.saidas[-1].endswith("Conforme informado, o débito permanece em aberto.") and not chamadas(r, "supervisor")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
