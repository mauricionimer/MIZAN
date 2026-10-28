"""Canal Telegram: convite, vínculo, webhook, conversa e entrega. Sem rede e sem IA real.

    python test_agente_telegram.py
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from agente import api, auditor, canal_telegram    # noqa: E402
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
ENVIADOS = []
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
os.environ.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="segredo-forte", TELEGRAM_BOT_USERNAME="mizan_bot")

main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": "Adm", "role": role, "empresa_id": empresa})}
ADM, OP = jwt("goias"), jwt("goias", "operador", "op")
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})
H = {"X-Telegram-Bot-Api-Secret-Token": "segredo-forte"}
def upd(texto, uid, chat=555, tipo="private"):
    return {"update_id": uid, "message": {"chat": {"id": chat, "type": tipo}, "from": {"is_bot": False}, "text": texto}}

print("— webhook: quem pode chamar —")
checar(c.post("/canal/telegram/webhook", json=upd("oi", 1)).status_code == 403, "sem o segredo: 403")
checar(c.post("/canal/telegram/webhook", json=upd("oi", 1), headers={"X-Telegram-Bot-Api-Secret-Token": "errado"}).status_code == 403, "segredo errado: 403")
os.environ["TELEGRAM_WEBHOOK_SECRET"] = ""
checar(c.post("/canal/telegram/webhook", json=upd("oi", 1), headers={"X-Telegram-Bot-Api-Secret-Token": ""}).status_code == 503, "sem configuração: 503, nunca aceita segredo vazio")
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "segredo-forte"
checar(c.post("/canal/telegram/webhook", json=upd("oi", 1), headers=H).status_code == 200, "segredo certo: 200")
checar(ENVIADOS[-1][1] == canal_telegram.MSG_SEM_VINCULO, "chat sem vínculo recebe só a instrução", ENVIADOS[-1][1][:40])
checar(c.post("/canal/telegram/webhook", content=b"nao json", headers=H).status_code == 400, "corpo inválido: 400")

print("— convite —")
checar(c.post("/agente/casos/p1/telegram-convite", headers=OP).status_code == 403, "operador não gera convite")
checar(c.post("/agente/casos/p1/telegram-convite", headers=jwt("beta")).status_code == 404, "devedor de outra empresa: 404")
r = c.post("/agente/casos/p1/telegram-convite", headers=ADM)
conv = r.json()
checar(r.status_code == 200 and conv["link"].startswith("https://t.me/mizan_bot?start="), "admin recebe o link do bot", str(conv)[:90])
codigo = conv["codigo"]
caso = REPO.caso_de("goias", "p1")
checar("convite_hash" in caso["dados"]["telegram"] and codigo[32:] not in json.dumps(caso["dados"]), "o caso guarda só o hash do segredo")
checar(len(codigo) <= 64, "o código cabe no limite do Telegram (64)", str(len(codigo)))

print("— vínculo —")
ENVIADOS.clear()
checar(c.post("/canal/telegram/webhook", json=upd("/start " + codigo[:-2] + "xx", 2), headers=H).status_code == 200 and
       ENVIADOS[-1][1] == canal_telegram.MSG_CONVITE_INVALIDO, "código adulterado não liga")
checar(REPO.caso_por_telegram(555) is None, "e nada ficou ligado")
c.post("/canal/telegram/webhook", json=upd("/start " + codigo, 3), headers=H)
checar(REPO.caso_por_telegram(555) is not None and ENVIADOS[-1][1] == canal_telegram.MSG_BOAS_VINDAS, "convite certo liga o chat e dá boas-vindas")
c.post("/canal/telegram/webhook", json=upd("/start " + codigo, 4, chat=777), headers=H)
checar(REPO.caso_por_telegram(777) is None and REPO.caso_por_telegram(555) is not None, "o convite vale uma vez: outro chat não rouba o vínculo")
r2 = c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()
vencido = datetime.now(timezone.utc) + timedelta(days=8)
checar(canal_telegram.vincular(REPO, r2["codigo"], 888, agora=vencido) is None, "convite vencido não liga")
c.post("/canal/telegram/webhook", json=upd("/start " + r2["codigo"], 5, chat=999), headers=H)
checar(REPO.caso_por_telegram(999) is not None and REPO.caso_por_telegram(555) is None, "novo convite religa o caso a outro chat e solta o anterior")
c.post("/canal/telegram/webhook", json=upd("/start " + c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"], 6, chat=555), headers=H)

print("— conversa —")
ENVIADOS.clear()
ROTEIRO[:] = [tri("pagar_negociar"), Resposta(ferramentas=[{"nome": "verificar_identidade", "args": {"tres_primeiros_digitos_cpf": "123"}}]),
              Resposta(texto="Obrigado, Maria. Quanto você consegue pagar por mês?")]
checar(c.post("/canal/telegram/webhook", json=upd("Quero negociar, CPF começa com 123", 10), headers=H).status_code == 200, "mensagem aceita")
checar(any("Quanto você consegue pagar" in t for ch, t in ENVIADOS) and all(ch == "555" for ch, _ in ENVIADOS),
       "a resposta do agente chegou ao Telegram do devedor", str(ENVIADOS)[:120])
n = len(ENVIADOS)
c.post("/canal/telegram/webhook", json=upd("Quero negociar, CPF começa com 123", 10), headers=H)
checar(len(ENVIADOS) == n, "o mesmo update reenviado pelo Telegram não duplica a resposta")
mens = REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 50)
checar([m["direcao"] for m in mens] == ["entrada", "saida"], "o caso registra uma entrada e uma saída", str([m["direcao"] for m in mens]))

print("— o que é ignorado —")
n = len(ENVIADOS)
for u in (upd("oi", 20, tipo="group"), {"update_id": 21, "message": {"chat": {"id": 555, "type": "private"}, "photo": []}},
          {"update_id": 22, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": True}, "text": "oi"}}, {"update_id": 23}):
    c.post("/canal/telegram/webhook", json=u, headers=H)
checar(len(ENVIADOS) == n, "grupo, foto, bot e update sem mensagem são ignorados")

print("— entrega com falha —")
canal_telegram.enviar_texto = lambda chat, texto: False
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Posso explicar sim.")]
checar(c.post("/canal/telegram/webhook", json=upd("Como funciona?", 30), headers=H).status_code == 200, "falha de rede não derruba o atendimento")
mens = REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 50)
checar(mens[-1]["direcao"] == "saida" and "Posso explicar" in mens[-1]["texto"], "a mensagem continua registrada no caso")

print("— atendente responde pelo chat do Mizan —")
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
ENVIADOS.clear()
r = c.post("/agente/casos/p1/atendente", json={"texto": "Oi, sou do banco. Posso ajudar?"}, headers=ADM)
checar(r.status_code == 409 and "Assuma o caso" in r.json()["detail"], "enquanto o agente cuida do caso, a pessoa não fala por cima", str(r.status_code))
c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=ADM)
checar(REPO.caso_de("goias", "p1")["situacao"] == "com_pessoa", "a equipe assumiu o caso")
r = c.post("/agente/casos/p1/atendente", json={"texto": "Oi, sou do banco. Posso ajudar?"}, headers=ADM)
checar(r.status_code == 200 and r.json()["entregue_telegram"] is True and r.json()["telegram_ligado"] is True, "a resposta da pessoa é entregue", str(r.status_code))
checar(ENVIADOS == [("555", "Oi, sou do banco. Posso ajudar?")], "e chega exatamente ao Telegram ligado ao caso", str(ENVIADOS))
msgs = r.json()["mensagens"]
checar(msgs[-1]["direcao"] == "saida" and msgs[-1]["trace_id"] == "pessoa", "fica registrada no caso, marcada como da pessoa")
ENVIADOS.clear()
c.post("/canal/telegram/webhook", json=upd("Pode sim, obrigado", 40), headers=H)
r = c.get("/agente/casos/p1", headers=ADM).json()
checar(r["mensagens"][-1]["direcao"] == "entrada" and "Pode sim" in r["mensagens"][-1]["texto"], "o que o devedor responde aparece no chat do Mizan")
checar(ENVIADOS == [], "e o agente não responde por cima enquanto o caso está com a pessoa", str(ENVIADOS))
checar(c.post("/agente/casos/p1/atendente", json={"texto": ""}, headers=ADM).status_code == 422, "mensagem vazia: 422")
checar(c.post("/agente/casos/p1/atendente", json={"texto": "oi"}, headers=jwt("beta")).status_code == 404, "outra empresa: 404")

print("— sinal leve e digitando —")
s1 = c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"]
ACOES = []
canal_telegram.enviar_acao = lambda chat, acao="typing": ACOES.append(str(chat)) or True
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
c.post("/canal/telegram/webhook", json=upd("Mais uma pergunta", 50), headers=H)
checar(c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"] != s1, "chegou mensagem: o sinal muda (a tela recarrega sozinha)")
s2 = c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"]
checar(c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"] == s2, "sem novidade, o sinal é o mesmo (a tela não recarrega à toa)")
checar(c.get("/agente/casos/p1/sinal", headers=jwt("beta")).json()["sinal"] == "", "outra empresa não vê nada")
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
c.post("/agente/casos/p1/controle", json={"acao": "devolver"}, headers=ADM)
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Claro.")]
ACOES.clear()
c.post("/canal/telegram/webhook", json=upd("Como funciona?", 51), headers=H)
checar(ACOES == ["555"], "o Telegram mostra \"digitando…\" assim que a mensagem chega", str(ACOES))

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
