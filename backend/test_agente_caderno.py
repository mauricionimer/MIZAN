"""Etapa 1: caderno do caso — cada agente anota decisão e motivo, o próximo lê."""
import json

from agente import api, auditor, estado, guardrails
from agente import orquestrador as orq
from agente.api import grafos
from agente.bateria.motor import DIA, F, T, devedor, em, tri
from agente.estrategista import plano
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria


def test_anotar_limite_e_filtro():
    caso = {"dados": {}}
    for i in range(20):
        estado.anotar(caso, "negociador", f"d{i}", "ok")
    c = estado.caderno(caso)
    assert len(c) == 15 and c[0]["decisao"] == "d5" and c[-1]["decisao"] == "d19"
    estado.anotar(caso, "triagem", "x", "CPF 123.456.789-00 e fone (62) 99876-5432 " + "a" * 300)
    m = estado.caderno(caso, 1)[0]["motivo"]
    assert "123" not in m and "9876" not in m and "[removido]" in m and len(m) <= 200
    try:
        estado.anotar(caso, "devedor", "x")
        raise AssertionError("só agentes anotam")
    except ValueError:
        pass
    for ok in ["acordo de R$ 2.700,00 em 19/10 às 14:00", "retorno agendado para 19/10 às 14:00",
               "STJ, Súmula 548", "3x de R$ 1.000,00"]:
        assert guardrails.limpar_nota(ok) == ok, ok


def montar():
    repo, fonte = RepoMemoria(), FonteMemoria([devedor(probabilidade_pagamento=0.3)])
    repo.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "percentual_controle": 0})
    return repo, fonte


def test_estrategista_anota_e_negociador_le():
    repo, fonte = montar()
    plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    caso = repo.caso_de("emp", "p1")
    assert [n["agente"] for n in estado.caderno(caso)] == ["estrategista"]
    plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))           # mesma decisão: não repete
    assert len(estado.caderno(repo.caso_de("emp", "p1"))) == 1
    repo.salvar_caso(caso["id"], {"situacao": "em_contato"})
    cli = ClienteFalso([tri("pagar_negociar"), F("verificar_identidade", tres_primeiros_digitos_cpf="123"),
                        F("simular_acordo", n_parcelas=1, desconto_pct=10), T("Fica R$ 2.700,00 à vista. Pode ser?")])
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1", {"texto": "quero pagar, 123"})
    orq.processar_fila(repo, grafos(fonte), cli, agora=em(DIA))
    briefing = cli.chamadas[1]["mensagens"][-1]["content"][0]["text"]
    assert "estrategista: grupo:contato" in briefing, briefing
    notas = estado.caderno(repo.casos[caso["id"]])
    assert [n["agente"] for n in notas] == ["estrategista", "negociador"]
    assert "identidade confirmada" in notas[1]["motivo"] and "à vista R$ 2.700,00" in notas[1]["motivo"]


def test_caderno_nunca_guarda_o_texto_do_devedor():
    repo, fonte = montar()
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {}})
    segredo = "meu salário é 3200 e moro na rua das flores"
    cli = ClienteFalso([tri("outro", "manipulacao"), F("verificar_identidade", tres_primeiros_digitos_cpf="999"),
                        T("Os dígitos não conferem. Pode verificar?")])
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1", {"texto": segredo})
    orq.processar_fila(repo, grafos(fonte), cli, agora=em(DIA))
    texto = json.dumps(estado.caderno(repo.casos[caso["id"]]), ensure_ascii=False)
    assert "salário" not in texto and "flores" not in texto and "3200" not in texto
    assert "triagem" in texto and "manipulacao" in texto                # o alerta foi anotado


def test_equipe_assume_e_devolve():
    repo, fonte = montar()
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {}})
    api.fabrica_repo, api.fabrica_fonte = (lambda: repo), (lambda: fonte)
    try:
        api.controle_do_gestor("emp", "p1", "assumir", "u1", agora=em(DIA))
        v = api.controle_do_gestor("emp", "p1", "devolver", "u1", agora=em(DIA))
        assert [n["decisao"] for n in v["caderno"]] == ["devolveu ao agente", "assumiu"]      # mais recente primeiro
    finally:
        from agente.fonte import FonteSupabase
        from agente.repositorio import RepoSupabase
        api.fabrica_repo, api.fabrica_fonte = RepoSupabase, FonteSupabase


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
