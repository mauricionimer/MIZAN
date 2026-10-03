"""O diagnóstico mede o modelo EM USO pela empresa, sem treinar nada (D6).

    python test_diagnostico_ativo.py

Antes, /admin/modelo/qualidade treinava um modelo novo com os pagamentos de
todas as empresas e media esse modelo, não o que decide. Aqui se confere que a
medida é a do modelo ativo da empresa, nos pagamentos dela, e que pagamentos
que o modelo já viu no treino ficam de fora.
"""
import hashlib, os, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
TMP = tempfile.mkdtemp(prefix="mizan_dg_")
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_DATA_DIR=TMP)
(Path(TMP) / "model").mkdir(parents=True)
for n in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl"):
    shutil.copy(AQUI / "model" / n, Path(TMP) / "model" / n)

import main                                           # noqa: E402
import scheduler                                      # noqa: E402
import travas                                         # noqa: E402
from auth import criar_token                          # noqa: E402
from fastapi.testclient import TestClient             # noqa: E402
from model import modelos_empresa as me, treino_feedbacks as tf   # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

TETO, IN_MAX = 1000, 400
rng = np.random.default_rng(11)

def gerar(empresa, prefixo, n, n_cart, com_fb):
    carts = [{"id": f"{prefixo}-c{i}", "empresa_id": empresa} for i in range(n_cart)]
    preds, fbs = [], []
    for i in range(n):
        dias = int(rng.integers(10, 900)); valor = float(rng.lognormal(8, 0.8)); renda = float(rng.lognormal(7.9, 0.5))
        p = 1 / (1 + np.exp(-(-0.004 * dias + 0.0004 * renda + 0.8)))
        pid = f"{prefixo}-p{i:06d}"
        preds.append({"id": pid, "carteira_id": carts[i % n_cart]["id"], "cpf": f"{prefixo}{i:09d}",
                      "produto": ["cartao", "consignado", "pessoal"][i % 3], "uf": "GO", "status": "ativo",
                      "valor_divida": round(valor, 2), "dias_em_atraso": dias, "renda_estimada": round(renda, 2),
                      "score_recuperabilidade": 50.0,
                      "created_at": f"2026-{1 + i % 9:02d}-{1 + i % 27:02d}T10:00:00+00:00"})
        if i < com_fb:
            pagou = bool(rng.random() < p)
            fbs.append({"id": f"{prefixo}-f{i:06d}a", "predicao_id": pid, "pagou": pagou,
                        "valor_recuperado": round(valor * 0.6, 2) if pagou else 0.0,
                        "created_at": "2026-09-01T10:00:00+00:00"})
            if i % 10 == 0:   # um segundo registro: quem não pagou e depois pagou conta como pago
                fbs.append({"id": f"{prefixo}-f{i:06d}b", "predicao_id": pid, "pagou": True,
                            "created_at": "2026-09-05T10:00:00+00:00"})
    return carts, preds, fbs

CA, PA, FA = gerar("Alfa", "a", 1600, 3, 1500)      # empresa_id com maiúscula, como pode vir do cadastro
CB, PB, FB = gerar("beta", "b", 600, 2, 20)         # poucos pagamentos: não treina
FB.append({"id": "orfao", "predicao_id": None, "pagou": True, "created_at": "2026-09-01"})
T = {"carteiras": CA + CB, "predicoes": PA + PB, "feedbacks": FA + FB}

class Q:
    def __init__(s, t): s.t, s.l, s.rng = t, list(T.get(t, [])), None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.l = [x for x in s.l if x.get(c) == v]; return s
    def in_(s, c, vs):
        vs = list(vs)
        if len(vs) > IN_MAX: raise RuntimeError(f"in_ com {len(vs)} itens")
        vs = set(vs); s.l = [x for x in s.l if x.get(c) in vs]; return s
    @property
    def not_(s):
        q = s
        class N:
            def is_(_, c, __): q.l = [x for x in q.l if x.get(c) is not None]; return q
        return N()
    def order(s, c, desc=False): s.l = sorted(s.l, key=lambda x: str(x.get(c)), reverse=desc); return s
    def range(s, i, f): s.rng = (i, f); return s
    def execute(s):
        d = s.l[s.rng[0]:s.rng[1] + 1] if s.rng else s.l
        return type("R", (), {"data": d[:TETO]})()
DB = type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main.get_db = lambda: DB
import db as _db; _db.get_db = lambda: DB

TRAVAS = set()
def _adq(nome, duracao_min=30):
    if nome in TRAVAS: return False
    TRAVAS.add(nome); return True
travas.adquirir, travas.liberar = _adq, lambda nome: TRAVAS.discard(nome)
main._registrar_auditoria = lambda *a, **k: None

GLOBAL = Path(TMP) / "model" / "mizan_model.pkl"
hash_global = hashlib.sha256(GLOBAL.read_bytes()).hexdigest()


from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from model import diagnostico as dg
from model.score import score_carteira
from fastapi.testclient import TestClient

print("— modelo geral, pagamentos da alfa —")
_fit = HistGradientBoostingClassifier.fit
TREINOS = []
HistGradientBoostingClassifier.fit = lambda self, *a, **k: (TREINOS.append(1), _fit(self, *a, **k))[1]
r = dg.avaliar_modelo_ativo(DB, "Alfa")
HistGradientBoostingClassifier.fit = _fit
checar(r["ok"] and r["modelo"]["origem"] == "geral" and r["base"] == "todos" and r["n_amostras"] == 1500,
       "mede o modelo geral nos 1.500 devedores da alfa", f"{r.get('modelo')} {r.get('n_amostras')}")
checar(not TREINOS, "e não treina modelo nenhum para medir", f"{len(TREINOS)} ajustes")
df_a, _, _ = tf.datasets(DB, ["alfa"])["alfa"]
p = score_carteira(df_a.drop(columns=["pagou", "data_referencia"]), "alfa")["score_recuperabilidade"].to_numpy() / 100
checar(abs(r["medicao"]["auc_roc"] - round(roc_auc_score(df_a["pagou"], p), 4)) < 1e-9,
       "o AUC é o do score que o modelo ativo dá a esses devedores", str(r["medicao"]["auc_roc"]))
mc = r["medicao"]["matriz_confusao"]
checar(sum(mc.values()) == 1500, "a matriz de confusão cobre todos os medidos")
checar(r["separacao"]["ok"] and len(r["calibracao_por_faixa"]) == 5, "KS/Gini e calibração por faixa")
checar(hashlib.sha256(GLOBAL.read_bytes()).hexdigest() == hash_global, "o modelo geral continua intacto")

r = dg.avaliar_modelo_ativo(DB, "beta")
checar(not r["ok"] and "20" in r["motivo"], "beta, com 20 pagamentos, não tem dado para medir", r["motivo"])

print("\n— modelo próprio treinado com os pagamentos: só vale o que ele não viu —")
reg = tf.treinar_empresa(DB, "alfa", "teste")
me.ativar("alfa", reg["versao"])
r = dg.avaliar_modelo_ativo(DB, "alfa")
checar(not r["ok"] and r["modelo"]["origem"] == "proprio" and r["base"] == "depois_do_treino" and r["n_amostras"] == 0,
       "logo depois do treino não há pagamento inédito: não mede com os que ele já viu", r.get("motivo"))
T["feedbacks"].extend({"id": f"dg{i}", "predicao_id": f"a-p{i:06d}", "pagou": i % 2 == 0, "valor_recuperado": 0.0,
                       "created_at": datetime.now(timezone.utc).isoformat()} for i in range(1500, 1580))
r = dg.avaliar_modelo_ativo(DB, "alfa")
checar(r["ok"] and r["n_amostras"] == 80 and r["modelo"]["versao"] == reg["versao"],
       "com 80 pagamentos novos, mede o modelo próprio só neles", f"{r.get('n_amostras')} {r.get('motivo', '')}")
cmp_ = r.get("comparacao_com_o_treino") or {}
checar(cmp_.get("auc_no_treino") == reg["metricas"]["novo"]["auc"] and cmp_.get("auc_agora") == r["medicao"]["auc_roc"],
       "e compara com o AUC do teste feito no treino", str(cmp_))
checar(r["dados_do_treino"]["n_treino"] == reg["n_amostras"] and r["dados_do_treino"]["n_variaveis"],
       "volume do treino do modelo em uso por variável", str(r["dados_do_treino"]))

print("\n— a rota —")
c = TestClient(main.app, raise_server_exceptions=False)
U = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": "", "email": "c@c"},
     "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa", "email": "a@a"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": U[u]["email"], "nome": "N",
                                                          "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}
checar(c.get("/admin/modelo/qualidade", headers=H("ua")).status_code == 403, "admin de empresa não vê")
j = c.get("/admin/modelo/qualidade", headers=H("uc")).json()
checar(j.get("ok") is False and "empresa" in j.get("motivo", ""), "sem empresa: pede para escolher", j.get("motivo"))
j = c.get("/admin/modelo/qualidade", headers=H("uc"), params={"empresa_id": "alfa"}).json()
checar(j.get("ok") is True and j["modelo"]["origem"] == "proprio" and "procedencia" in j, "com empresa: mede o modelo dela")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
