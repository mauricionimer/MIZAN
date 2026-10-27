"""Liga (ou desliga) o bot do Telegram ao servidor do Mizan.

    python telegram_webhook.py ligar https://SEU-SERVIDOR.onrender.com
    python telegram_webhook.py desligar
    python telegram_webhook.py status

Lê TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_SECRET do ambiente (ou do .env). O Telegram
passa a chamar POST /canal/telegram/webhook com o segredo no cabeçalho
X-Telegram-Bot-Api-Secret-Token. Precisa de internet; rode no seu computador.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def chamar(metodo: str, **params) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Defina TELEGRAM_BOT_TOKEN (o token que o @BotFather entregou).")
    dados = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/{metodo}", data=dados), timeout=15) as r:
        return json.loads(r.read())


def main(argv: list) -> None:
    acao = argv[1] if len(argv) > 1 else "status"
    if acao == "ligar":
        if len(argv) < 3 or not argv[2].startswith("https://"):
            sys.exit("Uso: python telegram_webhook.py ligar https://SEU-SERVIDOR")
        segredo = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        if len(segredo) < 16:
            sys.exit("Defina TELEGRAM_WEBHOOK_SECRET com pelo menos 16 caracteres (letras, números, _ e -).")
        print(chamar("setWebhook", url=argv[2].rstrip("/") + "/canal/telegram/webhook", secret_token=segredo,
                     allowed_updates=json.dumps(["message"]), drop_pending_updates="true"))
    elif acao == "desligar":
        print(chamar("deleteWebhook"))
    else:
        info = chamar("getWebhookInfo").get("result", {})
        print({k: info.get(k) for k in ("url", "pending_update_count", "last_error_date", "last_error_message")})


if __name__ == "__main__":
    main(sys.argv)
