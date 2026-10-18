"""Revisão da frente dos agentes analíticos (Estrategista, Acompanhamento,
Supervisor, passagem, Cientista e api). Um teste por correção, com dados fictícios."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

for _v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_IA_PAPEIS",
           "MIZAN_ESTRATEGISTA_MAX"):
    os.environ.pop(_v, None)

from agente import api, auditor, ciencia, cientista, estrategista, passagem
from agente import orquestrador as orq
from agente.bateria.motor import DIA, devedor, em
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria

REGRAS = auditor.POLITICA_DEMONSTRACAO
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
falhas = 0


def checar(cond, texto, extra=""):
    global falhas
    print(("ok    " if cond else "FALHA ") + texto + (f" ({extra})" if extra and not cond else ""))
    if not cond:
        falhas += 1


def com_papeis(papeis):
    os.environ["MIZAN_IA_PAPEIS"] = ",".join(("triagem", "negociador") + tuple(papeis))


def sem_papeis():
    os.environ.pop("MIZAN_IA_PAPEIS", None)


# ── 1. grupo de entrada fixo: quem fechou acordo não some do Cientista ──────

def t_grupo_entrada():
    repo, fonte = RepoMemoria(), FonteMemoria([devedor(id="p1", probabilidade_pagamento=0.4)])
    repo.gravar_politica("emp", 1, {**REGRAS, "percentual_controle": 0})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "contato" and c["dados"]["grupo_entrada"] == "contato", "1. primeiro plano grava grupo_entrada")
    repo.salvar_caso(c["id"], {"situacao": "acordo_ativo"})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA + timedelta(days=1)))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "so_lembrete" and c["dados"]["grupo_entrada"] == "contato",
           "1. plano seguinte muda o grupo, mas não o de entrada", str((c["grupo"], c["dados"].get("grupo_entrada"))))
    checar(len(cientista.observacoes(repo, fonte, "emp")) == 1, "1. caso com acordo continua na conta do Cientista")


# ── 2. selo com direção: agente pior não ganha "evidência" ──────────────────

def _obs(n, p, grupo, dias=95, produto="cartao"):
    o = []
    for i in range(n):
        pagou = (i % 100) < p * 100
        o.append({"grupo": grupo, "pagou": pagou, "recuperado": 900.0 if pagou else 0.0, "divida": 3000.0,
                  "chance": 0.1 + (i % 10) * 0.05, "dias": dias, "produto": produto, "teve_acordo": pagou,
                  "quebrou": False})
    return o


def t_selo_com_direcao():
    pior = ciencia.analisar(_obs(200, 0.15, "agente") + _obs(200, 0.45, "sorteado"))
    t = pior["comparacao"]["taxa_pagamento"]
    checar(t["selo"] == ciencia.SEM_EVIDENCIA and t["direcao"] == ciencia.PIOR,
           "2. agente pior: sem evidência e direcao 'pior'", str(t))
    rc = cientista.relatorio_codigo(pior)
    checar("rever a abordagem" in rc["recomendacao"] and "Manter" not in rc["recomendacao"]
           and rc["direcao"] == ciencia.PIOR, "2. relatório em código recomenda rever a abordagem", rc["recomendacao"])
    melhor = ciencia.analisar(_obs(200, 0.45, "agente") + _obs(200, 0.15, "sorteado"))
    t = melhor["comparacao"]["taxa_pagamento"]
    checar(t["selo"] == ciencia.EVIDENCIA and t["direcao"] == ciencia.MELHOR, "2. agente melhor continua com evidência")
    checar(ciencia.selo(200, 200, -0.3, -0.2, True) == ciencia.SEM_EVIDENCIA, "2. selo() nunca dá evidência abaixo de zero")
    # IA que manda manter com o agente pior é reprovada nas travas e vale o relatório em código
    rel = json.dumps({"resumo": "O agente ainda não mostra resultado.", "hipoteses": [
        {"hipotese": "Procurar ajuda", "metrica": "taxa_pagamento", "resultado": "Ainda incerto.",
         "condicoes": "Carteira atual.", "proximo_experimento": "Seguir o sorteio."}],
        "recomendacao": "Manter a abordagem atual.", "recomendacao_metrica": "taxa_pagamento"})
    com_papeis(("cientista",))
    r = cientista.analisar(_ctx(ClienteFalso({"cientista": [rel, rel]})), _obs(200, 0.15, "agente")
                           + _obs(200, 0.45, "sorteado"), [])
    checar(r["origem"] == "codigo" and "rever a abordagem" in r["relatorio"]["recomendacao"],
           "2. IA que manda manter com agente pior cai na reserva", r["relatorio"]["recomendacao"])


def _ctx(cliente, caso=None, agora=None):
    from agente.rastreio import Rastreio
    repo = RepoMemoria()
    repo.gravar_politica("emp", 1, REGRAS)
    agora = agora or AGORA
    return orq.Contexto(caso=caso or {"id": None, "empresa_id": "emp", "situacao": "novo", "dados": {}},
                        evento={"id": None, "tipo": "laboratorio", "dados": {}}, repo=repo,
                        rastreio=Rastreio("emp", repo.gravar_passo), cliente=cliente, hoje=agora.date(), agora=agora)


# ── 7. Cientista: travas e hipóteses ────────────────────────────────────────

def t_cientista_travas():
    res = ciencia.analisar(_obs(40, 0.3, "agente") + _obs(40, 0.25, "sorteado"))
    perm = cientista._numeros_permitidos(res)
    for txt in ("Não há dúvida de que o agente causou a alta.", "Não resta dúvida: isso garante mais pagamentos.",
                "O agente aumentou a taxa de pagamento.", "O agente elevou o recebimento.",
                "O efeito do agente é claro.", "Sem dúvida o agente funciona."):
        checar(cientista.conferir(txt, perm, False), f"7. trava causal barra: {txt}")
    for txt in ("Ainda não há evidência de efeito do agente.", "Sem selo, não dá para dizer que o agente aumentou a taxa."):
        checar(not cientista.conferir(txt, perm, False), f"7. ressalva honesta passa: {txt}",
               str(cientista.conferir(txt, perm, False)))
    for txt, oferta in (("Manter o agente ligado nesta carteira.", False), ("Uma parcela dos devedores responde melhor.", False),
                        ("Testar parcelado_12x primeiro.", True), ("Começar pelo WhatsApp.", True),
                        ("Oferecer 30% de desconto.", True), ("Testar o parcelamento em 12x.", True)):
        checar(bool(cientista._OFERTA.search(txt)) == oferta, f"7. _OFERTA {'pega' if oferta else 'não pega'}: {txt}")


def t_cientista_segmentos_e_faixa():
    obs = _obs(200, 0.45, "agente") + _obs(200, 0.15, "sorteado")
    segs = ciencia.segmentos(obs)
    checar(segs and all(s["taxa_pagamento"]["selo"] != ciencia.EVIDENCIA for s in segs),
           "7. segmento tem no máximo 'indício'", str([s["taxa_pagamento"]["selo"] for s in segs]))
    checar(ciencia._faixa(-5) == "sem atraso" and ciencia._faixa(0) == "sem atraso"
           and ciencia._faixa(1) == "até 90 dias" and ciencia._faixa(400) == "mais de 360 dias",
           "7. _faixa: dias <= 0 é 'sem atraso', não 'mais de 360'")


def t_cientista_hipotese_passagens():
    sinais_motivo = {"dias": 7, "passagens": 4, "nao_coube": 0, "por_motivo": {"pedido_do_devedor": 3, "falha": 1}}
    h = cientista._hipotese_passagens(sinais_motivo)[0]
    checar("deixa de fora" not in h["hipotese"] and "pedido_do_devedor" in h["hipotese"],
           "7. hipótese das passagens sem 'não coube' tem título próprio", h["hipotese"])
    sinais_nc = {"dias": 7, "passagens": 4, "nao_coube": 2, "valor_pedido_quando_nao_coube": 200.0,
                 "menor_parcela_possivel": 787.5, "por_motivo": {"pedido_do_devedor": 4}}
    checar("deixa de fora" in cientista._hipotese_passagens(sinais_nc)[0]["hipotese"], "7. com 'não coube' o título fala da política")
    hip = {"hipotese": "H", "resultado": "Ainda não dá para concluir.", "condicoes": "Carteira atual.",
           "proximo_experimento": "Seguir o sorteio."}
    rel = json.dumps({"resumo": "Ainda não dá para concluir.", "hipoteses": [
        {**hip, "metrica": "taxa_pagamento"}, {**hip, "metrica": "recuperado_por_real"}, {**hip, "metrica": "bandit"}],
        "recomendacao": "Seguir o sorteio do grupo de comparação.", "recomendacao_metrica": "taxa_pagamento"})
    com_papeis(("cientista",))
    r = cientista.analisar(_ctx(ClienteFalso({"cientista": [rel]})), _obs(10, 0.3, "agente") + _obs(10, 0.3, "sorteado"),
                           [], sinais_nc)
    hips = r["relatorio"]["hipoteses"]
    checar(r["origem"] == "ia" and len(hips) == cientista.MAX_HIPOTESES and hips[-1]["metrica"] == "passagens"
           and hips[0]["metrica"] == "taxa_pagamento", "7. hipótese das passagens entra sem passar de MAX_HIPOTESES",
           str([h["metrica"] for h in hips]))


TESTES = [t_grupo_entrada, t_selo_com_direcao, t_cientista_travas, t_cientista_segmentos_e_faixa,
          t_cientista_hipotese_passagens]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception as e:                          # um teste quebrado não esconde os outros
            import traceback
            traceback.print_exc()
            checar(False, f"{t.__name__} levantou {type(e).__name__}: {e}")
        finally:
            sem_papeis()
    print(f"\n{'TUDO OK' if not falhas else f'{falhas} falha(s)'}")
    sys.exit(falhas)
