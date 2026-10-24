"""Bug de 18/10: o agente passava o caso para uma pessoa por qualquer coisa.

Causas: (1) o valor que a pessoa escreveu ("200 reais") era barrado nas travas
e duas reprovações transferiam direto; (2) cota estourada da IA também virava
transferência. Agora: reprovou duas vezes, pede para reformular (só na segunda
vez seguida transfere); valor dito pela pessoa pode ser repetido; simulação
fora da política não pode ser citada; cota estourada espera e tenta de novo.
"""
import os

from agente import llm
from agente import orquestrador as orq
from agente.api import grafos
from agente.bateria.motor import ID_OK, Cenario, F, T, executar, tri
from agente.llm import ClienteFalso, Resposta


def rodar(passos, roteiro, **kw):
    c = Cenario("t", "t", "t", dados=dict(ID_OK), passos=passos, conferir=[], **kw)
    return executar(c, ClienteFalso(roteiro))


def test_valor_que_nao_cabe_nao_transfere():
    r = rodar([("mensagem", "consigo pagar 200 reais por mês")],
              {"triagem": [tri("pagar_negociar")],
               "negociador": [T("Com esse valor por mês não consigo fechar agora. Podemos ver a menor parcela?")]})
    assert r.saidas[-1].endswith("Podemos ver a menor parcela?")
    assert r.repo.casos[r.caso["id"]]["situacao"] != "com_pessoa"


def test_duas_reprovacoes_pedem_para_reformular_e_nao_transferem():
    ruim = T("Fica R$ 77,00 por mês.")                     # valor que nenhuma ferramenta deu
    r = rodar([("mensagem", "qual é a parcela mínima?")],
              {"triagem": [tri("duvida")], "negociador": [ruim, ruim]})
    caso = r.repo.casos[r.caso["id"]]
    assert caso["situacao"] != "com_pessoa", caso["situacao"]
    assert "dizer de outro jeito" in r.saidas[-1]


def test_reprovacao_de_novo_em_seguida_transfere():
    ruim = T("Fica R$ 77,00 por mês.")
    r = rodar([("mensagem", "qual é a parcela mínima?"), ("mensagem", "a mínima mesmo")],
              {"triagem": [tri("duvida"), tri("duvida")], "negociador": [ruim, ruim, ruim, ruim]})
    assert r.repo.casos[r.caso["id"]]["situacao"] == "com_pessoa"


def test_resposta_boa_zera_a_contagem():
    ruim, boa = T("Fica R$ 77,00 por mês."), T("Posso simular para você. Quantas parcelas prefere?")
    r = rodar([("mensagem", "qual a parcela?"), ("mensagem", "ok"), ("mensagem", "e a mínima?")],
              {"triagem": [tri("duvida")] * 3, "negociador": [ruim, ruim, boa, ruim, ruim]})
    assert r.repo.casos[r.caso["id"]]["situacao"] != "com_pessoa"


def test_simulacao_fora_da_politica_nao_pode_ser_citada():
    r = rodar([("mensagem", "consigo pagar 200 reais")],
              {"triagem": [tri("pagar_negociar")],
               "negociador": [F("simular_acordo", n_parcelas=12, desconto_pct=80, cabe_por_mes=200),
                              lambda s, m: T(f"Fica em 12x de R$ 50,00 com 80% de desconto."),
                              T("Com 80% eu não consigo. Quer ver a menor parcela permitida?"),
                              T("Quer ver a menor parcela permitida?")]})
    assert "80%" not in r.saidas[-1]


def test_e_muito_caro_nao_e_sofrimento_grave():
    r = rodar([("mensagem", "não consigo, é muito")],
              {"triagem": [tri("pagar_negociar", "sofrimento_grave", emocao="ansioso")],
               "negociador": [T("Entendo. Posso ver uma opção com mais parcelas para você?")]})
    assert r.repo.casos[r.caso["id"]]["situacao"] != "com_pessoa"
    assert "CVV" not in " ".join(r.saidas) and r.saidas[-1].endswith("mais parcelas para você?")


def test_risco_a_vida_continua_indo_para_pessoa_com_cvv():
    r = rodar([("mensagem", "não aguento mais viver com essa dívida")],
              {"triagem": [tri("outro", emocao="calmo")], "negociador": []})
    assert r.repo.casos[r.caso["id"]]["situacao"] == "com_pessoa" and "CVV" in r.saidas[-1]


def test_chamada_de_ferramenta_escrita_como_texto_nao_sai():
    r = rodar([("mensagem", "sim, sou eu")],
              {"triagem": [tri("outro")],
               "negociador": [T('<json>{"args": {}, "tool": "consultar_caso"}</json>'),
                              T("Para sua segurança, me diga os três primeiros dígitos do seu CPF.")]})
    assert "<json>" not in " ".join(r.saidas) and r.saidas[-1].endswith("dígitos do seu CPF.")
    from agente import guardrails as g
    for vazado in ('<tools>["verificar_identidade"]</tools>Olá!', '<tool_call>x</tool_call>', '```json {}```'):
        assert any("código" in m for m in g.conferir(vazado, g.permitidos_de([]), set())), vazado
    assert not g.conferir("Posso simular com mais parcelas. Qual prefere?", g.permitidos_de([]), set())


class Ocupado(ClienteFalso):
    """Primeira chamada do negociador: cota estourada."""
    def __init__(self, roteiro):
        super().__init__(roteiro)
        self.vezes = 0

    def gerar(self, **kw):
        if kw.get("papel") == "negociador" and self.vezes == 0:
            self.vezes += 1
            raise llm.IaOcupada("Gemini HTTP 429", esperar_s=40)
        return super().gerar(**kw)


def test_cota_estourada_espera_e_nao_transfere():
    from datetime import timedelta
    from agente import api as agente_api
    c = Cenario("t", "t", "t", dados=dict(ID_OK), passos=[("mensagem", "quanto fica à vista?")], conferir=[])
    cli = Ocupado({"triagem": [tri("pagar_negociar")], "negociador": [T("Posso simular para você.")]})
    r = executar(c, cli)
    caso = r.repo.casos[r.caso["id"]]
    assert caso["situacao"] != "com_pessoa", caso["situacao"]
    assert any(p["no"] == "aguardar_ia" for p in r.repo.passos)
    # REG-IA-OCUPADA-001: uma tentativa transitória continua em recuperação;
    # ela não pode aparecer como erro nem vazar o nome interno da exceção.
    tentativa = next(p for p in r.repo.passos if p["no"] == "negociar")
    assert tentativa["resultado"] == "aguardando"
    assert tentativa["detalhe"]["codigo"] == "ia_ocupada"
    publico = agente_api._passo_publico(tentativa)
    assert publico["resultado"] == "aguardando"
    assert "IaOcupada" not in str(publico)
    pend = [e for e in r.repo.eventos.values() if e["situacao"] == "pendente"]
    assert pend, "evento devia voltar para a fila"
    # REG-IA-OCUPADA-002: a conversa aberta retoma o evento pronto sem
    # depender do próximo ciclo do agendador.
    depois = pend[0]["disponivel_em"] + timedelta(seconds=1)
    antigo_ativo = os.environ.get("MIZAN_AGENTE_ATIVO")
    antigas_fabricas = agente_api.fabrica_repo, agente_api.fabrica_fonte, agente_api.fabrica_cliente
    os.environ["MIZAN_AGENTE_ATIVO"] = "1"
    agente_api.fabrica_repo = lambda: r.repo
    agente_api.fabrica_fonte = lambda: r.fonte
    agente_api.fabrica_cliente = lambda: cli
    try:
        resposta = agente_api.retomar_caso("emp", "p1", agora=depois)
    finally:
        agente_api.fabrica_repo, agente_api.fabrica_fonte, agente_api.fabrica_cliente = antigas_fabricas
        if antigo_ativo is None:
            os.environ.pop("MIZAN_AGENTE_ATIVO", None)
        else:
            os.environ["MIZAN_AGENTE_ATIVO"] = antigo_ativo
    saidas = [m["texto"] for m in r.repo.mensagens if m["direcao"] == "saida"]
    assert saidas and saidas[-1].endswith("Posso simular para você.")
    assert resposta["evento"]["situacao"] == "feito"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
