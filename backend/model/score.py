import os
import threading
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent

# Fallbacks para modelos antigos sem metadata de features
_FEATURES_V1 = ["valor_divida", "renda_estimada", "dias_em_atraso", "comprometimento_renda"]
_FEATURES_V2 = [
    "valor_divida", "renda_estimada", "dias_em_atraso",
    "comprometimento_renda", "log_valor_divida", "log_renda", "valor_por_dia",
]
_CATS_V2 = ["produto", "status", "uf"]

# Guarda os três artefatos sob UMA chave: inserir uma chave em dict é atômico
# sob o GIL, então quem lê no fast path nunca vê o cache preenchido pela metade.
# (Outros módulos só chamam _cache.clear(), nunca leem as chaves.)
_cache: dict = {}
# Sem o lock, duas requisições simultâneas em cold start fariam o joblib.load
# em duplicado — ~800ms cada.
_cache_lock = threading.Lock()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    from model.train import ALIASES
    rename = {col: ALIASES[col.lower().strip()] for col in df.columns if col.lower().strip() in ALIASES}
    return df.rename(columns=rename) if rename else df


def _adicionar_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Converte None (SQL NULL) para NaN antes de qualquer operação numérica
    for col in ['valor_divida', 'renda_estimada', 'dias_em_atraso']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'valor_divida' in df.columns and 'renda_estimada' in df.columns:
        df['comprometimento_renda'] = (
            df['valor_divida'] / df['renda_estimada'].replace(0, np.nan)
        ).fillna(0).clip(0, 10)
    if 'valor_divida' in df.columns:
        df['log_valor_divida'] = np.log1p(df['valor_divida'].clip(0))
    if 'renda_estimada' in df.columns:
        df['log_renda'] = np.log1p(df['renda_estimada'].clip(0))
    if 'valor_divida' in df.columns and 'dias_em_atraso' in df.columns:
        df['valor_por_dia'] = df['valor_divida'] / (df['dias_em_atraso'] + 1)
    return df


def _carregar_modelos() -> tuple:
    modelos = _cache.get("modelos")
    if modelos is not None:
        return modelos

    with _cache_lock:
        # Outra thread pode ter carregado enquanto esperávamos o lock.
        modelos = _cache.get("modelos")
        if modelos is not None:
            return modelos

        arquivos = {
            "mizan_model.pkl": MODEL_DIR / "mizan_model.pkl",
            "kmeans.pkl":      MODEL_DIR / "kmeans.pkl",
            "scaler.pkl":      MODEL_DIR / "scaler.pkl",
        }
        ausentes = [nome for nome, path in arquivos.items() if not path.exists()]
        if ausentes:
            raise FileNotFoundError(2, "No such file or directory", str(MODEL_DIR / ausentes[0]))

        clf    = joblib.load(arquivos["mizan_model.pkl"])
        kmeans = joblib.load(arquivos["kmeans.pkl"])
        meta   = joblib.load(arquivos["scaler.pkl"])

        _cache["modelos"] = (clf, kmeans, meta)
        return clf, kmeans, meta


def _preprocessar_para_score(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    df = _normalizar_colunas(df)
    df = _adicionar_derivadas(df)
    df = df.copy()

    features_numericas   = meta.get("features_numericas")
    features_categoricas = meta.get("features_categoricas")
    medians = meta.get("medians", {})
    modes   = meta.get("modes", {})
    cat_cols = meta["cat_cols"]

    # Retrocompatibilidade com modelos antigos sem metadata de features
    if features_numericas is None:
        version = meta.get("model_version", 1)
        features_numericas = _FEATURES_V2 if version >= 2 else _FEATURES_V1
        # Prefere as chaves do dict de modos (salvas desde v1); cai para _CATS_V2 se ausente
        features_categoricas = list(modes.keys()) if modes else _CATS_V2

    # Garante colunas numéricas: imputa com mediana de treino se ausente
    for col in features_numericas:
        if col not in df.columns:
            df[col] = medians.get(col, 0.0)
        else:
            df[col] = df[col].fillna(medians.get(col, 0.0))

    # Garante colunas categóricas: imputa com moda de treino se ausente
    for col in features_categoricas:
        if col not in df.columns:
            df[col] = modes.get(col, "outro")
        else:
            df[col] = df[col].fillna(modes.get(col, "outro")).astype(str)

    if features_categoricas:
        df_enc = pd.get_dummies(df[features_categoricas], drop_first=False)
    else:
        df_enc = pd.DataFrame(index=df.index)

    # Alinha exatamente às colunas do treino
    df_enc = df_enc.reindex(columns=cat_cols, fill_value=0)

    return pd.concat([df[features_numericas], df_enc], axis=1)


# Features críticas: ausência ou valor zero degradam significativamente o score
_FEATURES_CRITICAS = ["valor_divida", "dias_em_atraso"]
_FEATURES_IMPORTANTE = ["renda_estimada"]


def _avaliar_qualidade_dados(df_original: pd.DataFrame) -> pd.Series:
    """
    Para cada linha, detecta features críticas ausentes ou zeradas.
    Retorna uma Series de strings descrevendo os problemas (vazia = sem problemas).
    """
    problemas = pd.Series([""] * len(df_original), index=df_original.index)

    for col in _FEATURES_CRITICAS:
        if col not in df_original.columns:
            problemas = problemas + f"{col} ausente; "
        else:
            col_num = pd.to_numeric(df_original[col], errors="coerce")
            mascara  = col_num.isna() | (col_num == 0)
            problemas[mascara] = problemas[mascara] + f"{col} zerado/nulo; "

    for col in _FEATURES_IMPORTANTE:
        if col not in df_original.columns:
            problemas = problemas + f"{col} ausente; "
        else:
            col_num = pd.to_numeric(df_original[col], errors="coerce")
            mascara  = col_num.isna() | (col_num == 0)
            problemas[mascara] = problemas[mascara] + f"{col} zerado/nulo; "

    return problemas.str.strip("; ")


# Quantas linhas pontuar por vez.
#
# A pontuação é o pico de memória da análise: medido numa carteira de 200 mil
# devedores, o processo saía de 167 MB para 542 MB — a matriz de features
# alargada pelo one-hot, a versão escalada em float64 e a entrada do
# classificador, todas vivas ao mesmo tempo e todas do tamanho da carteira.
#
# Cada linha é pontuada sozinha: o scaler é elementar, o KMeans e o
# predict_proba respondem por linha, e _preprocessar_para_score realinha às
# colunas do treino, então um lote não depende do que veio nos outros. Processar
# em blocos dá exatamente o mesmo resultado com o pico preso ao tamanho do bloco
# em vez do tamanho da carteira.
LOTE_SCORE = 20_000


def score_carteira(df: pd.DataFrame) -> pd.DataFrame:
    clf, kmeans, meta = _carregar_modelos()
    scaler = meta["scaler"]

    # Avalia qualidade dos dados ANTES de imputar — assim a flag reflete o CSV original
    avisos_qualidade = _avaliar_qualidade_dados(df)

    n = len(df)
    score = np.empty(n, dtype=float)
    clusters = np.empty(n, dtype=int)
    for inicio in range(0, n, LOTE_SCORE):
        fim = min(inicio + LOTE_SCORE, n)
        X_bloco  = _preprocessar_para_score(df.iloc[inicio:fim], meta)
        X_scaled = scaler.transform(X_bloco)
        c_bloco  = kmeans.predict(X_scaled)
        prob     = clf.predict_proba(np.column_stack([X_scaled, c_bloco]))[:, 1]
        clusters[inicio:fim] = c_bloco
        score[inicio:fim]    = (prob * 100).round(1)
        # Libera antes do próximo bloco: sem isto o pico voltaria a ser a soma
        # de dois blocos, que é pouco, mas é dobrar à toa.
        del X_bloco, X_scaled, prob

    resultado                           = df.copy()
    resultado["score_recuperabilidade"] = score
    resultado["cluster_id"]             = clusters
    cluster_labels                      = meta.get("cluster_labels", {})
    resultado["perfil_cluster"]         = [
        cluster_labels.get(int(c), f"Cluster {c}") for c in clusters
    ]
    # Flag de qualidade: True quando há features críticas ausentes/zeradas
    resultado["dados_incompletos"] = avisos_qualidade != ""
    resultado["aviso_dados"]       = avisos_qualidade

    return resultado


def _pontuar_registro(registro: dict, meta: dict, scaler, clf, kmeans, cluster_fixo: "int | None" = None):
    """Roda o pipeline de score para um único registro. Se cluster_fixo for dado,
    usa-o em vez de recalcular — necessário para isolar o efeito de UMA variável por vez."""
    df1 = pd.DataFrame([registro])
    X1 = _preprocessar_para_score(df1, meta)
    X1_scaled = scaler.transform(X1)
    cluster = cluster_fixo if cluster_fixo is not None else int(kmeans.predict(X1_scaled)[0])
    X_clf = np.concatenate([X1_scaled[0], [cluster]]).reshape(1, -1)
    prob = float(clf.predict_proba(X_clf)[0, 1])
    return round(prob * 100, 1), cluster


# Colunas derivadas são recalculadas a partir das colunas base a cada preprocessamento
# (ver _adicionar_derivadas) — "neutralizá-las" direto não tem efeito algum, porque o
# pipeline as sobrescreve de volta. Seu impacto já aparece embutido na variável base.
_FEATURES_DERIVADAS = {"comprometimento_renda", "log_valor_divida", "log_renda", "valor_por_dia"}


# ── Reason codes ────────────────────────────────────────────────────────────
# Tradução das variáveis do modelo para linguagem que vai ao operador, ao
# devedor e, se preciso, ao regulador — sem expor peso de modelo.
#
# Cada variável tem duas leituras, porque o mesmo fator pode pesar nos dois
# sentidos: 'negativo' quando derrubou o score, 'positivo' quando sustentou.
# Só entram variáveis que o modelo de fato usa; o que não estiver aqui cai no
# nome da própria variável, para nunca sumir da explicação silenciosamente.
REASON_CODES: dict[str, dict[str, str]] = {
    "dias_em_atraso": {
        "negativo": "Tempo de inadimplência elevado",
        "positivo": "Atraso recente, ainda no início da régua",
    },
    "score_bureau": {
        "negativo": "Histórico restritivo no mercado",
        "positivo": "Histórico favorável no mercado",
    },
    "valor_divida": {
        "negativo": "Valor da dívida acima do perfil da carteira",
        "positivo": "Valor da dívida dentro do perfil da carteira",
    },
    "renda_estimada": {
        "negativo": "Renda estimada abaixo do perfil da carteira",
        "positivo": "Renda estimada compatível com a dívida",
    },
    "comprometimento_renda": {
        "negativo": "Dívida alta em relação à renda estimada",
        "positivo": "Dívida proporcional à renda estimada",
    },
    "tentativas_contato": {
        "negativo": "Muitas tentativas de contato sem desfecho",
        "positivo": "Poucas tentativas de contato até aqui",
    },
    "promessa_quebrada": {
        "negativo": "Acordo anterior não cumprido",
        "positivo": "Sem acordo descumprido no histórico",
    },
    "produto": {
        "negativo": "Modalidade de crédito com recuperação historicamente menor",
        "positivo": "Modalidade de crédito com recuperação historicamente maior",
    },
    "status": {
        "negativo": "Situação cadastral desfavorável",
        "positivo": "Situação cadastral favorável",
    },
    "uf": {
        "negativo": "Região com recuperação historicamente menor",
        "positivo": "Região com recuperação historicamente maior",
    },
    "mes_analise": {
        "negativo": "Época do ano desfavorável à cobrança",
        "positivo": "Época do ano favorável à cobrança",
    },
}

# Abaixo disso a variável não explica nada de útil e só polui a leitura.
IMPACTO_MINIMO_REASON_CODE = 1.0

# Quantos motivos mostrar. Três é o que cabe numa justificativa legível sem
# virar despejo de modelo.
MAX_REASON_CODES = 3


def _reason_codes(contribuicoes: list[dict], limite: int = MAX_REASON_CODES) -> dict:
    """Converte as contribuições numéricas nos motivos que puxaram o score.

    Separa em dois grupos porque são perguntas diferentes: o que derrubou
    (o que o devedor precisaria mudar) e o que sustentou (o que pesa a favor).
    """
    def traduzir(c: dict) -> dict:
        impacto = c["impacto_pontos"]
        sentido = "negativo" if impacto < 0 else "positivo"
        textos = REASON_CODES.get(c["variavel"])
        return {
            "variavel": c["variavel"],
            "motivo": textos[sentido] if textos else c["variavel"].replace("_", " ").capitalize(),
            "impacto_pontos": impacto,
            "traduzido": textos is not None,
        }

    relevantes = [c for c in contribuicoes if abs(c["impacto_pontos"]) >= IMPACTO_MINIMO_REASON_CODE]
    negativos = sorted([c for c in relevantes if c["impacto_pontos"] < 0],
                       key=lambda c: c["impacto_pontos"])[:limite]
    positivos = sorted([c for c in relevantes if c["impacto_pontos"] > 0],
                       key=lambda c: -c["impacto_pontos"])[:limite]

    saida = {
        "desfavoraveis": [traduzir(c) for c in negativos],
        "favoraveis": [traduzir(c) for c in positivos],
        "impacto_minimo": IMPACTO_MINIMO_REASON_CODE,
    }

    # Score saturado (0 ou 100) zera toda contribuição: com a nota no teto ou
    # no chão, trocar uma variável sozinha não move nada, e o método ceteris
    # paribus não tem o que medir. Acontece sobretudo com modelo treinado em
    # dados simulados, que separa artificialmente bem. Melhor dizer isso do que
    # devolver uma lista vazia sem explicação.
    if not saida["desfavoraveis"] and not saida["favoraveis"]:
        saida["motivo"] = (
            "Nenhuma variável isolada altera este score de forma relevante. "
            "Ocorre quando a nota está no extremo da escala: com o score saturado, "
            "mudar um fator por vez não desloca o resultado. A explicação volta a "
            "existir quando o modelo produzir notas mais graduadas."
        )
    return saida


def explicar_predicao(registro: dict) -> dict:
    """
    Explicação local do score de UM devedor: para cada variável do modelo, compara o
    score real com o score que o registro teria se aquela variável, isoladamente, fosse
    substituída pela referência da população de treino (mediana para numéricas, moda para
    categóricas) — mantendo as demais variáveis e o cluster fixos. A diferença é o quanto
    aquela variável específica empurrou o score deste CPF para cima ou para baixo.

    Não usa nenhuma biblioteca de explicabilidade externa — é um "what-if" (ceteris
    paribus) direto sobre o próprio modelo em produção.
    """
    clf, kmeans, meta = _carregar_modelos()
    scaler = meta["scaler"]

    features_numericas = meta.get("features_numericas") or _FEATURES_V2
    features_categoricas = meta.get("features_categoricas") or _CATS_V2
    medians = meta.get("medians", {})
    modes = meta.get("modes", {})

    reg_norm = _normalizar_colunas(pd.DataFrame([registro])).iloc[0].to_dict()

    score_real, cluster_real = _pontuar_registro(reg_norm, meta, scaler, clf, kmeans)

    contribuicoes = []
    for col in features_numericas:
        if col in _FEATURES_DERIVADAS:
            continue
        valor_real = reg_norm.get(col)
        referencia = medians.get(col, 0.0)
        reg_neutro = {**reg_norm, col: referencia}
        score_neutro, _ = _pontuar_registro(reg_neutro, meta, scaler, clf, kmeans, cluster_fixo=cluster_real)
        contribuicoes.append({
            "variavel": col,
            "tipo": "numerica",
            "valor_real": valor_real,
            "valor_referencia": referencia,
            "impacto_pontos": round(score_real - score_neutro, 1),
        })

    for col in features_categoricas:
        valor_real = str(reg_norm.get(col) or "")
        referencia = modes.get(col, "outro")
        if valor_real == referencia:
            impacto = 0.0
        else:
            reg_neutro = {**reg_norm, col: referencia}
            score_neutro, _ = _pontuar_registro(reg_neutro, meta, scaler, clf, kmeans, cluster_fixo=cluster_real)
            impacto = round(score_real - score_neutro, 1)
        contribuicoes.append({
            "variavel": col,
            "tipo": "categorica",
            "valor_real": valor_real,
            "valor_referencia": referencia,
            "impacto_pontos": impacto,
        })

    contribuicoes.sort(key=lambda c: abs(c["impacto_pontos"]), reverse=True)

    return {
        "score": score_real,
        "cluster_id": cluster_real,
        "contribuicoes": contribuicoes,
        "reason_codes": _reason_codes(contribuicoes),
    }
