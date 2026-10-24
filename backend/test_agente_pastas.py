"""Pastas de devedores: lista com a cor do semáforo, busca e filtro por cor.

    python test_agente_pastas.py
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste", MIZAN_AGENTE_ATIVO="1")

import main                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from auth import criar_token                       # noqa: E402
from agente import api as agente_api               # noqa: E402
from agente.repositorio import RepoMemoria         # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


N = 30
PREDICOES = [{"id": f"p{r}", "carteira_id": "cart-1", "rank": r, "cpf": f"{r:011d}",
              "nome": f"Devedor {r}" if r != 7 else "Mariana Alves",
              "valor_divida": 1000.0 * r, "dias_em_atraso": r, "score_recuperabilidade": float(r)}
             for r in range(1, N + 1)]
CARTEIRAS = [{"id": "cart-1", "empresa_id": "banco_alfa"}, {"id": "cart-outra", "empresa_id": "banco_beta"}]


class Q:
    def __init__(self, linhas):
        self.linhas, self._neg, self._faixa, self._lim = list(linhas), False, None, None
        self._ordens = []

    def select(self, *a, **k): return self
    def limit(self, n): self._lim = n; return self
    def eq(self, col, val): self.linhas = [l for l in self.linhas if l.get(col) == val]; return self

    def in_(self, col, vals):
        vals = set(vals)
        self.linhas = [l for l in self.linhas if (l.get(col) not in vals) == self._neg]
        self._neg = False
        return self

    @property
    def not_(self): self._neg = True; return self

    def or_(self, expr):
        alvos = [(p.split(".", 2)[0], p.split(".", 2)[2].strip("*").lower()) for p in expr.split(",")]
        self.linhas = [l for l in self.linhas if any(v in str(l.get(c) or "").lower() for c, v in alvos)]
        return self

    def order(self, col, desc=False):
        self._ordens.append((col, desc)); return self

    def range(self, a, b): self._faixa = (a, b); return self

    def execute(self):
        total, dados = len(self.linhas), self.linhas
        for col, desc in reversed(self._ordens):
            dados = sorted(dados, key=lambda l: (l.get(col) is None, l.get(col) or 0), reverse=desc)
        if self._faixa:
            dados = dados[self._faixa[0]:self._faixa[1] + 1]
        if self._lim is not None:
            dados = dados[:self._lim]
        return type("R", (), {"data": dados, "count": total})()


class DB:
    def table(self, nome):
        return Q({"predicoes": PREDICOES, "carteiras": CARTEIRAS}.get(nome, []))


repo = RepoMemoria()


def caso(pid, situacao, **dados):
    c = repo.obter_ou_criar_caso("banco_alfa", pid)
    repo.salvar_caso(c["id"], {"situacao": situacao, "dados": dados})


agora = datetime.now(timezone.utc).isoformat()
caso("p3", "atrasado")                                                           # vermelho (regra)
caso("p7", "negociando")                                                         # amarelo
caso("p9", "em_contato", leitura={"quando": agora, "emocao": "irritado", "sinais": []})   # vermelho (leitura)
caso("p12", "novo", leitura={"quando": agora, "semaforo": "amarelo", "semaforo_motivo": "tem dúvida real", "sinais": []})
caso("p15", "quitado")                                                           # branco

main.get_db = lambda: DB()
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
main._extra_empresa = lambda eid: {}
agente_api.fabrica_repo = lambda: repo
c = TestClient(main.app)


def token(empresa="banco_alfa", role="admin"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "a@a.com", "nome": "A", "role": role, "empresa_id": empresa})}


def pastas(**p):
    return c.get("/agente/pastas", headers=token(), params={"carteira_id": "cart-1", **p})


print("— lista e cores —")
r = pastas(limit=60)
d = r.json()
checar(r.status_code == 200 and d["agente_ligado"] is True, "responde", str(r.status_code) + r.text[:80])
cores = {i["id"]: i["semaforo"]["cor"] for i in d["itens"]}
checar(cores["p3"] == "vermelho" and cores["p9"] == "vermelho", "atrasado e irritado são vermelhos")
checar(cores["p7"] == "amarelo" and cores["p12"] == "amarelo", "negociando e leitura do agente são amarelos")
checar(cores["p15"] == "branco" and cores["p20"] == "branco", "quitado e quem nunca foi acionado são brancos")
checar([i["semaforo"]["cor"] for i in d["itens"][:4]] == ["vermelho", "vermelho", "amarelo", "amarelo"],
       "os urgentes vêm primeiro", str([i["id"] for i in d["itens"][:5]]))
checar([i["rank"] for i in d["itens"][:2]] == [3, 9], "dentro de cada cor, pela fila")
checar(d["contagem"] == {"vermelho": 2, "amarelo": 2, "branco": N - 4, "total": N}, "contagens por cor", str(d["contagem"]))
checar(len(d["itens"]) == N, "traz todos sem repetir", str(len(d["itens"])))
checar(len({i["id"] for i in d["itens"]}) == N, "sem repetição")
checar(d["itens"][0]["cpf"].count("*") == 6 and "00000000003" not in str(d), "o CPF sai parcial")
checar(any(a["name"] == "Situação" for a in d["itens"][0]["arquivos"]), "a pasta traz os arquivos do caso")
checar(d["itens"][-1]["arquivos"][0]["name"] == "Sem atendimento", "quem não tem caso: pasta sem atendimento")

print("— filtro por cor —")
for cor, esperados in (("vermelho", [3, 9]), ("amarelo", [7, 12])):
    r = pastas(cor=cor).json()
    checar([i["rank"] for i in r["itens"]] == esperados, f"só {cor}", str([i["rank"] for i in r["itens"]]))
r = pastas(cor="branco", limit=60).json()
checar(len(r["itens"]) == N - 4 and all(i["semaforo"]["cor"] == "branco" for i in r["itens"]), "só brancos", str(len(r["itens"])))
checar(pastas(cor="roxo").status_code == 422, "cor inválida é recusada")

print("— busca —")
r = pastas(busca="mariana").json()
checar([i["nome"] for i in r["itens"]] == ["Mariana Alves"] and r["itens"][0]["semaforo"]["cor"] == "amarelo", "acha pelo nome")
r = pastas(busca="00000000009").json()
checar([i["id"] for i in r["itens"]] == ["p9"], "acha pelo CPF")
checar(pastas(busca="zzzz").json()["itens"] == [], "sem resultado vem vazio")
r = pastas(busca="Devedor 1").json()
checar(r["contagem"]["total"] == len(r["itens"]) == 11 and r["filtrado"] == 11, "a contagem acompanha a busca", str(r["contagem"]))

print("— paginação —")
a, b = pastas(limit=10, offset=0).json(), pastas(limit=10, offset=10).json()
checar(len(a["itens"]) == 10 and len(b["itens"]) == 10 and not ({i["id"] for i in a["itens"]} & {i["id"] for i in b["itens"]}),
       "páginas sem repetir")
checar([i["rank"] for i in a["itens"][:4]] == [3, 9, 7, 12], "a primeira página começa pelos destaques")
checar(a["filtrado"] == N, "filtrado = total da busca")

print("— acesso —")
r = c.get("/agente/pastas", headers=token("banco_beta"), params={"carteira_id": "cart-1"})
checar(r.status_code == 403, "outra empresa não lê a carteira", str(r.status_code))
checar(c.get("/agente/pastas", params={"carteira_id": "cart-1"}).status_code in (401, 403), "sem login não entra")

print("— agente desligado —")
os.environ["MIZAN_AGENTE_ATIVO"] = "0"
r = pastas(limit=60).json()
checar(r["agente_ligado"] is False and all(i["semaforo"]["cor"] == "branco" for i in r["itens"]),
       "sem o agente, todos aparecem brancos e a lista continua funcionando")
os.environ["MIZAN_AGENTE_ATIVO"] = "1"

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
