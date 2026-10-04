"""Performance da IA: admin e operador leem só a própria empresa; COMANDO escolhe.

    python test_ia_leitura.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402
from fastapi import HTTPException
from fastapi.testclient import TestClient

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

PAPEL = {}
main._usuario_autenticado = lambda cred: dict(PAPEL)

pedidas = []
import model.diagnostico as diag, model.bandit as bandit_mod, model.modelos_empresa as me
diag.avaliar_modelo_ativo = lambda db, emp: pedidas.append(("qualidade", emp)) or {"ok": False, "motivo": "x"}
class B:
    n_tentativas = [0]; alpha = 1.0
    def stats(self): return []
bandit_mod.carregar_bandit = lambda emp: pedidas.append(("bandit", emp)) or B()
me.carregar_versoes = lambda emp: pedidas.append(("modelos", emp)) or {"versao_ativa": None, "versoes": []}
class Q:
    def __getattr__(s, n): return lambda *a, **k: s
    def execute(s): return type("R", (), {"data": [], "count": 0})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q())})()

hc = TestClient(main.app, raise_server_exceptions=False); H = {"Authorization": "Bearer t"}

def ultima(tipo): return [e for t, e in pedidas if t == tipo][-1]

PAPEL.clear(); PAPEL.update(role="admin", empresa_id="goiasbank")
for rota, tipo in (("/admin/modelo/qualidade", "qualidade"), ("/admin/bandit/stats", "bandit"), ("/comando/modelos", "modelos")):
    r = hc.get(rota + "?empresa_id=outra", headers=H)
    checar(r.status_code == 200 and ultima(tipo) == "goiasbank",
           f"admin em {rota}: sempre a própria empresa, mesmo pedindo outra", f"{r.status_code} {ultima(tipo) if pedidas else '-'}")
r = hc.get("/admin/drift?empresa_id=outra", headers=H)
checar(r.status_code == 200, "admin lê a estabilidade da própria empresa", str(r.status_code))

PAPEL.clear(); PAPEL.update(role="comando", empresa_id="")
hc.get("/admin/modelo/qualidade?empresa_id=Beta", headers=H)
checar(ultima("qualidade") == "beta", "comando escolhe a empresa")
checar(hc.get("/comando/modelos", headers=H).status_code == 400, "comando sem empresa em /comando/modelos: 400")

PAPEL.clear(); PAPEL.update(role="operador", empresa_id="goiasbank")
r = hc.get("/admin/modelo/qualidade?empresa_id=outra", headers=H)
checar(r.status_code == 200 and ultima("qualidade") == "goiasbank", "operador lê a IA só da própria empresa", f"{r.status_code}")
PAPEL.clear(); PAPEL.update(role="operador", empresa_id="")
checar(hc.get("/admin/modelo/qualidade", headers=H).status_code == 403, "usuário sem empresa não lê")

# Ativar e desativar continuam só do COMANDO.
PAPEL.clear(); PAPEL.update(role="admin", empresa_id="goiasbank")
main._exigir_comando = lambda cred: (_ for _ in ()).throw(HTTPException(status_code=403, detail="só comando"))
r = hc.post("/comando/modelos/ativar", json={"empresa_id": "goiasbank", "versao": "v1"}, headers=H)
checar(r.status_code == 403, "admin não ativa modelo", str(r.status_code))

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
