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
    """O gasto do dia da empresa chegou ao teto: o caso vai para uma pessoa."""


class PrecoDesconhecido(RuntimeError):
    pass


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
_VAR_MODELO = {"triagem": "MIZAN_MODELO_TRIAGEM", "negociador": "MIZAN_MODELO_NEGOCIADOR"}


def modelo_para(papel: str) -> str:
    return os.getenv(_VAR_MODELO.get(papel, ""), "") or MODELO_FALSO


def _estimar_tokens(texto: str) -> int:
    # Só para o cliente falso ter números plausíveis nos testes; custo é zero.
    return max(1, len(texto) // 4)


class ClienteFalso:
    """Responde em ordem o que estiver em `roteiro`.

    Cada item é uma Resposta, um texto, uma exceção (para testar falhas) ou uma
    função (sistema, mensagens) -> Resposta | str. Guarda as chamadas recebidas.
    """

    def __init__(self, roteiro=None):
        self.roteiro = list(roteiro or [])
        self.chamadas: list = []

    def gerar(self, *, sistema: str, mensagens: list, modelo: str = MODELO_FALSO,
              ferramentas: list | None = None, max_tokens: int = 1024, papel: str | None = None) -> Resposta:
        self.chamadas.append({"sistema": sistema, "mensagens": copy.deepcopy(mensagens),
                              "modelo": modelo, "ferramentas": ferramentas})
        item = self.roteiro.pop(0) if self.roteiro else ""
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
        msg = self.sdk.messages.create(**pedido)
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


def cliente():
    """O cliente configurado em MIZAN_AGENTE_CLIENTE (padrão: falso)."""
    tipo = os.getenv("MIZAN_AGENTE_CLIENTE", "falso").strip().lower()
    if tipo == "falso":
        return ClienteFalso()
    if tipo == "anthropic":
        return ClienteAnthropic()
    raise NotImplementedError(f"cliente de IA {tipo!r} não existe")
