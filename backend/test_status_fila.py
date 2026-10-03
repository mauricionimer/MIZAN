"""Filtro de status da fila (pago / não pago / pendente) com milhares de feedbacks.

    python test_status_fila.py

C6 (docs/MAPA_DO_SISTEMA.md): o filtro mandava a lista de CPFs na consulta; com
milhares de feedbacks a URL estoura. O stub impõe o in_ curto e o teto de mil
linhas por resposta, como o Supabase real.
"""
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


TETO_RESPOSTA = 1000
IN_MAXIMO = 400
N = 2600
UUID = lambda i: f"pa-{i:032d}"

CARTEIRAS = [{"id": "c-alfa", "empresa_id": "alfa", "usuario_email": "a@a.com", "total_devedores": N,
              "valor_face": 1.0, "valor_esperado": 1.0, "score_medio": 50.0, "created_at": "2026-01-01"}]
PRED = [{"id": UUID(i), "carteira_id": "c-alfa", "cpf": f"{i:011d}", "nome": f"A{i}", "valor_divida": 100.0,
         "score_recuperabilidade": 50.0, "rank": i + 1, "uf": "GO" if i % 2 else "SP", "produto": "p"}
        for i in range(N)]
# 1.800 com feedback: pagou quem tem i % 3 == 0; o resto dos 1.800 não pagou. 800 pendentes.
FB = [{"id": f"f{i}", "predicao_id": UUID(i), "cpf": f"{i:011d}", "pagou": i % 3 == 0,
       "valor_recuperado": 1.0, "created_at": "2026-02-01T10:00:00", "empresa": "alfa"} for i in range(1800)]
TABELAS = {"carteiras": CARTEIRAS, "predicoes": PRED, "feedbacks": FB, "usuarios": []}


class Q:
    def __init__(self, tabela):
        self.t = tabela
        self.l = list(TABELAS.get(tabela, []))
        self._ord, self._lim, self._rng, self._count = [], None, None, False

    def select(self, *a, **k):
        self._count = k.get("count") == "exact"
        return self

    def eq(self, c, v): self.l = [x for x in self.l if x.get(c) == v]; return self
    def neq(self, c, v): self.l = [x for x in self.l if x.get(c) != v]; return self
    def is_(self, c, _): self.l = [x for x in self.l if x.get(c) is None]; return self

    @property
    def not_(self):
        q = self
        class N:
            def is_(_, c, __): q.l = [x for x in q.l if x.get(c) is not None]; return q
        return N()

    def in_(self, c, vs):
        vs = list(vs)
        if len(vs) > IN_MAXIMO:
            raise RuntimeError(f"URL grande demais: {len(vs)} itens num in_ (limite simulado {IN_MAXIMO})")
        vs = set(vs); self.l = [x for x in self.l if x.get(c) in vs]; return self

    def order(self, c, desc=False): self._ord.append((c, desc)); return self
    def limit(self, n): self._lim = n; return self
    def range(self, i, f): self._rng = (i, f); return self

    def execute(self):
        d = self.l
        for c, desc in reversed(self._ord):       # a ordenação acumula, como no PostgREST
            d = sorted(d, key=lambda x: (x.get(c) is None, x.get(c)), reverse=desc)
        total = len(d)
        if self._rng: d = d[self._rng[0]:self._rng[1] + 1]
        if self._lim is not None: d = d[:self._lim]
        d = d[:TETO_RESPOSTA]
        return type("R", (), {"data": d, "count": total if self._count else None})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
USERS = {"ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa", "email": "a@a.com"},
         "uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": "", "email": "c@c.com"}}
main.buscar_usuario_por_id = lambda uid: USERS[uid]
main._registrar_auditoria = lambda *a, **k: None
main._cache_get = lambda *a, **k: None
main._cache_set = lambda *a, **k: None

c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u, role, emp: {"Authorization": "Bearer " + criar_token(
    {"sub": u, "email": "e@e.com", "nome": "N", "role": role, "empresa_id": emp})}
HA, HC = H("ua", "admin", "alfa"), H("uc", "comando", "")


PAGOS = {i for i in range(1800) if i % 3 == 0}
NAO = set(range(1800)) - PAGOS
PEND = set(range(1800, N))

def pedir(status, **extra):
    r = c.get("/carteiras/c-alfa/ranking", headers=HA, params={"status": status, "limit": 50, **extra})
    return r, (r.json() if r.status_code == 200 else {})

def cpfs(j): return [it.get("cpf") for it in j.get("itens", [])]

for status, esperado in (("pago", PAGOS), ("nao_pago", NAO), ("pendente", PEND)):
    r, j = pedir(status)
    checar(r.status_code == 200, f"{status}: responde 200 mesmo com 1.800 feedbacks", f"{r.status_code} {r.text[:120]}")
    checar(j.get("filtrado") == len(esperado), f"{status}: conta {len(esperado)}", j.get("filtrado"))
    ordem = sorted(esperado)[:50]
    checar(cpfs(j) == [f"{i:011d}" for i in ordem], f"{status}: a primeira página é a do topo da fila, em ordem")
    r2, j2 = pedir(status, offset=50)
    checar(cpfs(j2) == [f"{i:011d}" for i in sorted(esperado)[50:100]], f"{status}: a segunda página continua de onde parou")

r, j = pedir("pago", uf="GO")
esp = sorted(i for i in PAGOS if i % 2)
checar(j.get("filtrado") == len(esp) and cpfs(j) == [f"{i:011d}" for i in esp[:50]], "status junto com outro filtro (UF)")

r, j = pedir("pago", limit=500)
checar(len(j.get("itens", [])) == 500, "página de 500 cabe mesmo com in_ curto", len(j.get("itens", [])))

r = c.get("/carteiras/c-alfa/ranking", headers=HA, params={"limit": 50})
checar(r.status_code == 200 and r.json().get("filtrado") == N, "sem status continua igual")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
