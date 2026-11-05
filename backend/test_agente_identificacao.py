"""O agente diz quem é (de qual empresa fala) quando perguntam, antes de pedir o CPF.
Sem rede e sem IA real.

    python test_agente_identificacao.py
"""
import json, os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cryptography.fernet import Fernet
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from agente import api, auditor, canal_telegram, negociador    # noqa: E402
from agente.fonte import FonteMemoria              # noqa: E402
from agente.juridico import sinais                 # noqa: E402
from agente.llm import ClienteFalso, Resposta      # noqa: E402
from agente.repositorio import RepoMemoria         # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1


print("— o detector —")
SIM = ["Quem é você?.", "Quem é você?", "Da mizan?\nOu algum banco?", "De qual banco é isso?", "De qual empresa você fala?",
       "Você é um robô?", "Isso é golpe?", "De onde você fala?", "Com quem estou falando?", "Quem está falando?",
       "É da Mizan?", "você é uma pessoa?", "qual a empresa?", "quem é vc", "é golpe?", "Você é do banco?",
       "Isso é seguro?", "Isso é de verdade?", "É oficial?"]
NAO = ["Quero parcelar em 3 vezes", "Meu CPF começa com 123", "Posso pagar 300 por mês", "Sim, sou eu", "Não reconheço essa dívida",
       "Quero falar com uma pessoa", "Qual o valor da parcela?", "Oi", "Tudo bem e você?",
       "É verdade, estou devendo mesmo", "Não é golpe, eu pago amanhã", "Sim é verdade", "Isso é um absurdo",
       "Quem é você? Eu queria entender essa dívida porque faz muito tempo que não pago nada e ganho pouco hoje em dia"]
for t in SIM:
    checar(sinais.pergunta_quem_e(t), f"pergunta quem é: {t!r}")
for t in NAO:
    checar(not sinais.pergunta_quem_e(t), f"não é essa pergunta: {t[:50]!r}")
checar(sinais.cita_mizan("Da mizan?") and not sinais.cita_mizan("de qual banco?"), "só fala da Mizan se a pessoa falou")


print("— pelo Telegram, com as frases do print —")
DEV = {"id": "p1", "empresa_id": "goias", "cpf": "123.456.789-00", "nome": "Maria das Dores",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao"}
REPO, FONTE = RepoMemoria(), FonteMemoria([DEV], nome_empresa="Goiás Bank")
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
ROTEIRO, CLIENTES = [], []
api.fabrica_repo = lambda: REPO
api.fabrica_fonte = lambda: FONTE
api.fabrica_cliente = lambda: CLIENTES.append(ClienteFalso(ROTEIRO)) or CLIENTES[-1]
ENVIADOS = []
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
canal_telegram.apagar_mensagem = lambda chat, mid: True
canal_telegram.enviar_acao = lambda chat, acao="typing": True
os.environ.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="segredo-forte", TELEGRAM_BOT_USERNAME="mizan_bot")
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
ADM = {"Authorization": "Bearer " + criar_token({"sub": "adm", "email": "adm@x", "nome": "Adm", "role": "admin", "empresa_id": "goias"})}
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})
def msg(uid, texto):
    return {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": False}, "text": texto}}
def receber(uid, texto):
    return canal_telegram.receber(msg(uid, texto), repo=REPO)
def chamadas_do_negociador():
    return [ch for cl in CLIENTES for ch in cl.chamadas if ch["papel"] == "negociador"]

codigo = c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"]
receber(1, "/start " + codigo)
ENVIADOS.clear()

ROTEIRO[:] = [tri("duvida")]
r = receber(10, "Quem é você?.")
resp = ENVIADOS[-1][1] if ENVIADOS else ""
checar(r["acao"] == "mensagem" and "assistente virtual de Goiás Bank" in resp, "\"Quem é você?\": diz de qual empresa fala", resp[:90])
checar("não uma pessoa" in resp and "pendência financeira no seu nome" in resp, "e o que é (automático) e por que está falando")
checar("três primeiros dígitos do seu CPF" in resp, "depois pede a confirmação, como o fluxo manda")
checar("nunca peço senha" in resp, "e avisa que nunca pede senha nem dados da conta")
checar("Mizan" not in resp, "não fala da Mizan se ninguém perguntou")
checar(not chamadas_do_negociador(), "sem chamar a IA de conversa (resposta pronta)")
mens = REPO.ultimas_mensagens("goias", REPO.caso_de("goias", "p1")["id"], 20)
checar([m["direcao"] for m in mens][-2:] == ["entrada", "saida"], "fica registrada no caso")

ROTEIRO[:] = [tri("duvida")]
receber(11, "Da mizan?\nOu algum banco?")
resp = ENVIADOS[-1][1]
checar("assistente virtual de Goiás Bank" in resp and "A Mizan é a plataforma de tecnologia que Goiás Bank usa" in resp,
       "\"Da Mizan? Ou algum banco?\": diz que é o Goiás Bank e que a Mizan é a plataforma", resp[:120])
checar("Não, não somos" not in resp, "e nunca nega ser a instituição")

# identidade já confirmada: não pede o CPF de novo
caso = REPO.caso_de("goias", "p1")
REPO.salvar_caso(caso["id"], {"dados": {**caso["dados"], "identidade_ok": True}})
ROTEIRO[:] = [tri("duvida")]
receber(12, "Isso é golpe?")
resp = ENVIADOS[-1][1]
checar("assistente virtual de Goiás Bank" in resp and "CPF" not in resp and "seguir a conversa" in resp,
       "com a identidade confirmada, responde e não pede o CPF de novo", resp[-110:])

print("— mensagem longa vai para a conversa, que sabe o nome da empresa —")
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Sou o assistente virtual do Goiás Bank. Pode me contar sua situação.")]
longa = "Quem é você? Eu queria entender essa dívida porque faz muito tempo que não pago nada e ganho pouco hoje em dia"
receber(13, longa)
ch = chamadas_do_negociador()
checar(len(ch) == 1, "a IA de conversa foi chamada")
corpo = json.dumps(ch[0]["mensagens"], ensure_ascii=False) if ch else ""
checar('"instituicao": "Goiás Bank"' in corpo.replace('\\"', '"'), "o briefing leva o nome da empresa", corpo[:0])
checar("PRIMEIRO, em uma ou duas frases" in ch[0]["sistema"] and negociador.VERSAO_PROMPT.startswith("negociador-v"),
       "e a regra de dizer quem é está no prompt")

print("— não repete a mesma pergunta —")
PERGUNTA = "Para conversarmos com segurança, você lembra os três primeiros dígitos do seu CPF? Assim consigo te ajudar com a pendência."
OUTRA = "Entendo, sem problema. Preciso só dos três primeiros dígitos para proteger seus dados. Se preferir, uma pessoa da equipe continua com você."
ROTEIRO[:] = [tri("duvida"), Resposta(texto=PERGUNTA)]
receber(20, "Hum")
n0 = len(chamadas_do_negociador())
ROTEIRO[:] = [tri("duvida"), Resposta(texto=PERGUNTA), Resposta(texto=OUTRA)]
receber(21, "Não sei se quero falar disso agora")
ch = chamadas_do_negociador()[n0:]
checar(len(ch) == 2, "resposta igual à anterior: a IA é chamada de novo", str(len(ch)))
checar(ENVIADOS[-1][1] == OUTRA, "e a pessoa recebe a versão nova, não a repetição", ENVIADOS[-1][1][:60])
retorno = json.dumps(ch[1]["mensagens"][-1], ensure_ascii=False) if len(ch) > 1 else ""
checar("repete quase igual" in retorno, "a IA é avisada de que repetiu")
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Combinado, vamos no seu tempo. Quando quiser retomar, é só me escrever por aqui.")]
n1 = len(chamadas_do_negociador())
receber(22, "Tá bom, depois eu vejo")
checar(len(chamadas_do_negociador()) - n1 == 1, "resposta diferente passa de primeira")

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
