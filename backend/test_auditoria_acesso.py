"""A auditoria é de admin e comando; operador não a lê pela API.

    python test_auditoria_acesso.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                    # noqa: E402
from auth import criar_token                   # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

LINHAS = [{"id": 1, "empresa_id": "alfa", "acao": "usuario_criado"}, {"id": 2, "empresa_id": "beta", "acao": "x"}]
class Q:
    def __init__(s): s.f = {}
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f[c] = v; return s
    def gte(s, *a): return s
    def lte(s, *a): return s
    def order(s, *a, **k): return s
    def range(s, *a): return s
    def limit(s, *a): return s
    def execute(s):
        d = [x for x in LINHAS if all(x.get(k) == v for k, v in s.f.items())]
        return type("R", (), {"data": d, "count": len(d)})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q())})()
U = {"op": {"ativo": True, "id": "op", "role": "operador", "empresa_id": "alfa"},
     "ad": {"ativo": True, "id": "ad", "role": "admin", "empresa_id": "alfa"},
     "co": {"ativo": True, "id": "co", "role": "comando", "empresa_id": ""}}
main.buscar_usuario_por_id = lambda uid: U[uid]
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "e@e.com", "nome": "N", "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}

checar(c.get("/auditoria", headers=H("op")).status_code == 403, "operador não lê a auditoria")
r = c.get("/auditoria", headers=H("ad"))
checar(r.status_code == 200, "admin lê", str(r.status_code))
itens = r.json() if isinstance(r.json(), list) else r.json().get("itens", [])
checar(itens and all(x["empresa_id"] == "alfa" for x in itens), "e só da própria empresa", str(itens)[:80])
checar(c.get("/auditoria", headers=H("co")).status_code == 200, "comando lê")
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
