"""Agentes — rotas das telas: conversa do caso, simulação da mensagem do devedor,
Central de orquestração. Repositório e fonte em memória; sem banco e sem IA real.

    python test_agente_api.py
"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
for v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from agente import api, auditor                    # noqa: E402
from agente.fonte import FonteMemoria              # noqa: E402
from agente.llm import ClienteFalso, Resposta      # noqa: E402
from agente.repositorio import RepoMemoria         # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

DEV = {"id": "p1", "empresa_id": "goias", "cpf": "123.456.789-00", "nome": "Maria das Dores",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao"}
REPO, FONTE = RepoMemoria(), FonteMemoria([DEV])
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
ROTEIRO = []
api.fabrica_repo = lambda: REPO
api.fabrica_fonte = lambda: FONTE
api.fabrica_cliente = lambda: ClienteFalso(ROTEIRO)

main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": "Adm", "role": role, "empresa_id": empresa})}
ADM, OP, CMD, OUTRA = jwt("goias"), jwt("goias", "operador", "op"), jwt("", "comando", "cmd"), jwt("beta")
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})

print("— interruptor e acesso —")
r = c.post("/agente/casos/p1/mensagem", json={"texto": "oi"}, headers=ADM)
checar(r.status_code == 409 and "desligado" in r.json()["detail"], "agente desligado: 409, nada acontece")
checar(REPO.eventos == {}, "nenhum evento criado com o agente desligado")
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
checar(c.post("/agente/casos/p1/mensagem", json={"texto": "oi"}, headers=OP).status_code == 403, "operador não simula conversa")
checar(c.post("/agente/casos/p1/mensagem", json={"texto": "oi"}, headers=OUTRA).status_code == 404,
       "devedor de outra empresa: não encontrado")
checar(c.post("/agente/casos/p1/mensagem", json={"texto": "oi"}, headers=CMD).status_code == 400, "comando precisa escolher a empresa")
checar(c.post("/agente/casos/p1/mensagem", json={"texto": ""}, headers=ADM).status_code == 422, "mensagem vazia: 422")
checar(c.get("/agente/central", headers=OP).status_code == 403, "Central só para admin e comando")

print("— conversa pela tela —")
ROTEIRO[:] = [tri("pagar_negociar"), Resposta(ferramentas=[{"nome": "verificar_identidade", "args": {"tres_primeiros_digitos_cpf": "123"}}]),
              Resposta(texto="Obrigado, Maria. Quanto você consegue pagar por mês?")]
r = c.post("/agente/casos/p1/mensagem", json={"texto": "Quero negociar, CPF começa com 123"}, headers=ADM)
j = r.json()
checar(r.status_code == 200 and [m["direcao"] for m in j["mensagens"]] == ["entrada", "saida"], "mensagem e resposta", str(j)[:200])
checar(j["caso"]["situacao"] == "em_contato" and j["caso"]["identidade_confirmada"], "caso em contato, identidade confirmada")
checar(j["evento"]["situacao"] == "feito" and j["trace_id"], "evento feito, com trace")
nos = [p["no"] for p in j["passos"]]
checar("triagem" in nos and "ferramenta:verificar_identidade" in nos and "auditor" in nos, "passos do trace para a tela", str(nos))
checar("123.456" not in r.text and "cpf" not in json.dumps(j["caso"]), "a tela não recebe CPF")
r = c.get("/agente/casos/p1", headers=OP)
checar(r.status_code == 200 and len(r.json()["mensagens"]) == 2, "operador lê a conversa")
checar(c.get("/agente/casos/p9", headers=OP).json()["caso"] is None, "caso que não existe: vazio")

print("— Central —")
r = c.get("/agente/central", headers=ADM).json()
checar(r["ligado"] and r["eventos"].get("feito") == 1 and r["casos"] == {"em_contato": 1}, "fila e casos por situação", str(r)[:200])
checar(r["politica"]["versao"] == 1 and r["politica"]["regras"]["desconto_max_pct"] == 30 and r["custo_hoje_usd"] == 0,
       "política vigente e custo do dia")
REPO.inserir_evento({"empresa_id": "goias", "caso_id": "x", "tipo": "desconhecido", "chave": "k1", "prioridade": 1})
REPO.eventos[list(REPO.eventos)[-1]].update(situacao="falhou", erro="LookupError")
r = c.get("/agente/central", headers=ADM).json()
checar(r["falhas"] and r["falhas"][0]["erro"] == "LookupError", "eventos que falharam aparecem")
checar(c.get("/agente/central", headers=OUTRA).json()["eventos"] == {}, "outra empresa não vê nada")
t = c.get(f"/agente/traces/{j['trace_id']}", headers=ADM).json()
checar(len(t["passos"]) == len(j["passos"]), "trace completo")

print("— política pela tela —")
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)
r = c.get("/agente/politica", headers=ADM).json()
checar(r["versoes"][0]["versao"] == 1 and r["demonstracao"]["desconto_max_pct"] == 30, "versões e valores de demonstração")
nova = {**auditor.POLITICA_DEMONSTRACAO, "desconto_max_pct": 20}
checar(c.post("/agente/politica", json={"regras": nova}, headers=OP).status_code == 403, "operador não muda a política")
checar(c.post("/agente/politica", json={"regras": {**nova, "desconto_max_pct": 200}}, headers=ADM).status_code == 422,
       "política inválida: 422 com o motivo")
r = c.post("/agente/politica", json={"regras": nova}, headers=ADM)
checar(r.status_code == 200 and r.json()["versao"] == 2 and REPO.politica_ativa("goias")["regras"]["desconto_max_pct"] == 20,
       "versão 2 ativa")
checar([p["ativa"] for p in REPO.politicas_da_empresa("goias")] == [True, False], "a versão 1 fica guardada, inativa")
checar(AUD and AUD[-1]["acao"] == "politica_agente_alterada" and AUD[-1]["detalhes"]["versao"] == 2, "mudança na auditoria")
ROTEIRO[:] = [tri("pagar_negociar"), Resposta(ferramentas=[{"nome": "simular_acordo", "args": {"desconto_pct": 25, "n_parcelas": 1}}]),
              Resposta(texto="Esse desconto não está disponível. Posso simular outras condições.")]
j = c.post("/agente/casos/p1/mensagem", json={"texto": "faz 25% à vista?"}, headers=ADM).json()
aud = [p for p in j["passos"] if p["no"] == "auditor"]
checar(all(p["versao_politica"] == 2 for p in aud), "o agente obedece a versão nova na conversa seguinte")

print("— controles do gestor —")
checar(c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=OP).status_code == 403, "operador não assume pelo controle")
r = c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=ADM)
checar(r.status_code == 200 and r.json()["caso"]["situacao"] == "com_pessoa", "gestor assume: o agente para")
ROTEIRO[:] = ["NÃO DEVIA SER CHAMADO"]
j = c.post("/agente/casos/p1/mensagem", json={"texto": "oi?"}, headers=ADM).json()
checar(j["mensagens"][-1]["direcao"] == "entrada", "com o caso assumido, o agente não responde")
r = c.post("/agente/casos/p1/controle", json={"acao": "devolver"}, headers=ADM)
checar(r.json()["caso"]["situacao"] == "em_contato", "devolve ao agente")
checar(c.post("/agente/casos/p1/controle", json={"acao": "apagar"}, headers=ADM).status_code == 422, "ação inválida: 422")
checar(c.post("/agente/casos/p9/controle", json={"acao": "assumir"}, headers=ADM).status_code == 404, "sem caso: 404")
caso = REPO.caso_de("goias", "p1")
REPO.travar_caso(caso["id"], "outro", datetime(2030, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc))
checar(c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=ADM).status_code == 409,
       "caso sendo processado: 409, tenta de novo")
checar(any(p["no"] == "controle_do_gestor" and p["agente"] == "pessoa" for p in REPO.passos), "controle fica no rastreio")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
