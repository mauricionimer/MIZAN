"""Resultados reais e painel do COMANDO enxergam a base inteira, não as primeiras mil linhas.

    python test_resultados_escala.py

Achados ao mapear o sistema para a Central de Ajuda (docs/MAPA_DO_SISTEMA.md):

  C1  /performance e /performance/pagamentos liam as predições da carteira sem
      paginar: com 2.600 devedores (a base de produção tem 2.603), os
      pagamentos de quem estava fora das mil primeiras sumiam dos resultados.
  C2  liam os 5.000 feedbacks mais novos — na prática mil — DE TODAS AS EMPRESAS
      e filtravam depois. Com mais de mil feedbacks recentes de outro cliente,
      esta empresa via quase nada.
  C3  um in_ com 1.000 ids numa URL: a medição no Supabase real mostrou que 800
      já falham.
  C4  o painel do COMANDO somava só mil carteiras e mil feedbacks.

Este stub impõe os dois tetos reais: mil linhas por resposta e um in_ curto.
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
IN_MAXIMO = 400          # medido no Supabase real: 400 passa, 800 falha

N_ALFA = 2600            # mais que o teto, como a base de produção
N_BETA = 3000
UUID = lambda p, i: f"{p}-{i:032d}"

CARTEIRAS = ([{"id": "c-alfa", "empresa_id": "alfa", "usuario_email": "a@a.com",
               "total_devedores": N_ALFA, "valor_face": 1.0, "valor_esperado": 1.0,
               "score_medio": 50.0, "created_at": "2026-01-01"}]
             + [{"id": "c-beta", "empresa_id": "beta", "usuario_email": "b@b.com",
                 "total_devedores": N_BETA, "valor_face": 1.0, "valor_esperado": 1.0,
                 "score_medio": 50.0, "created_at": "2026-01-01"}]
             # carteiras extras para passar de mil no painel do COMANDO
             + [{"id": f"cx{i}", "empresa_id": f"e{i % 7}", "usuario_email": "x@x.com",
                 "total_devedores": 1, "valor_face": 1.0, "valor_esperado": 1.0,
                 "score_medio": 50.0, "created_at": "2026-01-01"} for i in range(1200)])

PRED = [{"id": UUID("pa", i), "carteira_id": "c-alfa", "cpf": f"{i:011d}", "nome": f"A{i}",
         "valor_divida": 100.0, "score_recuperabilidade": 80.0 if i % 2 else 20.0}
        for i in range(N_ALFA)]
PRED += [{"id": UUID("pb", i), "carteira_id": "c-beta", "cpf": f"9{i:010d}", "nome": f"B{i}",
          "valor_divida": 100.0, "score_recuperabilidade": 50.0} for i in range(N_BETA)]

# Feedbacks da alfa: só de quem está DEPOIS das mil primeiras predições. Antigos.
FB = [{"id": f"fa{i}", "predicao_id": UUID("pa", 1000 + i), "cpf": f"{1000 + i:011d}",
       "pagou": bool(i % 2), "valor_recuperado": 50.0 if i % 2 else 0.0,
       "created_at": f"2026-02-{1 + i % 20:02d}T10:{i % 60:02d}:00", "empresa": "alfa"}
      for i in range(1500)]
# Feedbacks da beta: 3.000, todos MAIS NOVOS que os da alfa.
FB += [{"id": f"fb{i}", "predicao_id": UUID("pb", i), "cpf": f"9{i:010d}",
        "pagou": True, "valor_recuperado": 10.0,
        "created_at": f"2026-06-{1 + i % 25:02d}T10:{i % 60:02d}:00", "empresa": "beta"}
       for i in range(N_BETA)]
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

print("— /performance —")
r = c.get("/performance", headers=HA, params={"carteira_id": "c-alfa"})
j = r.json()
checar(r.status_code == 200 and j.get("total_feedbacks") == 1500,
       "por carteira: conta os 1.500 pagamentos de quem está além das mil primeiras predições",
       f"{r.status_code} {str(j)[:100]}")
r = c.get("/performance", headers=HA)
j = r.json()
checar(r.status_code == 200 and j.get("total_feedbacks") == 1500,
       "por empresa: 1.500, mesmo com 3.000 feedbacks MAIS NOVOS de outro cliente",
       f"{r.status_code} {str(j)[:100]}")
faixas = {m["faixa"]: m for m in j.get("metricas_por_faixa", [])}
checar(sum(m["total_feedbacks"] for m in faixas.values()) == 1500, "e as faixas somam o mesmo total")
checar("Sem score" not in faixas, "todos os feedbacks acharam a predição (scores lidos em lotes curtos)",
       str(list(faixas)))
r = c.get("/performance", headers=HC)
checar(r.status_code == 200 and r.json().get("total_feedbacks") == 4500,
       "COMANDO sem escopo: 4.500 (todas as empresas), paginado", str(r.json())[:90])

print("\n— /performance/pagamentos —")
r = c.get("/performance/pagamentos", headers=HA, params={"carteira_id": "c-alfa"})
checar(r.status_code == 200 and len(r.json()) == 1500, "lista os 1.500 pagamentos da carteira",
       f"{r.status_code} {len(r.json()) if r.status_code == 200 else r.text[:80]}")
r = c.get("/performance/pagamentos", headers=HA)
checar(r.status_code == 200 and len(r.json()) == 1500, "por empresa, também 1.500 (nada da beta)",
       f"{r.status_code} {len(r.json()) if r.status_code == 200 else r.text[:80]}")
checar(isinstance(r.json(), list) and all(x["cpf"].startswith("0") for x in r.json()), "e nenhum CPF de outra empresa")

print("\n— /feedbacks/status —")
r = c.get("/feedbacks/status", headers=HA, params={"carteira_id": "c-alfa"})
checar(r.status_code == 200 and len(r.json()) == 1500, "mapa de status com os 1.500 CPFs",
       f"{r.status_code} {len(r.json()) if r.status_code == 200 else r.text[:80]}")

print("\n— painel do COMANDO —")
r = c.get("/comando/visao-geral", headers=HC)
j = r.json()
checar(r.status_code == 200, "responde", str(r.status_code) + r.text[:80])
emp = {e["empresa_id"]: e for e in j.get("empresas", [])}
checar(sum(e["total_carteiras"] for e in emp.values()) == len(CARTEIRAS),
       f"soma as {len(CARTEIRAS)} carteiras, não as primeiras mil",
       str(sum(e["total_carteiras"] for e in emp.values())))
checar(emp.get("alfa", {}).get("n_feedbacks") == 1500 and emp.get("beta", {}).get("n_feedbacks") == N_BETA,
       "conta os feedbacks de cada empresa por inteiro",
       f"alfa={emp.get('alfa', {}).get('n_feedbacks')} beta={emp.get('beta', {}).get('n_feedbacks')}")
checar(abs(emp.get("alfa", {}).get("valor_recuperado_real", 0) - 750 * 50.0) < 0.01,
       "e o valor recuperado real da alfa (750 pagamentos × R$ 50)", str(emp.get("alfa", {}).get("valor_recuperado_real")))

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
