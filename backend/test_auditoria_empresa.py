"""COMANDO filtra a auditoria por empresa; admin continua preso à própria.

    python test_auditoria_empresa.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402
from fastapi.testclient import TestClient

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

LINHAS = [{"id": 1, "empresa_id": "goiasbank"}, {"id": 2, "empresa_id": "outra"},
          {"id": 3, "empresa_id": None}, {"id": 4, "empresa_id": ""}]
class Q:
    def __init__(s): s.f = lambda l: True
    def select(s, *a, **k): return s
    def eq(s, c, v):
        ant = s.f; s.f = lambda l: ant(l) and l.get(c) == v; return s
    def or_(s, expr):
        ant = s.f
        if expr == "empresa_id.is.null,empresa_id.eq.":
            s.f = lambda l: ant(l) and l.get("empresa_id") in (None, "")
        return s
    def gte(s, *a): return s
    def lte(s, *a): return s
    def order(s, *a, **k): return s
    def range(s, *a): return s
    def execute(s): return type("R", (), {"data": [l for l in LINHAS if s.f(l)]})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q())})()

PAPEL = {}
main._exigir_admin_ou_comando = lambda cred: dict(PAPEL)
hc = TestClient(main.app); H = {"Authorization": "Bearer t"}
ids = lambda r: sorted(l["id"] for l in r.json())

PAPEL.update(role="comando", empresa_id="")
checar(ids(hc.get("/auditoria", headers=H)) == [1, 2, 3, 4], "comando sem filtro: tudo")
checar(ids(hc.get("/auditoria?empresa_id=GoiasBank", headers=H)) == [1], "comando filtra pela empresa (normalizada)")
checar(ids(hc.get("/auditoria?empresa_id=_plataforma", headers=H)) == [3, 4], "'_plataforma' traz as ações sem empresa")

PAPEL.clear(); PAPEL.update(role="admin", empresa_id="goiasbank")
checar(ids(hc.get("/auditoria", headers=H)) == [1], "admin: só a própria empresa")
checar(ids(hc.get("/auditoria?empresa_id=outra", headers=H)) == [1], "admin não escapa passando empresa_id")
checar(ids(hc.get("/auditoria?empresa_id=_plataforma", headers=H)) == [1], "admin não vê as da plataforma")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
