"""Premissas da empresa: validadas, auditadas e sem apagar o resto da configuração.

    python test_premissas.py
"""
import os, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from model import premissas as P                   # noqa: E402
from model import ciclo, priorizacao, proposta     # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

# ── validação ────────────────────────────────────────────────────────────
print("— validação —")
lim, err = P.validar({"comissao_especializada_pct": "18,5", "cessao_pct": 3, "recuperacao_se_pagar": 0.8,
                      "criterio_priorizacao": "proporcional_por_grupo", "buffer_margem_pct": 25,
                      "comprometimento_max_pct": 50})
checar(not err and lim["comissao_especializada_pct"] == 18.5, "valores válidos passam; vírgula decimal é aceita", str(err))
for chave, ruim, trecho in [
    ("comissao_especializada_pct", -1, "mínimo"), ("comissao_especializada_pct", 101, "máximo"),
    ("comissao_especializada_pct", "abc", "número"), ("comissao_especializada_pct", True, "número"),
    ("comissao_especializada_pct", float("nan"), "número"),
    ("recuperacao_se_pagar", 0, "maior que"), ("recuperacao_se_pagar", 1.5, "máximo"),
    ("buffer_margem_pct", 100, "menor que"), ("comprometimento_max_pct", 0, "maior que"),
    ("criterio_priorizacao", "qualquer", "opções"),
]:
    _, e = P.validar({chave: ruim})
    checar(chave in e and trecho in e[chave], f"{chave}={ruim!r} é recusado", str(e.get(chave)))
_, e = P.validar({"comisao_especializada_pct": 10})
checar("comisao_especializada_pct" in e, "chave com erro de digitação é recusada, não ignorada")
lim, _ = P.validar({"cessao_pct": None})
checar(lim == {"cessao_pct": None}, "null apaga e volta ao padrão")
checar(P.aplicar({"retencao": {"ativa": True, "dias": 365}, "cessao_pct": 3}, {"cessao_pct": None, "buffer_margem_pct": 20})
       == {"retencao": {"ativa": True, "dias": 365}, "buffer_margem_pct": 20}, "aplicar preserva o resto da configuração")

# os padrões da tela são os do código que calcula
checar(P.PREMISSAS["buffer_margem_pct"].padrao == proposta.BUFFER_MARGEM_PCT_PADRAO
       and P.PREMISSAS["comprometimento_max_pct"].padrao == proposta.COMPROMETIMENTO_MAX_PCT_PADRAO
       and P.PREMISSAS["criterio_priorizacao"].padrao == priorizacao.CRITERIO_PADRAO
       and P.PREMISSAS["recuperacao_se_pagar"].padrao == main.PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO,
       "os padrões mostrados são os mesmos que o código aplica")

# ── rotas ────────────────────────────────────────────────────────────────
print("\n— rotas —")
TAB = {"empresa_config": [{"empresa_id": "alfa", "extra": {"retencao": {"ativa": True, "dias": 365}, "outra": 1}}]}
AUD, FALHA_LEITURA = [], {"v": False}
class Q:
    def __init__(s, t): s.t, s.f, s.op, s.d = t, {}, "select", None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f[c] = v; return s
    def limit(s, *a): return s
    def update(s, d): s.op, s.d = "update", d; return s
    def insert(s, d): s.op, s.d = "insert", d; return s
    def execute(s):
        if s.op == "select":
            if FALHA_LEITURA["v"]: raise RuntimeError("banco fora")
            return type("R", (), {"data": [r for r in TAB.get(s.t, []) if all(r.get(k) == v for k, v in s.f.items())]})()
        if s.op == "update":
            for r in TAB[s.t]:
                if all(r.get(k) == v for k, v in s.f.items()): r.update(s.d)
        else:
            TAB.setdefault(s.t, []).append(dict(s.d))
        return type("R", (), {"data": [1]})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
U = {"op": {"ativo": True, "id": "op", "role": "operador", "empresa_id": "alfa"},
     "ad": {"ativo": True, "id": "ad", "role": "admin", "empresa_id": "alfa"},
     "ab": {"ativo": True, "id": "ab", "role": "admin", "empresa_id": "beta"},
     "co": {"ativo": True, "id": "co", "role": "comando", "empresa_id": ""}}
main.buscar_usuario_por_id = lambda uid: U[uid]
main._registrar_auditoria = lambda *a, **k: AUD.append(k or {"args": a})
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "e@e.com", "nome": "N", "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}

checar(c.get("/empresa/premissas", headers=H("op")).status_code == 403, "operador não lê as premissas")
checar(c.put("/empresa/premissas", headers=H("op"), json={"valores": {"cessao_pct": 3}}).status_code == 403, "nem grava")
r = c.get("/empresa/premissas", headers=H("ad")); j = r.json()
lista = {p["chave"]: p for p in j["premissas"]}
checar(r.status_code == 200 and len(lista) == 6 and not any(p["definida"] for p in lista.values()), "admin lê: seis premissas, nenhuma informada ainda")
checar(lista["buffer_margem_pct"]["valor"] == 30.0 and lista["comissao_especializada_pct"]["valor"] is None, "valores efetivos: padrão onde não há, e 'não informado' sem padrão")
checar(c.get("/empresa/premissas", headers=H("co")).status_code == 400, "comando sem escolher empresa: 400")
checar(c.get("/empresa/premissas", headers=H("co"), params={"empresa_id_alvo": "alfa"}).status_code == 200, "comando escolhe a empresa")

r = c.put("/empresa/premissas", headers=H("ad"), json={"valores": {"comissao_especializada_pct": "18,5", "recuperacao_se_pagar": 0.8, "criterio_priorizacao": "proporcional_por_grupo"}})
checar(r.status_code == 200, "admin grava", f"{r.status_code} {r.text[:80]}")
extra = TAB["empresa_config"][0]["extra"]
checar(extra.get("retencao") == {"ativa": True, "dias": 365} and extra.get("outra") == 1, "a retenção e o resto da configuração continuam lá")
checar(extra["comissao_especializada_pct"] == 18.5 and extra["recuperacao_se_pagar"] == 0.8, "valores gravados já limpos")
# o código que calcula lê o que foi gravado
custos = ciclo.custos_de_config(main._extra_empresa("alfa"))
checar(custos["comissao_pct"] == 18.5 and custos["origem"] == "configurado", "o ciclo de cobrança passa a usar a comissão")
checar(priorizacao.de_config(main._extra_empresa("alfa")) == "proporcional_por_grupo", "a fila passa a usar o critério")
checar(main._premissa_recuperacao_se_pagar("alfa") == 0.8, "a taxa passa a usar 'recuperação se pagar'")
checar(any(a.get("acao") == "premissas_atualizadas" and a["detalhes"]["comissao_especializada_pct"] == {"antes": None, "depois": 18.5} for a in AUD),
       "ficou na auditoria, com o antes e o depois")

r = c.put("/empresa/premissas", headers=H("ad"), json={"valores": {"comissao_especializada_pct": 150, "criterio_priorizacao": "x"}})
checar(r.status_code == 422 and set(r.json()["detail"]["erros"]) == {"comissao_especializada_pct", "criterio_priorizacao"},
       "valor inválido: 422 com o erro de cada campo", str(r.json())[:100])
checar(TAB["empresa_config"][0]["extra"]["comissao_especializada_pct"] == 18.5, "e nada foi alterado")
r = c.put("/empresa/premissas", headers=H("ad"), json={"valores": {"comissao_especializada_pct": 12, "buffer_margem_pct": 500}})
checar(r.status_code == 422 and TAB["empresa_config"][0]["extra"]["comissao_especializada_pct"] == 18.5,
       "um campo ruim derruba o conjunto: não grava só os bons")

r = c.put("/empresa/premissas", headers=H("ad"), json={"valores": {"comissao_especializada_pct": None}})
checar(r.status_code == 200 and "comissao_especializada_pct" not in TAB["empresa_config"][0]["extra"], "null apaga: volta ao padrão")

r = c.put("/empresa/premissas", headers=H("ab"), json={"valores": {"cessao_pct": 4}})
checar(r.status_code == 200 and TAB["empresa_config"][0]["extra"].get("cessao_pct") is None
       and any(x["empresa_id"] == "beta" for x in TAB["empresa_config"]), "admin de outra empresa grava só na dele (cria a linha)")

FALHA_LEITURA["v"] = True
antes = dict(TAB["empresa_config"][0]["extra"])
r = c.put("/empresa/premissas", headers=H("ad"), json={"valores": {"cessao_pct": 9}})
FALHA_LEITURA["v"] = False
checar(r.status_code == 503 and TAB["empresa_config"][0]["extra"] == antes,
       "se o banco falha ao ler, não grava: não apaga a retenção", str(r.status_code))

# a rota genérica não é atalho para valor inválido
r = c.put("/empresa/config", headers=H("ad"), json={"extra": {"cessao_pct": 999}})
checar(r.status_code == 400, "PUT /empresa/config também recusa premissa fora do limite", str(r.status_code))
r = c.put("/empresa/config", headers=H("ad"), json={"extra": {"cessao_pct": 4}})
checar(r.status_code == 200 and TAB["empresa_config"][0]["extra"]["cessao_pct"] == 4.0, "e aceita a válida")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
