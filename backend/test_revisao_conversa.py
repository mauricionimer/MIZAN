"""Correções da revisão da conversa (Triagem, Negociador, travas e ferramentas).

Cada teste é um achado da revisão de 18/10/2026 que não pode voltar. Roda sem
IA real e sem banco (ClienteFalso, RepoMemoria, FonteMemoria, dados fictícios).
"""
from agente.bateria.motor import ID_OK, Cenario, F, T, executar, tri
from agente.llm import ClienteFalso


def rodar(passos, roteiro, dados=None, **kw):
    c = Cenario("t", "t", "t", dados=dict(ID_OK if dados is None else dados), passos=passos, conferir=[], **kw)
    return executar(c, ClienteFalso(roteiro))


def caso(r):
    return r.repo.casos[r.caso["id"]]


# ── (a) risco à vida junto com "me deixa em paz" ────────────────────────────

def test_sofrimento_com_pedido_de_parar_suspende_e_avisa_a_equipe():
    r = rodar([("mensagem", "me deixa em paz, vou me matar")], {"triagem": [], "negociador": []})
    assert caso(r)["situacao"] == "suspenso", caso(r)["situacao"]
    assert any("sofrimento grave" in (a.get("observacao") or "") for a in r.fonte.agenda), r.fonte.agenda
    txt = r.saidas[-1]
    assert "188" in txt and "passar a conversa" not in txt, txt        # sem promessa de pessoa


def test_sofrimento_com_contestacao_contesta_e_avisa_a_equipe():
    r = rodar([("mensagem", "essa dívida não é minha, vou me matar")], {"triagem": [], "negociador": []})
    assert caso(r)["situacao"] == "contestado", caso(r)["situacao"]
    assert any("sofrimento grave" in (a.get("observacao") or "") for a in r.fonte.agenda)
    assert "188" in r.saidas[-1]


def test_sofrimento_sozinho_continua_indo_para_pessoa():
    r = rodar([("mensagem", "vou me matar")], {"triagem": [tri("outro")], "negociador": []})
    assert caso(r)["situacao"] == "com_pessoa" and "188" in r.saidas[-1]


# ── (d) e (e) regras da Triagem ─────────────────────────────────────────────

def test_desculpe_o_engano_quero_pagar_vai_para_a_ia():
    r = rodar([("mensagem", "Desculpe o engano, quero pagar sim")],
              {"triagem": [tri("pagar_negociar")], "negociador": [T("Ótimo! Vamos ver as opções.")]})
    assert caso(r)["situacao"] not in ("suspenso", "contestado", "com_pessoa"), caso(r)["situacao"]
    assert r.saidas[-1].endswith("Vamos ver as opções.")


def test_para_de_cobrar_esses_juros_nao_suspende():
    r = rodar([("mensagem", "Para de cobrar esses juros e me dá um desconto")],
              {"triagem": [tri("pagar_negociar")], "negociador": [T("Posso simular um desconto para você.")]})
    assert caso(r)["situacao"] != "suspenso"


def test_sofrimento_da_ia_vale_com_tristeza():
    r = rodar([("mensagem", "não vejo saída nenhuma, tudo dá errado")],
              {"triagem": [tri("outro", "sofrimento_grave", emocao="triste")], "negociador": []})
    assert caso(r)["situacao"] == "com_pessoa" and "188" in r.saidas[-1]


def test_frases_novas_de_risco_a_vida():
    from agente import triagem
    for f in ["eu só quero morrer", "tenho vontade de morrer", "vou me jogar da ponte",
              "não quero mais estar aqui", "penso em tirar a minha vida"]:
        assert "sofrimento_grave" in triagem.regras(f)["sinais"], f
    for f in ["quero morrer de rir", "vou me jogar de cabeça nesse acordo"]:
        assert "sofrimento_grave" not in triagem.regras(f)["sinais"], f


# ── (g) CPF não vai para a IA ───────────────────────────────────────────────

def test_cpf_completo_nao_chega_na_ia_e_confirma_pelos_tres_primeiros():
    import json
    r = rodar([("mensagem", "Sou eu sim, meu cpf é 123.456.789-00"), ("mensagem", "ok, e agora?")],
              {"triagem": [tri("outro"), tri("outro")],
               "negociador": [F("verificar_identidade", tres_primeiros_digitos_cpf="123.***.***-**"), T("Obrigado!"),
                              T("Vamos ver as opções.")]}, dados={})
    txt = json.dumps(r.cliente.chamadas, ensure_ascii=False)
    assert "456" not in txt and "789-00" not in txt, "CPF completo chegou na IA"
    assert "123.***.***-**" in txt
    assert caso(r)["dados"].get("identidade_ok") is True
    # Se a IA mandar o CPF inteiro para a ferramenta, valem os 3 primeiros dígitos.
    r = rodar([("mensagem", "123.456.789-00")],
              {"triagem": [tri("outro")],
               "negociador": [F("verificar_identidade", tres_primeiros_digitos_cpf="123.456.789-00"), T("Obrigado!")]},
              dados={})
    assert caso(r)["dados"].get("identidade_ok") is True and not caso(r)["dados"].get("falhas_identidade")


def test_mascarar_nao_mexe_em_data_nem_valor():
    from agente import triagem
    assert triagem.mascarar("pago dia 20/10/2026") == "pago dia 20/10/2026"
    assert triagem.mascarar("R$ 15.000,00 ou 300 400 500") == "R$ 15.000,00 ou 300 400 500"
    assert triagem.mascarar("conta 1234567890") == "conta [número]"


# ── (l) Triagem tolerante a formato ─────────────────────────────────────────

def test_triagem_tolera_forma():
    from agente import triagem
    for bruto in ['{"intencao":"outro","confianca":"0.9"}', '{"intencao":"outro","confianca":90}',
                  'Aqui está: {"intencao":"Outro","confianca":0.9}', '{"intencao":"outro"}']:
        v = triagem._validar(bruto)
        assert v["intencao"] == "outro" and 0 <= v["confianca"] <= 1, bruto
    try:
        triagem._validar('{"intencao":"comprar","confianca":0.9}')
        assert False, "intenção fora da lista devia ser recusada"
    except ValueError:
        pass


# ── (b), (c), (h), (i), (j) travas de saída ─────────────────────────────────

def test_limites_da_politica_e_dias_de_atraso_nao_viram_valor():
    from agente import auditor, guardrails
    pol = {"ok": True, "versao": 1, "regras": auditor.POLITICA_DEMONSTRACAO, "aviso": "x"}
    caso_ = {"ok": True, "valor_divida": 15000.0, "dias_em_atraso": 95,
             "compromissos": [{"id": "a1", "tipo": "promessa", "data": "2026-10-20", "valor": 270.0}]}
    perm = guardrails.permitidos_de([pol, caso_])
    assert guardrails.conferir("Consigo te dar até 30% de desconto.", perm)
    assert guardrails.conferir("A parcela mínima é R$ 50,00.", perm)
    assert guardrails.conferir("Fica R$ 95,00 por mês.", perm)
    assert not guardrails.conferir("Sua dívida é de R$ 15.000,00 e a promessa de R$ 270,00 vence dia 20/10.", perm)


def test_negociador_nao_cita_limite_da_politica():
    r = rodar([("mensagem", "qual o máximo de desconto?")],
              {"triagem": [tri("pagar_negociar")],
               "negociador": [F("consultar_politica"), T("Consigo te dar até 30% de desconto."),
                              T("Consigo te dar até 30% de desconto."), ]})
    assert not any("30%" in s for s in r.saidas), r.saidas
    assert "dizer de outro jeito" in r.saidas[-1]


def test_reprovacao_diz_o_termo():
    from agente import guardrails
    perm = guardrails.permitidos_de([])
    m = guardrails.conferir("Se não pagar, vamos processar você.", perm)
    assert any("processar" in x for x in m), m
    m = guardrails.conferir("Seu CPF é 123.456.789-00.", perm)
    assert m and not any("456" in x for x in m), m            # diz o tipo, nunca repete o dado


def test_acoes_ditas_com_outras_palavras():
    from agente import guardrails
    perm = guardrails.permitidos_de([])
    for t in ["Combinado, te chamo dia 20 às 10h.", "Pronto, sua cobrança está pausada.",
              "Já avisei a equipe, vão te ligar amanhã.", "Seu acordo está aprovado!",
              "Pagamento recebido, obrigado!", "Sua dívida está zerada.", "Anotado! A equipe confere."]:
        assert guardrails.conferir(t, perm, feitas=set()), t
    assert not guardrails.conferir("Pronto, sua cobrança está pausada.", perm, feitas={"suspender_cobranca"})
    assert not guardrails.conferir("Posso pedir para a equipe te ligar?", perm, feitas=set())


# ── (f) aceite com pagamento hoje ───────────────────────────────────────────

def test_aceite_com_pagamento_hoje_vale_so_no_aceite():
    from agente.bateria.motor import ACEITE, DIA
    hoje = DIA.isoformat()
    r = rodar([("mensagem", "Aceito à vista, pago hoje mesmo no pix")],
              {"triagem": [tri("pagar_negociar")],
               "negociador": [F("simular_acordo", n_parcelas=1, desconto_pct=10), ACEITE(hoje), T("Combinado!")]})
    assert caso(r)["situacao"] == "acordo_ativo", caso(r)["situacao"]
    assert "R11_DATA" not in r.bloqueios()
    # retorno para hoje continua barrado (só o aceite aceita hoje)
    r = rodar([("mensagem", "me chama mais tarde")],
              {"triagem": [tri("outro")],
               "negociador": [F("agendar_retorno", data=hoje, motivo="pediu"), T("Posso te chamar amanhã?")]})
    assert "R11_DATA" in r.bloqueios()


if __name__ == "__main__":
    import sys
    falhas = 0
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            try:
                f()
                print("ok", nome)
            except Exception as e:                        # noqa: BLE001
                falhas += 1
                print("FALHA", nome, type(e).__name__, str(e)[:300])
    print("falhas:", falhas)
    sys.exit(falhas)
