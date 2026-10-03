"""Conexão salva só é usada por quem pode, e só contra o servidor dela.

    python test_conexoes_escopo.py

Achado ao documentar o sistema: `_resolver_credenciais` decifrava a senha SALVA
de qualquer `conexao_id` que viesse na requisição, sem checar de quem era, e a
usava contra o host que a requisição indicasse. Qualquer usuário autenticado,
de qualquer empresa e de qualquer papel, que conhecesse o id de uma conexão
recebia a senha do cliente num servidor que ele mesmo apontasse.

Em volta disso, três portas abertas do mesmo tipo:
  - operador podia testar conexão com host e senha digitados (sonda de rede);
  - qualquer usuário da empresa editava a conexão (PATCH);
  - as rotas de permissão aceitavam o id de uma conexão de OUTRA empresa.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cryptography.fernet import Fernet                              # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())

import main                                                          # noqa: E402
from auth import criar_token                                         # noqa: E402
from fastapi.testclient import TestClient                            # noqa: E402
import sqlalchemy                                                    # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


SENHA = "senha-secreta-do-cliente"
TAB = {
    "conexoes_db": [{"id": "cx-alfa", "empresa_id": "alfa", "usuario_id": "u-admin-alfa", "tipo": "postgres",
                     "host": "db.alfa.example", "porta": 5432, "banco": "carteira", "usuario": "leitor",
                     "senha": main._encrypt(SENHA), "query": "SELECT 1"}],
    "conexao_permissoes": [{"id": "p1", "conexao_id": "cx-alfa", "operador_id": "u-op-liberado"}],
    "usuarios": [{"id": "u-op-liberado", "empresa_id": "alfa"}, {"id": "u-op-alfa2", "empresa_id": "alfa"},
                 {"id": "u-op-beta", "empresa_id": "beta"}],
}
USERS = {
    "u-admin-alfa":  {"ativo": True, "id": "u-admin-alfa", "role": "admin", "empresa_id": "alfa"},
    "u-admin-beta":  {"ativo": True, "id": "u-admin-beta", "role": "admin", "empresa_id": "beta"},
    "u-op-liberado": {"ativo": True, "id": "u-op-liberado", "role": "operador", "empresa_id": "alfa"},
    "u-op-alfa2":    {"ativo": True, "id": "u-op-alfa2", "role": "operador", "empresa_id": "alfa"},
    "u-comando":     {"ativo": True, "id": "u-comando", "role": "comando", "empresa_id": ""},
}
ESCRITAS = []


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
        if s.op != "select":
            ESCRITAS.append((s.t, s.op, dict(s.f), s.dados))
            return type("R", (), {"data": []})()
        d = [x for x in TAB.get(s.t, []) if all(x.get(k) == v for k, v in s.f.items() if not isinstance(v, list))]
        return type("R", (), {"data": d})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.buscar_usuario_por_id = lambda uid: USERS[uid]
main._registrar_auditoria = lambda *a, **k: None
main._validar_destino_externo = lambda conn: None      # sem DNS no teste

tentativas = []


def engine_falso(url, **k):
    tentativas.append(url)
    raise RuntimeError("sem rede no teste")


sqlalchemy.create_engine = engine_falso
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda uid: {"Authorization": "Bearer " + criar_token(
    {"sub": uid, "email": "x@x.com", "nome": "N", "role": USERS[uid]["role"],
     "empresa_id": USERS[uid]["empresa_id"]})}


def testar(uid, **corpo):
    tentativas.clear()
    base = {"tipo": "postgres", "query": "SELECT 1"}
    return c.post("/testar-db", headers=H(uid), json={**base, **corpo})


print("— a senha salva só vai para o servidor salvo —")
r = testar("u-admin-alfa", conexao_id="cx-alfa", host="servidor-do-atacante.example", banco="x", usuario="x")
checar(len(tentativas) == 1 and "db.alfa.example" in tentativas[0] and "atacante" not in tentativas[0],
       "host da requisição é ignorado: a conexão usa o servidor cadastrado", str(tentativas))
checar(SENHA in tentativas[0], "e a senha salva é usada nele (fluxo legítimo continua)")

print("\n— quem pode usar —")
r = testar("u-admin-beta", conexao_id="cx-alfa")
checar(r.status_code == 403 and not tentativas, "admin de OUTRA empresa: 403 e nem tenta conectar", f"{r.status_code} {tentativas}")
r = testar("u-op-alfa2", conexao_id="cx-alfa")
checar(r.status_code == 403 and not tentativas, "operador sem permissão: 403", f"{r.status_code}")
r = testar("u-op-liberado", conexao_id="cx-alfa")
checar(len(tentativas) == 1 and "db.alfa.example" in tentativas[0], "operador liberado usa a conexão", f"{r.status_code} {tentativas}")
r = testar("u-comando", conexao_id="cx-alfa")
checar(len(tentativas) == 1, "comando usa qualquer uma")
r = testar("u-admin-alfa", conexao_id="nao-existe")
checar(r.status_code == 404 and not tentativas, "conexão inexistente: 404")

print("\n— host e senha digitados —")
r = testar("u-op-liberado", host="outro.example", banco="b", usuario="u", senha="s")
checar(r.status_code == 403 and not tentativas, "operador não digita host e senha (sonda de rede)", str(r.status_code))
r = testar("u-admin-alfa", host="meu.example", banco="b", usuario="u", senha="s")
checar(len(tentativas) == 1 and "meu.example" in tentativas[0], "admin digita o banco dele normalmente", f"{r.status_code} {tentativas}")
tentativas.clear()
r = c.post("/listar-tabelas", headers=H("u-op-alfa2"), json={"tipo": "postgres", "host": "x.example", "banco": "b", "usuario": "u", "senha": "s"})
checar(r.status_code == 403 and not tentativas, "/listar-tabelas: mesma regra para operador")
tentativas.clear()
r = c.post("/analisar/db", headers=H("u-admin-beta"), json={"tipo": "postgres", "conexao_id": "cx-alfa", "query": "SELECT 1"})
checar(r.status_code == 403 and not tentativas, "/analisar/db: admin de outra empresa não usa a conexão", str(r.status_code))

print("\n— editar a conexão —")
r = c.patch("/conexoes/cx-alfa", headers=H("u-op-liberado"), json={"query": "SELECT * FROM x"})
checar(r.status_code == 403, "operador não edita, mesmo com permissão de uso", str(r.status_code))
r = c.patch("/conexoes/cx-alfa", headers=H("u-admin-beta"), json={"query": "SELECT * FROM x"})
checar(r.status_code == 403, "admin de outra empresa não edita", str(r.status_code))
ESCRITAS.clear()
r = c.patch("/conexoes/cx-alfa", headers=H("u-admin-alfa"), json={"query": "SELECT * FROM x"})
checar(r.status_code == 200 and any(e[1] == "update" for e in ESCRITAS), "admin da empresa edita", str(r.status_code))

print("\n— permissões de uso —")
for metodo, url in (("get", "/conexoes/cx-alfa/permissoes"),
                    ("post", "/conexoes/cx-alfa/permissoes/u-op-alfa2"),
                    ("delete", "/conexoes/cx-alfa/permissoes/u-op-liberado")):
    ESCRITAS.clear()
    r = getattr(c, metodo)(url, headers=H("u-admin-beta"))
    checar(r.status_code == 403 and not ESCRITAS, f"admin de outra empresa: {metodo.upper()} recusado", str(r.status_code))
ESCRITAS.clear()
r = c.post("/conexoes/cx-alfa/permissoes/u-op-beta", headers=H("u-admin-alfa"))
checar(r.status_code == 400 and not ESCRITAS, "não libera a conexão a usuário de outra empresa", str(r.status_code))
r = c.post("/conexoes/cx-alfa/permissoes/u-op-alfa2", headers=H("u-admin-alfa"))
checar(r.status_code == 200 and any(e[1] == "insert" for e in ESCRITAS), "libera a quem é da mesma empresa", str(r.status_code))

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
