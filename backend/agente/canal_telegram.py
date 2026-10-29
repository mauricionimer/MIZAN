"""Canal Telegram: o devedor conversa com o agente do Mizan pelo Telegram.

O agente não muda: o Telegram é só uma porta, como a tela de demonstração. A
mensagem que chega vira o mesmo evento `mensagem_devedor` da fila, e o que o
agente escreve (já passado pelo Auditor e pelas travas de saída) é entregue de
volta no mesmo chat. Lembretes e mensagens do Acompanhamento seguem pelo mesmo caminho.

Como o chat é ligado a um devedor
  1. A equipe gera um convite do caso (`gerar_convite`): um link t.me/<bot>?start=<código>.
     O código leva o id do caso e um segredo aleatório; no caso fica só o hash do
     segredo e a validade (7 dias). Vale para UM Telegram: cada pessoa precisa do próprio link.
  2. O devedor abre o link e toca em Iniciar: o Telegram manda `/start <código>`,
     e o chat_id fica gravado no caso. Um chat fica ligado a um caso só (ligar
     de novo desliga o anterior: útil na demonstração).
  3. Ligar o chat NÃO prova quem a pessoa é. A confirmação de identidade
     continua sendo do agente (primeiros dígitos do CPF), antes de qualquer valor.

O que pode dar errado no vínculo, e o que a pessoa ouve (ver `vincular`)
  - a mesma pessoa abre o mesmo link de novo .......... "você já está conectado"
  - outra pessoa abre um link já usado ................. "este link já foi usado em outro Telegram"
                                                          (e a equipe vê o aviso no caso)
  - a equipe gerou um link mais novo ................... "este link foi substituído"
  - venceu (7 dias) .................................... "este link venceu"
  - código adulterado ou incompleto .................... "não reconheci este link"

Entrega
  - O que o agente escreve numa rodada vai ao chat no fim da rodada (`entregar`).
    Falhou a rede: tenta de novo na próxima rodada, por até `JANELA_REENVIO`.
  - Mensagens da pessoa da equipe e avisos do sistema vão na hora (`enviar_para_caso`).
  - O devedor bloqueou o bot (Telegram responde 403): o caso fica marcado e
    não se tenta mais até ele voltar a escrever.

Segurança
  - O webhook só aceita chamadas com o cabeçalho `X-Telegram-Bot-Api-Secret-Token`
    igual a TELEGRAM_WEBHOOK_SECRET (comparação em tempo constante). Sem a variável, recusa.
  - O token do bot (TELEGRAM_BOT_TOKEN) nunca vai para log, rastreio nem resposta.
  - Só conversa privada; grupos e bots são ignorados. Foto, áudio e afins recebem
    um aviso de que só lemos texto.
  - Cada update do Telegram tem chave própria (`telegram:<update_id>`): reenvio não duplica.
  - O que vai ao Telegram é texto puro, sem formatação.
  - Cada conversa dispara no máximo MIZAN_IA_RODADAS_CASO rodadas de IA (padrão 30,
    acima do ritmo de uma conversa de verdade; mensagens seguidas contam como uma)
    a cada MIZAN_IA_JANELA_CASO_MIN minutos (padrão 10). O teto de gasto é por
    empresa e por dia: sem este, um devedor (ou quem tivesse o link dele) mandando
    500 mensagens esgotava a IA de todos os outros devedores da empresa. Passado o
    limite, as mensagens não se perdem: juntam-se num único evento adiado para o
    fim da janela, e UMA rodada responde a todas (ver `_adiar_se_passou_do_limite`).
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

API = "https://api.telegram.org"
VALIDADE_CONVITE = timedelta(days=7)
MAX_TEXTO_TELEGRAM = 4096
MAX_ENTREGUES = 60
MAX_HASHES = 5
TIMEOUT_S = 8
JANELA_REENVIO = timedelta(minutes=15)   # mensagem do agente que falhou: tenta de novo nas rodadas seguintes
ESPERA_CASO_S = 150                      # o webhook acompanha a resposta até isto (caso ocupado, IA ocupada)
RETOMAR_ATE_S = 90                       # IA ocupada: se a nova tentativa sai em até isto, espera e tenta (como a tela)
DIGITANDO_S = 4                          # "digitando…" some em ~5 s no Telegram: renova enquanto o agente responde
INTERVALO_AVISO = {"pausa": timedelta(minutes=30), "so_texto": timedelta(minutes=10)}
BLOQUEADO = "bloqueado"                  # o devedor bloqueou o bot (403)
MARCAS_DIRETAS = ("pessoa", "aviso")    # trace_id de mensagens que vão na hora, fora das rodadas do agente

# Ao ligar, quem fala primeiro é o próprio agente, com a mesma abertura da conversa pelo Mizan
# (ver `abrir_conversa`). Esta linha só vale para casos em que o agente não conversa
# (com a equipe, suspenso, contestado, quitado).
MSG_CONECTADO = "Olá{nome}! Você está conectado ao atendimento de {empresa}. Pode escrever por aqui."
MSG_CONECTADO_EQUIPE = " Uma pessoa da equipe vai te responder."
MSG_JA_LIGADO = "Você já está conectado. Pode escrever sua mensagem aqui."
MSG_SEM_VINCULO = ("Para falar com o assistente, abra o link que o banco enviou para você. "
                   "Se não recebeu, peça um novo convite à equipe.")
MSG_CONVITE = {
    "usado": ("Este link já foi usado em outro Telegram. Cada pessoa precisa do próprio link: "
              "peça um novo à equipe."),
    "substituido": "Este link foi substituído por um mais novo. Use o link mais recente que a equipe enviou.",
    "vencido": "Este link venceu. Peça um novo à equipe.",
    "invalido": "Não reconheci este link. Confira se copiou o link inteiro ou peça um novo à equipe.",
}
MSG_CONVITE_INVALIDO = MSG_CONVITE["invalido"]
MSG_PAUSADO = ("Recebemos sua mensagem. O atendimento automático está pausado agora; "
               "uma pessoa da equipe vai responder por aqui.")
MSG_SO_TEXTO = "Por enquanto eu só consigo ler mensagens de texto. Pode escrever o que precisa?"
MSG_ESPERA = "Recebi suas mensagens, já te respondo."
AVISO_ASSUMIU = "A partir de agora, uma pessoa da equipe vai continuar o seu atendimento por aqui."
AVISO_DEVOLVEU = "O assistente virtual voltou a acompanhar o seu atendimento. Pode escrever quando quiser."

_MIDIA = ("photo", "voice", "audio", "video", "video_note", "document", "sticker", "animation", "location", "contact")


def configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip())


def segredo_confere(recebido: str | None) -> bool:
    esperado = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    return bool(esperado) and hmac.compare_digest(str(recebido or ""), esperado)


def _agora(agora=None) -> datetime:
    return agora or datetime.now(timezone.utc)


def _quando(valor) -> datetime | None:
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ── envio ────────────────────────────────────────────────────────────────────

def _enviar_texto(chat_id, texto: str):
    """sendMessage na API do Telegram. Nunca levanta erro.

    Devolve True (entregou), False (falhou; dá para tentar de novo) ou BLOQUEADO
    (o Telegram recusou com 403: o devedor bloqueou o bot ou apagou a conta).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    for i in range(0, len(texto), MAX_TEXTO_TELEGRAM):
        corpo = json.dumps({"chat_id": chat_id, "text": texto[i:i + MAX_TEXTO_TELEGRAM],
                            "disable_web_page_preview": True}).encode("utf-8")
        req = urllib.request.Request(f"{API}/bot{token}/sendMessage", data=corpo,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                if r.status != 200:
                    return False
        except urllib.error.HTTPError as e:
            print(f"[Telegram] envio recusado: HTTP {e.code}")         # nunca imprime a URL: ela leva o token
            return BLOQUEADO if e.code == 403 else False
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"[Telegram] envio falhou: {type(e).__name__}")
            return False
    return True


enviar_texto = _enviar_texto        # os testes trocam este nome


def _enviar_acao(chat_id, acao: str = "typing") -> bool:
    """Mostra "digitando…" no chat (dura uns 5 s). Só para o devedor ver que o agente recebeu."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False
    req = urllib.request.Request(f"{API}/bot{token}/sendChatAction",
                                 data=json.dumps({"chat_id": chat_id, "action": acao}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


enviar_acao = _enviar_acao          # os testes trocam este nome


def _apagar_mensagem(chat_id, message_id) -> bool:
    """Apaga uma mensagem que o devedor mandou (o bot pode, em conversa privada). Nunca levanta erro."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or message_id is None:
        return False
    req = urllib.request.Request(f"{API}/bot{token}/deleteMessage",
                                 data=json.dumps({"chat_id": chat_id, "message_id": message_id}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


apagar_mensagem = _apagar_mensagem  # os testes trocam este nome


# ── estado do Telegram no caso ──────────────────────────────────────────────

def _tg(caso: dict | None) -> dict:
    return dict(((caso or {}).get("dados") or {}).get("telegram") or {})


_ALTERADO: dict = {}                    # caso_id -> quando o webhook gravou o Telegram dele (neste processo)


def alterado_desde(caso_id, marca: float) -> bool:
    """O Telegram deste caso mudou depois de `marca` (time.monotonic)?"""
    return _ALTERADO.get(str(caso_id), 0.0) >= marca


def _gravar_tg(repo, caso: dict, tg: dict, **outros) -> None:
    """Grava o estado do Telegram (e notas novas do caderno) sobre a versão mais recente do caso.

    `outros` são campos de `dados` que mudam junto (ex.: identidade_ok, conversa_desde).

    O webhook roda fora da trava do caso: reler antes de gravar evita apagar o que o
    agente acabou de salvar (identidade, acordo...) com uma cópia velha de `dados`.
    """
    atual = (repo.obter_caso(caso["id"]) or {}).get("dados") or {}
    dados = dict(atual)
    dados["telegram"] = tg
    dados.update(outros)
    meu = list((caso.get("dados") or {}).get("caderno") or [])
    novas = [n for n in meu if n not in (atual.get("caderno") or [])]
    if novas:
        from agente import estado
        dados["caderno"] = (list(atual.get("caderno") or []) + novas)[-estado.MAX_CADERNO:]
    caso["dados"] = dados
    _ALTERADO[str(caso["id"])] = time.monotonic()
    repo.salvar_caso(caso["id"], {"dados": dados})
    _ALTERADO[str(caso["id"])] = time.monotonic()


def _hash(segredo: str) -> str:
    return hashlib.sha256(segredo.encode("utf-8")).hexdigest()


def _guardar(lista, valor, n: int = MAX_HASHES) -> list:
    return ([v for v in (lista or []) if v != valor] + [valor])[-n:]


def status(caso: dict | None, agora: datetime | None = None) -> dict:
    """O que a tela mostra sobre o Telegram do caso (sem o chat_id)."""
    tg, agora = _tg(caso), _agora(agora)
    expira = _quando(tg.get("convite_expira"))
    return {
        "configurado": configurado(),
        "ligado": bool(tg.get("chat_id")),
        "desde": tg.get("vinculado_em") if tg.get("chat_id") else None,
        "bloqueado": bool(tg.get("chat_id") and tg.get("bloqueado_em")),
        "convite_pendente_ate": (tg.get("convite_expira") if tg.get("convite_hash") and expira and expira > agora else None),
        "tentativa_outro_chat_em": tg.get("tentativa_outro_chat_em"),
    }


# ── convite e vínculo ────────────────────────────────────────────────────────

def gerar_convite(repo, caso: dict, agora: datetime | None = None) -> dict:
    """Gera um convite novo para o caso. Um convite que ainda valia deixa de valer."""
    agora = _agora(agora)
    segredo = secrets.token_urlsafe(9)
    expira = agora + VALIDADE_CONVITE
    tg = _tg(caso)
    substituiu = bool(tg.get("convite_hash"))
    if substituiu:
        tg["substituidos"] = _guardar(tg.get("substituidos"), tg["convite_hash"])
    tg.update({"convite_hash": _hash(segredo), "convite_expira": expira.isoformat()})
    _gravar_tg(repo, caso, tg)
    codigo = caso["id"].replace("-", "") + segredo
    bot = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    return {"codigo": codigo, "expira_em": expira.isoformat(), "configurado": configurado() and bool(bot),
            "link": f"https://t.me/{bot}?start={codigo}" if bot else None,
            "vinculado": bool(tg.get("chat_id")), "substituiu": substituiu}


def _ler_codigo(codigo: str) -> tuple:
    """(caso_id, segredo) ou (None, None). O id do caso são os 32 primeiros caracteres."""
    codigo = (codigo or "").strip()
    if len(codigo) <= 32:
        return None, None
    try:
        return str(uuid.UUID(codigo[:32])), codigo[32:]
    except ValueError:
        return None, None


def _bate(lista, h: str) -> bool:
    return any(hmac.compare_digest(str(x), h) for x in (lista or []))


def vincular(repo, codigo: str, chat_id, agora: datetime | None = None) -> tuple:
    """Liga o chat ao caso do convite. Devolve (caso, motivo).

    motivo: "ligado", "ja_ligado" (o mesmo chat abriu o link de novo) ou, sem caso,
    "usado", "substituido", "vencido", "invalido".
    """
    from agente import estado
    agora, chat = _agora(agora), str(chat_id)
    caso_id, segredo = _ler_codigo(codigo)
    caso = repo.obter_caso(caso_id) if caso_id else None
    if not caso:
        return None, "invalido"
    tg, h = _tg(caso), _hash(segredo)
    if not (tg.get("convite_hash") and hmac.compare_digest(tg["convite_hash"], h)):
        if _bate(tg.get("usados"), h):
            if tg.get("chat_id") == chat:
                return caso, "ja_ligado"
            # Outra pessoa com um link já usado: não liga, e a equipe fica sabendo.
            tg["tentativa_outro_chat_em"] = agora.isoformat()
            tg["tentativas_outro_chat"] = int(tg.get("tentativas_outro_chat") or 0) + 1
            _gravar_tg(repo, caso, tg)
            return None, "usado"
        return None, "substituido" if _bate(tg.get("substituidos"), h) else "invalido"
    expira = _quando(tg.get("convite_expira"))
    if not expira or agora > expira:
        return None, "vencido"
    if tg.get("chat_id") == chat:
        # A mesma pessoa abriu um convite novo do mesmo caso: só consome o convite.
        tg.update({"usados": _guardar(tg.get("usados"), h), "convite_hash": None, "convite_expira": None})
        _gravar_tg(repo, caso, tg)
        return caso, "ja_ligado"
    anterior = repo.caso_por_telegram(chat)
    if anterior and anterior["id"] != caso["id"]:
        tg_a = _tg(anterior)
        tg_a.pop("chat_id", None)
        estado.anotar(anterior, "equipe", "Telegram desligado", "o mesmo Telegram foi ligado a outro devedor",
                      quando=agora)
        _gravar_tg(repo, anterior, tg_a)
    tg.update({"chat_id": chat, "vinculado_em": agora.isoformat(), "entregues": [],
               "usados": _guardar(tg.get("usados"), h), "convite_hash": None, "convite_expira": None})
    for k in ("bloqueado_em", "tentativa_outro_chat_em", "tentativas_outro_chat"):
        tg.pop(k, None)
    # Canal novo, pessoa ainda não confirmada: o agente confirma a identidade de novo
    # antes de falar de valores (uma confirmação feita antes, por outro canal ou num
    # teste pela tela, não vale para quem abriu o link).
    reconfirmar = bool((caso.get("dados") or {}).get("identidade_ok"))
    estado.anotar(caso, "equipe", "Telegram ligado",
                  "o devedor abriu o convite" + ("; confirmar a identidade de novo" if reconfirmar else ""), quando=agora)
    _gravar_tg(repo, caso, tg, identidade_ok=False, falhas_identidade=0)
    return caso, "ligado"


def desvincular(repo, caso: dict, agora: datetime | None = None) -> dict:
    """A equipe desliga o Telegram do caso (o convite pendente também deixa de valer)."""
    from agente import estado
    tg = _tg(caso)
    if tg.get("convite_hash"):
        tg["substituidos"] = _guardar(tg.get("substituidos"), tg["convite_hash"])
    for k in ("chat_id", "vinculado_em", "convite_hash", "convite_expira", "bloqueado_em",
              "tentativa_outro_chat_em", "tentativas_outro_chat"):
        tg.pop(k, None)
    estado.anotar(caso, "equipe", "Telegram desligado", "desligado pela equipe", quando=_agora(agora))
    _gravar_tg(repo, caso, tg)
    return status(caso, agora)


# ── entrega ──────────────────────────────────────────────────────────────────

def _chave(m: dict) -> str:
    q = _quando(m.get("criado_em"))
    base = f"{int(q.timestamp()) if q else m.get('criado_em')}|{m.get('texto')}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def entregar(ctx) -> int:
    """Manda ao Telegram o que o agente escreveu e ainda não chegou lá. Devolve quantas entregou.

    Chamado pelo orquestrador no fim de cada rodada. Considera as mensagens do
    agente desde que o chat foi ligado e dentro de `JANELA_REENVIO`: o que falhou
    numa rodada vai na próxima. Falha de rede nunca derruba o atendimento.
    """
    if "telegram" not in (ctx.caso.get("dados") or {}):
        return 0
    marca = getattr(ctx, "tg_marca", 0.0)
    if alterado_desde(ctx.caso["id"], marca):                   # o webhook mudou algo nesta rodada: relê
        ctx.tg_marca = time.monotonic()
        tg = _tg(ctx.repo.obter_caso(ctx.caso["id"]) or ctx.caso)
    else:
        tg = _tg(ctx.caso)
    chat_id = tg.get("chat_id")
    if not chat_id or tg.get("bloqueado_em") or not configurado():
        return 0
    from agente import estado
    agora = _agora(getattr(ctx, "agora", None))
    desde = max(filter(None, [_quando(tg.get("vinculado_em")), agora - JANELA_REENVIO]))
    trace = getattr(ctx.rastreio, "trace_id", None)
    # Com o caso na mão de uma pessoa, só vai o que foi escrito nesta rodada (ex.: o aviso de
    # transferência); uma resposta antiga do agente que tinha falhado não chega atrasada por cima dela.
    so_desta_rodada = ctx.caso.get("situacao") in estado.SO_PESSOA_TIRA
    entregues = list(tg.get("entregues") or [])
    mensagens = ctx.repo.ultimas_mensagens(ctx.caso["empresa_id"], ctx.caso["id"], 20)
    # Depois que uma pessoa da equipe falou (ou houve um aviso de passagem), resposta velha
    # do agente que tinha falhado não vai mais: ficaria fora de ordem.
    corte = max([q for m in mensagens if m.get("direcao") == "saida" and m.get("trace_id") in MARCAS_DIRETAS
                 and (q := _quando(m.get("criado_em")))] or [desde])
    pendentes = []
    for m in mensagens:
        q = _quando(m.get("criado_em"))
        desta_rodada = m.get("trace_id") == trace
        if (m.get("direcao") != "saida" or m.get("trace_id") in MARCAS_DIRETAS or not q or q < desde
                or _chave(m) in entregues or (not desta_rodada and (so_desta_rodada or q < corte))):
            continue
        pendentes.append(m)
    n = 0
    for i, m in enumerate(pendentes):
        r = enviar_texto(chat_id, m["texto"])
        if r is True:
            entregues.append(_chave(m))
            n += 1
            continue
        if r == BLOQUEADO:
            # Bloqueou o bot: o que estava na fila é descartado (ficou no caso). Quando ele voltar
            # a escrever, a conversa recomeça dali, sem respostas velhas chegando de uma vez.
            tg["bloqueado_em"] = agora.isoformat()
            entregues.extend(_chave(x) for x in pendentes[i:])
        break
    tg["entregues"] = entregues[-MAX_ENTREGUES:]
    ctx.saida["_telegram"] = {k: tg[k] for k in ("entregues", "bloqueado_em") if k in tg}
    dados = dict(ctx.caso.get("dados") or {})
    dados["telegram"] = tg
    ctx.caso["dados"] = dados
    return n


def enviar_para_caso(repo, caso: dict, texto: str, agora: datetime | None = None) -> str:
    """Manda um texto já registrado no caso (pessoa da equipe ou aviso) ao chat ligado.

    Devolve "entregue", "sem_telegram", "nao_configurado", "falhou" ou "bloqueado".
    """
    tg = _tg(caso)
    if not tg.get("chat_id"):
        return "sem_telegram"
    if not configurado():
        return "nao_configurado"
    if tg.get("bloqueado_em"):
        return "bloqueado"
    r = enviar_texto(tg["chat_id"], texto)
    if r == BLOQUEADO:
        tg["bloqueado_em"] = _agora(agora).isoformat()
        _gravar_tg(repo, caso, tg)
        return "bloqueado"
    return "entregue" if r is True else "falhou"


def avisar(repo, caso: dict, texto: str, agora: datetime | None = None) -> str:
    """Aviso do sistema ao devedor (ex.: uma pessoa assumiu): fica no caso e vai ao Telegram, se ligado."""
    repo.gravar_mensagem(caso["empresa_id"], caso["id"], "saida", texto, "aviso", criado_em=_agora(agora))
    return enviar_para_caso(repo, caso, texto, agora)


def _pode_avisar(repo, caso: dict, tipo: str, agora: datetime, intervalo: timedelta | None = None) -> bool:
    """Avisos automáticos (pausa, só texto, espera) no máximo uma vez por intervalo."""
    tg = _tg(caso)
    avisos = dict(tg.get("avisos") or {})
    ultimo = _quando(avisos.get(tipo))
    if ultimo and agora - ultimo < (intervalo or INTERVALO_AVISO[tipo]):
        return False
    avisos[tipo] = agora.isoformat()
    tg["avisos"] = avisos
    _gravar_tg(repo, caso, tg)
    return True


# ── abertura: o Telegram começa como a conversa pelo Mizan ─────────────────

def abrir_conversa(repo, caso: dict, agora: datetime | None = None) -> str:
    """Primeira fala depois que o devedor abre o convite. Devolve como abriu.

    A conversa recomeça aqui (`dados.conversa_desde`): a IA só lê o que vem daqui
    para frente, como numa conversa nova pelo Mizan.
      - caso novo: o mesmo fluxo de abordagem do plano (o Estrategista escolhe o tom e
        o agente se apresenta e pede a confirmação) ................ "abordagem"
      - o agente já tinha aberto a conversa e ninguém respondeu ainda (ex.: a abordagem do
        plano saiu antes do convite): essa abertura chega ao Telegram . "retomada"
      - já houve conversa (outra pessoa, outro canal, teste pela tela): a pessoa nova
        recebe a mesma apresentação da abordagem, e a conversa recomeça "apresentacao"
      - caso com a equipe, suspenso, contestado ou quitado: só avisa que está conectado "conectado"
    """
    from agente import api, estado, ferramentas, orquestrador as orq
    from agente.estrategista import texto_abordagem
    from agente.llm import ia_ligada
    agora = _agora(agora)
    emp = caso["empresa_id"]
    fonte = api.fabrica_fonte()
    dev = fonte.devedor(emp, caso["predicao_id"]) or {}
    nome, empresa = ferramentas._primeiro_nome(dev.get("nome")), fonte.nome_empresa(emp)

    if caso["situacao"] == "novo" and not caso.get("grupo_controle") and api.ligado():
        _gravar_tg(repo, caso, _tg(caso), conversa_desde=agora.isoformat())
        chave = f"abordagem:{caso['predicao_id']}:telegram:{agora.isoformat()}"
        orq.registrar_evento(repo, emp, caso["id"], "abordagem", chave,
                             {"com_ia": ia_ligada("estrategista"), "convite": True}, origem="telegram")
        _processar_caso(repo, caso, chave, agora, _tg(caso).get("chat_id"))
        if any(m["direcao"] == "saida" and (_quando(m.get("criado_em")) or agora) >= agora
               for m in repo.ultimas_mensagens(emp, caso["id"], 5)):
            return "abordagem"
        caso = repo.obter_caso(caso["id"]) or caso

    msgs = repo.ultimas_mensagens(emp, caso["id"], 50)
    # Só a abertura sem resposta é retomada. Uma resposta do agente a outra pessoa
    # não faz sentido para quem acabou de chegar.
    rabo = [] if any(m["direcao"] == "entrada" for m in msgs) else \
        [m for m in msgs if m.get("trace_id") not in MARCAS_DIRETAS][-2:]
    tg = _tg(caso)
    if rabo and (caso["situacao"] in estado.PODE_FALAR or caso["situacao"] == "com_pessoa"):
        entregues = list(tg.get("entregues") or [])
        for m in rabo:
            if enviar_texto(tg["chat_id"], m["texto"]) is True:
                entregues.append(_chave(m))
        tg["entregues"] = entregues[-MAX_ENTREGUES:]
        _gravar_tg(repo, caso, tg, conversa_desde=_quando(rabo[0].get("criado_em")).isoformat())
        return "retomada"

    _gravar_tg(repo, caso, tg, conversa_desde=agora.isoformat())
    if caso["situacao"] in estado.PODE_FALAR:
        # Mesma abertura do plano: apresenta, pede a confirmação. Fica no caso como fala do assistente.
        texto = texto_abordagem(nome, empresa)
        repo.gravar_mensagem(emp, caso["id"], "saida", texto, "abertura", criado_em=agora)
        if enviar_texto(tg["chat_id"], texto) is True:
            caso = repo.obter_caso(caso["id"]) or caso
            tg = _tg(caso)
            tg["entregues"] = (list(tg.get("entregues") or []) +
                               [_chave({"criado_em": agora.isoformat(), "texto": texto})])[-MAX_ENTREGUES:]
            _gravar_tg(repo, caso, tg)
        return "apresentacao"
    texto = MSG_CONECTADO.format(nome=f", {nome}" if nome else "", empresa=empresa)
    if caso["situacao"] == "com_pessoa":
        texto += MSG_CONECTADO_EQUIPE
    avisar(repo, caso, texto, agora)
    return "conectado"


# ── limite de IA por conversa ───────────────────────────────────────────────

def _limite_rodadas() -> tuple:
    """(máximo de rodadas, janela). Lido a cada chamada: o ambiente pode mudar sem reiniciar."""
    try:
        maximo = max(1, int(os.getenv("MIZAN_IA_RODADAS_CASO", "30")))
    except ValueError:
        maximo = 30
    try:
        janela = timedelta(minutes=max(1, int(os.getenv("MIZAN_IA_JANELA_CASO_MIN", "10"))))
    except ValueError:
        janela = timedelta(minutes=10)
    return maximo, janela


def _adiar_se_passou_do_limite(repo, caso: dict, chave: str, texto: str, agora: datetime) -> dict | None:
    """Conta as rodadas de IA da conversa e, passado o limite, adia em vez de processar.

    Devolve None se a mensagem pode ser processada agora (e conta a rodada), ou
    {"acao": ...} se foi adiada. As rodadas ficam em `dados.telegram.rodadas_ia`,
    incluindo a do evento adiado (na data em que ele vai rodar): é ela que
    responde, de uma vez, a tudo o que chegou enquanto a janela estava cheia.
    """
    from agente import orquestrador as orq
    maximo, janela = _limite_rodadas()
    tg = _tg(caso)
    rodadas = sorted(q for q in (_quando(x) for x in tg.get("rodadas_ia") or []) if q and q > agora - janela)

    pendente = repo.evento_por_chave(caso["empresa_id"], tg["adiado_chave"]) if tg.get("adiado_chave") else None
    if pendente and pendente.get("situacao") == "pendente":
        # Já existe a rodada adiada desta janela: a mensagem entra nela. Fica o
        # FIM do texto acumulado, que é o mais recente (a triagem lê até 2000).
        from agente import triagem
        dados = dict(pendente.get("dados") or {})
        dados["texto"] = (str(dados.get("texto") or "") + "\n" + texto)[-triagem.MAX_CARACTERES:]
        repo.atualizar_evento(pendente["id"], {"dados": dados})
        if _pode_avisar(repo, caso, "espera", agora, janela):
            enviar_texto(tg.get("chat_id"), MSG_ESPERA)
        return {"acao": "adiado", "caso_id": caso["id"]}

    if len(rodadas) < maximo:
        tg["rodadas_ia"] = [q.isoformat() for q in rodadas] + [agora.isoformat()]
        tg.pop("adiado_chave", None)
        _gravar_tg(repo, caso, tg)
        return None

    # Janela cheia: uma rodada só, quando a mais antiga das que contam sair da janela.
    quando = rodadas[-maximo] + janela
    orq.registrar_evento(repo, caso["empresa_id"], caso["id"], "mensagem_devedor", chave,
                         {"texto": texto}, origem="telegram", disponivel_em=quando)
    tg["rodadas_ia"] = [q.isoformat() for q in rodadas] + [quando.isoformat()]
    tg["adiado_chave"] = chave
    _gravar_tg(repo, caso, tg)
    if _pode_avisar(repo, caso, "espera", agora, janela):
        enviar_texto(tg.get("chat_id"), MSG_ESPERA)
    return {"acao": "adiado", "caso_id": caso["id"]}


# ── recebimento (webhook) ───────────────────────────────────────────────────

def _digitando(chat_id, parar: threading.Event) -> None:
    while not parar.wait(DIGITANDO_S):
        enviar_acao(chat_id)


def _processar_caso(repo, caso: dict, chave: str, agora: datetime, chat_id=None) -> None:
    """Processa a fila só deste caso e acompanha até a resposta sair, como a tela do Mizan.

    - Caso ocupado (o agente ainda responde a mensagem anterior): espera soltar.
    - IA ocupada por instantes: a nova tentativa sai em até RETOMAR_ATE_S; espera e
      tenta de novo, como a conversa aberta no Mizan faz. Mais longe que isso, o
      agendador (a cada minuto) retoma.
    - Enquanto isso, o devedor vê "digitando…".
    """
    from agente import api, orquestrador as orq
    fonte = api.fabrica_fonte()
    grafos, cliente = api.grafos(fonte), api.fabrica_cliente()
    limite = time.monotonic() + ESPERA_CASO_S
    parar = threading.Event()
    if chat_id is not None:
        threading.Thread(target=_digitando, args=(chat_id, parar), daemon=True).start()
    try:
        while True:
            orq.processar_fila(repo, grafos, cliente, limite=5, agora=max(agora, datetime.now(timezone.utc)),
                               empresa_id=caso["empresa_id"], caso_id=caso["id"])
            ev = repo.evento_por_chave(caso["empresa_id"], chave) or {}
            pronto_em = _quando(ev.get("disponivel_em"))
            falta = (pronto_em - datetime.now(timezone.utc)).total_seconds() if pronto_em else 0
            if ev.get("situacao") != "pendente" or falta > RETOMAR_ATE_S or time.monotonic() > limite:
                return
            time.sleep(1)
    finally:
        parar.set()


_TRAVAS: dict = {}
_TRAVAS_LOCK = threading.Lock()


def _trava_do_caso(caso_id: str) -> threading.Lock:
    """Uma mensagem por vez por caso, no recebimento (juntar mensagens sem corrida)."""
    with _TRAVAS_LOCK:
        return _TRAVAS.setdefault(caso_id, threading.Lock())


_VISTAS: list = []                      # updates já tratados neste processo (o Telegram pode reenviar)


def _ja_visto(chave: str) -> bool:
    with _TRAVAS_LOCK:
        if chave in _VISTAS:
            return True
        _VISTAS.append(chave)
        del _VISTAS[:-500]
        return False


def _juntar_na_fila(repo, caso: dict, chave: str, texto: str) -> dict | None:
    """O devedor mandou outra mensagem antes de o agente começar a responder a anterior:
    ela entra no mesmo evento, e UMA resposta cobre as duas. No Mizan a caixa espera a
    resposta; aqui a pessoa pode mandar várias seguidas. Devolve o evento, ou None."""
    from agente import triagem
    fila = repo.pendente_do_caso(caso["empresa_id"], caso["id"], "mensagem_devedor")
    if not fila or fila.get("chave") == chave:
        return None
    dados = dict(fila.get("dados") or {})
    if chave in (dados.get("juntadas") or []):
        return fila
    dados["texto"] = (str(dados.get("texto") or "") + "\n" + texto)[-triagem.MAX_CARACTERES:]
    dados["juntadas"] = (list(dados.get("juntadas") or []) + [chave])[-30:]
    if not repo.atualizar_evento_pendente(fila["id"], {"dados": dados}):
        return None                             # começou a ser processado agora: vira mensagem nova
    return fila


def receber(update: dict, repo=None, agora: datetime | None = None, processar=True) -> dict:
    """Trata um update do Telegram. Devolve {"acao": ...} (usado nos testes e no log)."""
    from agente import api, orquestrador as orq
    msg = (update or {}).get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private" or (msg.get("from") or {}).get("is_bot") or chat.get("id") is None:
        return {"acao": "ignorado"}
    chat_id, texto = chat["id"], (msg.get("text") or "").strip()
    repo = repo or api.fabrica_repo()
    agora = _agora(agora)

    if not texto:
        if not any(k in msg for k in _MIDIA):
            return {"acao": "ignorado"}
        caso = repo.caso_por_telegram(chat_id)
        if not caso:
            enviar_texto(chat_id, MSG_SEM_VINCULO)
            return {"acao": "sem_vinculo"}
        if _pode_avisar(repo, caso, "so_texto", agora):
            enviar_texto(chat_id, MSG_SO_TEXTO)
        return {"acao": "midia", "caso_id": caso["id"]}

    if texto.startswith("/start"):
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            caso = repo.caso_por_telegram(chat_id)
            enviar_texto(chat_id, MSG_JA_LIGADO if caso else MSG_SEM_VINCULO)
            return {"acao": "ja_ligado" if caso else "sem_vinculo"}
        caso, motivo = vincular(repo, partes[1], chat_id, agora)
        if motivo in ("ligado", "ja_ligado"):
            # O Telegram exige que a pessoa toque em Iniciar, e isso aparece no chat como
            # "/start <código comprido>". Apagado, a conversa começa limpa, só com o agente.
            apagar_mensagem(chat_id, msg.get("message_id"))
        if motivo == "ligado":
            enviar_acao(chat_id)
            como = abrir_conversa(repo, caso, agora)
            return {"acao": "vinculado", "caso_id": caso["id"], "abertura": como}
        if motivo == "ja_ligado":
            enviar_texto(chat_id, MSG_JA_LIGADO)
            return {"acao": "ja_ligado", "caso_id": caso["id"]}
        enviar_texto(chat_id, MSG_CONVITE[motivo])
        return {"acao": f"convite_{motivo}"}

    caso = repo.caso_por_telegram(chat_id)
    if not caso:
        enviar_texto(chat_id, MSG_SEM_VINCULO)
        return {"acao": "sem_vinculo"}
    tg = _tg(caso)
    if tg.get("bloqueado_em"):
        tg.pop("bloqueado_em")                  # escreveu de novo: desbloqueou o bot
        _gravar_tg(repo, caso, tg)
    texto = texto[:api.MAX_TEXTO]
    chave = f"telegram:{update.get('update_id', uuid.uuid4().hex)}"

    if not api.ligado():
        # Agente desligado: a mensagem não se perde (a equipe vê no caso) e o devedor sabe que foi recebida.
        if any(m.get("trace_id") == chave for m in repo.ultimas_mensagens(caso["empresa_id"], caso["id"], 20)):
            return {"acao": "repetido", "caso_id": caso["id"]}
        repo.gravar_mensagem(caso["empresa_id"], caso["id"], "entrada", texto, chave, criado_em=agora)
        if _pode_avisar(repo, caso, "pausa", agora):
            avisar(repo, caso, MSG_PAUSADO, agora)
        return {"acao": "agente_desligado", "caso_id": caso["id"]}

    trava = _trava_do_caso(caso["id"])
    esperou = not trava.acquire(blocking=False)
    if esperou:
        trava.acquire()
    try:
        if _ja_visto(chave) or repo.evento_por_chave(caso["empresa_id"], chave):
            return {"acao": "repetido", "caso_id": caso["id"]}   # reenvio do Telegram: não conta rodada
        if esperou:
            caso = repo.obter_caso(caso["id"]) or caso       # outra mensagem deste caso mexeu nele enquanto esperava
        fila = _juntar_na_fila(repo, caso, chave, texto)
        if fila:
            pronto = _quando(fila.get("disponivel_em"))
            if not pronto or (pronto - datetime.now(timezone.utc)).total_seconds() <= RETOMAR_ATE_S:
                enviar_acao(chat_id)
            return {"acao": "juntou", "caso_id": caso["id"]}
        adiado = _adiar_se_passou_do_limite(repo, caso, chave, texto, agora)
        if adiado:
            return adiado
        ev, novo = orq.registrar_evento(repo, caso["empresa_id"], caso["id"], "mensagem_devedor", chave,
                                        {"texto": texto}, origem="telegram")
    finally:
        trava.release()
    if novo and processar:
        enviar_acao(chat_id)                    # "digitando…" já, antes da IA começar
        _processar_caso(repo, caso, chave, agora, chat_id)
    return {"acao": "mensagem" if novo else "repetido", "caso_id": caso["id"]}
