"""Telas ao vivo: contadores de mudança por empresa (GET /mudancas). Sem banco e sem IA real.

    python test_mudancas.py
"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste", MIZAN_AGENTE_ATIVO="1")
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
import main                                                       # noqa: E402
from auth import criar_token                                      # noqa: E402
from fastapi.testclient import TestClient                         # noqa: E402
from agente import api, auditor, mudancas, orquestrador as orq    # noqa: E402
from agente.fonte import FonteMemoria                             # noqa: E402
from agente.llm import ClienteFalso, Resposta                     # noqa: E402
from agente.repositorio import RepoMemoria                        # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

USUARIOS = {}
def jwt(sub, empresa, role="admin"):
    USUARIOS[sub] = {"id": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa, "ativo": True}
    return {"Authorization": "Bearer " + criar_token({"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role,
                                                      "empresa_id": empresa})}
main.buscar_usuario_por_id = lambda uid: USUARIOS.get(uid)
main._conferir_versao_da_senha = lambda *a, **k: None
c = TestClient(main.app, raise_server_exceptions=False)
GOIAS, BETA, CMD = jwt("adm", "goias"), jwt("adm-b", "beta"), jwt("cmd", "", "comando")
v = lambda h, q="": c.get("/mudancas" + q, headers=h).json()

print("— quem pode perguntar —")
checar(c.get("/mudancas").status_code in (401, 403), "sem login: recusado")
a0, b0, cmd0 = v(GOIAS), v(BETA), v(CMD)
checar(set(a0) == {"agenda", "casos"}, "devolve a versão da agenda e dos casos", str(a0))
checar(v(GOIAS) == a0, "sem mudança, a versão é a mesma (a tela não recarrega à toa)")

print("— o agente marca na agenda —")
DEV = {"id": "p1", "empresa_id": "goias", "cpf": "123.456.789-00", "nome": "Luciana", "valor_divida": 3000.0,
       "dias_em_atraso": 95, "produto": "cartao"}
REPO, FONTE = RepoMemoria(), FonteMemoria([DEV])
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
caso = REPO.obter_ou_criar_caso("goias", "p1")
REPO.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": {"identidade_ok": True, "divida": 3000.0}})
tri = json.dumps({"intencao": "outro", "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})
orq.registrar_evento(REPO, "goias", caso["id"], "mensagem_devedor", "m1", {"texto": "marca dia 3 às 10h"})
orq.processar_proximo(REPO, api.grafos(FONTE), ClienteFalso([
    tri, Resposta(ferramentas=[{"nome": "agendar_retorno", "args": {"data": "2026-11-03", "hora": "10:00", "motivo": "x"}}]),
    Resposta(texto="Combinado.")]), datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc))
a1 = v(GOIAS)
checar(a1["agenda"] != a0["agenda"] and a1["casos"] != a0["casos"], "a agenda e os casos da empresa mudaram de versão")
checar(v(BETA) == b0, "a outra empresa não recarrega nada")
checar(v(CMD)["agenda"] != cmd0["agenda"] and v(CMD, "?empresa_id=beta") == b0,
       "o comando vê o total de todas, ou só a empresa que escolheu")

print("— alguém salva algo pelo sistema —")
api.fabrica_repo, api.fabrica_fonte = (lambda: REPO), (lambda: FONTE)
r = c.post("/agente/casos/p1/telegram-desligar", json={}, headers=GOIAS)  # qualquer escrita da empresa
checar(r.status_code == 200, "a escrita deu certo", str(r.status_code))
checar(v(GOIAS) != a1, "uma escrita da empresa avisa as telas dela")
b1 = v(BETA)
c.get("/agente/casos/p1", headers=GOIAS)
a2 = v(GOIAS)
r = c.post("/agente/casos/naoexiste/telegram-desligar", json={}, headers=GOIAS)
checar(r.status_code == 404 and v(GOIAS) == a2, "escrita que falhou não avisa ninguém", str(r.status_code))
checar(v(BETA) == b1 and v(GOIAS) == v(GOIAS), "leituras não mudam nada")

print("— reiniciar o servidor também conta como mudança —")
antes = mudancas.versoes("goias")
mudancas._INICIO = "outro"
checar(mudancas.versoes("goias") != antes, "versão nova depois de reiniciar (a tela recarrega uma vez)")

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
