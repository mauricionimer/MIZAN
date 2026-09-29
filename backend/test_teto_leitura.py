"""Regressão: o teto de linhas do PostgREST não pode truncar número em silêncio.

    python test_teto_leitura.py

O PostgREST devolve no máximo ~1000 linhas por resposta, e não avisa: vem 200 e
um pedaço dos dados. O projeto já convivia com isso — retrain.py tem _BATCH=1000
e duas rotas de métricas têm laço próprio, comentado "(paginado)". Onde faltava,
o efeito era silencioso e grave.

Reabrir uma carteira de 5.000 devedores devolvia 1.000, e o resumo inteiro —
total em risco, valor esperado, score médio, distribuições — saía calculado
sobre um quinto da carteira. Nenhum erro, nenhum aviso: só números menores, que
ninguém tem como desconfiar olhando a tela.

O escopo por empresa tinha o mesmo problema por dois caminhos: quatro lugares
truncavam em 100 explicitamente e sete confiavam no "sem limite", que é mil.
Uma empresa que analisa uma carteira por dia passa de cem em três meses.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from auth import criar_token                       # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


TETO = 1000          # o mesmo que o projeto já assume em retrain.py
N = 5000             # carteira maior que o teto, de propósito
N_CARTEIRAS = 250    # mais que os 100 que quatro consultas truncavam

PREDICOES = [
    {"id": f"p{r}", "carteira_id": "c1", "rank": r, "cpf": f"{r:011d}", "nome": f"D{r}",
     "produto": "cartao" if r % 2 else "consignado", "uf": "GO" if r % 3 else "SP",
     "valor_divida": 1000.0, "score_recuperabilidade": 50.0,
     "valor_esperado_recuperacao": 500.0, "dias_em_atraso": 100}
    for r in range(1, N + 1)
]
CARTEIRAS = ([{"id": "c1", "empresa_id": "e", "usuario_email": "a@a.com",
               "created_at": "2026-01-01", "valor_esperado": 2_500_000.0}]
             + [{"id": f"c{i}", "empresa_id": "e"} for i in range(2, N_CARTEIRAS + 1)])

leituras = {"n": 0}


class Q:
    def __init__(self, tabela):
        self.linhas = list({"predicoes": PREDICOES, "carteiras": CARTEIRAS}.get(tabela, []))
        self.rng = None
        self._exata = False

    def select(self, *a, **k):
        self._exata = k.get("count") == "exact"
        return self

    def eq(self, c, v):
        self.linhas = [l for l in self.linhas if l.get(c) == v]
        return self

    def in_(self, c, vs):
        vs = set(vs)
        self.linhas = [l for l in self.linhas if l.get(c) in vs]
        return self

    def order(self, *a, **k): return self
    def limit(self, n):       return self

    def range(self, i, f):
        self.rng = (i, f)
        return self

    def execute(self):
        leituras["n"] += 1
        total = len(self.linhas)
        d = self.linhas
        if self.rng:
            d = d[self.rng[0]:self.rng[1] + 1]
        # O corte do servidor: acontece com ou sem range pedido, e a resposta
        # não diz que faltou nada.
        return type("R", (), {"data": d[:TETO], "count": total})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
main._extra_empresa = lambda e: {}

c = TestClient(main.app)
H = {"Authorization": "Bearer " + criar_token(
    {"sub": "u", "email": "a@a.com", "nome": "A", "role": "admin", "empresa_id": "e"})}


# ── 1. a carteira inteira volta ──────────────────────────────────────────
print("— reabrir uma carteira maior que o teto —")
r = c.get("/carteiras/c1", headers=H).json()
resumo = r["resumo"]

checar(resumo["total_devedores"] == N,
       f"devolve os {N} devedores, não os primeiros {TETO}",
       str(resumo["total_devedores"]))
checar(resumo["total_em_risco"] == N * 1000.0,
       "e o total em risco é o da carteira inteira",
       f"R$ {resumo['total_em_risco']:,.0f}")
checar(resumo["valor_esperado_recuperacao_total"] == N * 500.0,
       "e o valor esperado também",
       "truncado, o número iria para a reunião cinco vezes menor")
checar(len(r["ranking_completo"]) == N, "o ranking vem completo")
checar(sorted(resumo["produtos"]) == ["cartao", "consignado"],
       "os seletores enxergam a carteira toda", str(resumo["produtos"]))


# ── 2. o alcance soma o topo de verdade ──────────────────────────────────
print("\n— alcance acima do teto —")
a = c.get("/carteiras/c1/alcance?capacidade=4000", headers=H).json()
checar(a["n"] == 4000, "considera os 4.000 pedidos", str(a["n"]))
checar(a["valor"] == 4000 * 500.0, "e soma os 4.000, não os primeiros mil",
       f"R$ {a['valor']:,.0f} (truncado daria R$ 500.000)")

a2 = c.get("/carteiras/c1/alcance?capacidade=500", headers=H).json()
checar(a2["valor"] == 500 * 500.0, "capacidade abaixo do teto continua certa")


# ── 3. a página do ranking não regrediu ──────────────────────────────────
print("\n— a paginação continua paginando —")
antes = leituras["n"]
p = c.get("/carteiras/c1/ranking?offset=0&limit=50", headers=H).json()
checar(len(p["itens"]) == 50, "uma página é uma página", str(len(p["itens"])))
checar(p["total"] == N, "e o total é o da carteira inteira", str(p["total"]))
checar(leituras["n"] - antes <= 4,
       "sem varrer a carteira para montar uma página",
       f"{leituras['n'] - antes} consultas")


# ── 4. o escopo por empresa ──────────────────────────────────────────────
print("\n— carteiras da empresa —")
ids = main._ids_carteiras(main.get_db(), "e")
checar(len(ids) == N_CARTEIRAS,
       f"enxerga as {N_CARTEIRAS} carteiras, não as primeiras 100",
       f"{len(ids)} encontradas")


# ── 5. a paginação para quando acaba ─────────────────────────────────────
print("\n— o laço termina —")
vazio = main._todas_as_linhas(lambda: Q("predicoes").eq("carteira_id", "inexistente"))
checar(vazio == [], "consulta sem resultado devolve lista vazia")

exato = main._todas_as_linhas(lambda: Q("predicoes"), lote=N)
checar(len(exato) == N, "resultado do tamanho exato do lote não duplica nem perde",
       f"{len(exato)} linhas")

um = main._todas_as_linhas(lambda: Q("carteiras").eq("id", "c1"))
checar(len(um) == 1, "uma linha só também termina")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
