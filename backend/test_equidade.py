"""Regressão: a análise de equidade separa diferença legítima de injustiça.

    python test_equidade.py

A referência técnica (Volume 7) alerta que um modelo discrimina sem nunca
nomear o atributo protegido, bastando usar um proxy — o exemplo dela é o CEP.
O Mizan usa `uf`, que é da mesma família.

O teste constrói dois mundos em que eu já sei a resposta:

  mundo justo   — uma região paga menos e por isso é priorizada menos;
                  entre quem pagou, a priorização é equilibrada.
  mundo injusto — as duas regiões pagam igual, mas uma é priorizada menos;
                  entre quem pagou, a diferença permanece.

Paridade demográfica acusa os dois. Só a igualdade de oportunidade distingue,
e é isso que o módulo precisa dizer.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from model.equidade import MINIMO_POR_GRUPO, analisar  # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


rng = np.random.default_rng(4)
N = 400   # por região


def mundo(taxa_pag_a, taxa_pag_b, prior_pagante_a, prior_pagante_b):
    """Duas regiões; controla quem paga e quem é priorizado entre os pagantes."""
    uf = np.array(["GO"] * N + ["BA"] * N)
    pagou = np.concatenate([
        rng.random(N) < taxa_pag_a,
        rng.random(N) < taxa_pag_b,
    ])
    sel = np.zeros(2 * N, dtype=bool)
    for ini, taxa in ((0, prior_pagante_a), (N, prior_pagante_b)):
        faixa = slice(ini, ini + N)
        pagantes = np.where(pagou[faixa])[0] + ini
        nao = np.where(~pagou[faixa])[0] + ini
        sel[rng.choice(pagantes, int(len(pagantes) * taxa), replace=False)] = True
        sel[rng.choice(nao, int(len(nao) * 0.10), replace=False)] = True
    return pd.DataFrame({"uf": uf}), sel, pagou


# ── mundo justo: BA paga menos, é priorizada menos, mas seus pagantes não ──
print("— mundo justo (BA paga menos; entre pagantes, tratamento igual) —")
df, sel, pagou = mundo(0.50, 0.20, 0.80, 0.80)
r = analisar(df, "uf", sel, pagou)
checar(r["ok"], "a análise roda")
par = r["paridade_demografica"]
opo = r["igualdade_oportunidade"]
checar(par["razao"] < 0.80, "paridade demográfica acusa diferença",
       f'razão {par["razao"]}')
checar(opo["ok"] and opo["razao"] >= 0.80,
       "mas entre quem pagou o tratamento é equilibrado",
       f'razão {opo["razao"]}')
checar("acompanha diferença real de pagamento" in r["leitura"],
       "e a leitura diz que a diferença é de comportamento, não de tratamento")

# ── mundo injusto: pagam igual, mas BA é priorizada menos ─────────────────
print("\n— mundo injusto (pagam igual; BA priorizada menos) —")
df2, sel2, pagou2 = mundo(0.40, 0.40, 0.85, 0.35)
r2 = analisar(df2, "uf", sel2, pagou2)
par2, opo2 = r2["paridade_demografica"], r2["igualdade_oportunidade"]
checar(par2["razao"] < 0.80, "paridade demográfica acusa", f'razão {par2["razao"]}')
checar(opo2["ok"] and opo2["razao"] < 0.80,
       "e a igualdade de oportunidade TAMBÉM acusa — é isso que distingue",
       f'razão {opo2["razao"]}')
checar("pede revisão" in r2["leitura"],
       "a leitura aponta que não se explica por comportamento")
checar(opo2["menos_favorecido"] == "BA", "e nomeia o grupo prejudicado",
       opo2["menos_favorecido"])

# ── as duas acima do corte: não pode falar de "diferença acima" ───────────
print("\n— sem diferença relevante —")
df_ok = pd.DataFrame({"uf": ["GO"] * N + ["BA"] * N})
pagou_ok = rng.random(2 * N) < 0.40
sel_ok = rng.random(2 * N) < 0.20            # priorização igual nas duas
r_ok = analisar(df_ok, "uf", sel_ok, pagou_ok)
checar(r_ok["paridade_demografica"]["razao"] >= 0.80
       and r_ok["igualdade_oportunidade"]["razao"] >= 0.80,
       "as duas medidas passam do corte",
       f'{r_ok["paridade_demografica"]["razao"]} e {r_ok["igualdade_oportunidade"]["razao"]}')
checar("não há diferença relevante" in r_ok["leitura"],
       "e a leitura diz isso, sem inventar uma diferença para explicar")
checar("a diferença acima" not in r_ok["leitura"],
       "não fala de 'diferença acima' quando não houve diferença")

# ── o caso que a paridade sozinha não pega ────────────────────────────────
print("\n— paridade passa, oportunidade não —")
uf_s = np.array(["GO"] * N + ["BA"] * N)
# BA tem MAIS devedores ruins priorizados e MENOS bons: a fatia total empata
pagou_s = np.concatenate([rng.random(N) < 0.40, rng.random(N) < 0.40])
sel_s = np.zeros(2 * N, dtype=bool)
for ini, t_pag, t_nao in ((0, 0.45, 0.06), (N, 0.12, 0.28)):
    faixa = slice(ini, ini + N)
    pag = np.where(pagou_s[faixa])[0] + ini
    nao = np.where(~pagou_s[faixa])[0] + ini
    sel_s[rng.choice(pag, int(len(pag) * t_pag), replace=False)] = True
    sel_s[rng.choice(nao, int(len(nao) * t_nao), replace=False)] = True
r_s = analisar(pd.DataFrame({"uf": uf_s}), "uf", sel_s, pagou_s)
checar(r_s["paridade_demografica"]["razao"] >= 0.80,
       "a paridade demográfica não acusa nada",
       f'razão {r_s["paridade_demografica"]["razao"]}')
checar(r_s["igualdade_oportunidade"]["razao"] < 0.80,
       "mas a igualdade de oportunidade acusa",
       f'razão {r_s["igualdade_oportunidade"]["razao"]}')
checar("paridade sozinha não pegaria" in r_s["leitura"],
       "e a leitura nomeia exatamente esse caso")

# ── sem desfecho: só paridade, e o módulo diz que não conclui ─────────────
print("\n— sem o desfecho real —")
r3 = analisar(df2, "uf", sel2)
checar(r3["igualdade_oportunidade"] is None, "sem 'pagou', não calcula oportunidade")
checar(any("legítima" in a for a in r3["avisos"]),
       "e avisa que diferença de priorização pode ser legítima")
checar("não prova discriminação" in r3["leitura"],
       "a leitura não conclui discriminação a partir da paridade sozinha")

# ── grupos pequenos viram ruído e ficam fora ──────────────────────────────
print("\n— amostras pequenas —")
df4 = pd.DataFrame({"uf": ["GO"] * 200 + ["BA"] * 200 + ["AC"] * 5})
sel4 = np.concatenate([rng.random(200) < 0.5, rng.random(200) < 0.4, np.ones(5, bool)])
r4 = analisar(df4, "uf", sel4)
checar(r4["paridade_demografica"]["mais_favorecido"] != "AC",
       f"grupo com 5 devedores não vira o mais favorecido (mínimo {MINIMO_POR_GRUPO})",
       r4["paridade_demografica"]["mais_favorecido"])
checar(any("AC" in a for a in r4["avisos"]), "e o aviso nomeia quem ficou de fora")

# ── o que não dá para medir tem de ser dito ───────────────────────────────
print("\n— limites declarados —")
checar(any("não coleta raça" in a for a in r["avisos"]),
       "declara que raça, gênero e idade não são medíveis aqui")
r5 = analisar(df, "renda", sel, pagou)
checar(r5["ok"] is False and "não está na carteira" in r5["motivo"],
       "atributo ausente devolve motivo, não estoura")

# ── uma região só: não há o que comparar ──────────────────────────────────
r6 = analisar(pd.DataFrame({"uf": ["GO"] * 100}), "uf", np.ones(100, bool))
checar(r6["paridade_demografica"]["ok"] is False,
       "com um grupo só, diz que não dá para comparar")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
