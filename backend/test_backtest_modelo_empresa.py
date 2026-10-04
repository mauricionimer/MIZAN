"""O backtest pontua com o modelo da empresa, o mesmo que a análise usa.

    python test_backtest_modelo_empresa.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import numpy as np, pandas as pd
import main, backtest  # noqa: E402
from model import score as _score
from fastapi.testclient import TestClient

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

pedidos = []
original = _score.score_carteira
def espiao(df, empresa_id=None):
    pedidos.append(empresa_id)
    return original(df, None)          # pontua com o base: aqui só importa QUAL foi pedido
_score.score_carteira = espiao

rng = np.random.default_rng(3)
n = 400
df = pd.DataFrame({"cpf": [f"{i:011d}" for i in range(n)],
                   "valor_divida": rng.lognormal(8, 1, n).round(2),
                   "dias_em_atraso": rng.integers(10, 400, n),
                   "pagou": rng.integers(0, 2, n)})

backtest.rodar(df.copy(), "goias_bank")
checar(pedidos[-1] == "goias_bank", "rodar() pede o modelo da empresa informada", str(pedidos[-1]))
backtest.rodar(df.copy())
checar(pedidos[-1] is None, "sem empresa, o modelo base", str(pedidos[-1]))

PAPEL = {"p": {"sub": "u1", "email": "a@g.com", "role": "admin", "empresa_id": "goias_bank"}}
main._usuario_autenticado = lambda cred: dict(PAPEL["p"])
hc = TestClient(main.app)
arq = ("h.csv", df.to_csv(index=False).encode(), "text/csv")
r = hc.post("/backtest", files={"file": arq}, data={"empresa_id": "outra"}, headers={"Authorization": "Bearer t"})
checar(r.status_code == 200 and pedidos[-1] == "goias_bank",
       "admin: sempre o modelo da própria empresa, ignora o empresa_id enviado", f"{r.status_code} {pedidos[-1]}")
PAPEL["p"] = {"sub": "c1", "email": "c@m.app", "role": "comando", "empresa_id": ""}
r = hc.post("/backtest", files={"file": arq}, data={"empresa_id": " Goias_Bank "}, headers={"Authorization": "Bearer t"})
checar(r.status_code == 200 and pedidos[-1] == "goias_bank", "comando: o modelo da cliente escolhida", f"{r.status_code} {pedidos[-1]}")
r = hc.post("/backtest", files={"file": arq}, headers={"Authorization": "Bearer t"})
checar(r.status_code == 200 and pedidos[-1] is None, "comando sem empresa: o modelo base", f"{r.status_code} {pedidos[-1]}")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
