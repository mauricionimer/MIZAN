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


def pode_falar(situacao: str) -> bool:
    return situacao in PODE_FALAR
