"""Prova dinâmica do plano de segurança (docs: PLANO_SEGURANCA.md). Ataca o app em memória.

    python test_seguranca_plano.py

Sobe um servidor "interno" para o SSRF, faz força bruta trocando o IP, conta
chamadas ao PBKDF2, manda 40 mensagens pelo Telegram e conta rodadas de IA.
Cada verificação tem um CONTROLE: o caminho legítimo continua funcionando (sem
controle, "recusar tudo" passaria).

Simulados: banco (Supabase), provedor de IA, Telegram e e-mail. NÃO são
substituídas as funções de segurança testadas (_usuario_autenticado,
_buscar_api_key, o limitador, a validação de token, conferir_login...).
"""
import base64
import copy
import hashlib
import io
import json
import os
import secrets
import sys
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from cryptography.fernet import Fernet                                     # noqa: E402

os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x",
                  JWT_SECRET="segredo-de-teste-com-mais-de-32-caracteres-ok",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode(), MIZAN_AGENTE_ATIVO="1")
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_IA_RODADAS_CASO", "MIZAN_IA_JANELA_CASO_MIN"):
    os.environ.pop(v, None)

import pandas as pd                                                       # noqa: E402
import auth                                                               # noqa: E402
import db as _db_mod                                                      # noqa: E402
import main                                                               # noqa: E402
from auth import criar_token, hash_senha, versao_da_senha                 # noqa: E402
from fastapi.testclient import TestClient                                 # noqa: E402

falhas = 0


def checar(cond, item, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  [{item}] {titulo}" + (f"  — {detalhe}" if detalhe and not cond else ""))
    if not cond:
        falhas += 1


# ── Banco falso (imita o cliente do Supabase) ────────────────────────────────
T: dict = {}
CONSULTAS: list = []          # (tabela, filtros, operação)
QUEBRAR_COLUNA: set = set()
PADROES = {"reset_tokens": {"usado": False}}   # DEFAULT das colunas no schema.sql   # colunas cujo filtro levanta "column does not exist"


class Q:
    def __init__(self, tabela):
        self.t, self.filtros, self._op, self._lim = tabela, [], None, None

    def select(self, *a, **k): return self
    def eq(self, c, v): self.filtros.append(("eq", c, v)); return self
    def neq(self, c, v): self.filtros.append(("neq", c, v)); return self
    def in_(self, c, vs): self.filtros.append(("in", c, list(vs))); return self
    def order(self, *a, **k): return self
    def limit(self, n): self._lim = n; return self
    def range(self, *a): return self
    def insert(self, linha): self._op = ("insert", linha); return self
    def upsert(self, linha, **k): self._op = ("upsert", linha); return self
    def update(self, dados): self._op = ("update", dados); return self
    def delete(self): self._op = ("delete",); return self

    def _casa(self, l):
        for op, c, v in self.filtros:
            if (op == "eq" and l.get(c) != v) or (op == "neq" and l.get(c) == v) or (op == "in" and l.get(c) not in v):
                return False
        return True

    def execute(self):
        CONSULTAS.append((self.t, list(self.filtros), self._op[0] if self._op else "select"))
        for _, c, _ in self.filtros:
            if c in QUEBRAR_COLUNA:
                raise RuntimeError(f'column {self.t}.{c} does not exist')
        tab = T.setdefault(self.t, [])
        # Cópias, como o Supabase: a rota mexer no que recebeu não altera o "banco".
        R = lambda d: SimpleNamespace(data=copy.deepcopy(d), count=len(d))          # noqa: E731
        if self._op and self._op[0] in ("insert", "upsert"):
            novas = self._op[1] if isinstance(self._op[1], list) else [self._op[1]]
            feitas = []
            for n in novas:
                n = {"id": f"{self.t}-{len(tab) + 1}", **PADROES.get(self.t, {}), **copy.deepcopy(n)}
                if self._op[0] == "upsert" and "chave" in n:
                    T[self.t] = tab = [l for l in tab if l.get("chave") != n["chave"]]
                tab.append(n)
                feitas.append(n)
            return R(feitas)
        alvo = [l for l in tab if self._casa(l)]
        if self._op and self._op[0] == "update":
            for l in alvo:
                l.update(copy.deepcopy(self._op[1]))
            return R(alvo)
        if self._op and self._op[0] == "delete":
            T[self.t] = [l for l in tab if l not in alvo]
            return R(alvo)
        return R(alvo[:self._lim] if self._lim is not None else alvo)


class DB:
    def table(self, n): return Q(n)
    storage = None


main.get_db = lambda: DB()
_db_mod.get_db = lambda: DB()                 # auth.py busca o banco por aqui
main._registrar_auditoria = lambda *a, **k: None

SENHA = "Senha-Forte-123"


def usuario(uid, role="admin", empresa="alfa", ativo=True, senha=SENHA, h=None):
    return {"id": uid, "email": f"{uid}@x.com", "nome": uid, "role": role, "empresa_id": empresa,
            "ativo": ativo, "senha_hash": h or hash_senha(senha)}


def reset():
    T.clear()
    CONSULTAS.clear()
    QUEBRAR_COLUNA.clear()
    main._tentativas_login.clear()
    main._cache_store.clear()
    main._limite.LIMITADOR.limpar()
    T["usuarios"] = [usuario("adm-a"), usuario("adm-b", empresa="beta"), usuario("inativo", ativo=False)]


def tok(uid, **extra):
    u = next(x for x in T["usuarios"] if x["id"] == uid)
    return {"Authorization": "Bearer " + criar_token({"sub": uid, "email": u["email"], "nome": uid, "role": u["role"],
                                                      "empresa_id": u["empresa_id"], "sv": versao_da_senha(u),
                                                      "auth_time": int(time.time()), **extra})}


def payload_do(token):
    p = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


c = TestClient(main.app, raise_server_exceptions=False)


# ═════ S1: SSRF pelo token_uri ═══════════════════════════════════════════════
print("— S1: credencial do Google só fala com o Google —")
reset()
ACESSOS = []


class Interno(BaseHTTPRequestHandler):
    def do_POST(self):
        ACESSOS.append(self.path)
        corpo = json.dumps({"segredo": "conteudo-do-servico-interno"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a): pass


srv = HTTPServer(("127.0.0.1", 0), Interno)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URI_INTERNA = f"http://127.0.0.1:{srv.server_port}/token"

from cryptography.hazmat.primitives import serialization                  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa                 # noqa: E402

_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def cred(**k):
    return {"type": "service_account", "project_id": "p", "private_key_id": "1", "private_key": _pem,
            "client_email": "leitor@p.iam.gserviceaccount.com", "client_id": "1",
            "token_uri": "https://oauth2.googleapis.com/token", **k}


# Controle da montagem: sem a trava, o google-auth chega mesmo ao servidor interno.
from google.oauth2.service_account import Credentials                     # noqa: E402
import google.auth.transport.requests as _gtr                             # noqa: E402

try:
    Credentials.from_service_account_info(cred(token_uri=URI_INTERNA),
                                          scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
                                          ).refresh(_gtr.Request())
except Exception:
    pass
checar(len(ACESSOS) == 1, "S1", "controle da montagem: google-auth sem trava chega ao servidor interno", str(ACESSOS))
ACESSOS.clear()

r = c.post("/testar-db", json={"tipo": "sheets", "sheets_id": "x", "sheets_credenciais": cred(token_uri=URI_INTERNA)},
           headers=tok("adm-a"))
checar(r.status_code == 400 and not ACESSOS and "conteudo-do-servico-interno" not in r.text,
       "S1", "/testar-db com JSON novo: 400, sem requisição ao interno", f"{r.status_code} {ACESSOS} {r.text[:120]}")
T["conexoes_db"] = [{"id": "cx-ruim", "empresa_id": "alfa", "tipo": "sheets", "sheets_id": "x",
                     "sheets_credenciais": cred(token_uri=URI_INTERNA)}]
r = c.post("/testar-db", json={"tipo": "sheets", "conexao_id": "cx-ruim"}, headers=tok("adm-a"))
checar(r.status_code == 400 and not ACESSOS, "S1", "conexão já salva com token_uri interno: barrada no uso",
       f"{r.status_code} {ACESSOS} {r.text[:120]}")
for ruim, nome in ((cred(token_uri=URI_INTERNA), "token_uri"), (cred(universe_domain="evil.com"), "universe_domain"),
                   (cred(client_email="a@gmail.com"), "client_email"), (cred(type="authorized_user"), "type")):
    r = c.post("/conexoes", json={"nome": "s", "tipo": "sheets", "sheets_id": "x", "sheets_credenciais": ruim},
               headers=tok("adm-a"))
    checar(r.status_code == 400, "S1", f"/conexoes recusa credencial com {nome} errado", f"{r.status_code} {r.text[:100]}")
r = c.post("/conexoes", json={"nome": "s", "tipo": "sheets", "sheets_id": "x", "sheets_credenciais": cred()},
           headers=tok("adm-a"))
salva = [x for x in T.get("conexoes_db", []) if x.get("nome") == "s"]
checar(r.status_code == 200 and salva, "S1", "controle: credencial com token_uri do Google é salva", f"{r.status_code} {r.text[:120]}")
if salva:
    guardada = main._credencial_sheets_salva(salva[0])
    checar(guardada["token_uri"] == "https://oauth2.googleapis.com/token" and "universe_domain" not in guardada,
           "S1", "o que fica guardado é a credencial limpa")
checar(not ACESSOS, "S1", "nenhuma requisição chegou ao servidor interno", str(ACESSOS))
srv.shutdown()


# ═════ S2: força bruta trocando o IP ═════════════════════════════════════════
print("\n— S2: limite de login pelo e-mail, não pelo IP —")
reset()


def tentar(email, senha, n, ip0=1):
    return [c.post("/auth/login", json={"email": email, "senha": senha},
                   headers={"X-Forwarded-For": f"203.0.113.{ip0 + i}"}) for i in range(n)]


rs = tentar("adm-a@x.com", "errada", 8)
cods = [r.status_code for r in rs]
checar(cods == [401] * 5 + [429] * 3, "S2", "8 tentativas, IP diferente em cada: 5 × 401 e depois 429", str(cods))
r = c.post("/auth/login", json={"email": "adm-a@x.com", "senha": SENHA}, headers={"X-Forwarded-For": "198.51.100.9"})
checar(r.status_code == 429, "S2", "nem a senha certa entra durante o bloqueio (por e-mail)", str(r.status_code))
r = c.post("/auth/login", json={"email": "adm-b@x.com", "senha": SENHA}, headers={"X-Forwarded-For": "203.0.113.1"})
checar(r.status_code == 200, "S2", "controle: outra conta continua entrando", str(r.status_code))
rs2 = tentar("ninguem@x.com", "errada", 8, ip0=50)
checar([r.status_code for r in rs2] == cods and [r.json() for r in rs2] == [r.json() for r in rs],
       "S2", "e-mail inexistente recebe exatamente a mesma sequência", str([r.status_code for r in rs2]))
reset()
cods_ip = [c.post("/auth/login", json={"email": f"e{i}@x.com", "senha": "x"},
                  headers={"X-Forwarded-For": "192.0.2.7"}).status_code for i in range(32)]
checar(cods_ip[:30] == [401] * 30 and cods_ip[30:] == [429, 429], "S2", "um IP, muitos e-mails: 429 depois de 30",
       str(cods_ip[-4:]))
reset()
for i in range(main._RATE_MAX_CHAVES + 50):
    main._registrar_tentativa(f"login:email:x{i}@x.com")
checar(len(main._tentativas_login) <= main._RATE_MAX_CHAVES, "S2", "o registro de tentativas tem teto de chaves",
       str(len(main._tentativas_login)))
reset()
tentar("adm-a@x.com", "errada", 5)
token_reset = auth.criar_reset_token("adm-a@x.com")
r = c.post("/auth/redefinir-senha", json={"token": token_reset, "nova_senha": "Nova-Senha-456"})
r2 = c.post("/auth/login", json={"email": "adm-a@x.com", "senha": "Nova-Senha-456"})
checar(r.status_code == 200 and r2.status_code == 200, "S2", "redefinir a senha limpa o bloqueio do e-mail",
       f"{r.status_code} {r2.status_code}")


# ═════ S3: chave de API só pelo hash ═════════════════════════════════════════
print("\n— S3: chave de API só pelo hash —")
reset()
T["api_keys"] = [{"id": "k-velha", "empresa_id": "alfa", "api_key": "mizan_test_vazada", "api_key_hash": None,
                  "ativa": True},
                 {"id": "k-nova", "empresa_id": "alfa", "api_key_hash": main._hash_api_key("mizan_chave_boa"),
                  "ativa": True}]
corpo = {"cpf": "12345678909", "pagou": True, "valor_recuperado": 10}
r = c.post("/webhook/pagamento", json=corpo, headers={"X-API-Key": "mizan_test_vazada"})
checar(r.status_code == 401, "S3", "chave que só existe em texto puro: 401 no /webhook/pagamento", str(r.status_code))
checar(not any(c_ == "api_key" for t, fs, _ in CONSULTAS if t == "api_keys" for _, c_, _ in fs),
       "S3", "a busca nunca filtra pela coluna api_key")
r = c.post("/webhook/pagamento", json=corpo, headers={"X-API-Key": "mizan_chave_boa"})
checar(r.status_code != 401, "S3", "controle: chave pelo hash autentica", str(r.status_code))
QUEBRAR_COLUNA.add("api_key_hash")
checar(main._buscar_api_key(DB(), "mizan_test_vazada") is None and main._buscar_api_key(DB(), "mizan_chave_boa") is None,
       "S3", "sem a coluna de hash, nada entra (falha fechada)")


# ═════ S4: exceção crua na resposta ══════════════════════════════════════════
print("\n— S4: falha interna não vaza na resposta —")
reset()
SEGREDO = "SEGREDO_INTERNO_9f3 host=10.0.0.5 senha=hunter2"
_orig_url = main._construir_url_db


def _explode(conn):
    raise RuntimeError(SEGREDO)


main._construir_url_db = _explode
r = c.post("/testar-db", json={"tipo": "postgres", "host": "db.exemplo.com", "banco": "b", "usuario": "u",
                               "senha": "s", "query": "SELECT 1"}, headers=tok("adm-a"))
main._construir_url_db = _orig_url
import re                                                                 # noqa: E402
checar(r.status_code == 503 and "SEGREDO_INTERNO" not in r.text and "10.0.0.5" not in r.text and "hunter2" not in r.text,
       "S4", "a mensagem da exceção não aparece na resposta", r.text[:160])
checar(bool(re.search(r"Código: [0-9a-f]{8}", r.text)), "S4", "a resposta traz o código de 8 caracteres", r.text[:160])


# ═════ S6: documentação fechada em produção ══════════════════════════════════
print("\n— S6: /docs fechado em produção —")
for rota in ("/docs", "/redoc", "/openapi.json"):
    checar(c.get(rota).status_code == 404, "S6", f"{rota} dá 404")
checar(c.get("/health").status_code == 200, "S6", "controle: /health continua 200")


# ═════ S7: tempo do login não revela o e-mail ════════════════════════════════
print("\n— S7: um PBKDF2 por login, exista o e-mail ou não —")
reset()
_pbkdf2_real = hashlib.pbkdf2_hmac
CONTA = [0]


def _contando(*a, **k):
    CONTA[0] += 1
    return _pbkdf2_real(*a, **k)


c.post("/auth/login", json={"email": "aquecer@x.com", "senha": "x"})   # o hash fictício é calculado uma vez
contagens, respostas = {}, {}
hashlib.pbkdf2_hmac = _contando
try:
    for nome, email in (("existente", "adm-a@x.com"), ("inexistente", "fulano@x.com"), ("desativado", "inativo@x.com")):
        main._tentativas_login.clear()
        CONTA[0] = 0
        r = c.post("/auth/login", json={"email": email, "senha": "errada"})
        contagens[nome], respostas[nome] = CONTA[0], (r.status_code, r.json())
finally:
    hashlib.pbkdf2_hmac = _pbkdf2_real
checar(len(set(contagens.values())) == 1 and list(contagens.values())[0] == 1, "S7",
       "mesmo número de PBKDF2 (1) nos três casos", str(contagens))
checar(len(set(json.dumps(v) for v in respostas.values())) == 1, "S7", "resposta idêntica nos três casos",
       str(respostas))


# ═════ S8: custo do hash ═════════════════════════════════════════════════════
print("\n— S8: PBKDF2 com 600 mil iterações —")
reset()
h = hash_senha("abc12345")
partes = h.split("$")
checar(partes[0] == "pbkdf2_sha256" and int(partes[1]) >= 600_000, "S8", "hash novo com >= 600 mil iterações", h[:30])
sal = secrets.token_hex(16)
legado = f"{sal}${_pbkdf2_real('sha256', SENHA.encode(), sal.encode(), 100_000).hex()}"
T["usuarios"].append(usuario("velho", h=legado))
r = c.post("/auth/login", json={"email": "velho@x.com", "senha": SENHA})
checar(r.status_code == 200, "S8", "hash antigo continua entrando", str(r.status_code))
novo = next(u for u in T["usuarios"] if u["id"] == "velho")["senha_hash"]
checar(novo.startswith("pbkdf2_sha256$600000$") and auth.verificar_senha(SENHA, novo), "S8", "o login regrava o hash",
       novo[:30])
if r.status_code == 200:
    r2 = c.get("/auth/me", headers={"Authorization": "Bearer " + r.json()["token"]})
    checar(r2.status_code == 200, "S8", "o token emitido nesse login funciona no /auth/me", str(r2.status_code))


# ═════ S9: sessão com teto ═══════════════════════════════════════════════════
print("\n— S9: /auth/refresh não renova para sempre —")
reset()
r = c.post("/auth/login", json={"email": "adm-a@x.com", "senha": SENHA})
t1 = r.json().get("token", "")
at = payload_do(t1).get("auth_time") if t1 else None
checar(isinstance(at, int) and abs(at - time.time()) < 60, "S9", "o login grava auth_time no token", str(at))
time.sleep(1.1)
r = c.post("/auth/refresh", headers={"Authorization": "Bearer " + t1})
checar(r.status_code == 200 and payload_do(r.json()["token"]).get("auth_time") == at, "S9",
       "renovar mantém o mesmo auth_time", f"{r.status_code}")
r = c.post("/auth/refresh", headers=tok("adm-a", auth_time=int(time.time()) - 31 * 86400))
checar(r.status_code == 401, "S9", "auth_time de 31 dias atrás: 401 no refresh", str(r.status_code))
r = c.post("/auth/refresh", headers=tok("adm-a", auth_time=int(time.time()) - 29 * 86400))
checar(r.status_code == 200, "S9", "controle: 29 dias ainda renova", str(r.status_code))


# ═════ S10: segredos de produção ═════════════════════════════════════════════
print("\n— S10: segredo fraco não sobe —")
BOM_JWT, BOA_CHAVE = secrets.token_urlsafe(48), Fernet.generate_key().decode()
for jwt, chave, nome in (("curto", BOA_CHAVE, "JWT curto"), (main._JWT_PADRAO, BOA_CHAVE, "JWT padrão do código"),
                         ("", BOA_CHAVE, "JWT vazio"), (BOM_JWT, "", "chave Fernet vazia"),
                         (BOM_JWT, "nao-e-fernet", "chave Fernet inválida")):
    try:
        main._conferir_segredos_de_producao(jwt, chave)
        recusou = False
    except RuntimeError:
        recusou = True
    checar(recusou, "S10", f"recusa {nome}")
try:
    main._conferir_segredos_de_producao(BOM_JWT, BOA_CHAVE)
    aceitou = True
except RuntimeError:
    aceitou = False
checar(aceitou, "S10", "controle: aceita segredos bons")


# ═════ S11: planilha bomba ═══════════════════════════════════════════════════
print("\n— S11: .xlsx que explode ao abrir —")
reset()
LEITURAS = [0]
_read_excel_real = pd.read_excel


def _conta_excel(*a, **k):
    LEITURAS[0] += 1
    return _read_excel_real(*a, **k)


pd.read_excel = _conta_excel
bomba_buf = io.BytesIO()
with zipfile.ZipFile(bomba_buf, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("xl/worksheets/sheet1.xml", b"\0" * (120 * 1024 * 1024))
bomba = bomba_buf.getvalue()
checar(len(bomba) < 1024 * 1024, "S11", "montagem: a bomba tem menos de 1 MB compactada", str(len(bomba)))
for rota in ("/analisar", "/backtest", "/feedback/lote"):
    LEITURAS[0] = 0
    r = c.post(rota, files={"file": ("bomba.xlsx", bomba,
                                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
               headers=tok("adm-a"))
    checar(r.status_code == 413 and LEITURAS[0] == 0, "S11", f"{rota}: 413 sem chamar o leitor de Excel",
           f"{r.status_code} leituras={LEITURAS[0]} {r.text[:80]}")
normal = io.BytesIO()
pd.DataFrame({"cpf": ["12345678909"], "valor_divida": [100.0], "dias_em_atraso": [30]}).to_excel(normal, index=False)
LEITURAS[0] = 0
c.post("/analisar", files={"file": ("ok.xlsx", normal.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
       headers=tok("adm-a"))
checar(LEITURAS[0] == 1, "S11", "controle: planilha normal chega ao leitor", str(LEITURAS[0]))
pd.read_excel = _read_excel_real


# ═════ S13: cabeçalhos da API ════════════════════════════════════════════════
print("\n— S13: cabeçalhos de segurança na API —")
reset()
r = c.get("/auth/me", headers=tok("adm-a"))
checar(r.status_code == 200 and r.headers.get("cache-control") == "no-store"
       and r.headers.get("x-content-type-options") == "nosniff", "S13", "rota autenticada com no-store e nosniff",
       str(dict(r.headers))[:160])
checar(c.get("/health").headers.get("x-content-type-options") == "nosniff", "S13", "nosniff também na rota pública")


# ═════ S14: desafio de identidade ════════════════════════════════════════════
print("\n— S14: o que a tela mostra não confirma a identidade —")
from agente import ferramentas                                            # noqa: E402

CPF = "12345678909"
mostrado = main._cpf_parcial(CPF)
digitos = "".join(ch for ch in mostrado if ch.isdigit())
pedacos = {mostrado, digitos, *(digitos[i:i + 3] for i in range(len(digitos) - 2))}
confirmou = []
for p in pedacos:
    ctx = SimpleNamespace(caso={"dados": {}})
    if ferramentas._verificar_identidade(ctx, None, {"cpf": CPF, "valor_divida": 1}, {"tres_primeiros_digitos_cpf": p}
                                         ).get("confirmada"):
        confirmou.append(p)
checar(not confirmou and CPF[:3] not in digitos[:3], "S14", "nenhum pedaço da máscara da tela confirma",
       f"{mostrado} {confirmou}")
ctx = SimpleNamespace(caso={"dados": {}})
checar(ferramentas._verificar_identidade(ctx, None, {"cpf": CPF, "valor_divida": 1},
                                         {"tres_primeiros_digitos_cpf": CPF}).get("confirmada"),
       "S14", "controle: o CPF completo confirma")
checar(CPF[:3] not in main._cpf_no_log(CPF), "S14", "o log também não mostra os 3 primeiros")


# ═════ S16: extra da configuração ════════════════════════════════════════════
print("\n— S16: PUT /empresa/config só aceita chaves conhecidas —")
reset()
r = c.put("/empresa/config", json={"extra": {"chave_inventada": True}}, headers=tok("adm-a"))
checar(r.status_code == 422, "S16", "chave desconhecida em extra: 422", str(r.status_code))
r = c.put("/empresa/config", json={"nome_exibicao": "Banco Alfa"}, headers=tok("adm-a"))
checar(r.status_code == 200, "S16", "controle: alterar nome_exibicao continua 200", f"{r.status_code} {r.text[:80]}")


# ═════ S18: token de redefinição ═════════════════════════════════════════════
print("\n— S18: token de redefinição guardado como hash —")
reset()
token_link = auth.criar_reset_token("adm-a@x.com")
guardado = json.dumps(T.get("reset_tokens", []))
checar(token_link and token_link not in guardado, "S18", "o banco não contém o token do link")
r = c.post("/auth/redefinir-senha", json={"token": token_link, "nova_senha": "Outra-Senha-789"})
checar(r.status_code == 200, "S18", "controle: o link redefine a senha", str(r.status_code))
r = c.post("/auth/redefinir-senha", json={"token": token_link, "nova_senha": "Mais-Uma-000"})
checar(r.status_code == 400, "S18", "o mesmo link não serve duas vezes", str(r.status_code))


# ═════ OK-IA: CPF fora das chamadas à IA ═════════════════════════════════════
print("\n— OK-IA: a IA não recebe o CPF completo —")
from agente import triagem                                                # noqa: E402

m = triagem.mascarar("meu cpf é 123.456.789-09, ou 12345678909")
checar("456" not in m and "789" not in m, "OK-IA", "o texto que vai à IA sai mascarado", m)


# ═════ S15: uma conversa não esgota a IA da empresa ══════════════════════════
print("\n— S15: 40 mensagens no Telegram, no máximo o limite de rodadas de IA (padrão 30) —")
from agente import api as agente_api, auditor, canal_telegram            # noqa: E402
from agente.fonte import FonteMemoria                                     # noqa: E402
from agente.llm import ClienteFalso, Resposta                             # noqa: E402
from agente.repositorio import RepoMemoria                                # noqa: E402

REPO = RepoMemoria()
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
agente_api.fabrica_repo = lambda: REPO
agente_api.fabrica_fonte = lambda: FonteMemoria([{"id": "p1", "empresa_id": "goias", "cpf": "123.456.789-00",
                                                  "nome": "Maria", "valor_divida": 3000.0, "dias_em_atraso": 95,
                                                  "produto": "cartao"}])
RODADAS = [0]
_tri = json.dumps({"intencao": "duvida", "confianca": 0.9, "valores_citados": [], "datas_citadas": [],
                   "sinais_de_risco": []})


class ClienteContado(ClienteFalso):
    """IA simulada que conta as rodadas (uma triagem por rodada) e responde sempre."""

    def _proximo(self, papel):
        if papel in (None, "triagem"):
            RODADAS[0] += 1
            return _tri
        return Resposta(texto="Certo.")


agente_api.fabrica_cliente = lambda: ClienteContado()
ENVIADOS = []
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append(texto) or True)
canal_telegram.enviar_acao = lambda *a, **k: True
os.environ.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="s", TELEGRAM_BOT_USERNAME="mizan_bot")
reset()
T["usuarios"].append(usuario("adm-g", empresa="goias"))
r = c.post("/agente/casos/p1/telegram-convite", headers=tok("adm-g"))
conv = r.json() if r.status_code == 200 else None
caso = REPO.caso_de("goias", "p1")
checar(conv is not None and caso is not None, "S15", "montagem: convite gerado pela rota", f"{r.status_code} {r.text[:100]}")
if conv:
    canal_telegram.receber({"update_id": 1, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": False},
                                                        "text": "/start " + conv["codigo"]}}, repo=REPO)
upd = lambda uid, t: {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"},  # noqa: E731
                                                    "from": {"is_bot": False}, "text": t}}
for i in range(40):
    canal_telegram.receber(upd(100 + i, f"mensagem {i}"), repo=REPO)
LIMITE = canal_telegram._limite_rodadas()[0]
checar(LIMITE < 40 and caso is not None and 1 <= RODADAS[0] <= LIMITE, "S15",
       f"40 mensagens seguidas: no máximo {LIMITE} rodadas de IA", f"rodadas={RODADAS[0]}")
avisos = [t for t in ENVIADOS if t == canal_telegram.MSG_ESPERA]
checar(len(avisos) == 1, "S15", "o devedor recebe um único aviso fixo, sem IA", str(len(avisos)))
if caso:
    cid = REPO.caso_de("goias", "p1")["id"]
    adiados = [e for e in REPO.eventos.values() if e["caso_id"] == cid and e["situacao"] == "pendente"]
    checar(len(adiados) == 1 and adiados[0]["disponivel_em"] > datetime.now(timezone.utc)
           and "mensagem 39" in adiados[0]["dados"]["texto"] and f"mensagem {LIMITE}" in adiados[0]["dados"]["texto"],
           "S15", "o que passou do limite fica num único evento adiado, com todas as mensagens",
           str([(e["disponivel_em"], len(e["dados"].get("texto", ""))) for e in adiados]))
    # Controle: aberta a janela, a conversa continua sendo atendida (uma rodada para tudo).
    antes = RODADAS[0]
    from agente import orquestrador as orq
    depois = datetime.now(timezone.utc) + timedelta(minutes=11)
    orq.processar_fila(REPO, agente_api.grafos(agente_api.fabrica_fonte()), ClienteContado(), agora=depois,
                       empresa_id="goias", caso_id=cid)
    checar(RODADAS[0] == antes + 1, "S15", "controle: aberta a janela, uma rodada responde a todas",
           f"{antes} -> {RODADAS[0]}")

print()
print("APROVADO" if not falhas else f"{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
