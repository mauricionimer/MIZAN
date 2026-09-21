"""
PSI (Population Stability Index) — Mizan.

Responde a pergunta que nenhuma métrica de acerto responde: *a carteira que
estou analisando hoje ainda parece com aquela em que o modelo aprendeu?*

Importa porque a degradação por mudança de população é silenciosa. Nada quebra,
nenhum erro aparece: o modelo simplesmente passa a chutar. O caso clássico é o
cliente que começa a comprar carteira de cartão quando o modelo só viu
consignado — as notas continuam saindo, e continuam erradas.

Cálculo, sobre faixas de score definidas no treino:

    PSI = Σ (p_atual − p_treino) × ln(p_atual / p_treino)

Régua de mercado usada pela indústria de crédito:

    PSI < 0,10   população estável
    0,10 – 0,25  atenção
    PSI > 0,25   falha crítica — retreinar, e enquanto isso tratar o score
                 como ordenação grosseira, não como probabilidade

O PSI mede deslocamento de população, não perda de acurácia. Pode dar alto com
o modelo ainda acertando, e pode dar baixo com o modelo já ruim por outra razão
(mudança de comportamento com a mesma distribuição de entrada). É alarme de
"olhe para isto", não veredito.
"""

import math

# Cortes da régua de mercado.
PSI_ATENCAO = 0.10
PSI_CRITICO = 0.25

# Piso para proporção zero: sem ele, ln(0) ou divisão por zero derrubam o
# cálculo quando uma faixa fica vazia — o que é comum em carteira pequena.
_EPS = 1e-4

N_FAIXAS_PADRAO = 10


def construir_referencia(scores: list[float], n_faixas: int = N_FAIXAS_PADRAO) -> dict:
    """Congela a distribuição de score do treino, para comparações futuras.

    Guarda os limites das faixas e a proporção em cada uma. Os limites vêm dos
    quantis do próprio treino, então cada faixa nasce com peso parecido.
    """
    limpos = sorted(float(s) for s in scores if s is not None and not _nan(s))
    if len(limpos) < n_faixas:
        return {"ok": False, "motivo": f"Amostra insuficiente para {n_faixas} faixas: {len(limpos)}."}

    # Cortes internos por quantil (n_faixas - 1 cortes).
    cortes = []
    for i in range(1, n_faixas):
        pos = i * len(limpos) / n_faixas
        idx = min(int(pos), len(limpos) - 1)
        cortes.append(round(limpos[idx], 4))

    # Quantis repetidos viram faixa vazia; remove duplicatas mantendo a ordem.
    cortes = sorted(set(cortes))

    proporcoes = _distribuir(limpos, cortes)

    # Referência degenerada: quando o modelo separa demais, os scores empilham
    # nos extremos, os quantis colidem e as faixas somem ou ficam vazias. Medir
    # PSI contra isso acusa "crítico" para qualquer carteira, inclusive uma
    # idêntica ao treino — alarme que toca sempre é alarme que ninguém escuta.
    #
    # Os dois sinais são objetivos, não limiar arbitrário: faixas a menos
    # significa que os quantis colidiram, e faixa vazia significa que aquele
    # intervalo não existe na população de treino.
    faixas_perdidas = len(proporcoes) < n_faixas
    faixa_vazia     = any(p == 0 for p in proporcoes)
    if faixas_perdidas or faixa_vazia:
        motivos = []
        if faixas_perdidas:
            motivos.append(f"quantis colidiram ({len(proporcoes)} de {n_faixas} faixas)")
        if faixa_vazia:
            motivos.append("há faixa sem nenhum caso")
        return {
            "ok": False,
            "degenerada": True,
            "motivo": (
                "Distribuição de score concentrada demais para servir de referência: "
                + " e ".join(motivos)
                + ". Costuma indicar modelo que separa artificialmente bem — típico de "
                "treino em dados simulados. O PSI volta a fazer sentido quando o modelo "
                "for treinado com resultados reais."
            ),
            "cortes": cortes,
            "proporcoes": proporcoes,
            "n_referencia": len(limpos),
            "n_faixas": len(proporcoes),
        }

    return {
        "ok": True,
        "cortes": cortes,
        "proporcoes": proporcoes,
        "n_referencia": len(limpos),
        "n_faixas": len(proporcoes),
    }


def calcular(scores_atuais: list[float], referencia: dict) -> dict:
    """Compara a distribuição atual com a de referência e devolve o PSI."""
    if not referencia:
        return {"ok": False, "motivo": "Sem distribuição de referência gravada no modelo."}
    if not referencia.get("ok"):
        return {
            "ok": False,
            "degenerada": bool(referencia.get("degenerada")),
            "motivo": referencia.get("motivo") or "Referência de PSI indisponível.",
        }

    atuais = [float(s) for s in scores_atuais if s is not None and not _nan(s)]
    if len(atuais) < 20:
        return {"ok": False, "motivo": f"Amostra atual pequena demais para PSI: {len(atuais)}."}

    cortes = referencia["cortes"]
    p_ref = referencia["proporcoes"]
    p_atual = _distribuir(sorted(atuais), cortes)

    faixas, psi_total = [], 0.0
    for i, (a, r) in enumerate(zip(p_atual, p_ref)):
        a_ = max(a, _EPS)
        r_ = max(r, _EPS)
        contrib = (a_ - r_) * math.log(a_ / r_)
        psi_total += contrib
        faixas.append({
            "faixa": i + 1,
            "limite_inferior": None if i == 0 else cortes[i - 1],
            "limite_superior": None if i == len(p_ref) - 1 else cortes[i],
            "pct_treino": round(r * 100, 2),
            "pct_atual": round(a * 100, 2),
            "contribuicao": round(contrib, 4),
        })

    psi = round(psi_total, 4)
    if psi > PSI_CRITICO:
        nivel, leitura = "critico", "Mudança crítica de população — retreinar o modelo."
    elif psi > PSI_ATENCAO:
        nivel, leitura = "atencao", "Deslocamento relevante de população — acompanhar de perto."
    else:
        nivel, leitura = "estavel", "População estável em relação ao treino."

    return {
        "ok": True,
        "psi": psi,
        "nivel": nivel,
        "leitura": leitura,
        "n_atual": len(atuais),
        "n_referencia": referencia.get("n_referencia"),
        "corte_atencao": PSI_ATENCAO,
        "corte_critico": PSI_CRITICO,
        "faixas": faixas,
    }


def _distribuir(ordenados: list[float], cortes: list[float]) -> list[float]:
    """Proporção de valores em cada faixa delimitada por `cortes`."""
    n = len(ordenados)
    contagens = [0] * (len(cortes) + 1)
    for v in ordenados:
        i = 0
        while i < len(cortes) and v > cortes[i]:
            i += 1
        contagens[i] += 1
    return [c / n for c in contagens]


def _nan(v) -> bool:
    try:
        return v != v
    except TypeError:
        return True
