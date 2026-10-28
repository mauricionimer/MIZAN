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
       ENVIADOS[-1][1] == canal_telegram.MSG_CONVITE["invalido"], "código adulterado não liga")
checar(REPO.caso_por_telegram(555) is None, "e nada ficou ligado")
c.post("/canal/telegram/webhook", json=upd("/start " + codigo, 3), headers=H)
checar(REPO.caso_por_telegram(555) is not None and ENVIADOS[-1][1] == canal_telegram.MSG_BOAS_VINDAS, "convite certo liga o chat e dá boas-vindas")
st = c.get("/agente/casos/p1", headers=ADM).json()["telegram"]
checar(st["ligado"] and not st["convite_pendente_ate"] and "chat_id" not in json.dumps(st), "a tela vê \"ligado\", sem o chat_id", str(st))
c.post("/canal/telegram/webhook", json=upd("/start " + codigo, 4), headers=H)
checar(ENVIADOS[-1][1] == canal_telegram.MSG_JA_LIGADO, "a mesma pessoa abre o link de novo: \"você já está conectado\"")
c.post("/canal/telegram/webhook", json=upd("/start", 4_1), headers=H)
checar(ENVIADOS[-1][1] == canal_telegram.MSG_JA_LIGADO, "/start sem código num chat ligado: \"já conectado\"")
c.post("/canal/telegram/webhook", json=upd("/start", 4_2, chat=321), headers=H)
checar(ENVIADOS[-1][1] == canal_telegram.MSG_SEM_VINCULO, "/start sem código num chat sem vínculo: pede o link")
c.post("/canal/telegram/webhook", json=upd("/start " + codigo, 5, chat=777), headers=H)
checar(REPO.caso_por_telegram(777) is None and REPO.caso_por_telegram(555) is not None,
       "o convite vale uma vez: outro chat não rouba o vínculo")
checar(ENVIADOS[-1][1] == canal_telegram.MSG_CONVITE["usado"], "e a segunda pessoa ouve que cada um precisa do próprio link")
checar(c.get("/agente/casos/p1", headers=ADM).json()["telegram"]["tentativa_outro_chat_em"],
       "a equipe vê no caso que alguém tentou usar o link em outro Telegram")
r2 = c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()
checar(r2["vinculado"] is True, "gerar convite com o chat ligado avisa a tela (para confirmar antes)")
vencido = datetime.now(timezone.utc) + timedelta(days=8)
checar(canal_telegram.vincular(REPO, r2["codigo"], 888, agora=vencido) == (None, "vencido"), "convite vencido não liga")
r3 = c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()
checar(r3["substituiu"] is True, "um convite novo substitui o pendente")
c.post("/canal/telegram/webhook", json=upd("/start " + r2["codigo"], 6, chat=999), headers=H)
checar(REPO.caso_por_telegram(999) is None and ENVIADOS[-1][1] == canal_telegram.MSG_CONVITE["substituido"],
       "o link substituído não liga e diz para usar o mais novo")
c.post("/canal/telegram/webhook", json=upd("/start " + r3["codigo"], 7, chat=999), headers=H)
checar(REPO.caso_por_telegram(999) is not None and REPO.caso_por_telegram(555) is None, "novo convite religa o caso a outro chat e solta o anterior")
c.post("/canal/telegram/webhook", json=upd("/start " + c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"], 8, chat=555), headers=H)
checar(REPO.caso_por_telegram(555) is not None, "e volta para o primeiro chat com outro convite")

print("— desligar o Telegram do caso —")
checar(c.post("/agente/casos/p1/telegram-desligar", json={}, headers=OP).status_code == 403, "operador não desliga")
r = c.post("/agente/casos/p1/telegram-desligar", json={}, headers=ADM)
checar(r.status_code == 200 and r.json()["telegram"]["ligado"] is False and REPO.caso_por_telegram(555) is None, "admin desliga")
ENVIADOS.clear()
c.post("/canal/telegram/webhook", json=upd("oi", 9), headers=H)
checar(ENVIADOS == [("555", canal_telegram.MSG_SEM_VINCULO)], "depois de desligado, o chat só recebe a instrução")
c.post("/canal/telegram/webhook", json=upd("/start " + c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"], 9_1), headers=H)

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

print("— o que é ignorado e o que não é texto —")
n = len(ENVIADOS)
for u in (upd("oi", 20, tipo="group"), {"update_id": 22, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": True}, "text": "oi"}},
          {"update_id": 23}, {"update_id": 24, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": False}}}):
    c.post("/canal/telegram/webhook", json=u, headers=H)
checar(len(ENVIADOS) == n, "grupo, bot e update sem mensagem são ignorados")
foto = lambda uid: {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": False}, "photo": [{}]}}
c.post("/canal/telegram/webhook", json=foto(25), headers=H)
c.post("/canal/telegram/webhook", json=foto(26), headers=H)
checar(ENVIADOS[n:] == [("555", canal_telegram.MSG_SO_TEXTO)], "foto ou áudio: avisa que só lê texto, uma vez (sem repetir a cada foto)", str(ENVIADOS[n:]))

print("— entrega com falha e reenvio —")
canal_telegram.enviar_texto = lambda chat, texto: False
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Posso explicar sim.")]
checar(c.post("/canal/telegram/webhook", json=upd("Como funciona?", 30), headers=H).status_code == 200, "falha de rede não derruba o atendimento")
mens = REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 50)
checar(mens[-1]["direcao"] == "saida" and "Posso explicar" in mens[-1]["texto"], "a mensagem continua registrada no caso")
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
ENVIADOS.clear()
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Os juros já estão no valor.")]
c.post("/canal/telegram/webhook", json=upd("E os juros?", 31), headers=H)
checar([t for _, t in ENVIADOS] == ["Posso explicar sim.", "Os juros já estão no valor."],
       "na rodada seguinte, o que tinha falhado vai antes, na ordem", str(ENVIADOS))
ENVIADOS.clear()
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Certo.")]
c.post("/canal/telegram/webhook", json=upd("Ok", 32), headers=H)
checar([t for _, t in ENVIADOS] == ["Certo."], "e nada é entregue duas vezes", str(ENVIADOS))

print("— devedor bloqueou o bot —")
canal_telegram.enviar_texto = lambda chat, texto: canal_telegram.BLOQUEADO
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Tudo bem.")]
c.post("/canal/telegram/webhook", json=upd("Vou pensar", 33), headers=H)
checar(c.get("/agente/casos/p1", headers=ADM).json()["telegram"]["bloqueado"] is True, "o caso fica marcado como bloqueado")
TENTOU = []
canal_telegram.enviar_texto = lambda chat, texto: TENTOU.append(texto) or True
checar(canal_telegram.enviar_para_caso(REPO, REPO.caso_de("goias", "p1"), "teste") == "bloqueado" and TENTOU == [],
       "e não se tenta mais enquanto ele não voltar")
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Que bom que voltou.")]
c.post("/canal/telegram/webhook", json=upd("Voltei", 34), headers=H)
checar(c.get("/agente/casos/p1", headers=ADM).json()["telegram"]["bloqueado"] is False and "Que bom que voltou." in TENTOU,
       "voltou a escrever: desbloqueia e a resposta chega", str(TENTOU))
checar("Tudo bem." not in TENTOU, "o que falhou com o bot bloqueado não chega atrasado", str(TENTOU))

print("— atendente responde pelo chat do Mizan —")
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
ENVIADOS.clear()
r = c.post("/agente/casos/p1/atendente", json={"texto": "Oi, sou do banco. Posso ajudar?"}, headers=ADM)
checar(r.status_code == 409 and "Assuma o caso" in r.json()["detail"], "enquanto o agente cuida do caso, a pessoa não fala por cima", str(r.status_code))
r = c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=ADM)
checar(REPO.caso_de("goias", "p1")["situacao"] == "com_pessoa", "a equipe assumiu o caso")
checar(r.json().get("entrega") == "entregue" and ENVIADOS == [("555", canal_telegram.AVISO_ASSUMIU)],
       "o devedor fica sabendo que agora fala com uma pessoa", str(ENVIADOS))
r = c.post("/agente/casos/p1/atendente", json={"texto": "Oi, sou do banco. Posso ajudar?"}, headers=ADM)
checar(r.status_code == 200 and r.json()["entrega"] == "entregue" and r.json()["telegram_ligado"] is True, "a resposta da pessoa é entregue", str(r.status_code))
checar(ENVIADOS[-1] == ("555", "Oi, sou do banco. Posso ajudar?"), "e chega exatamente ao Telegram ligado ao caso", str(ENVIADOS))
msgs = r.json()["mensagens"]
checar(msgs[-1]["direcao"] == "saida" and msgs[-1]["trace_id"] == "pessoa", "fica registrada no caso, marcada como da pessoa")
checar(any(m["trace_id"] == "aviso" and m["texto"] == canal_telegram.AVISO_ASSUMIU for m in msgs), "o aviso de passagem também fica no caso")
at = c.get("/agente/atendimentos", headers=ADM).json()["itens"]
checar(len(at) == 1 and at[0]["predicao_id"] == "p1" and at[0]["esperando"] is False, "lista de atendimentos: respondido, não espera", str(at))
ENVIADOS.clear()
c.post("/canal/telegram/webhook", json=upd("Pode sim, obrigado", 40), headers=H)
r = c.get("/agente/casos/p1", headers=ADM).json()
checar(r["mensagens"][-1]["direcao"] == "entrada" and "Pode sim" in r["mensagens"][-1]["texto"], "o que o devedor responde aparece no chat do Mizan")
checar(ENVIADOS == [], "e o agente não responde por cima enquanto o caso está com a pessoa", str(ENVIADOS))
at = c.get("/agente/atendimentos", headers=ADM).json()["itens"]
checar(at[0]["esperando"] is True, "e o caso aparece como esperando resposta da equipe")
checar(c.post("/agente/casos/p1/atendente", json={"texto": ""}, headers=ADM).status_code == 422, "mensagem vazia: 422")
checar(c.post("/agente/casos/p1/atendente", json={"texto": "oi"}, headers=jwt("beta")).status_code == 404, "outra empresa: 404")
checar(c.get("/agente/atendimentos", headers=jwt("beta")).json()["itens"] == [], "outra empresa não vê os atendimentos")

print("— sinal leve e digitando —")
s1 = c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"]
ACOES = []
canal_telegram.enviar_acao = lambda chat, acao="typing": ACOES.append(str(chat)) or True
c.post("/canal/telegram/webhook", json=upd("Mais uma pergunta", 50), headers=H)
checar(c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"] != s1, "chegou mensagem: o sinal muda (a tela recarrega sozinha)")
s2 = c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"]
checar(c.get("/agente/casos/p1/sinal", headers=ADM).json()["sinal"] == s2, "sem novidade, o sinal é o mesmo (a tela não recarrega à toa)")
checar(c.get("/agente/casos/p1/sinal", headers=jwt("beta")).json()["sinal"] == "", "outra empresa não vê nada")

print("— devolver ao agente —")
canal_telegram.enviar_texto = lambda chat, texto: False
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Resposta velha que não deve chegar.")]
c.post("/agente/casos/p1/controle", json={"acao": "devolver"}, headers=ADM)
ENVIADOS.clear()
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
r = c.post("/agente/casos/p1/controle", json={"acao": "assumir"}, headers=ADM)
r = c.post("/agente/casos/p1/controle", json={"acao": "devolver"}, headers=ADM)
checar(r.json().get("entrega") == "entregue" and ENVIADOS[-1] == ("555", canal_telegram.AVISO_DEVOLVEU),
       "ao devolver, o devedor sabe que o assistente voltou", str(ENVIADOS))
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Claro.")]
ACOES.clear()
ENVIADOS.clear()
c.post("/canal/telegram/webhook", json=upd("Como funciona?", 51), headers=H)
checar(ACOES == ["555"], "o Telegram mostra \"digitando…\" assim que a mensagem chega", str(ACOES))
checar([t for _, t in ENVIADOS] == ["Claro."], "o agente volta a responder, sem nada atrasado de antes da passagem", str(ENVIADOS))

print("— agente desligado —")
os.environ["MIZAN_AGENTE_ATIVO"] = "0"
ENVIADOS.clear()
antes = len(REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 200))
c.post("/canal/telegram/webhook", json=upd("Alguém aí?", 60), headers=H)
c.post("/canal/telegram/webhook", json=upd("Alguém aí?", 60), headers=H)
c.post("/canal/telegram/webhook", json=upd("Oi??", 61), headers=H)
mens = REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 200)
entradas = [m["texto"] for m in mens[antes:] if m["direcao"] == "entrada"]
checar(entradas == ["Alguém aí?", "Oi??"], "a mensagem não se perde (e o reenvio do Telegram não duplica)", str(entradas))
checar(ENVIADOS == [("555", canal_telegram.MSG_PAUSADO)], "o devedor sabe que foi recebida, uma vez só", str(ENVIADOS))
os.environ["MIZAN_AGENTE_ATIVO"] = "1"

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
