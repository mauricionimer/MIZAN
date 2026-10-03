"""Treino com os pagamentos registrados no Mizan: por empresa, inativo, sem misturar (D1).

    python test_treino_feedbacks.py

Antes, o agendador retreinava o modelo GERAL com os pagamentos de todas as
empresas juntos e o promovia sozinho. Aqui se confere que:
  - só entram as predições das carteiras da empresa;
  - a versão nasce inativa e o modelo geral não muda;
  - o agendador treina só quem tem pagamentos novos suficientes;
  - a rota antiga do retreino geral está desativada.

O stub impõe os tetos reais do Supabase: mil linhas por resposta e in_ curto.
"""
import hashlib, os, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
TMP = tempfile.mkdtemp(prefix="mizan_fb_")
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

print("— o conjunto de dados de cada empresa —")
ds = tf.datasets(DB)
checar(set(ds) == {"alfa", "beta"}, "uma entrada por empresa, com o id normalizado", str(set(ds)))
df_a, datas_a, precos_a = ds["alfa"]
checar(len(df_a) == 1500, "alfa: um registro por predição com pagamento (1.500, não os 1.650 feedbacks)", len(df_a))
checar(len(ds["beta"][0]) == 20, "beta: só os 20 dela", len(ds["beta"][0]))
pagos_esperados = sum(1 for i in range(1500) if any(f["pagou"] for f in FA if f["predicao_id"] == f"a-p{i:06d}"))
checar(int(df_a["pagou"].sum()) == pagos_esperados, "quem foi marcado pago em algum momento conta como pago",
       f"{int(df_a['pagou'].sum())} vs {pagos_esperados}")
checar(not any(c in df_a.columns for c in ("cpf", "nome", "carteira_id", "id")),
       "nenhum identificador entra no conjunto", list(df_a.columns))
checar(set(tf.datasets(DB, ["ALFA"])) == {"alfa"}, "pedir uma empresa traz só ela")

print("\n— treino manual pelo COMANDO —")
c = TestClient(main.app, raise_server_exceptions=False)
USERS = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": "", "email": "c@c.com"},
         "uo": {"ativo": True, "id": "uo", "role": "operador", "empresa_id": "alfa", "email": "o@o.com"},
         "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa", "email": "a@a.com"}}
main.buscar_usuario_por_id = lambda uid: USERS[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": USERS[u]["email"], "nome": "N",
                                                          "role": USERS[u]["role"], "empresa_id": USERS[u]["empresa_id"]})}
for u in ("uo", "ua"):
    r = c.post("/comando/treino/feedbacks", headers=H(u), json={"empresa_id": "alfa"})
    checar(r.status_code == 403, f"{USERS[u]['role']} não treina", r.status_code)
r = c.post("/admin/retreinar", headers=H("uc"))
checar(r.status_code == 410, "o retreino geral (todas as empresas juntas) está desativado", r.status_code)

# roda o treino no mesmo fio, para o teste esperar o fim
class FioNaHora:
    def __init__(s, target, args=(), daemon=None): s.t, s.a = target, args
    def start(s): s.t(*s.a)
main.threading = type("SoParaOTreino", (), {"Thread": FioNaHora})   # só o main; o sklearn usa o threading de verdade
r = c.post("/comando/treino/feedbacks", headers=H("uc"), json={"empresa_id": "Alfa"})
checar(r.status_code == 202, "COMANDO inicia o treino da alfa", f"{r.status_code} {r.text[:150]}")
j = c.get(f"/comando/treino/{r.json().get('id')}", headers=H("uc")).json()
reg = j.get("registro") or {}
checar(j.get("estado") == "concluido", "o treino termina", f"{j.get('estado')} {j.get('erro', '')}")
checar(reg.get("origem") == "feedbacks" and reg.get("n_amostras") == 1500, "versão registrada com a origem e as 1.500 linhas",
       f"{reg.get('origem')} {reg.get('n_amostras')}")
checar(reg.get("promovido") is False and me.versao_ativa("alfa") is None, "a versão nasce INATIVA")
checar(reg.get("validacao") == "temporal", "validação no tempo, pela data da análise", reg.get("validacao"))
checar("atual" in (reg.get("metricas") or {}), "e o modelo em uso é medido na mesma fatia")
checar(not TRAVAS, "a trava de treino é devolvida")

r = c.post("/comando/treino/feedbacks", headers=H("uc"), json={"empresa_id": "beta"})
j = c.get(f"/comando/treino/{r.json().get('id')}", headers=H("uc")).json()
checar(j.get("estado") == "recusado" and "300" in (j.get("erro") or ""),
       "beta, com 20 pagamentos, é recusada com o motivo", f"{j.get('estado')} {j.get('erro')}")
r = c.post("/comando/treino/feedbacks", headers=H("uc"), json={"empresa_id": "ninguem"})
j = c.get(f"/comando/treino/{r.json().get('id')}", headers=H("uc")).json()
checar(j.get("estado") == "recusado", "empresa sem pagamentos: recusada", j.get("erro"))
TRAVAS.add("treino_modelo_empresa")
r = c.post("/comando/treino/feedbacks", headers=H("uc"), json={"empresa_id": "alfa"})
checar(r.status_code == 409, "com outro treino em andamento: 409", r.status_code)
TRAVAS.clear()

print("\n— o modelo de preço é da empresa (D10) —")
from model import price_model as pm
checar((reg.get("modelo_de_preco") or {}).get("ok") is True, "treina o modelo de preço junto com a versão",
       str(reg.get("modelo_de_preco")))
checar(not any(c in df_a.columns for c in ("valor_recuperado", "score_recuperabilidade")),
       "valor recuperado e score antigo NÃO viram variável do modelo de score")
amostra = PA[:5]
checar(pm.prever(amostra, "alfa") is None, "versão inativa: o modelo de preço ainda não vale")
# um arquivo global antigo, treinado com todas as empresas, não pode mais valer para ninguém
import joblib
joblib.dump({"lixo": True}, Path(TMP) / "model" / "price_model.pkl")
me.ativar("alfa", reg["versao"])
taxas = pm.prever(amostra, "alfa")
checar(taxas is not None and len(taxas) == 5 and all(0 <= t <= 1 for t in taxas), "ativada: a alfa usa o modelo de preço dela",
       str(taxas))
checar(pm.prever(amostra, "beta") is None and pm.prever(amostra, None) is None,
       "beta e quem não tem empresa caem na premissa (o arquivo global não é lido)")
checar((pm.stats("alfa") or {}).get("disponivel") is True and pm.stats("beta") is None, "estatísticas por empresa")
me.desativar("alfa")
checar(pm.prever(amostra, "alfa") is None, "voltar ao modelo geral tira também o modelo de preço")

print("\n— o agendador —")
T["feedbacks"].extend({"id": f"novo{i}", "predicao_id": f"a-p{i:06d}", "pagou": True,
           "created_at": datetime.now(timezone.utc).isoformat()} for i in range(1500, 1540))
antes = len(me.carregar_versoes("alfa")["versoes"])
res = scheduler.verificar_e_retreinar(min_feedbacks=30)
emp = res.get("empresas", {})
checar(emp.get("alfa", {}).get("acao") == "treinou" and emp["alfa"]["novos"] == 40,
       "alfa: 40 pagamentos novos desde o último treino → treina", str(emp.get("alfa")))
checar(emp.get("beta", {}).get("acao") == "aguardando", "beta: abaixo do mínimo → aguarda", str(emp.get("beta")))
checar(len(me.carregar_versoes("alfa")["versoes"]) == antes + 1 and me.versao_ativa("alfa") is None,
       "a versão do agendador também nasce inativa")
checar(hashlib.sha256(GLOBAL.read_bytes()).hexdigest() == hash_global, "o modelo GERAL não muda")
checar(not TRAVAS, "as travas são devolvidas")
res2 = scheduler.verificar_e_retreinar(min_feedbacks=30)
checar(res2["empresas"]["alfa"]["acao"] == "aguardando" and res2["empresas"]["alfa"]["novos"] == 0,
       "sem pagamento novo, não treina de novo", str(res2["empresas"]["alfa"]))
TRAVAS.add("retreino")
checar(scheduler.verificar_e_retreinar(30).get("acao") == "pulado", "outra instância verificando: pula")
TRAVAS.clear()

print("\n— datas do arquivo de treino —")
import pandas as pd
from model.treino_empresa import _ler_datas
lidas = _ler_datas(pd.Series(["2026-01-01", "2026-01-27", "2026-03-05", "05/03/2026"])).dt.strftime("%Y-%m-%d").tolist()
checar(lidas == ["2026-01-01", "2026-01-27", "2026-03-05", "2026-03-05"],
       "ISO e brasileiro na mesma coluna, sem trocar dia e mês", str(lidas))

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
