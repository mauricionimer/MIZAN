"""Regressão: reabrir uma carteira devolve a MESMA fila que foi analisada.

    python test_ordem_fila.py

A posição de um devedor na fila é resultado da política de priorização sobre o
valor esperado líquido — foi a mudança mais consequente do produto, porque
ordenar por probabilidade perdia para "maior dívida primeiro".

O rank nunca era gravado. Ao reabrir, o sistema reordenava por
score_recuperabilidade e renumerava: a decisão inteira era desfeita em
silêncio. Numa carteira de teste, 1 em cada 20 devedores ficava na mesma
posição e 11 em 20 mudavam de faixa de prioridade — o que muda a etiqueta
Alta/Média/Baixa, o alcance da operação e quem o operador liga primeiro.

O banco em produção pode ter carteiras gravadas antes disso, sem rank. Para
elas a ordem é recomputada com a mesma política, e não por score.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


main._extra_empresa = lambda eid: {}


def devedor(cpf, score, divida, rank=None, uf="GO"):
    linha = {
        "cpf": cpf, "uf": uf, "score_recuperabilidade": score, "valor_divida": divida,
        "valor_esperado_liquido": round(score / 100 * divida, 2),
        "valor_esperado_recuperacao": round(score / 100 * divida, 2),
    }
    if rank is not None:
        linha["rank"] = rank
    return linha


# ── 1. com rank gravado, o banco manda ───────────────────────────────────
print("— carteira gravada com rank —")

# Propositalmente embaralhado e com score CRESCENTE junto ao rank, de modo que
# ordenar por score daria exatamente o contrário do rank.
gravada = [
    devedor("003", 90.0, 1_000, rank=3),
    devedor("001", 30.0, 90_000, rank=1),
    devedor("002", 60.0, 10_000, rank=2),
]
ranking = main._reconstruir_ranking(gravada, "banco_alfa")

checar([d["cpf"] for d in ranking] == ["001", "002", "003"],
       "a fila sai na ordem do rank gravado",
       str([d["cpf"] for d in ranking]))
checar([d["rank"] for d in ranking] == [1, 2, 3], "e o rank é preservado, não renumerado")
checar(ranking[0]["cpf"] == "001",
       "quem tem score 30 e dívida de 90 mil vem antes de score 90 e dívida de mil",
       "é a decisão de ordenar por valor, e ela precisa sobreviver ao reload")


# ── 2. sem rank, recomputa pela política — não por score ─────────────────
print("\n— carteira antiga, sem rank —")

antiga = [
    devedor("003", 90.0, 1_000),
    devedor("001", 30.0, 90_000),
    devedor("002", 60.0, 10_000),
]
ranking = main._reconstruir_ranking(antiga, "banco_alfa")
por_score = [d["cpf"] for d in sorted(antiga, key=lambda p: -p["score_recuperabilidade"])]

checar([d["cpf"] for d in ranking] == ["001", "002", "003"],
       "recompõe por valor esperado, como a análise faria",
       str([d["cpf"] for d in ranking]))
checar([d["cpf"] for d in ranking] != por_score,
       "e NÃO por score, que era o comportamento antigo",
       f"por score seria {por_score}")
checar([d["rank"] for d in ranking] == [1, 2, 3], "o rank é atribuído pela posição")


# ── 3. mistura: linhas sem rank não embaralham o topo ────────────────────
print("\n— mistura (gravação parcial antes do ALTER TABLE) —")

mista = [
    devedor("sem_a", 99.0, 500),
    devedor("com_1", 10.0, 5_000, rank=1),
    devedor("sem_b", 95.0, 600),
    devedor("com_2", 20.0, 4_000, rank=2),
]
ranking = main._reconstruir_ranking(mista, "banco_alfa")
checar([d["cpf"] for d in ranking][:2] == ["com_1", "com_2"],
       "quem tem rank ocupa o começo da fila",
       str([d["cpf"] for d in ranking]))
checar(set([d["cpf"] for d in ranking][2:]) == {"sem_a", "sem_b"},
       "e quem não tem vai para o fim, em vez de furar a ordem")


# ── 4. o que já funcionava continua ──────────────────────────────────────
print("\n— o resto do contrato —")

sem_ve = [{"cpf": "x", "rank": 1, "valor_divida": 1000.0, "score_recuperabilidade": 40.0}]
r = main._reconstruir_ranking(sem_ve, "banco_alfa")
checar(r[0]["valor_esperado_recuperacao"] == 400.0,
       "valor esperado ausente continua sendo derivado de score × dívida")

checar(main._reconstruir_ranking([], "banco_alfa") == [],
       "carteira vazia não quebra")

um = main._reconstruir_ranking([devedor("u", 50.0, 100)], "banco_alfa")
checar(len(um) == 1 and um[0]["rank"] == 1, "carteira de um devedor não quebra")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
