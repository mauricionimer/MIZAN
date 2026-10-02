"""Regressão: quem pode o quê, conferido no CADASTRO e não no token.

    python test_autorizacao.py

Resultado de uma varredura por rotas que consultam por CPF sem escopo de empresa.
Ela achou uma classe de erro, não uma rota:

  1. GET /predicoes/historico/{cpf} recebia a credencial e nunca a usava.
     HTTPBearer só confere que o cabeçalho EXISTE: com "Bearer lixo" a rota
     devolvia o histórico de score de qualquer CPF, de qualquer empresa.

  2. POST /webhook/pagamento deixava `body.empresa` vencer a empresa da chave.
     Uma chave da alfa que mandasse "empresa": "beta" gravava o pagamento no
     escopo da beta, ligado a uma predição da beta.

  3. O servidor confiava em role e empresa_id GRAVADOS NO TOKEN, que dura 7 dias.
     Desligar, rebaixar ou tirar um usuário da empresa não tinha efeito até o
     token vencer — e _exigir_comando / _exigir_admin_ou_comando conferiam só a
     assinatura, nem a existência do usuário. Um admin desligado seguia
     gerenciando a equipe; um comando desligado seguia no controle da plataforma.

  4. Admin sem empresa (o que "remover da empresa" produz) passava a listar os
     usuários de TODOS os clientes, porque empresa vazia significava "todas".

  5. /contatos e /confirmar-pagamento falhavam ABERTO: `if cart_ids:` descartava o
     filtro quando a lista vinha vazia. /contatos ainda reconstruía o contexto do
     bandit a partir da predição mais recente de QUALQUER empresa.

  6. POST /upload era a única rota de trabalho pesado sem credencial nenhuma.
"""
import io
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── Banco simulado ───────────────────────────────────────────────────────
CARTEIRAS = [{"id": "c-alfa", "empresa_id": "alfa"}, {"id": "c-beta", "empresa_id": "beta"}]
PRED = [
    {"id": "p-alfa", "carteira_id": "c-alfa", "cpf": "11111111111", "created_at": "2026-01-01",
     "score_recuperabilidade": 50.0, "valor_divida": 1000.0, "dias_em_atraso": 90,
     "perfil_cluster": "x", "cluster_id": 1},
    {"id": "p-beta", "carteira_id": "c-beta", "cpf": "22222222222", "created_at": "2026-02-01",
     "score_recuperabilidade": 90.0, "valor_divida": 9000.0, "dias_em_atraso": 30,
     "perfil_cluster": "y", "cluster_id": 2},
    {"id": "p-dupla-a", "carteira_id": "c-alfa", "cpf": "33333333333", "created_at": "2026-01-10",
     "score_recuperabilidade": 40.0, "valor_divida": 2000.0, "dias_em_atraso": 60,
     "perfil_cluster": "x", "cluster_id": 1},
    {"id": "p-dupla-b", "carteira_id": "c-beta", "cpf": "33333333333", "created_at": "2026-03-10",
     "score_recuperabilidade": 80.0, "valor_divida": 8000.0, "dias_em_atraso": 20,
     "perfil_cluster": "y", "cluster_id": 2},
]
CONTATOS = [{"id": "t1", "cpf": "22222222222", "empresa_id": "beta", "observacao": "falei com a esposa",
             "created_at": "2026-01-01"}]
FEEDBACKS, BANDIT_CHAMADAS = [], []


class Q:
    def __init__(self, tabela):
        self.tabela = tabela
        self.linhas = list({"predicoes": PRED, "carteiras": CARTEIRAS, "contatos": CONTATOS}.get(tabela, []))
        self._ins = None

    def select(self, *a, **k): return self

    def eq(self, c, v):
        self.linhas = [l for l in self.linhas if l.get(c) == v]
        return self

    def in_(self, c, vs):
        vs = set(vs)
        self.linhas = [l for l in self.linhas if l.get(c) in vs]
        return self

    def order(self, col, desc=False):
        self.linhas.sort(key=lambda l: l.get(col) or "", reverse=desc)
        return self

    def limit(self, n): self.linhas = self.linhas[:n]; return self
    def range(self, i, f): self.linhas = self.linhas[i:f + 1]; return self

    def insert(self, linha):
        self._ins = dict(linha, id=f"n{len(FEEDBACKS) + 1}")
        return self

    def execute(self):
        if self._ins is not None:
            if self.tabela == "feedbacks":
                FEEDBACKS.append(self._ins)
            return type("R", (), {"data": [self._ins]})()
        return type("R", (), {"data": self.linhas})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._registrar_auditoria = lambda *a, **k: None
main._fechar_loop_bandit = lambda db, cpf, pagou, v, pred, emp: BANDIT_CHAMADAS.append((cpf, emp, (pred or {}).get("id")))
main._cache_del_prefix = lambda *a, **k: None
main._writeback_pagamento = lambda *a, **k: None
main.listar_usuarios = lambda empresa_id="": [{"email": "x@x", "empresa_id": empresa_id or "TODAS"}]

# O cadastro: a autoridade sobre quem é e o que pode
CADASTRO = {
    "u-admin":   {"id": "u-admin",   "ativo": True,  "role": "admin",    "empresa_id": "alfa"},
    "u-fired":   {"id": "u-fired",   "ativo": False, "role": "admin",    "empresa_id": "alfa"},
    "u-demoted": {"id": "u-demoted", "ativo": True,  "role": "operador", "empresa_id": "alfa"},
    "u-moved":   {"id": "u-moved",   "ativo": True,  "role": "admin",    "empresa_id": ""},
    "u-op":      {"id": "u-op",      "ativo": True,  "role": "operador", "empresa_id": "alfa"},
    "u-boss":    {"id": "u-boss",    "ativo": True,  "role": "comando",  "empresa_id": ""},
    "u-boss-off": {"id": "u-boss-off", "ativo": False, "role": "comando", "empresa_id": ""},
    "u-nova":    {"id": "u-nova",    "ativo": True,  "role": "admin",    "empresa_id": "nova"},
}
main.buscar_usuario_por_id = lambda uid: CADASTRO.get(uid)
CHAVES = {"k-alfa": {"id": "k1", "empresa_id": "alfa", "empresa_nome": "Alfa"},
          "k-sem": {"id": "k2", "empresa_id": "", "empresa_nome": "Sem"}}
main._buscar_api_key = lambda db, t: CHAVES.get(t)
main._marcar_uso_api_key = lambda *a: None

c = TestClient(main.app, raise_server_exceptions=False)


def tok(sub, role=None, empresa=None):
    """Token com o que o cadastro dizia na emissão — por padrão, o que diz hoje."""
    u = CADASTRO.get(sub, {})
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x.com", "nome": sub,
         "role": role if role is not None else u.get("role", "operador"),
         "empresa_id": empresa if empresa is not None else u.get("empresa_id", "")})}


# ── 1. histórico: o token precisa valer ──────────────────────────────────
print("— /predicoes/historico —")
r = c.get("/predicoes/historico/33333333333", headers={"Authorization": "Bearer lixo"})
checar(r.status_code == 401, "token inventado é recusado", f"{r.status_code} — era 200 com o histórico")
r = c.get("/predicoes/historico/33333333333")
checar(r.status_code in (401, 403), "sem token também")

r = c.get("/predicoes/historico/33333333333", headers=tok("u-admin"))
ids = [h["id"] for h in r.json().get("historico", [])]
checar(r.status_code == 200 and ids == ["p-dupla-a"],
       "devolve só o histórico da própria empresa", str(ids))
checar(c.get("/predicoes/historico/22222222222", headers=tok("u-admin")).status_code == 404,
       "CPF que só existe em outra empresa é 404, não o histórico dela")
r = c.get("/predicoes/historico/33333333333", headers=tok("u-boss"))
checar(len(r.json().get("historico", [])) == 2, "comando vê as duas", str(r.status_code))
checar(c.get("/predicoes/historico/11111111111", headers=tok("u-nova")).status_code == 404,
       "empresa sem carteira não vê o de ninguém")


# ── 2. webhook: a chave manda, não o corpo ───────────────────────────────
print("\n— /webhook/pagamento —")
FEEDBACKS.clear(); BANDIT_CHAMADAS.clear()
r = c.post("/webhook/pagamento", headers={"X-API-Key": "k-alfa"},
           json={"cpf": "22222222222", "pagou": True, "valor_recuperado": 9000, "empresa": "beta"})
checar(r.status_code == 200, "a chamada é aceita", str(r.status_code))
checar(FEEDBACKS and FEEDBACKS[0]["empresa"] == "alfa",
       "mas grava na empresa DA CHAVE, não na do corpo",
       f"gravou em {FEEDBACKS[0]['empresa'] if FEEDBACKS else '—'} — era 'beta'")
checar(FEEDBACKS and "predicao_id" not in FEEDBACKS[0],
       "e não liga à predição da beta", "")
checar(BANDIT_CHAMADAS and BANDIT_CHAMADAS[0][1] == "alfa" and BANDIT_CHAMADAS[0][2] is None,
       "o bandit da beta não aprende com isso")

FEEDBACKS.clear()
r = c.post("/webhook/pagamento", headers={"X-API-Key": "k-alfa"},
           json={"cpf": "33333333333", "pagou": True, "empresa": "Alfa"})
checar(r.status_code == 200 and FEEDBACKS[0].get("predicao_id") == "p-dupla-a",
       "nome de exibição no corpo não quebra a integração",
       "o campo é ignorado, não rejeitado")
r = c.post("/webhook/pagamento", headers={"X-API-Key": "k-sem"},
           json={"cpf": "11111111111", "pagou": True})
checar(r.status_code == 403, "chave sem empresa vinculada é recusada", str(r.status_code))
checar(c.post("/webhook/pagamento", headers={"X-API-Key": "inventada"},
              json={"cpf": "1", "pagou": True}).status_code == 401, "chave inexistente segue 401")


# ── 3. o cadastro manda, não o token ─────────────────────────────────────
print("\n— o token prova quem é; o cadastro diz o que pode —")
ROTA_ADMIN = "/auth/usuarios"
r = c.get(ROTA_ADMIN, headers=tok("u-admin"))
checar(r.status_code == 200, "admin ativo acessa a rota de admin (controle)", str(r.status_code))

r = c.get(ROTA_ADMIN, headers=tok("u-fired", "admin", "alfa"))
checar(r.status_code == 401, "admin DESLIGADO é recusado, mesmo com token válido", f"{r.status_code}")

r = c.get(ROTA_ADMIN, headers=tok("u-demoted", "admin", "alfa"))
checar(r.status_code == 403, "admin REBAIXADO no cadastro perde o acesso na hora",
       f"{r.status_code} — o token dizia admin, o cadastro diz operador")

r = c.get(ROTA_ADMIN, headers=tok("u-moved", "admin", "alfa"))
checar(r.status_code == 403,
       "admin REMOVIDO da empresa é recusado, em vez de listar TODAS",
       f"{r.status_code} — empresa vazia significava 'todos os usuários de todos os clientes'")

# rota de comando
ROTA_COMANDO = "/comando/visao-geral"
r = c.get(ROTA_COMANDO, headers=tok("u-boss-off", "comando", ""))
checar(r.status_code == 401, "comando DESLIGADO é recusado", str(r.status_code))
r = c.get(ROTA_COMANDO, headers=tok("u-admin", "comando", ""))
checar(r.status_code == 403,
       "token que ALEGA ser comando, de usuário que no cadastro é admin, é recusado",
       str(r.status_code))
r = c.get(ROTA_COMANDO, headers=tok("fantasma", "comando", ""))
checar(r.status_code == 401, "usuário que nem existe mais é recusado")

# o que muda o papel no cadastro vale na hora, nos dois sentidos
CADASTRO["u-op"]["role"] = "admin"
checar(c.get(ROTA_ADMIN, headers=tok("u-op", "operador", "alfa")).status_code == 200,
       "promovido no cadastro ganha acesso sem esperar o token novo")
CADASTRO["u-op"]["role"] = "operador"

# o empresa_id também vem do cadastro
CADASTRO["u-admin"]["empresa_id"] = "beta"
FEEDBACKS.clear()
r = c.post("/feedback", headers=tok("u-admin", "admin", "alfa"),
           json={"cpf": "22222222222", "pagou": True})
checar(FEEDBACKS and FEEDBACKS[0]["empresa"] == "beta",
       "mudar a empresa no cadastro vale na hora",
       f"gravou em {FEEDBACKS[0]['empresa'] if FEEDBACKS else '—'}; o token ainda dizia alfa")
CADASTRO["u-admin"]["empresa_id"] = "alfa"

# /feedback decide pelo role: um admin rebaixado não pode registrar pagamento manual
FEEDBACKS.clear()
r = c.post("/feedback", headers=tok("u-demoted", "admin", "alfa"),
           json={"cpf": "11111111111", "pagou": True})
checar(r.status_code == 403 and not FEEDBACKS,
       "admin REBAIXADO a operador não registra pagamento manual",
       f"{r.status_code}, gravou {len(FEEDBACKS)} — o token ainda dizia admin")
FEEDBACKS.clear()
r = c.post("/feedback", headers=tok("u-fired", "admin", "alfa"),
           json={"cpf": "11111111111", "pagou": True})
checar(r.status_code == 401 and not FEEDBACKS, "e o desligado também não", str(r.status_code))

# rotas isoladas que só validavam a assinatura
for rotulo, metodo, rota in (("lista conexões", "get", "/conexoes"),
                             ("registra contato", "post", "/contatos"),
                             ("lista contatos do CPF", "get", "/contatos/22222222222")):
    r = getattr(c, metodo)(rota, headers=tok("u-fired", "admin", "alfa"),
                           **({"json": {"cpf": "1", "canal": "telefone", "resultado": "contactado"}}
                              if metodo == "post" else {}))
    checar(r.status_code == 401, f"{rotulo}: usuário desligado é recusado", str(r.status_code))


# ── 4. contatos: falha fechada ───────────────────────────────────────────
print("\n— /contatos —")
r = c.get("/contatos/22222222222", headers=tok("u-moved", "admin", "alfa"))
checar(r.status_code == 403,
       "usuário sem empresa não lista contatos de ninguém",
       f"{r.status_code} — via observação livre, vazaria telefone e nome de parente")
r = c.get("/contatos/22222222222", headers=tok("u-admin"))
checar(r.status_code == 200 and r.json() == [],
       "e quem tem empresa só vê os da própria", str(r.json()))

body = {"cpf": "22222222222", "canal": "telefone", "resultado": "pagou", "valor_recuperado": 5}
r = c.post("/contatos", headers=tok("u-admin"), json=body)
checar(r.status_code == 404,
       "registrar 'pagou' para CPF que só existe em outra empresa é 404",
       f"{r.status_code} — antes a resposta revelava se o CPF existia em QUALQUER empresa")
r = c.post("/contatos", headers=tok("u-nova"), json={**body, "cpf": "11111111111"})
checar(r.status_code == 404, "empresa sem carteira não casa com CPF de ninguém", str(r.status_code))
r = c.post("/contatos", headers=tok("u-moved", "admin", "alfa"), json={**body, "cpf": "11111111111"})
checar(r.status_code == 403, "usuário sem empresa é recusado", str(r.status_code))


# ── 5. confirmar pagamento: falha fechada ────────────────────────────────
print("\n— /devedores/{cpf}/confirmar-pagamento —")
FEEDBACKS.clear()
r = c.post("/devedores/22222222222/confirmar-pagamento", headers=tok("u-nova"), json={})
checar(r.status_code == 404 and not FEEDBACKS,
       "empresa sem carteira não confirma pagamento do CPF de outra",
       f"{r.status_code}, gravou {len(FEEDBACKS)} — o `if cart_ids:` caía em 'sem filtro'")


# ── 6. /upload ───────────────────────────────────────────────────────────
print("\n— /upload —")
csv = ("cpf,valor\n1,2\n").encode()
r = c.post("/upload", files={"file": ("a.csv", io.BytesIO(csv), "text/csv")})
checar(r.status_code in (401, 403), "exige credencial", f"{r.status_code} — era 200 para qualquer um")
r = c.post("/upload", headers={"Authorization": "Bearer lixo"},
           files={"file": ("a.csv", io.BytesIO(csv), "text/csv")})
checar(r.status_code == 401, "e credencial falsa não basta", str(r.status_code))
r = c.post("/upload", headers=tok("u-admin"), files={"file": ("a.csv", io.BytesIO(csv), "text/csv")})
checar(r.status_code == 200 and r.json()["rows"] == 1, "autenticado continua funcionando", str(r.status_code))


# ── 7. nenhuma rota recebe credencial sem usá-la ─────────────────────────
print("\n— a classe de erro, não só as instâncias —")
import ast                                          # noqa: E402

tree = ast.parse((AQUI / "main.py").read_text())


def usa(no, nome):
    return any(isinstance(n, ast.Name) and n.id == nome for n in ast.walk(no))


ociosas = []
so_assinatura = []
for no in ast.walk(tree):
    if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    deco = [d for d in no.decorator_list if isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "put", "patch", "delete")]
    if not deco:
        continue
    rota = f"{deco[0].func.attr.upper()} {ast.literal_eval(deco[0].args[0])}"
    if "credentials" in [a.arg for a in no.args.args] and not any(usa(st, "credentials") for st in no.body):
        ociosas.append(rota)
    chamadas = {n.func.id for st in no.body for n in ast.walk(st)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    if "validar_token" in chamadas and no.name not in ("auth_refresh",):
        so_assinatura.append(rota)

checar(not ociosas, "toda rota que recebe credencial a usa", str(ociosas))
checar(not so_assinatura,
       "nenhuma rota confere só a assinatura do token",
       f"{so_assinatura} (auth_refresh é a exceção: ele mesmo confere o cadastro)")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
