"""A1 — painel de resultados do admin.

    python test_resultados_admin.py
"""
import os, sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import agenda, resultados as R                     # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

HOJE = date(2026, 10, 14)
agenda.hoje = lambda: HOJE
def em(dias):
    return datetime.combine(HOJE - timedelta(days=dias), time(12), tzinfo=agenda.FUSO).astimezone(timezone.utc).isoformat()

print("— regras —")
checar([R.faixa_desconto(v) for v in (None, 0, 5, 10, 15, 30, 31, "x")] ==
       ["nao_informado", "sem_desconto", "ate_10", "ate_10", "10_20", "20_30", "acima_30", "nao_informado"], "faixas de desconto")
checar([R.modalidade(v) for v in (None, 1, 2, 12)] == ["nao_informado", "a_vista", "parcelado", "parcelado"], "à vista × parcelado")
g = R.agrupar([{"pagou": True, "valor_recuperado": 100, "canal_cobranca": "whatsapp"},
               {"pagou": False, "canal_cobranca": "whatsapp"},
               {"pagou": True, "valor_recuperado": 50}], lambda f: f.get("canal_cobranca"), com_taxa=True)
checar([(x["chave"], x["registros"], x["pagos"], x["taxa_pagamento"]) for x in g] ==
       [("whatsapp", 2, 1, 0.5), ("nao_informado", 1, 1, 1.0)], "taxa por grupo; sem canal vai para Não informado, por último")
g = R.agrupar([{"pagou": True, "valor_recuperado": 100, "parcelas": 1}, {"pagou": False, "parcelas": None}],
              lambda f: R.modalidade(f.get("parcelas")), com_taxa=False)
checar(len(g) == 1 and "taxa_pagamento" not in g[0] and "registros" not in g[0],
       "corte só de composição: não pagos ficam fora e não há taxa")
grandes = [{"chave": "a", "taxa_pagamento": 0.9, "registros": 5, "amostra_pequena": True},
           {"chave": "b", "taxa_pagamento": 0.4, "registros": 50, "amostra_pequena": False},
           {"chave": "nao_informado", "taxa_pagamento": 0.95, "registros": 90, "amostra_pequena": False}]
checar(R.melhor(grandes)["chave"] == "b", "o 'melhor' ignora amostra pequena e Não informado")

# 40 registros por WhatsApp (16 pagos), 35 por telefone (7 pagos), 5 por SMS (5 pagos)
FBS = []
def fb(i, canal, pagou, valor=0, dias=1, pred=None, empresa="goias", **cond):
    FBS.append({"id": f"f{i}", "empresa": empresa, "pagou": pagou, "valor_recuperado": valor,
                "canal_cobranca": canal, "predicao_id": pred, "created_at": em(dias), **cond})
n = 0
for k in range(40):
    n += 1; fb(n, "whatsapp", k < 16, 100 if k < 16 else 0, pred="p-curto", parcelas=1 if k < 16 else None, desconto_pct=10 if k < 16 else None)
for k in range(35):
    n += 1; fb(n, "telefone", k < 7, 300 if k < 7 else 0, pred="p-longo", parcelas=6 if k < 7 else None, desconto_pct=0 if k < 7 else None)
for k in range(5):
    n += 1; fb(n, "sms", True, 50)
n += 1; fb(n, "whatsapp", True, 9999, empresa="beta")
n += 1; fb(n, "whatsapp", True, 7777, dias=200)
PRED = [{"id": "p-curto", "dias_em_atraso": 20}, {"id": "p-longo", "dias_em_atraso": 400}]
CONT = [{"empresa_id": "goias", "canal": "whatsapp", "resultado": r, "created_at": em(2)}
        for r in ["contactado"] * 20 + ["sem_resposta"] * 15 + ["prometeu_pagar"] * 5] + \
       [{"empresa_id": "goias", "canal": "telefone", "resultado": "contactado", "created_at": em(2)}] + \
       [{"empresa_id": "beta", "canal": "telefone", "resultado": "contactado", "created_at": em(2)}]
MODO = {"sem_colunas": False}

class Rr:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.rng = None; s.cols = ""
    def select(s, cols="*", **k): s.cols = cols; return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def gte(s, c, v): s.f.append(lambda l: str(l.get(c) or "") >= v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def order(s, *a, **k): return s
    def range(s, i, f): s.rng = (i, f); return s
    def execute(s):
        if MODO["sem_colunas"] and s.t == "feedbacks" and "canal_cobranca" in s.cols:
            raise Exception("column feedbacks.canal_cobranca does not exist")
        base = {"feedbacks": FBS, "predicoes": PRED, "contatos": CONT}.get(s.t, [])
        d = [dict(l) for l in base if all(f(l) for f in s.f)]
        if MODO["sem_colunas"] and s.t == "feedbacks":
            for l in d:
                for c in main._COLUNAS_ACORDO: l.pop(c, None)
        if s.rng: d = d[s.rng[0]:s.rng[1] + 1]
        return Rr(d)

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ADM, OP, CMD = jwt("goias"), jwt("goias", "operador", "op"), jwt("", "comando", "cmd")

print("— rota —")
r = c.get("/resultados?periodo=90d", headers=ADM)
checar(r.status_code == 200, "admin lê", r.text[:120])
j = r.json()
t = j["totais"]
checar((t["registros"], t["pagos"], t["recuperado"]) == (80, 28, 16 * 100 + 7 * 300 + 5 * 50),
       "totais só da empresa e do período", str(t))
canal = {g["chave"]: g for g in j["por_canal"]}
checar(canal["whatsapp"]["taxa_pagamento"] == 0.4 and canal["telefone"]["taxa_pagamento"] == 0.2, "taxa por canal")
checar(canal["sms"]["amostra_pequena"] and not canal["whatsapp"]["amostra_pequena"], "SMS com 5 registros: amostra pequena")
checar(j["melhor_canal"]["chave"] == "whatsapp", "melhor canal ignora o SMS (100%, mas 5 registros)")
fase = {g["chave"]: g for g in j["por_fase"]}
checar(fase["0-30 dias"]["registros"] == 40 and fase["181+ dias"]["registros"] == 35 and fase["nao_informado"]["registros"] == 5,
       "fase vem do atraso da predição ligada; sem predição, Não informado")
checar([g["chave"] for g in j["por_fase"]][-1] == "nao_informado", "Não informado por último")
mod = {g["chave"]: g for g in j["por_modalidade"]}
checar(mod["a_vista"]["pagos"] == 16 and mod["parcelado"]["pagos"] == 7 and mod["nao_informado"]["pagos"] == 5,
       "à vista × parcelado conta só pagamentos")
checar(mod["parcelado"]["ticket_medio"] == 300.0, "ticket médio")
desc = {g["chave"]: g["pagos"] for g in j["por_desconto"]}
checar(desc == {"sem_desconto": 7, "ate_10": 16, "nao_informado": 5}, "faixas de desconto", str(desc))
cc = {g["chave"]: g for g in j["contatos_por_canal"]}
checar(cc["whatsapp"]["contatos"] == 40 and cc["whatsapp"]["taxa_efetivo"] == round(25 / 40, 4)
       and cc["whatsapp"]["taxa_promessa"] == 0.125 and cc["telefone"]["contatos"] == 1, "contatos por canal (outra empresa fora)")
r = c.get("/resultados?periodo=tudo", headers=ADM).json()
checar(r["totais"]["registros"] == 81, "'tudo' inclui o registro antigo")
checar(c.get("/resultados?periodo=7d", headers=ADM).status_code == 422, "período inválido: 422")
checar(c.get("/resultados", headers=OP).status_code == 403, "operador não acessa")
checar(c.get("/resultados", headers=CMD).status_code == 400, "comando escolhe a empresa")
checar(c.get("/resultados?empresa_id=beta&periodo=90d", headers=CMD).json()["totais"]["recuperado"] == 9999, "comando lê a escolhida")

print("— banco sem as colunas do acordo —")
MODO["sem_colunas"] = True
r = c.get("/resultados?periodo=90d", headers=ADM)
j = r.json()
checar(r.status_code == 200 and j["condicoes_ativas"] is False, "responde e avisa")
checar([g["chave"] for g in j["por_canal"]] == ["nao_informado"] and j["totais"]["registros"] == 80,
       "tudo vai para Não informado, sem perder os totais")
MODO["sem_colunas"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
