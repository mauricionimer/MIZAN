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
TMP = tempfile.mkdtemp(prefix="mizan_revmod_")
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_DATA_DIR=TMP)
# modelos globais copiados para a pasta de teste: o treino por empresa grava lá, não no repositório
import shutil  # noqa: E402
(Path(TMP) / "model").mkdir(parents=True)
for _n in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl", "versions.json"):
    if (AQUI / "model" / _n).exists():
        shutil.copy(AQUI / "model" / _n, Path(TMP) / "model" / _n)
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
        s.ordem = []
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def neq(s, c, v): s.f.append(lambda l: l.get(c) != v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def is_(s, c, v): s.f.append(lambda l: l.get(c) is None); return s
    def gte(s, *a): return s
    def lte(s, *a): return s
    def order(s, col, desc=False): s.ordem.append((col, desc)); return s
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
        for col, desc in reversed(s.ordem):
            alvo = sorted(alvo, key=lambda l: str(l.get(col) or ""), reverse=desc)
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


print("\n== 4. bandit: taxa por oferta, estado antigo, lock por empresa, versão ==")
import threading, joblib  # noqa: E402
from model import bandit as B  # noqa: E402
_tmp_bandit = Path(tempfile.mkdtemp())
B._arquivo_bandit = lambda emp: _tmp_bandit / f"bandit_{B._chave(emp)}.pkl"
_tabela_b: dict = {}
def _carregar_b(emp):
    emp = B._chave(emp)
    if emp not in _tabela_b:
        return None, 0
    estado, versao = _tabela_b[emp]
    return B._bandit_de_json(estado), versao
def _gravar_b(emp, bandit, versao):
    emp = B._chave(emp)
    atual = _tabela_b.get(emp)
    if atual is not None and atual[1] != versao:
        return False
    _tabela_b[emp] = (B._bandit_para_json(bandit), versao + 1)
    return True
B._carregar_com_versao = _carregar_b
B._gravar_se_versao = _gravar_b
B._carregar_supabase = lambda emp: _carregar_b(emp)[0]
B._salvar_supabase = lambda emp, b: _gravar_b(emp, b, _tabela_b.get(B._chave(emp), (None, 0))[1])

CTX = [0.5] * B.D
EMP = "emp_pop"
id_12x = B.acao_id_de("whatsapp", "parcelado_12x")
for i in range(10):
    cpf = f"{i:011d}"
    for _ in range(2):        # dois contatos (sem devedor: como a rota /contatos chama)
        B.registrar_resultado(id_12x, CTX, 0.05, EMP, pagou=False)
    B.registrar_resultado(id_12x, CTX, 1.0, EMP, pagou=True, devedor=cpf)
B.registrar_resultado(id_12x, CTX, 1.0, EMP, pagou=True, devedor="00000000000")  # repetido
pop = B.pop_por_oferta(EMP, 0.3)["parcelado_12x"]
checar(pop["n_tentativas"] == 10 and pop["taxa_observada"] == 1.0,
       "10 devedores, 2 contatos cada, todos pagaram → taxa 100% (denominador por devedor × oferta)", str(pop))
checar(sum(B.carregar_bandit(EMP).n_tentativas) == 31, "contatos continuam atualizando o LinUCB")
estado = _tabela_b[EMP][0]
checar("00000000000" not in str(estado), "o estado guarda código do devedor, não o CPF")

# estado antigo (sem os campos novos), em JSON e em .pkl
antigo = {k: v for k, v in B._bandit_para_json(B.LinUCB()).items()
          if k not in ("ofertas_apresentadas", "ofertas_pagas", "n_pagamentos")}
antigo["n_tentativas"][id_12x] = 4
b_ant = B._bandit_de_json(antigo)
checar(b_ant.ofertas_apresentadas == {} and b_ant.n_tentativas[id_12x] == 4, "estado antigo em JSON carrega")
b_pkl = B.LinUCB(); del b_pkl.__dict__["ofertas_apresentadas"]; del b_pkl.__dict__["ofertas_pagas"]
joblib.dump(b_pkl, _tmp_bandit / "velho.pkl")
b_pkl2 = joblib.load(_tmp_bandit / "velho.pkl")
checar(b_pkl2.ofertas_pagas == {} and B._bandit_para_json(b_pkl2)["ofertas_apresentadas"] == {},
       "estado antigo em .pkl carrega e completa os campos")
_tabela_b["emp_antiga"] = (antigo, 3)
pop_ant = B.pop_por_oferta("emp_antiga", 0.3)["parcelado_12x"]
checar(pop_ant["n_tentativas"] == 4, "sem contagem nova, a oferta usa os contadores antigos")

# lock por empresa e banco fora do lock
checar(B._lock_de("a") is not B._lock_de("b") and B._lock_de("a") is B._lock_de("a"), "um lock por empresa")
livre = []
def _gravar_espiando(emp, bandit, versao):
    t = threading.Thread(target=lambda: livre.append(B._lock_de(emp).acquire(timeout=1)
                                                     and (B._lock_de(emp).release() or True)))
    t.start(); t.join()
    return _gravar_b(emp, bandit, versao)
B._gravar_se_versao = _gravar_espiando
B.registrar_resultado(id_12x, CTX, 0.5, EMP, pagou=False)
B._gravar_se_versao = _gravar_b
checar(livre == [True], "gravação no banco acontece fora do lock da empresa")

# zerar e ajustar_alpha sobem a versão: feedback lido antes não grava por cima
lido, v_lido = _carregar_b(EMP)
B.ajustar_alpha(2.0, EMP)
checar(_tabela_b[EMP][1] == v_lido + 1 and _tabela_b[EMP][0]["alpha"] == 2.0, "ajustar_alpha sobe a versão")
checar(_gravar_b(EMP, lido, v_lido) is False, "feedback com versão velha não apaga o alpha novo")
lido, v_lido = _carregar_b(EMP)
B.zerar(EMP)
checar(_tabela_b[EMP][1] == v_lido + 1 and sum(_tabela_b[EMP][0]["n_tentativas"]) == 0
       and _tabela_b[EMP][0]["alpha"] == 2.0, "zerar sobe a versão e mantém o alpha")
checar(_gravar_b(EMP, lido, v_lido) is False, "feedback com versão velha não desfaz o zerar")


print("\n== 5. /testar-db: prévia de reserva lê só 5 linhas ==")
import sqlite3  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
lidas = {"n": 0}
def _conta(x):
    lidas["n"] += 1
    return x
eng = create_engine("sqlite://")
with eng.connect() as cx:
    cx.connection.create_function("conta", 1, _conta)
    cx.execute(text("create table t (id integer, nome text)"))
    cx.execute(text("insert into t values " + ",".join(f"({i}, 'n{i}')" for i in range(5000))))
    dfp = main._previa_sem_subconsulta_sqlalchemy(cx, text("select conta(id) as id, nome from t"), RuntimeError("x"))
    checar(len(dfp) == 5 and list(dfp.columns) == ["id", "nome"], "reserva SQLAlchemy devolve 5 linhas com as colunas")
    checar(lidas["n"] < 100, "reserva SQLAlchemy não lê a tabela inteira", f'{lidas["n"]} linhas avaliadas de 5000')
    try:
        main._previa_sem_subconsulta_sqlalchemy(cx, text("select * from nao_existe"), RuntimeError("erro da prévia"))
        checar(False, "reserva que falha devolve o erro da prévia")
    except RuntimeError as e:
        checar(str(e) == "erro da prévia", "reserva que falha devolve o erro da prévia")
lidas["n"] = 0
raw = sqlite3.connect(":memory:")
raw.create_function("conta", 1, _conta)
raw.execute("create table t (id integer)")
raw.executemany("insert into t values (?)", [(i,) for i in range(5000)])
dfp = main._previa_sem_subconsulta_dbapi(raw, "select conta(id) as id from t", RuntimeError("x"))
checar(len(dfp) == 5 and lidas["n"] < 100, "reserva DB-API (SQL Server) lê só o começo", f'{lidas["n"]} avaliadas')


print("\n== 6. webhook e /feedback/lote idempotentes ==")
from fastapi.testclient import TestClient  # noqa: E402
from auth import criar_token  # noqa: E402
LACO = []
_fechar_orig = main._fechar_loop_bandit
main._fechar_loop_bandit = lambda db, cpf, pagou, val, pred, emp: LACO.append((cpf, emp, (pred or {}).get("id")))
main._cumprir_promessas = lambda *a, **k: None
main._cache_del_prefix = lambda *a, **k: None
main._buscar_api_key = lambda db, tok: {"id": "k1", "empresa_id": "alfa"} if tok == "chave-alfa" else None
main._marcar_uso_api_key = lambda *a, **k: None
main.buscar_usuario_por_id = lambda uid: {"id": uid, "ativo": True}
cli = TestClient(main.app, raise_server_exceptions=False)

def base_feedback():
    TAB.clear(); LACO.clear(); CONTA["insert"].clear()
    TAB["carteiras"] = [{"id": "c-a", "empresa_id": "alfa"}, {"id": "c-b", "empresa_id": "beta"}]
    TAB["predicoes"] = [
        {"id": "pa1", "carteira_id": "c-a", "cpf": "11111111111", "created_at": "2026-10-01"},
        {"id": "pa2", "carteira_id": "c-a", "cpf": "11111111111", "created_at": "2026-10-10"},
        {"id": "pb1", "carteira_id": "c-b", "cpf": "22222222222", "created_at": "2026-10-11"},
    ]
    TAB["feedbacks"] = []

base_feedback()
corpo = {"cpf": "11111111111", "pagou": True, "valor_recuperado": 300, "data_pagamento": "2026-10-15"}
r1 = cli.post("/webhook/pagamento", headers={"X-API-Key": "chave-alfa"}, json=corpo)
r2 = cli.post("/webhook/pagamento", headers={"X-API-Key": "chave-alfa"}, json=corpo)
checar(r1.status_code == 200 and r2.status_code == 200 and r2.json().get("repetido") is True
       and r2.json()["feedback_id"] == r1.json()["feedback_id"], "webhook repetido devolve o mesmo feedback", r2.text[:120])
checar(len(TAB["feedbacks"]) == 1 and len(LACO) == 1, "webhook repetido não grava nem fecha o laço de novo",
       f'{len(TAB["feedbacks"])} feedbacks, {len(LACO)} laços')
checar(TAB["feedbacks"][0].get("predicao_id") == "pa2", "webhook liga à predição mais recente da empresa")
r3 = cli.post("/webhook/pagamento", headers={"X-API-Key": "chave-alfa"},
              json={**corpo, "data_pagamento": "2026-11-15"})
checar(r3.json().get("repetido") is None and len(TAB["feedbacks"]) == 2, "parcela de outra data é gravada")
r4 = cli.post("/webhook/pagamento", headers={"X-API-Key": "chave-alfa"},
              json={"cpf": "11111111111", "pagou": True, "valor_recuperado": 50})
r5 = cli.post("/webhook/pagamento", headers={"X-API-Key": "chave-alfa"},
              json={"cpf": "11111111111", "pagou": True, "valor_recuperado": 50})
checar(TAB["feedbacks"][-1].get("data_pagamento") and r5.json().get("repetido") is True,
       "sem data: vale a de hoje e o reenvio é reconhecido")

def jwt_admin(emp="alfa"):
    return {"Authorization": "Bearer " + criar_token({"sub": "u1", "email": "u1@x", "nome": "U1",
                                                      "role": "admin", "empresa_id": emp})}
def enviar_lote(linhas):
    csv = "cpf,pagou,valor_recuperado,data_pagamento\n" + "\n".join(linhas)
    return cli.post("/feedback/lote", headers=jwt_admin(),
                    files={"file": ("f.csv", io.BytesIO(csv.encode()), "text/csv")})

base_feedback()
consultas_pred = {"n": 0}
_pred_um = main._predicao_do_cpf
main._predicao_do_cpf = lambda *a, **k: (consultas_pred.__setitem__("n", consultas_pred["n"] + 1), _pred_um(*a, **k))[1]
_ids_orig = main._ids_carteiras
chamadas_ids = {"n": 0}
main._ids_carteiras = lambda db, e: (chamadas_ids.__setitem__("n", chamadas_ids["n"] + 1), _ids_orig(db, e))[1]
linhas = ["11111111111,sim,300,2026-10-15", "11111111111,sim,300,2026-10-15",
          "22222222222,sim,100,2026-10-15", "33333333333,nao,0,2026-10-15"]
r = enviar_lote(linhas)
j = r.json()
checar(r.status_code == 200 and j["importados"] == 3 and j["repetidos"] == 1, "linha repetida no arquivo é pulada", r.text[:160])
checar(len(LACO) == 3, "laço do bandit só nos inserts novos", str(len(LACO)))
fb = {f["cpf"]: f for f in TAB["feedbacks"]}
checar(fb["11111111111"].get("predicao_id") == "pa2" and "predicao_id" not in fb["22222222222"],
       "predições em lote: mais recente da empresa, nunca de outra")
checar(consultas_pred["n"] == 0 and chamadas_ids["n"] == 1,
       "carteiras lidas uma vez e nenhuma consulta de predição por linha",
       f'{chamadas_ids["n"]} leituras de carteiras, {consultas_pred["n"]} por linha')
LACO.clear()
r = enviar_lote(linhas)
checar(r.json()["importados"] == 0 and r.json()["repetidos"] == 4 and not LACO and len(TAB["feedbacks"]) == 3,
       "reimportar o mesmo arquivo não duplica nem ensina o bandit de novo", r.text[:120])
main._predicao_do_cpf = _pred_um
main._ids_carteiras = _ids_orig

os.environ["MIZAN_MAX_LINHAS_FEEDBACK_LOTE"] = "2"
r = enviar_lote(linhas)
os.environ.pop("MIZAN_MAX_LINHAS_FEEDBACK_LOTE")
checar(r.status_code == 413 and "limite por importação é 2" in r.json().get("detail", ""),
       "lote acima do limite: 413 com mensagem clara", r.text[:120])
main._fechar_loop_bandit = _fechar_orig


print("\n== 7. treino da empresa: modelo atual medido em amostra não bloqueia ==")
from model import modelos_empresa as me, treino_empresa as te  # noqa: E402
rng7 = np.random.default_rng(7); N7 = 2000
dias7 = rng7.integers(10, 900, N7); valor7 = rng7.lognormal(8.0, 0.8, N7).round(2)
renda7 = rng7.lognormal(7.9, 0.5, N7).round(2)
pagou7 = (rng7.random(N7) < 1 / (1 + np.exp(-(-0.004 * dias7 + 0.0004 * renda7 + 0.8)))).astype(int)
df7 = pd.DataFrame({"cpf": [f"{(i * 7919) % 10**11:011d}" for i in range(N7)], "valor_divida": valor7,
                    "renda_estimada": renda7, "dias_em_atraso": dias7,
                    "produto": rng7.choice(["cartao", "consignado"], N7), "uf": rng7.choice(["GO", "DF"], N7),
                    "pagou": np.where(pagou7 == 1, "sim", "não"),
                    "data_referencia": pd.date_range("2024-01-01", periods=N7, freq="6h").strftime("%d/%m/%Y")})
raw7 = df7.to_csv(index=False).encode()
reg1 = te.treinar(raw7, "h.csv", "emp-amostra", "")
me.ativar("emp-amostra", reg1["versao"])
reg2 = te.treinar(raw7, "h.csv", "emp-amostra", "")
at = reg2["metricas"]["atual"]
checar(at.get("em_amostra") is True and at.get("auc") is None and "metricas_em_amostra" in at,
       "mesmo arquivo do modelo ativo: medida do atual marcada 'em amostra' e fora da comparação",
       at.get("indisponivel", ""))
cli7 = TestClient(main.app, raise_server_exceptions=False)
h7 = {"Authorization": "Bearer " + criar_token({"sub": "cmd", "email": "cmd@x", "nome": "Cmd",
                                                 "role": "comando", "empresa_id": ""})}
main._exigir_comando = lambda cred: {"role": "comando", "email": "cmd@x", "sub": "cmd"}
r7 = cli7.post("/comando/modelos/ativar", headers=h7, json={"empresa_id": "emp-amostra", "versao": reg2["versao"]})
checar(r7.status_code == 200, "ativação não é bloqueada pela medida em amostra", f"{r7.status_code} {r7.text[:120]}")
reg3 = te.treinar(raw7, "h.csv", "emp-limpa", "")
checar(reg3["metricas"]["atual"].get("origem") == "global" and not reg3["metricas"]["atual"].get("em_amostra"),
       "sem modelo próprio, o atual (geral) continua comparado normalmente")


print("\n== 8. treino com feedbacks lê só a empresa pedida ==")
from model import treino_feedbacks as tf  # noqa: E402
TAB.clear()
TAB["carteiras"] = [{"id": "ca", "empresa_id": "Alfa"}, {"id": "cb", "empresa_id": "beta"}]
TAB["predicoes"] = ([{"id": f"pa{i}", "carteira_id": "ca", "valor_divida": 1000, "dias_em_atraso": 30 + i,
                      "created_at": "2026-09-01"} for i in range(30)]
                    + [{"id": f"pb{i}", "carteira_id": "cb", "valor_divida": 900, "dias_em_atraso": 40,
                        "created_at": "2026-09-01"} for i in range(50)])
TAB["feedbacks"] = ([{"id": f"fa{i}", "predicao_id": f"pa{i}", "pagou": i % 2 == 0, "created_at": "2026-09-10"}
                     for i in range(30)]
                    + [{"id": f"fb{i}", "predicao_id": f"pb{i}", "pagou": True, "created_at": "2026-09-10"}
                       for i in range(50)])
lidos_fb = []
_exec_orig = Q.execute
def _exec_espia(q):
    r = _exec_orig(q)
    if q.t == "feedbacks" and q.ins is None and q.patch is None and not q.dele:
        lidos_fb.extend(x["id"] for x in r.data)
    return r
Q.execute = _exec_espia
ds = tf.datasets(DB, ["alfa"])
Q.execute = _exec_orig
checar(set(ds) == {"alfa"} and len(ds["alfa"][0]) == 30, "dataset da alfa com os 30 pagamentos dela")
checar(lidos_fb and not any(i.startswith("fb") for i in lidos_fb),
       "nenhum feedback de outra empresa é lido", f"{len(lidos_fb)} lidos")


print("\n== 9. ajuda com cache do catálogo ==")
import ajuda  # noqa: E402
lidos_md = []
_interp = ajuda._interpretar
ajuda._interpretar = lambda arq: (lidos_md.append(arq.name), _interp(arq))[1]
ajuda._CACHE_CATALOGO.clear()
c1 = ajuda.carregar(); n1 = len(lidos_md)
c2 = ajuda.carregar()
checar(n1 > 0 and len(lidos_md) == n1 and [e.id for e in c1] == [e.id for e in c2],
       "segunda leitura vem do cache (nenhum .md reinterpretado)", f"{n1} arquivos na primeira")
pasta_tmp = Path(tempfile.mkdtemp())
amostra = sorted(p_ for p_ in ajuda.PASTA.glob("*.md") if not p_.name.startswith("_"))[0]
destino = pasta_tmp / amostra.name
destino.write_text(amostra.read_text(encoding="utf-8"), encoding="utf-8")
a1 = ajuda.carregar(pasta_tmp)
lidos_md.clear()
destino.write_text(amostra.read_text(encoding="utf-8") + "\n", encoding="utf-8")
a2 = ajuda.carregar(pasta_tmp)
checar(lidos_md == [amostra.name] and len(a1) == len(a2), "arquivo alterado é relido sem reiniciar")
a2.clear()
checar(len(ajuda.carregar(pasta_tmp)) == len(a1), "quem altera a lista devolvida não estraga o cache")
ajuda._interpretar = _interp


print(f"\n{falhas} falha(s)")
sys.exit(falhas)
