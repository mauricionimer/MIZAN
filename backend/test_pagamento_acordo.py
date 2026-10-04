"""Pagamento ligado à carteira escolhida na busca, com as condições do acordo.

    python test_pagamento_acordo.py
"""
import os, sys, re
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CARTEIRAS = [{"id": "c-g1", "empresa_id": "goias", "nome_arquivo": "jan.csv", "created_at": "2026-01-01"},
             {"id": "c-g2", "empresa_id": "goias", "nome_arquivo": "fev.csv", "created_at": "2026-02-01"},
             {"id": "c-b",  "empresa_id": "beta",  "nome_arquivo": "b.csv",   "created_at": "2026-03-01"}]
PREDICOES = [
    {"id": "p1", "carteira_id": "c-g1", "cpf": "11111111111", "nome": "Maria Dias", "created_at": "2026-01-01"},
    {"id": "p2", "carteira_id": "c-g2", "cpf": "11111111111", "nome": "Maria Dias", "created_at": "2026-02-01"},
    {"id": "p3", "carteira_id": "c-g2", "cpf": "22222222222", "nome": "João Souza", "created_at": "2026-02-01"},
    {"id": "pb", "carteira_id": "c-b",  "cpf": "11111111111", "nome": "Maria Dias", "created_at": "2026-03-01"},
]
FEEDBACKS = []
MODO = {"sem_colunas": False}

class Q:
    def __init__(s, t):
        s.t = t; s.ins = None; s.lim = None
        s.linhas = list({"predicoes": PREDICOES, "carteiras": CARTEIRAS}.get(t, []))
    def select(s, *a, **k): return s
    def eq(s, c, v): s.linhas = [l for l in s.linhas if l.get(c) == v]; return s
    def in_(s, c, vs): vs = set(vs); s.linhas = [l for l in s.linhas if l.get(c) in vs]; return s
    def or_(s, expr):
        conds = [re.match(r"(\w+)\.ilike\.\*(.*)\*", p).groups() for p in expr.split(",")]
        s.linhas = [l for l in s.linhas if any(v.lower() in str(l.get(c, "")).lower() for c, v in conds)]
        return s
    def order(s, col, desc=False): s.linhas.sort(key=lambda l: l.get(col) or "", reverse=desc); return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.linhas = s.linhas[i:f + 1]; return s
    def insert(s, linha): s.ins = dict(linha, id=f"f{len(FEEDBACKS) + 1}"); return s
    def execute(s):
        if s.ins is not None:
            if MODO["sem_colunas"] and any(k in s.ins for k in main._COLUNAS_ACORDO):
                raise Exception("Could not find the 'forma_pagamento' column of 'feedbacks'")
            FEEDBACKS.append(s.ins); return type("R", (), {"data": [s.ins]})()
        d = s.linhas[:s.lim] if s.lim is not None else s.linhas
        return type("R", (), {"data": d})()

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._fechar_loop_bandit = lambda *a, **k: None
main._writeback_pagamento = lambda *a, **k: None
main._registrar_auditoria = lambda *a, **k: None
main.buscar_usuario_por_id = lambda uid: {"id": uid, "ativo": True}
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "a@x.com", "nome": "A", "role": role, "empresa_id": empresa})}
G, B, CMD = jwt("goias"), jwt("beta"), jwt("", "comando")
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)

print("— busca —")
r = c.get("/devedores/buscar?q=maria", headers=G).json()["itens"]
checar([x["id"] for x in r] == ["p2", "p1"], "admin acha pelo nome, só nas carteiras dele, a mais recente primeiro", str([x["id"] for x in r]))
checar(r[0]["carteira_nome"] == "fev.csv", "e cada item diz de que carteira é")
r = c.get("/devedores/buscar?q=222.222", headers=G).json()["itens"]
checar([x["id"] for x in r] == ["p3"], "acha pelo CPF com pontuação")
checar(c.get("/devedores/buscar?q=m", headers=G).json()["itens"] == [], "texto curto demais não busca")
checar(c.get("/devedores/buscar?q=maria", headers=CMD).status_code == 400, "comando sem empresa: 400")
r = c.get("/devedores/buscar?q=maria&empresa_id_alvo=beta", headers=CMD).json()["itens"]
checar([x["id"] for x in r] == ["pb"], "comando busca na empresa escolhida")
checar(c.get("/devedores/buscar?q=maria", headers=jwt("goias", "operador")).status_code == 403, "operador não busca")
r = c.get("/devedores/buscar?q=ma*ria,x", headers=G)
checar(r.status_code == 200, "caracteres de filtro são limpos, sem erro")

print("\n— pagamento ligado à carteira escolhida —")
acordo = {"forma_pagamento": "pix", "parcelas": 6, "com_juros": True, "taxa_juros_mensal": 1.99, "desconto_pct": 15}
r = c.post("/feedback", headers=G, json={"cpf": "11111111111", "pagou": True, "valor_recuperado": 300,
                                          "predicao_id": "p1", **acordo})
checar(r.status_code == 200 and r.json()["predicao_id"] == "p1", "liga à carteira escolhida (a de janeiro), não à mais recente", str(r.json()))
f = FEEDBACKS[-1]
checar(all(f.get(k) == v for k, v in acordo.items()), "grava forma, parcelas, juros, taxa e desconto", str({k: f.get(k) for k in acordo}))

r = c.post("/feedback", headers=G, json={"cpf": "11111111111", "pagou": True, "predicao_id": "pb"})
checar(r.json()["predicao_id"] == "p2", "carteira de OUTRA empresa é ignorada: cai na mais recente da própria", str(r.json().get("predicao_id")))
r = c.post("/feedback", headers=G, json={"cpf": "22222222222", "pagou": True, "predicao_id": "p1"})
checar(r.json()["predicao_id"] == "p3", "predição de outro CPF é ignorada", str(r.json().get("predicao_id")))

r = c.post("/feedback", headers=G, json={"cpf": "22222222222", "pagou": True, "parcelas": 3, "com_juros": False, "taxa_juros_mensal": 5})
checar("taxa_juros_mensal" not in FEEDBACKS[-1], "sem juros, a taxa não é gravada")
r = c.post("/feedback", headers=G, json={"cpf": "22222222222", "pagou": False, **acordo})
checar(not any(k in FEEDBACKS[-1] for k in main._COLUNAS_ACORDO), "não pagou: nenhuma condição de acordo é gravada")

checar(c.post("/feedback", headers=G, json={"cpf": "2", "pagou": True, "forma_pagamento": "cheque"}).status_code == 422, "forma de pagamento desconhecida: 422")
checar(c.post("/feedback", headers=G, json={"cpf": "2", "pagou": True, "parcelas": 0}).status_code == 422, "parcelas fora de 1–120: 422")

print("\n— banco sem as colunas novas —")
MODO["sem_colunas"] = True; n = len(FEEDBACKS)
r = c.post("/feedback", headers=G, json={"cpf": "22222222222", "pagou": True, **acordo})
checar(r.status_code == 200 and len(FEEDBACKS) == n + 1 and "forma_pagamento" not in FEEDBACKS[-1],
       "o pagamento é gravado sem as condições, em vez de se perder", str(r.status_code))

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
