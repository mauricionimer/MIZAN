"""Regressão: a oferta da carteira sai do motor de propostas, não de limiares.

    python test_oferta_carteira.py

A carteira trazia desconto e prazo de uma escada de limiares de score — acima
de 75 sem desconto, acima de 50 com 15% em 6x, e assim por diante. Aqueles
números não vieram de lugar nenhum. O Excel exportado trazia uma oferta e a
tela do devedor trazia outra, calculada a partir da referência técnica.

Agora as duas usam o mesmo catálogo de arquétipos, escolhido por valor
esperado, e a planilha diz de onde a sugestão veio.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

from model import bandit as B          # noqa: E402
B._salvar_supabase = lambda e, b: None
B._carregar_supabase = lambda e: None

import main                             # noqa: E402
from model.proposta import ARQUETIPOS_PADRAO  # noqa: E402

main.get_db = lambda: (_ for _ in ()).throw(Exception("sem banco no teste"))

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


rng = np.random.default_rng(5)
N = 800
df = pd.DataFrame({
    "cpf": [f"{i:011d}" for i in range(N)],
    "valor_divida": rng.lognormal(8.2, 0.9, N).round(2),
    "renda_estimada": rng.lognormal(7.9, 0.6, N).round(2),
    "dias_em_atraso": rng.integers(15, 900, N),
    "produto": rng.choice(["cartao", "consignado"], N),
    "uf": rng.choice(["GO", "SP"], N),
})

# ── a escada inventada não pode voltar ────────────────────────────────────
fonte = (AQUI / "main.py").read_text()
checar("_calcular_oferta" not in fonte,
       "a função de oferta por limiar de score foi removida")
checar("np.select([_s >= 75, _s >= 50, _s >= 30], [0, 15, 35], default=55)" not in fonte,
       "a escada vetorizada de descontos também saiu")

# ── sem feedback: sugestão uniforme, e a planilha admite ──────────────────
res = main._analisar_df(df.copy(), "t.csv", _empresa_id="empresa_sem_dados")
r = res["ranking_completo"]
rotulos_validos = {a["rotulo"] for a in ARQUETIPOS_PADRAO}
descontos_validos = {a["desconto_pct"] for a in ARQUETIPOS_PADRAO}

checar(all(d["estrategia_oferta"] in rotulos_validos for d in r),
       "toda oferta vem do catálogo compartilhado com a tela do devedor")
checar(all(float(d["desconto_sugerido_pct"]) in descontos_validos for d in r),
       "e os descontos também",
       str(sorted({d["desconto_sugerido_pct"] for d in r})))
checar(r[0]["origem_oferta"] == "sem_evidencia",
       "sem feedback, a procedência diz que não há evidência",
       r[0]["origem_oferta"])
checar("não se diferenciam" in (res["resumo"].get("aviso_oferta") or ""),
       "e o resumo explica por que a sugestão é a mesma para todos")
checar(all(d["desconto_sugerido_pct"] == 0 for d in r),
       "sem evidência de que desconto aumenta pagamento, não se desconta")

# o valor da proposta bate com dívida menos desconto
d0 = r[0]
esperado = round(d0["valor_divida"] * (1 - d0["desconto_sugerido_pct"] / 100), 2)
checar(abs(d0["valor_proposta"] - esperado) < 0.02,
       "valor da proposta é a dívida menos o desconto",
       f'{d0["valor_proposta"]} contra {esperado}')

# ── com feedback: a procedência muda e o aviso troca de texto ─────────────
CTX = [0.5] * B.D
for i in range(40):
    B.registrar_resultado(6, CTX, 0.9 if i < 34 else 0.0, "empresa_com_dados")
for i in range(30):
    B.registrar_resultado(5, CTX, 0.8 if i < 4 else 0.0, "empresa_com_dados")

res2 = main._analisar_df(df.copy(), "t.csv", _empresa_id="empresa_com_dados")
r2 = res2["ranking_completo"]
checar(r2[0]["origem_oferta"] == "bandit",
       "com feedback, a procedência passa a ser o histórico", r2[0]["origem_oferta"])
aviso2 = res2["resumo"].get("aviso_oferta") or ""
checar("vale para a empresa" in aviso2,
       "e o aviso passa a dizer que a oferta é da carteira, não do devedor")
checar(r2[0]["estrategia_oferta"] != r[0]["estrategia_oferta"],
       "o feedback muda a oferta escolhida",
       f'{r[0]["estrategia_oferta"]} -> {r2[0]["estrategia_oferta"]}')

# ── a fila continua por valor esperado ────────────────────────────────────
ve = [d["valor_esperado_recuperacao"] for d in r]
checar(all(ve[i] >= ve[i + 1] for i in range(len(ve) - 1)),
       "a carteira segue ordenada por valor esperado")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
