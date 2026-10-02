"""O diagnóstico do banco é só do comando e só lê.

    python test_diagnostico_banco.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402
from auth import criar_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

LIMITE_URL = 400
ESCRITAS = []
class Q:
    def __init__(s, t): s.t = t; s.n = 0; s.rng = None
    def select(s, *a): return s
    def in_(s, c, v):
        if len(list(v)) > LIMITE_URL: raise RuntimeError("414 URI too long")
        return s
    def order(s, *a): return s
    def limit(s, n): return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, *a): ESCRITAS.append("insert"); return s
    def update(s, *a): ESCRITAS.append("update"); return s
    def delete(s): ESCRITAS.append("delete"); return s
    def execute(s):
        if s.rng: return type("R", (), {"data": [{"id": i} for i in range(1000)]})()
        return type("R", (), {"data": []})()
USERS = {"c": {"ativo": True, "id": "c", "role": "comando", "empresa_id": ""},
         "a": {"ativo": True, "id": "a", "role": "admin", "empresa_id": "x"}}
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.buscar_usuario_por_id = lambda uid: USERS[uid]
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u, r: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "e@e.com", "nome": "N", "role": r, "empresa_id": ""})}

checar(c.get("/comando/diagnostico-banco", headers=H("a", "admin")).status_code == 403, "admin não acessa")
checar(c.get("/comando/diagnostico-banco").status_code in (401, 403), "sem token não acessa")
r = c.get("/comando/diagnostico-banco", headers=H("c", "comando"))
j = r.json()
checar(r.status_code == 200, "comando acessa", r.text[:80])
checar(j["in_"]["maior_testado_ok"] == 400 and j["in_"]["primeira_falha"]["itens"] == 800,
       "acha o maior in_ aceito (400) e onde falha (800)", str(j["in_"]))
checar(j["in_"]["adotado_cabe"] is True, "diz que os 100 adotados cabem")
checar(j["teto_resposta"]["recebidas"] == 1000 and j["teto_resposta"]["veredito"] == "lote adotado cabe", "mede o teto de resposta", str(j["teto_resposta"]))
checar(j["ordenacao_rank_id"]["aceita"] is True, "confere a ordenação rank,id")
checar(not ESCRITAS, "não escreve nada", str(ESCRITAS))
LIMITE_URL = 50
j = c.get("/comando/diagnostico-banco", headers=H("c", "comando")).json()
checar(j["in_"]["adotado_cabe"] is False, "se o servidor aceitar menos que 100, avisa que o adotado NÃO cabe", str(j["in_"]))
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
