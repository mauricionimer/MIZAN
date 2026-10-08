"""Painel do COMANDO: a mesma base analisada duas vezes não conta em dobro.

    python test_comando_unicos.py
"""
import os, sys
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

TAB = {}
FALHA_PREDICOES = {"ativo": False}

class R:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.ini = 0; s.fim = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def neq(s, c, v): s.f.append(lambda l: l.get(c) != v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def order(s, *a, **k): return s
    def range(s, a, b): s.ini, s.fim = a, b; return s
    def execute(s):
        if s.t == "predicoes" and FALHA_PREDICOES["ativo"]:
            raise RuntimeError("sem acesso")
        linhas = [dict(l) for l in TAB.get(s.t, []) if all(f(l) for f in s.f)]
        return R(linhas[s.ini:(s.fim + 1) if s.fim is not None else None])

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
CMD = {"Authorization": "Bearer " + criar_token(
    {"sub": "cmd", "email": "c@m", "nome": "cmd", "role": "comando", "empresa_id": ""})}

def pred(i, cart, cpf, divida, esperado, score):
    return {"id": i, "carteira_id": cart, "cpf": cpf, "valor_divida": divida,
            "valor_esperado_recuperacao": esperado, "score_recuperabilidade": score}

TAB["carteiras"] = [
    # A mesma base de 3 devedores analisada duas vezes (c2 é a mais recente)...
    {"id": "c1", "empresa_id": "goias", "total_devedores": 3, "valor_face": 600, "valor_esperado": 300, "score_medio": 50, "created_at": "2026-10-01T10:00:00Z"},
    {"id": "c2", "empresa_id": "goias", "total_devedores": 3, "valor_face": 660, "valor_esperado": 330, "score_medio": 60, "created_at": "2026-10-05T10:00:00Z"},
    # ...e uma empresa com uma carteira só, que segue como antes.
    {"id": "c9", "empresa_id": "beta", "total_devedores": 2, "valor_face": 1000, "valor_esperado": 400, "score_medio": 40, "created_at": "2026-10-02T10:00:00Z"},
]
TAB["predicoes"] = [
    pred(1, "c1", "111.111.111-11", 100, 50, 40), pred(2, "c1", "22222222222", 200, 100, 50), pred(3, "c1", "33333333333", 300, 150, 60),
    pred(4, "c2", "11111111111", 120, 60, 50), pred(5, "c2", "22222222222", 220, 110, 60), pred(6, "c2", "44444444444", 320, 160, 70),
    pred(7, "c9", "55555555555", 500, 200, 40), pred(8, "c9", "66666666666", 500, 200, 40),
]
TAB["feedbacks"] = []
TAB["usuarios"] = []
TAB["empresa_config"] = []

print("— devedores únicos —")
r = c.get("/comando/visao-geral", headers=CMD)
j = r.json()
emp = {e["empresa_id"]: e for e in j["empresas"]}
g = emp["goias"]
checar(r.status_code == 200 and g["total_carteiras"] == 2, "continua mostrando as 2 carteiras", r.text[:100])
checar(g["total_devedores"] == 4, "4 devedores únicos (CPF com e sem máscara é o mesmo), não 6", str(g["total_devedores"]))
checar(g["valor_face_total"] == 120 + 220 + 320 + 300, "valor de face: a análise mais recente de cada CPF, sem somar as duas", str(g["valor_face_total"]))
checar(g["valor_esperado_total"] == 60 + 110 + 160 + 150, "valor esperado do mesmo jeito", str(g["valor_esperado_total"]))
checar(g["score_medio"] == round((50 + 60 + 70 + 60) / 4, 1), "score médio dos devedores únicos", str(g["score_medio"]))
checar(emp["beta"]["total_devedores"] == 2 and emp["beta"]["valor_face_total"] == 1000, "empresa com uma carteira: igual a antes")
checar(j["totais"]["total_devedores"] == 6 and j["totais"]["valor_face_total"] == 960 + 1000, "totais do topo sem duplicar", str(j["totais"]))

print("— sem acesso às predições —")
FALHA_PREDICOES["ativo"] = True
g = {e["empresa_id"]: e for e in c.get("/comando/visao-geral", headers=CMD).json()["empresas"]}["goias"]
checar(g["total_devedores"] == 6 and g["valor_face_total"] == 1260, "volta à soma das carteiras em vez de quebrar", str(g["total_devedores"]))

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
