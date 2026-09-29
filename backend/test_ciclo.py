"""Regressão: o ciclo de cobrança e o que cada fase custa.

    python test_ciclo.py

A referência técnica (Volume 5, seção 26) descreve quatro fases com economia
diferente. O Mizan tinha faixas de aging que eram só rótulos de tempo: não
sabiam que aos 31 dias entra comissão de terceiro sobre o recuperado, nem que
depois de 360 a alternativa deixa de ser cobrar e passa a ser vender.

Isso muda a fila: o valor esperado bruto superestima o que sobra para o banco,
e é o líquido que deve ordenar.
"""
import os
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

from model import bandit as B                      # noqa: E402
B._salvar_supabase = lambda e, b: None
B._carregar_supabase = lambda e: None
B.salvar_bandit = lambda e, b: None

import main                                        # noqa: E402
from model import ciclo                            # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── as fronteiras da referência ──────────────────────────────────────────
print("— fases —")
for dias, esperado in ((-3, "preventiva"), (0, "administrativa"), (30, "administrativa"),
                       (31, "especializada"), (360, "especializada"), (361, "write_off")):
    checar(ciclo.fase_de(dias) == esperado, f"{dias:>4} dias → {esperado}",
           ciclo.fase_de(dias))
checar(ciclo.fase_de(None) == "administrativa", "dias ausente não estoura")
checar(ciclo.fase_de("abc") == "administrativa", "dias inválido não estoura")
checar(ciclo.FASES["especializada"].tem_comissao
       and not ciclo.FASES["administrativa"].tem_comissao,
       "só a fase terceirizada cobra comissão")

# ── a comissão só entra se for informada ─────────────────────────────────
print("\n— comissão —")
sem = ciclo.custos_de_config({})
com = ciclo.custos_de_config({"comissao_especializada_pct": 20})
checar(sem["comissao_pct"] is None and sem["origem"] == "nao_informado",
       "sem configuração, nenhuma taxa é assumida")
checar(ciclo.liquido(1000, "especializada", sem) == 1000,
       "e o líquido é igual ao bruto — não se inventa custo")
checar(ciclo.aviso(sem) and "BRUTO" in ciclo.aviso(sem),
       "mas o aviso diz que o número está bruto")
checar(ciclo.liquido(1000, "especializada", com) == 800,
       "com 20% informado, desconta a comissão", str(ciclo.liquido(1000, "especializada", com)))
checar(ciclo.liquido(1000, "administrativa", com) == 1000,
       "fase interna do banco não paga comissão")
checar(ciclo.aviso(com) is None, "e o aviso some quando está configurado")
checar(ciclo.custos_de_config({"comissao_especializada_pct": 150})["comissao_pct"] is None,
       "percentual absurdo é recusado em vez de aplicado")
checar(ciclo.custos_de_config({"comissao_especializada_pct": "vinte"})["comissao_pct"] is None,
       "texto no lugar do número não estoura")

# ── a faixa da referência é referência, não regra ────────────────────────
checar(ciclo.COMISSAO_MERCADO == (10.0, 25.0) and ciclo.CESSAO_MERCADO == (2.0, 5.0),
       "as faixas citadas na referência estão registradas")
checar(ciclo.custos_de_config({"comissao_especializada_pct": 8})["comissao_pct"] == 8,
       "mas um contrato fora da faixa é aceito: o do cliente é que manda")

# ── ponta a ponta, e a fila muda ─────────────────────────────────────────
print("\n— na análise da carteira —")
rng = np.random.default_rng(6)
N = 600
df = pd.DataFrame({
    "cpf": [f"{i:011d}" for i in range(N)],
    "valor_divida": rng.lognormal(8.2, 0.9, N).round(2),
    "renda_estimada": rng.lognormal(7.9, 0.6, N).round(2),
    "dias_em_atraso": rng.integers(5, 800, N),
    "produto": rng.choice(["cartao"], N),
    "uf": rng.choice(["GO", "SP"], N),
})


def rodar(extra):
    main.get_db = lambda: types.SimpleNamespace(table=lambda t: types.SimpleNamespace(
        select=lambda *a, **k: types.SimpleNamespace(eq=lambda *a, **k: types.SimpleNamespace(
            limit=lambda *a: types.SimpleNamespace(
                execute=lambda: types.SimpleNamespace(data=[{"extra": extra}]))))))
    return main._analisar_df(df.copy(), "t.csv", _empresa_id="e1")


bruto = rodar({})
liq = rodar({"comissao_especializada_pct": 20, "cessao_pct": 3})

checar(all("fase_cobranca" in d for d in bruto["ranking_completo"]),
       "cada devedor traz a fase do ciclo")
checar(bruto["ranking_completo"][0]["origem_custo_cobranca"] == "nao_informado",
       "e a procedência do custo")
checar("aviso_ciclo" in bruto["resumo"] and "aviso_ciclo" not in liq["resumo"],
       "o aviso de valor bruto aparece só quando falta configurar")


def soma_fase(res, fase):
    return sum(f["valor_esperado_liquido"] for f in res["resumo"]["ciclo_cobranca"]
               if f["fase"] == fase)


esp_bruto, esp_liq = soma_fase(bruto, "especializada"), soma_fase(liq, "especializada")
checar(abs(esp_liq - esp_bruto * 0.8) < 1,
       "a fase especializada perde exatamente os 20% de comissão",
       f"R$ {esp_bruto:,.0f} → R$ {esp_liq:,.0f}")
checar(soma_fase(bruto, "administrativa") == soma_fase(liq, "administrativa"),
       "e a fase interna não muda")

ordem_bruto = [d["cpf"] for d in bruto["ranking_completo"][:50]]
ordem_liq = [d["cpf"] for d in liq["ranking_completo"][:50]]
checar(ordem_bruto != ordem_liq,
       "a fila muda quando o custo entra — é o ponto de descontar a comissão")

# ── cobrar ou vender ─────────────────────────────────────────────────────
wo = liq["resumo"].get("write_off")
checar(wo is not None, "acima de 360 dias, o resumo compara cobrar e vender")
checar(wo and wo["valor_se_vendida"] > 0 and "vale_mais_vender" in wo,
       "com os dois números e a conclusão",
       f'cobrar R$ {wo["esperado_cobrando"]:,.0f} × vender R$ {wo["valor_se_vendida"]:,.0f}')
checar("write_off" not in bruto["resumo"],
       "sem percentual de cessão, não há comparação — não se inventa o preço de venda")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
