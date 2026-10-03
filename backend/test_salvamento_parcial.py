"""Gravação que falha no meio não deixa carteira pela metade nem finge sucesso.

    python test_salvamento_parcial.py
"""
import os, sys
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CART, PRED, LOG = {}, [], []
MODO = {"falhar_insercao": False}
class Q:
    def __init__(s, t): s.t = t; s.op = None; s.dados = None; s.f = {}
    def insert(s, d): s.op = "insert"; s.dados = d; return s
    def delete(s): s.op = "delete"; return s
    def update(s, d): s.op = "update"; return s
    def select(s, *a, **k): s.op = "select"; return s
    def eq(s, c, v): s.f[c] = v; return s
    def in_(s, *a): return s
    def is_(s, *a): return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s
    def range(s, *a): return s
    def execute(s):
        LOG.append((s.t, s.op))
        if s.t == "carteiras" and s.op == "insert":
            CART["c1"] = dict(s.dados); return type("R", (), {"data": [{"id": "c1"}]})()
        if s.t == "carteiras" and s.op == "delete":
            CART.pop(s.f.get("id"), None)
        if s.t == "predicoes" and s.op == "insert":
            if MODO["falhar_insercao"] and len(PRED) >= main.LOTE_INSERCAO:
                raise RuntimeError("conexão caiu")
            PRED.extend(s.dados)
            return type("R", (), {"data": [{"cpf": d["cpf"], "id": "i" + d["cpf"]} for d in s.dados]})()
        if s.t == "predicoes" and s.op == "delete":
            PRED[:] = [p for p in PRED if p["carteira_id"] != s.f.get("carteira_id")]
        return type("R", (), {"data": []})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._registrar_auditoria = lambda *a, **k: None

rng = np.random.default_rng(1)
N = 5000
df = pd.DataFrame({
    "cpf": [f"{i:011d}" for i in range(N)],
    "valor_divida": rng.lognormal(8.2, 0.9, N).round(2),
    "renda_estimada": rng.lognormal(7.9, 0.6, N).round(2),
    "dias_em_atraso": rng.integers(15, 900, N),
    "produto": rng.choice(["cartao", "consignado"], N),
    "uf": rng.choice(["GO", "SP"], N),
})

r = main._analisar_df(df.copy(), "t.csv", _empresa_id="e1")["resumo"]
checar(not r.get("salvamento_incompleto") and r.get("carteira_id") == "c1", "caminho feliz: salvo e sem alerta")
checar(len(PRED) == N, f"as {N} predições gravadas", str(len(PRED)))

CART.clear(); PRED.clear(); MODO["falhar_insercao"] = True
r = main._analisar_df(df.copy(), "t.csv", _empresa_id="e1")["resumo"]
checar(r.get("salvamento_incompleto") is True, "falha no meio: a resposta avisa que o salvamento foi incompleto")
checar(r.get("carteira_id") is None, "e não devolve o id de uma carteira que não existe mais")
checar(not CART and not PRED, "a carteira parcial e suas predições foram desfeitas",
       f"carteiras={len(CART)} predições={len(PRED)}")
checar(r.get("total_devedores") == N,
       "a análise em si continua na resposta")

# A tela pede a análise sem a fila (incluir_ranking=false) e busca as páginas
# no servidor. Sem carteira gravada não há servidor para paginar: a fila tem de
# vir na resposta, senão a tabela abre com "0 devedores".
CART.clear(); PRED.clear()
resp = main._analisar_df(df.copy(), "t.csv", _empresa_id="e1", _incluir_ranking=False)
checar(len(resp.get("ranking_completo") or []) == N,
       "gravação falhou: a fila inteira vem na resposta mesmo sem incluir_ranking",
       str(len(resp.get("ranking_completo") or [])))
CART.clear(); PRED.clear(); MODO["falhar_insercao"] = False
resp = main._analisar_df(df.copy(), "t.csv", _empresa_id="e1", _incluir_ranking=False)
checar("ranking_completo" not in resp, "gravação certa: a fila continua fora da resposta (vem por página)")
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
