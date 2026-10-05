"""Regressão: o motor de renegociação reproduz as simulações da referência.

    python test_proposta.py      (ou python -m pytest test_proposta.py)

As duas simulações da referência técnica são reproduzidas linha a linha. Se
alguém mexer na fórmula do valor esperado ou no teste de capacidade de
pagamento, estes números param de bater — que é exatamente o ponto: o motor
não pode divergir da referência que ele diz implementar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model.proposta import (  # noqa: E402
    Margem, PoliticaProposta, avaliar, calcular_margem,
    montar_propostas, parcela_maxima,
)

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


def perto(a, b, tol=1.0):
    return a is not None and abs(a - b) <= tol


# ===========================================================================
# SIMULAÇÃO 1 — João
# Dívida R$ 10.000 + R$ 2.000 de juros = R$ 12.000. Atraso 180 dias.
# Margem livre: R$ 400/mês.
# ===========================================================================
print("— Simulação 1 (João, dívida de R$ 12.000, margem de R$ 400) —")

DIVIDA_1 = 12000.0
MARGEM_1 = Margem(400.0, "informada")

# As quatro propostas da tabela, com a PoP que a referência atribui a cada uma
ARQ_1 = [
    {"rotulo": "A — Rápida/Sem desconto",  "desconto_pct": 0.0,  "n_parcelas": 6},
    {"rotulo": "B — Longo/Sem desconto",   "desconto_pct": 0.0,  "n_parcelas": 36},
    {"rotulo": "C — Desconto moderado",    "desconto_pct": 30.0, "n_parcelas": 12},
    {"rotulo": "D — Quitação à vista",     "desconto_pct": 60.0, "n_parcelas": 1},
]
POP_1 = [0.02, 0.65, 0.15, 0.35]
props_1 = montar_propostas(DIVIDA_1, ARQ_1)
av_1 = avaliar(props_1, MARGEM_1, POP_1, origem_pop="referencia")

# parcelas da tabela: 2.000 / 333 / 700 / 4.800 à vista
checar(perto(props_1[0].parcela, 2000), "1A parcela de R$ 2.000", f"{props_1[0].parcela}")
checar(perto(props_1[1].parcela, 333, tol=1.0), "1B parcela de R$ 333", f"{props_1[1].parcela}")
checar(perto(props_1[2].parcela, 700), "1C parcela de R$ 700", f"{props_1[2].parcela}")
checar(perto(props_1[3].valor_cobrado, 4800), "1D quitação de R$ 4.800", f"{props_1[3].valor_cobrado}")

# valores esperados da tabela: 240 / 7.800 / 1.260 / 1.680
for p, esperado in zip(props_1, [240.0, 7800.0, 1260.0, 1680.0]):
    checar(perto(p.valor_esperado, esperado), f"EV de {p.rotulo} = R$ {esperado:,.0f}",
           f"calculado {p.valor_esperado}")

# capacidade de pagamento: A falha, B passa, C falha, D não se aplica
checar(props_1[0].cabe_no_bolso is False, "1A não cabe (R$ 2.000 > R$ 400)")
checar(props_1[1].cabe_no_bolso is True,  "1B cabe (R$ 333 < R$ 400)")
checar(props_1[2].cabe_no_bolso is False, "1C não cabe (R$ 700 > R$ 400)")
checar(props_1[3].cabe_no_bolso is None,  "1D à vista não passa pelo teste de margem")

# a decisão da referência: B em destaque, D como opção secundária
checar(av_1.recomendada is props_1[1],
       "recomenda a B — a única que cabe no bolso e maximiza o EV",
       av_1.recomendada.rotulo if av_1.recomendada else "nenhuma")
checar(av_1.alternativa_a_vista is props_1[3], "mantém a quitação à vista como alternativa")

# a armadilha: a proposta de maior EV entre TODAS seria a B mesmo; mas se a
# margem fosse menor, o motor não pode recomendar algo que não cabe
av_apertada = avaliar(montar_propostas(DIVIDA_1, ARQ_1), Margem(300.0, "informada"),
                      POP_1, origem_pop="referencia")
checar(av_apertada.recomendada is None or av_apertada.recomendada.parcela <= 300,
       "com margem de R$ 300, não recomenda parcela que não cabe",
       f"{av_apertada.recomendada.rotulo if av_apertada.recomendada else 'nenhuma'}")


# ===========================================================================
# SIMULAÇÃO 2 — Carlos
# Dívida R$ 3.000 (saldo com juros). Vive de bicos, ~R$ 800/mês.
# ===========================================================================
print("\n— Simulação 2 (Carlos, dívida de R$ 3.000, bicos de R$ 800) —")

DIVIDA_2 = 3000.0
MARGEM_2 = Margem(800.0, "informada")

# A linha B da tabela tem parcela de R$ 270 com 0% de desconto: 12 × 270 =
# R$ 3.240 > dívida. São juros embutidos, e o EV da referência (R$ 900) usa
# R$ 3.000 — juros novos não são recuperação da dívida.
ARQ_2 = [
    {"rotulo": "A — 3x sem juros", "desconto_pct": 0.0,  "n_parcelas": 3},
    # 1,204346% ao mês pela tabela Price dá a parcela de R$ 270 da referência
    # (antes a conta era de juros simples, com 0,667% ao mês).
    {"rotulo": "B — 12x",          "desconto_pct": 0.0,  "n_parcelas": 12,
     "juros_mensal_pct": 1.204346},
    {"rotulo": "C — 10x",          "desconto_pct": 33.0, "n_parcelas": 10},
    {"rotulo": "D — À vista",      "desconto_pct": 60.0, "n_parcelas": 1},
]
POP_2 = [0.05, 0.30, 0.70, 0.40]
props_2 = montar_propostas(DIVIDA_2, ARQ_2)
av_2 = avaliar(props_2, MARGEM_2, POP_2, origem_pop="referencia")

for p, esperado in zip(props_2, [1000.0, 270.0, 200.0, 1200.0]):
    checar(perto(p.parcela, esperado, tol=2.0), f"parcela de {p.rotulo} = R$ {esperado:,.0f}",
           f"calculado {p.parcela}")

for p, esperado in zip(props_2, [150.0, 900.0, 1400.0, 480.0]):
    checar(perto(p.valor_esperado, esperado, tol=10.0),
           f"EV de {p.rotulo} = R$ {esperado:,.0f}", f"calculado {p.valor_esperado}")

checar(av_2.recomendada is props_2[2],
       "recomenda a C — cabe nos bicos e dá o maior retorno esperado",
       av_2.recomendada.rotulo if av_2.recomendada else "nenhuma")
checar(props_2[0].cabe_no_bolso is False, "2A não cabe (R$ 1.000 > R$ 800)")

# o juros embutido não pode inflar o valor recuperado
checar(perto(props_2[1].valor_cobrado, 3000.0),
       "juros embutido não entra como recuperação", f"{props_2[1].valor_cobrado}")
checar(props_2[1].parcela * 12 > props_2[1].valor_cobrado,
       "mas a soma das parcelas fica acima da dívida, como na referência",
       f"12 × {props_2[1].parcela} = {round(props_2[1].parcela * 12, 2)}")


# ===========================================================================
# Margem livre
# ===========================================================================
print("\n— Margem livre —")

# "R$ 4.500 (Renda) - R$ 2.500 (Despesas fixas) - 30% Buffer = R$ 1.400"
m = calcular_margem(4500, 2500)
checar(perto(m.valor, 1400.0), "reproduz o cálculo de margem da referência", f"R$ {m.valor}")

# "Parcela não pode comprometer mais que 30% da margem livre" -> R$ 1.000 vira R$ 300
politica_30 = PoliticaProposta(buffer_margem_pct=0.0, comprometimento_max_pct=30.0)
m2 = calcular_margem(5000, 4000, politica_30)
checar(perto(m2.valor, 1000.0), "margem sem buffer = renda - despesas", f"R$ {m2.valor}")
checar(perto(parcela_maxima(m2, politica_30), 300.0),
       "teto de 30% da margem livre", f"R$ {parcela_maxima(m2, politica_30)}")

sem_desp = calcular_margem(4500, None)
checar(not sem_desp.conhecida, "sem despesas, a margem é desconhecida — não estimada")
checar("despesas_mensais" in sem_desp.motivo, "e o motivo diz o que falta",
       sem_desp.motivo[:60])

negativa = calcular_margem(3000, 3500)
checar(negativa.valor == 0.0 and negativa.motivo,
       "despesa maior que renda: margem zero, com explicação", negativa.motivo[:50])


# ===========================================================================
# Honestidade do motor quando falta informação
# ===========================================================================
print("\n— Quando falta informação —")

av_sem_margem = avaliar(montar_propostas(DIVIDA_1, ARQ_1),
                        calcular_margem(4500, None), POP_1, origem_pop="modelo")
checar(all(p.cabe_no_bolso is None for p in av_sem_margem.propostas if not p.a_vista),
       "sem margem, nenhuma proposta é aprovada nem reprovada por capacidade")
checar("capacidade de pagamento" in av_sem_margem.aviso,
       "e o aviso diz que o teste não rodou", av_sem_margem.aviso[:60])

# Sem saber se cabe no bolso, o motor não pode coroar ninguém: apontar a
# parcela de maior valor esperado sem verificar capacidade é pior do que não
# apontar nada — foi o que a tela mostrou, sugerindo R$ 2.000/mês às cegas.
checar(av_sem_margem.recomendada is None,
       "sem margem, nenhuma proposta é marcada como sugerida",
       av_sem_margem.recomendada.rotulo if av_sem_margem.recomendada else "nenhuma")
checar("informe as despesas" in av_sem_margem.aviso,
       "e o aviso diz o que fazer para destravar")
checar(all(len(p.observacao) < 60 for p in av_sem_margem.propostas),
       "a observação de cada proposta fica curta, sem repetir o motivo inteiro",
       f"maior tem {max(len(p.observacao) for p in av_sem_margem.propostas)} caracteres")
# com margem, continua recomendando normalmente
checar(av_1.recomendada is not None, "com margem conhecida, a recomendação volta")

# PoP igual para todas: o motor precisa admitir que não está discriminando
av_igual = avaliar(montar_propostas(DIVIDA_1, ARQ_1), MARGEM_1,
                   [0.4, 0.4, 0.4, 0.4], origem_pop="modelo")
checar(not av_igual.pop_discrimina, "detecta que a PoP é a mesma para todas")
checar("não distingue as ofertas por probabilidade" in av_igual.aviso,
       "e avisa que a ordenação não separa por probabilidade")
checar(av_1.pop_discrimina, "com PoP por oferta, marca que está discriminando")


# ===========================================================================
# PoP por oferta, vinda do feedback real
# ===========================================================================
print("\n— PoP por oferta (bandit) —")

import os as _os, tempfile as _tmp  # noqa: E402
_os.environ["MIZAN_DATA_DIR"] = _tmp.mkdtemp()
Path(_os.environ["MIZAN_DATA_DIR"], "model").mkdir(parents=True, exist_ok=True)
from model import bandit as B  # noqa: E402
from model.proposta import ARQUETIPOS_PADRAO  # noqa: E402

B._salvar_supabase = lambda e, b: None
B._carregar_supabase = lambda e: None
CTX = [0.5] * B.D
EMP = "banco_teste"

# O catálogo de ofertas tem de ser o mesmo dos dois lados, senão o bandit
# aprende sobre uma oferta e a tela propõe outra.
checar({a["oferta"] for a in ARQUETIPOS_PADRAO} == {a["oferta"] for a in B.ACOES},
       "proposta e bandit usam o mesmo catálogo de ofertas")

# Sem feedback nenhum: a estimativa é exatamente a do modelo
pops = B.pop_por_oferta(EMP, 0.65)
checar(all(abs(v["pop"] - 0.65) < 1e-9 for v in pops.values()),
       "sem feedback, a PoP de toda oferta é a do modelo",
       f'{sorted({v["pop"] for v in pops.values()})}')
checar(all(v["origem"] == "modelo" for v in pops.values()),
       "e a origem diz que veio do modelo, não do histórico")

# 20 renegociações com desconto de 30%, 16 pagaram (ação 6 = telefone + 30%)
for i in range(20):
    B.registrar_resultado(6, CTX, 0.9 if i < 16 else 0.0, EMP)
pops = B.pop_por_oferta(EMP, 0.65)
d30 = pops["desconto_30pct"]

checar(d30["origem"] == "bandit", "com histórico, a oferta passa a vir do bandit")
checar(d30["n_tentativas"] == 20 and d30["n_pagamentos"] == 16,
       "conta tentativas e pagamentos separadamente",
       f'{d30["n_pagamentos"]}/{d30["n_tentativas"]}')
checar(perto(d30["taxa_observada"], 0.80, tol=0.001), "taxa observada de 80%",
       str(d30["taxa_observada"]))
# suavização: entre o modelo (0,65) e o observado (0,80), puxado pela evidência
checar(0.65 < d30["pop"] < 0.80, "a estimativa fica entre o modelo e o observado",
       f'{d30["pop"]}')
checar(pops["parcelado_4x"]["pop"] == 0.65,
       "oferta sem histórico continua na probabilidade do modelo")

# "1 de 1" não pode virar 100%
B2 = "outro_banco"
B.registrar_resultado(2, CTX, 1.0, B2)     # ação 2 = whatsapp + desconto_30pct
um_de_um = B.pop_por_oferta(B2, 0.30)["desconto_30pct"]
checar(um_de_um["pop"] < 0.45,
       "um único pagamento não vira certeza", f'pop={um_de_um["pop"]} com 1 observação')
checar(um_de_um["taxa_observada"] == 1.0,
       "embora a taxa crua seja 100% — é a suavização que segura")

# a recompensa parcial não infla a PoP: quem pagou metade pagou
B3 = "terceiro"
for _ in range(10):
    B.registrar_resultado(1, CTX, 0.5, B3)   # 10 pagamentos parciais
est = B.pop_por_oferta(B3, 0.20)["parcelado_4x"]
checar(est["taxa_observada"] == 1.0,
       "pagamento parcial conta como pagamento na PoP", str(est["taxa_observada"]))
bandit3 = B.carregar_bandit(B3)
checar(perto(bandit3.recompensa_acumulada[1] / 10, 0.5, tol=0.001),
       "mas a taxa de recuperação continua 0,5 — são grandezas diferentes",
       f"{bandit3.recompensa_acumulada[1] / 10}")

# --- e agora o ponto: a PoP passa a DISCRIMINAR as propostas
props = montar_propostas(12000.0)
aval = avaliar(props, Margem(3000.0, "informada"), [0.65] * 4, "modelo",
               pop_por_oferta=B.pop_por_oferta(EMP, 0.65))
pops_usadas = {p.pop for p in aval.propostas}
checar(len(pops_usadas) > 1, "com histórico, as propostas deixam de ter a mesma PoP",
       str(sorted(pops_usadas)))
checar(aval.pop_discrimina, "e o motor marca que está discriminando por probabilidade")
checar("renegociação" in aval.aviso and "modelo" in aval.aviso,
       "o aviso diz em quanto histórico a estimativa se apoia", aval.aviso[:90])
d30_prop = next(p for p in aval.propostas if p.oferta == "desconto_30pct")
checar(d30_prop.origem_pop == "bandit" and d30_prop.pop_observacoes == 20,
       "a proposta carrega origem e evidência para a tela mostrar",
       f"{d30_prop.origem_pop}, {d30_prop.pop_observacoes} obs")

# estado gravado antes do contador existir não pode quebrar nem mentir
antigo = B._bandit_para_json(B.carregar_bandit(EMP))
del antigo["n_pagamentos"]
recuperado = B._bandit_de_json(antigo)
checar(recuperado.n_pagamentos == [0] * B.N_ACOES,
       "estado antigo, sem o contador, volta zerado em vez de estourar")
checar(recuperado.n_tentativas == B.carregar_bandit(EMP).n_tentativas,
       "e o resto do estado antigo é preservado")


# ===========================================================================
# Formatação de moeda
# ===========================================================================
print("\n— Formatação —")

from model.proposta import _brl  # noqa: E402

checar(_brl(2000.0) == "R$ 2.000,00", "milhar com ponto, centavo com vírgula", _brl(2000.0))
checar(_brl(1234567.89) == "R$ 1.234.567,89", "mais de um separador de milhar", _brl(1234567.89))
checar(_brl(333.33) == "R$ 333,33", "sem milhar", _brl(333.33))

# O bug que só apareceu ao renderizar a tela: trocar os separadores com
# replace encadeado convertia o ponto final da frase em vírgula.
obs = avaliar(montar_propostas(12000.0, ARQ_1), Margem(400.0, "informada"),
              POP_1, origem_pop="ref")
frase = next(p.observacao for p in obs.propostas if p.cabe_no_bolso is False)
checar(frase.endswith("."), "a observação termina em ponto, não em vírgula", repr(frase[-28:]))
checar("R$ 2.000,00" in frase and "R$ 400,00" in frase,
       "e os valores continuam no formato brasileiro", frase)


# ===========================================================================
# O endpoint /predicoes/{cpf}/propostas
# ===========================================================================
print("\n— Endpoint —")

import os, types  # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


DESPESAS_NA_CARTEIRA = {"v": None}


class _Q:
    """Banco falso: "c-alfa" é do banco_alfa; "c-beta" é da credtotal."""
    def __init__(s, tbl): s.tbl, s.f = tbl, {}
    def select(s, *a, **k): s.cols = a[0] if a else ""; return s
    def eq(s, c, v): s.f[c] = v; return s
    def in_(s, c, v): s.f[c] = v; return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s

    # O código lê em páginas (range), então o stub precisa recortar de verdade:
    # devolver sempre tudo faria o laço de paginação nunca terminar.
    def range(s, ini, fim):
        s._corte = (ini, fim)
        return s

    def _pagina(s, linhas):
        ini, fim = getattr(s, "_corte", (None, None))
        return linhas if ini is None else linhas[ini:fim + 1]

    def execute(s):
        if s.tbl == "carteiras":
            dono = {"c-alfa": "banco_alfa", "c-beta": "credtotal"}
            return types.SimpleNamespace(
                data=s._pagina([{"id": k} for k, v in dono.items() if v == s.f.get("empresa_id")]))
        if s.tbl == "predicoes":
            carteiras_visiveis = s.f.get("carteira_id") or []
            if "c-alfa" not in carteiras_visiveis:
                return types.SimpleNamespace(data=s._pagina([]))
            linha = {
                "cpf": s.f.get("cpf"), "nome": "Devedor Teste",
                "valor_divida": 12000.0, "renda_estimada": 4500.0,
                "dias_em_atraso": 180, "score_recuperabilidade": 65.0,
                "probabilidade_pagamento": 0.65, "carteira_id": "c-alfa",
            }
            # Só devolve a coluna se a consulta a pediu, como o banco de verdade.
            if DESPESAS_NA_CARTEIRA["v"] is not None and "despesas_mensais" in getattr(s, "cols", ""):
                linha["despesas_mensais"] = DESPESAS_NA_CARTEIRA["v"]
            return types.SimpleNamespace(data=[linha])
        if s.tbl == "empresa_config":
            return types.SimpleNamespace(data=[{"extra": {}}])
        return types.SimpleNamespace(data=s._pagina([]))


main.get_db = lambda: types.SimpleNamespace(table=lambda t: _Q(t))
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}

from auth import criar_token  # noqa: E402
h = {"Authorization": "Bearer " + criar_token(
    {"sub": "u1", "email": "op@alfa.com", "nome": "Op", "role": "operador",
     "empresa_id": "banco_alfa"})}
c = TestClient(main.app)

r = c.get("/predicoes/11122233344/propostas", headers=h)
checar(r.status_code == 200, "responde 200 para devedor da própria empresa", str(r.status_code))
corpo = r.json() if r.status_code == 200 else {}
checar(len(corpo.get("propostas", [])) == 4, "devolve as quatro propostas",
       str(len(corpo.get("propostas", []))))
checar(corpo.get("margem", {}).get("origem") == "indisponivel",
       "sem despesas na carteira, margem vem como indisponível")
checar("não distingue as ofertas por probabilidade" in (corpo.get("aviso") or ""),
       "e avisa que a PoP é a mesma para todas as ofertas")

# operador informa as despesas na hora da ligação
r2 = c.get("/predicoes/11122233344/propostas?despesas_mensais=2500", headers=h)
corpo2 = r2.json()
checar(perto(corpo2["margem"]["valor"], 1400.0),
       "com despesas informadas, calcula a margem", f'R$ {corpo2["margem"]["valor"]}')
checar(corpo2["parcela_maxima"] == 1400.0, "e o teto da parcela sai da política")
reprovadas = [p for p in corpo2["propostas"] if p["cabe_no_bolso"] is False]
checar(len(reprovadas) >= 1, "reprova o que não cabe, em vez de esconder",
       f'{len(reprovadas)} reprovada(s)')
checar(corpo2["recomendada"] is not None
       and corpo2["recomendada"]["parcela"] <= 1400.0,
       "a recomendada cabe na margem",
       f'R$ {corpo2["recomendada"]["parcela"]}' if corpo2["recomendada"] else "nenhuma")

# escopo: CPF de carteira de OUTRA empresa não pode vazar
h_beta = {"Authorization": "Bearer " + criar_token(
    {"sub": "u2", "email": "op@beta.com", "nome": "Op", "role": "operador",
     "empresa_id": "credtotal"})}
r3 = c.get("/predicoes/11122233344/propostas", headers=h_beta)
checar(r3.status_code == 404, "devedor de outra empresa não vaza pelo endpoint",
       str(r3.status_code))

# despesas que vieram NA CARTEIRA (coluna despesas_mensais): a margem sai delas,
# sem o operador digitar nada. A rota não pedia essa coluna ao banco, então o
# caminho "a carteira pode trazer as despesas" nunca funcionou.
DESPESAS_NA_CARTEIRA["v"] = 2500.0
r4 = c.get("/predicoes/11122233344/propostas", headers=h)
corpo4 = r4.json()
checar(corpo4.get("margem", {}).get("origem") == "informada" and perto(corpo4["margem"]["valor"], 1400.0),
       "despesas da carteira alimentam a margem sem o operador digitar",
       str(corpo4.get("margem")))
DESPESAS_NA_CARTEIRA["v"] = None

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
