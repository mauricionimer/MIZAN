"""Conexão Google Sheets salva guarda a credencial (cifrada) e sincroniza (D12).

    python test_conexao_sheets.py

Antes, o cadastro da conexão não guardava a credencial da conta de serviço, e
a sincronização (manual e automática) de toda conexão Sheets salva falhava.
A credencial tem a chave privada do cliente: entra no banco cifrada e nunca
volta para a tela.
"""
import os, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cryptography.fernet import Fernet                              # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())

import pandas as pd                                                  # noqa: E402
import main                                                          # noqa: E402
from auth import criar_token                                         # noqa: E402
from fastapi.testclient import TestClient                            # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CRED = {"type": "service_account", "client_email": "leitor@projeto.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
        "private_key": "-----BEGIN PRIVATE KEY-----\nSEGREDO\n-----END PRIVATE KEY-----\n"}
TAB = {"conexoes_db": [], "conexao_permissoes": []}
FALHA_COLUNA = False

class Q:
    def __init__(s, t): s.t, s.f, s.op, s.dados = t, {}, "select", None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f[c] = v; return s
    def in_(s, c, v): s.f[c] = list(v); return s
    def limit(s, *a): return s
    def order(s, *a, **k): return s
    def update(s, d): s.op, s.dados = "update", d; return s
    def insert(s, d): s.op, s.dados = "insert", d; return s
    def delete(s): s.op = "delete"; return s
    def execute(s):
        linhas = [x for x in TAB.get(s.t, []) if all(x.get(k) == v for k, v in s.f.items() if not isinstance(v, list))]
        if s.op == "insert":
            if FALHA_COLUNA and "sheets_credenciais" in s.dados:
                raise RuntimeError("Could not find the 'sheets_credenciais' column of 'conexoes_db'")
            novo = {"id": f"cx{len(TAB[s.t]) + 1}", "created_at": "2026-10-03", **s.dados}
            TAB[s.t].append(novo)
            return type("R", (), {"data": [dict(novo)]})()
        if s.op == "update":
            for x in linhas: x.update(s.dados)
            return type("R", (), {"data": linhas})()
        if s.op == "delete":
            for x in linhas: TAB[s.t].remove(x)
            return type("R", (), {"data": linhas})()
        return type("R", (), {"data": [dict(x) for x in linhas]})()

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
USERS = {"ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa"},
         "ub": {"ativo": True, "id": "ub", "role": "admin", "empresa_id": "beta"},
         "uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": ""}}
main.buscar_usuario_por_id = lambda uid: USERS[uid]
main._registrar_auditoria = lambda *a, **k: None
LIDAS = []
def ler_falso(conn):
    LIDAS.append(conn.sheets_credenciais)
    raise RuntimeError("sem rede no teste")
main._ler_google_sheets = ler_falso
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "x@x", "nome": "N",
                                                          "role": USERS[u]["role"], "empresa_id": USERS[u]["empresa_id"]})}
base = {"nome": "Planilha do banco", "tipo": "sheets", "sheets_id": "1AbC", "sheets_aba": "Devedores"}

print("— salvar —")
r = c.post("/conexoes", headers=H("ua"), json=base)
checar(r.status_code == 400 and not TAB["conexoes_db"], "Sheets sem credencial: recusa em vez de salvar algo que não sincroniza", r.status_code)
r = c.post("/conexoes", headers=H("ua"), json={**base, "sheets_credenciais": {"type": "service_account"}})
checar(r.status_code == 400, "credencial sem chave privada: recusa", r.status_code)
r = c.post("/conexoes", headers=H("ua"), json={**base, "sheets_credenciais": CRED})
gravada = TAB["conexoes_db"][0] if TAB["conexoes_db"] else {}
checar(r.status_code == 200 and gravada.get("sheets_credenciais"), "salva com a credencial", r.status_code)
checar("SEGREDO" not in str(gravada.get("sheets_credenciais")) and "leitor@" not in str(gravada.get("sheets_credenciais")),
       "a credencial vai CIFRADA para o banco")
checar("sheets_credenciais" not in r.json()["conexao"] and r.json()["conexao"].get("tem_credencial_sheets") is True
       and "SEGREDO" not in r.text, "a resposta não devolve a credencial, só diz que ela existe")

print("\n— listar —")
r = c.get("/conexoes", headers=H("ua"))
checar(r.status_code == 200 and "SEGREDO" not in r.text and "sheets_credenciais" not in r.text
       and r.json()[0]["tem_credencial_sheets"] is True, "a listagem não traz a credencial", r.text[:120])

print("\n— sincronizar e testar com a credencial salva —")
try:
    main._sincronizar_conexao_row(dict(gravada), "x@x", "ua", "alfa")
except Exception:
    pass
checar(LIDAS and LIDAS[-1] == CRED, "a sincronização lê a planilha com a credencial decifrada")
LIDAS.clear()
r = c.post("/testar-db", headers=H("ua"), json={"tipo": "sheets", "conexao_id": gravada["id"]})
checar(LIDAS and LIDAS[-1] == CRED, "testar a conexão salva usa a credencial guardada, sem colar de novo", r.status_code)
LIDAS.clear()
r = c.post("/testar-db", headers=H("ub"), json={"tipo": "sheets", "conexao_id": gravada["id"]})
checar(r.status_code == 403 and not LIDAS, "outra empresa não usa a credencial", r.status_code)

print("\n— conexões antigas, salvas sem credencial —")
TAB["conexoes_db"].append({"id": "velha", "empresa_id": "alfa", "usuario_id": "ua", "tipo": "sheets",
                           "sheets_id": "1Velha", "nome": "antiga"})
try:
    main._sincronizar_conexao_row(dict(TAB["conexoes_db"][-1]), "x@x", "ua", "alfa")
    msg = ""
except ValueError as e:
    msg = str(e)
checar("credencial" in msg, "a sincronização diz o que falta, em vez de um erro do Google", msg)
r = c.patch("/conexoes/velha", headers=H("ua"), json={"sheets_credenciais": CRED})
v = TAB["conexoes_db"][-1].get("sheets_credenciais")
checar(r.status_code == 200 and v and "SEGREDO" not in v, "dá para completar a credencial pela edição, cifrada", r.status_code)
LIDAS.clear()
try:
    main._sincronizar_conexao_row(dict(TAB["conexoes_db"][-1]), "x@x", "ua", "alfa")
except Exception:
    pass
checar(LIDAS and LIDAS[-1] == CRED, "e então ela sincroniza")

print("\n— banco sem a coluna nova —")
FALHA_COLUNA = True
r = c.post("/conexoes", headers=H("ua"), json={**base, "sheets_credenciais": CRED})
checar(r.status_code == 503 and "migracao_conexoes_sheets" in r.text, "diz qual migração rodar", r.text[:140])
FALHA_COLUNA = False

print("\n— apagar —")
r = c.delete("/conexoes/velha", headers=H("ub"))
checar(r.status_code == 403, "admin de outra empresa não apaga", r.status_code)
r = c.delete("/conexoes/velha", headers=H("uc"))
checar(r.status_code == 200 and not any(x["id"] == "velha" for x in TAB["conexoes_db"]), "COMANDO apaga a de qualquer empresa")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
