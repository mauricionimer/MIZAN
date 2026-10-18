"""Passagem para a equipe (docs/PLANO_PASSAGEM_EQUIPE.md): ficha, sugestão,
fila por prioridade, retorno do atendente e sinais para o Cientista."""
import json
import re
from datetime import datetime, timedelta, timezone

from agente import auditor, cientista, passagem
from agente.bateria.motor import Cenario, F, T, executar, tri
from agente.llm import ClienteFalso

REGRAS = auditor.POLITICA_DEMONSTRACAO              # 30% de desconto, 12 parcelas, entrada 10%
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")


def caso(divida=15000.0, valores=None, simulacoes=None):
    return {"id": "c1", "empresa_id": "emp", "situacao": "negociando",
            "dados": {"divida": divida, "identidade_ok": True, "valores_ditos": valores or [],
                      "simulacoes": simulacoes or []}}


def test_sugestao_cabe_no_valor_dito_e_esta_na_politica():
    s = passagem.sugerir_proposta(caso(3000.0, [300.0]), REGRAS, 1, AGORA)
    assert s["cabe"] is True and s["mensal"] <= 300
    assert s["n_parcelas"] <= 12 and s["desconto_pct"] <= 30
    # das que cabem, a que mais recupera (pouco desconto)
    outras = [v for v in passagem._validas(caso(3000.0), REGRAS, 1, AGORA) if passagem._mensal(*v) <= 300]
    assert s["valor_negociado"] == round(max(v[1]["valor_negociado"] for v in outras), 2)


def test_nada_cabe_sugere_a_menor_parcela():
    s = passagem.sugerir_proposta(caso(15000.0, [200.0]), REGRAS, 1, AGORA)
    assert s["cabe"] is False and s["n_parcelas"] == 12 and s["desconto_pct"] == 30
    assert "menor parcela" in s["motivo"]


def test_sem_valor_dito_sugere_proximo_degrau():
    sim = [{"condicoes": {"n_parcelas": 6, "desconto_pct": 0.0, "entrada_pct": 10.0, "juros_mensal_pct": 0},
            "conta": {"entrada": 1500.0, "parcela": 2250.0, "total_pago": 15000.0, "valor_negociado": 15000.0}}]
    s = passagem.sugerir_proposta(caso(15000.0, simulacoes=sim), REGRAS, 1, AGORA)
    assert s["n_parcelas"] > 6 and s["desconto_pct"] >= 0
    f = passagem.montar_ficha(caso(15000.0, simulacoes=sim), "pedido_do_devedor", None, REGRAS, 1, AGORA)
    assert f["tentado"][0]["resumo"].endswith("6x de R$ 2.250,00")


def test_prioridade_ordena_irritado_com_pressa_antes():
    calma = passagem.montar_ficha(caso(), "duvida", {"emocao": "calmo", "urgencia": "baixa"}, REGRAS, 1, AGORA)
    brava = passagem.montar_ficha(caso(), "pedido_do_devedor", {"emocao": "irritado", "urgencia": "alta"}, REGRAS, 1, AGORA)
    grave = passagem.montar_ficha(caso(), "dificuldade_grave", {"emocao": "desesperado", "urgencia": "alta"}, REGRAS, 1, AGORA)
    assert grave["prioridade"] > brava["prioridade"] > calma["prioridade"]
    assert brava["nivel"] == "urgente" and calma["nivel"] == "normal"
    # a espera aumenta a prioridade
    assert passagem.para_tela(calma, AGORA + timedelta(hours=10))["prioridade"] == calma["prioridade"] + 10


def test_ia_invalida_cai_na_leitura_da_triagem():
    c = caso()
    c["dados"]["caderno"] = [{"agente": "triagem", "motivo": "ansioso, urgência alta"}]
    f = passagem.montar_ficha(c, "duvida", {"emocao": "furioso", "urgencia": "agora"}, REGRAS, 1, AGORA)
    assert f["emocao"] == "ansioso" and f["urgencia"] == "alta"


def test_ficha_sem_cpf_ou_telefone():
    f = passagem.montar_ficha(caso(), "duvida", {"situacao": "CPF 123.456.789-00 tel 62 99999-8888 quer pagar"},
                              REGRAS, 1, AGORA)
    assert not CPF.search(json.dumps(f, ensure_ascii=False)) and "99999" not in f["situacao"]


def test_transferencia_de_verdade_grava_ficha_e_agenda_com_sugestao():
    c = Cenario("t", "t", "t", dados={"identidade_ok": True, "divida": 15000.0},
                passos=[("mensagem", "só consigo 200 por mês"), ("mensagem", "quero falar com uma pessoa")],
                roteiro=[json.dumps({"intencao": "pagar_negociar", "confianca": 0.9, "valores_citados": [200],
                                     "datas_citadas": [], "sinais_de_risco": [], "emocao": "ansioso"}),
                         T("Entendo. Posso ver opções com mais parcelas."),
                         tri("pedir_humano", emocao="irritado", urgencia="alta"),
                         F("transferir_para_humano", motivo="pedido_do_devedor", resumo="Pediu uma pessoa.")],
                conferir=[])
    r = executar(c, None)
    cs = r.repo.casos[r.caso["id"]]
    f = cs["dados"]["passagem"]
    assert cs["situacao"] == "com_pessoa" and f["valor_dito"] == 200.0
    assert f["sugestao"]["cabe"] is False and f["nivel"] in ("normal", "alta", "urgente") and len(cs["dados"]["passagens"]) == 1
    obs = [a["observacao"] for a in r.fonte.agenda]
    assert any("Disse que consegue: R$ 200,00" in o and "Sugestão:" in o for o in obs), obs


def test_retorno_do_atendente_e_nota():
    c = caso()
    passagem.guardar(c, passagem.montar_ficha(c, "duvida", None, REGRAS, 1, AGORA))
    passagem.registrar_retorno(c, True, "ana@demo", "ajudou, CPF 123.456.789-00", AGORA)
    assert c["dados"]["passagem"]["retorno"]["ajudou"] is True
    assert "123.456" not in c["dados"]["passagem"]["retorno"]["comentario"]
    s = passagem.sinais_da_equipe([c], AGORA)
    assert s["retornos"] == 1 and s["nota_supervisor"] == 1.0
    try:
        passagem.registrar_retorno(caso(), True, None)
        assert False, "caso sem passagem devia falhar"
    except LookupError:
        pass


def test_sinais_da_semana_e_hipotese_do_cientista():
    casos = []
    for i, v in enumerate([150, 200, 250, 1100, None]):
        c = caso(15000.0, [v] if v else [])
        passagem.guardar(c, passagem.montar_ficha(c, "pedido_do_devedor", None, REGRAS, 1, AGORA - timedelta(days=i)))
        casos.append(c)
    velho = caso(15000.0, [100])
    passagem.guardar(velho, passagem.montar_ficha(velho, "duvida", None, REGRAS, 1, AGORA - timedelta(days=20)))
    s = passagem.sinais_da_equipe(casos + [velho], AGORA)
    assert s["passagens"] == 5 and s["com_valor_dito"] == 4 and s["nao_coube"] == 3   # 1100 cabe: entrada R$ 1.050 + 12x de R$ 787,50
    assert s["valor_pedido_quando_nao_coube"] == 200.0
    hip = cientista._hipotese_passagens(s)
    assert hip and hip[0]["selo"] == "sem evidência" and "3 de 5" in hip[0]["resultado"]
    # selo da métrica 'passagens' é sempre do código
    assert cientista._selo_da_metrica({"comparacao": {}}, "passagens") == "sem evidência"


def test_valores_anotados_so_os_plausiveis():
    c = caso(3000.0)
    passagem.anotar_valores(c, [200, "abc", True, -5, 0, 99_999_999])
    assert c["dados"]["valores_ditos"] == [200.0]


def test_api_fila_e_retorno_com_repo_em_memoria():
    from agente import api
    from agente.repositorio import RepoMemoria
    repo = RepoMemoria()
    c = repo.obter_ou_criar_caso("emp", "pred-1")
    c["dados"] = {"divida": 15000.0, "identidade_ok": True, "valores_ditos": [200.0]}
    f = passagem.montar_ficha(c, "pedido_do_devedor", {"emocao": "irritado", "urgencia": "alta"}, REGRAS, 1, AGORA)
    passagem.guardar(c, f)
    repo.salvar_caso(c["id"], {"dados": c["dados"]})
    antes = api.fabrica_repo
    api.fabrica_repo = lambda: repo
    try:
        fila = api.passagens_da_fila("emp", ["pred-1", "pred-x"], AGORA)
        assert list(fila) == ["pred-1"] and fila["pred-1"]["nivel"] == "urgente"
        api.registrar_retorno_passagem("emp", "pred-1", False, "ana@demo", "faltou o motivo")
        assert repo.caso_de("emp", "pred-1")["dados"]["passagem"]["retorno"]["ajudou"] is False
        assert api.sinais_equipe("emp", AGORA)["nota_supervisor"] == 0.0
        try:
            api.registrar_retorno_passagem("emp", "pred-x", True, None)
            assert False
        except LookupError:
            pass
    finally:
        api.fabrica_repo = antes


def test_agenda_junta_a_ficha_e_ordena_por_prioridade():
    import os, sys
    os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:1"); os.environ.setdefault("SUPABASE_KEY", "x")
    os.environ.setdefault("JWT_SECRET", "teste")
    import main
    from agente import api
    fichas = {"p1": {"prioridade": 10, "nivel": "normal"}, "p2": {"prioridade": 80, "nivel": "urgente"}}
    antes = (api.ligado, api.passagens_da_fila)
    api.ligado = lambda: True
    api.passagens_da_fila = lambda emp, ids, agora=None: {k: v for k, v in fichas.items() if k in ids}
    try:
        itens = [{"predicao_id": "p1", "observacao": "Transferido pelo agente: x", "data": "2026-10-19"},
                 {"predicao_id": "p2", "observacao": "Transferido pelo agente: y", "data": "2026-10-19"},
                 {"predicao_id": "p3", "observacao": "Ligar de volta", "data": "2026-10-19"}]
        main._com_passagem("emp", itens, "pendente")
        assert itens[1]["passagem"]["nivel"] == "urgente" and "passagem" not in itens[2]
        api.passagens_da_fila = lambda *a, **k: 1 / 0          # módulo quebrado não derruba a agenda
        outros = [dict(i, passagem=None) for i in itens]
        main._com_passagem("emp", outros, "pendente")
    finally:
        api.ligado, api.passagens_da_fila = antes


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
