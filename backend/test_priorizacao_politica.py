"""Regressão: as duas políticas de fila, e o que cada uma custa.

    python test_priorizacao_politica.py

Medir equidade mostrou que ordenar por valor esperado desprioriza a região de
dívidas menores mesmo quando ela paga igual — valor esperado é probabilidade
vezes dívida, e dívida menor perde sempre. Não é defeito: é o preço de
maximizar recuperação.

A política proporcional troca recuperação por paridade. Este teste confere que
a troca acontece nos dois sentidos: a proporcional equaliza de verdade, e
recupera menos de verdade. Uma alternativa que não custasse nada seria sinal
de que ela não está fazendo nada.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from model.equidade import analisar            # noqa: E402
from model.priorizacao import de_config, ordenar  # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# Duas regiões do mesmo tamanho, que PAGAM IGUAL e só diferem no valor devido.
rng = np.random.default_rng(5)
N = 600
grupo = np.array(["GO"] * N + ["BA"] * N)
valor = np.concatenate([rng.lognormal(8.6, 0.6, N), rng.lognormal(7.4, 0.6, N)])
prob = rng.random(2 * N) * 0.6 + 0.2
pagou = rng.random(2 * N) < 0.40
recuperado = valor * pagou
CAP = int(0.20 * len(valor))


def medir(criterio):
    ordem = ordenar(valor, prob, grupo, criterio)
    sel = np.zeros(len(valor), dtype=bool)
    sel[ordem[:CAP]] = True
    eq = analisar(pd.DataFrame({"uf": grupo}), "uf", sel, pagou)
    return {
        "recuperado": recuperado[sel].sum(),
        "paridade": eq["paridade_demografica"]["razao"],
        "oportunidade": eq["igualdade_oportunidade"]["razao"],
        "ba": int(sel[N:].sum()),
    }

ve = medir("valor_esperado")
pp = medir("proporcional_por_grupo")

print(f"   valor esperado : recupera R$ {ve['recuperado']:>12,.0f} · paridade {ve['paridade']:.2f} · BA {ve['ba']}")
print(f"   proporcional   : recupera R$ {pp['recuperado']:>12,.0f} · paridade {pp['paridade']:.2f} · BA {pp['ba']}")
print()

# ── o problema existe ─────────────────────────────────────────────────────
checar(ve["paridade"] < 0.80,
       "por valor esperado, a região de dívidas menores é desprioriza",
       f'paridade {ve["paridade"]:.2f}')

# ── a alternativa resolve ─────────────────────────────────────────────────
checar(pp["paridade"] >= 0.95,
       "a política proporcional equaliza a fatia por região",
       f'paridade {pp["paridade"]:.2f}')
checar(pp["oportunidade"] >= 0.80,
       "e também entre quem pagou", f'oportunidade {pp["oportunidade"]:.2f}')
checar(abs(pp["ba"] - CAP / 2) <= 2,
       "com metade do esforço para cada região de mesmo tamanho",
       f'{pp["ba"]} de {CAP}')

# ── e cobra o preço ───────────────────────────────────────────────────────
checar(pp["recuperado"] < ve["recuperado"],
       "a equidade custa recuperação — alternativa de graça seria suspeita",
       f'R$ {ve["recuperado"] - pp["recuperado"]:,.0f} a menos')

# ── a proporção vale em QUALQUER corte, não só no que foi escolhido ───────
ordem_pp = ordenar(valor, prob, grupo, "proporcional_por_grupo")
for corte in (50, 120, 400, 900):
    ba = int((grupo[ordem_pp[:corte]] == "BA").sum())
    checar(abs(ba - corte / 2) <= 2,
           f"em {corte} contatos, a divisão segue proporcional", f"BA com {ba}")

# ── dentro do grupo, continua valendo valor esperado ──────────────────────
ev = valor * prob
so_ba = [i for i in ordem_pp if grupo[i] == "BA"]
checar(all(ev[so_ba[i]] >= ev[so_ba[i + 1]] - 1e-9 for i in range(len(so_ba) - 1)),
       "dentro de cada região, a ordem continua por valor esperado")

# ── grupos de tamanhos diferentes: a fatia acompanha o tamanho ────────────
g2 = np.array(["A"] * 100 + ["B"] * 900)
v2 = rng.lognormal(8, 0.5, 1000)
p2 = rng.random(1000)
ord2 = ordenar(v2, p2, g2, "proporcional_por_grupo")
a_em_100 = int((g2[ord2[:100]] == "A").sum())
checar(abs(a_em_100 - 10) <= 2,
       "grupo com 10% da carteira recebe ~10% dos contatos", f"{a_em_100} de 100")

# ── o padrão e a configuração ─────────────────────────────────────────────
checar(de_config(None) == "valor_esperado", "sem configuração, o padrão é valor esperado")
checar(de_config({"criterio_priorizacao": "proporcional_por_grupo"}) == "proporcional_por_grupo",
       "a empresa pode escolher a proporcional")
checar(de_config({"criterio_priorizacao": "inventado"}) == "valor_esperado",
       "critério desconhecido cai no padrão em vez de estourar")
checar(np.array_equal(ordenar(valor, prob, None, "proporcional_por_grupo"),
                      ordenar(valor, prob, None, "valor_esperado")),
       "sem a coluna de grupo, a proporcional não tem o que equalizar e vira a padrão")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
