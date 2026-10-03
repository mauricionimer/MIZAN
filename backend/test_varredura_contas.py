"""Varredura das telas de conta, empresa, retenção e chaves de API.

    python test_varredura_contas.py

  1. trocar ou redefinir a senha derruba as outras sessões (o token durava 7 dias);
  2. "excluir minha conta" não apaga o que é da empresa e não tranca a plataforma;
  3. a auditoria não guarda o CPF inteiro;
  4. retenção e pedido do titular alcançam feedbacks gravados com o nome da empresa;
  5. mover usuário entre empresas normaliza o id e fica na auditoria;
  6. o logo é aceito pelo conteúdo, não pelo nome nem pelo tipo declarado;
  7. a cor da empresa precisa ser #rrggbb;
  8. o COMANDO cria e revoga chaves de API (antes, só por SQL).
"""
import os, sys, uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import auth                                   # noqa: E402
import main                                   # noqa: E402
from fastapi.testclient import TestClient     # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

T = {k: [] for k in ("usuarios", "contatos", "duvidas", "conexoes_db", "auditoria", "api_keys", "feedbacks",
                     "predicoes", "carteiras", "reset_tokens", "empresa_config", "recomendacoes", "login_tentativas")}
SUBIDOS = []

class Q:
    def __init__(s, t): s.t, s.f, s.op, s.d, s.rng, s.lim, s.cols = t, [], "select", None, None, None, None
    def select(s, cols="*", **k):
        s.cols = None if cols.strip() == "*" else [c.strip() for c in cols.split(",")]
        return s
    def eq(s, c, v): s.f.append(lambda x: x.get(c) == v); return s
    def neq(s, c, v): s.f.append(lambda x: x.get(c) != v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda x: x.get(c) in vs); return s
    def is_(s, c, v): s.f.append(lambda x: x.get(c) is None); return s
    def gte(s, c, v): s.f.append(lambda x: str(x.get(c) or "") >= v); return s
    def lte(s, c, v): s.f.append(lambda x: str(x.get(c) or "") <= v); return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, d): s.op, s.d = "insert", d; return s
    def update(s, d): s.op, s.d = "update", d; return s
    def delete(s): s.op = "delete"; return s
    def execute(s):
        tab = T.setdefault(s.t, [])
        alvo = [x for x in tab if all(f(x) for f in s.f)]
        if s.op == "insert":
            for d in (s.d if isinstance(s.d, list) else [s.d]):
                tab.append({"id": d.get("id") or str(uuid.uuid4()), "created_at": "2026-10-03", **d})
            return type("R", (), {"data": tab[-1:]})()
        if s.op == "update":
            for x in alvo: x.update(s.d)
            return type("R", (), {"data": alvo})()
        if s.op == "delete":
            for x in alvo: tab.remove(x)
            return type("R", (), {"data": alvo})()
        d = alvo[s.rng[0]:s.rng[1] + 1] if s.rng else alvo
        d = d[:s.lim] if s.lim else d
        return type("R", (), {"data": [({k: x.get(k) for k in s.cols} if s.cols else dict(x)) for x in d]})()

class Bucket:
    def upload(s, caminho, conteudo, opcoes): SUBIDOS.append(opcoes)
    def get_public_url(s, caminho): return "https://x/" + caminho
DB = type("DB", (), {"table": staticmethod(lambda n: Q(n)),
                     "storage": type("S", (), {"from_": staticmethod(lambda b: Bucket())})()})()
main.get_db = lambda: DB
auth._db = lambda: DB
import db as _dbm; _dbm.get_db = lambda: DB
main._checar_rate_limit = lambda *a: None
main._registrar_tentativa = lambda *a: None
main._limpar_tentativas = lambda *a: None
AUD = []
main._registrar_auditoria = lambda *a, **k: AUD.append(k if k else {"acao": a[0], "detalhes": a[5] if len(a) > 5 else {}})

def usuario(i, email, role, empresa, senha="Senha123"):
    T["usuarios"].append({"id": i, "email": email, "nome": i, "role": role, "empresa_id": empresa,
                          "ativo": True, "senha_hash": auth.hash_senha(senha)})
usuario("uc", "c@m.app", "comando", "")
usuario("ua", "a@alfa.com", "admin", "alfa")
usuario("uo", "o@alfa.com", "operador", "alfa")
c = TestClient(main.app, raise_server_exceptions=False)
def entrar(email, senha="Senha123"):
    r = c.post("/auth/login", json={"email": email, "senha": senha})
    return {"Authorization": "Bearer " + r.json().get("token", "")}

print("— 1. senha trocada derruba as outras sessões —")
h1, h2 = entrar("o@alfa.com"), entrar("o@alfa.com")       # dois aparelhos
checar(c.get("/auth/me", headers=h1).status_code == 200, "logado nos dois")
r = c.post("/auth/alterar-senha", headers=h1, json={"senha_atual": "Senha123", "nova_senha": "Nova1234"})
novo = {"Authorization": "Bearer " + r.json().get("token", "")}
checar(r.status_code == 200 and c.get("/auth/me", headers=novo).status_code == 200,
       "quem trocou recebe um token novo e continua dentro")
checar(c.get("/auth/me", headers=h2).status_code == 401, "a outra sessão (ou um token roubado) cai")
checar(c.post("/auth/refresh", headers=h2).status_code == 401, "e não dá para renová-la")
antigo = {"Authorization": "Bearer " + auth.criar_token({"sub": "uo", "email": "o@alfa.com", "nome": "uo",
                                                          "role": "operador", "empresa_id": "alfa"})}
checar(c.get("/auth/me", headers=antigo).status_code == 401, "token emitido antes desta versão (sem a marca) também cai")
T["reset_tokens"] += [{"id": "r1", "token": "t1", "email": "a@alfa.com", "expires_at": "2099-01-01T00:00:00+00:00", "usado": False},
                      {"id": "r2", "token": "t2", "email": "a@alfa.com", "expires_at": "2099-01-01T00:00:00+00:00", "usado": False}]
ha = entrar("a@alfa.com")
auth.redefinir_senha_com_token("t1", "Outra123")
checar(all(t["usado"] for t in T["reset_tokens"]), "redefinir pelo link mata também os outros links do mesmo e-mail")
checar(c.get("/auth/me", headers=ha).status_code == 401, "e derruba as sessões abertas")
ha = entrar("a@alfa.com", "Outra123")

print("\n— 2. excluir a própria conta —")
T["contatos"].append({"id": "ct1", "cpf": "1", "usuario_id": "uo", "usuario_nome": "uo", "empresa_id": "alfa"})
T["conexoes_db"].append({"id": "cx1", "usuario_id": "uo", "empresa_id": "alfa", "nome": "banco do cliente"})
T["duvidas"].append({"id": "d1", "autor_id": "uo", "autor_nome": "uo", "autor_email": "o@alfa.com"})
r = c.delete("/auth/me", headers=novo)
checar(r.status_code == 200 and not any(u["id"] == "uo" for u in T["usuarios"]), "o cadastro sai")
checar(T["contatos"] and T["contatos"][0]["usuario_nome"] == "Usuário removido", "o histórico de contatos fica, sem o nome dela")
checar(T["conexoes_db"], "a conexão com o banco do cliente continua com a empresa")
checar(T["duvidas"][0]["autor_email"] == "" and T["duvidas"][0]["autor_nome"] == "Usuário removido", "o nome sai das dúvidas")
checar(any(a.get("acao") == "conta_excluida" and a.get("usuario_email") == "" for a in AUD), "fica na auditoria, sem o e-mail")
hc = entrar("c@m.app")
r = c.delete("/auth/me", headers=hc)
checar(r.status_code == 400 and any(u["id"] == "uc" for u in T["usuarios"]), "o único COMANDO não se exclui", r.status_code)

print("\n— 3. auditoria sem CPF inteiro —")
fonte = (AQUI / "main.py").read_text(encoding="utf-8")
checar('detalhes={"cpf": cpf,' not in fonte and '"cpf_final"' in fonte, "confirmar pagamento audita só o final do CPF")

print("\n— 4. pedido do titular alcança feedback com o nome da empresa —")
T["carteiras"].append({"id": "ca", "empresa_id": "alfa"})
T["predicoes"].append({"id": "pa", "carteira_id": "ca", "cpf": "12345678901", "created_at": "2026-01-01"})
T["feedbacks"] += [{"id": "f-nome", "cpf": "12345678901", "empresa": "Banco Alfa", "predicao_id": "pa", "created_at": "2026-01-01"},
                   {"id": "f-outra", "cpf": "12345678901", "empresa": "beta", "predicao_id": "pb", "created_at": "2026-01-01"}]
r = c.post("/retencao/titular", headers=ha, json={"cpf": "123.456.789-01"})
fb = {f["id"]: f for f in T["feedbacks"]}
checar(r.status_code == 200 and fb["f-nome"]["cpf"] is None, "o feedback gravado como 'Banco Alfa' perde o CPF", r.text[:120])
checar(fb["f-outra"]["cpf"] == "12345678901", "o de outra empresa não é tocado")

print("\n— 5. mover usuário entre empresas —")
usuario("ux", "x@novo.com", "operador", "")
r = c.post("/empresas/Goias_Bank/usuarios", headers=hc, json={"email": "X@novo.com"})
ux = next(u for u in T["usuarios"] if u["id"] == "ux")
checar(r.status_code == 200 and ux["empresa_id"] == "goias_bank", "id da empresa em minúscula, e-mail sem diferença de caixa", ux["empresa_id"])
checar(any(a.get("acao") == "usuario_movido_para_empresa" for a in AUD), "fica na auditoria")
c.delete("/empresas/goias_bank/usuarios/ux", headers=hc)
checar(any(a.get("acao") == "usuario_removido_da_empresa" for a in AUD), "remover também")

print("\n— 6. logo da empresa —")
r = c.post("/empresa/foto", headers=ha, files={"file": ("logo.png", b"<html><script>x</script></html>", "text/html")})
checar(r.status_code == 400 and not SUBIDOS, "HTML com nome .png é recusado", r.status_code)
png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
r = c.post("/empresa/foto", headers=ha, files={"file": ("logo.png", png, "text/html")})
checar(r.status_code == 200 and SUBIDOS and SUBIDOS[-1]["content-type"] == "image/png",
       "PNG de verdade sobe com o tipo do conteúdo, não o declarado", str(SUBIDOS[-1:]))

print("\n— 7. cor da empresa —")
checar(c.put("/empresa/config", headers=ha, json={"cor_primaria": "red;background:url(x)"}).status_code == 422, "cor fora de #rrggbb é recusada")
checar(c.put("/empresa/config", headers=ha, json={"cor_primaria": "#1d4ed8"}).status_code == 200, "#rrggbb passa")

print("\n— 8. chaves de API —")
checar(c.post("/comando/api-keys", headers=ha, json={"empresa_id": "alfa", "rotulo": "x1"}).status_code == 403, "admin não cria chave")
r = c.post("/comando/api-keys", headers=hc, json={"empresa_id": "Alfa", "rotulo": "webhook produção"})
j = r.json()
chave = j.get("chave", "")
linha = T["api_keys"][-1] if T["api_keys"] else {}
checar(r.status_code == 200 and chave.startswith("mzk_") and linha.get("empresa_id") == "alfa", "COMANDO cria a chave da alfa")
checar(chave not in str(linha) and linha.get("api_key_hash") == main._hash_api_key(chave), "o banco guarda só o hash")
checar(main._buscar_api_key(DB, chave) is not None, "a chave autentica")
lista = c.get("/comando/api-keys", headers=hc).json()
checar(lista and "api_key_hash" not in lista[0] and chave not in str(lista), "a listagem não traz chave nem hash")
r = c.post(f"/comando/api-keys/{linha['id']}/revogar", headers=hc)
checar(r.status_code == 200 and main._buscar_api_key(DB, chave) is None, "revogada, para de autenticar na hora")
checar({"chave_api_criada", "chave_api_revogada"} <= {a.get("acao") for a in AUD}, "criação e revogação na auditoria")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
