"""O2 — simulador "Fazer oferta": análise para quem paga e para o banco.

    python test_simulador_oferta.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
from model import oferta as O                      # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

print("— regras da análise —")
base = dict(teto_parcela=500.0, sobra_mes=1000.0, pop=0.4, origem_pop="modelo", melhor_ev=4000.0, melhor_rotulo="12x")
a = O.analisar(12000, O.condicoes({"n_parcelas": 20}), **base)          # parcela 600 > 500
checar(a["devedor"]["veredito"] == "ruim" and "acima" in a["devedor"]["motivos"][0], "parcela acima do teto: ruim para quem paga")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24}), **base)          # parcela 416,67
checar(a["devedor"]["veredito"] == "boa", "parcela dentro do teto: boa")
checar(a["banco"]["valor_esperado"] == 4000.0 and a["banco"]["veredito"] == "boa", "valor esperado = negociado × chance; igual à melhor: boa")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24, "entrada_pct": 20}), **base)   # entrada 2.000 > sobra 1.000
checar(a["devedor"]["veredito"] == "atencao" and any("entrada" in m for m in a["devedor"]["motivos"]), "entrada maior que a sobra do mês: atenção")
a = O.analisar(10000, O.condicoes({"n_parcelas": 1, "desconto_pct": 50}), **base)   # à vista 5.000 > sobra
checar(a["devedor"]["veredito"] == "atencao", "à vista maior que a sobra: depende de reserva")
a = O.analisar(10000, O.condicoes({"n_parcelas": 1, "desconto_pct": 95}), **base)   # à vista 500 ≤ sobra
checar(a["devedor"]["veredito"] == "boa", "à vista que cabe na sobra de um mês: boa")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24}), **{**base, "teto_parcela": None, "sobra_mes": None})
checar(a["devedor"]["veredito"] == "atencao" and "despesas" in a["devedor"]["motivos"][0], "sem margem: não verificável")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24, "desconto_pct": 10}), **base)  # EV 3.600 = 90%
checar(a["banco"]["veredito"] == "atencao" and a["banco"]["razao_melhor"] == 0.9, "90% da melhor: atenção")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24, "desconto_pct": 30}), **base)  # 70%
checar(a["banco"]["veredito"] == "ruim", "70% da melhor: ruim")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24}), **{**base, "valor_venda": 5000.0})
checar(a["banco"]["veredito"] == "ruim" and "venda" in a["banco"]["motivos"][0], "abaixo do valor de venda da dívida: ruim")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24, "juros_mensal_pct": 2}), **base)
checar(a["banco"]["valor_esperado"] == 4000.0 and any("juros" in m for m in a["banco"]["motivos"]), "juros não sobem o valor esperado")
a = O.analisar(10000, O.condicoes({"n_parcelas": 24, "desconto_pct": 40}), **{**base, "alcada": {"desconto_max_pct": 30}})
checar(a["pode_confirmar"] is False and a["geral"] == "ruim" and a["fora_da_alcada"], "fora da alçada: não pode confirmar")
checar(O.analisar(10000, O.condicoes({"n_parcelas": 24}), **base)["geral"] == "boa", "as duas boas: geral boa")

print("— rota —")
PRED = {"cpf": "111", "nome": "Maria Dias", "valor_divida": 10000, "renda_estimada": 5000, "despesas_mensais": 3000,
        "score_recuperabilidade": 40, "probabilidade_pagamento": 0.4, "carteira_id": "c1"}
main._predicao_do_cpf = lambda db, cpf, emp, colunas=None: dict(PRED) if cpf == "111" and emp in ("goias", "") else None
EXTRA = {"goias": {"alcada_oferta": {"desconto_max_pct": 30}, "cessao_pct": 10}}
main._extra_empresa = lambda e: EXTRA.get(e, {})
main._empresa_da_carteira = lambda db, cid: "goias"
main._politica_proposta = lambda e: None
import model.bandit as B
B.pop_por_oferta = lambda emp, pop, k=None: {"parcelado_12x": {"pop": 0.5, "origem": "bandit", "n_tentativas": 40}}
main.get_db = lambda: None
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="operador"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u", "email": "a@x", "nome": "A", "role": role, "empresa_id": empresa})}
OP, OUTRA, CMD = jwt("goias"), jwt("beta"), jwt("", "comando")

r = c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 12, "desconto_pct": 0}, headers=OP)
j = r.json()
checar(r.status_code == 200, "operador simula", r.text[:150])
checar(j["familia"] == "parcelado_12x" and j["banco"]["chance_pagar"] == 0.5 and j["banco"]["origem_chance"] == "bandit"
       and j["banco"]["observacoes_chance"] == 40, "chance de pagar vem da família da oferta (histórico real)")
checar(j["devedor"]["sobra_mes"] is not None and j["devedor"]["parcela_maxima"] is not None, "usa a margem livre do devedor")
checar(j["banco"]["valor_venda"] == 1000.0, "valor de venda vem da Premissa de cessão (10% da dívida)")
checar(j["alcada"] == {"desconto_max_pct": 30.0}, "devolve a alçada da empresa")
r = c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 12, "desconto_pct": 50}, headers=OP).json()
checar(r["pode_confirmar"] is False and "Desconto acima" in r["fora_da_alcada"][0], "desconto acima da alçada bloqueia")
r = c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 3, "despesas_mensais": 4900}, headers=OP).json()
checar(r["devedor"]["veredito"] == "ruim", "despesas informadas na hora mudam a margem (sobra quase nada)")
checar(c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 200}, headers=OP).status_code == 422, "parcelas fora do limite: 422")
checar(c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 3}, headers=OUTRA).status_code == 404, "outra empresa: 404")
r = c.post("/predicoes/111/simular-oferta", json={"n_parcelas": 3}, headers=CMD)
checar(r.status_code == 200 and r.json()["alcada"] == {"desconto_max_pct": 30.0}, "comando usa o catálogo/alçada da empresa da carteira")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
