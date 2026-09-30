"""Regressão: um feedback nunca se liga à carteira de outro cliente.

    python test_feedback_escopo.py

Achado ao revisar o código do acesso por chave de API. Em POST /feedback a
predição era procurada só por CPF, em todas as empresas. Consequências:

  - o predicao_id de OUTRO cliente era gravado no feedback de quem chamou;
  - o bandit da empresa que chamou aprendia com o contexto (score, dívida,
    renda) de uma predição alheia;
  - o painel do outro cliente monta seu escopo pelos predicao_id das próprias
    carteiras, então a empresa A, enviando um pagamento para um CPF que só
    existe na carteira da B, gravava um "pagou" que aparecia no painel da B.

O lote (POST /feedback/lote) já tinha o recorte por empresa, mas falhava ABERTO:
`if lista:` descartava o filtro quando a lista vinha vazia — cliente novo, sem
carteira — e o CPF voltava a casar com qualquer empresa.

Além disso, o caminho JWT dessas rotas só validava o token, que dura 7 dias, sem
conferir se o usuário seguia ativo: quem fosse desligado continuava gravando
pagamentos, que alimentam o treino, até o token expirar.
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


# ── Banco simulado: duas empresas com CPFs que se sobrepõem ──────────────
CARTEIRAS = [
    {"id": "c-alfa",   "empresa_id": "alfa"},
    {"id": "c-beta",   "empresa_id": "beta"},
    # a empresa "nova" ainda não tem carteira nenhuma
]
PREDICOES = [
    # só na alfa
    {"id": "p-alfa-so", "carteira_id": "c-alfa", "cpf": "11111111111", "created_at": "2026-01-01",
     "valor_divida": 1000.0, "score_recuperabilidade": 50.0},
    # só na beta
    {"id": "p-beta-so", "carteira_id": "c-beta", "cpf": "22222222222", "created_at": "2026-02-01",
     "valor_divida": 9000.0, "score_recuperabilidade": 90.0},
    # nas duas: a da beta é MAIS RECENTE, de propósito
    {"id": "p-alfa-dupla", "carteira_id": "c-alfa", "cpf": "33333333333", "created_at": "2026-01-10",
     "valor_divida": 2000.0, "score_recuperabilidade": 40.0},
    {"id": "p-beta-dupla", "carteira_id": "c-beta", "cpf": "33333333333", "created_at": "2026-03-10",
     "valor_divida": 8000.0, "score_recuperabilidade": 80.0},
]
FEEDBACKS = []
BANDIT = []          # (cpf, empresa, id da predição usada)


class Q:
    def __init__(self, tabela):
        self.tabela = tabela
        self.linhas = list({"predicoes": PREDICOES, "carteiras": CARTEIRAS}.get(tabela, []))
        self._ins = None
        self._lim = None
        self._rng = None

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

    def limit(self, n):
        self._lim = n
        return self

    def range(self, i, f):
        self._rng = (i, f)
        return self

    def insert(self, linha):
        self._ins = dict(linha, id=f"f{len(FEEDBACKS) + 1}")
        return self

    def execute(self):
        if self._ins is not None:
            FEEDBACKS.append(self._ins)
            return type("R", (), {"data": [self._ins]})()
        d = self.linhas
        if self._rng:
            d = d[self._rng[0]:self._rng[1] + 1]
        if self._lim is not None:
            d = d[:self._lim]
        return type("R", (), {"data": d})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._fechar_loop_bandit = lambda db, cpf, pagou, val, pred, emp: BANDIT.append(
    (cpf, emp, (pred or {}).get("id")))
main._writeback_pagamento = lambda *a, **k: None
main._registrar_auditoria = lambda *a, **k: None
main._cache_del_prefix = lambda *a, **k: None

USUARIOS = {"u-alfa": True, "u-beta": True, "u-nova": True, "u-saiu": False}
main.buscar_usuario_por_id = lambda uid: (
    {"id": uid, "ativo": USUARIOS[uid]} if uid in USUARIOS else None)

CHAVES = {}
main._buscar_api_key = lambda db, tok: CHAVES.get(tok)
main._marcar_uso_api_key = lambda db, l: None

c = TestClient(main.app, raise_server_exceptions=False)


def jwt(sub, empresa, role="admin"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x.com", "nome": sub, "role": role, "empresa_id": empresa})}


def reset():
    FEEDBACKS.clear()
    BANDIT.clear()


def enviar(headers, cpf, **extra):
    return c.post("/feedback", headers=headers, json={"cpf": cpf, "pagou": True,
                                                       "valor_recuperado": 500, **extra})


# ── 1. o furo original ───────────────────────────────────────────────────
print("— CPF que só existe na carteira de outro cliente —")
reset()
r = enviar(jwt("u-alfa", "alfa"), "22222222222")
checar(r.status_code == 200, "o feedback é aceito", str(r.status_code))
checar(r.json().get("predicao_id") is None,
       "mas NÃO se liga à predição do outro cliente",
       f"predicao_id={r.json().get('predicao_id')}")
checar("predicao_id" not in FEEDBACKS[0],
       "e a linha gravada não carrega o predicao_id alheio",
       "é ele que faria o pagamento aparecer no painel da beta")
checar(BANDIT and BANDIT[0][2] is None,
       "o bandit da alfa não aprende com a predição da beta",
       f"usou {BANDIT[0][2] if BANDIT else '—'}")

# ── 2. CPF nas duas empresas ─────────────────────────────────────────────
print("\n— CPF nas duas empresas, a da beta mais recente —")
reset()
r = enviar(jwt("u-alfa", "alfa"), "33333333333")
checar(r.json().get("predicao_id") == "p-alfa-dupla",
       "escolhe a predição da PRÓPRIA empresa, mesmo sendo a mais antiga",
       str(r.json().get("predicao_id")))
r = enviar(jwt("u-beta", "beta"), "33333333333")
checar(r.json().get("predicao_id") == "p-beta-dupla", "e a beta, a dela")

# ── 3. caso normal ───────────────────────────────────────────────────────
reset()
r = enviar(jwt("u-alfa", "alfa"), "11111111111")
checar(r.json().get("predicao_id") == "p-alfa-so", "CPF da própria empresa continua se ligando")
checar(BANDIT and BANDIT[0][2] == "p-alfa-so", "e o bandit recebe a predição certa")

# ── 4. falha fechada: empresa sem carteira ───────────────────────────────
print("\n— empresa sem nenhuma carteira (cliente novo) —")
reset()
r = enviar(jwt("u-nova", "nova"), "22222222222")
checar(r.status_code == 200 and r.json().get("predicao_id") is None,
       "não casa com a predição de ninguém",
       "lista vazia NÃO pode virar 'sem filtro'")

# ── 5. lote ──────────────────────────────────────────────────────────────
print("\n— lote —")


def lote(headers, cpfs):
    csv = "cpf,pagou\n" + "\n".join(f"{x},sim" for x in cpfs)
    return c.post("/feedback/lote", headers=headers,
                  files={"file": ("f.csv", io.BytesIO(csv.encode()), "text/csv")})


reset()
r = lote(jwt("u-alfa", "alfa"), ["11111111111", "22222222222", "33333333333"])
checar(r.status_code == 200 and r.json()["importados"] == 3, "importa as três linhas",
       str(r.json().get("importados")))
lig = {f["cpf"]: f.get("predicao_id") for f in FEEDBACKS}
checar(lig["11111111111"] == "p-alfa-so", "CPF da alfa liga na alfa")
checar(lig["22222222222"] is None, "CPF só da beta não liga em nada")
checar(lig["33333333333"] == "p-alfa-dupla", "CPF nas duas liga na da alfa, não na mais recente")

reset()
r = lote(jwt("u-nova", "nova"), ["22222222222"])
checar(FEEDBACKS and "predicao_id" not in FEEDBACKS[0],
       "lote de empresa SEM carteira também não casa com outra",
       "era o buraco do `if lista:`, que descartava o filtro quando a lista vinha vazia")

# ── 6. comando ───────────────────────────────────────────────────────────
print("\n— comando (sem empresa própria) —")
reset()
r = enviar(jwt("u-alfa", "", role="comando"), "22222222222", empresa="beta")
checar(r.json().get("predicao_id") == "p-beta-so",
       "informando a empresa, é nela que procura", str(r.json().get("predicao_id")))
reset()
r = enviar(jwt("u-alfa", "", role="comando"), "33333333333", empresa="alfa")
checar(r.json().get("predicao_id") == "p-alfa-dupla",
       "e respeita a escolha mesmo quando há outra mais recente")
reset()
r = enviar(jwt("u-alfa", "", role="comando"), "11111111111")
checar(r.status_code == 200 and r.json().get("predicao_id") == "p-alfa-so",
       "sem informar empresa, comando ainda funciona", str(r.status_code))

# ── 7. operador segue barrado ────────────────────────────────────────────
r = enviar(jwt("u-alfa", "alfa", role="operador"), "11111111111")
checar(r.status_code == 403, "operador continua sem poder registrar manualmente", str(r.status_code))

# ── 8. usuário desativado ────────────────────────────────────────────────
print("\n— usuário desligado com token ainda válido —")
reset()
h_saiu = jwt("u-saiu", "alfa")
r = enviar(h_saiu, "11111111111")
checar(r.status_code == 401, "/feedback recusa", str(r.status_code))
r = lote(h_saiu, ["11111111111"])
checar(r.status_code == 401, "/feedback/lote também", str(r.status_code))
checar(FEEDBACKS == [], "e nada foi gravado",
       "o token dura 7 dias; sem a checagem, o pagamento falso entrava até lá")

r = enviar(jwt("fantasma", "alfa"), "11111111111")
checar(r.status_code == 401, "token de usuário que nem existe mais também é recusado")

# ── 9. chave de API ──────────────────────────────────────────────────────
print("\n— acesso por chave de API —")
CHAVES["k-alfa"] = {"id": "k1", "empresa_nome": "Alfa", "empresa_id": "alfa"}
CHAVES["k-orfa"] = {"id": "k2", "empresa_nome": "Sem Empresa", "empresa_id": ""}
reset()
r = enviar({"Authorization": "Bearer k-alfa"}, "22222222222")
checar(r.status_code == 200 and r.json().get("predicao_id") is None,
       "chave da alfa não se liga à predição da beta")
r = enviar({"Authorization": "Bearer k-alfa"}, "11111111111")
checar(r.json().get("predicao_id") == "p-alfa-so", "e se liga à da alfa")
r = enviar({"Authorization": "Bearer k-orfa"}, "11111111111")
checar(r.status_code == 403, "chave sem empresa vinculada é recusada, não liberada", str(r.status_code))
r = enviar({"Authorization": "Bearer k-inventada"}, "11111111111")
checar(r.status_code == 401, "chave inexistente segue 401")

# ── 10. muitas carteiras ─────────────────────────────────────────────────
print("\n— empresa com centenas de carteiras —")
for i in range(250):
    CARTEIRAS.append({"id": f"c-gr-{i}", "empresa_id": "grande"})
PREDICOES.append({"id": "p-gr-antiga", "carteira_id": "c-gr-3", "cpf": "44444444444",
                  "created_at": "2026-01-01", "valor_divida": 1.0})
PREDICOES.append({"id": "p-gr-nova", "carteira_id": "c-gr-230", "cpf": "44444444444",
                  "created_at": "2026-05-01", "valor_divida": 1.0})
reset()
r = enviar(jwt("u-alfa", "grande"), "44444444444")
checar(r.json().get("predicao_id") == "p-gr-nova",
       "acha a mais recente mesmo espalhada em lotes de carteiras",
       "a antiga está no 1º lote e a nova no 3º")

# ── 11. código morto ─────────────────────────────────────────────────────
print("\n— código morto —")
checar(not hasattr(main, "_exigir_admin"), "_exigir_admin foi removido",
       "sem chamador, e a condição só era segura por acidente")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
