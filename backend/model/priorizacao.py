"""
Como a fila é ordenada — e o que cada critério custa.

Medir equidade (model/equidade.py) expôs um efeito que não é defeito de
implementação: ordenar por valor esperado desprioriza sistematicamente a
região de dívidas menores, mesmo quando ela paga igual. Valor esperado é
probabilidade vezes dívida, e dívida menor perde sempre. Como renda e tamanho
de dívida andam juntos, a fila que mais recupera também é a que menos atende
a carteira mais pobre.

Isso é uma escolha de política, não um bug, e o sistema não deve tomá-la
sozinho. Aqui ficam as duas, para a empresa configurar e para o backtest
medir o custo de cada uma.

  valor_esperado          Recupera mais. É o padrão. Ordena por
                          probabilidade × dívida, sem olhar região.

  proporcional_por_grupo  Cada região recebe uma fatia do esforço
                          proporcional ao seu tamanho na carteira, e dentro
                          dela vale o valor esperado. A paridade passa a
                          valer por construção; recupera-se menos, porque
                          contatos que iriam para dívidas grandes vão para
                          dívidas menores.

Nenhuma das duas é "a certa". A referência técnica coloca essa decisão na
governança de modelos, com comitê — o que este módulo faz é tornar as duas
executáveis e o custo mensurável.
"""

import numpy as np
import pandas as pd

CRITERIO_PADRAO = "valor_esperado"
CRITERIOS = ("valor_esperado", "proporcional_por_grupo")


def _valor_esperado(valor: np.ndarray, prob: np.ndarray) -> np.ndarray:
    return valor * prob


def ordenar(valor: np.ndarray, prob: np.ndarray,
            grupo: "np.ndarray | pd.Series | None" = None,
            criterio: str = CRITERIO_PADRAO) -> np.ndarray:
    """Índices da carteira na ordem de atendimento.

    Em 'proporcional_por_grupo', cada item recebe como chave a sua posição
    relativa dentro do próprio grupo — o terceiro de um grupo de dez vale
    0,25; o terceiro de um grupo de cem vale 0,025. Ordenar por essa chave faz
    com que, em QUALQUER ponto de corte da fila, cada região apareça na
    proporção do seu tamanho. Não é cota fixa numa capacidade escolhida: a
    proporção vale para qualquer capacidade.
    """
    ev = _valor_esperado(np.asarray(valor, dtype=float), np.asarray(prob, dtype=float))

    if criterio != "proporcional_por_grupo" or grupo is None:
        return np.argsort(-ev, kind="stable")

    g = pd.Series(np.asarray(grupo)).fillna("—").astype(str).to_numpy()
    chave = np.empty(len(ev), dtype=float)
    for valor_grupo in np.unique(g):
        pos = np.where(g == valor_grupo)[0]
        # dentro do grupo, melhor valor esperado primeiro
        ordem_interna = pos[np.argsort(-ev[pos], kind="stable")]
        n = len(ordem_interna)
        chave[ordem_interna] = (np.arange(n) + 0.5) / n

    # desempate por valor esperado, para a fila ser determinística
    return np.lexsort((-ev, chave))


def de_config(extra: "dict | None") -> str:
    """Critério configurado pela empresa; cai no padrão se não houver."""
    criterio = ((extra or {}).get("criterio_priorizacao") or "").strip()
    return criterio if criterio in CRITERIOS else CRITERIO_PADRAO
