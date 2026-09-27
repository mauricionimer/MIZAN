"""
Backtest de carteira histórica: o Mizan teria recuperado mais?

Recebe uma carteira em que a cobrança JÁ ACONTECEU e o desfecho é conhecido,
pontua como se fosse antes da cobrança e compara a fila que o Mizan teria
formado com a fila que a operação usa hoje.

A comparação que decide a conversa não é contra o acaso — é contra ordenar
por valor da dívida, que é o que a maioria das operações de cobrança faz.
Se o Mizan não ganhar disso na base do próprio cliente, ele não tem o que
vender, e este relatório diz isso com todas as letras.

    python backtest.py carteira_historica.csv

Colunas obrigatórias:
    cpf, valor_divida, dias_em_atraso, pagou
Colunas que melhoram a análise:
    renda_estimada, produto, uf, valor_recuperado
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# Capacidades operacionais típicas: com quantos por cento da carteira a
# operação consegue realmente falar num ciclo.
CAPACIDADES = [0.10, 0.20, 0.30, 0.50]

# Colunas que carregam a resposta. Pontuar com qualquer uma delas produz um
# KS altíssimo e um backtest que mente — é o erro clássico, e caro, porque só
# aparece quando o modelo vai para produção e não repete o resultado.
COLUNAS_VAZAMENTO = {
    "pagou", "valor_recuperado", "data_pagamento", "quitado", "liquidado",
    "status_pagamento", "recuperado", "valor_pago", "pago",
}

OBRIGATORIAS = {"cpf", "valor_divida", "dias_em_atraso", "pagou"}


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

def _normalizar_pagou(serie: pd.Series) -> pd.Series:
    """Aceita 1/0, true/false, sim/não, pago/não pago."""
    if serie.dtype == bool:
        return serie.astype(int)
    texto = serie.astype(str).str.strip().str.lower()
    positivos = {"1", "true", "t", "sim", "s", "y", "yes", "pago", "pagou", "quitado"}
    negativos = {"0", "false", "f", "nao", "não", "n", "no", "nao pagou", "não pagou",
                 "em aberto", "inadimplente"}
    convertido = texto.map(lambda v: 1 if v in positivos else (0 if v in negativos else None))
    if convertido.isna().any():
        numerico = pd.to_numeric(serie, errors="coerce")
        convertido = convertido.fillna((numerico > 0).astype(float))
    return convertido.fillna(0).astype(int)


def preparar(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Valida e normaliza a carteira. Devolve o df e os avisos encontrados."""
    from model.train import ALIASES

    avisos: list[str] = []
    df = df.rename(columns={c: ALIASES[c.lower().strip()]
                            for c in df.columns if c.lower().strip() in ALIASES})
    df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]

    faltando = OBRIGATORIAS - set(df.columns)
    if faltando:
        raise ValueError(
            f"Faltam colunas obrigatórias: {sorted(faltando)}. "
            f"Encontradas: {sorted(df.columns)}"
        )

    df = df.copy()
    df["pagou"] = _normalizar_pagou(df["pagou"])
    for col in ("valor_divida", "dias_em_atraso", "renda_estimada", "valor_recuperado"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "valor_recuperado" not in df.columns:
        # Sem o valor recuperado, assume-se recuperação integral de quem pagou.
        # É premissa declarada, não medição — e o relatório diz isso.
        df["valor_recuperado"] = df["pagou"] * df["valor_divida"].fillna(0)
        avisos.append(
            "Coluna 'valor_recuperado' ausente: assumiu-se que quem pagou quitou "
            "integralmente. Os valores de recuperação são o teto, não o realizado."
        )

    n_pagou = int(df["pagou"].sum())
    if n_pagou == 0 or n_pagou == len(df):
        raise ValueError(
            f"A carteira precisa ter os dois desfechos. Encontrado: "
            f"{n_pagou} pagaram de {len(df)}."
        )
    if len(df) < 200:
        avisos.append(
            f"Carteira pequena ({len(df)} linhas). Os números servem de indício, "
            "não de validação — variação amostral domina abaixo de algumas "
            "centenas de casos."
        )
    return df, avisos


def detectar_vazamento(df: pd.DataFrame) -> list[str]:
    """Colunas que entregam o desfecho e não podem entrar na pontuação."""
    return sorted(c for c in df.columns
                  if c in COLUNAS_VAZAMENTO and c not in ("pagou", "valor_recuperado"))


# ---------------------------------------------------------------------------
# Filas concorrentes
# ---------------------------------------------------------------------------

def _captura_por_capacidade(df: pd.DataFrame, ordem: np.ndarray) -> dict:
    """Quanto se recupera trabalhando os N% do topo desta fila."""
    ordenado = df.iloc[ordem]
    total = float(df["valor_recuperado"].sum())
    saida = {}
    for cap in CAPACIDADES:
        n = max(1, int(round(len(df) * cap)))
        topo = ordenado.head(n)
        recuperado = float(topo["valor_recuperado"].sum())
        saida[cap] = {
            "n_trabalhados":   n,
            "valor_capturado": round(recuperado, 2),
            "pct_capturado":   round(100 * recuperado / total, 1) if total > 0 else 0.0,
            "pagantes":        int(topo["pagou"].sum()),
        }
    return saida


def comparar_filas(df: pd.DataFrame, score: np.ndarray, semente: int = 42) -> dict:
    """Mizan contra o que a operação já faz e contra o acaso.

    Duas filas do Mizan, de propósito. Ordenar por score é ordenar por
    PROBABILIDADE de pagar; o banco quer VALOR recuperado, e quem paga com
    mais frequência costuma dever menos. A fila por valor esperado
    (probabilidade × dívida) é a que responde à pergunta do banco.
    """
    rng = np.random.default_rng(semente)
    valor = df["valor_divida"].fillna(0).to_numpy()
    valor_esperado = (score / 100.0) * valor
    filas = {
        "mizan_score":    np.argsort(-score),
        "mizan_ev":       np.argsort(-valor_esperado),
        "maior_divida":   np.argsort(-valor),
        "aleatorio":      rng.permutation(len(df)),
        # teto teórico: fila perfeita, só para mostrar quanto do possível foi capturado
        "oraculo":        np.argsort(-df["valor_recuperado"].fillna(0).to_numpy()),
    }
    return {nome: _captura_por_capacidade(df, ordem) for nome, ordem in filas.items()}


def decis(df: pd.DataFrame, score: np.ndarray) -> list[dict]:
    """Taxa de pagamento por decil de score. Num bom modelo, cai de cima para baixo."""
    ordem = np.argsort(-score)
    ordenado = df.iloc[ordem].reset_index(drop=True)
    grupos = np.array_split(np.arange(len(ordenado)), 10)
    saida = []
    for i, idx in enumerate(grupos, start=1):
        if len(idx) == 0:
            continue
        faixa = ordenado.iloc[idx]
        saida.append({
            "decil":            i,
            "n":                len(faixa),
            "taxa_pagamento":   round(100 * float(faixa["pagou"].mean()), 1),
            "valor_recuperado": round(float(faixa["valor_recuperado"].sum()), 2),
            "score_medio":      round(float(score[ordem][idx].mean()), 1),
        })
    return saida


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def rodar(df: pd.DataFrame) -> dict:
    """Pontua a carteira e compara as filas. Não escreve nada no banco."""
    from model.diagnostico import _ks_gini
    from model.score import score_carteira

    df, avisos = preparar(df)
    vazando = detectar_vazamento(df)
    if vazando:
        avisos.append(
            f"Colunas removidas antes de pontuar por entregarem o desfecho: "
            f"{vazando}. Mantê-las produziria um KS alto e falso."
        )

    entrada = df.drop(columns=[c for c in ("pagou", "valor_recuperado", *vazando)
                               if c in df.columns])
    pontuado = score_carteira(entrada)
    score = pontuado["score_recuperabilidade"].astype(float).to_numpy()

    separacao = _ks_gini(df["pagou"].to_numpy(), score / 100.0)
    filas = comparar_filas(df, score)

    # A comparação que decide: ganhar de "maior dívida primeiro"
    ganho = {}
    for cap in CAPACIDADES:
        m = filas["mizan_ev"][cap]["valor_capturado"]
        v = filas["maior_divida"][cap]["valor_capturado"]
        ganho[cap] = {
            "mizan":        m,
            "maior_divida": v,
            "diferenca":    round(m - v, 2),
            "vantagem_pct": round(100 * (m - v) / v, 1) if v > 0 else None,
        }

    return {
        "n_devedores":        len(df),
        "n_pagaram":          int(df["pagou"].sum()),
        "taxa_pagamento":     round(100 * float(df["pagou"].mean()), 1),
        "valor_face":         round(float(df["valor_divida"].sum()), 2),
        "valor_recuperado":   round(float(df["valor_recuperado"].sum()), 2),
        "separacao":          separacao,
        "decis":              decis(df, score),
        "filas":              filas,
        "ganho_sobre_pratica_atual": ganho,
        "avisos":             avisos,
    }


def _brl(v: float) -> str:
    inteiro, _, cent = f"{v:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{cent}"


def relatorio(r: dict) -> str:
    """Relatório em texto, para ler no terminal ou colar numa apresentação."""
    L = []
    L.append("=" * 68)
    L.append("BACKTEST MIZAN — CARTEIRA HISTÓRICA")
    L.append("=" * 68)
    L.append(f"Devedores: {r['n_devedores']}   ·   Pagaram: {r['n_pagaram']} "
             f"({r['taxa_pagamento']}%)")
    L.append(f"Valor de face: {_brl(r['valor_face'])}   ·   "
             f"Recuperado: {_brl(r['valor_recuperado'])}")

    s = r["separacao"]
    L.append("")
    L.append("-- O score separa quem pagou de quem não pagou? ------------------")
    if s.get("ok") is False:
        L.append(f"   {s.get('motivo')}")
    else:
        L.append(f"   KS   {s['ks']:>5}  ({s['ks_leitura']})")
        L.append(f"   Gini {s['gini']:>5}  ({s['gini_leitura']})")
        if s.get("ks_leitura") == "suspeito":
            L.append("   ATENÇÃO: KS acima de 50 costuma ser vazamento de dados,")
            L.append("   não qualidade de modelo. Conferir as colunas de entrada.")

    L.append("")
    L.append("-- Taxa de pagamento por decil de score --------------------------")
    L.append("   (num modelo que funciona, a taxa cai do decil 1 para o 10)")
    for d in r["decis"]:
        barra = "█" * int(round(d["taxa_pagamento"] / 3))
        L.append(f"   {d['decil']:>2}º  {d['taxa_pagamento']:>5.1f}%  {barra}")

    L.append("")
    L.append("-- Quanto se recupera trabalhando só o topo da fila --------------")
    L.append(f"   {'capacidade':<13}{'Mizan (VE)':>12}{'só score':>11}"
             f"{'maior dívida':>15}{'acaso':>9}{'teto':>8}")
    for cap in CAPACIDADES:
        f = r["filas"]
        L.append(f"   {int(cap*100):>3}% da base"
                 f"{f['mizan_ev'][cap]['pct_capturado']:>12.1f}%"
                 f"{f['mizan_score'][cap]['pct_capturado']:>10.1f}%"
                 f"{f['maior_divida'][cap]['pct_capturado']:>14.1f}%"
                 f"{f['aleatorio'][cap]['pct_capturado']:>8.1f}%"
                 f"{f['oraculo'][cap]['pct_capturado']:>7.1f}%")
    L.append("   VE = valor esperado (probabilidade × dívida). 'Teto' é a fila")
    L.append("   perfeita, impossível na prática: mostra quanto do possível foi pego.")

    L.append("")
    L.append("-- Ganho sobre a prática atual (maior dívida primeiro) -----------")
    venceu = 0
    for cap in CAPACIDADES:
        g = r["ganho_sobre_pratica_atual"][cap]
        sinal = "+" if g["diferenca"] >= 0 else ""
        if g["diferenca"] > 0:
            venceu += 1
        pct = f"{sinal}{g['vantagem_pct']}%" if g["vantagem_pct"] is not None else "—"
        L.append(f"   {int(cap*100):>3}% da base: {sinal}{_brl(g['diferenca'])}  ({pct})")

    L.append("")
    if venceu == len(CAPACIDADES):
        L.append("   O Mizan recuperou mais em todas as capacidades testadas.")
    elif venceu == 0:
        L.append("   O Mizan NÃO superou a prática atual em nenhuma capacidade.")
        L.append("   Nesta carteira, ordenar por valor da dívida recupera mais.")
    else:
        L.append(f"   O Mizan superou a prática atual em {venceu} de "
                 f"{len(CAPACIDADES)} capacidades.")

    if r["avisos"]:
        L.append("")
        L.append("-- Ressalvas ----------------------------------------------------")
        for a in r["avisos"]:
            L.append(f"   · {a}")

    L.append("=" * 68)
    return "\n".join(L)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 2
    caminho = Path(sys.argv[1])
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}")
        return 1
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(caminho)
    else:
        df = pd.read_csv(caminho, sep=None, engine="python")
    print(relatorio(rodar(df)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
