"""Situações de um caso e as mudanças permitidas (docs/PLANO_EXECUCAO_AGENTES.md, 4.2).

O agente só move o caso pelas mudanças desta tabela. Algumas situações são
"da pessoa": uma vez lá, só uma pessoa tira o caso dali. É isso que garante
que um pedido para parar o contato, uma contestação ou uma transferência não
sejam desfeitos pelo próprio agente.
"""

SITUACOES = (
    "novo", "so_lembrete", "em_contato", "negociando", "acordo_ativo",
    "atrasado", "pagamento_em_conferencia", "contestado", "suspenso",
    "com_pessoa", "quitado", "quebrado",
)

# Daqui o agente não tira o caso; só uma pessoa.
SO_PESSOA_TIRA = frozenset({"contestado", "suspenso", "com_pessoa"})

# Fim do atendimento.
FINAIS = frozenset({"quitado"})

# Em qualquer situação o agente pode suspender (pedido para parar), registrar
# contestação ou passar para uma pessoa.
_SEMPRE = {"suspenso", "contestado", "com_pessoa"}

_AGENTE: dict[str, set] = {
    "novo":                     {"so_lembrete", "em_contato"},
    "so_lembrete":              {"em_contato", "negociando", "pagamento_em_conferencia", "quitado"},
    "em_contato":               {"negociando", "pagamento_em_conferencia"},
    "negociando":               {"em_contato", "acordo_ativo", "pagamento_em_conferencia"},
    "acordo_ativo":             {"atrasado", "pagamento_em_conferencia", "quitado"},
    "atrasado":                 {"acordo_ativo", "negociando", "quebrado", "pagamento_em_conferencia"},
    "pagamento_em_conferencia": {"acordo_ativo", "atrasado", "em_contato", "quitado"},
    "quebrado":                 {"em_contato", "negociando", "pagamento_em_conferencia"},
    "contestado":               set(),
    "suspenso":                 set(),
    "com_pessoa":               set(),
    "quitado":                  set(),
}

# Quem fala com o devedor só fala nestas situações.
PODE_FALAR = frozenset({"so_lembrete", "em_contato", "negociando", "acordo_ativo",
                        "atrasado", "pagamento_em_conferencia", "quebrado"})


class TransicaoProibida(ValueError):
    pass


def permitidas(atual: str, por: str = "agente") -> set:
    """Situações para onde o caso pode ir a partir de `atual`."""
    if atual not in SITUACOES:
        raise TransicaoProibida(f"situação desconhecida: {atual}")
    if por == "pessoa":
        # A pessoa decide; só não reabre um caso quitado.
        return set() if atual in FINAIS else set(SITUACOES) - {atual}
    if atual in SO_PESSOA_TIRA or atual in FINAIS:
        return set()
    return _AGENTE[atual] | _SEMPRE


def mudar(atual: str, nova: str, por: str = "agente") -> str:
    """Confere e devolve a nova situação; levanta TransicaoProibida se não pode."""
    if nova not in SITUACOES:
        raise TransicaoProibida(f"situação desconhecida: {nova}")
    if nova not in permitidas(atual, por):
        raise TransicaoProibida(f"{por} não pode mudar de {atual} para {nova}")
    return nova


# ── caderno do caso: como os agentes se passam o que decidiram ──────────────
MAX_CADERNO = 15
AGENTES_DO_CADERNO = ("estrategista", "triagem", "negociador", "acompanhamento", "supervisor", "cientista", "equipe")


def anotar(caso: dict, agente: str, decisao: str, motivo: str = "", trace_id=None, quando=None) -> None:
    """Uma linha no caderno do caso: quem decidiu o quê e por quê.

    O próximo agente lê antes de agir. Nunca guarda texto do devedor: o motivo
    passa pelo filtro de dado pessoal e tem no máximo 200 caracteres.
    """
    from agente.guardrails import limpar_nota
    if agente not in AGENTES_DO_CADERNO:
        raise ValueError(f"agente desconhecido no caderno: {agente}")
    dados = dict(caso.get("dados") or {})
    nota = {"agente": agente, "decisao": limpar_nota(decisao, 60), "motivo": limpar_nota(motivo, 200),
            "quando": quando.isoformat() if hasattr(quando, "isoformat") else quando, "trace_id": trace_id}
    dados["caderno"] = (list(dados.get("caderno") or []) + [nota])[-MAX_CADERNO:]
    caso["dados"] = dados


def caderno(caso: dict, n: int = MAX_CADERNO) -> list:
    return list((caso.get("dados") or {}).get("caderno") or [])[-n:]


def pode_falar(situacao: str) -> bool:
    return situacao in PODE_FALAR
