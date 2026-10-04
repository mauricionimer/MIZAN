"""O que mais pesa no score: por empresa, no modelo que a pontua, e funcionando.

    python test_peso_variaveis.py

Antes a rota lia `feature_importances_` do modelo geral, que o modelo calibrado
não tem: respondia 400 e a tela mostrava sempre "indisponível". Agora usa o
mesmo método da explicação de cada devedor, nos devedores da empresa.
"""
import os, shutil, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
TMP = tempfile.mkdtemp(prefix="mizan_peso_")
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste", MIZAN_DATA_DIR=TMP)
(Path(TMP) / "model").mkdir(parents=True)
for n in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl"):
    shutil.copy(AQUI / "model" / n, Path(TMP) / "model" / n)

import main                                                       # noqa: E402
from auth import criar_token                                      # noqa: E402
from fastapi.testclient import TestClient                         # noqa: E402
from model import modelos_empresa as me, treino_empresa as te     # noqa: E402
from model.score import explicar_predicao, peso_das_variaveis     # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

rng = np.random.default_rng(5)
def devedores(n):
    return pd.DataFrame({"valor_divida": rng.lognormal(8, 0.8, n).round(2), "renda_estimada": rng.lognormal(7.9, 0.5, n).round(2),
                         "dias_em_atraso": rng.integers(10, 900, n), "produto": rng.choice(["cartao", "consignado", "pessoal"], n),
                         "uf": rng.choice(["GO", "SP", "DF"], n), "status": "inadimplente"})

print("— o método —")
df = devedores(40)
r = peso_das_variaveis(df)
por_var = {v["variavel"]: v for v in r["variaveis"]}
# o peso de cada variável é a média, em módulo, do que a explicação individual dá a ela
expl = [explicar_predicao(row) for row in df.to_dict("records")]
for var in ("dias_em_atraso", "valor_divida", "renda_estimada"):
    media = np.mean([abs(next(c["impacto_pontos"] for c in e["contribuicoes"] if c["variavel"] == var)) for e in expl])
    checar(abs(media - por_var[var]["impacto_medio_pontos"]) < 0.15,
           f"{var}: igual à média das explicações de cada devedor", f"{por_var[var]['impacto_medio_pontos']} vs {media:.2f}")
checar(abs(sum(v["percentual"] for v in r["variaveis"]) - 100) < 0.5, "as porcentagens somam 100")
checar("score_bureau" in r["nao_medidas"] and "score_bureau" not in por_var,
       "variável que a carteira não traz é listada como não medida, não como peso zero")
checar(not any(v["variavel"] in ("comprometimento_renda", "log_renda") for v in r["variaveis"]),
       "derivadas não são trocadas sozinhas (o efeito está na variável de origem)")

print("\n— a rota —")
PRED = [{"id": f"p{i:04d}", "carteira_id": "c-novo", **row} for i, row in enumerate(devedores(600).to_dict("records"))]
CART = [{"id": "c-velho", "empresa_id": "alfa", "created_at": "2026-01-01"},
        {"id": "c-novo", "empresa_id": "alfa", "created_at": "2026-09-01"}]
class Q:
    def __init__(s, t): s.l, s.lim, s.desc = list({"carteiras": CART, "predicoes": PRED}.get(t, [])), None, False
    def select(s, *a, **k): return s
    def eq(s, c, v): s.l = [x for x in s.l if x.get(c) == v]; return s
    def order(s, c, desc=False): s.l = sorted(s.l, key=lambda x: str(x.get(c)), reverse=desc); return s
    def limit(s, n): s.lim = n; return s
    def execute(s): return type("R", (), {"data": s.l[:s.lim] if s.lim else s.l})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
U = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": ""},
     "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "x@x", "nome": "N",
                                                          "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}
c = TestClient(main.app, raise_server_exceptions=False)
_r = c.get("/admin/feature-importance?empresa_id=beta", headers=H("ua"))
checar(_r.status_code == 200 and "beta" not in _r.text,
       "admin vê só a própria empresa (o empresa_id de outra é ignorado)", f"{_r.status_code}")
j = c.get("/admin/feature-importance", headers=H("uc")).json()
checar(j["ok"] is False and "empresa" in j["mensagem"], "sem empresa: pede para escolher")
j = c.get("/admin/feature-importance", headers=H("uc"), params={"empresa_id": "alfa"}).json()
checar(j.get("ok") and j["carteira_id"] == "c-novo" and j["n_devedores"] == 500,
       "mede em até 500 devedores da análise mais recente", f"{j.get('carteira_id')} {j.get('n_devedores')}")
checar(j["modelo"]["origem"] == "geral" and j["features"] and j["features"][0]["impacto_medio_pontos"] > 0,
       "modelo geral: devolve pesos (antes: sempre indisponível)", str(j["features"][:2]))
geral = {f["variavel"]: f["impacto_medio_pontos"] for f in j["features"]}

# a empresa ganha modelo próprio, com outra relação entre as variáveis
n = 3000
d = devedores(n)
pagou = (d["valor_divida"] < d["valor_divida"].median()).map({True: "sim", False: "não"})   # só o valor importa
reg = te.treinar(d.assign(pagou=pagou).to_csv(index=False).encode(), "h.csv", "alfa", "t")
me.ativar("alfa", reg["versao"])
j = c.get("/admin/feature-importance", headers=H("uc"), params={"empresa_id": "alfa"}).json()
proprio = {f["variavel"]: f["impacto_medio_pontos"] for f in j["features"]}
checar(j["modelo"]["origem"] == "proprio" and proprio != geral, "com modelo próprio ativo, mede o modelo próprio",
       f"{j['modelo']['origem']}")
checar(j["features"][0]["variavel"] == "valor_divida", "e aparece o que esse modelo aprendeu (só o valor importava)",
       str(j["features"][:2]))
j = c.get("/admin/feature-importance", headers=H("uc"), params={"empresa_id": "sem_analise"}).json()
checar(j["ok"] is False and "análise" in j["mensagem"], "empresa sem análise: diz isso", j.get("mensagem"))

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
