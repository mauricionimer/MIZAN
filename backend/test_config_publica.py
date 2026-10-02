"""config-publica não revela quem tem conta.

    python test_config_publica.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                    # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

TAB = {"usuarios": [{"email": "ana@banco.com", "empresa_id": "banco"}],
       "empresa_config": [{"empresa_id": "banco", "nome_exibicao": "Banco X", "foto_url": "u",
                           "cor_primaria": "#123456", "extra": {"permitir_upload_db": True}}]}
consultas = []
class Q:
    def __init__(s, t): s.t = t; s.l = TAB.get(t, []); consultas.append(t)
    def select(s, *a): return s
    def eq(s, c, v): s.l = [x for x in s.l if x.get(c) == v]; return s
    def limit(s, n): return s
    def execute(s): return type("R", (), {"data": s.l})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
c = TestClient(main.app)

a = c.get("/empresa/config-publica", params={"email": "ana@banco.com"}).json()
b = c.get("/empresa/config-publica", params={"email": "ninguem@x.com"}).json()
checar(a == b, "e-mail existente e inexistente dão a mesma resposta", f"{a} | {b}")
checar(not a.get("empresa_id"), "e nenhuma revela empresa")
checar("usuarios" not in consultas, "a tabela de usuários nem é consultada")
r = c.get("/empresa/config-publica", params={"empresa_id": "banco"}).json()
checar(r.get("nome_exibicao") == "Banco X" and r.get("cor_primaria") == "#123456", "link ?empresa= segue funcionando")
checar("extra" not in r, "flags internas (extra) não saem no endpoint público", str(r))
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
