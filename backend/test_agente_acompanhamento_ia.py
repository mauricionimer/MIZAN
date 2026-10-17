"""Etapa 3: Acompanhamento com IA — cardápio fechado, travas e texto pronto como reserva."""
import json
import os
from datetime import date

from agente.bateria.cenarios import SEG, TER
from agente.bateria.motor import ID_OK, Cenario, em, executar
from agente.llm import ClienteFalso

VENC = TER.isoformat()
ACORDO = {**ID_OK, "acordo": {"condicoes": {"n_parcelas": 6, "desconto_pct": 10, "entrada_pct": 10},
                              "primeiro_pagamento": 270.0, "data": VENC},
          "caderno": [{"agente": "triagem", "decisao": "pagar_negociar", "motivo": "ansioso", "quando": None, "trace_id": None}]}
PROM = [("promessa", VENC, 270.0)]
ATRASO = em(date(2026, 10, 23))


def ia(**d):
    return json.dumps({"motivo": "teste", "mensagem": "", **d})


def rodar(passos, acomp, **kw):
    os.environ["MIZAN_IA_PAPEIS"] = "triagem,negociador,acompanhamento"
    try:
        c = Cenario("t", "t", "t", passos=passos, conferir=[], situacao="acordo_ativo", dados=dict(ACORDO),
                    agenda=list(PROM), **kw)
        return executar(c, ClienteFalso({"acompanhamento": list(acomp)}))
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)


def test_lembrete_escrito_pela_ia():
    r = rodar([("relogio", None, em(SEG))],
              [ia(acao="lembrar", mensagem="Oi, Maria! Amanhã (20/10) vence a parcela de R$ 270,00. Qualquer coisa, me chama.")])
    assert r.saidas == ["Oi, Maria! Amanhã (20/10) vence a parcela de R$ 270,00. Qualquer coisa, me chama."]
    briefing = r.cliente.chamadas[0]["mensagens"][0]["content"]
    assert '"pode_fazer": ["lembrar", "esperar"]' in briefing and "ansioso" in briefing      # leu o caderno
    assert any(p["detalhe"].get("origem") == "ia" for p in r.repo.passos)


def test_valor_errado_reprova_e_reserva_e_o_texto_pronto():
    r = rodar([("relogio", None, em(SEG))],
              [ia(acao="lembrar", mensagem="Amanhã vence R$ 250,00."), ia(acao="lembrar", mensagem="Vence R$ 999,00.")])
    assert len(r.saidas) == 1 and "R$ 270,00" in r.saidas[0] and "Lembrete:" in r.saidas[0]   # texto pronto
    assert any(p["detalhe"].get("sem_ia") == "ValueError" for p in r.repo.passos)


def test_acao_inventada_vira_texto_pronto():
    r = rodar([("relogio", None, ATRASO)], [ia(acao="dar_desconto_de_50", mensagem="ok")])
    assert r.repo.casos[r.caso["id"]]["situacao"] == "atrasado" and "Aconteceu alguma coisa?" in r.saidas[0]


def test_atraso_oferece_remarcar():
    r = rodar([("relogio", None, ATRASO)],
              [ia(acao="oferecer_remarcar", mensagem="Oi, Maria. Vi que a parcela de 20/10 ficou pendente. Quer combinar outra data?")])
    caso = r.repo.casos[r.caso["id"]]
    assert caso["situacao"] == "atrasado" and "outra data" in r.saidas[0]
    assert "nova data" in caso["dados"]["objetivo"]
    assert caso["dados"]["caderno"][-1]["decisao"] == "oferecer_remarcar"


def test_atraso_chama_pessoa():
    r = rodar([("relogio", None, ATRASO)], [ia(acao="chamar_pessoa", motivo="já quebrou acordo e está irritada")])
    assert r.repo.casos[r.caso["id"]]["situacao"] == "com_pessoa"
    assert any("já quebrou acordo" in (a.get("observacao") or "") for a in r.fonte.agenda)


def test_sem_resposta_espera_mais_uma_vez_so():
    r = rodar([("relogio", None, ATRASO), ("relogio", None, em(date(2026, 10, 28))),
               ("relogio", None, em(date(2026, 10, 30)))],
              [ia(acao="procurar", mensagem="Oi, Maria. A parcela de 20/10 ficou pendente. Aconteceu algo?"),
               ia(acao="esperar_mais", motivo="disse que recebe salário dia 29"),
               ia(acao="esperar_mais", motivo="de novo")])                    # segunda espera: não vale
    caso = r.repo.casos[r.caso["id"]]
    assert caso["situacao"] == "com_pessoa", caso["situacao"]
    assert [n["decisao"] for n in caso["dados"]["caderno"] if n["agente"] == "acompanhamento"][:2] == ["procurar", "esperou_mais"]


def test_desligado_e_igual_a_hoje():
    os.environ.pop("MIZAN_IA_PAPEIS", None)
    c = Cenario("t", "t", "t", passos=[("relogio", None, em(SEG))], conferir=[], situacao="acordo_ativo",
                dados=dict(ACORDO), agenda=list(PROM))
    r = executar(c, ClienteFalso({"acompanhamento": [ia(acao="lembrar", mensagem="não deveria")]}))
    assert "Lembrete:" in r.saidas[0] and not r.cliente.chamadas


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
