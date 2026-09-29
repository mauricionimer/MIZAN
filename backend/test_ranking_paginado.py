"""Regressão: uma página da fila, sem trazer a carteira inteira.

    python test_ranking_paginado.py

/carteiras/{id} devolve o ranking completo — 581 bytes por devedor em JSON, ou
seja 29 MB para 50 mil e 116 MB para 200 mil, para uma tabela que mostra 50 por
vez. Esta rota entrega as 50.

O que precisa ser verdade:

  1. A ordem é a da fila (rank), não a do score.
  2. O total é o da carteira inteira, não o do filtro — senão filtrar por
     produto reclassificaria a prioridade de quem sobrou.
  3. A etiqueta de prioridade vira recorte de rank, e o recorte tem de bater
     com o que a tela calcula (conferido à parte contra a implementação em JS).
  4. Nenhuma rota deixa ler carteira de outra empresa.
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


N = 100
# Score DECRESCE conforme o rank cresce ao contrário: quem está no topo da fila
# tem score baixo e dívida alta. Se algo reordenar por score, o teste vê.
PREDICOES = [
    {"id": f"p{r}", "carteira_id": "cart-1", "rank": r,
     "cpf": f"{r:011d}", "nome": f"Devedor {r}",
     "produto": "cartao" if r % 2 else "consignado",
     "uf": "GO" if r % 3 else "SP",
     "valor_divida": 100000.0 / r, "score_recuperabilidade": float(r),
     "valor_esperado_liquido": 100000.0 / r}
    for r in range(1, N + 1)
]
CARTEIRAS = [{"id": "cart-1", "empresa_id": "banco_alfa"},
             {"id": "cart-outra", "empresa_id": "banco_beta"}]
FEEDBACKS = [
    {"cpf": f"{1:011d}", "pagou": True,  "created_at": "2026-09-01", "predicao_id": "p1"},
    {"cpf": f"{2:011d}", "pagou": False, "created_at": "2026-09-01", "predicao_id": "p2"},
    # o mesmo CPF depois pagou — só o mais recente vale
    {"cpf": f"{2:011d}", "pagou": True,  "created_at": "2026-09-20", "predicao_id": "p2"},
]


class Q:
    def __init__(self, tabela, linhas):
        self.tabela, self.linhas = tabela, list(linhas)
        self._neg = False
        self._faixa = None
        self._lim = None

    def select(self, *a, **k): return self

    # No PostgREST, count="exact" conta o conjunto FILTRADO e ignora limit e
    # range — eles recortam as linhas devolvidas, não a contagem. Truncar aqui
    # faria o stub mentir e o total da carteira sair como 1.
    def limit(self, n):
        self._lim = n
        return self

    def eq(self, col, val):
        self.linhas = [l for l in self.linhas if l.get(col) == val]
        return self

    def gte(self, col, v):
        self.linhas = [l for l in self.linhas if (l.get(col) or 0) >= v]
        return self

    def lte(self, col, v):
        self.linhas = [l for l in self.linhas if (l.get(col) or 0) <= v]
        return self

    def in_(self, col, vals):
        vals = set(vals)
        if self._neg:
            self.linhas = [l for l in self.linhas if l.get(col) not in vals]
            self._neg = False
        else:
            self.linhas = [l for l in self.linhas if l.get(col) in vals]
        return self

    @property
    def not_(self):
        self._neg = True
        return self

    def or_(self, expressao):
        # "nome.ilike.*x*,cpf.ilike.*x*"
        alvos = []
        for parte in expressao.split(","):
            campo, _, valor = parte.split(".", 2)
            alvos.append((campo, valor.strip("*").lower()))
        self.linhas = [l for l in self.linhas
                       if any(v in str(l.get(c) or "").lower() for c, v in alvos)]
        return self

    def order(self, col, desc=False):
        self.linhas.sort(key=lambda l: (l.get(col) is None, l.get(col) or 0), reverse=desc)
        return self

    def range(self, ini, fim):
        self._faixa = (ini, fim)
        return self

    def execute(self):
        total = len(self.linhas)          # antes de qualquer recorte
        dados = self.linhas
        if self._faixa:
            dados = dados[self._faixa[0]:self._faixa[1] + 1]
        if self._lim is not None:
            dados = dados[:self._lim]
        return type("R", (), {"data": dados, "count": total})()


class DB:
    def table(self, nome):
        return Q(nome, {"predicoes": PREDICOES, "carteiras": CARTEIRAS,
                        "feedbacks": FEEDBACKS}.get(nome, []))


main.get_db = lambda: DB()
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
main._extra_empresa = lambda eid: {}

c = TestClient(main.app)


def token(empresa="banco_alfa", role="admin"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "a@a.com", "nome": "A", "role": role, "empresa_id": empresa})}


def pagina(**params):
    return c.get("/carteiras/cart-1/ranking", headers=token(), params=params)


# ── 1. a página ──────────────────────────────────────────────────────────
print("— paginação —")
r = pagina(offset=0, limit=10)
checar(r.status_code == 200, "responde", str(r.status_code) + r.text[:60])
d = r.json()
checar(len(d["itens"]) == 10, "devolve o tamanho pedido", str(len(d["itens"])))
checar(d["total"] == N, "o total é o da carteira inteira", str(d["total"]))
checar([i["rank"] for i in d["itens"]] == list(range(1, 11)),
       "na ordem da fila, não do score",
       "score cresce com o rank de propósito: reordenar por score inverteria")

r2 = pagina(offset=10, limit=10).json()
checar([i["rank"] for i in r2["itens"]] == list(range(11, 21)), "a segunda página continua de onde parou")
checar(not ({i["cpf"] for i in d["itens"]} & {i["cpf"] for i in r2["itens"]}),
       "sem repetir ninguém entre páginas")

r3 = pagina(offset=0, limit=9999).json()
checar(len(r3["itens"]) <= 500, "o limite tem teto", f"pediu 9999, veio {len(r3['itens'])}")
checar(pagina(offset=-5, limit=0).status_code == 200, "offset negativo e limite zero não quebram")
checar(len(pagina(offset=5000, limit=10).json()["itens"]) == 0, "página além do fim vem vazia")


# ── 2. filtros ───────────────────────────────────────────────────────────
print("\n— filtros —")
d = pagina(produto="cartao", limit=5).json()
checar(all(i["produto"] == "cartao" for i in d["itens"]), "filtra por produto")
checar(d["filtrado"] == 50, "e conta quantos casaram", str(d["filtrado"]))
checar(d["total"] == N, "sem mexer no total da carteira",
       "senão a prioridade de quem sobrou seria recalculada")

d = pagina(uf="SP", limit=5).json()
checar(all(i["uf"] == "SP" for i in d["itens"]), "filtra por UF")

d = pagina(busca="Devedor 42", limit=5).json()
checar(len(d["itens"]) == 1 and d["itens"][0]["rank"] == 42, "busca por nome", str(len(d["itens"])))
d = pagina(busca="00000000007", limit=5).json()
checar(any(i["rank"] == 7 for i in d["itens"]), "busca por CPF")
checar(pagina(busca="*,*").status_code == 200, "busca com caractere de filtro não quebra")


# ── 3. prioridade vira recorte de rank ───────────────────────────────────
print("\n— prioridade —")
alta = pagina(prioridade="Alta", limit=500).json()
checar([i["rank"] for i in alta["itens"]] == list(range(1, 21)),
       "Alta é o primeiro quinto da fila", f"{alta['filtrado']} itens")
media = pagina(prioridade="Média", limit=500).json()
checar([i["rank"] for i in media["itens"]] == list(range(21, 51)), "Média vai de 21 a 50")
baixa = pagina(prioridade="Baixa", limit=500).json()
checar([i["rank"] for i in baixa["itens"]] == list(range(51, 101)), "Baixa é o resto")
checar(alta["filtrado"] + media["filtrado"] + baixa["filtrado"] == N,
       "as três faixas cobrem a fila inteira, sem sobra nem sobreposição")


# ── 4. status vem dos feedbacks ──────────────────────────────────────────
print("\n— status —")
pagos = pagina(status="pago", limit=500).json()
checar({i["rank"] for i in pagos["itens"]} == {1, 2},
       "pagos inclui quem mudou de não-pago para pago",
       str(sorted(i["rank"] for i in pagos["itens"])))
nao = pagina(status="nao_pago", limit=500).json()
checar(nao["filtrado"] == 0, "e o feedback antigo não conta mais",
       "só o mais recente de cada CPF vale")
pend = pagina(status="pendente", limit=500).json()
checar(pend["filtrado"] == N - 2, "pendentes é quem nunca teve feedback", str(pend["filtrado"]))


# ── 5. escopo por empresa ────────────────────────────────────────────────
print("\n— escopo —")
r = c.get("/carteiras/cart-outra/ranking", headers=token("banco_alfa"))
checar(r.status_code == 403, "não lê a fila de outra empresa", str(r.status_code))
r = c.get("/carteiras/cart-outra/ranking", headers=token("", "comando"))
checar(r.status_code == 200, "comando enxerga qualquer carteira", str(r.status_code))
checar(c.get("/carteiras/cart-1/ranking").status_code in (401, 403),
       "sem token, nada")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
