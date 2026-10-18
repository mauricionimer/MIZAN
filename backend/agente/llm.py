"""Cliente de IA trocável, com custo medido e teto (docs/PLANO_EXECUCAO_AGENTES.md, 9).

Os agentes nunca falam direto com um fornecedor: pedem a `cliente()` e recebem
alguém que responde `gerar(...)`. Nos testes e até a chave existir, é o
ClienteFalso: responde o que o teste mandou e custa zero.

Preço não fica escrito aqui. Vem de MIZAN_AGENTE_PRECOS, conferido na página
oficial do fornecedor no dia em que a chave for ligada:

    MIZAN_AGENTE_PRECOS='{"<modelo>": [<US$ por milhão de entrada>, <US$ por milhão de saída>]}'

Modelo real sem preço configurado não roda: custo desconhecido não pode virar
custo zero no painel.
"""
import copy
import json
import os
from dataclasses import dataclass, field


@dataclass
class Resposta:
    texto: str = ""
    ferramentas: list = field(default_factory=list)   # [{"id": str, "nome": str, "args": dict}]
    tokens_entrada: int = 0
    tokens_saida: int = 0
    modelo: str = ""
    custo_usd: float = 0.0
    # "fim", "ferramenta", "limite" (cortou no máximo de tokens) ou "recusa"
    parada: str = ""
    # Blocos da resposta como vieram do fornecedor, para voltar ao histórico sem
    # edição (inclui os de raciocínio). Vazio no cliente falso.
    bruto: list = field(default_factory=list)
    tokens_cache_escrita: int = 0
    tokens_cache_leitura: int = 0


class TetoExcedido(RuntimeError):
    """O gasto do dia da empresa chegou ao teto: o evento espera a virada do dia
    (meia-noite de Brasília); o caso continua com o agente."""


class PrecoDesconhecido(RuntimeError):
    pass


class SemRoteiro(RuntimeError):
    """Teste: o cliente falso não tem resposta preparada para este agente."""


# Agentes que usam IA. Os de hoje (triagem e negociador) vêm ligados; os novos
# só entram quando listados em MIZAN_IA_PAPEIS. Tirar um da lista o faz voltar
# ao caminho em código, sem deploy.
PAPEIS = ("triagem", "negociador", "acompanhamento", "estrategista", "supervisor", "cientista")
PAPEIS_PADRAO = "triagem,negociador"


def ia_ligada(papel: str) -> bool:
    lista = os.getenv("MIZAN_IA_PAPEIS", PAPEIS_PADRAO)
    return papel in {p.strip().lower() for p in lista.split(",") if p.strip()}


MODELO_FALSO = "falso"


def _precos() -> dict:
    bruto = os.getenv("MIZAN_AGENTE_PRECOS", "").strip()
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
        return {str(k): (float(v[0]), float(v[1])) for k, v in dados.items()}
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise PrecoDesconhecido(f"MIZAN_AGENTE_PRECOS inválido: {type(e).__name__}") from e


# Cache de prompt (documentação da Anthropic): gravar custa ~1,25x a entrada
# (validade de 5 minutos) e ler do cache ~0,1x.
FATOR_CACHE_ESCRITA = 1.25
FATOR_CACHE_LEITURA = 0.1


def custo(modelo: str, tokens_entrada: int, tokens_saida: int,
          cache_escrita: int = 0, cache_leitura: int = 0) -> float:
    if modelo == MODELO_FALSO:
        return 0.0
    precos = _precos()
    if modelo not in precos:
        raise PrecoDesconhecido(f"sem preço configurado para o modelo {modelo!r}")
    p_in, p_out = precos[modelo]
    entrada = tokens_entrada + cache_escrita * FATOR_CACHE_ESCRITA + cache_leitura * FATOR_CACHE_LEITURA
    return round((entrada * p_in + tokens_saida * p_out) / 1_000_000, 6)


def teto_dia_usd() -> float:
    """Gasto máximo por empresa por dia. Escolha de projeto: o orçamento total
    do protótipo é US$ 10; US$ 1 por dia deixa folga para dez dias de testes."""
    try:
        return max(0.0, float(os.getenv("MIZAN_AGENTE_TETO_DIA_USD", "1.0")))
    except ValueError:
        return 1.0


def conferir_teto(gasto_hoje: float) -> None:
    if gasto_hoje >= teto_dia_usd():
        raise TetoExcedido(f"gasto do dia US$ {gasto_hoje:.4f} chegou ao teto US$ {teto_dia_usd():.2f}")


# Roteamento de modelos (cap. 9.3.4): tarefa simples no barato, conversa no maior.
_VAR_MODELO = {p: f"MIZAN_MODELO_{p.upper()}" for p in PAPEIS}


def modelo_para(papel: str) -> str:
    """Modelo do agente; os agentes novos, sem variável própria, usam o da triagem."""
    proprio = os.getenv(_VAR_MODELO.get(papel, ""), "")
    if proprio:
        return proprio
    if papel not in ("triagem", "negociador"):
        return os.getenv("MIZAN_MODELO_TRIAGEM", "") or MODELO_FALSO
    return MODELO_FALSO


def _estimar_tokens(texto: str) -> int:
    # Só para o cliente falso ter números plausíveis nos testes; custo é zero.
    return max(1, len(texto) // 4)


class ClienteFalso:
    """Responde em ordem o que estiver em `roteiro`.

    Cada item é uma Resposta, um texto, uma exceção (para testar falhas) ou uma
    função (sistema, mensagens) -> Resposta | str. Guarda as chamadas recebidas.

    `roteiro` pode ser uma lista (uma fila só, como sempre: atende triagem e
    negociador) ou um dicionário {papel: [respostas]}, uma fila por agente.
    Agente novo sem resposta preparada levanta SemRoteiro: o agente usa o
    caminho em código, e os roteiros antigos continuam alinhados.
    """
    ANTIGOS = (None, "triagem", "negociador")

    def __init__(self, roteiro=None):
        if isinstance(roteiro, dict):
            self.filas = {p: list(v) for p, v in roteiro.items()}
            self.roteiro = None
        else:
            self.filas = None
            self.roteiro = list(roteiro or [])
        self.chamadas: list = []

    def _proximo(self, papel):
        if self.filas is not None:
            fila = self.filas.get(papel)
            if fila:
                return fila.pop(0)
            if papel in self.ANTIGOS:
                return ""
            raise SemRoteiro(f"sem resposta preparada para {papel}")
        if papel not in self.ANTIGOS:
            raise SemRoteiro(f"sem resposta preparada para {papel}")
        return self.roteiro.pop(0) if self.roteiro else ""

    def gerar(self, *, sistema: str, mensagens: list, modelo: str = MODELO_FALSO,
              ferramentas: list | None = None, max_tokens: int = 1024, papel: str | None = None) -> Resposta:
        item = self._proximo(papel)
        self.chamadas.append({"sistema": sistema, "mensagens": copy.deepcopy(mensagens),
                              "modelo": modelo, "ferramentas": ferramentas, "papel": papel})
        if callable(item) and not isinstance(item, Resposta):
            item = item(sistema, mensagens)
        if isinstance(item, BaseException):
            raise item
        r = item if isinstance(item, Resposta) else Resposta(texto=str(item))
        for i, f in enumerate(r.ferramentas):
            f.setdefault("id", f"falso_{len(self.chamadas)}_{i}")
        r.parada = r.parada or ("ferramenta" if r.ferramentas else "fim")
        entrada = sistema + "".join(str(m.get("content", m.get("conteudo", ""))) for m in mensagens)
        r.tokens_entrada = r.tokens_entrada or _estimar_tokens(entrada)
        r.tokens_saida = r.tokens_saida or _estimar_tokens(r.texto)
        r.modelo = r.modelo or modelo
        r.custo_usd = custo(r.modelo, r.tokens_entrada, r.tokens_saida)
        return r


_PARADA = {"end_turn": "fim", "stop_sequence": "fim", "tool_use": "ferramenta",
           "max_tokens": "limite", "pause_turn": "limite", "refusal": "recusa"}

# Esforço por papel: classificar é tarefa simples; a conversa usa o padrão do modelo.
_ESFORCO = {"triagem": "low"}


def _erros_momentaneos_anthropic() -> tuple:
    """Erros da Anthropic que passam sozinhos. Import tolerante: sem o SDK (ou numa
    versão sem alguma classe), a tupla fica menor e nada quebra."""
    try:
        import anthropic
    except ImportError:
        return ()
    nomes = ("RateLimitError", "InternalServerError", "APIConnectionError", "APITimeoutError")
    return tuple(c for c in (getattr(anthropic, n, None) for n in nomes) if isinstance(c, type))


def _espera_anthropic(e) -> float:
    """Segundos pedidos pelo cabeçalho retry-after, se houver; senão, 60."""
    try:
        return max(30.0, float(e.response.headers.get("retry-after")))
    except (AttributeError, TypeError, ValueError):
        return 60.0


class ClienteAnthropic:
    """API oficial da Anthropic (SDK `anthropic`). A chave vem de ANTHROPIC_API_KEY.

    Instruções e ferramentas são fixas e vão com cache de prompt; o que muda a
    cada chamada vem depois, nas mensagens.
    """

    def __init__(self, sdk=None, timeout: float = 60.0):
        if sdk is None:
            import anthropic
            sdk = anthropic.Anthropic(timeout=timeout, max_retries=2)
        self.sdk = sdk

    def gerar(self, *, sistema: str, mensagens: list, modelo: str, ferramentas: list | None = None,
              max_tokens: int = 1024, papel: str | None = None) -> Resposta:
        if modelo == MODELO_FALSO:
            raise PrecoDesconhecido("cliente real sem modelo configurado (MIZAN_MODELO_*)")
        pedido = {"model": modelo, "max_tokens": max_tokens, "messages": mensagens,
                  "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}]}
        if ferramentas:
            pedido["tools"] = ferramentas
        if papel in _ESFORCO:
            pedido["output_config"] = {"effort": _ESFORCO[papel]}
        try:
            msg = self.sdk.messages.create(**pedido)
        except _erros_momentaneos_anthropic() as e:
            # Cota, sobrecarga ou rede: o evento espera e tenta de novo (nunca vira transferência).
            raise IaOcupada(f"Anthropic {type(e).__name__}", esperar_s=_espera_anthropic(e)) from None
        texto = "".join(b.text for b in msg.content if b.type == "text")
        chamadas = [{"id": b.id, "nome": b.name, "args": dict(b.input or {})}
                    for b in msg.content if b.type == "tool_use"]
        u = msg.usage
        escrita = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        leitura = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        r = Resposta(texto=texto, ferramentas=chamadas, modelo=modelo,
                     tokens_entrada=int(u.input_tokens or 0) + escrita + leitura,
                     tokens_saida=int(u.output_tokens or 0),
                     parada=_PARADA.get(msg.stop_reason, "limite"),
                     bruto=[b.model_dump(exclude_none=True) for b in msg.content],
                     tokens_cache_escrita=escrita, tokens_cache_leitura=leitura)
        r.custo_usd = custo(modelo, int(u.input_tokens or 0), r.tokens_saida, escrita, leitura)
        return r


# --- Gemini (API do Google AI Studio) ----------------------------------------

_PARADA_GEMINI = {"STOP": "fim", "MAX_TOKENS": "limite", "MALFORMED_FUNCTION_CALL": "limite",
                  "UNEXPECTED_TOOL_CALL": "limite", "TOO_MANY_TOOL_CALLS": "limite"}
# Bloqueios do próprio Google viram "recusa": o caso vai para uma pessoa.
_RECUSA_GEMINI = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY", "LANGUAGE", "OTHER"}
# Raciocínio por papel: classificar pede pouco; negociar, um pouco mais.
_RACIOCINIO_GEMINI = {"triagem": "minimal", "negociador": "low"}
_URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


class ErroGemini(RuntimeError):
    pass


class IaOcupada(ErroGemini):
    """Falha momentânea da IA: cota, sobrecarga (429/5xx), rede ou tempo esgotado,
    no Gemini ou na Anthropic. O evento espera e tenta de novo; não é motivo para
    tirar o caso do agente."""
    def __init__(self, msg: str, esperar_s: float = 60.0):
        super().__init__(msg)
        self.esperar_s = esperar_s


# Status que passam sozinhos: cota (429), erro do servidor e proxy (500/502/503/504).
_HTTP_MOMENTANEO = (429, 500, 502, 503, 504)


def _ler_json(bruto: bytes) -> dict | None:
    """Corpo em JSON, ou None se veio outra coisa (página HTML de proxy, corpo cortado)."""
    try:
        d = json.loads(bruto or b"{}")
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _enviar_http(url: str, corpo: dict, chave: str, timeout: float) -> dict:
    """POST no Gemini com até 3 tentativas.

    Falha momentânea (cota, servidor, proxy, rede, tempo esgotado ou corpo que não
    é JSON) vira IaOcupada: o orquestrador adia o evento em vez de passar o caso
    para uma pessoa. Só erro do pedido (400, 403...) vira ErroGemini.
    """
    import http.client
    import time
    import urllib.error
    import urllib.request
    dados = json.dumps(corpo).encode("utf-8")
    motivo = "sem resposta"
    for tentativa in range(3):
        req = urllib.request.Request(url, data=dados, headers={"x-goog-api-key": chave,
                                                               "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = _ler_json(r.read())
            if d is not None:
                return d
            motivo = "resposta que não é JSON"
        except urllib.error.HTTPError as e:
            try:
                bruto = e.read()
            except Exception:                        # corpo do erro ilegível: segue sem ele
                bruto = b""
            erro = ((_ler_json(bruto) or {}).get("error") or {})
            if not isinstance(erro, dict):
                erro = {}
            detalhes = [d for d in (erro.get("details") or []) if isinstance(d, dict)]
            # A mensagem do Google nunca traz a chave. Em cota estourada, diz qual.
            cotas = [f"{v.get('quotaId')}={v.get('quotaValue')}" for det in detalhes
                     for v in det.get("violations") or []]
            esperas = [det["retryDelay"] for det in detalhes if det.get("retryDelay")]
            if e.code not in _HTTP_MOMENTANEO:
                raise ErroGemini(f"Gemini HTTP {e.code} {erro.get('status', '')} cotas={cotas} esperar={esperas}") from None
            pedido = 0.0
            for s in esperas:
                try:
                    pedido = max(pedido, float(str(s).rstrip("s")))
                except ValueError:
                    pass
            if tentativa < 2 and pedido <= 30:
                # O Google diz quanto esperar (RetryInfo, ex. "17s"); até 30 s, espera aqui.
                time.sleep(max(pedido, 2.0 * (tentativa + 1)))
                continue
            raise IaOcupada(f"Gemini HTTP {e.code} {erro.get('status', '')} cotas={cotas} esperar={esperas}",
                            esperar_s=max(60.0, pedido)) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as e:
            # Rede: DNS, conexão recusada ou derrubada (RemoteDisconnected), tempo esgotado.
            motivo = type(e).__name__
        if tentativa < 2:
            time.sleep(2.0 * (tentativa + 1))
    raise IaOcupada(f"Gemini indisponível: {motivo}", esperar_s=60.0)


def _para_gemini(mensagens: list) -> list:
    """Histórico no formato do agente (blocos estilo Anthropic) -> `contents` do Gemini."""
    conteudos = []
    for m in mensagens:
        papel = "model" if m["role"] == "assistant" else "user"
        blocos = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": str(m["content"])}]
        partes = []
        for b in blocos:
            tipo = b.get("type")
            if tipo == "gemini":                    # resposta do Gemini como veio (com assinatura de raciocínio)
                partes.extend(b["partes"])
            elif tipo == "text":
                if b.get("text"):
                    partes.append({"text": b["text"]})
            elif tipo == "tool_use":                # histórico vindo de outro cliente ou do falso
                partes.append({"functionCall": {"name": b["name"], "args": b.get("input") or {}}})
            elif tipo == "tool_result":
                bruto = b.get("content")
                try:
                    resultado = json.loads(bruto) if isinstance(bruto, str) else bruto
                except ValueError:
                    resultado = bruto
                resposta = {"name": _nome_da_chamada(b["tool_use_id"]), "response": {"resultado": resultado}}
                if _id_gemini(b["tool_use_id"]):
                    resposta["id"] = _id_gemini(b["tool_use_id"])
                partes.append({"functionResponse": resposta})
        if not partes:
            continue
        if conteudos and conteudos[-1]["role"] == papel:
            conteudos[-1]["parts"].extend(partes)
        else:
            conteudos.append({"role": papel, "parts": partes})
    return conteudos


def _id_da_chamada(nome: str, n: int, id_gemini: str | None = None) -> str:
    # O id leva o nome da ferramenta: o Gemini pede o nome de volta no resultado.
    return f"{nome}__id:{id_gemini}" if id_gemini else f"{nome}__g{n}"


def _nome_da_chamada(id_: str) -> str:
    return id_.rsplit("__", 1)[0]


def _id_gemini(id_: str) -> str | None:
    sufixo = id_.rsplit("__", 1)[-1]
    return sufixo[3:] if sufixo.startswith("id:") else None


class ClienteGemini:
    """API do Gemini (Google AI Studio), por HTTP direto, sem SDK. Chave em GEMINI_API_KEY.

    O histórico do agente segue no formato de blocos já usado com a Anthropic;
    a conversão é feita aqui. A resposta do modelo volta ao histórico como um
    bloco "gemini" com as partes originais: modelos com raciocínio exigem a
    assinatura de volta na chamada seguinte.
    """

    def __init__(self, chave: str | None = None, enviar=None, timeout: float = 60.0):
        self.chave = chave if chave is not None else (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
        self.enviar = enviar or _enviar_http
        self.timeout = timeout
        self._n = 0

    def gerar(self, *, sistema: str, mensagens: list, modelo: str, ferramentas: list | None = None,
              max_tokens: int = 1024, papel: str | None = None) -> Resposta:
        if modelo == MODELO_FALSO:
            raise PrecoDesconhecido("cliente real sem modelo configurado (MIZAN_MODELO_*)")
        if not self.chave:
            raise ErroGemini("GEMINI_API_KEY não configurada")
        custo(modelo, 0, 0)                          # sem preço configurado, não chama
        corpo = {"systemInstruction": {"parts": [{"text": sistema}]},
                 "contents": _para_gemini(mensagens),
                 # O raciocínio conta no limite de saída: folga para não cortar a resposta.
                 "generationConfig": {"maxOutputTokens": max(4 * max_tokens, 4096)}}
        if papel in _RACIOCINIO_GEMINI:
            corpo["generationConfig"]["thinkingConfig"] = {"thinkingLevel": _RACIOCINIO_GEMINI[papel]}
        if ferramentas:
            corpo["tools"] = [{"functionDeclarations": [
                {"name": f["name"], "description": f.get("description", ""),
                 "parametersJsonSchema": f.get("input_schema") or {"type": "object", "properties": {}}}
                for f in ferramentas]}]
        d = self.enviar(_URL_GEMINI.format(modelo=modelo), corpo, self.chave, self.timeout)

        u = d.get("usageMetadata") or {}
        cache = int(u.get("cachedContentTokenCount") or 0)
        entrada = int(u.get("promptTokenCount") or 0)
        saida = int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)
        r = Resposta(modelo=modelo, tokens_entrada=entrada, tokens_saida=saida, tokens_cache_leitura=cache)
        r.custo_usd = custo(modelo, entrada - cache, saida, 0, cache)

        cand = (d.get("candidates") or [None])[0]
        if (d.get("promptFeedback") or {}).get("blockReason") or not cand:
            r.parada = "recusa"
            return r
        partes = (cand.get("content") or {}).get("parts") or []
        r.texto = "".join(p.get("text", "") for p in partes if "text" in p and not p.get("thought"))
        for p in partes:
            if "functionCall" in p:
                self._n += 1
                fc = p["functionCall"]
                r.ferramentas.append({"id": _id_da_chamada(fc["name"], self._n, fc.get("id")), "nome": fc["name"],
                                      "args": dict(fc.get("args") or {})})
        motivo = cand.get("finishReason") or "STOP"
        r.motivo_parada = motivo                       # o que o Google disse (vai para o rastreio)
        r.parada = ("ferramenta" if r.ferramentas and motivo == "STOP"
                    else "recusa" if motivo in _RECUSA_GEMINI else _PARADA_GEMINI.get(motivo, "limite"))
        if partes:
            r.bruto = [{"type": "gemini", "partes": partes}]
        return r


def cliente():
    """O cliente configurado em MIZAN_AGENTE_CLIENTE (padrão: falso)."""
    tipo = os.getenv("MIZAN_AGENTE_CLIENTE", "falso").strip().lower()
    if tipo == "falso":
        return ClienteFalso()
    if tipo == "anthropic":
        return ClienteAnthropic()
    if tipo == "gemini":
        return ClienteGemini()
    raise NotImplementedError(f"cliente de IA {tipo!r} não existe")
