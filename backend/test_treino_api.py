"""API de treino por empresa: só COMANDO, uma tarefa por vez, auditada, sem dado pessoal no registro.

    python test_treino_api.py
"""
import json, os, shutil, sys, tempfile, threading, time
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
TMP = tempfile.mkdtemp(prefix="mizan_api_")
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste", MIZAN_DATA_DIR=TMP)
(Path(TMP) / "model").mkdir(parents=True)
for n in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl"):
    shutil.copy(AQUI / "model" / n, Path(TMP) / "model" / n)

import main                                      # noqa: E402
from auth import criar_token                     # noqa: E402
from fastapi.testclient import TestClient        # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

USERS = {"c": {"ativo": True, "id": "c", "role": "comando", "empresa_id": "", "email": "c@x.com"},
         "a": {"ativo": True, "id": "a", "role": "admin", "empresa_id": "goias", "email": "a@x.com"}}
main.buscar_usuario_por_id = lambda uid: USERS[uid]
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)
_trava = threading.Lock()
main._travas.adquirir = lambda nome, duracao_min=30: _trava.acquire(blocking=False)
main._travas.liberar = lambda nome: _trava.release() if _trava.locked() else None
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u, r: {"Authorization": "Bearer " + criar_token({"sub": u, "email": USERS[u]["email"], "nome": "N", "role": r, "empresa_id": ""})}
HC, HA = H("c", "comando"), H("a", "admin")

rng = np.random.default_rng(3)
N = 2000
dias = rng.integers(10, 900, N); renda = rng.lognormal(7.9, 0.5, N)
pagou = rng.random(N) < 1 / (1 + np.exp(0.004 * dias - 0.8))
df = pd.DataFrame({"cpf": [f"{i:011d}" for i in range(N)], "nome": [f"Pessoa {i}" for i in range(N)],
                   "valor_divida": rng.lognormal(8, .8, N).round(2), "renda_estimada": renda.round(2),
                   "dias_em_atraso": dias, "produto": rng.choice(["cartao", "pessoal"], N),
                   "uf": "GO", "pagou": np.where(pagou, "sim", "nao"),
                   "data_referencia": pd.date_range("2024-01-01", periods=N, freq="8h").strftime("%d/%m/%Y")})
CSV = df.to_csv(index=False).encode()

def enviar(h, conteudo=CSV, nome="g.csv", emp="Goias Bank"):
    return c.post("/comando/treino", headers=h, data={"empresa_id": emp}, files={"file": (nome, conteudo)})

def esperar(jid, ate=180):
    t0 = time.time()
    while time.time() - t0 < ate:
        j = c.get(f"/comando/treino/{jid}", headers=HC).json()
        if j["estado"] in ("concluido", "recusado", "falhou"):
            return j
        time.sleep(0.5)
    return j

# ── acesso ──────────────────────────────────────────────────────────────
checar(enviar(HA).status_code == 403, "admin não treina")
checar(enviar({}).status_code in (401, 403), "sem token não treina")
checar(c.get("/comando/modelos", headers=HA, params={"empresa_id": "x"}).status_code == 403, "admin não lista versões")
checar(enviar(HC, nome="g.txt").status_code == 400, "extensão errada: 400")
checar(enviar(HC, conteudo=b"a" * (26 * 1024 * 1024)).status_code == 413, "arquivo de 26 MB: 413")

# ── recusa de arquivo ruim, assíncrona ──────────────────────────────────
r = enviar(HC, conteudo=df.drop(columns=["pagou"]).to_csv(index=False).encode())
checar(r.status_code == 202, "aceita e processa em segundo plano", r.text[:60])
j = esperar(r.json()["id"])
checar(j["estado"] == "recusado" and "resultado" in j["erro"].lower(), "arquivo sem resultado: recusado com motivo", str(j)[:100])

# ── treino de verdade, e um só por vez ──────────────────────────────────
r = enviar(HC)
jid = r.json()["id"]
r2 = enviar(HC)
checar(r2.status_code == 409, "segundo treino enquanto o primeiro roda: 409", str(r2.status_code))
j = esperar(jid)
checar(j["estado"] == "concluido", "treino conclui", str(j)[:200])
checar("registro" in j and j["registro"]["dados_descartados"] is True, "registro diz que os dados foram descartados")
texto = json.dumps(j)
checar("00000000007" not in texto and "Pessoa 7" not in texto, "o estado da tarefa não carrega CPF nem nome")
checar(not any(isinstance(v, (bytes, bytearray)) for v in j.values()), "nem o arquivo")

ver = j["versao"]
l = c.get("/comando/modelos", headers=HC, params={"empresa_id": "Goias Bank"}).json()
checar(l["usando"] == "global" and l["versoes"][0]["versao"] == ver, "depois de treinar, ainda usa o global")

# ── ativação ────────────────────────────────────────────────────────────
from model import modelos_empresa as me
dados = me.carregar_versoes("goias bank")
auc_novo = dados["versoes"][0]["metricas"]["novo"]["auc"]
dados["versoes"][0]["metricas"]["novo"]["auc"] = 0.01          # força "pior que o atual"
me.salvar_versoes("goias bank", dados)
r = c.post("/comando/modelos/ativar", headers=HC, json={"empresa_id": "Goias Bank", "versao": ver})
checar(r.status_code == 409, "modelo pior que o atual não ativa sem confirmação", r.text[:90])
r = c.post("/comando/modelos/ativar", headers=HC, json={"empresa_id": "Goias Bank", "versao": ver, "forcar": True})
checar(r.status_code == 200, "com confirmação ativa", r.text[:80])
l = c.get("/comando/modelos", headers=HC, params={"empresa_id": "Goias Bank"}).json()
checar(l["usando"] == "proprio" and l["versao_ativa"] == ver, "agora usa o próprio")
checar(c.post("/comando/modelos/ativar", headers=HC, json={"empresa_id": "Goias Bank", "versao": "nao_existe"}).status_code == 404, "versão inexistente: 404")
checar(main._get_versao_ativa("goias bank") == ver and main._get_versao_ativa("outro") != ver,
       "a carteira registra a versão da empresa; outra empresa não")
r = c.post("/comando/modelos/desativar", headers=HC, json={"empresa_id": "Goias Bank"})
checar(r.status_code == 200 and c.get("/comando/modelos", headers=HC, params={"empresa_id": "Goias Bank"}).json()["usando"] == "global",
       "desativar volta ao global")

acoes = [a["acao"] for a in AUD]
checar(acoes.count("modelo_treinado") == 1 and "modelo_ativado" in acoes and "modelo_desativado" in acoes,
       "treino, ativação e desativação auditados", str(acoes))
checar(not any("cpf" in json.dumps(a.get("detalhes", {})).lower() for a in AUD), "auditoria sem dado pessoal")
checar(c.get("/comando/modelos", headers=HC, params={"empresa_id": "../../x"}).status_code == 200, "empresa_id estranho não quebra nem escapa")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if falhas else 0)
