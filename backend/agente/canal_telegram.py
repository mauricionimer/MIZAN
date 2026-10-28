"""Canal Telegram: o devedor conversa com o agente do Mizan pelo Telegram.

O agente não muda: o Telegram é só uma porta, como a tela de demonstração. A
mensagem que chega vira o mesmo evento `mensagem_devedor` da fila, e o que o
agente escreve (já passado pelo Auditor e pelas travas de saída) é entregue de
volta no mesmo chat. Lembretes e mensagens do Acompanhamento seguem pelo mesmo caminho.

Como o chat é ligado a um devedor
  1. A equipe gera um convite do caso (`gerar_convite`): um link t.me/<bot>?start=<código>.
     O código leva o id do caso e um segredo aleatório; no caso fica só o hash do
     segredo e a validade (7 dias). Vale uma vez.
  2. O devedor abre o link e toca em Iniciar: o Telegram manda `/start <código>`,
     e o chat_id fica gravado no caso. Um chat fica ligado a um caso só (ligar
     de novo desliga o anterior: útil na demonstração).
  3. Ligar o chat NÃO prova quem a pessoa é. A confirmação de identidade
     continua sendo do agente (primeiros dígitos do CPF), antes de qualquer valor.

Segurança
  - O webhook só aceita chamadas com o cabeçalho `X-Telegram-Bot-Api-Secret-Token`
    igual a TELEGRAM_WEBHOOK_SECRET (comparação em tempo constante). Sem a variável, recusa.
  - O token do bot (TELEGRAM_BOT_TOKEN) nunca vai para log, rastreio nem resposta.
  - Só conversa privada com texto; grupos, bots, fotos e áudios são ignorados.
  - Cada update do Telegram tem chave própria (`telegram:<update_id>`): reenvio não duplica.
  - O que vai ao Telegram é texto puro, sem formatação.
"""
import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

API = "https://api.telegram.org"
VALIDADE_CONVITE = timedelta(days=7)
MAX_TEXTO_TELEGRAM = 4096
MAX_ENTREGUES = 60
TIMEOUT_S = 8

MSG_BOAS_VINDAS = ("Olá! Este é o assistente virtual de negociação. Você pode escrever aqui. Por segurança, vou "
                   "confirmar quem você é antes de falar de valores. Para começar, escreva \"oi\".")
MSG_SEM_VINCULO = ("Para falar com o assistente, abra o link que o banco enviou para você. "
                   "Se não recebeu, peça um novo convite à equipe.")
MSG_CONVITE_INVALIDO = "Esse convite não é mais válido. Peça um novo link à equipe."


def configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip())


def segredo_confere(recebido: str | None) -> bool:
    esperado = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    return bool(esperado) and hmac.compare_digest(str(recebido or ""), esperado)


# ── envio ────────────────────────────────────────────────────────────────────

def _enviar_texto(chat_id, texto: str) -> bool:
    """sendMessage na API do Telegram. Nunca levanta erro: devolve se entregou."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    ok = True
    for i in range(0, len(texto), MAX_TEXTO_TELEGRAM):
        corpo = json.dumps({"chat_id": chat_id, "text": texto[i:i + MAX_TEXTO_TELEGRAM],
                            "disable_web_page_preview": True}).encode("utf-8")
        req = urllib.request.Request(f"{API}/bot{token}/sendMessage", data=corpo,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                ok = ok and r.status == 200
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"[Telegram] envio falhou: {type(e).__name__}")        # nunca imprime a URL: ela leva o token
            return False
    return ok


enviar_texto = _enviar_texto        # os testes trocam este nome


# ── convite e vínculo ────────────────────────────────────────────────────────

def _hash(segredo: str) -> str:
    return hashlib.sha256(segredo.encode("utf-8")).hexdigest()


def gerar_convite(repo, caso: dict, agora: datetime | None = None) -> dict:
    """Gera (ou renova) o convite do caso. Devolve {link, codigo, expira_em, configurado}."""
    agora = agora or datetime.now(timezone.utc)
    segredo = secrets.token_urlsafe(9)
    expira = agora + VALIDADE_CONVITE
    dados = dict(caso.get("dados") or {})
    tg = dict(dados.get("telegram") or {})
    tg.update({"convite_hash": _hash(segredo), "convite_expira": expira.isoformat()})
    dados["telegram"] = tg
    repo.salvar_caso(caso["id"], {"dados": dados})
    codigo = caso["id"].replace("-", "") + segredo
    bot = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    return {"codigo": codigo, "expira_em": expira.isoformat(), "configurado": configurado() and bool(bot),
            "link": f"https://t.me/{bot}?start={codigo}" if bot else None,
            "vinculado": bool(tg.get("chat_id"))}


def _ler_codigo(codigo: str) -> tuple:
    """(caso_id, segredo) ou (None, None). O id do caso são os 32 primeiros caracteres."""
    codigo = (codigo or "").strip()
    if len(codigo) <= 32:
        return None, None
    try:
        return str(uuid.UUID(codigo[:32])), codigo[32:]
    except ValueError:
        return None, None


def vincular(repo, codigo: str, chat_id, agora: datetime | None = None) -> dict | None:
    """Liga o chat ao caso do convite. Devolve o caso, ou None se o convite não vale."""
    agora = agora or datetime.now(timezone.utc)
    caso_id, segredo = _ler_codigo(codigo)
    if not caso_id:
        return None
    caso = repo.obter_caso(caso_id)
    tg = ((caso or {}).get("dados") or {}).get("telegram") or {}
    if not caso or not tg.get("convite_hash") or not hmac.compare_digest(tg["convite_hash"], _hash(segredo)):
        return None
    try:
        if agora > datetime.fromisoformat(tg["convite_expira"]):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    anterior = repo.caso_por_telegram(chat_id)
    if anterior and anterior["id"] != caso["id"]:
        dados_a = dict(anterior.get("dados") or {})
        dados_a["telegram"] = {k: v for k, v in (dados_a.get("telegram") or {}).items() if k != "chat_id"}
        repo.salvar_caso(anterior["id"], {"dados": dados_a})
    dados = dict(caso.get("dados") or {})
    dados["telegram"] = {"chat_id": str(chat_id), "vinculado_em": agora.isoformat(), "entregues": []}   # convite gasto
    repo.salvar_caso(caso["id"], {"dados": dados})
    caso["dados"] = dados
    return caso


# ── entrega das respostas ───────────────────────────────────────────────────

def entregar(ctx) -> int:
    """Manda ao Telegram o que o agente escreveu nesta rodada. Devolve quantas entregou.

    Chamado pelo orquestrador no fim de cada rodada; sem vínculo ou sem
    configuração, não faz nada. Falha de rede nunca derruba o atendimento: a
    mensagem continua registrada no caso e a próxima rodada tenta de novo.
    """
    tg = (ctx.caso.get("dados") or {}).get("telegram") or {}
    chat_id = tg.get("chat_id")
    if not chat_id or not configurado():
        return 0
    trace = ctx.rastreio.trace_id
    entregues = list(tg.get("entregues") or [])
    n = 0
    novas = [m for m in ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 20)
             if m.get("direcao") == "saida" and m.get("trace_id") == trace]
    for i, m in enumerate(novas):
        chave = f"{trace}:{i}"
        if chave in entregues:
            continue
        if enviar_texto(chat_id, m["texto"]):
            entregues.append(chave)
            n += 1
        else:
            break
    dados = dict(ctx.caso.get("dados") or {})
    dados["telegram"] = {**tg, "entregues": entregues[-MAX_ENTREGUES:]}
    ctx.caso["dados"] = dados
    return n


def enviar_para_caso(caso: dict, texto: str) -> bool:
    """Manda um texto ao chat ligado ao caso (usado quando uma pessoa responde). False se não há chat ou falhou."""
    chat_id = ((caso.get("dados") or {}).get("telegram") or {}).get("chat_id")
    return bool(chat_id and configurado() and enviar_texto(chat_id, texto))


# ── recebimento (webhook) ───────────────────────────────────────────────────

def receber(update: dict, repo=None, agora: datetime | None = None, processar=True) -> dict:
    """Trata um update do Telegram. Devolve {"acao": ...} (usado nos testes e no log)."""
    from agente import api, orquestrador as orq
    msg = (update or {}).get("message") or {}
    chat, texto = msg.get("chat") or {}, (msg.get("text") or "").strip()
    if chat.get("type") != "private" or (msg.get("from") or {}).get("is_bot") or not texto or chat.get("id") is None:
        return {"acao": "ignorado"}
    chat_id = chat["id"]
    repo = repo or api.fabrica_repo()
    agora = agora or datetime.now(timezone.utc)

    if texto.startswith("/start"):
        partes = texto.split(maxsplit=1)
        caso = vincular(repo, partes[1], chat_id, agora) if len(partes) == 2 else None
        if caso:
            enviar_texto(chat_id, MSG_BOAS_VINDAS)
            return {"acao": "vinculado", "caso_id": caso["id"]}
        enviar_texto(chat_id, MSG_CONVITE_INVALIDO if len(partes) == 2 else MSG_SEM_VINCULO)
        return {"acao": "convite_invalido" if len(partes) == 2 else "sem_vinculo"}

    caso = repo.caso_por_telegram(chat_id)
    if not caso:
        enviar_texto(chat_id, MSG_SEM_VINCULO)
        return {"acao": "sem_vinculo"}
    if not api.ligado():
        return {"acao": "agente_desligado"}
    texto = texto[:api.MAX_TEXTO]
    ev, novo = orq.registrar_evento(repo, caso["empresa_id"], caso["id"], "mensagem_devedor",
                                    f"telegram:{update.get('update_id', uuid.uuid4().hex)}",
                                    {"texto": texto}, origem="telegram")
    if novo and processar:
        fonte = api.fabrica_fonte()
        orq.processar_fila(repo, api.grafos(fonte), api.fabrica_cliente(), limite=5, agora=agora,
                           empresa_id=caso["empresa_id"])
    return {"acao": "mensagem" if novo else "repetido", "caso_id": caso["id"]}
