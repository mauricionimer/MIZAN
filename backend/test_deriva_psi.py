"""A deriva é o PSI da população recente de UMA empresa (D4).

    python test_deriva_psi.py

Antes, /admin/drift comparava a média de score dos últimos 30 dias com a do
histórico inteiro (que incluía os próprios 30 dias), juntando todas as
empresas, com limite fixo de 10 pontos, e mandava e-mail a cada abertura.
"""
import os, sys
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import numpy as np                                    # noqa: E402
import main                                           # noqa: E402
from auth import criar_token                          # noqa: E402
from fastapi.testclient import TestClient             # noqa: E402
from model.psi import construir_referencia, calcular  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

rng = np.random.default_rng(3)
REF = construir_referencia(list(rng.uniform(0, 100, 5000)))
agora, velho = datetime.utcnow().isoformat(), (datetime.utcnow() - timedelta(days=90)).isoformat()
# alfa: recente desloca para baixo (deriva); beta: recente igual ao treino
PRED = ([{"id": f"a{i}", "carteira_id": "ca", "score_recuperabilidade": float(rng.uniform(0, 40)), "created_at": agora} for i in range(1500)]
        + [{"id": f"av{i}", "carteira_id": "ca", "score_recuperabilidade": float(rng.uniform(60, 100)), "created_at": velho} for i in range(1500)]
        + [{"id": f"b{i}", "carteira_id": "cb", "score_recuperabilidade": float(rng.uniform(0, 100)), "created_at": agora} for i in range(800)])
TAB = {"carteiras": [{"id": "ca", "empresa_id": "alfa"}, {"id": "cb", "empresa_id": "beta"}], "predicoes": PRED}

class Q:
    def __init__(s, t): s.l, s.rng = list(TAB.get(t, [])), None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.l = [x for x in s.l if x.get(c) == v]; return s
    def gte(s, c, v): s.l = [x for x in s.l if (x.get(c) or "") >= v]; return s
    def in_(s, c, vs):
        assert len(vs) <= 400
        vs = set(vs); s.l = [x for x in s.l if x.get(c) in vs]; return s
    def order(s, c, desc=False): s.l = sorted(s.l, key=lambda x: str(x.get(c))); return s
    def range(s, i, f): s.rng = (i, f); return s
    def execute(s):
        d = s.l[s.rng[0]:s.rng[1] + 1] if s.rng else s.l
        return type("R", (), {"data": d[:1000]})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
import model.score as sc
sc._carregar_modelos = lambda emp=None: (None, None, {"psi_referencia": REF})
EMAILS = []
import email_utils
email_utils.email_drift = lambda *a, **k: EMAILS.append(a)
U = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": ""},
     "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "x@x", "nome": "N",
                                                          "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}
c = TestClient(main.app, raise_server_exceptions=False)

_r = c.get("/admin/drift?empresa_id=beta", headers=H("ua"))
checar(_r.status_code == 200 and "beta" not in _r.text,
       "admin vê só a própria empresa (o empresa_id de outra é ignorado)", f"{_r.status_code}")
j = c.get("/admin/drift", headers=H("uc")).json()
checar(j["status"] == "escolha_empresa" and j["drift_detectado"] is False, "sem empresa: pede para escolher")
j = c.get("/admin/drift", headers=H("uc"), params={"empresa_id": "alfa"}).json()
esperado = calcular([p["score_recuperabilidade"] for p in PRED if p["id"].startswith("a") and not p["id"].startswith("av")], REF)
checar(j["n"] == 1500, "só os 1.500 da alfa nos últimos 30 dias (nem os antigos, nem a beta)", j.get("n"))
checar(j["psi"]["psi"] == esperado["psi"] and j["status"] == "critico" and j["drift_detectado"],
       "é o mesmo PSI da análise, com a mesma régua", f"{j['psi']['psi']} {j['status']}")
j = c.get("/admin/drift", headers=H("uc"), params={"empresa_id": "beta"}).json()
checar(j["status"] == "estavel" and not j["drift_detectado"], "beta, igual ao treino: estável", f"{j['psi'].get('psi')}")
j = c.get("/admin/drift", headers=H("uc"), params={"empresa_id": "ninguem"}).json()
checar(j["status"] == "indisponivel" and not j["drift_detectado"], "empresa sem análise recente: indisponível, com o motivo", j.get("mensagem"))
checar(not EMAILS, "abrir a tela não manda e-mail")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
