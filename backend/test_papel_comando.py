"""Regressão: criar comando é possível, ficar sem nenhum não é.

    python test_papel_comando.py

O COMANDO é o papel de plataforma — cria empresas, cria usuários, promove
modelo. Ele só existia por inserção direta no banco: a rota de registro exigia
comando E recusava criar outro, e alterar_role recusava mexer em qualquer
comando. Era uma trava grosseira que funcionava por impedir tudo.

Abrindo a criação, a trava grosseira some e uma precisa toma o lugar: zerar os
comandos ativos tranca a plataforma do lado de fora, e não há tela para
desfazer — só acesso direto ao banco.

O limite de autoridade continua onde estava: só comando cria comando. O admin
de um banco cliente não alcança nenhuma destas rotas.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
import auth as A                                   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── Banco simulado ───────────────────────────────────────────────────────
USUARIOS = []


class Q:
    def __init__(self, linhas):
        self.linhas = list(linhas)
        self._patch = None

    def select(self, *a, **k): return self
    def limit(self, n):        return self
    def order(self, *a, **k):  return self

    def eq(self, col, val):
        self.linhas = [l for l in self.linhas if l.get(col) == val]
        return self

    def neq(self, col, val):
        self.linhas = [l for l in self.linhas if l.get(col) != val]
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def insert(self, linha):
        USUARIOS.append(linha)
        self.linhas = [linha]
        return self

    def execute(self):
        if self._patch is not None:
            for l in self.linhas:
                l.update(self._patch)
        return type("R", (), {"data": self.linhas})()


class DB:
    def table(self, nome):
        return Q(USUARIOS if nome == "usuarios" else [])


A._db = lambda: DB()
main.get_db = lambda: DB()
main._registrar_auditoria = lambda *a, **k: None
main.buscar_usuario_por_id = lambda uid: next((u for u in USUARIOS if u["id"] == uid), None)

c = TestClient(main.app)


# Um usuário de verdade para cada papel. O servidor confere o papel no CADASTRO,
# não no token: um token com role "admin" e o sub de um comando é, para o
# servidor, um comando. O teste antigo forjava exatamente isso e dependia de o
# token ser a autoridade — que é o que deixou de valer.
_SUB_POR_PAPEL = {"comando": "u-chefe", "admin": "u-admin", "operador": "u-op"}


def token(role="comando", empresa=""):
    sub = _SUB_POR_PAPEL[role]
    return {"Authorization": "Bearer " + A.criar_token(
        {"sub": sub, "email": f"{sub}@mizan.app", "nome": sub,
         "role": role, "empresa_id": empresa,
         # como o login emite: com a marca da senha atual (ver auth.versao_da_senha)
         "sv": A.versao_da_senha(main.buscar_usuario_por_id(sub) or {})})}


def reset():
    USUARIOS.clear()
    USUARIOS.append({"id": "u-chefe", "email": "chefe@mizan.app", "nome": "Chefe",
                     "role": "comando", "ativo": True, "empresa_id": "", "senha_hash": "x"})


# ── 1. criar comando ─────────────────────────────────────────────────────
print("— criar um comando —")
reset()
r = c.post("/auth/registrar", headers=token(), json={
    "email": "socio@mizan.app", "nome": "Sócio", "senha": "senha12345",
    "role": "comando", "empresa_id": "banco_alfa"})
checar(r.status_code == 200, "comando cria outro comando", str(r.status_code) + " " + r.text[:70])
novo = next((u for u in USUARIOS if u["email"] == "socio@mizan.app"), None)
checar(novo is not None and novo["role"] == "comando", "e o papel gravado é comando")
checar(novo is not None and novo["empresa_id"] == "",
       "e ele não nasce dentro de uma empresa cliente",
       "o sistema já recusa MOVER um comando para empresa; nascer numa seria o mesmo estado")


# ── 2. o limite de autoridade não mudou ──────────────────────────────────
print("\n— quem pode fazer isso —")
reset()
USUARIOS.append({"id": "u-admin", "email": "u-admin@mizan.app", "nome": "Admin", "role": "admin",
                 "ativo": True, "empresa_id": "banco_alfa", "senha_hash": "x"})
USUARIOS.append({"id": "u-op", "email": "u-op@mizan.app", "nome": "Op", "role": "operador",
                 "ativo": True, "empresa_id": "banco_alfa", "senha_hash": "x"})
antes = len(USUARIOS)
for papel in ("admin", "operador"):
    r = c.post("/auth/registrar", headers=token(papel, "banco_alfa"), json={
        "email": "x@x.com", "nome": "X", "senha": "senha12345", "role": "comando"})
    checar(r.status_code == 403, f"{papel} não cria comando", str(r.status_code))
checar(len(USUARIOS) == antes, "e ninguém foi criado")

r = c.post("/auth/registrar", headers=token(), json={
    "email": "y@y.com", "nome": "Y", "senha": "senha12345", "role": "dono_do_mundo"})
checar(r.status_code == 400, "papel inventado é recusado")

r = c.post("/auth/registrar", headers=token(), json={
    "email": "z@z.com", "nome": "Z", "senha": "senha12345", "role": "admin"})
checar(r.status_code == 400, "admin sem empresa é recusado",
       "só o comando dispensa empresa")


# ── 3. não ficar sem nenhum comando ──────────────────────────────────────
print("\n— a trava que passa a ser necessária —")
reset()
r = c.patch("/auth/usuarios/u-chefe/role", headers=token(), json={"role": "admin"})
checar(r.status_code == 400, "rebaixar o único comando é recusado", str(r.status_code))
checar("único COMANDO" in r.json().get("detail", ""), "e a mensagem diz o porquê",
       r.json().get("detail", "")[:60])
checar(USUARIOS[0]["role"] == "comando", "e ele continua comando")

r = c.patch("/auth/usuarios/u-chefe/ativo", headers=token(), json={"ativo": False})
checar(r.status_code == 400, "desativar o único comando é recusado", str(r.status_code))
checar(USUARIOS[0]["ativo"] is True, "e ele continua ativo",
       "sem isto a plataforma tranca e só o banco desfaz")

# com dois, rebaixar um passa a ser permitido
USUARIOS.append({"id": "u-2", "email": "socio@mizan.app", "nome": "Sócio",
                 "role": "comando", "ativo": True, "empresa_id": "", "senha_hash": "x"})
r = c.patch("/auth/usuarios/u-2/role", headers=token(), json={"role": "admin"})
checar(r.status_code == 200, "com dois comandos, rebaixar um é permitido", str(r.status_code))
checar(USUARIOS[1]["role"] == "admin", "e o papel muda de fato")

# e agora o que sobrou volta a ser protegido
r = c.patch("/auth/usuarios/u-chefe/ativo", headers=token(), json={"ativo": False})
checar(r.status_code == 400, "o que sobrou volta a ser o último e é protegido")


# ── 4. comando inativo não conta como proteção ───────────────────────────
print("\n— um comando desativado não segura a plataforma —")
reset()
USUARIOS.append({"id": "u-velho", "email": "antigo@mizan.app", "nome": "Antigo",
                 "role": "comando", "ativo": False, "empresa_id": "", "senha_hash": "x"})
r = c.patch("/auth/usuarios/u-chefe/ativo", headers=token(), json={"ativo": False})
checar(r.status_code == 400,
       "com o outro comando inativo, o ativo continua protegido",
       "senão sobrariam só comandos que não conseguem entrar")


# ── 5. promover alguém a comando ─────────────────────────────────────────
print("\n— promover —")
reset()
USUARIOS.append({"id": "u-ad", "email": "ad@banco.com", "nome": "Ad",
                 "role": "admin", "ativo": True, "empresa_id": "banco_alfa", "senha_hash": "x"})
r = c.patch("/auth/usuarios/u-ad/role", headers=token(), json={"role": "comando"})
checar(r.status_code == 200, "comando promove um admin a comando", str(r.status_code))
checar(USUARIOS[1]["role"] == "comando", "o papel muda")
checar(USUARIOS[1]["empresa_id"] == "", "e ele sai da empresa cliente ao subir",
       "comando é papel de plataforma, não de cliente")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
