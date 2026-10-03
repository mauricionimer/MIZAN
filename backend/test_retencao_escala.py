"""Regressão: a retenção enxerga a base inteira, não as primeiras mil linhas.

    python test_retencao_escala.py

O PostgREST devolve no máximo ~1000 linhas por resposta e não avisa. A retenção
lia com `.limit(50000)`, que parece pedir cinquenta mil e entrega mil. Efeitos:

  - a prévia dizia "1.000 registros com CPF" para uma base de 41.000, e o admin
    escolhia o prazo olhando um número vinte vezes menor que o real;
  - "Executar agora" anonimizava no máximo mil por clique, e a tela dizia
    "concluído". O resto ficava com CPF, sem nenhum aviso;
  - o pedido de um titular (LGPD art. 18) podia deixar linhas dele para trás.

O escopo de predições também passava todas as carteiras da empresa num único
in_. Os stubs dos outros testes não impõem esse teto, e foi assim que o erro
passou: era preciso um teste que o impusesse.

Premissa declarada: o teto de tamanho da URL (ITENS_POR_IN, abaixo) é uma
suposição conservadora, não um valor medido no Supabase. O teste garante que o
código não depende de uma lista longa passar; quanto cabe de fato, só o servidor
real diz.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
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


TETO_RESPOSTA = 1000     # o teto que o PostgREST impõe, com ou sem range
ITENS_POR_IN = 120       # suposição conservadora sobre a URL: abaixo dos 200 que o update antigo usava

AGORA = datetime.now(timezone.utc)
VELHO = (AGORA - timedelta(days=900)).isoformat()
NOVO = (AGORA - timedelta(days=5)).isoformat()

N_CART = 260             # mais que um lote de cem, e mais que ITENS_POR_IN
N_PRED = 3500            # mais que três respostas cheias
N_FB = 2500

CARTEIRAS = ([{"id": f"c{i}", "empresa_id": "alfa"} for i in range(N_CART)]
             + [{"id": "c-beta", "empresa_id": "beta"}])
PRED = [{"id": f"p{i}", "carteira_id": f"c{i % N_CART}", "cpf": f"{i:011d}",
         "created_at": VELHO, "anonimizado_em": None} for i in range(N_PRED)]
PRED += [{"id": f"pb{i}", "carteira_id": "c-beta", "cpf": f"9{i:010d}",
          "created_at": VELHO, "anonimizado_em": None} for i in range(50)]
FB = [{"id": f"f{i}", "empresa": "alfa", "cpf": f"{i:011d}", "created_at": VELHO,
       "anonimizado_em": None} for i in range(N_FB)]
FB += [{"id": f"fb{i}", "empresa": "beta", "cpf": f"9{i:010d}", "created_at": VELHO,
        "anonimizado_em": None} for i in range(50)]
CT = [{"id": f"t{i}", "empresa_id": "alfa", "cpf": f"{i:011d}", "created_at": NOVO,
       "anonimizado_em": None} for i in range(30)]
RC = [{"id": f"r{i}", "empresa_id": "alfa", "cpf": f"{i:011d}", "created_at": VELHO,
       "anonimizado_em": None} for i in range(40)]
TABELAS = {"carteiras": CARTEIRAS, "predicoes": PRED, "feedbacks": FB,
           "contatos": CT, "recomendacoes": RC}

atualizacoes = []
FALHA = {"tabela": None}


class Q:
    def __init__(self, tabela):
        self.tabela = tabela
        self.linhas = list(TABELAS.get(tabela, []))
        self._patch = None
        self._rng = None
        self._lim = None

    def select(self, *a, **k): return self

    def eq(self, c, v):
        self.linhas = [l for l in self.linhas if l.get(c) == v]
        return self

    def is_(self, c, _):
        self.linhas = [l for l in self.linhas if l.get(c) is None]
        return self

    def in_(self, c, vs):
        vs = list(vs)
        if len(vs) > ITENS_POR_IN:
            raise RuntimeError(f"URL grande demais: {len(vs)} itens num in_ (limite simulado {ITENS_POR_IN})")
        vs = set(vs)
        self.linhas = [l for l in self.linhas if l.get(c) in vs]
        return self

    def order(self, *a, **k): return self
    def limit(self, n):       self._lim = n; return self
    def range(self, i, f):    self._rng = (i, f); return self
    def update(self, patch):  self._patch = patch; return self

    def execute(self):
        # A falha é por TABELA, não geral. Quebrar a listagem de carteiras faria
        # a rota cair antes do laço da prévia e o teste passaria pelo motivo
        # errado: foi o que aconteceu na primeira versão, e uma mutação que
        # engolia o erro dentro do laço não foi detectada.
        if FALHA["tabela"] == self.tabela and self._patch is None:
            raise RuntimeError("o banco não respondeu")
        if self._patch is not None:
            for l in self.linhas:
                l.update(self._patch)
            atualizacoes.append((self.tabela, len(self.linhas)))
            return type("R", (), {"data": self.linhas})()
        d = self.linhas
        if self._rng:
            d = d[self._rng[0]:self._rng[1] + 1]
        if self._lim is not None:
            d = d[:self._lim]
        # O teto do servidor: acontece SEMPRE, com ou sem limit/range pedidos.
        return type("R", (), {"data": d[:TETO_RESPOSTA]})()


main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid, "role": "comando",
                                          "empresa_id": ""}
main._registrar_auditoria = lambda *a, **k: None
POLITICA = {"alfa": {"retencao": {"ativa": True, "dias": 365}}}
main._extra_empresa = lambda e: POLITICA.get(e, {})

c = TestClient(main.app, raise_server_exceptions=False)
H = {"Authorization": "Bearer " + criar_token(
    {"sub": "u", "email": "a@a.com", "nome": "A", "role": "comando", "empresa_id": ""})}


def anonimizadas(tabela, empresa_col, empresa):
    return sum(1 for l in TABELAS[tabela] if l.get(empresa_col) == empresa and l["anonimizado_em"])


# ── 1. a prévia vê tudo ──────────────────────────────────────────────────
print("— prévia —")
r = c.get("/retencao?empresa_id_alvo=alfa", headers=H)
checar(r.status_code == 200, "responde", str(r.status_code) + " " + r.text[:60])
p = r.json()["previa"]
checar(p["predicoes"]["com_identificacao"] == N_PRED,
       f"conta as {N_PRED} predições, não as primeiras {TETO_RESPOSTA}",
       str(p["predicoes"]))
checar(p["predicoes"]["vencidas"] == N_PRED, "e todas vencidas, com 365 dias de prazo")
checar(p["feedbacks"]["com_identificacao"] == N_FB,
       f"os {N_FB} feedbacks também", str(p["feedbacks"]))
checar(p["contatos"]["vencidas"] == 0 and p["contatos"]["com_identificacao"] == 30,
       "contatos recentes contam como identificados, mas não vencidos", str(p["contatos"]))
checar(r.json()["total_com_identificacao"] == N_PRED + N_FB + 30 + 40,
       "o total do cabeçalho é a soma real", str(r.json()["total_com_identificacao"]))


# ── 2. a execução anonimiza tudo de uma vez ──────────────────────────────
print("\n— execução —")
r = c.post("/retencao/executar?empresa_id_alvo=alfa", headers=H)
checar(r.status_code == 200, "executa", str(r.status_code) + " " + r.text[:80])
res = r.json().get("anonimizadas", {})
checar(res.get("predicoes") == N_PRED, f"anonimiza as {N_PRED} predições num clique só",
       f"anonimizou {res.get('predicoes')}")
checar(res.get("feedbacks") == N_FB, "e os feedbacks", str(res.get("feedbacks")))

restam = sum(1 for l in PRED if l["id"].startswith("p") and not l["id"].startswith("pb")
             and l["anonimizado_em"] is None)
checar(restam == 0, "nenhuma predição da empresa ficou com CPF",
       f"{restam} sobraram — com o teto de mil, seriam {N_PRED - TETO_RESPOSTA}")
checar(all(l["cpf"] is not None or l["anonimizado_em"] for l in PRED),
       "e o que foi anonimizado perdeu o identificador")

beta = [l for l in PRED if l["id"].startswith("pb")] + [l for l in FB if l["id"].startswith("fb")]
checar(all(l["anonimizado_em"] is None for l in beta),
       "a outra empresa não foi tocada", f"{len(beta)} linhas da beta")

# executar de novo não encontra nada
r = c.post("/retencao/executar?empresa_id_alvo=alfa", headers=H)
checar(r.json().get("total") == 0, "segunda execução não acha mais nada",
       str(r.json().get("total")))


# ── 3. o pedido de titular acha o CPF em todas as tabelas ────────────────
print("\n— pedido de titular —")
for t in (PRED, FB, CT, RC):
    for l in t:
        if l.get("empresa", l.get("empresa_id")) == "alfa" or l["id"].startswith("p"):
            l["anonimizado_em"] = None
            if l["id"] in ("p7", "f7", "t7", "r7"):
                l["cpf"] = "00000000007"
r = c.post("/retencao/titular?empresa_id_alvo=alfa", headers=H, json={"cpf": "000.000.000-07"})
checar(r.status_code == 200, "atende", str(r.status_code) + " " + r.text[:80])
checar(r.json().get("total", 0) >= 4,
       "acha o CPF nas quatro tabelas, mesmo com a base maior que o teto",
       str(r.json().get("anonimizadas")))


# ── 4. leitura que quebra não vira "zero registros" ──────────────────────
print("\n— o banco falha na leitura —")
FALHA["tabela"] = "feedbacks"          # as carteiras respondem; só uma tabela do laço falha
r = c.get("/retencao?empresa_id_alvo=alfa", headers=H)
checar(r.status_code == 500, "a prévia devolve erro, não zeros", str(r.status_code))
checar("com_identificacao" not in r.text,
       "e não mostra número nenhum",
       "um '0 registros com CPF' faria o admin concluir que não há o que anonimizar")
r = c.post("/retencao/executar?empresa_id_alvo=alfa", headers=H)
checar(r.status_code == 500, "a execução também devolve erro, não 'concluído'", str(r.status_code))
FALHA["tabela"] = None


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
