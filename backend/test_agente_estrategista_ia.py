"""Etapa 4: Estrategista com IA — ficha fechada, bandit como ferramenta, conferência em código."""
import json
import os

from agente import auditor, estrategista_ia
from agente import orquestrador as orq
from agente.api import grafos
from agente.bateria.motor import DIA, devedor, em
from agente.estrategista import plano
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria

BANDIT = {"oferta": "desconto_30pct", "modo": "aprendendo", "total_interacoes": 12, "canal": "whatsapp"}


def montar(n=1, pct=0):
    devs = [devedor(id=f"p{i}", probabilidade_pagamento=0.3, cpf=f"000.000.000-{i:02d}", regiao="Sudeste",
                    renda=4200, nome=f"Maria {i} da Silva") for i in range(n)]
    repo, fonte = RepoMemoria(), FonteMemoria(devs)
    fonte._bandit = dict(BANDIT)
    repo.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "percentual_controle": pct})
    return repo, fonte


def dec(**d):
    base = {"decisao": "abordar", "tom": "acolhedor", "oferta_inicial": "parcelado_12x", "concorda_bandit": False,
            "raciocinio": "atraso longo e dívida alta: parcelar cabe mais no bolso que desconto à vista"}
    return json.dumps({**base, **d})


def aplicar(repo, fonte, roteiro, papeis="triagem,negociador,estrategista"):
    os.environ["MIZAN_IA_PAPEIS"] = papeis
    try:
        cli = ClienteFalso({"estrategista": list(roteiro)})
        plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
        orq.processar_fila(repo, grafos(fonte), cli, limite=50, agora=em(DIA))
        return cli
    finally:
        os.environ.pop("MIZAN_IA_PAPEIS", None)


def saidas(repo):
    return [m["texto"] for m in repo.mensagens if m["direcao"] == "saida"]


def test_ficha_nao_tem_campo_proibido():
    repo, fonte = montar()
    cli = aplicar(repo, fonte, [dec()])
    ficha_txt = cli.chamadas[0]["mensagens"][0]["content"]
    ficha = json.loads(ficha_txt.removeprefix("<ficha>").removesuffix("</ficha>"))
    assert set(ficha) == set(estrategista_ia.FICHA_CAMPOS)
    baixo = ficha_txt.lower()
    for proibido in ("sudeste", "4200", "000.000", "silva", "maria"):
        assert proibido not in baixo, proibido
    assert ficha["bandit"]["oferta"] == "desconto_30pct" and ficha["chance"] == "média"


def test_abordagem_com_ia_e_estrategia_no_caso():
    repo, fonte = montar()
    aplicar(repo, fonte, [dec()])
    caso = repo.caso_de("emp", "p0")
    assert caso["situacao"] == "em_contato"
    s = saidas(repo)[0]
    assert s.startswith("Olá, Maria! Aqui é o assistente virtual de Banco Demonstração. Tudo bem?")
    assert "posso confirmar se estou falando com você" in s
    assert "tratar com privacidade" in s
    assert all(t not in s.lower() for t in ("pendência", "regularizar", "r$"))
    assert "opções para organizar a situação" in s.lower()
    est = caso["dados"]["estrategia"]
    assert est["oferta_inicial"] == "parcelado_12x" and est["concorda_bandit"] is False and est["bandit_oferta"] == "desconto_30pct"
    assert any(n["agente"] == "estrategista" and n["decisao"].startswith("abordar") for n in caso["dados"]["caderno"])
    passo = next(p for p in repo.passos if p["no"] == "estrategia")
    assert passo["detalhe"]["concorda_bandit"] is False and passo["detalhe"]["origem"] == "ia"


def test_decisao_invalida_vira_abertura_reservada():
    for ruim in (dec(oferta_inicial="desconto_90pct"), dec(decisao="adiar", adiar_dias=30), "isso não é json"):
        repo, fonte = montar()
        aplicar(repo, fonte, [ruim])
        saida = saidas(repo)[0]
        assert "posso confirmar se estou falando com você" in saida, ruim
        assert "pendência" not in saida.lower(), ruim
        assert "estrategia" not in repo.caso_de("emp", "p0")["dados"]


def test_adiar():
    repo, fonte = montar()
    aplicar(repo, fonte, [dec(decisao="adiar", adiar_dias=3, raciocinio="pediu para falar depois do dia 20")])
    caso = repo.caso_de("emp", "p0")
    assert caso["situacao"] == "novo" and not saidas(repo)
    adiado = [e for e in repo.eventos.values() if ":adiada:" in e["chave"]]
    assert len(adiado) == 1 and adiado[0]["dados"] == {"com_ia": False}


def test_limite_por_dia_e_sorteados_fora():
    os.environ["MIZAN_ESTRATEGISTA_MAX"] = "3"
    try:
        repo, fonte = montar(n=6)
        cli = aplicar(repo, fonte, [dec()] * 6)
        assert len([c for c in cli.chamadas if c["papel"] == "estrategista"]) == 3
        assert len(saidas(repo)) == 6                                  # os outros 3 com a abordagem de hoje
    finally:
        os.environ.pop("MIZAN_ESTRATEGISTA_MAX", None)
    repo, fonte = montar(n=20, pct=50)
    cli = aplicar(repo, fonte, [dec()] * 20)
    sorteados = {c["predicao_id"] for c in repo.casos.values() if c["grupo_controle"]}
    assert sorteados and not any(m for m in repo.mensagens if repo.casos[m["caso_id"]]["predicao_id"] in sorteados)


def test_lotes_de_dez():
    repo, fonte = montar(n=14)
    cli = aplicar(repo, fonte, [dec()] * 14)
    assert len([c for c in cli.chamadas if c["papel"] == "estrategista"]) == 10   # o lote 2 sai no ciclo seguinte
    pendentes = [e for e in repo.eventos.values() if e["tipo"] == "abordagem" and e["situacao"] == "pendente"]
    assert len(pendentes) == 4


def test_desligado_e_igual_a_hoje():
    repo, fonte = montar()
    cli = aplicar(repo, fonte, [dec()], papeis="triagem,negociador")
    assert not cli.chamadas and "posso confirmar se estou falando com você" in saidas(repo)[0]


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
