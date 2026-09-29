"""
Ciclo de cobrança: em que fase a dívida está, e o que cada fase custa.

A referência técnica (Volume 5, seção 26) descreve quatro fases com economia
DIFERENTE em cada uma, e é essa diferença que o Mizan ignorava. As faixas de
aging que existiam — 0-29, 30-59, 90-179 — eram só rótulos de tempo: não
sabiam que aos 31 dias entra comissão de terceiro, nem que depois de 360 a
alternativa deixa de ser cobrar e passa a ser vender.

    Preventiva        D-5 a D-1    SMS/push antes do vencimento
    Administrativa    D+1 a D+30   régua interna do banco, custo baixo
    Especializada     D+31 a D+360 escritório terceirizado cobra comissão
    Write-off         D+360+       reconhece a perda; vende a carteira

Duas consequências para a conta:

Na fase especializada o banco não fica com tudo que recupera — paga comissão
de sucesso. O valor esperado bruto passa a superestimar o retorno, e é o
líquido que deveria ordenar a fila.

Depois de 360 dias existe um piso: vender o pacote para fundo de NPL. Se o
esperado líquido de uma dívida for menor que o que ela valeria vendida,
cobrar destrói valor.

Sobre os números: a referência cita comissão "geralmente de 10% a 25%" e
cessão "por exemplo 2% a 5% do valor de face". São faixas de mercado, não o
contrato de um banco específico. Por isso NADA é aplicado por padrão — sem
configuração o sistema informa a fase e diz que o custo não foi informado,
em vez de escolher um número dentro da faixa e apresentá-lo como se fosse do
cliente.
"""

from dataclasses import dataclass

# Limites em dias de atraso, conforme a referência.
FIM_ADMINISTRATIVA = 30
FIM_ESPECIALIZADA = 360

# Faixas que a referência cita como praticadas no mercado. Servem para a tela
# mostrar o intervalo esperado e para validar o que a empresa configurar —
# nunca como valor aplicado por conta própria.
COMISSAO_MERCADO = (10.0, 25.0)
CESSAO_MERCADO = (2.0, 5.0)


@dataclass(frozen=True)
class Fase:
    id: str
    rotulo: str
    descricao: str
    tem_comissao: bool


FASES = {
    "preventiva": Fase(
        "preventiva", "Preventiva",
        "Antes do vencimento: lembrete, sem cobrança.", False),
    "administrativa": Fase(
        "administrativa", "Administrativa interna",
        "Até 30 dias: régua do próprio banco, custo baixo, sem desconto pesado.", False),
    "especializada": Fase(
        "especializada", "Especializada",
        "De 31 a 360 dias: escritório terceirizado, com comissão sobre o recuperado.", True),
    "write_off": Fase(
        "write_off", "Write-off / cessão",
        "Acima de 360 dias: perda reconhecida; a alternativa é vender a carteira.", False),
}


def fase_de(dias_em_atraso) -> str:
    """Fase do ciclo para um atraso em dias."""
    try:
        d = float(dias_em_atraso)
    except (TypeError, ValueError):
        return "administrativa"
    if d < 0:
        return "preventiva"
    if d <= FIM_ADMINISTRATIVA:
        return "administrativa"
    if d <= FIM_ESPECIALIZADA:
        return "especializada"
    return "write_off"


def _pct(extra: dict, chave: str, faixa: tuple) -> "float | None":
    """Percentual configurado pela empresa, se estiver dentro do razoável."""
    try:
        v = float(extra[chave])
    except (KeyError, TypeError, ValueError):
        return None
    # Aceita qualquer valor entre 0 e 100: a faixa da referência é referência,
    # não regra — o contrato do cliente é que manda. Fora de 0–100 é erro.
    return v if 0 <= v <= 100 else None


def custos_de_config(extra: "dict | None") -> dict:
    """Comissão e valor de cessão configurados, com a procedência."""
    extra = extra or {}
    comissao = _pct(extra, "comissao_especializada_pct", COMISSAO_MERCADO)
    cessao = _pct(extra, "cessao_pct", CESSAO_MERCADO)
    return {
        "comissao_pct": comissao,
        "cessao_pct": cessao,
        "origem": "configurado" if comissao is not None else "nao_informado",
        "faixa_mercado_comissao": COMISSAO_MERCADO,
        "faixa_mercado_cessao": CESSAO_MERCADO,
    }


def liquido(valor_esperado: float, fase: str, custos: dict) -> float:
    """Valor esperado descontada a comissão, quando a fase cobra e há número.

    Sem comissão configurada devolve o bruto — e quem chama precisa dizer que
    é bruto. Aplicar uma taxa que ninguém informou seria inventar o resultado
    na direção que mais engana: para baixo no custo, para cima no retorno.
    """
    if not FASES.get(fase, FASES["administrativa"]).tem_comissao:
        return float(valor_esperado or 0)
    c = custos.get("comissao_pct")
    if c is None:
        return float(valor_esperado or 0)
    return float(valor_esperado or 0) * (1 - c / 100)


def valor_cessao(valor_face: float, custos: dict) -> "float | None":
    """Quanto a dívida valeria vendida a fundo de NPL, se houver percentual."""
    c = custos.get("cessao_pct")
    if c is None:
        return None
    return float(valor_face or 0) * (c / 100)


def aviso(custos: dict) -> "str | None":
    """O que falta configurar para a conta ficar completa."""
    if custos.get("comissao_pct") is None:
        a, b = COMISSAO_MERCADO
        return (
            "Nenhuma comissão de cobrança foi informada, então o valor esperado das "
            f"dívidas em fase especializada (31 a 360 dias) está BRUTO. O mercado pratica "
            f"de {a:.0f}% a {b:.0f}% sobre o recuperado; configure "
            "'comissao_especializada_pct' para a fila refletir o que sobra para o banco."
        )
    return None
