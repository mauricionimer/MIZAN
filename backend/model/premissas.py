"""
Premissas da empresa: os números que são do banco, não do Mizan.

Seis valores mudam o que o sistema calcula e antes só podiam ser gravados pela
API, sem tela, sem validação e sem registro do que valia antes. Cada um tem
padrão declarado (ou "não informado", que o sistema trata como tal em vez de
inventar um número) e limites. Nada aqui é recomendação: a faixa de mercado que
o material de referência cita fica no texto de ajuda, nunca como valor aplicado.

Guardadas em `empresa_config.extra`, com os mesmos nomes que o resto do código já
lia (ciclo.py, priorizacao.py, proposta.py, main.py). Gravar só passa por aqui.
"""

from dataclasses import dataclass
from typing import Optional

from model.priorizacao import CRITERIOS, CRITERIO_PADRAO
from model.proposta import BUFFER_MARGEM_PCT_PADRAO, COMPROMETIMENTO_MAX_PCT_PADRAO

RECUPERACAO_SE_PAGAR_PADRAO = 1.0       # espelha main.PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO


@dataclass(frozen=True)
class Premissa:
    chave: str
    rotulo: str
    tipo: str                     # "percentual" | "fracao" | "escolha"
    padrao: Optional[object]      # None = "não informado"
    descricao: str
    efeito: str                   # quando vale: "proximas_analises" | "imediato"
    ajuda_id: str                 # entrada da Central de Ajuda
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    minimo_exclusivo: bool = False
    maximo_exclusivo: bool = False
    opcoes: tuple = ()
    escala_ui: float = 1.0        # a tela mostra valor × escala (fração → %)
    sem_padrao_diz: str = ""      # o que acontece enquanto não for informada


PREMISSAS = {p.chave: p for p in (
    Premissa(
        "comissao_especializada_pct", "Comissão do escritório de cobrança", "percentual", None,
        "Percentual que o banco paga sobre o que é recuperado na fase especializada (31 a 360 dias).",
        "proximas_analises", "comissao-de-cobranca", 0.0, 100.0,
        sem_padrao_diz="Não informada: o valor esperado dessa fase fica bruto, e o sistema avisa."),
    Premissa(
        "cessao_pct", "Valor de venda da carteira (cessão)", "percentual", None,
        "Percentual do valor de face que um fundo pagaria por dívidas acima de 360 dias.",
        "proximas_analises", "cessao-e-write-off", 0.0, 100.0,
        sem_padrao_diz="Não informado: a comparação cobrar × vender não é feita."),
    Premissa(
        "recuperacao_se_pagar", "Quanto entra quando o devedor paga", "fracao",
        RECUPERACAO_SE_PAGAR_PADRAO,
        "Parte da dívida que se recupera quando o devedor efetivamente paga. 100% é pagamento integral.",
        "proximas_analises", "recuperacao-se-pagar", 0.0, 1.0, minimo_exclusivo=True, escala_ui=100.0),
    Premissa(
        "criterio_priorizacao", "Critério da fila", "escolha", CRITERIO_PADRAO,
        "Como a fila é ordenada. Por valor esperado recupera mais; proporcional por região reparte o esforço.",
        "proximas_analises", "criterio-de-priorizacao", opcoes=tuple(CRITERIOS)),
    Premissa(
        "buffer_margem_pct", "Folga de segurança na margem livre", "percentual",
        BUFFER_MARGEM_PCT_PADRAO,
        "Quanto da sobra do mês (renda − despesas) é separado como segurança antes de calcular a parcela.",
        "imediato", "margem-livre", 0.0, 100.0, maximo_exclusivo=True),
    Premissa(
        "comprometimento_max_pct", "Teto da parcela sobre a margem", "percentual",
        COMPROMETIMENTO_MAX_PCT_PADRAO,
        "Quanto da margem livre uma parcela pode ocupar. 100% é a margem inteira.",
        "imediato", "parcela-maxima", 0.0, 100.0, minimo_exclusivo=True),
)}


def _como_numero(v):
    if isinstance(v, bool):
        raise ValueError("informe um número")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        t = v.strip().replace(",", ".")
        if not t:
            raise ValueError("informe um número")
        return float(t)
    raise ValueError("informe um número")


def validar_um(chave: str, bruto) -> object:
    """Valor limpo de UMA premissa, ou ValueError com a mensagem para a tela."""
    p = PREMISSAS[chave]
    if p.tipo == "escolha":
        if bruto not in p.opcoes:
            raise ValueError("escolha uma das opções: " + ", ".join(p.opcoes))
        return bruto
    try:
        v = _como_numero(bruto)
    except ValueError:
        raise ValueError("informe um número")
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("informe um número")
    esc = p.escala_ui
    lo, hi = p.minimo, p.maximo
    if lo is not None and (v < lo or (p.minimo_exclusivo and v == lo)):
        raise ValueError(f"precisa ser {'maior que' if p.minimo_exclusivo else 'no mínimo'} {lo * esc:g}")
    if hi is not None and (v > hi or (p.maximo_exclusivo and v == hi)):
        raise ValueError(f"precisa ser {'menor que' if p.maximo_exclusivo else 'no máximo'} {hi * esc:g}")
    return v


def validar(valores: dict) -> tuple:
    """(limpos, erros). `None` apaga a premissa e devolve ao padrão. Chave
    desconhecida é erro: uma gravação com erro de digitação não pode sumir em
    silêncio."""
    limpos, erros = {}, {}
    for chave, bruto in (valores or {}).items():
        if chave not in PREMISSAS:
            erros[chave] = "premissa desconhecida"
            continue
        if bruto is None:
            limpos[chave] = None
            continue
        try:
            limpos[chave] = validar_um(chave, bruto)
        except ValueError as e:
            erros[chave] = str(e)
    return limpos, erros


def aplicar(extra: dict, limpos: dict) -> dict:
    """Novo `extra`: mescla as premissas e preserva todo o resto (retenção etc.)."""
    novo = dict(extra or {})
    for chave, v in limpos.items():
        if v is None:
            novo.pop(chave, None)
        else:
            novo[chave] = v
    return novo


def descrever(extra: dict) -> list:
    """O que a tela mostra: valor efetivo, padrão e se foi informado."""
    saida = []
    for p in PREMISSAS.values():
        valor, definida = p.padrao, False
        if p.chave in (extra or {}):
            try:
                valor, definida = validar_um(p.chave, extra[p.chave]), True
            except ValueError:
                valor, definida = p.padrao, False      # guardado fora do limite: vale o padrão
        saida.append({
            "chave": p.chave, "rotulo": p.rotulo, "tipo": p.tipo, "descricao": p.descricao,
            "efeito": p.efeito, "ajuda_id": p.ajuda_id, "padrao": p.padrao, "valor": valor,
            "definida": definida, "minimo": p.minimo, "maximo": p.maximo,
            "minimo_exclusivo": p.minimo_exclusivo, "maximo_exclusivo": p.maximo_exclusivo,
            "opcoes": list(p.opcoes), "escala_ui": p.escala_ui, "sem_padrao_diz": p.sem_padrao_diz,
        })
    return saida
