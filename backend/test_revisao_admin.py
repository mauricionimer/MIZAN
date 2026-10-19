"""Revisão das entregas F1–F4 / A1–A5: correções achadas na revisão.

1. Distribuir fila: cada thread grava com o próprio cliente do banco (o cliente
   HTTP/2 não pode ser compartilhado entre threads).
2. COMANDO confirmando pagamento na fila: o pagamento leva a empresa da
   carteira do devedor (antes ia sem empresa e sumia de Resultados, do painel
   e da baixa automática das promessas).

    python test_revisao_admin.py
"""
import os, sys, threading
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

print("— 1. distribuir fila: um cliente por thread —")
usados = {}                     # id(cliente) -> threads que o usaram

class Q:
    def __init__(s, dono): s.dono = dono
    def update(s, *_): return s
    def eq(s, *_): return s
    def in_(s, *_): return s
    def execute(s):
        usados.setdefault(id(s.dono), set()).add(threading.get_ident())
        return type("R", (), {"data": []})()

class Cliente:
    def table(self, _): return Q(self)

locais = threading.local()
def get_db_por_thread():
    if not hasattr(locais, "c"):
        locais.c = Cliente()
    return locais.c
main.get_db = get_db_por_thread
compartilhado = Cliente()
main._gravar_responsavel(compartilhado, "c1", [f"p{i}" for i in range(1000)], "op", "Ana")
checar(id(compartilhado) not in usados, "o cliente da thread principal não é usado pelas threads de gravação")
checar(usados and all(len(t) == 1 for t in usados.values()), "cada cliente é usado por uma thread só",
       str({k: len(v) for k, v in usados.items()}))

print("— 2. COMANDO confirma pagamento: empresa da carteira —")
GRAVADO, CUMPRIU, BANDIT = [], [], []

class Q2:
    def __init__(s, t): s.t = t; s.ins = None
    def select(s, *a, **k): return s
    def eq(s, *a): return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s
    def insert(s, l): s.ins = l; return s
    def execute(s):
        if s.ins is not None:
            GRAVADO.append(s.ins); return type("R", (), {"data": [{"id": "fb1", "created_at": "2026-10-05"}]})()
        return type("R", (), {"data": []})()

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q2(n))})()
main._predicao_do_cpf = lambda db, cpf, emp, colunas=None: {"id": "p1", "carteira_id": "cart-goias"}
main._empresa_da_carteira = lambda db, cid: {"cart-goias": "goiasbank"}.get(cid, "")
main._cumprir_promessas = lambda db, emp, cpf, *a: CUMPRIU.append(emp)
main._fechar_loop_bandit = lambda db, cpf, pagou, v, pred, emp: BANDIT.append(emp)
main._writeback_pagamento = lambda *a, **k: None
main._registrar_auditoria = lambda *a, **k: None
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": f"u-{role}", "email": f"{role}@x", "nome": role, "role": role, "empresa_id": empresa})}

# O COMANDO escolhe a empresa: sem ela a idempotência e a predição ficavam sem escopo.
r = c.post("/devedores/11111111111/confirmar-pagamento", json={"valor_recuperado": 300}, headers=jwt("", "comando"))
checar(r.status_code == 400 and not GRAVADO, "comando sem empresa escolhida: 400 e nada gravado", r.text[:120])
r = c.post("/devedores/11111111111/confirmar-pagamento?empresa_id=goiasbank", json={"valor_recuperado": 300},
           headers=jwt("", "comando"))
checar(r.status_code == 200, "comando confirma na empresa escolhida", r.text[:120])
checar(GRAVADO and GRAVADO[-1]["empresa"] == "goiasbank", "o pagamento leva a empresa da carteira", str(GRAVADO[-1:]))
checar(CUMPRIU[-1:] == ["goiasbank"] and BANDIT[-1:] == ["goiasbank"], "promessas e aprendizado da empresa certa")
r = c.post("/devedores/22222222222/confirmar-pagamento", json={"valor_recuperado": 50}, headers=jwt("goiasbank", "admin"))
checar(r.status_code == 200 and GRAVADO[-1]["empresa"] == "goiasbank", "admin continua gravando a própria empresa")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
