"""O1 — catálogo de ofertas da empresa, contas e alçada.

    python test_ofertas_catalogo.py
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
perto = lambda a, b, tol=0.01: abs(a - b) <= tol

print("— contas —")
c = O.calcular(10000, desconto_pct=20)
checar(c["valor_negociado"] == 8000 and c["total_pago"] == 8000 and c["economia"] == 2000, "à vista com desconto")
c = O.calcular(10000, desconto_pct=0, entrada_pct=10, n_parcelas=9, juros_mensal_pct=0)
checar(c["entrada"] == 1000 and c["parcela"] == 1000 and c["total_pago"] == 10000, "entrada + parcelas sem juros")
c = O.calcular(3000, n_parcelas=12, juros_mensal_pct=2)
checar(perto(c["parcela"], 283.68, 0.01) and perto(c["total_pago"], 3404.16, 0.1), "tabela Price: 3.000 em 12x a 2% = 283,68", str(c))
checar(c["juros_total"] > 0 and c["valor_negociado"] == 3000, "juros não mudam o valor negociado")
c = O.calcular(1000, n_parcelas=1, entrada_pct=50, juros_mensal_pct=5)
checar(c["entrada"] == 0 and c["total_pago"] == 1000, "à vista ignora entrada e juros")

print("— família —")
checar([O.familia(1, 10), O.familia(1, 15), O.familia(1, 16), O.familia(6, 0), O.familia(7, 0), O.familia(24, 5)] ==
       ["avista_10pct", "avista_10pct", "desconto_30pct", "parcelado_4x", "parcelado_12x", "parcelado_12x"], "regra das famílias")

print("— validação —")
cat = O.validar_catalogo([{"nome": "Feirão 40%", "desconto_pct": "40", "n_parcelas": 1},
                          {"nome": "Feirão 40%", "desconto_pct": 0, "n_parcelas": 10, "entrada_pct": 20, "juros_mensal_pct": "1,5"}])
checar(cat[0]["id"] == "feirao-40" and cat[1]["id"] == "feirao-40-2", "id a partir do nome, sem repetir")
checar(cat[0]["familia"] == "desconto_30pct" and cat[1]["familia"] == "parcelado_12x", "família automática")
checar(cat[1]["juros_mensal_pct"] == 1.5 and cat[0]["entrada_pct"] == 0, "aceita vírgula; à vista zera entrada")
for itens, msg in [([], "vazio"), ([{"nome": "x", "n_parcelas": 1}], "nome curto"),
                   ([{"nome": "Ok", "desconto_pct": 99}], "desconto acima de 95"),
                   ([{"nome": "Ok", "n_parcelas": 2.5}], "parcela quebrada"),
                   ([{"nome": "Ok", "juros_mensal_pct": 30, "n_parcelas": 3}], "juros acima de 20"),
                   ([{"nome": "Ok", "ativa": False}], "nenhuma ativa"),
                   ([{"nome": f"Oferta {i}"} for i in range(21)], "mais de 20")]:
    try:
        O.validar_catalogo(itens); checar(False, f"recusa {msg}")
    except ValueError:
        checar(True, f"recusa {msg}")
checar(O.validar_alcada({"desconto_max_pct": "30", "parcelas_max": 12, "parcela_min": "", "juros_min_pct": None}) ==
       {"desconto_max_pct": 30.0, "parcelas_max": 12}, "alçada: vazio = sem limite")
cond = O.condicoes({"desconto_pct": 40, "n_parcelas": 18, "juros_mensal_pct": 0.5})
conta = O.calcular(1000, **cond)
motivos = O.fora_da_alcada(cond, conta, {"desconto_max_pct": 30, "parcelas_max": 12, "parcela_min": 50, "juros_min_pct": 1})
checar(len(motivos) == 4, "fora da alçada: desconto, parcelas, parcela mínima e juros", " | ".join(motivos))
checar(O.fora_da_alcada(cond, conta, {}) == [], "sem alçada, sem bloqueio")
checar([o["id"] for o in O.catalogo_padrao()] == ["parcelado_4x", "parcelado_12x", "avista_10pct", "desconto_30pct"],
       "padrão = as 4 ofertas de sempre, com as famílias de sempre")
checar(O.catalogo_da_empresa({"catalogo_ofertas": [{"nome": "x"}]})[1] is True, "catálogo gravado inválido cai no padrão")

print("— rotas —")
EXTRA = {}
GRAVOU = []
main._extra_empresa = lambda e: EXTRA.get(e, {})
def gravar(db, empresa, novos, payload):
    antes = dict(EXTRA.get(empresa, {}))
    depois = dict(antes)
    for k, v in novos.items():
        depois.pop(k, None) if v is None else depois.__setitem__(k, v)
    EXTRA[empresa] = depois; GRAVOU.append(empresa)
    return antes, depois
main._gravar_extra = gravar
main._registrar_auditoria = lambda **k: None
main.get_db = lambda: None
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
cli = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u", "email": "a@x", "nome": "A", "role": role, "empresa_id": empresa})}
ADM, OP, CMD, OUTRA = jwt("goias"), jwt("goias", "operador"), jwt("", "comando"), jwt("beta")

r = cli.get("/empresa/ofertas", headers=OP).json()
checar(r["padrao"] is True and len(r["catalogo"]) == 4, "sem catálogo: operador lê as 4 padrão")
novo = [{"nome": "À vista 25%", "desconto_pct": 25, "n_parcelas": 1},
        {"nome": "Entrada + 10x", "desconto_pct": 5, "n_parcelas": 10, "entrada_pct": 20, "juros_mensal_pct": 1.99}]
checar(cli.put("/empresa/ofertas", json={"catalogo": novo}, headers=OP).status_code == 403, "operador não edita")
r = cli.put("/empresa/ofertas", json={"catalogo": novo, "alcada": {"desconto_max_pct": 30}}, headers=ADM)
checar(r.status_code == 200 and r.json()["padrao"] is False and len(r.json()["catalogo"]) == 2, "admin salva o catálogo", r.text[:100])
checar(r.json()["alcada"] == {"desconto_max_pct": 30.0}, "e a alçada")
checar(cli.get("/empresa/ofertas", headers=OUTRA).json()["padrao"] is True, "outra empresa continua no padrão")
r = cli.put("/empresa/ofertas", json={"catalogo": [{"nome": "Ok", "desconto_pct": 120}]}, headers=ADM)
checar(r.status_code == 422 and "Desconto" in r.json()["detail"], "valor inválido: 422 com o motivo", r.text[:100])
checar(cli.put("/empresa/ofertas", json={}, headers=ADM).status_code == 422, "nada para salvar: 422")
checar(cli.get("/empresa/ofertas", headers=CMD).status_code == 400, "comando escolhe a empresa")
checar(cli.get("/empresa/ofertas?empresa_id_alvo=goias", headers=CMD).json()["padrao"] is False, "comando lê a escolhida")
r = cli.put("/empresa/ofertas", json={"restaurar_padrao": True}, headers=ADM).json()
checar(r["padrao"] is True and r["alcada"] == {"desconto_max_pct": 30.0}, "restaurar padrão mantém a alçada")

print("— propostas usam o catálogo —")
EXTRA["goias"]["catalogo_ofertas"] = O.validar_catalogo(novo)
main._predicao_do_cpf = lambda db, cpf, emp, colunas=None: {
    "cpf": cpf, "nome": "Maria", "valor_divida": 10000, "renda_estimada": 5000, "despesas_mensais": 3000,
    "score_recuperabilidade": 50, "probabilidade_pagamento": 0.4, "carteira_id": "c1"}
main._politica_proposta = lambda e: None
r = cli.get("/predicoes/111/propostas", headers=OP)
j = r.json()
checar(r.status_code == 200 and [p["rotulo"] for p in j["propostas"]] == ["À vista 25%", "Entrada + 10x"],
       "a ficha mostra as ofertas da empresa", r.text[:150])
p2 = j["propostas"][1]
checar(p2["entrada"] == 1900.0 and p2["oferta"] == "parcelado_12x" and p2["id"] == "entrada-10x", "com entrada, família e id")
checar(perto(p2["parcela"], O.calcular(10000, 5, 20, 10, 1.99)["parcela"]), "parcela pela mesma conta do catálogo")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
