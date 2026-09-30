"""Regressão: pontuar em lotes dá exatamente o mesmo resultado.

    python test_score_em_lotes.py

A pontuação era o pico de memória da análise. Medido numa carteira de 200 mil
devedores: o processo saía de 167 MB para 542 MB — a matriz de features
alargada pelo one-hot, a versão escalada em float64 e a entrada do
classificador, todas vivas ao mesmo tempo e todas do tamanho da carteira.

Cada linha é pontuada sozinha, então processar em blocos prende o pico ao
tamanho do bloco. Mas "prende o pico" só vale se o resultado for o MESMO — não
parecido, o mesmo. Um score que variasse na terceira casa entre uma execução e
outra mudaria a ordem da fila e, com ela, a etiqueta de prioridade de quem está
na fronteira.

Por isso o teste compara valor a valor, com um tamanho de carteira que não é
múltiplo do lote: o último bloco quebrado é onde um erro de índice apareceria.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import numpy as np                                 # noqa: E402
import pandas as pd                                # noqa: E402
from model import score as S                       # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


def carteira(n, semente=3):
    r = np.random.default_rng(semente)
    return pd.DataFrame({
        "cpf": [f"{i:011d}" for i in range(n)],
        "nome": ["Maria Aparecida"] * n,
        "valor_divida": r.lognormal(8.2, .9, n).round(2),
        "renda_estimada": r.lognormal(7.9, .6, n).round(2),
        "dias_em_atraso": r.integers(5, 900, n),
        "produto": r.choice(["cartao", "consignado", "pessoal"], n),
        "uf": r.choice(["GO", "SP", "MG"], n),
        "status": ["inadimplente"] * n,
    })


COLUNAS = ("score_recuperabilidade", "cluster_id", "perfil_cluster",
           "dados_incompletos", "aviso_dados")


def comparar(n, lote, titulo):
    df = carteira(n)
    S.LOTE_SCORE = lote
    em_lotes = S.score_carteira(df)
    S.LOTE_SCORE = 10 ** 9          # tudo de uma vez, como era antes
    de_uma_vez = S.score_carteira(df)

    for col in COLUNAS:
        iguais = bool((em_lotes[col] == de_uma_vez[col]).all())
        if not iguais:
            checar(False, f"{titulo}: {col} divergiu")
            return
    dif = float((em_lotes["score_recuperabilidade"]
                 - de_uma_vez["score_recuperabilidade"]).abs().max())
    checar(dif == 0.0, titulo, f"maior diferença de score: {dif}")


# ── O caso que mais erra: o último bloco não fecha certo ─────────────────
print("— resultado idêntico —")
comparar(2_500, 1_000, "carteira com resto quebrado (2.500 em blocos de 1.000)")
comparar(3_000, 1_000, "carteira múltipla exata do lote (3.000 em blocos de 1.000)")
comparar(999, 1_000, "carteira menor que um bloco")
comparar(1_000, 1_000, "carteira do tamanho exato de um bloco")


# ── Tamanhos de borda ────────────────────────────────────────────────────
print("\n— bordas —")
S.LOTE_SCORE = 20_000
um = S.score_carteira(carteira(1))
checar(len(um) == 1 and um["score_recuperabilidade"].notna().all(),
       "carteira de um devedor é pontuada")

S.LOTE_SCORE = 1
tres = S.score_carteira(carteira(3))
S.LOTE_SCORE = 10 ** 9
tres_junto = S.score_carteira(carteira(3))
checar(bool((tres["score_recuperabilidade"] == tres_junto["score_recuperabilidade"]).all()),
       "lote de uma linha por vez também bate",
       "o caso extremo do bloco: se o índice estiver errado, aparece aqui")


# ── A ordem das linhas não pode mudar ────────────────────────────────────
print("\n— a ordem —")
S.LOTE_SCORE = 500
df = carteira(1_750)
out = S.score_carteira(df)
checar(list(out["cpf"]) == list(df["cpf"]),
       "as linhas voltam na ordem em que entraram",
       "a fila é ordenada depois; embaralhar aqui trocaria devedor de score")

S.LOTE_SCORE = 20_000   # devolve o padrão para quem importar depois
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
