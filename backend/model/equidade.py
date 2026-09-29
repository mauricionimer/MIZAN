"""
Equidade: o modelo trata grupos de forma desigual? E isso é discriminação?

A referência técnica é explícita sobre o risco (Volume 7, seção 32): um modelo
não precisa usar raça ou gênero para discriminar — basta usar uma variável
proxy. O exemplo que ela dá é o CEP, que separa bairro periférico de bairro
rico e produz o mesmo efeito sem nunca nomear o atributo protegido.

O Mizan usa `uf` como variável. É proxy geográfica mais grossa que CEP, mas
da mesma família, e é a única que dá para testar: o sistema não coleta raça,
gênero nem idade — o que é correto pela minimização da LGPD, e ao mesmo tempo
significa que NÃO É POSSÍVEL medir disparidade nesses eixos. Este módulo mede
o que existe e diz o que não consegue medir.

Duas medidas, e a diferença entre elas é o ponto:

  Paridade demográfica — a fatia priorizada é parecida entre os grupos?
    Diferença aqui pode ser legítima: se uma carteira regional realmente paga
    menos, priorizá-la menos é negócio, não preconceito.

  Igualdade de oportunidade — ENTRE QUEM PAGOU, a fatia priorizada é parecida?
    Esta controla a diferença legítima. Se entre os bons pagadores um grupo é
    sistematicamente deixado para trás, o modelo está falhando com ele — e aí
    não há justificativa de negócio.

Nenhuma das duas decide sozinha se houve discriminação. O módulo entrega os
números e a leitura; a decisão é do comitê, que é exatamente o que a
referência descreve na governança de modelos.
"""

import numpy as np
import pandas as pd

# O corte de 4/5 (80%) é a convenção mais usada no mercado para sinalizar
# impacto desproporcional. NÃO vem da referência técnica deste projeto nem da
# regulação brasileira — é prática consagrada de origem norte-americana
# (EEOC), adotada aqui como ponto de partida configurável, não como lei.
RAZAO_ATENCAO = 0.80

# Abaixo disto a taxa de um grupo é ruído: dez devedores viram 0% ou 100% por
# acaso, e comparar isso com um grupo de mil produziria alarme falso.
MINIMO_POR_GRUPO = 30


def _taxas(df: pd.DataFrame, atributo: str, selecionado: np.ndarray,
           subconjunto: "np.ndarray | None" = None) -> list[dict]:
    """Fatia selecionada de cada grupo, opcionalmente dentro de um subconjunto."""
    linhas = []
    for grupo, idx in df.groupby(atributo, dropna=False).groups.items():
        pos = df.index.get_indexer(idx)
        if subconjunto is not None:
            pos = pos[subconjunto[pos]]
        n = len(pos)
        if n == 0:
            continue
        n_sel = int(selecionado[pos].sum())
        linhas.append({
            "grupo": str(grupo),
            "n": n,
            "selecionados": n_sel,
            "taxa": round(n_sel / n, 4),
            "amostra_pequena": n < MINIMO_POR_GRUPO,
        })
    return sorted(linhas, key=lambda r: -r["taxa"])


def _comparar(linhas: list[dict], razao_atencao: float) -> dict:
    """Razão entre o grupo menos e o mais favorecido, ignorando os pequenos."""
    confiaveis = [r for r in linhas if not r["amostra_pequena"] and r["taxa"] > 0]
    if len(confiaveis) < 2:
        return {
            "ok": False,
            "motivo": ("Menos de dois grupos com amostra suficiente "
                       f"(mínimo de {MINIMO_POR_GRUPO} por grupo): não dá para comparar."),
        }
    maior, menor = confiaveis[0], confiaveis[-1]
    razao = round(menor["taxa"] / maior["taxa"], 4) if maior["taxa"] > 0 else None
    return {
        "ok": True,
        "razao": razao,
        "mais_favorecido": maior["grupo"],
        "menos_favorecido": menor["grupo"],
        "acima_do_corte": razao is not None and razao >= razao_atencao,
    }


def analisar(df: pd.DataFrame, atributo: str, selecionado: np.ndarray,
             pagou: "np.ndarray | None" = None,
             razao_atencao: float = RAZAO_ATENCAO) -> dict:
    """Paridade demográfica e, quando há desfecho, igualdade de oportunidade.

    `selecionado` é o vetor booleano de quem o sistema priorizou.
    `pagou` é o desfecho real, quando conhecido.
    """
    if atributo not in df.columns:
        return {"ok": False, "motivo": f"Coluna '{atributo}' não está na carteira."}

    selecionado = np.asarray(selecionado).astype(bool)
    df = df.reset_index(drop=True)

    paridade_linhas = _taxas(df, atributo, selecionado)
    paridade = {"grupos": paridade_linhas, **_comparar(paridade_linhas, razao_atencao)}

    oportunidade = None
    if pagou is not None:
        pagou = np.asarray(pagou).astype(bool)
        if pagou.sum() >= 2:
            linhas = _taxas(df, atributo, selecionado, subconjunto=pagou)
            oportunidade = {"grupos": linhas, **_comparar(linhas, razao_atencao)}
        else:
            oportunidade = {"ok": False, "motivo": "Poucos pagantes para comparar grupos."}

    avisos = []
    pequenos = [r["grupo"] for r in paridade_linhas if r["amostra_pequena"]]
    if pequenos:
        avisos.append(
            f"Grupos com menos de {MINIMO_POR_GRUPO} devedores ficaram fora da comparação, "
            f"porque a taxa deles é ruído: {', '.join(pequenos)}."
        )
    avisos.append(
        "O Mizan não coleta raça, gênero nem idade — correto pela minimização da LGPD, e "
        "por isso mesmo não há como medir disparidade nesses eixos. O que está medido aqui "
        f"é '{atributo}', que serve de proxy geográfica."
    )
    if oportunidade is None:
        avisos.append(
            "Sem o desfecho real, só dá para medir paridade demográfica. Diferença de "
            "priorização entre regiões pode ser legítima — uma carteira que paga menos é "
            "priorizada menos por razão de negócio. Para separar o legítimo do injusto é "
            "preciso a igualdade de oportunidade, que exige saber quem pagou."
        )

    return {
        "ok": True,
        "atributo": atributo,
        "razao_atencao": razao_atencao,
        "paridade_demografica": paridade,
        "igualdade_oportunidade": oportunidade,
        "avisos": avisos,
        "leitura": _ler(paridade, oportunidade, atributo, razao_atencao),
    }


def _ler(paridade: dict, oportunidade: "dict | None", atributo: str,
         razao_atencao: float) -> str:
    """A frase que resume, sem decidir pelo comitê."""
    if not paridade.get("ok"):
        return paridade.get("motivo", "Não foi possível comparar os grupos.")

    r = paridade["razao"]
    base = (f"Por {atributo}, o grupo menos priorizado ({paridade['menos_favorecido']}) "
            f"recebe {r:.0%} da atenção que o mais priorizado "
            f"({paridade['mais_favorecido']}) recebe.")

    if oportunidade and oportunidade.get("ok"):
        ro = oportunidade["razao"]
        paridade_ok = r >= razao_atencao
        if paridade_ok and ro >= razao_atencao:
            return (base + f" Entre quem de fato pagou, a proporção se mantém ({ro:.0%}). "
                    "As duas medidas estão acima do corte de atenção: não há diferença "
                    "relevante de tratamento entre as regiões desta carteira.")
        if ro >= razao_atencao:
            return (base + " Entre quem de fato pagou, porém, a priorização é equilibrada "
                    f"({ro:.0%}): a diferença acima acompanha diferença real de pagamento, "
                    "não um grupo sendo deixado para trás.")
        if paridade_ok:
            return (base + " A paridade está acima do corte, mas entre quem de fato pagou "
                    f"a diferença aparece ({ro:.0%}): bons pagadores de "
                    f"{oportunidade['menos_favorecido']} são priorizados menos que bons "
                    f"pagadores de {oportunidade['mais_favorecido']}. É o caso que a "
                    "paridade sozinha não pegaria, e pede revisão.")
        return (base + f" E entre quem de fato pagou a diferença permanece ({ro:.0%}): "
                f"bons pagadores de {oportunidade['menos_favorecido']} são priorizados "
                "menos que bons pagadores de "
                f"{oportunidade['mais_favorecido']}. Isso não se explica por diferença de "
                "comportamento e pede revisão.")

    if r >= razao_atencao:
        return base + " Está acima do corte de atenção usado no mercado."
    return (base + " Está abaixo do corte de atenção usado no mercado. Sozinho isso não "
            "prova discriminação: pode refletir diferença real de pagamento entre as "
            "carteiras. Para separar as duas coisas é preciso o desfecho real.")
