"""Verificação em duas etapas (2FA) e limite de login persistente, de ponta a ponta pela API.
Banco falso em memória (com os filtros que as rotas usam), sem rede.

    python test_dois_fatores.py
"""
import base64, copy, json, os, sys, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryptography.fernet import Fernet                                   # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x",
                  JWT_SECRET="segredo-de-teste-com-mais-de-32-caracteres",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())
os.environ.pop("MIZAN_2FA_OBRIGATORIO", None)
import auth                                                              # noqa: E402
import db as _db_mod                                                     # noqa: E402
import dois_fatores as d2                                                # noqa: E402
import limite_login                                                      # noqa: E402
import main                                                              # noqa: E402
from auth import criar_token, hash_senha                                 # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1


# ── banco falso ──────────────────────────────────────────────────────────
T, AUDIT = {}, []
FORA = {"ligado": False}


class Q:
    def __init__(s, t): s.t, s.f, s.op, s.lim = t, [], None, None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def gte(s, c, v): s.f.append(lambda l: str(l.get(c)) >= v); return s
    def lt(s, c, v): s.f.append(lambda l: str(l.get(c)) < v); return s
    def or_(s, expr):
        # só o formato usado em _gravar_uso_2fa: "col.is.null,col.lt.N"
        partes = [p.split(".") for p in expr.split(",")]
        def ok(l):
            for col, op, val in partes:
                if op == "is" and val == "null" and l.get(col) is None:
                    return True
                if op == "lt" and l.get(col) is not None and int(l.get(col)) < int(val):
                    return True
            return False
        s.f.append(ok); return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def insert(s, linha): s.op = ("insert", linha); return s
    def update(s, dados): s.op = ("update", dados); return s
    def delete(s): s.op = ("delete",); return s

    def execute(s):
        if FORA["ligado"] and s.t == "login_tentativas":
            raise RuntimeError("banco fora")
        tab = T.setdefault(s.t, [])
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        R = lambda d, n=None: SimpleNamespace(data=copy.deepcopy(d), count=len(d) if n is None else n)  # noqa: E731
        if s.op and s.op[0] == "insert":
            n = {"id": f"{s.t}-{len(tab) + 1}", **copy.deepcopy(s.op[1])}
            tab.append(n)
            return R([n])
        if s.op and s.op[0] == "update":
            for l in alvo:
                l.update(copy.deepcopy(s.op[1]))
            return R(alvo)
        if s.op and s.op[0] == "delete":
            T[s.t] = [l for l in tab if l not in alvo]
            return R(alvo)
        return R(alvo[:s.lim] if s.lim else alvo, len(alvo))


class DB:
    def table(self, n): return Q(n)
    storage = None


main.get_db = lambda: DB()
_db_mod.get_db = lambda: DB()
main._registrar_auditoria = lambda *a, **k: AUDIT.append(k.get("acao"))
main._usuario_autenticado.__globals__["_registrar_auditoria"] = main._registrar_auditoria
SENHA = "Senha-Forte-123"
C2FA = {k: None for k in d2.COLUNAS} | {"totp_ativo": False}


def usuario(uid, role="admin", migrado=True):
    u = {"id": uid, "email": f"{uid}@x.com", "nome": uid, "role": role, "empresa_id": "alfa", "ativo": True,
         "senha_hash": hash_senha(SENHA)}
    return {**u, **C2FA} if migrado else u


def reset(*usuarios):
    T.clear(); AUDIT.clear()
    main._tentativas_login.clear()
    main._limite.LIMITADOR.limpar()
    FORA["ligado"] = False
    T["usuarios"] = list(usuarios)


c = TestClient(main.app, raise_server_exceptions=False)
H = lambda tok: {"Authorization": f"Bearer {tok}"}                     # noqa: E731
def entrar(email, senha=SENHA, ip="203.0.113.1"):
    return c.post("/auth/login", json={"email": email, "senha": senha}, headers={"X-Forwarded-For": ip})
def u_banco(uid):
    return next(x for x in T["usuarios"] if x["id"] == uid)
def cod_agora(segredo, desloca=0):
    return d2.codigo(segredo, d2.passo_de() + desloca)
ROTA = "/auth/usuarios"                                                  # rota comum de administrador

print("— TOTP: vetores do RFC 6238 —")
seg_rfc = base64.b32encode(b"12345678901234567890").decode()
checar(all(d2.codigo(seg_rfc, t // 30, 8) == e for t, e in
           [(59, "94287082"), (1111111109, "07081804"), (1234567890, "89005924"), (2000000000, "69279037")]),
       "códigos iguais aos do RFC (SHA-1, 8 dígitos)")
s = d2.novo_segredo()
checar(d2.verificar(s, cod_agora(s)) is not None and d2.verificar(s, cod_agora(s, -1)) is not None
       and d2.verificar(s, cod_agora(s, -3)) is None, "vale o código atual e o do passo vizinho; antigo não")
checar(d2.verificar(s, cod_agora(s), ultimo_passo=d2.passo_de()) is None, "código já usado não vale de novo")
codigos, hashes = d2.novos_codigos_recuperacao()
checar(len(codigos) == 10 and not any(cd.replace("-", "") in json.dumps(hashes) for cd in codigos),
       "10 códigos de recuperação; o banco guarda só hash")
r1 = d2.usar_recuperacao(hashes, codigos[0].upper())
checar(r1 is not None and len(r1) == 9 and d2.usar_recuperacao(r1, codigos[0]) is None, "código de recuperação vale uma vez")

print("— limite de login no banco (sobrevive a reinício) —")
reset(usuario("adm"))
cods = [entrar("adm@x.com", "errada", ip=f"203.0.113.{i}").status_code for i in range(4)]
main._tentativas_login.clear()                                          # "reinício" do servidor
cods += [entrar("adm@x.com", "errada", ip="203.0.113.9").status_code]
cods += [entrar("adm@x.com", SENHA, ip="203.0.113.10").status_code]
checar(cods == [401] * 5 + [429], "4 erros + reinício + 1 erro: a senha certa fica bloqueada (429)", str(cods))
linhas = json.dumps(T.get("login_tentativas", []))
checar(T.get("login_tentativas") and "adm@x.com" not in linhas and "203.0.113" not in linhas,
       "o banco guarda a chave em HMAC, sem e-mail nem IP", linhas[:120])
reset(usuario("adm"))
FORA["ligado"] = True
cods = [entrar("adm@x.com", "errada").status_code for _ in range(6)]
checar(cods == [401] * 5 + [429], "banco fora: a contagem em memória continua barrando", str(cods))
reset(usuario("adm", migrado=False))
entrar("adm@x.com", "errada"); entrar("adm@x.com", SENHA)
checar(not [l for l in T.get("login_tentativas", []) if l["chave"] == limite_login.chave_protegida("login:email:adm@x.com")],
       "login certo apaga os erros do e-mail")

print("— antes da migração: ninguém é obrigado —")
reset(usuario("adm", migrado=False))
r = entrar("adm@x.com")
checar(r.status_code == 200 and "configurar_2fa" not in r.json() and c.get(ROTA, headers=H(r.json()["token"])).status_code == 200,
       "sem as colunas no banco, o administrador entra e usa como antes")

print("— depois da migração: administrador configura no próximo acesso —")
reset(usuario("adm"), usuario("op", role="operador"))
r = entrar("adm@x.com")
tok0 = r.json().get("token")
checar(r.status_code == 200 and r.json().get("configurar_2fa") is True, "login devolve configurar_2fa")
r = c.get(ROTA, headers=H(tok0))
checar(r.status_code == 403 and r.json()["detail"] == d2.MSG_OBRIGATORIO, "as outras rotas respondem 403 com o aviso")
checar(c.get("/auth/me", headers=H(tok0)).status_code == 200 and c.get("/auth/2fa", headers=H(tok0)).json()["obrigatorio"],
       "identidade e situação do 2FA continuam acessíveis")
r = entrar("op@x.com")
checar(r.status_code == 200 and "configurar_2fa" not in r.json()
       and c.get("/auth/2fa", headers=H(r.json()["token"])).json()["obrigatorio"] is False, "operador não é obrigado")

r = c.post("/auth/2fa/iniciar", json={}, headers=H(tok0))
seg = r.json().get("segredo", "")
checar(r.status_code == 200 and r.json()["uri"].startswith("otpauth://totp/Mizan") and seg in r.json()["uri"],
       "iniciar devolve o segredo e o endereço para o app")
checar(str(r.json().get("qr") or "").startswith("data:image/svg+xml"), "e o QR code pronto (SVG)")
pend = u_banco("adm")["totp_pendente"]
checar(pend.startswith("fernet:") and seg not in pend, "o segredo pendente fica cifrado no banco")
r = c.post("/auth/2fa/confirmar", json={"codigo": "000000" if cod_agora(seg) != "000000" else "111111"}, headers=H(tok0))
checar(r.status_code == 400, "código errado na confirmação: 400 (não derruba a sessão)", str(r.status_code))
r = c.post("/auth/2fa/confirmar", json={"codigo": cod_agora(seg)}, headers=H(tok0))
tok1, recs = r.json().get("token"), r.json().get("codigos_recuperacao", [])
ub = u_banco("adm")
checar(r.status_code == 200 and len(recs) == 10 and tok1, "confirmar liga o 2FA e mostra 10 códigos de recuperação")
checar(ub["totp_ativo"] and ub["totp_segredo"].startswith("fernet:") and not ub["totp_pendente"]
       and not any(x.replace("-", "") in json.dumps(ub) for x in recs), "no banco: segredo cifrado e só hashes")
checar("2fa_ativado" in AUDIT, "ativação na auditoria")
r = c.get(ROTA, headers=H(tok0))
checar(r.status_code == 401 and r.json()["detail"] == d2.MSG_SESSAO_SEM_2FA, "a sessão antiga (sem o código) cai")
checar(c.get(ROTA, headers=H(tok1)).status_code == 200, "a sessão nova funciona")

print("— login em duas etapas —")
r = entrar("adm@x.com")
desafio = r.json().get("desafio")
checar(r.status_code == 200 and r.json().get("requer_2fa") and "token" not in r.json(), "senha certa: pede o código, sem sessão")
checar(c.get(ROTA, headers=H(desafio)).status_code == 401, "o desafio não serve como sessão")
r = c.post("/auth/login/2fa", json={"desafio": desafio, "codigo": "12345"})
checar(r.status_code == 401 and r.json()["detail"] == "Código incorreto.", "código errado: recusado")
# o código de agora já foi usado na confirmação: o próximo passo vale
codigo2 = cod_agora(seg, 1)
r = c.post("/auth/login/2fa", json={"desafio": desafio, "codigo": codigo2})
tok2 = r.json().get("token")
corpo = json.dumps(r.json())
checar(r.status_code == 200 and tok2 and c.get(ROTA, headers=H(tok2)).status_code == 200, "código certo: entra")
checar(not any(k in corpo for k in ("totp_segredo", "totp_recuperacao", "totp_pendente", "senha_hash")),
       "a resposta não traz segredo, hashes nem senha")
r = c.post("/auth/login/2fa", json={"desafio": entrar("adm@x.com").json()["desafio"], "codigo": codigo2})
checar(r.status_code == 401 and "já foi usado" in r.json().get("detail", ""), "o mesmo código não entra duas vezes",
       r.json().get("detail", ""))
r = c.post("/auth/login/2fa", json={"desafio": entrar("adm@x.com").json()["desafio"], "codigo": recs[0]})
checar(r.status_code == 200 and "2fa_codigo_recuperacao_usado" in AUDIT, "código de recuperação entra (e fica na auditoria)")
r = c.post("/auth/login/2fa", json={"desafio": entrar("adm@x.com").json()["desafio"], "codigo": recs[0]})
checar(r.status_code == 401, "o mesmo código de recuperação não entra de novo")
velho = criar_token({"sub": "adm", "fin": "2fa", "sv": auth.versao_da_senha(u_banco("adm")), "auth_time": 1}, expira_s=-10)
checar(c.post("/auth/login/2fa", json={"desafio": velho, "codigo": cod_agora(seg)}).status_code == 401, "desafio vencido: entra de novo")
falso = criar_token({"sub": "adm", "email": "adm@x.com", "role": "admin", "sv": auth.versao_da_senha(u_banco("adm"))})
checar(c.post("/auth/login/2fa", json={"desafio": falso, "codigo": cod_agora(seg)}).status_code == 401,
       "token de sessão não serve como desafio")

print("— limite de códigos —")
main._tentativas_login.clear()
for k in [l for l in T.get("login_tentativas", [])]:
    T["login_tentativas"].remove(k)
d = entrar("adm@x.com").json()["desafio"]
cods = [c.post("/auth/login/2fa", json={"desafio": d, "codigo": "000001"}).status_code for _ in range(6)]
checar(cods == [401] * 5 + [429], "5 códigos errados: bloqueio de 15 minutos", str(cods))

print("— renovação de sessão —")
r = c.post("/auth/refresh", headers=H(tok2))
checar(r.status_code == 200 and auth.validar_token(r.json()["token"]).get("mfa") is True
       and "totp_segredo" not in json.dumps(r.json()), "renovar mantém a marca do 2FA, sem expor segredo")
checar(c.post("/auth/refresh", headers=H(tok0)).status_code == 401, "token sem o código não renova")

print("— desligar, redefinir e interruptor —")
r = c.post("/auth/2fa/desativar", json={"senha": SENHA, "codigo": cod_agora(seg, 1)}, headers=H(tok2))
checar(r.status_code == 403, "administrador não desliga (é obrigatório)")
reset(usuario("op", role="operador"))
tk = entrar("op@x.com").json()["token"]
sg = c.post("/auth/2fa/iniciar", json={}, headers=H(tk)).json()["segredo"]
tk = c.post("/auth/2fa/confirmar", json={"codigo": cod_agora(sg)}, headers=H(tk)).json()["token"]
r = c.post("/auth/2fa/desativar", json={"senha": "errada", "codigo": cod_agora(sg, 1)}, headers=H(tk))
checar(r.status_code == 400, "operador: senha errada não desliga")
r = c.post("/auth/2fa/desativar", json={"senha": SENHA, "codigo": cod_agora(sg, 1)}, headers=H(tk))
checar(r.status_code == 200 and not u_banco("op")["totp_ativo"], "operador com senha e código desliga")

reset(usuario("adm"), usuario("cmd", role="comando"))
for x in T["usuarios"]:
    x.update({"totp_ativo": True, "totp_segredo": d2.cifrar(seg)})
tk_cmd = criar_token({"sub": "cmd", "email": "cmd@x.com", "nome": "cmd", "role": "comando", "empresa_id": "",
                      "sv": auth.versao_da_senha(u_banco("cmd")), "mfa": True})
tk_adm = criar_token({"sub": "adm", "email": "adm@x.com", "nome": "adm", "role": "admin", "empresa_id": "alfa",
                      "sv": auth.versao_da_senha(u_banco("adm")), "mfa": True})
checar(c.delete("/auth/usuarios/cmd/2fa", headers=H(tk_adm)).status_code == 403, "administrador não redefine o 2FA de ninguém")
r = c.delete("/auth/usuarios/adm/2fa", headers=H(tk_cmd))
checar(r.status_code == 200 and not u_banco("adm")["totp_ativo"] and "2fa_redefinido" in AUDIT,
       "COMANDO redefine o 2FA de quem perdeu o celular (com auditoria)")
r = c.get(ROTA, headers=H(tk_adm))
checar(r.status_code == 403 and r.json()["detail"] == d2.MSG_OBRIGATORIO, "e a pessoa configura de novo no próximo acesso")
os.environ["MIZAN_2FA_OBRIGATORIO"] = "0"
checar(c.get(ROTA, headers=H(tk_adm)).status_code == 200, "MIZAN_2FA_OBRIGATORIO=0: ninguém é obrigado (emergência)")
os.environ.pop("MIZAN_2FA_OBRIGATORIO")

print("— sessão antiga não cadastra celular sem a senha —")
reset(usuario("adm"))
antigo = criar_token({"sub": "adm", "email": "adm@x.com", "nome": "adm", "role": "admin", "empresa_id": "alfa",
                      "sv": auth.versao_da_senha(u_banco("adm")), "auth_time": int(time.time()) - 3600})
r = c.post("/auth/2fa/iniciar", json={}, headers=H(antigo))
checar(r.status_code == 400 and r.json()["detail"] == d2.MSG_SENHA_PARA_CONFIGURAR, "sessão de 1 h atrás: pede a senha")
checar(c.post("/auth/2fa/iniciar", json={"senha": "errada"}, headers=H(antigo)).status_code == 400, "senha errada: recusa")
r = c.post("/auth/2fa/iniciar", json={"senha": SENHA}, headers=H(antigo))
checar(r.status_code == 200 and r.json().get("segredo"), "com a senha certa: segue")

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
