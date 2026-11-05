"""Excluir um cliente e todos os dados dele (painel COMANDO): travas, limites e o que sai do servidor.
Banco falso em memória; a função do banco (public.excluir_dados_cliente) é simulada aqui e foi
provada no PostgreSQL 16 de verdade com o esquema do projeto (docs/EXCLUIR_CLIENTE.md).

    python test_excluir_cliente.py
"""
import copy, json, os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryptography.fernet import Fernet                                   # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x",
                  JWT_SECRET="segredo-de-teste-com-mais-de-32-caracteres",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())
os.environ["MIZAN_2FA_OBRIGATORIO"] = "0"      # aqui o COMANDO falso só tem 2FA na seção do aplicativo
import auth                                                              # noqa: E402
import db as _db_mod                                                     # noqa: E402
import dois_fatores as d2                                                # noqa: E402
import main                                                              # noqa: E402
import storage_ml                                                        # noqa: E402
from auth import criar_token, hash_senha                                 # noqa: E402
from model import modelos_empresa                                        # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1


# ── banco falso ──────────────────────────────────────────────────────────
T, AUDIT, RPC = {}, [], []
RPC_ERRO = {"texto": None}


class Q:
    def __init__(s, t): s.t, s.f, s.op, s.lim = t, [], None, None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def or_(s, expr):
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
        tab = T.setdefault(s.t, [])
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        R = lambda d: SimpleNamespace(data=copy.deepcopy(d), count=len(d))  # noqa: E731
        if s.op and s.op[0] == "insert":
            tab.append({"id": f"{s.t}-{len(tab) + 1}", **copy.deepcopy(s.op[1])}); return R([tab[-1]])
        if s.op and s.op[0] == "update":
            for l in alvo:
                l.update(copy.deepcopy(s.op[1]))
            return R(alvo)
        if s.op and s.op[0] == "delete":
            T[s.t] = [l for l in tab if l not in alvo]; return R(alvo)
        return R(alvo[:s.lim] if s.lim else alvo)


class DB:
    def table(self, n): return Q(n)
    def rpc(self, nome, params):
        class Chamada:
            def execute(_):
                RPC.append((nome, params))
                if RPC_ERRO["texto"]:
                    raise RuntimeError(RPC_ERRO["texto"])
                return SimpleNamespace(data={"usuarios": 2, "carteiras": 1, "predicoes": 40, "agente_mensagens": 0})
        return Chamada()
    storage = None


main.get_db = lambda: DB()
_db_mod.get_db = lambda: DB()
main._registrar_auditoria = lambda *a, **k: AUDIT.append((k.get("acao"), k.get("empresa_id"), k.get("detalhes")))
main._usuario_autenticado.__globals__["_registrar_auditoria"] = main._registrar_auditoria
SENHA = "Senha-Forte-123"
SEG = d2.novo_segredo()
C2FA = {k: None for k in d2.COLUNAS} | {"totp_ativo": False}


def usuario(uid, role="admin", empresa="goias", **extra):
    return {"id": uid, "email": f"{uid}@x.com", "nome": uid, "role": role, "empresa_id": empresa, "ativo": True,
            "senha_hash": hash_senha(SENHA), **C2FA, **extra}


def reset(com_2fa=False):
    T.clear(); AUDIT.clear(); RPC.clear(); RPC_ERRO["texto"] = None
    main._tentativas_login.clear(); main._limite.LIMITADOR.limpar()
    cmd = usuario("cmd", role="comando", empresa="")
    if com_2fa:
        cmd.update({"totp_ativo": True, "totp_segredo": d2.cifrar(SEG)})
    T["usuarios"] = [cmd, usuario("adm"), usuario("op", role="operador"), usuario("b1", empresa="beta")]
    T["empresa_config"] = [{"empresa_id": "goias", "nome_exibicao": "Goiás Bank"}, {"empresa_id": "beta", "nome_exibicao": "Banco Beta"}]
    T["carteiras"] = [{"id": "c1", "empresa_id": "goias"}]


def token(uid):
    u = next(x for x in T["usuarios"] if x["id"] == uid)
    return criar_token({"sub": uid, "email": u["email"], "nome": uid, "role": u["role"], "empresa_id": u["empresa_id"],
                        "sv": auth.versao_da_senha(u), "mfa": True})


c = TestClient(main.app, raise_server_exceptions=False)
H = lambda tok: {"Authorization": f"Bearer {tok}"}                      # noqa: E731
def excluir(empresa="goias", confirmacao="Goiás Bank", senha=SENHA, codigo="", quem="cmd"):
    return c.post(f"/comando/empresas/{empresa}/excluir-tudo", headers=H(token(quem)),
                  json={"confirmacao": confirmacao, "senha": senha, "codigo": codigo})
def cod(desloca=0):
    return d2.codigo(SEG, d2.passo_de() + desloca)


print("— quem pode —")
reset()
checar(c.post("/comando/empresas/goias/excluir-tudo", json={}).status_code in (401, 403), "sem login: recusado")
checar(excluir(quem="adm").status_code == 403, "administrador da empresa não exclui o próprio cliente")
checar(excluir(quem="op").status_code == 403, "operador não exclui")
checar(not RPC, "e o banco não foi chamado")

print("— travas —")
r = excluir(empresa="naoexiste", confirmacao="naoexiste")
checar(r.status_code == 404 and not RPC, "cliente que não existe: 404")
T["usuarios"][0]["empresa_id"] = "goias"
r = excluir()
checar(r.status_code == 400 and "COMANDO" in r.json()["detail"] and not RPC, "empresa com usuário COMANDO: recusada")
T["usuarios"][0]["empresa_id"] = ""
for errado in ("", "goiás", "Goias Bank", "Banco Beta", "beta"):
    r = excluir(confirmacao=errado)
    checar(r.status_code == 400 and not RPC, f"nome digitado errado ({errado!r}): recusado")
r = excluir(senha="errada")
checar(r.status_code == 401 and r.json()["detail"] == "Senha incorreta." and not RPC, "senha errada: recusado")
codigos = [excluir(senha="errada").status_code for _ in range(6)]
checar(codigos[-1] == 429 and not RPC, "senha errada várias vezes: bloqueio temporário", str(codigos))
checar(excluir().status_code == 429 and not RPC, "e nem a senha certa passa durante o bloqueio")

print("— exclusão —")
reset()
r = excluir(confirmacao="  GOIÁS bank ")
corpo = r.json()
checar(r.status_code == 200 and corpo["ok"] and corpo["total"] == 43, "nome certo (sem diferenciar maiúsculas) e senha certa: exclui", str(corpo))
checar(RPC == [("excluir_dados_cliente", {"p_empresa": "goias"})], "o banco recebe SÓ o cliente pedido", str(RPC))
checar(corpo["apagados"] == {"usuarios": 2, "carteiras": 1, "predicoes": 40}, "a resposta traz o que foi apagado (sem zeros)", str(corpo["apagados"]))
checar(AUDIT and AUDIT[-1][0] == "cliente_excluido" and AUDIT[-1][1] == "goias" and AUDIT[-1][2] == {"apagados": corpo["apagados"]},
       "fica na auditoria quem apagou e quanto, sem dado pessoal", str(AUDIT[-1:]))
reset()
checar(excluir(confirmacao="goias").status_code == 200, "o código do cliente também confirma")
reset()
checar(excluir(empresa="beta", confirmacao="Banco Beta").status_code == 200 and RPC[-1][1] == {"p_empresa": "beta"},
       "outro cliente: exclui só o dele")

print("— aplicativo autenticador (se ligado) —")
reset(com_2fa=True)
r = excluir()
checar(r.status_code == 401 and "Código" in r.json()["detail"] and not RPC, "com 2FA ligado, sem o código: recusado")
r = excluir(codigo="000000")
checar(r.status_code == 401 and not RPC, "código errado: recusado")
r = excluir(codigo=cod())
checar(r.status_code == 200 and len(RPC) == 1, "código certo: exclui")
r = excluir(codigo=cod())
checar(r.status_code == 401 and len(RPC) == 1, "o mesmo código não vale duas vezes")

print("— banco sem a função / com erro —")
reset()
RPC_ERRO["texto"] = "{'code': 'PGRST202', 'message': 'Could not find the function public.excluir_dados_cliente(p_empresa) in the schema cache'}"
r = excluir()
checar(r.status_code == 503 and "migracao_excluir_cliente.sql" in r.json()["detail"], "função ainda não criada: 503 e diz qual SQL rodar", r.json().get("detail", "")[:80])
RPC_ERRO["texto"] = "connection reset"
r = excluir()
checar(r.status_code == 503 and "Nada foi apagado" in r.json()["detail"] and "connection" not in r.text, "erro do banco: 503 sem vazar detalhe e sem apagar")
checar(not any(a[0] == "cliente_excluido" for a in AUDIT), "e não registra uma exclusão que não aconteceu")

print("— arquivos fora do banco —")
reset()
ENVIADOS = []
with tempfile.TemporaryDirectory() as tmp:
    modelos_empresa.EMPRESAS_DIR = Path(tmp) / "empresas"
    pasta = modelos_empresa.pasta("goias"); pasta.mkdir(parents=True)
    (pasta / "mizan_model.pkl").write_bytes(b"x")
    outra = modelos_empresa.pasta("beta"); outra.mkdir(parents=True)
    (outra / "mizan_model.pkl").write_bytes(b"y")
    modelos_empresa._cache[modelos_empresa.slug("goias")] = (9e18, None)
    storage_ml.apagar_empresa = lambda slug: ENVIADOS.append(slug) or 3
    r = excluir()
    checar(r.status_code == 200 and not pasta.exists(), "a pasta de modelos do cliente sai do disco")
    checar(outra.exists(), "a do outro cliente fica")
    checar(modelos_empresa.slug("goias") not in modelos_empresa._cache, "e o cache de modelos dele é limpo")
    checar(ENVIADOS == ["goias"] and r.json()["apagados"].get("modelos_arquivos") == 4, "o Storage recebe só o cliente certo", str(r.json()["apagados"]))

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
