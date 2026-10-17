"""Agenda dos agentes, atendimento com pessoa e a trava "não diz que fez sem ter feito".

Caso real (16/10/2026, Gemini): o devedor pediu para ser chamado segunda às 14h e
o agente respondeu "Já agendei" sem ter chamado ferramenta nenhuma.
Roda sem IA e sem banco.
"""
from agente import api, auditor, guardrails
from agente import orquestrador as orq
from agente.api import grafos
from agente.bateria.motor import DIA, F, T, devedor, em, tri
from agente.fonte import OPERADOR_A_DEFINIR, FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria

SEGUNDA = "2026-10-19"          # DIA é sexta, 16/10
PERM = guardrails.permitidos_de([])


def montar(dev=None, politica=True):
    repo, fonte = RepoMemoria(), FonteMemoria([dev or devedor()])
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {}})
    if politica:
        repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    return repo, fonte, caso


def falar(repo, fonte, caso, texto, roteiro, chave="m1"):
    cli = ClienteFalso(roteiro)
    antes = len(repo.mensagens)
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", chave, {"texto": texto})
    orq.processar_fila(repo, grafos(fonte), cli, agora=em(DIA))
    return [m["texto"] for m in repo.mensagens[antes:] if m["direcao"] == "saida"], cli


# ── 1. trava: ação dita só com a ferramenta feita ──────────────────────────

def test_afirmar_sem_ferramenta_e_barrado():
    for texto in ["Combinado, Fábio! Já agendei nosso retorno para segunda-feira, às 14h.",
                  "Marquei aqui para segunda.", "Pronto, está agendado para segunda.",
                  "Registrei o pagamento informado e a equipe vai conferir.",
                  "Transferi seu caso para a equipe.", "Sua cobrança foi suspensa.",
                  "Acordo fechado! Obrigado."]:
        assert any("diz que fez" in m for m in guardrails.conferir(texto, PERM, feitas=set())), texto


def test_afirmar_com_ferramenta_passa():
    assert not guardrails.conferir("Já agendei para segunda.", PERM, feitas={"agendar_retorno"})
    assert not guardrails.conferir("Registrei o aviso de pagamento; a equipe vai conferir.", PERM,
                                   feitas={"registrar_pagamento_informado"})
    assert not guardrails.conferir("Pronto, transferi para a equipe.", PERM, feitas={"marcar_atendimento_humano"})


def test_oferecer_nao_e_afirmar():
    for texto in ["Posso agendar um retorno para segunda às 14h?", "Quer que eu marque com uma pessoa da equipe?",
                  "Vou registrar seu pedido, tudo bem?", "Prefere que uma pessoa da equipe fale com você?",
                  "Me diga o dia e o horário que eu vejo se dá para marcar."]:
        assert not guardrails.conferir(texto, PERM, feitas=set()), texto


def test_ia_nunca_confirma_pagamento():
    for texto in ["Seu pagamento foi confirmado!", "Recebemos seu pagamento, obrigado.", "Sua dívida está quitada."]:
        assert any("só o banco confirma" in m for m in guardrails.conferir(texto, PERM, feitas=set(PERM))), texto


def test_caso_fabio_de_ponta_a_ponta():
    repo, fonte, caso = montar()
    saidas, _ = falar(repo, fonte, caso, "queria agendar pra você me chamar na segunda 14 horas tem como?", [
        tri("outro"),
        T("Combinado, Fábio! Já agendei nosso retorno para segunda-feira, dia 20/10, às 14h."),   # mentira
        F("agendar_retorno", data=SEGUNDA, hora="14:00", motivo="devedor pediu retorno"),
        T("Combinado! Agendei nosso retorno para segunda, 19/10, às 14h.")])
    assert len(saidas) == 1 and "19/10" in saidas[0], saidas
    assert any(p["no"] == "guardrails" and p["detalhe"].get("reprovado") for p in repo.passos)
    item = fonte.agenda[0]
    assert (item["data"], item["hora"], item["tipo"]) == (SEGUNDA, "14:00", "retorno")


# ── 3 e 5. hora na agenda e atendimento com pessoa ─────────────────────────

def test_hora_fora_da_janela_e_bloqueada():
    repo, fonte, caso = montar()
    falar(repo, fonte, caso, "pode ser segunda às 22h?", [
        tri("outro"), F("agendar_retorno", data=SEGUNDA, hora="22:00", motivo="x"), T("Esse horário não dá.")])
    assert not fonte.agenda
    assert any(p["no"] == "auditor" and p["regra"] == "R2_HORARIO" for p in repo.passos)
    falar(repo, fonte, caso, "domingo?", [
        tri("outro"), F("agendar_retorno", data="2026-10-18", hora="10:00", motivo="x"), T("Domingo não dá.")], "m2")
    assert not fonte.agenda


def test_atendimento_sem_responsavel_vai_para_o_administrador():
    repo, fonte, caso = montar(devedor(responsavel_id=None))
    saidas, _ = falar(repo, fonte, caso, "quero marcar uma reunião segunda às 14h", [
        tri("outro"),
        F("marcar_atendimento_humano", data=SEGUNDA, hora="14:00", motivo="reuniao",
          resumo="Quer conversar sobre a dívida do cartão.")])
    item = fonte.agenda[0]
    assert item["operador_id"] == OPERADOR_A_DEFINIR and item["hora"] == "14:00"
    assert repo.casos[caso["id"]]["situacao"] == "com_pessoa"
    assert saidas == ["Olá, Maria! Aqui é o assistente virtual de Banco Demonstração. Combinado: uma pessoa da "
                      "nossa equipe vai falar com você em 19/10, às 14:00. Até lá, se precisar, é só escrever por aqui."]


def test_atendimento_com_responsavel_vai_para_ele():
    repo, fonte, caso = montar(devedor(responsavel_id="op1", responsavel_nome="Ana"))
    saidas, _ = falar(repo, fonte, caso, "pode ser segunda às 15h com alguém?", [
        tri("outro"), F("marcar_atendimento_humano", data=SEGUNDA, hora="15:00", motivo="pedido_do_devedor",
                        resumo="Quer falar com uma pessoa.")])
    assert (fonte.agenda[0]["operador_id"], fonte.agenda[0]["operador_nome"]) == ("op1", "Ana")
    assert "Ana vai falar com você em 19/10, às 15:00" in saidas[0]


def test_agenda_dos_agentes_e_atribuicao():
    repo, fonte, caso = montar(devedor(responsavel_id=None))
    falar(repo, fonte, caso, "segunda 14h", [tri("outro"), F("marcar_atendimento_humano", data=SEGUNDA, hora="14:00",
                                                                 motivo="reuniao", resumo="Reunião.")])
    fonte._operadores = [{"id": "u-ana", "nome": "Ana"}]
    api.fabrica_repo, api.fabrica_fonte = (lambda: repo), (lambda: fonte)
    try:
        ag = api.agenda("emp")
        assert len(ag["itens"]) == 1 and ag["itens"][0]["a_definir"] and ag["itens"][0]["tipo"] == "atendimento"
        assert ag["operadores"] == [{"id": "u-ana", "nome": "Ana"}]
        for errado in ("u-outro", ""):
            try:
                api.atribuir("emp", ag["itens"][0]["id"], errado)
                raise AssertionError("operador de fora não pode")
            except LookupError:
                pass
        assert api.atribuir("emp", ag["itens"][0]["id"], "u-ana")["operador"]["nome"] == "Ana"
        assert fonte.agenda[0]["operador_id"] == "u-ana"
        try:
            api.atribuir("emp", ag["itens"][0]["id"], "u-ana")       # segundo clique
            raise AssertionError("já atribuído")
        except LookupError:
            pass
        assert api.agenda("emp", )["itens"][0]["a_definir"] is False
    finally:
        from agente.fonte import FonteSupabase
        from agente.repositorio import RepoSupabase
        api.fabrica_repo, api.fabrica_fonte = RepoSupabase, FonteSupabase


# ── 4. a tela explica cada passo e o silêncio ──────────────────────────────

def test_silencio_explicado_e_passos_com_quem():
    repo, fonte, caso = montar(politica=False)
    saidas, _ = falar(repo, fonte, caso, "oi, tudo bem?", [tri("outro"), T("Olá! Como posso ajudar?")])
    assert saidas == []
    v = api.ver_caso("emp", "p1", repo)
    assert v["silencio"] and "R0_SEM_POLITICA" in v["silencio"], v["silencio"]
    quem = {p["quem"] for p in v["passos"]}
    assert {"Triagem", "Negociador", "Auditor"} <= quem, quem
    assert all(p["explicacao"] for p in v["passos"])
    assert "oi, tudo bem" not in str(v["passos"])                # o texto do devedor não vai para o rastreio


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
