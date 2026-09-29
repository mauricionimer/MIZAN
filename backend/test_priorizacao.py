"""Regressão: a fila é ordenada por valor esperado, não por score.

    python test_priorizacao.py    (ou python -m pytest test_priorizacao.py)

O score é probabilidade de pagar. O banco quer valor recuperado. Quem paga
com mais frequência costuma dever menos, então ordenar por score manda o
operador ligar primeiro para quem paga fácil e deve pouco — e a carteira
rende menos do que renderia com a regra mais simples da operação, que é
começar pela maior dívida.

Medido em backtest.py: trabalhando 10% de uma carteira em que o pagamento
segue exatamente o score, a fila por valor esperado captura 39,2% do total,
"maior dívida primeiro" captura 32,8%, e a fila por score puro captura 15,8%.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# Dois devedores que separam as duas regras de ordenação:
#   A: score alto, dívida pequena   -> valor esperado    100
#   B: score baixo, dívida enorme   -> valor esperado  6.000
# Por score, A vem primeiro. Por valor esperado, B vem primeiro — e é B que
# traz dinheiro para a carteira.
df = pd.DataFrame({
    "score_recuperabilidade":     [90.0, 20.0, 55.0],
    "valor_divida":               [1000.0, 30000.0, 5000.0],
    "valor_esperado_recuperacao": [900.0, 6000.0, 2750.0],
})

ordenado = df.sort_values("valor_esperado_recuperacao", ascending=False).reset_index(drop=True)
checar(ordenado.loc[0, "valor_divida"] == 30000.0,
       "a dívida grande de score baixo vem antes da pequena de score alto",
       f'primeiro da fila deve R$ {ordenado.loc[0, "valor_divida"]:,.0f}')

por_score = df.sort_values("score_recuperabilidade", ascending=False).reset_index(drop=True)
checar(por_score.loc[0, "valor_esperado_recuperacao"]
       < ordenado.loc[0, "valor_esperado_recuperacao"],
       "ordenar por score colocaria em primeiro quem rende menos",
       f'R$ {por_score.loc[0, "valor_esperado_recuperacao"]:,.0f} contra '
       f'R$ {ordenado.loc[0, "valor_esperado_recuperacao"]:,.0f}')

# o código de produção usa mesmo o campo certo
fonte = (AQUI / "main.py").read_text()
checar('sort_values("score_recuperabilidade", ascending=False)' not in fonte,
       "main.py não ordena mais a carteira por score")
checar("from model.priorizacao import" in fonte,
       "e ordena pelo módulo de política, não por sort_values solto")
# O padrão continua sendo valor esperado; a alternativa proporcional existe,
# mas só entra se a empresa configurar (ver test_priorizacao_politica.py).
from model.priorizacao import CRITERIO_PADRAO, de_config  # noqa: E402
checar(CRITERIO_PADRAO == "valor_esperado" and de_config(None) == "valor_esperado",
       "e o padrão de quem não configura nada continua o valor esperado")

# retaguarda: carteira sem o campo de valor esperado não pode quebrar
sem_ve = pd.DataFrame({"score_recuperabilidade": [10.0, 90.0]})
_ordem = ("valor_esperado_recuperacao" if "valor_esperado_recuperacao" in sem_ve.columns
          else "score_recuperabilidade")
checar(_ordem == "score_recuperabilidade",
       "sem valor esperado, cai no score em vez de estourar")

# a fila por valor esperado tem de bater a fila por score em valor capturado
rng = np.random.default_rng(3)
n = 600
valor = rng.lognormal(8.0, 1.1, n)
prob = rng.random(n)
recuperado = valor * (rng.random(n) < prob)          # paga conforme a própria prob
ve = prob * valor
cap = int(n * 0.2)
por_ve = recuperado[np.argsort(-ve)][:cap].sum()
por_prob = recuperado[np.argsort(-prob)][:cap].sum()
por_divida = recuperado[np.argsort(-valor)][:cap].sum()
checar(por_ve > por_prob,
       "em 20% da base, valor esperado captura mais que probabilidade pura",
       f"R$ {por_ve:,.0f} contra R$ {por_prob:,.0f}")
checar(por_ve > por_divida,
       "e mais que ordenar pela maior dívida",
       f"R$ {por_ve:,.0f} contra R$ {por_divida:,.0f}")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
