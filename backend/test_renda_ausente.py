"""Renda ausente é desconhecida, não zero (D9); e NaN não derruba a análise.

    python test_renda_ausente.py

Antes: sem a coluna de renda, ou com a célula em branco ou zero, a renda virava
0 e a razão dívida ÷ renda virava 0 — o devedor parecia não ter comprometimento
nenhum, o perfil mais favorável. E uma única célula de renda em branco fazia a
análise devolver erro, porque o NaN ia parar no JSON da resposta.
"""
import json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                                     # noqa: E402
from model import score as sc, train as tr                      # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

base = {"valor_divida": [5000.0] * 5, "dias_em_atraso": [120] * 5}
df = pd.DataFrame({**base, "renda_estimada": [None, 0, "", 2500.0, 50000.0]})

print("— variáveis derivadas —")
for mod in (sc, tr):
    d = mod._adicionar_derivadas(df)
    checar(d["comprometimento_renda"][:3].isna().all() and d["log_renda"][:3].isna().all(),
           f"{mod.__name__}: renda vazia, zero ou em branco fica desconhecida (não 0)",
           str(d["comprometimento_renda"].tolist()))
    checar(abs(d["comprometimento_renda"][3] - 2.0) < 1e-9 and abs(d["comprometimento_renda"][4] - 0.1) < 1e-9,
           f"{mod.__name__}: com renda, dívida ÷ renda como antes")

print("\n— pontuação —")
clf, km, meta = sc._carregar_modelos()
X = sc._preprocessar_para_score(df.copy(), meta)
med = meta.get("medians", {})
if "comprometimento_renda" in X.columns and "comprometimento_renda" in med:
    checar(np.allclose(X["comprometimento_renda"][:3], med["comprometimento_renda"]),
           "o modelo recebe a mediana do treino no lugar da renda desconhecida",
           f"{X['comprometimento_renda'][:3].tolist()} vs {med['comprometimento_renda']}")
r = sc.score_carteira(df.copy())
s = r["score_recuperabilidade"].tolist()
checar(s[0] == s[1] == s[2], "vazia, zero e em branco dão o mesmo score", str(s[:3]))
checar(bool(r["dados_incompletos"][0]) and "renda_estimada" in r["aviso_dados"][0],
       "e a linha continua marcada como dado incompleto", r["aviso_dados"][0])

print("\n— a análise com renda em branco responde —")
main.get_db = lambda: (_ for _ in ()).throw(RuntimeError("sem banco"))
main._extra_empresa = lambda e: {}
for nome, entrada in {
    "célula em branco": pd.DataFrame({"cpf": ["1", "2", "3"], "valor_divida": [1000, 2000, 3000],
                                      "dias_em_atraso": [30, 90, 400], "renda_estimada": [3000, None, 5000]}),
    "sem a coluna": pd.DataFrame({"cpf": ["1", "2", "3"], "valor_divida": [1000, 2000, 3000],
                                  "dias_em_atraso": [30, 90, 400]}),
}.items():
    out = main._analisar_df(entrada, "x.csv", _usuario_id="u", _usuario_email="e", _empresa_id="alfa")
    try:
        json.dumps(out, allow_nan=False, default=str)
        ok = True
    except ValueError:
        ok = False
    checar(ok, f"{nome}: a resposta é JSON válido (sem NaN)")
    rendas = [d.get("renda_estimada") for d in out["top10_prioritarios"]]
    checar(None in rendas and 0 not in rendas, f"{nome}: a renda desconhecida vai como vazia, não 0", str(rendas))

checar(main._sem_nan({"a": [float("nan"), np.float64("inf"), 1.5], "b": np.nan}) == {"a": [None, None, 1.5], "b": None},
       "_sem_nan troca NaN e infinito por null em qualquer nível")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
