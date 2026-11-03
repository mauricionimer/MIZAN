"""Áudio do devedor pelo Telegram: transcrição, limites, falhas e aceite por áudio.
Sem rede e sem IA real (o Gemini e o Telegram são falsos).

    python test_agente_audio.py
"""
import base64, contextlib, http.server, io, json, os, sys, threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from cryptography.fernet import Fernet
# Como em test_agente_telegram: simula produção (chave Fernet obrigatória).
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode())
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AUDIO", "MIZAN_AUDIO_MAX_S",
          "MIZAN_AUDIO_POR_DIA", "MIZAN_MODELO_AUDIO", "MIZAN_MODELO_TRIAGEM", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(v, None)
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
os.environ["MIZAN_AGENTE_PRECOS"] = json.dumps({"gemini-audio-teste": [0.5, 1.5]})
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from agente import api, audio, auditor, canal_telegram, ferramentas, llm   # noqa: E402
from agente.fonte import FonteMemoria              # noqa: E402
from agente.llm import ClienteFalso, Resposta      # noqa: E402
from agente.repositorio import RepoMemoria         # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1


print("— módulo de áudio —")
checar(not audio.ligado(), "sem chave do Gemini: desligado (o bot continua dizendo que só lê texto)")
checar(audio.por_que_desligado() == "falta GEMINI_API_KEY", "o log diz o que falta", audio.por_que_desligado())
os.environ.update(GEMINI_API_KEY="chave-teste")
checar(not audio.ligado(), "com chave, mas sem modelo do Gemini: desligado")
os.environ.update(MIZAN_AGENTE_CLIENTE="gemini", MIZAN_MODELO_TRIAGEM="gemini-triagem")
checar(audio.ligado() and audio.modelo() == "gemini-triagem", "agente no Gemini: usa o modelo da Triagem", audio.modelo())
os.environ.pop("MIZAN_MODELO_TRIAGEM")
os.environ["MIZAN_MODELO_NEGOCIADOR"] = "gemini-negociador"
checar(audio.modelo() == "gemini-negociador", "sem modelo da Triagem: usa o do negociador", audio.modelo())
os.environ.pop("MIZAN_MODELO_NEGOCIADOR")
checar(not audio.ligado() and audio.por_que_desligado().startswith("falta o modelo"), "sem nenhum modelo: desligado, e o log diz por quê")
os.environ["MIZAN_MODELO_TRIAGEM"] = "gemini-triagem"
os.environ["MIZAN_AGENTE_CLIENTE"] = "anthropic"
checar(not audio.ligado(), "agente na Anthropic sem modelo de áudio: desligado")
os.environ["MIZAN_MODELO_AUDIO"] = "gemini-audio-teste"
checar(audio.ligado() and audio.modelo() == "gemini-audio-teste", "MIZAN_MODELO_AUDIO vale com qualquer agente")
os.environ["MIZAN_AUDIO"] = "0"
checar(not audio.ligado() and audio.por_que_desligado() == "MIZAN_AUDIO=0", "MIZAN_AUDIO=0 desliga")
os.environ.pop("MIZAN_AUDIO")
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_MODELO_TRIAGEM"):
    os.environ.pop(v)

voz = {"voice": {"file_id": "f1", "duration": 7, "mime_type": "audio/ogg", "file_size": 9000}}
checar(audio.do_telegram(voz) == {"file_id": "f1", "segundos": 7, "bytes": 9000, "mime": "audio/ogg"}, "mensagem de voz")
checar(audio.do_telegram({"voice": {"file_id": "f2"}})["mime"] == "audio/ogg", "voz sem mime: OGG (o formato do Telegram)")
checar(audio.do_telegram({"audio": {"file_id": "f3", "mime_type": "audio/mpeg"}})["mime"] == "audio/mpeg", "arquivo de áudio")
checar(audio.do_telegram({"photo": [{}]}) is None and audio.do_telegram({"voice": {}}) is None, "foto ou voz sem arquivo: não é áudio")
checar(audio.formato("audio/ogg") == "audio/ogg" and audio.formato("audio/mpeg") == "audio/mp3"
       and audio.formato("audio/ogg; codecs=opus") == "audio/ogg", "formatos que o Gemini ouve")
checar(audio.formato("audio/x-m4a") is None and audio.formato("") is None and audio.formato(None) is None, "outros: não")
checar(audio.duracao(200) == "3:20" and audio.duracao(7) == "0:07", "duração para a equipe ler")
checar(audio.veio_de_audio("🎤 aceito") and audio.veio_de_audio("ok\n🎤 aceito") and not audio.veio_de_audio("aceito 🎤"),
       "marca de áudio em qualquer linha (mensagens juntas), só no começo da linha")
checar(audio._limpar('Transcrição: "quero pagar dia 10"') == "quero pagar dia 10", "tira rótulo e aspas")
checar(audio._limpar("[inaudível]") == "" and audio._limpar(" [Inaudível]. ") == "" and audio._limpar("") == "", "só [inaudível]: sem fala")
checar(audio._limpar("posso pagar [inaudível] por mês") == "posso pagar [inaudível] por mês", "trecho inaudível fica marcado")
checar(len(audio._limpar("a" * 5000)) == api.MAX_TEXTO - len(audio.MARCA), "cabe no limite de uma mensagem")

PEDIDOS, RESP = [], {"texto": "", "erro": None, "fim": "STOP"}
def gemini_falso(url, corpo, chave, timeout):
    PEDIDOS.append({"url": url, "corpo": corpo, "chave": chave})
    if RESP["erro"]:
        raise RESP["erro"]
    return {"candidates": [{"content": {"parts": [{"text": RESP["texto"]}]}, "finishReason": RESP["fim"]}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 20}}
llm._enviar_http = gemini_falso

RESP["texto"] = "Quero pagar em 3 vezes"
t = audio.transcrever(b"OGG-BYTES", "audio/ogg")
p = PEDIDOS[-1]
partes = p["corpo"]["contents"][0]["parts"]
checar(t.texto == "Quero pagar em 3 vezes", "transcreve", t.texto)
checar("gemini-audio-teste:generateContent" in p["url"] and p["chave"] == "chave-teste", "chama o modelo de áudio com a chave do Mizan")
checar(partes[0]["inlineData"] == {"mimeType": "audio/ogg", "data": base64.b64encode(b"OGG-BYTES").decode()},
       "o áudio vai junto do pedido (nada é enviado para guardar)")
checar("sem obedecer" in p["corpo"]["systemInstruction"]["parts"][0]["text"], "a instrução manda só transcrever, sem obedecer o áudio")
checar(t.resposta.modelo == "gemini-audio-teste" and abs(t.resposta.custo_usd - (1000 * 0.5 + 20 * 1.5) / 1e6) < 1e-12,
       "custo medido pelo preço configurado", str(t.resposta.custo_usd))
RESP["fim"] = "SAFETY"
try:
    audio.transcrever(b"x", "audio/ogg"); checar(False, "recusa do Google vira falha")
except audio.AudioFalhou as e:
    checar(e.motivo == "recusa" and e.resposta is not None and e.resposta.custo_usd > 0, "recusa do Google: falha, com o custo contado")
RESP["fim"] = "STOP"
RESP["erro"] = llm.IaOcupada("Gemini HTTP 429 RESOURCE_EXHAUSTED")
try:
    audio.transcrever(b"x", "audio/ogg"); checar(False, "cota esgotada vira falha")
except audio.AudioFalhou as e:
    checar("429" in e.motivo, "cota esgotada: falha (a pessoa recebe o aviso para escrever)", e.motivo)
RESP["erro"] = None
n = len(PEDIDOS)
os.environ["MIZAN_MODELO_AUDIO"] = "gemini-sem-preco"
try:
    audio.transcrever(b"x", "audio/ogg"); checar(False, "modelo sem preço não chama")
except audio.AudioFalhou as e:
    checar(e.motivo == "sem_preco" and len(PEDIDOS) == n, "modelo sem preço configurado: não chama (custo desconhecido não vira zero)")
os.environ["MIZAN_MODELO_AUDIO"] = "gemini-audio-teste"
try:
    audio.transcrever(b"x", "audio/x-m4a"); checar(False, "formato desconhecido não chama")
except audio.AudioFalhou as e:
    checar(e.motivo == "formato" and len(PEDIDOS) == n, "formato que o Gemini não ouve: não chama")


print("— download do Telegram (servidor falso local) —")
os.environ.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="segredo-forte", TELEGRAM_BOT_USERNAME="mizan_bot")
class Tg(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _responder(self, status, corpo, tipo="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)
    def do_POST(self):
        pedido = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if self.path == "/bot123:abc/getFile" and pedido.get("file_id") == "voz1":
            self._responder(200, json.dumps({"ok": True, "result": {"file_path": "voice/file_1.oga"}}).encode())
        else:
            self._responder(400, b'{"ok":false}')
    def do_GET(self):
        if self.path == "/file/bot123:abc/voice/file_1.oga":
            self._responder(200, b"A" * 1000, "audio/ogg")
        else:
            self._responder(404, b"")
    def log_message(self, *a):
        pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Tg)
threading.Thread(target=srv.serve_forever, daemon=True).start()
API_REAL, canal_telegram.API = canal_telegram.API, f"http://127.0.0.1:{srv.server_port}"
saida = io.StringIO()
with contextlib.redirect_stdout(saida):
    baixado = canal_telegram._baixar_arquivo("voz1", 5000)
    grande = canal_telegram._baixar_arquivo("voz1", 500)
    errado = canal_telegram._baixar_arquivo("outro", 5000)
checar(baixado == b"A" * 1000, "baixa o áudio só na memória (getFile e download)")
checar(grande is None, "arquivo maior que o limite: não baixa")
checar(errado is None and "getFile recusado: HTTP 400" in saida.getvalue(), "arquivo que não existe: nada", saida.getvalue().strip())
checar("123:abc" not in saida.getvalue(), "o token do bot nunca vai para o log")
canal_telegram.API = API_REAL
srv.shutdown()


print("— conversa por áudio no Telegram —")
DEV = {"id": "p1", "empresa_id": "goias", "cpf": "123.456.789-00", "nome": "Maria das Dores",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao"}
REPO, FONTE = RepoMemoria(), FonteMemoria([DEV])
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
ROTEIRO, CLIENTES = [], []
api.fabrica_repo = lambda: REPO
api.fabrica_fonte = lambda: FONTE
api.fabrica_cliente = lambda: CLIENTES.append(ClienteFalso(ROTEIRO)) or CLIENTES[-1]
ENVIADOS, BAIXADOS, BAIXAR = [], [], {"dados": b"OGG-BYTES"}
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
canal_telegram.apagar_mensagem = lambda chat, mid: True
canal_telegram.enviar_acao = lambda chat, acao="typing": True
canal_telegram.baixar_arquivo = lambda fid, mx: BAIXADOS.append(fid) or BAIXAR["dados"]

main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
ADM = {"Authorization": "Bearer " + criar_token({"sub": "adm", "email": "adm@x", "nome": "Adm", "role": "admin", "empresa_id": "goias"})}
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})
def msg(uid, **campos):
    return {"update_id": uid, "message": {"chat": {"id": 555, "type": "private"}, "from": {"is_bot": False}, **campos}}
def voz(uid, segundos=8, mime="audio/ogg", tipo="voice", tamanho=12000):
    return msg(uid, **{tipo: {"file_id": f"arq{uid}", "duration": segundos, "mime_type": mime, "file_size": tamanho}})
def receber(update, agora=None):
    return canal_telegram.receber(update, repo=REPO, agora=agora)
def ultima_entrada():
    caso = REPO.caso_de("goias", "p1")
    return [m["texto"] for m in REPO.ultimas_mensagens("goias", caso["id"], 50) if m["direcao"] == "entrada"][-1]
def passos_audio():
    return [p for p in REPO.passos if p["no"] == "transcrever_audio"]

codigo = c.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"]
receber(msg(1, text="/start " + codigo))
checar(REPO.caso_por_telegram(555) is not None, "chat ligado ao caso")

ENVIADOS.clear()
ROTEIRO[:] = [tri("pagar_negociar"), Resposta(ferramentas=[{"nome": "verificar_identidade", "args": {"tres_primeiros_digitos_cpf": "123"}}]),
              Resposta(texto="Obrigado, Maria. Quanto você consegue pagar por mês?")]
RESP["texto"] = "Quero negociar, meu CPF começa com 123"
r = receber(voz(10))
checar(r["acao"] == "mensagem", "áudio vira mensagem", str(r))
checar(BAIXADOS == ["arq10"], "baixou o áudio uma vez")
checar(ultima_entrada() == "🎤 Quero negociar, meu CPF começa com 123", "o caso guarda só a transcrição, com a marca 🎤", ultima_entrada())
checar(any("Quanto você consegue pagar" in t for _, t in ENVIADOS), "o agente responde por texto no Telegram", str(ENVIADOS)[:120])
checar(REPO.caso_de("goias", "p1")["dados"].get("identidade_ok") is True, "o áudio passou pelo mesmo caminho do texto (identidade confirmada)")
cli = CLIENTES[-1]
neg = [ch for ch in cli.chamadas if ch["papel"] == "negociador"]
checar(any("🎤 Quero negociar" in json.dumps(ch["mensagens"], ensure_ascii=False) for ch in cli.chamadas if ch["papel"] == "triagem"),
       "a Triagem leu a transcrição")
checar(neg and "🎤 é um áudio" in neg[0]["sistema"], "o negociador sabe que 🎤 é áudio transcrito")
pa = passos_audio()
checar(len(pa) == 1 and pa[0]["resultado"] == "ok" and pa[0]["modelo"] == "gemini-audio-teste" and pa[0]["custo_usd"] > 0
       and pa[0]["versao_prompt"] == "audio-v1", "a transcrição aparece no rastreio, com custo (entra no teto do dia)", str(pa)[:200])
checar(pa[0]["detalhe"] == {"segundos": 8}, "o rastreio leva só a duração, nunca o que foi dito", str(pa[0]["detalhe"]))
checar("OGG-BYTES" not in json.dumps(REPO.caso_de("goias", "p1"), default=str) and
       not any("OGG" in json.dumps(p, default=str) for p in REPO.passos), "o áudio não fica guardado no caso nem no rastreio")

n = len(BAIXADOS)
r = receber(voz(10))
checar(r["acao"] == "repetido" and len(BAIXADOS) == n, "o mesmo áudio reenviado pelo Telegram não é transcrito de novo", str(r))

ENVIADOS.clear()
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Posso explicar sim.")]
RESP["texto"] = "Como funciona o parcelamento?"
r = receber(voz(11, tipo="audio", mime="audio/mpeg"))
checar(r["acao"] == "mensagem" and PEDIDOS[-1]["corpo"]["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "audio/mp3",
       "arquivo de áudio em MP3 também", str(r))

print("— quando não dá para ouvir —")
def sem_rodada(update, acao, aviso, nota, baixa=False, agora=None):
    ENVIADOS.clear()
    n_cli, n_baixa = len(CLIENTES), len(BAIXADOS)
    r = receber(update, agora)
    checar(r["acao"] == acao, f"{acao}: ação", str(r))
    checar(ENVIADOS == ([("555", aviso)] if aviso else []), f"{acao}: a pessoa sabe o que fazer", str(ENVIADOS))
    if nota is not None:
        checar(ultima_entrada() == nota, f"{acao}: a equipe vê no caso que chegou um áudio", ultima_entrada())
    checar(len(CLIENTES) == n_cli, f"{acao}: nenhuma rodada do agente")
    checar((len(BAIXADOS) > n_baixa) == baixa, f"{acao}: {'baixou' if baixa else 'nem baixou'} o áudio")

RESP["texto"] = "[inaudível]"
receber(voz(19))
ENVIADOS.clear()
n = len(BAIXADOS)
r = receber(voz(19))
checar(r["acao"] == "repetido" and len(BAIXADOS) == n and ENVIADOS == [],
       "áudio que falhou, reenviado pelo Telegram: não baixa nem avisa de novo", str(r))
sem_rodada(voz(20, segundos=200), "audio_longo", canal_telegram.MSG_AUDIO_LONGO.format(limite="2 minutos"),
           "🎤 [áudio de 3:20 longo demais, não transcrito]")
sem_rodada(voz(21, segundos=30, tamanho=audio.MAX_BYTES + 1), "audio_longo", canal_telegram.MSG_AUDIO_LONGO.format(limite="2 minutos"),
           "🎤 [áudio de 0:30 longo demais, não transcrito]")
os.environ["MIZAN_AUDIO_MAX_S"] = "90"
sem_rodada(voz(22, segundos=100), "audio_longo", canal_telegram.MSG_AUDIO_LONGO.format(limite="90 segundos"),
           "🎤 [áudio de 1:40 longo demais, não transcrito]")
os.environ.pop("MIZAN_AUDIO_MAX_S")
sem_rodada(voz(23, tipo="audio", mime="audio/x-m4a"), "audio_formato", canal_telegram.MSG_AUDIO_FORMATO,
           "🎤 [áudio de 0:08 em formato que não abre]")
RESP["texto"] = "[inaudível]"
sem_rodada(voz(24), "audio_vazio", canal_telegram.MSG_AUDIO_VAZIO, "🎤 [áudio de 0:08 sem fala que deu para entender]", baixa=True)
RESP["erro"] = llm.IaOcupada("Gemini HTTP 429 RESOURCE_EXHAUSTED")
sem_rodada(voz(25), "audio_falhou", canal_telegram.MSG_AUDIO_FALHOU, "🎤 [áudio de 0:08 não transcrito]", baixa=True)
checar(passos_audio()[-1]["resultado"] == "erro" and "429" in passos_audio()[-1]["detalhe"]["motivo"],
       "a falha fica no rastreio, com o motivo técnico", str(passos_audio()[-1]["detalhe"]))
RESP["erro"] = KeyError("candidates")
sem_rodada(voz(31), "audio_falhou", canal_telegram.MSG_AUDIO_FALHOU, "🎤 [áudio de 0:08 não transcrito]", baixa=True)
checar(passos_audio()[-1]["detalhe"]["motivo"] == "KeyError", "resposta fora do esperado: a pessoa recebe o aviso (não fica sem retorno)")
RESP["erro"] = None
BAIXAR["dados"] = None
sem_rodada(voz(26), "audio_falhou", canal_telegram.MSG_AUDIO_FALHOU, "🎤 [áudio de 0:08 não transcrito]", baixa=True)
BAIXAR["dados"] = b"OGG-BYTES"
os.environ["MIZAN_AGENTE_TETO_DIA_USD"] = "0.000001"
sem_rodada(voz(27), "audio_teto", canal_telegram.MSG_AUDIO_FALHOU, "🎤 [áudio de 0:08 não transcrito]")
os.environ.pop("MIZAN_AGENTE_TETO_DIA_USD")

feitos = REPO.caso_de("goias", "p1")["dados"]["telegram"]["audios"]["n"]
os.environ["MIZAN_AUDIO_POR_DIA"] = str(feitos)
sem_rodada(voz(28), "audio_limite", canal_telegram.MSG_AUDIO_LIMITE, None)
sem_rodada(voz(29), "audio_limite", None, None)
amanha = datetime.now(timezone.utc) + timedelta(days=1)
ROTEIRO[:] = [tri("duvida"), Resposta(texto="Certo.")]
RESP["texto"] = "Tudo bem"
checar(receber(voz(30), agora=amanha)["acao"] == "mensagem", "no dia seguinte, o limite volta a zero")
os.environ.pop("MIZAN_AUDIO_POR_DIA")

ENVIADOS.clear()
receber(msg(40, photo=[{}]), agora=amanha + timedelta(hours=1))
checar(ENVIADOS == [("555", canal_telegram.MSG_SO_TEXTO_E_AUDIO)], "foto: avisa que lê texto e ouve áudio", str(ENVIADOS))
os.environ["MIZAN_AUDIO"] = "0"
ENVIADOS.clear()
n = len(BAIXADOS)
log = io.StringIO()
with contextlib.redirect_stdout(log):
    r = receber(voz(41), agora=amanha + timedelta(hours=2))
checar("transcrição desligada: MIZAN_AUDIO=0" in log.getvalue(), "o log do Render diz por que o áudio não foi ouvido", log.getvalue().strip())
checar(r["acao"] == "midia" and ENVIADOS == [("555", canal_telegram.MSG_SO_TEXTO)] and len(BAIXADOS) == n,
       "áudio desligado: volta o aviso de que só lê texto", str(ENVIADOS))
os.environ.pop("MIZAN_AUDIO")


print("— aceite de acordo por áudio —")
def aceite(texto_devedor, ofertas):
    dt = datetime.now(timezone.utc)
    msgs = [{"direcao": "saida", "texto": t, "criado_em": dt + timedelta(seconds=i + 1)} for i, t in enumerate(ofertas)]
    ctx = SimpleNamespace(caso={"id": "1", "empresa_id": "a", "dados": {}}, saida={"texto": texto_devedor},
                          repo=SimpleNamespace(ultimas_mensagens=lambda *a: msgs),
                          consultar_juridico=lambda acao, fatos: {"decisao": "prosseguir"})
    sim = {"condicoes": {"n_parcelas": 12, "desconto_pct": 0}, "conta": {"total_pago": 1200, "parcela": 100, "entrada": 0},
           "criada_em": dt.isoformat()}
    return ferramentas._conferir_aceite(ctx, None, sim, "2026-11-10")
b = aceite("🎤 Aceito", [])
checar(b and b["bloqueado"] and "por áudio" in b["motivo"] and "R$ 1.200,00" in b["motivo"] and "12x de R$ 100,00" in b["motivo"],
       "aceite por áudio sem a conta escrita antes: não registra e pede para escrever a conta", str(b))
checar(aceite("ok\n🎤 Aceito", []) is not None, "também quando o áudio veio junto com outra mensagem")
checar(aceite("Aceito", []) is None, "aceite escrito segue a regra de antes")
checar(aceite("🎤 Aceito", ["Total R$ 1.200,00 em 12 parcelas de R$ 100,00."]) is None,
       "aceite por áudio depois da conta escrita: registra")

print(f"\n{'TUDO OK' if not falhas else f'{falhas} FALHA(S)'}")
sys.exit(1 if falhas else 0)
