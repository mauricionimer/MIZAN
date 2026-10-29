"""Revisão da frente API: escopo por empresa, cache, login e rotas sensíveis.

    python test_revisao_api.py

Cobre as correções desta frente com um banco falso que imita o Supabase
(filtros eq/in_/is_, range, count) e o TestClient. Dados fictícios:
empresas "alfa" e "beta", CPFs inventados.

Já feitas antes: login (e-mail normalizado, IP real), esqueci a senha com
maiúscula, marca pública limitada por IP, primeiro admin sem senha fixa,
carteiras e conexões pela empresa, COMANDO sem contato, cache de desempenho com
dono antes e empresa na chave, pagamentos só para gestão, registrado_em inteiro.

Novas: /feedbacks/status com o mesmo cache, hora do "já confirmado" em
Brasília, lote e confirmação do COMANDO com empresa escolhida, contatos da
análise só da empresa, operador com a consulta salva, simulador com a política
da empresa, um limiar de acurácia, feedback automático com empresa, db_sync
ligando só na empresa, _empresa_da_carteira única, excluir conta pede senha,
retorno da passagem com caso ocupado = 409.
"""
import contextlib
import io
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import pandas as pd                                # noqa: E402
import main                                        # noqa: E402
import auth                                        # noqa: E402
import limite                                      # noqa: E402
from auth import criar_token, hash_senha           # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── Banco falso ──────────────────────────────────────────────────────────
T: dict = {}            # tabela -> linhas
CONSULTAS: list = []    # (tabela, [(op, coluna, valor)]) de cada execute
FALHAR: set = set()     # tabelas cujo execute levanta erro


def reset():
    T.clear()
    CONSULTAS.clear()
    FALHAR.clear()
    main._cache_store.clear()
    T.update({
        "carteiras": [
            {"id": "c-alfa", "empresa_id": "alfa", "usuario_id": "u-adm-a", "created_at": "2026-10-01"},
            {"id": "c-alfa2", "empresa_id": "alfa", "usuario_id": "u-adm-a", "created_at": "2026-10-02"},
            {"id": "c-beta", "empresa_id": "beta", "usuario_id": "u-adm-b", "created_at": "2026-10-03"},
        ],
        "predicoes": [
            {"id": "p-a1", "carteira_id": "c-alfa", "cpf": "11111111111", "created_at": "2026-10-01",
             "score_recuperabilidade": 45.0, "valor_divida": 1000.0, "nome": "Ana Teste"},
            {"id": "p-b1", "carteira_id": "c-beta", "cpf": "11111111111", "created_at": "2026-10-05",
             "score_recuperabilidade": 90.0, "valor_divida": 9000.0, "nome": "Ana Teste"},
        ],
        "feedbacks": [
            {"id": "f1", "cpf": "11111111111", "pagou": True, "predicao_id": "p-a1", "empresa": "alfa",
             "valor_recuperado": 300, "created_at": "2026-10-10T15:04:05.123+00:00", "registrado_por": "adm"},
        ],
        "conexoes_db": [
            {"id": "cx-alfa", "empresa_id": "alfa", "usuario_id": "u-adm-a", "tipo": "sheets",
             "sheets_id": "planilha-alfa", "sheets_credenciais": {"client_email": "x", "private_key": "y"},
             "query": "SELECT cpf, valor FROM devedores", "created_at": "2026-10-01"},
        ],
        "conexao_permissoes": [{"id": "pm1", "conexao_id": "cx-alfa", "operador_id": "u-op-a"}],
        "usuarios": [{"id": "u-adm-a", "senha_hash": hash_senha("Senha-Forte-123")}],
    })


class Q:
    def __init__(self, tabela):
        self.t = tabela
        self.filtros: list = []
        self._neg = False
        self._op = None          # ("insert", linha) | ("update", dados) | ("delete",)
        self._lim = None
        self._rng = None
        self._ord = None
        self._count = False

    def select(self, *a, **k):
        self._count = k.get("count") == "exact"
        return self

    @property
    def not_(self):
        self._neg = True
        return self

    def eq(self, c, v):
        self.filtros.append(("eq", c, v))
        return self

    def in_(self, c, vs):
        self.filtros.append(("in", c, list(vs)))
        return self

    def is_(self, c, v):
        self.filtros.append(("notnull" if self._neg else "null", c, v))
        self._neg = False
        return self

    def order(self, c, desc=False):
        if self._ord is None:
            self._ord = (c, desc)
        return self

    def limit(self, n):
        self._lim = n
        return self

    def range(self, i, f):
        self._rng = (i, f)
        return self

    def insert(self, linha):
        self._op = ("insert", linha)
        return self

    def upsert(self, linha, **k):
        self._op = ("upsert", linha)
        return self

    def update(self, dados):
        self._op = ("update", dados)
        return self

    def delete(self):
        self._op = ("delete",)
        return self

    def _casa(self, l):
        for op, c, v in self.filtros:
            if op == "eq" and l.get(c) != v:
                return False
            if op == "in" and l.get(c) not in v:
                return False
            if op == "null" and l.get(c) is not None:
                return False
            if op == "notnull" and l.get(c) is None:
                return False
        return True

    def execute(self):
        CONSULTAS.append((self.t, list(self.filtros), self._op[0] if self._op else "select"))
        if self.t in FALHAR:
            raise RuntimeError("banco fora do ar")
        tab = T.setdefault(self.t, [])
        R = lambda d, n=None: type("R", (), {"data": d, "count": n})()   # noqa: E731
        if self._op and self._op[0] in ("insert", "upsert"):
            novas = self._op[1] if isinstance(self._op[1], list) else [self._op[1]]
            feitas = []
            for n in novas:
                n = dict(n)
                n.setdefault("id", f"{self.t}-{len(tab) + 1}")
                n.setdefault("created_at", "2026-10-18T12:00:00+00:00")
                tab.append(n)
                feitas.append(n)
            return R(feitas)
        if self._op and self._op[0] == "update":
            alvo = [l for l in tab if self._casa(l)]
            for l in alvo:
                l.update(self._op[1])
            return R(alvo)
        if self._op and self._op[0] == "delete":
            alvo = [l for l in tab if self._casa(l)]
            T[self.t] = [l for l in tab if l not in alvo]
            return R(alvo)
        d = [l for l in tab if self._casa(l)]
        if self._ord:
            d = sorted(d, key=lambda l: str(l.get(self._ord[0]) or ""), reverse=self._ord[1])
        total = len(d)
        if self._rng:
            d = d[self._rng[0]:self._rng[1] + 1]
        if self._lim is not None:
            d = d[:self._lim]
        return R(d, total if self._count else None)


class DB:
    def table(self, n):
        return Q(n)


main.get_db = lambda: DB()
main._registrar_auditoria = lambda *a, **k: None
main._writeback_pagamento = lambda *a, **k: None
main._fechar_loop_bandit = lambda *a, **k: None
main._cumprir_promessas = lambda *a, **k: None

USUARIOS = {
    "u-adm-a": {"role": "admin", "empresa_id": "alfa"},
    "u-adm-b": {"role": "admin", "empresa_id": "beta"},
    "u-op-a": {"role": "operador", "empresa_id": "alfa"},
    "u-cmd": {"role": "comando", "empresa_id": ""},
    "u-sem": {"role": "admin", "empresa_id": ""},
}
main.buscar_usuario_por_id = lambda uid: ({"id": uid, "ativo": True, **USUARIOS[uid]}
                                          if uid in USUARIOS else None)

c = TestClient(main.app, raise_server_exceptions=False)


def h(uid):
    u = USUARIOS[uid]
    return {"Authorization": "Bearer " + criar_token(
        {"sub": uid, "email": f"{uid}@x.com", "nome": uid, "role": u["role"], "empresa_id": u["empresa_id"]})}


def consultas(tabela, op="select"):
    return [f for t, f, o in CONSULTAS if t == tabela and o == op]


# ═════════════ JÁ FEITAS ═════════════════════════════════════════════════
print("— login: e-mail normalizado e IP real —")
reset()
main._tentativas_login.clear()
main.buscar_usuario = lambda e: None
for email in ["Ana@X.com", "ANA@x.com", " ana@x.com", "ana@X.COM", "Ana@x.Com"]:
    c.post("/auth/login", json={"email": email, "senha": "errada"}, headers={"X-Forwarded-For": "9.9.9.9"})
r = c.post("/auth/login", json={"email": "ana@x.com", "senha": "errada"}, headers={"X-Forwarded-For": "9.9.9.9"})
checar(r.status_code == 429, "maiúsculas e espaços contam no mesmo limite do e-mail", str(r.status_code))
r = c.post("/auth/login", json={"email": "ana@x.com", "senha": "errada"},
           headers={"X-Forwarded-For": "8.8.8.8, 10.0.0.1"})
# Decisão D1 do plano de segurança (S2): o limite é pelo e-mail, porque o IP vem
# de cabeçalho forjável. Trocar o X-Forwarded-For não pode abrir cota nova.
checar(r.status_code == 429, "outro IP (o primeiro do X-Forwarded-For) HERDA o bloqueio do e-mail", str(r.status_code))
checar(limite.primeiro_ip("1.2.3.4, 10.0.0.1", "10.0.0.1") == "1.2.3.4"
       and limite.primeiro_ip(None, "10.0.0.1") == "10.0.0.1", "primeiro_ip lê o cliente, não o proxy")

print("\n— esqueci a senha com maiúscula —")
pedidos = []
main.criar_reset_token = lambda e: pedidos.append(e) or None
r = c.post("/auth/esqueci-senha", json={"email": "  Bia@Teste.COM "})
checar(r.status_code == 200 and pedidos == ["bia@teste.com"], "o token é pedido para o e-mail normalizado",
       str(pedidos))

print("\n— marca pública limitada por IP —")
limite.LIMITADOR._marcas.clear()
cods = [c.get("/empresa/marca", headers={"X-Forwarded-For": "7.7.7.7"}).status_code for _ in range(61)]
checar(cods[-1] == 429 and 429 not in cods[:60], "o mesmo IP passa de 60 consultas e leva 429", str(cods[-3:]))
r = c.get("/empresa/marca", headers={"X-Forwarded-For": "6.6.6.6"})
checar(r.status_code != 429, "outro IP segue consultando", str(r.status_code))

print("\n— primeiro admin sem senha fixa em produção —")
_antes = os.environ.pop("ADMIN_SENHA", None)
s, origem = auth._senha_do_primeiro_admin()
checar(origem == "aleatoria" and s != "mizan123" and len(s) >= 20, "sem ADMIN_SENHA: senha aleatória", origem)
os.environ["ADMIN_SENHA"] = "123"
checar(auth._senha_do_primeiro_admin()[1] == "aleatoria", "ADMIN_SENHA fraca é ignorada")
os.environ.pop("ADMIN_SENHA")
if _antes is not None:
    os.environ["ADMIN_SENHA"] = _antes

print("\n— carteiras pela empresa —")
reset()
r = c.get("/carteiras", headers=h("u-adm-a"))
ids = {x["id"] for x in r.json()} if r.status_code == 200 else set()
checar(ids == {"c-alfa", "c-alfa2"}, "admin vê só as carteiras da empresa", str(ids))
checar(r.headers.get("X-Total-Count") == "2", "e o total vem no cabeçalho", str(r.headers.get("X-Total-Count")))
r = c.get("/carteiras?limite=1&offset=1", headers=h("u-adm-a"))
checar(r.status_code == 200 and len(r.json()) == 1, "a lista pagina")
T["carteiras"].append({"id": "c-alfa3", "empresa_id": "alfa", "usuario_id": "u-op-a", "created_at": "2026-10-04"})
r = c.get("/carteiras?meus=true&limite=1", headers=h("u-adm-a"))
checar(r.status_code == 200 and [x["id"] for x in r.json()] == ["c-alfa2"],
       "meus=true devolve a última carteira da própria pessoa", str(r.json() if r.status_code == 200 else r.status_code))
r = c.get("/carteiras?meus=true", headers=h("u-op-a"))
checar(r.status_code == 200 and [x["id"] for x in r.json()] == ["c-alfa3"],
       "e não traz a de outra pessoa da mesma empresa", str(r.json() if r.status_code == 200 else r.status_code))
T["carteiras"].pop()
r = c.get("/carteiras", headers=h("u-sem"))
checar(r.status_code == 403, "quem está sem empresa não cai no filtro por usuario_id", str(r.status_code))
r = c.get("/carteiras/c-beta", headers=h("u-adm-a"))
checar(r.status_code == 403, "admin da alfa não abre carteira da beta", str(r.status_code))
r = c.get("/carteiras/c-beta", headers=h("u-cmd"))
checar(r.status_code != 403, "COMANDO abre qualquer uma", str(r.status_code))

print("\n— conexões só pela empresa —")
reset()
r = c.get("/conexoes", headers=h("u-adm-b"))
checar(r.status_code == 200 and r.json() == [], "admin da beta não vê a conexão da alfa")
try:
    main._conexao_usavel(DB(), "cx-alfa", {"sub": "u-adm-a", "role": "admin", "empresa_id": "beta"})
    usou = True
except main.HTTPException as e:
    usou = e.status_code != 403
checar(not usou, "quem criou a conexão e mudou de empresa não a usa mais")

print("\n— COMANDO não grava contato —")
r = c.post("/contatos", headers=h("u-cmd"), json={"cpf": "11111111111", "canal": "telefone",
                                                     "resultado": "sem_resposta"})
checar(r.status_code == 403, "COMANDO sem empresa recebe 403", str(r.status_code))

print("\n— cache de desempenho: dono antes, empresa na chave —")
reset()
r = c.get("/performance?carteira_id=c-alfa", headers=h("u-adm-a"))
checar(r.status_code == 200 and r.json().get("total_feedbacks") == 1, "o dono lê (e enche o cache)")
r = c.get("/performance?carteira_id=c-alfa", headers=h("u-adm-b"))
checar(r.status_code == 403, "outra empresa com o mesmo carteira_id não recebe o cache", str(r.status_code))
r = c.get("/performance/pagamentos?carteira_id=c-alfa", headers=h("u-adm-a"))
checar(r.status_code == 200 and r.json() and r.json()[0]["registrado_em"] == "2026-10-10T15:04:05.123+00:00",
       "pagamentos: registrado_em inteiro, com fuso", str(r.json()[:1]))
r = c.get("/performance/pagamentos?carteira_id=c-alfa", headers=h("u-adm-b"))
checar(r.status_code == 403, "pagamentos: dono conferido antes do cache", str(r.status_code))
r = c.get("/performance/pagamentos", headers=h("u-op-a"))
checar(r.status_code == 200 and r.json() == [], "operador não vê nome e CPF de quem pagou")
checar(all(k.endswith(":alfa") or k.count(":") == 1 for k in main._cache_store),
       "a chave do cache leva a empresa", str(list(main._cache_store)))

# ═════════════ NOVAS ═════════════════════════════════════════════════════
print("\n— /feedbacks/status: mesmo conserto de cache —")
reset()
r = c.get("/feedbacks/status?carteira_id=c-alfa", headers=h("u-adm-a"))
checar(r.status_code == 200 and "11111111111" in r.json(), "o dono lê o status")
checar(r.json()["11111111111"]["registrado_em"] == "2026-10-10T15:04:05.123+00:00", "registrado_em inteiro")
r = c.get("/feedbacks/status?carteira_id=c-alfa", headers=h("u-adm-b"))
checar(r.status_code == 403, "outra empresa não lê o cache do dono", str(r.status_code))
checar("fb_status:c-alfa:alfa" in main._cache_store, "chave com a empresa", str(list(main._cache_store)))

print("\n— hora do 'já confirmado' em Brasília —")
checar(main._hora_brasilia("2026-10-10T15:04:05.123+00:00") == "2026-10-10 12:04", "UTC vira hora de Brasília")
checar(main._hora_brasilia("2026-10-10T15:04:05") == "2026-10-10 12:04", "sem fuso é tratado como UTC")
checar(main._hora_brasilia(None) == "", "vazio fica vazio")

print("\n— /feedback/lote do COMANDO —")


def lote(headers, q=""):
    csv = "cpf,pagou\n11111111111,sim\n"
    return c.post("/feedback/lote" + q, headers=headers,
                  files={"file": ("f.csv", io.BytesIO(csv.encode()), "text/csv")})


reset()
r = lote(h("u-cmd"))
checar(r.status_code == 400, "sem empresa escolhida: 400", str(r.status_code))
checar(len(T["feedbacks"]) == 1, "e nada gravado (antes ia com o nome do usuário como empresa)")
r = lote(h("u-cmd"), "?empresa_id=beta")
novo = T["feedbacks"][-1]
checar(r.status_code == 200 and novo.get("empresa") == "beta" and novo.get("predicao_id") == "p-b1",
       "com a empresa: grava nela e liga à predição dela", str(novo))
r = lote(h("u-adm-a"), "?empresa_id=beta")
checar(T["feedbacks"][-1].get("empresa") == "alfa", "admin ignora o empresa_id da query (vale a dele)")

print("\n— confirmar pagamento do COMANDO —")
reset()
T["feedbacks"].clear()
apagados = []
main._cache_del_prefix = lambda p: apagados.append(p)
url = "/devedores/11111111111/confirmar-pagamento"
r = c.post(url, json={"valor_recuperado": 10}, headers=h("u-cmd"))
checar(r.status_code == 400 and not T["feedbacks"], "sem empresa: 400", str(r.status_code))
r = c.post(url + "?empresa_id=beta", json={"valor_recuperado": 10}, headers=h("u-cmd"))
checar(r.status_code == 200 and T["feedbacks"][-1]["empresa"] == "beta"
       and T["feedbacks"][-1]["predicao_id"] == "p-b1", "grava na beta e liga à predição da beta", r.text[:150])
checar("fb_status:beta" in apagados and "perf:c-beta" in apagados, "invalida o cache da beta", str(apagados))
r = c.post(url + "?empresa_id=beta", json={"valor_recuperado": 10}, headers=h("u-cmd"))
checar(r.status_code == 409, "idempotência na empresa escolhida: a segunda vez é 409", str(r.status_code))
checar("2026-10-18 09:00" in r.json().get("detail", ""), "a mensagem mostra a hora de Brasília (12:00 UTC = 09:00)",
       r.json().get("detail") or "")
r = c.post(url + "?empresa_id=alfa", json={"valor_recuperado": 10}, headers=h("u-cmd"))
checar(r.status_code == 200 and T["feedbacks"][-1]["predicao_id"] == "p-a1",
       "o pagamento da beta não bloqueia o da alfa", str(r.status_code))
main._cache_del_prefix = lambda p: [main._cache_store.pop(k) for k in list(main._cache_store) if k.startswith(p)]

print("\n— contatos na análise: só da empresa —")
reset()
T["contatos"] = [{"cpf": "11111111111", "empresa_id": "beta", "resultado": "acordo_fechado",
                  "created_at": None}]
for emp in ("alfa", None):
    CONSULTAS.clear()
    try:
        main._analisar_df(pd.DataFrame({"cpf": ["11111111111"]}), "x.csv", _empresa_id=emp)
    except main.HTTPException:
        pass                                   # 422 por falta de colunas: o enriquecimento já rodou
    filtros = consultas("contatos")
    if emp:
        checar(filtros and ("eq", "empresa_id", "alfa") in filtros[0], "a consulta filtra a empresa", str(filtros))
    else:
        checar(not filtros, "sem empresa, não consulta contatos de ninguém", str(filtros))
checar("x.notna().any()" in Path(main.__file__).read_text(encoding="utf-8"), "data vazia conferida com notna")

print("\n— operador usando conexão salva —")
reset()
conn = main.ConexaoDB(tipo="sheets", conexao_id="cx-alfa", query="SELECT * FROM senhas")
main._resolver_credenciais(conn, {"sub": "u-op-a", "role": "operador", "empresa_id": "alfa"})
checar(conn.query == "SELECT cpf, valor FROM devedores", "operador: vale a consulta salva", conn.query)
conn = main.ConexaoDB(tipo="sheets", conexao_id="cx-alfa", query="SELECT * FROM outra")
main._resolver_credenciais(conn, {"sub": "u-adm-a", "role": "admin", "empresa_id": "alfa"})
checar(conn.query == "SELECT * FROM outra", "admin pode trocar a consulta")

_ler, _anal = main._ler_google_sheets, main._analisar_df
main._ler_google_sheets = lambda conn: pd.DataFrame({"cpf": ["1"]})
main._analisar_df = lambda *a, **k: {"resumo": {"carteira_id": "c-nova"}}
r = c.post("/analisar/db", json={"tipo": "sheets", "conexao_id": "cx-alfa"}, headers=h("u-op-a"))
checar(r.status_code == 200 and T["conexoes_db"][0].get("carteira_id") is None,
       "operador não reaponta a carteira da conexão", f"{r.status_code} {T['conexoes_db'][0].get('carteira_id')}")
r = c.post("/analisar/db", json={"tipo": "sheets", "conexao_id": "cx-alfa"}, headers=h("u-adm-a"))
checar(r.status_code == 200 and T["conexoes_db"][0].get("carteira_id") == "c-nova", "admin reaponta")
_q_original = Q.execute


def _update_falha(self):
    if self.t == "conexoes_db" and self._op and self._op[0] == "update":
        raise RuntimeError("timeout")
    return _q_original(self)


Q.execute = _update_falha
saida = io.StringIO()
with contextlib.redirect_stdout(saida):
    r = c.post("/analisar/db", json={"tipo": "sheets", "conexao_id": "cx-alfa"}, headers=h("u-adm-a"))
Q.execute = _q_original
checar(r.status_code == 200 and "não religou a conexão" in saida.getvalue(),
       "falha ao religar fica registrada (não some num except: pass)", saida.getvalue()[-120:])
main._ler_google_sheets, main._analisar_df = _ler, _anal

print("\n— simulador do COMANDO com a política da empresa —")
reset()
politicas = []


class _Pare(Exception):
    pass


def _pol(emp):
    politicas.append(emp)
    raise _Pare()


_pol_orig = main._politica_proposta
main._politica_proposta = _pol
try:
    main._contexto_propostas("11111111111", {"sub": "u-cmd", "role": "comando", "empresa_id": ""}, None)
except _Pare:
    pass
main._politica_proposta = _pol_orig
checar(politicas and politicas[0] in ("alfa", "beta"), "a política vem da empresa do devedor, não da vazia",
       str(politicas))

print("\n— acurácia: um limiar só —")
checar(main.LIMIAR_ACERTO_SCORE == 50, "LIMIAR_ACERTO_SCORE = 50")
checar(main._acertou(50, True) and main._acertou(49, False) and not main._acertou(45, True),
       "corte em 50 para os dois lados")
fonte = Path(main.__file__).read_text(encoding="utf-8")
checar("score >= 40 and pagou" not in fonte and "score >= 50 and pagou" not in fonte,
       "/performance e /admin/modelos usam _acertou")
reset()
r = c.get("/performance?carteira_id=c-alfa", headers=h("u-adm-a"))
checar(r.json().get("acuracia_geral") == 0.0, "score 45 que pagou conta como erro em /performance",
       str(r.json().get("acuracia_geral")))

print("\n— feedback automático com empresa —")
checar('fb_row["empresa"] = _empresa_id' in fonte, "a coluna 'pagou' grava fb_row['empresa']")

print("\n— db_sync liga só na empresa —")
import db as _db_mod                                 # noqa: E402
import db_sync                                       # noqa: E402
import sqlalchemy                                    # noqa: E402

reset()
gravado_cfg = []
_rs, _ce, _gd = pd.read_sql, sqlalchemy.create_engine, _db_mod.get_db
pd.read_sql = lambda *a, **k: pd.DataFrame({"cpf": ["11111111111"], "pagou": ["sim"], "valor_recuperado": [5.0]})
db_sync.salvar_config = lambda cfg: gravado_cfg.append(cfg)
_db_mod.get_db = lambda: DB()
for empresa, esperado in (("alfa", "p-a1"), ("", None)):
    db_sync.carregar_config = lambda e=empresa: {**db_sync._PADRAO, "ativo": True, "tipo": "sqlite",
                                                 "banco": ":memory:", "empresa_id": e}
    T["feedbacks"].clear()
    res = db_sync.sincronizar()
    fb = T["feedbacks"][-1] if T["feedbacks"] else {}
    checar(res.get("sincronizou") and fb.get("predicao_id") == esperado,
           f"empresa {empresa or '(nenhuma)'}: liga em {esperado}", str(fb))
pd.read_sql, sqlalchemy.create_engine, _db_mod.get_db = _rs, _ce, _gd

print("\n— _empresa_da_carteira única —")
checar(fonte.count("def _empresa_da_carteira(") == 1, "uma definição só")
reset()
checar(main._empresa_da_carteira(DB(), "c-beta") == "beta" and main._empresa_da_carteira(DB(), None) == "",
       "lê a empresa e aceita id vazio")
FALHAR.add("carteiras")
try:
    main._empresa_da_carteira(DB(), "c-beta")
    propagou = False
except RuntimeError:
    propagou = True
checar(propagou, "erro do banco sobe")
checar(main._empresa_da_carteira_ou_vazio(DB(), "c-beta") == "", "a variante tolerante devolve vazio")

print("\n— DELETE /auth/me pede a senha —")
reset()
main._tentativas_login.clear()
auth._ultimo_comando_ativo = lambda db, uid: False
r = c.request("DELETE", "/auth/me", headers=h("u-adm-a"))
checar(r.status_code == 422, "sem corpo não apaga", str(r.status_code))
r = c.request("DELETE", "/auth/me", headers=h("u-adm-a"), json={"senha": "errada"})
checar(r.status_code == 401 and T["usuarios"], "senha errada: 401 e a conta fica", str(r.status_code))
r = c.request("DELETE", "/auth/me", headers=h("u-adm-a"), json={"senha": "Senha-Forte-123"})
checar(r.status_code == 200 and not T["usuarios"], "senha certa apaga", str(r.status_code))

print("\n— retorno da passagem com caso ocupado —")
from agente import api as agente_api                  # noqa: E402

Ocupado = getattr(agente_api, "CasoOcupado", RuntimeError)
_reg = agente_api.registrar_retorno_passagem


def _ocupado(*a, **k):
    raise Ocupado("O agente está processando este caso agora.")


agente_api.registrar_retorno_passagem = _ocupado
r = c.post("/agente/passagem/p-a1/retorno", headers=h("u-adm-a"), json={"ajudou": True})
checar(r.status_code == 409, "caso ocupado vira 409, não 500", str(r.status_code))
agente_api.registrar_retorno_passagem = _reg

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
