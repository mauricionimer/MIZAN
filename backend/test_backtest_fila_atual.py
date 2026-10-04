"""Backtest contra a fila que o banco usou de verdade (coluna ordem_atual).

    python test_backtest_fila_atual.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import numpy as np, pandas as pd
import backtest  # noqa: E402
from model import score as _score

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

colunas_vistas = []
original = _score.score_carteira
def espiao(df, empresa_id=None):
    colunas_vistas.append(set(df.columns))
    return original(df, empresa_id)
_score.score_carteira = espiao

rng = np.random.default_rng(7)
n = 600
base = pd.DataFrame({"cpf": [f"{i:011d}" for i in range(n)],
                     "valor_divida": rng.lognormal(8, 1, n).round(2),
                     "dias_em_atraso": rng.integers(10, 400, n),
                     "pagou": rng.integers(0, 2, n)})

r = backtest.rodar(base.copy())
checar(r["ganho_sobre_fila_atual"] is None and "fila_atual" not in r["filas"],
       "sem ordem_atual: nada muda (compara com maior dívida)")

# A fila do banco igual a "maior dívida primeiro": as duas têm de capturar o mesmo.
df = base.copy()
df["ordem_atual"] = (-df["valor_divida"]).rank(method="first").astype(int)
r = backtest.rodar(df)
f = r["filas"]
checar(all(f["fila_atual"][c]["valor_capturado"] == f["maior_divida"][c]["valor_capturado"]
           for c in backtest.CAPACIDADES), "ordem igual à maior dívida: mesma captura")
g = r["ganho_sobre_fila_atual"][0.2]
checar(g["fila_atual"] == f["fila_atual"][0.2]["valor_capturado"]
       and g["diferenca"] == round(g["mizan"] - g["fila_atual"], 2),
       "ganho contra a fila do banco = Mizan − fila do banco")
checar("ordem_atual" not in colunas_vistas[-1], "a ordem do banco não entra no modelo")

# Outro nome para a mesma coluna; e posições faltando vão para o fim.
df = base.copy()
df["ordem_banco"] = np.arange(1, n + 1, dtype=float)
df.loc[:9, "ordem_banco"] = np.nan
r = backtest.rodar(df)
topo = r["filas"]["fila_atual"][0.1]["n_trabalhados"]
checar(r["ganho_sobre_fila_atual"] is not None, "aceita o nome 'ordem_banco'")
checar(any("sem posição" in a for a in r["avisos"]), "avisa quem ficou sem posição")
ordem_esperada = list(range(10, n)) + list(range(10))
cap10 = base.iloc[ordem_esperada[:topo]]
esperado = round(float((cap10["pagou"] * cap10["valor_divida"]).sum()), 2)
checar(abs(r["filas"]["fila_atual"][0.1]["valor_capturado"] - esperado) < 0.01,
       "sem posição = fim da fila", f"{r['filas']['fila_atual'][0.1]['valor_capturado']} vs {esperado}")

# Ordem montada sabendo o resultado: avisa.
df = base.copy()
df["ordem_atual"] = (-df["pagou"] * 1e6 - df["valor_divida"]).rank(method="first")
r = backtest.rodar(df)
checar(any("sabendo o resultado" in a for a in r["avisos"]), "ordem que já conhece o desfecho é sinalizada")

# Coluna sem números: ignorada, com aviso.
df = base.copy(); df["ordem_atual"] = "x"
r = backtest.rodar(df)
checar(r["ganho_sobre_fila_atual"] is None and any("sem números" in a for a in r["avisos"]),
       "ordem_atual sem números é ignorada e avisada")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
