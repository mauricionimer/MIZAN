"""Divisão da fila entre operadores (docs/PLANO_OPERADOR.md, F1).

A fila chega ordenada pelo valor esperado. Repartir em blocos daria ao primeiro
operador só os melhores devedores; o rodízio em serpente (1,2,3,3,2,1,1,2,3…)
entrega a cada um uma fatia com o mesmo perfil de valor.
"""


def serpentina(ids_em_ordem: list, operadores: list) -> dict:
    """{operador: [ids]} — cada id vai para exatamente um operador."""
    if not operadores:
        raise ValueError("Escolha pelo menos um operador.")
    n = len(operadores)
    saida = {op: [] for op in operadores}
    for i, pid in enumerate(ids_em_ordem):
        volta, pos = divmod(i, n)
        op = operadores[pos] if volta % 2 == 0 else operadores[n - 1 - pos]
        saida[op].append(pid)
    return saida
