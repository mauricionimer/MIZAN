"""O3 — confirmar "fiz esta oferta": contato, Agenda e histórico.

    python test_ofertas_feitas.py
"""
import os, sys
from datetime import date, timedelta
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import agenda                                      # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

HOJE = date(2026, 10, 14)
agenda.hoje = lambda: HOJE
d = lambda n: (HOJE + timedelta(days=n)).isoformat()

TAB = {"contatos": [], "agenda": [], "ofertas_feitas": [], "recomendacoes": []}
MODO = {"sem_tabela": False}
PRED = {"id": "p1", "cpf": "111", "nome": "Maria Dias", "valor_divida": 10000, "renda_estimada": 5000,
        "despesas_mensais": 3000, "score_recuperabilidade": 40, "probabilidade_pagamento": 0.4, "carteira_id": "c1"}
main._predicao_do_cpf = lambda db, cpf, emp, colunas=None: dict(PRED) if cpf == "111" and emp in ("goias", "") else None
main._extra_empresa = lambda e: {"alcada_oferta": {"desconto_max_pct": 30}} if e == "goias" else {}
main._politica_proposta = lambda e: None
main._empresa_da_carteira = lambda db, cid: "goias"
import model.bandit as B
B.pop_por_oferta = lambda emp, pop, k=None: {}
APRENDEU = []
B.registrar_resultado = lambda **k: APRENDEU.append(k)

class R:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.ins = None; s.lim = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def insert(s, l): s.ins = l; return s
    def execute(s):
        if MODO["sem_tabela"] and s.t == "ofertas_feitas":
            raise Exception('relation "public.ofertas_feitas" does not exist')
        tab = TAB.setdefault(s.t, [])
        if s.ins is not None:
            novo = dict(s.ins, id=f"{s.t}-{len(tab) + 1}"); tab.append(novo); return R([novo])
        alvo = [dict(l) for l in tab if all(f(l) for f in s.f)]
        return R(alvo[:s.lim] if s.lim else alvo)

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="operador", sub="op-ana"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": "Ana", "role": role, "empresa_id": empresa})}
ANA, OUTRA, CMD = jwt("goias"), jwt("beta", sub="op-x"), jwt("", "comando", "cmd")
OF = {"cpf": "111", "desconto_pct": 10, "n_parcelas": 10, "entrada_pct": 20, "juros_mensal_pct": 0, "canal": "telefone", "base_id": "entrada-10x"}

print("— aceitou —")
r = c.post("/ofertas", json={**OF, "resposta": "aceitou", "data": d(5), "observacao": "Vai pagar no dia do salário"}, headers=ANA)
checar(r.status_code == 200, "registra a oferta aceita", r.text[:160])
j = r.json()
ct = TAB["contatos"][-1]
checar(ct["resultado"] == "prometeu_pagar" and ct["oferta"] == "parcelado_12x" and ct["desconto_oferecido_pct"] == 10,
       "vira contato 'Prometeu pagar' com a família e o desconto")
checar(ct["observacao"].startswith("Oferta: entrada R$ 1.800,00 + 10x de R$ 720,00, 10% de desconto."), "observação resume a oferta", ct["observacao"])
ag = TAB["agenda"][-1]
checar(ag["tipo"] == "promessa" and ag["data"] == d(5) and ag["valor"] == 1800.0 and ag["contato_id"] == ct["id"],
       "promessa na Agenda no valor do primeiro pagamento (a entrada)")
of = TAB["ofertas_feitas"][-1]
checar(of["resposta"] == "aceitou" and of["parcela"] == 720.0 and of["total_pago"] == 9000.0 and of["contato_id"] == ct["id"]
       and of["base_id"] == "entrada-10x" and of["predicao_id"] == "p1", "histórico guarda a oferta completa e o contato")
checar(of["veredito_geral"] in ("boa", "atencao", "ruim") and of["valor_esperado"] == 3600.0, "e a análise do momento (refeita no servidor)")
checar(APRENDEU and APRENDEU[-1]["recompensa"] == main._CONTATO_RECOMPENSA["prometeu_pagar"], "o bandit aprende com a família da oferta")

print("— vai pensar / recusou —")
r = c.post("/ofertas", json={**OF, "resposta": "vai_pensar", "data": d(2), "hora": "10:30", "canal": "whatsapp"}, headers=ANA)
checar(r.status_code == 200 and TAB["contatos"][-1]["resultado"] == "contactado" and TAB["agenda"][-1]["tipo"] == "retorno"
       and TAB["agenda"][-1]["hora"] == "10:30", "vai pensar: contato + retorno na Agenda")
antes = len(TAB["agenda"])
r = c.post("/ofertas", json={**OF, "resposta": "recusou", "n_parcelas": 1, "desconto_pct": 20}, headers=ANA)
checar(r.status_code == 200 and TAB["contatos"][-1]["resultado"] == "nao_quis" and len(TAB["agenda"]) == antes,
       "recusou: contato 'Não quis', sem agenda")
checar(TAB["ofertas_feitas"][-1].get("observacao") is None and "À vista R$ 8.000,00" in TAB["contatos"][-1]["observacao"], "à vista resumido")

print("— recusas —")
checar(c.post("/ofertas", json={**OF, "resposta": "aceitou"}, headers=ANA).status_code == 422, "aceitou sem data: 422")
checar(c.post("/ofertas", json={**OF, "resposta": "vai_pensar", "data": d(-1)}, headers=ANA).status_code == 422, "data no passado: 422")
r = c.post("/ofertas", json={**OF, "resposta": "recusou", "desconto_pct": 50}, headers=ANA)
checar(r.status_code == 422 and "alçada" in r.json()["detail"], "fora da alçada: 422 (o servidor confere de novo)", r.text[:100])
checar(c.post("/ofertas", json={**OF, "resposta": "talvez"}, headers=ANA).status_code == 422, "resposta inválida")
checar(c.post("/ofertas", json={**OF, "resposta": "recusou", "canal": "fax"}, headers=ANA).status_code == 422, "canal inválido")
checar(c.post("/ofertas", json={**OF, "resposta": "recusou"}, headers=CMD).status_code == 403, "comando não registra oferta")
checar(c.post("/ofertas", json={**OF, "resposta": "recusou"}, headers=OUTRA).status_code == 404, "outra empresa: devedor não encontrado")

print("— histórico —")
r = c.get("/ofertas?cpf=111", headers=ANA).json()
checar(r["ativo"] and len(r["itens"]) == 3, "lista as ofertas do devedor")
checar(c.get("/ofertas?cpf=111", headers=OUTRA).json()["itens"] == [], "outra empresa não vê")
checar(len(c.get("/ofertas?cpf=111&empresa_id=goias", headers=CMD).json()["itens"]) == 3, "comando lê a empresa escolhida")

print("— SQL ainda não rodado —")
MODO["sem_tabela"] = True
n_cont = len(TAB["contatos"])
r = c.post("/ofertas", json={**OF, "resposta": "recusou"}, headers=ANA)
checar(r.status_code == 200 and len(TAB["contatos"]) == n_cont + 1 and "migracao_ofertas" in r.json()["oferta_erro"],
       "o contato é gravado e o histórico avisa que falta o SQL")
checar(c.get("/ofertas?cpf=111", headers=ANA).json()["ativo"] is False, "histórico avisa, sem 500")
MODO["sem_tabela"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
