"""Canal Telegram: envio com conexão reaproveitada, contra uma API falsa local (sem rede).

    python test_telegram_conexao.py
"""
import json, os, sys, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CONEXOES, PEDIDOS = set(), []


class ApiFalsa(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"                    # mantém a conexão aberta, como a API de verdade

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        corpo = json.loads(self.rfile.read(n))
        CONEXOES.add(self.client_address[1])
        PEDIDOS.append((self.path.rsplit("/", 1)[-1], corpo))
        st = 403 if corpo.get("chat_id") == 403 else 200
        b = json.dumps({"ok": st == 200}).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), ApiFalsa)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["TELEGRAM_BOT_TOKEN"] = "1:abc"
from agente import canal_telegram as tg                     # noqa: E402
tg.API = f"http://127.0.0.1:{srv.server_address[1]}"

r = [tg.enviar_texto(5, f"msg {i}") for i in range(5)]
checar(all(x is True for x in r) and len(CONEXOES) == 1, "5 envios seguidos usam uma conexão só", f"{len(CONEXOES)} conexões")
checar(tg.enviar_texto(403, "oi") == tg.BLOQUEADO, "403 continua sendo 'o devedor bloqueou o bot'")
checar(tg.enviar_texto(5, "x" * 9000) is True and len([p for p in PEDIDOS if p[1].get("text", "").startswith("x")]) == 3,
       "texto longo vai em partes de até 4096")
for c, _ in list(tg._POOL):                                  # o servidor fecha as conexões paradas
    c.sock.close()
checar(tg.enviar_texto(5, "depois de cair") is True and PEDIDOS[-1][1]["text"] == "depois de cair",
       "conexão guardada caiu: reconecta sozinho e entrega (uma vez só)",
       str(sum(1 for p in PEDIDOS if p[1].get("text") == "depois de cair")))
tg.enviar_acao(5)
tg.apagar_mensagem(5, 99)
tg._ACOES.join()
checar(PEDIDOS[-2][0] == "sendChatAction" and PEDIDOS[-1] == ("deleteMessage", {"chat_id": 5, "message_id": 99}),
       "\"digitando…\" e apagar o /start vão em segundo plano")
srv.shutdown()
for c, _ in tg._POOL:
    c.close()
tg._POOL.clear()
tg.API = "http://127.0.0.1:9"
checar(tg.enviar_texto(5, "sem rede") is False, "rede fora do ar: devolve False, sem erro")

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
