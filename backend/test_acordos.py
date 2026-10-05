"""A4 — acordos em andamento.

    python test_acordos.py
"""
import os, sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import agenda, acordos                             # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

HOJE = date(2026, 10, 14)
agenda.hoje = lambda: HOJE

print("— regras —")
checar(acordos.vencimentos(date(2026, 1, 31), 4) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)],
       "mensal no mesmo dia; 31 vira o fim do mês curto")
checar(acordos.vencimentos(date(2026, 11, 10), 3)[-1] == date(2027, 1, 10), "vira o ano")
P = lambda venc, sit="pendente", v=100: {"vencimento": venc, "situacao": sit, "valor": v}
st = acordos.situacao([P(HOJE - timedelta(days=60), "paga"), P(HOJE + timedelta(days=5)), P(HOJE + timedelta(days=35))], HOJE)
checar(st["situacao"] == "em_dia" and st["pagas"] == 1 and st["valor_aberto"] == 200 and st["proximo_vencimento"] == (HOJE + timedelta(days=5)).isoformat(), "em dia")
st = acordos.situacao([P(HOJE - timedelta(days=40), "paga"), P(HOJE - timedelta(days=10)), P(HOJE + timedelta(days=20))], HOJE)
checar(st["situacao"] == "atrasado" and st["dias_atraso"] == 10 and st["valor_vencido"] == 100, "atrasado até 30 dias")
st = acordos.situacao([P(HOJE - timedelta(days=70), "paga"), P(HOJE - timedelta(days=31)), P(HOJE - timedelta(days=1))], HOJE)
checar(st["situacao"] == "quebrado" and st["valor_vencido"] == 200, "pagou a 1ª e parou: quebrado depois de 30 dias")
st = acordos.situacao([P(HOJE - timedelta(days=30)), P(HOJE)], HOJE)
checar(st["situacao"] == "atrasado", "exatamente 30 dias ainda é atrasado")
checar(acordos.situacao([P(HOJE, "paga"), P(HOJE, "paga")], HOJE)["situacao"] == "quitado", "quitado")

TAB = {"acordo_parcelas": [], "predicoes": [{"id": "p1", "nome": "Maria Dias", "responsavel_nome": "Ana"}]}
MODO = {"sem_tabela": False}

class R:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.ins = None; s.patch = None; s.lim = None; s.rng = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def gte(s, c, v): s.f.append(lambda l: str(l.get(c) or "") >= v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, l): s.ins = l; return s
    def update(s, p): s.patch = p; return s
    def execute(s):
        if MODO["sem_tabela"] and s.t == "acordo_parcelas":
            raise Exception('relation "public.acordo_parcelas" does not exist')
        tab = TAB.setdefault(s.t, [])
        if s.ins is not None:
            novos = [dict(x, id=f"q{len(tab) + i + 1}") for i, x in enumerate(s.ins if isinstance(s.ins, list) else [s.ins])]
            tab.extend(novos); return R(novos)
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        if s.patch is not None:
            for l in alvo: l.update(s.patch)
            return R([dict(l) for l in alvo])
        if s.rng: alvo = alvo[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: alvo = alvo[:s.lim]
        return R([dict(l) for l in alvo])

DB = type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.get_db = lambda: DB
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": "Adm", "role": role, "empresa_id": empresa})}
ADM, OP, CMD, OUTRA = jwt("goias"), jwt("goias", "operador", "op"), jwt("", "comando", "cmd"), jwt("beta")

print("— abrir acordo —")
main._abrir_acordo(DB, "goias", "111", "fb-1", {"id": "p1", "carteira_id": "c1"}, 4, 250.0, HOJE - timedelta(days=45), "Ana")
ps = sorted([p for p in TAB["acordo_parcelas"] if p["feedback_id"] == "fb-1"], key=lambda p: p["numero"])
checar(len(ps) == 4 and [p["situacao"] for p in ps] == ["paga", "pendente", "pendente", "pendente"], "4 parcelas, a 1ª paga")
checar(ps[0]["nome"] == "Maria Dias" and all(p["valor"] == 250.0 and p["total"] == 4 for p in ps), "busca o nome; mesmo valor em todas")
checar(ps[1]["vencimento"] == acordos.somar_meses(HOJE - timedelta(days=45), 1).isoformat(), "2ª vence um mês depois")
main._abrir_acordo(DB, "goias", "222", "fb-2", None, 1, 100.0, None, "Ana")
checar(not any(p["feedback_id"] == "fb-2" for p in TAB["acordo_parcelas"]), "à vista não abre acordo")
main._abrir_acordo(DB, "goias", "333", "fb-3", None, 3, 90.0, HOJE - timedelta(days=100), "Ana")    # vai quebrar
main._abrir_acordo(DB, "goias", "444", "fb-4", None, 2, 50.0, HOJE - timedelta(days=5), "Ana")      # em dia
main._abrir_acordo(DB, "beta", "555", "fb-5", None, 2, 999.0, HOJE, "X")
main._abrir_acordo(DB, "goias", "777", "fb-7", None, 2, 60.0, acordos.somar_meses(HOJE, -1) + timedelta(days=3), "Ana")  # vence em 3 dias
fonte = open(AQUI / "main.py", encoding="utf-8").read()
checar("_abrir_acordo(db, empresa_nome, payload.cpf, feedback_id" in fonte, "o registro em Pagamentos abre o acordo quando parcelado")

print("— listar —")
r = c.get("/acordos", headers=ADM)
checar(r.status_code == 200, "admin lista", r.text[:120])
j = r.json()
sit = {a["id"]: a["situacao"] for a in j["acordos"]}
checar(sit == {"fb-1": "atrasado", "fb-3": "quebrado", "fb-4": "em_dia", "fb-7": "em_dia"}, "situação de cada acordo (outra empresa fora)", str(sit))
checar([a["id"] for a in j["acordos"]][0] == "fb-3", "quebrados primeiro")
a1 = next(a for a in j["acordos"] if a["id"] == "fb-1")
checar(a1["responsavel_nome"] == "Ana" and len(a1["parcelas"]) == 4 and a1["valor_aberto"] == 750, "acordo traz responsável, parcelas e aberto")
res = j["resumo"]
checar(res["quebrado"] == 1 and res["atrasado"] == 1 and res["em_dia"] == 2, "resumo por situação")
checar(res["quebrado_valor"] == 180.0, "valor quebrado = parcelas vencidas", str(res["quebrado_valor"]))
checar(res["a_vencer_7d"] == 1 and res["a_vencer_7d_valor"] == 60.0, "a vencer em 7 dias: só a parcela que vence em 3 dias", str(res["a_vencer_7d"]))
checar([a["id"] for a in c.get("/acordos?situacao=quebrado", headers=ADM).json()["acordos"]] == ["fb-3"], "filtro por situação")
checar(c.get("/acordos?situacao=x", headers=ADM).status_code == 422, "situação inválida: 422")
checar(c.get("/acordos", headers=OP).status_code == 403, "operador não acessa")
checar(c.get("/acordos?empresa_id=beta", headers=CMD).json()["resumo"]["acordos"] == 1, "comando lê a empresa escolhida")

print("— baixar parcela —")
p2 = ps[1]["id"]
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=OP).status_code == 403, "operador não baixa")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=CMD).status_code == 403, "comando não baixa")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=OUTRA).status_code == 404, "outra empresa: 404")
r = c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=ADM)
checar(r.status_code == 200 and r.json()["parcela"]["situacao"] == "paga", "admin baixa a parcela")
checar(AUD and AUD[-1]["acao"] == "parcela_paga", "fica na auditoria")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=ADM).status_code == 409, "paga de novo: 409")
checar(next(a for a in c.get("/acordos", headers=ADM).json()["acordos"] if a["id"] == "fb-1")["pagas"] == 2, "o acordo conta a parcela")
checar(c.patch(f"/acordos/parcelas/{ps[0]['id']}", json={"acao": "desfazer"}, headers=ADM).status_code == 409,
       "a 1ª parcela não se desfaz aqui (é o pagamento de Pagamentos)")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "desfazer"}, headers=ADM).json()["parcela"]["situacao"] == "pendente", "desfazer")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "x"}, headers=ADM).status_code == 422, "ação inválida")

print("— parcela soma no painel —")
TAB["feedbacks"] = []; TAB["contatos"] = []; TAB["agenda"] = []
main._extra_empresa = lambda e: {}
for p in TAB["acordo_parcelas"]:
    if p["feedback_id"] == "fb-1" and p["numero"] == 2:
        p.update(situacao="paga", pago_em=datetime.combine(HOJE, time(15), tzinfo=agenda.FUSO).astimezone(timezone.utc).isoformat())
TAB["predicoes"][0]["responsavel_id"] = "op"
r = c.get("/painel/operador?periodo=hoje", headers=OP).json()
checar(r["recebido"] == 250.0 and r["pagamentos"] == 1, "a 2ª parcela baixada hoje entra no recebido do responsável", str(r.get("recebido")))

print("— SQL ainda não rodado —")
MODO["sem_tabela"] = True
checar(c.get("/acordos", headers=ADM).json()["ativo"] is False, "lista avisa, sem 500")
main._abrir_acordo(DB, "goias", "666", "fb-6", None, 3, 10.0, HOJE, "A")
checar(True, "abrir acordo sem a tabela não derruba o pagamento")
checar(c.patch(f"/acordos/parcelas/{p2}", json={"acao": "pagar"}, headers=ADM).status_code == 409, "baixar: 409 com o aviso")
checar(c.get("/painel/operador?periodo=hoje", headers=OP).status_code == 200, "o painel segue sem a tabela")
MODO["sem_tabela"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
