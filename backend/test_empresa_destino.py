"""Nenhuma análise grava carteira sem empresa (carteira órfã).

    python test_empresa_destino.py
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

def destino(payload, alvo):
    try:
        return main._empresa_destino_da_analise(payload, alvo)
    except HTTPException as e:
        return e.status_code

checar(destino({"role": "comando", "empresa_id": ""}, None) == 400, "comando sem empresa escolhida: recusa")
checar(destino({"role": "comando", "empresa_id": ""}, "  ") == 400, "comando com empresa em branco: recusa")
checar(destino({"role": "comando", "empresa_id": ""}, " Goias_Bank ") == "goias_bank", "comando com empresa: usa a escolhida, normalizada")
checar(destino({"role": "admin", "empresa_id": "goias_bank"}, "sicoob") == "goias_bank", "admin: sempre a própria, ignora o alvo")
checar(destino({"role": "admin", "empresa_id": ""}, None) == 400, "admin sem empresa: recusa")
checar(destino({"role": "operador", "empresa_id": ""}, "x") == 400, "operador sem empresa: recusa mesmo com alvo")

# Pelas rotas: a recusa vem antes de ler o arquivo ou conectar no banco.
PAPEL = {"p": {"sub": "u1", "email": "c@m.app", "role": "comando", "empresa_id": ""}}
main._usuario_autenticado = lambda cred: dict(PAPEL["p"])
chamou = []
main._analisar_df = lambda *a, **k: chamou.append(k.get("_empresa_id")) or {"resumo": {}}
hc = TestClient(main.app)
H = {"Authorization": "Bearer t"}
csv = ("c.csv", b"cpf,valor_divida,dias_em_atraso\n1,100,10\n", "text/csv")

r = hc.post("/analisar?incluir_ranking=false", files={"file": csv}, headers=H)
checar(r.status_code == 400 and not chamou, "/analisar do comando sem empresa: 400 e nada analisado", f"{r.status_code} {r.text[:80]}")
r = hc.post("/analisar?incluir_ranking=false", files={"file": csv}, data={"empresa_id": "goias_bank"}, headers=H)
checar(r.status_code == 200 and chamou == ["goias_bank"], "/analisar do comando com empresa: grava nela", f"{r.status_code} {chamou}")

chamou.clear()
r = hc.post("/analisar/db", json={"tipo": "postgres", "host": "db.exemplo.com", "query": "select 1"}, headers=H)
checar(r.status_code == 400 and "empresa" in r.text and not chamou,
       "/analisar/db do comando sem empresa: 400 antes de conectar", f"{r.status_code} {r.text[:80]}")

PAPEL["p"] = {"sub": "u2", "email": "a@x.com", "role": "admin", "empresa_id": ""}
r = hc.post("/analisar?incluir_ranking=false", files={"file": csv}, headers=H)
checar(r.status_code == 400 and not chamou, "/analisar de usuário sem empresa: 400", f"{r.status_code}")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
