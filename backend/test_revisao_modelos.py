"""Correções da revisão dos modelos (área 5): análise, sincronização, backtest,
bandit, /testar-db, feedbacks idempotentes, treinos e ajuda.

    python test_revisao_modelos.py
"""
import os, sys, io, tempfile
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.chdir(AQUI)
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402
from fastapi import HTTPException  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1


# ── banco falso que imita o Supabase (filtros, update, delete, range) ──
TAB: dict = {}
FALHAR = {"insert_predicoes": False}
CONTA = {"insert": {}}

class R:
    def __init__(s, d): s.data = d; s.count = None

class Q:
    def __init__(s, t):
        s.t = t; s.f = []; s.rng = None; s.lim = None; s.ins = None; s.patch = None; s.dele = False
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def neq(s, c, v): s.f.append(lambda l: l.get(c) != v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def is_(s, c, v): s.f.append(lambda l: l.get(c) is None); return s
    def gte(s, *a): return s
    def lte(s, *a): return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, j): s.rng = (i, j); return s
    def insert(s, x): s.ins = x; return s
    def update(s, p): s.patch = p; return s
    def upsert(s, x, **k): s.ins = x; return s
    def delete(s): s.dele = True; return s
    def execute(s):
        tab = TAB.setdefault(s.t, [])
        if s.ins is not None:
            CONTA["insert"][s.t] = CONTA["insert"].get(s.t, 0) + 1
            if s.t == "predicoes" and FALHAR["insert_predicoes"]:
                raise Exception("timeout de rede no meio do lote")
            linhas = s.ins if isinstance(s.ins, list) else [s.ins]
            novos = [dict(l, id=l.get("id") or f"{s.t}-{len(tab)+i+1}") for i, l in enumerate(linhas)]
            tab.extend(novos); return R([dict(n) for n in novos])
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        if s.dele:
            for l in alvo: tab.remove(l)
            return R(alvo)
        if s.patch is not None:
            for l in alvo: l.update(s.patch)
            return R(alvo)
        if s.rng: alvo = alvo[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: alvo = alvo[:s.lim]
        return R([dict(l) for l in alvo])

DB = type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.get_db = lambda: DB
main._registrar_auditoria = lambda *a, **k: None


def carteira_df(n=3):
    return pd.DataFrame({"cpf": [f"{i:011d}" for i in range(n)], "nome": [f"Pessoa {i}" for i in range(n)],
                         "valor_divida": [1000.0 + i for i in range(n)],
                         "dias_em_atraso": [60 + i for i in range(n)]})


print("== 1. limite de linhas por análise ==")
os.environ["MIZAN_MAX_LINHAS_ANALISE"] = "5"
try:
    main._analisar_df(carteira_df(6), "grande.csv", _empresa_id="alfa")
    checar(False, "carteira acima do limite é recusada")
except HTTPException as e:
    checar(e.status_code == 413 and "limite por análise é 5" in e.detail,
           "carteira acima do limite: 413 com mensagem clara", e.detail)
os.environ.pop("MIZAN_MAX_LINHAS_ANALISE")
checar(main._max_linhas_analise() == 50_000, "padrão do limite é 50 mil")
os.environ["MIZAN_MAX_LINHAS_ANALISE"] = "lixo"
checar(main._max_linhas_analise() == 50_000, "valor inválido cai no padrão")
os.environ.pop("MIZAN_MAX_LINHAS_ANALISE")

# gravação das predições aceita gerador e não pede a lista inteira
consumidos = []
def gerador(n):
    for i in range(n):
        consumidos.append(i)
        yield {"carteira_id": "c-x", "cpf": f"{i:011d}"}
TAB.clear()
mapa = main._inserir_predicoes_em_lotes(DB, gerador(main.LOTE_INSERCAO * 2 + 7))
checar(len(mapa) == main.LOTE_INSERCAO * 2 + 7, "gerador gravado inteiro, em lotes")

TAB.clear()
r = main._analisar_df(carteira_df(4), "c.csv", _empresa_id="alfa", _incluir_ranking=False)
checar("ranking_completo" not in r and len(r["top10_prioritarios"]) == 4,
       "sem ranking: resposta não leva a fila, só o top 10")
checar(len([p for p in TAB["predicoes"] if p["carteira_id"] == r["resumo"]["carteira_id"]]) == 4,
       "predições gravadas a partir do DataFrame")
r2 = main._analisar_df(carteira_df(4), "c.csv", _empresa_id="alfa")
checar(len(r2.get("ranking_completo", [])) == 4, "padrão continua mandando a fila inteira")


print("\n== 2. sincronização de carteira existente ==")
def cenario_sync():
    TAB.clear()
    TAB["carteiras"] = [{"id": "c-1", "empresa_id": "alfa"}]
    TAB["predicoes"] = [{"id": f"p{i}", "carteira_id": "c-1", "cpf": f"{i:011d}",
                         "responsavel_id": "op-1" if i == 1 else None,
                         "responsavel_nome": "Op Um" if i == 1 else None} for i in range(3)]
    TAB["feedbacks"] = [{"id": "f0", "predicao_id": "p0", "cpf": "00000000000", "pagou": True},
                        {"id": "f9", "predicao_id": "p2", "cpf": "00000000002", "pagou": False}]

cenario_sync()
FALHAR["insert_predicoes"] = True
r = main._analisar_df(carteira_df(2), "nova.csv", _empresa_id="alfa", _carteira_id_existente="c-1")
FALHAR["insert_predicoes"] = False
checar(r["resumo"].get("salvamento_incompleto") is True, "falha no insert avisa salvamento incompleto")
checar(sorted(p["id"] for p in TAB["predicoes"]) == ["p0", "p1", "p2"],
       "falha no insert não apaga as predições antigas")
checar(TAB["feedbacks"][0]["predicao_id"] == "p0", "falha no insert não solta os feedbacks")

cenario_sync()
r = main._analisar_df(carteira_df(2), "nova.csv", _empresa_id="alfa", _carteira_id_existente="c-1")
ids_novos = {p["cpf"]: p["id"] for p in TAB["predicoes"]}
checar(not r["resumo"].get("salvamento_incompleto") and set(ids_novos) == {"00000000000", "00000000001"}
       and not {"p0", "p1", "p2"} & set(ids_novos.values()),
       "sincronização troca as predições (antigas apagadas depois)")
fb = {f["id"]: f for f in TAB["feedbacks"]}
checar(fb["f0"]["predicao_id"] == ids_novos["00000000000"], "feedback religado à predição nova pelo CPF")
checar(fb["f9"]["predicao_id"] is None, "feedback de CPF que saiu fica sem predição")
dono = [p for p in TAB["predicoes"] if p["cpf"] == "00000000001"][0]
checar(dono.get("responsavel_id") == "op-1", "responsável preservado na sincronização")


print("\n== 3. backtest sem colunas do período e sem conclusão com KS suspeito ==")
import backtest  # noqa: E402
rng = np.random.default_rng(1); n = 2000
pagou = rng.random(n) < 0.3
base_bt = pd.DataFrame({"cpf": [f"{i:011d}" for i in range(n)], "valor_divida": rng.uniform(500, 20000, n).round(2),
                        "dias_em_atraso": rng.integers(30, 720, n), "renda_estimada": rng.uniform(1000, 8000, n).round(0),
                        "uf": rng.choice(["SP", "GO", "BA", "RS"], n), "pagou": pagou.astype(int)})
d2 = base_bt.copy()
d2["tentativas_contato"] = np.where(pagou, 1, 8); d2["promessa_quebrada"] = np.where(pagou, 0, 1)
r0 = backtest.rodar(base_bt.copy()); r1 = backtest.rodar(d2.copy())
checar(abs(r1["separacao"]["ks"] - r0["separacao"]["ks"]) < 1,
       "tentativas/promessa do período não inflam o KS", f'{r0["separacao"]["ks"]} x {r1["separacao"]["ks"]}')
checar({"tentativas_contato", "promessa_quebrada"} <= set(r1["colunas_ignoradas"])
       and any("durante a própria cobrança" in a for a in r1["avisos"]), "colunas do período saem com aviso")
d3 = base_bt.copy(); d3["nota_interna"] = np.where(pagou, 900, 100) + rng.integers(0, 50, n)
r3 = backtest.rodar(d3)
checar("nota_interna" in r3["colunas_ignoradas"] and any("separam sozinhas" in a for a in r3["avisos"]),
       "coluna de nome inocente que separa sozinha sai (mesmo critério do treino)")
# mantidas de propósito e sem o detector (simula vazamento que escapou dos dois)
_det = backtest.suspeitas_de_vazamento
backtest.suspeitas_de_vazamento = lambda df: []
rk = backtest.rodar(d2.copy(), manter_colunas_do_periodo=True)
backtest.suspeitas_de_vazamento = _det
checar(rk["separacao"]["ks_leitura"] == "suspeito" and rk["conclusao_valida"] is False,
       "KS suspeito marca conclusão inválida", str(rk["separacao"]["ks"]))
txt = backtest.relatorio(rk)
checar("recuperou mais" not in txt and "Sem conclusão" in txt, "relatório não conclui 'recuperou mais' com KS suspeito")
checar(r0["conclusao_valida"] is True, "carteira limpa mantém a conclusão")


print(f"\n{falhas} falha(s)")
sys.exit(falhas)
