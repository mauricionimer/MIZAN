"""
Motor de renegociação: margem livre (affordability) e valor esperado (EV).

Tudo aqui vem da referência técnica de crédito que embasa o Mizan — nenhuma
taxa, prazo ou limiar foi inventado. Onde a referência traz política do banco
("Regra do banco diz: parcela não pode comprometer mais que 30% da margem"),
o valor é configurável por empresa, não fixo no código.

A fórmula do valor esperado foi conferida contra as oito linhas das duas
simulações da referência e reconcilia todas:

    EV = dívida × (1 − desconto) × PoP

O detalhe que faz as duas baterem: quando a parcela embute juros, a soma das
parcelas é maior que a dívida (12 × R$ 270 = R$ 3.240 sobre dívida de
R$ 3.000), mas o EV da referência usa R$ 3.000. Juros embutidos são receita
nova, não recuperação do que estava devido — e recuperação é o que o EV mede.

Ver test_proposta.py: as duas tabelas são reproduzidas linha a linha.
"""

from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Política do banco (Policy Engine)
# ---------------------------------------------------------------------------

# A referência descreve a margem em duas etapas, com valores que são política
# do banco e não constante universal:
#
#   "R$ 4.500 (Renda) − R$ 2.500 (Despesas fixas) − 30% Buffer
#    = Margem Livre de R$ 1.400"          -> buffer de 30% sobre o líquido
#
#   "Parcela não pode comprometer mais que 30% da margem livre"
#                                          -> teto de comprometimento
#
# Os dois números aparecem em contextos diferentes (concessão de crédito novo),
# enquanto as simulações do motor de renegociação comparam a parcela direto
# com a margem (R$ 333 < R$ 400 passa). Por isso o padrão aqui reproduz o
# motor de renegociação (teto de 100%), e o teto mais rígido fica disponível
# para o banco que quiser adotá-lo.
BUFFER_MARGEM_PCT_PADRAO = 30.0        # desconto de segurança sobre o líquido
COMPROMETIMENTO_MAX_PCT_PADRAO = 100.0  # quanto da margem uma parcela pode ocupar


@dataclass
class PoliticaProposta:
    """Parâmetros que pertencem ao banco, não ao Mizan."""
    buffer_margem_pct: float = BUFFER_MARGEM_PCT_PADRAO
    comprometimento_max_pct: float = COMPROMETIMENTO_MAX_PCT_PADRAO

    @classmethod
    def de_config(cls, extra: "dict | None") -> "PoliticaProposta":
        extra = extra or {}
        return cls(
            buffer_margem_pct=float(
                extra.get("buffer_margem_pct", BUFFER_MARGEM_PCT_PADRAO)),
            comprometimento_max_pct=float(
                extra.get("comprometimento_max_pct", COMPROMETIMENTO_MAX_PCT_PADRAO)),
        )


# ---------------------------------------------------------------------------
# Margem livre (Affordability)
# ---------------------------------------------------------------------------

@dataclass
class Margem:
    valor: "float | None"       # R$ livres por mês; None = não dá para saber
    origem: str                 # "informada" | "indisponivel"
    renda: "float | None" = None
    despesas: "float | None" = None
    buffer_pct: float = BUFFER_MARGEM_PCT_PADRAO
    motivo: str = ""

    @property
    def conhecida(self) -> bool:
        return self.valor is not None


def calcular_margem(renda: "float | None", despesas: "float | None",
                    politica: "PoliticaProposta | None" = None) -> Margem:
    """Margem livre mensal = (renda − despesas) − buffer.

    Sem despesas não existe margem: a referência calcula affordability a
    partir de extrato bancário (Open Finance), e o Mizan não tem esse dado a
    menos que o cliente informe. Nesse caso a função devolve margem
    desconhecida em vez de estimar uma despesa qualquer — um número inventado
    aqui reprovaria propostas boas e aprovaria parcelas que o devedor não
    consegue pagar.
    """
    politica = politica or PoliticaProposta()
    try:
        renda_f = float(renda) if renda is not None else None
        despesas_f = float(despesas) if despesas is not None else None
    except (TypeError, ValueError):
        renda_f = despesas_f = None

    if renda_f is None or renda_f <= 0:
        return Margem(None, "indisponivel", renda_f, despesas_f,
                      politica.buffer_margem_pct,
                      "Renda não informada: sem ela não há como aferir capacidade de pagamento.")
    if despesas_f is None:
        return Margem(None, "indisponivel", renda_f, None,
                      politica.buffer_margem_pct,
                      "Despesas mensais não informadas: a margem livre exige renda e despesas. "
                      "Inclua a coluna 'despesas_mensais' na carteira para ativar a verificação.")

    liquido = renda_f - despesas_f
    margem = liquido * (1 - politica.buffer_margem_pct / 100)
    margem = max(0.0, round(margem, 2))
    motivo = ""
    if liquido <= 0:
        motivo = "Despesas iguais ou maiores que a renda: nenhuma parcela cabe no orçamento."
    return Margem(margem, "informada", renda_f, despesas_f,
                  politica.buffer_margem_pct, motivo)


def parcela_maxima(margem: Margem,
                   politica: "PoliticaProposta | None" = None) -> "float | None":
    """Maior parcela que a política do banco admite para esta margem."""
    if not margem.conhecida:
        return None
    politica = politica or PoliticaProposta()
    return round(margem.valor * politica.comprometimento_max_pct / 100, 2)


# ---------------------------------------------------------------------------
# Propostas
# ---------------------------------------------------------------------------

@dataclass
class Proposta:
    rotulo: str
    desconto_pct: float
    n_parcelas: int              # 1 = à vista
    oferta: str = ""             # id da oferta no bandit, quando houver
    valor_cobrado: float = 0.0   # dívida já com desconto — o que o banco recupera
    parcela: float = 0.0
    pop: "float | None" = None   # probabilidade de pagamento desta proposta
    origem_pop: str = ""
    pop_observacoes: int = 0     # feedbacks reais por trás da PoP
    valor_esperado: "float | None" = None
    cabe_no_bolso: "bool | None" = None   # None = não foi possível verificar
    observacao: str = ""

    @property
    def a_vista(self) -> bool:
        return self.n_parcelas <= 1


# Os quatro arquétipos seguem a forma da simulação da referência — duas
# parceladas e duas de quitação com desconto — mas usam o MESMO catálogo de
# ofertas do bandit (model/bandit.py: ACOES). Sem isso o produto teria dois
# vocabulários de oferta: o bandit aprenderia sobre "parcelado_12x" enquanto
# a tela propõe "12x com 30% de desconto", e o aprendizado nunca chegaria na
# proposta. Prazos e descontos continuam ponto de partida, ajustáveis por
# banco; o campo "oferta" é que amarra proposta e aprendizado.
ARQUETIPOS_PADRAO = [
    {"rotulo": "Parcelado em 4x, sem desconto", "desconto_pct": 0.0,
     "n_parcelas": 4,  "oferta": "parcelado_4x"},
    {"rotulo": "Parcelado em 12x",              "desconto_pct": 0.0,
     "n_parcelas": 12, "oferta": "parcelado_12x"},
    {"rotulo": "10% de desconto à vista",       "desconto_pct": 10.0,
     "n_parcelas": 1,  "oferta": "avista_10pct"},
    {"rotulo": "30% de desconto à vista",       "desconto_pct": 30.0,
     "n_parcelas": 1,  "oferta": "desconto_30pct"},
]


def montar_propostas(divida: float, arquetipos: "list[dict] | None" = None,
                     juros_mensal_pct: float = 0.0) -> "list[Proposta]":
    """Gera as propostas a partir da dívida.

    juros_mensal_pct embute juros na parcela sem alterar o valor recuperado:
    é isso que faz 12 × R$ 270 somarem mais que a dívida de R$ 3.000 na
    referência, sem que o EV suba junto.
    """
    divida = max(0.0, float(divida or 0))
    propostas = []
    for a in (arquetipos or ARQUETIPOS_PADRAO):
        desconto = float(a.get("desconto_pct", 0.0))
        n = max(1, int(a.get("n_parcelas", 1)))
        cobrado = round(divida * (1 - desconto / 100), 2)
        juros = float(a.get("juros_mensal_pct", juros_mensal_pct))
        total_parcelado = cobrado * (1 + juros / 100 * n)
        propostas.append(Proposta(
            rotulo=a.get("rotulo", ""),
            oferta=a.get("oferta", ""),
            desconto_pct=desconto,
            n_parcelas=n,
            valor_cobrado=cobrado,
            parcela=round(total_parcelado / n, 2),
        ))
    return propostas


# ---------------------------------------------------------------------------
# Avaliação: cabe no bolso? qual rende mais?
# ---------------------------------------------------------------------------

def _brl(valor: float) -> str:
    """R$ no formato brasileiro. Trocar os separadores com replace encadeado
    converte também o ponto final da frase — foi o que acontecia aqui."""
    inteiro, _, centavos = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


@dataclass
class Avaliacao:
    propostas: "list[Proposta]" = field(default_factory=list)
    recomendada: "Proposta | None" = None
    alternativa_a_vista: "Proposta | None" = None
    margem: "Margem | None" = None
    parcela_maxima: "float | None" = None
    pop_discrimina: bool = False
    aviso: str = ""

    def para_json(self) -> dict:
        return {
            "propostas": [asdict(p) for p in self.propostas],
            "recomendada": asdict(self.recomendada) if self.recomendada else None,
            "alternativa_a_vista": (asdict(self.alternativa_a_vista)
                                    if self.alternativa_a_vista else None),
            "margem": asdict(self.margem) if self.margem else None,
            "parcela_maxima": self.parcela_maxima,
            "pop_discrimina": self.pop_discrimina,
            "aviso": self.aviso,
        }


def avaliar(propostas: "list[Proposta]", margem: Margem,
            pop_por_proposta: "list[float] | None" = None,
            origem_pop: str = "",
            politica: "PoliticaProposta | None" = None,
            pop_por_oferta: "dict | None" = None) -> Avaliacao:
    """Aplica o filtro de capacidade de pagamento e ordena por valor esperado.

    A decisão é a da referência: entre as propostas que cabem no bolso, vence
    a de maior valor esperado. A quitação à vista fica como opção secundária —
    a referência não a submete ao teste de margem ("N/A: depende de poupança
    oculta"), porque um pagamento único não sai da renda mensal.
    """
    politica = politica or PoliticaProposta()
    teto = parcela_maxima(margem, politica)

    for i, p in enumerate(propostas):
        # A PoP por oferta vem do feedback real (bandit) e tem precedência:
        # é a única que distingue uma proposta da outra por probabilidade.
        estimativa = (pop_por_oferta or {}).get(p.oferta) if p.oferta else None
        if estimativa is not None:
            p.pop = float(estimativa.get("pop"))
            p.origem_pop = estimativa.get("origem", "")
            p.pop_observacoes = int(estimativa.get("n_tentativas") or 0)
        elif pop_por_proposta is not None and i < len(pop_por_proposta):
            p.pop = float(pop_por_proposta[i])
            p.origem_pop = origem_pop
        p.valor_esperado = (round(p.valor_cobrado * p.pop, 2)
                            if p.pop is not None else None)

        if p.a_vista:
            p.cabe_no_bolso = None
            p.observacao = "Pagamento único: não compromete a renda mensal."
        elif teto is None:
            p.cabe_no_bolso = None
            p.observacao = "Capacidade de pagamento não verificada."
        else:
            p.cabe_no_bolso = p.parcela <= teto
            dentro = "dentro da" if p.cabe_no_bolso else "acima da"
            p.observacao = (f"Parcela de {_brl(p.parcela)} {dentro} "
                            f"margem de {_brl(teto)}.")

    com_ev = [p for p in propostas if p.valor_esperado is not None]
    pops = {round(p.pop, 6) for p in com_ev if p.pop is not None}
    discrimina = len(pops) > 1

    # Só existe recomendação depois de passar pelo teste de capacidade. Sem
    # margem conhecida o motor ordena por valor esperado, mas não elege uma
    # "sugerida": apontar a parcela de maior valor sem saber se ela cabe no
    # orçamento é pior do que não apontar nada.
    elegiveis = [p for p in com_ev if p.cabe_no_bolso is True and not p.a_vista]
    recomendada = max(elegiveis, key=lambda p: p.valor_esperado) if elegiveis else None
    a_vista = [p for p in com_ev if p.a_vista]
    alternativa = max(a_vista, key=lambda p: p.valor_esperado) if a_vista else None

    avisos = []
    if not margem.conhecida:
        avisos.append(
            (margem.motivo or "Margem livre desconhecida.")
            + " Sem ela nenhuma proposta passa pelo teste de capacidade de pagamento, "
              "então nenhuma é sugerida — informe as despesas para saber qual cabe."
        )
    if com_ev and not discrimina:
        avisos.append(
            "Todas as propostas usam a mesma probabilidade de pagamento, porque ainda "
            "não há feedback real por tipo de oferta. Enquanto isso, a ordenação por "
            "valor esperado apenas favorece a proposta de maior valor — ela não "
            "distingue as ofertas por probabilidade. Cada renegociação registrada "
            "alimenta essa estimativa."
        )
    elif com_ev:
        n_obs = sum(p.pop_observacoes for p in com_ev)
        das_ofertas = sum(1 for p in com_ev if p.origem_pop == "bandit")
        if n_obs:
            avisos.append(
                f"A chance de pagamento vem de {n_obs} renegociação(ões) já registrada(s), "
                f"em {das_ofertas} de {len(com_ev)} ofertas. Onde ainda não há histórico, "
                "vale a probabilidade do modelo."
            )

    return Avaliacao(propostas=propostas, recomendada=recomendada,
                     alternativa_a_vista=alternativa, margem=margem,
                     parcela_maxima=teto, pop_discrimina=discrimina,
                     aviso=" ".join(avisos))
