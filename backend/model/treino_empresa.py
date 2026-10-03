"""
Treino de modelo por empresa, a partir de uma carteira histórica, sem guardá-la.

O arquivo entra como bytes, vira DataFrame, vira modelo — e some. Nada do
conteúdo vai para disco, para o banco ou para o log. O que fica registrado é o
que prova o treino sem identificar ninguém: SHA-256 do arquivo, contagens,
período, colunas, métricas e a distribuição de score em faixas (a do PSI).

Regras que não se negociam:

  - O alvo é pagamento REAL. Sem coluna de resultado, recusa. Nunca cai no alvo
    simulado do `train.py`, que serve para o modelo inicial e não mede nada.
  - Identificadores (CPF, nome, contato) saem do DataFrame antes de qualquer
    outra coisa. O modelo não precisa deles e não deve tê-los na memória.
  - Treinar NÃO ativa. O modelo novo fica guardado até o COMANDO ativar.
  - As métricas vêm de dados que o modelo não viu (o período mais recente, se
    houver data; senão uma fatia aleatória). O modelo que a empresa usa hoje é
    medido na mesma fatia, para a comparação ser justa.

Os mínimos abaixo são travas de engenharia, não afirmação estatística: com menos
que isso a métrica de teste oscila tanto que seria enganoso mostrá-la.
"""

import hashlib
import io
import logging
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import RobustScaler

log = logging.getLogger("mizan.treino")

MIN_LINHAS = 300
MIN_POR_CLASSE = 30
FRACAO_TESTE = 0.20
# Teto de linhas usadas no treino. Medido: 200 mil linhas levam o processo a
# ~410 MB (167 MB só de bibliotecas), o que não cabe com a API no ar nos 512 MB
# do plano gratuito. Acima do teto, treina com uma amostra aleatória (semente
# fixa) e diz isso. Em plano maior, sobe-se por MIZAN_TREINO_MAX_LINHAS.
MAX_LINHAS = int(os.getenv("MIZAN_TREINO_MAX_LINHAS", "100000"))
AMOSTRA_ESCALA = 50_000          # amostra para mediana/quartis do scaler
AMOSTRA_PARA_K = 20_000          # a escolha de k refaz o KMeans 9 vezes; em 200 mil linhas estoura a memória
LIMITE_VAZAMENTO = 0.90          # AUC de uma variável sozinha acima disso: provável cópia da resposta

ALIAS_ALVO = ("pagou", "pago", "paga", "quitou", "quitado", "pagamento", "recuperou", "recuperado")
ALIAS_DATA = ("data_referencia", "data_base", "data_inadimplencia", "data_vencimento",
              "data_atraso", "data")

# Saem do DataFrame logo na entrada.
IDENTIFICADORES = {"cpf", "cnpj", "nome", "nome_cliente", "email", "e-mail", "telefone", "celular",
                   "fone", "endereco", "endereço", "cep", "rg", "contrato", "numero_contrato"}
# Dizem o que aconteceu DEPOIS da cobrança: usadas como variável, o modelo "adivinha"
# olhando a resposta. Ficam fora das variáveis.
POS_DESFECHO = {"valor_recuperado", "valor_pago", "valor_pagamento", "data_pagamento", "pago_em",
                "data_quitacao", "quitacao", "recuperacao", "taxa_recuperada", "dias_ate_pagar"}

_VERDADEIRO = {"1", "true", "sim", "s", "yes", "y", "pago", "pagou", "quitado", "quitou", "recuperado"}
_FALSO = {"0", "false", "nao", "não", "n", "no", "nao pago", "não pago", "nao pagou", "não pagou",
          "inadimplente", "em aberto"}


class DadosInvalidos(ValueError):
    """Problema no arquivo enviado; a mensagem diz o que corrigir."""


def _norm(nome) -> str:
    return re.sub(r"\s+", "_", str(nome).strip().lower())


def ler_tabela(raw: bytes, nome_arquivo: str) -> pd.DataFrame:
    """CSV (',' ou ';', UTF-8 ou Latin-1) ou Excel. Tudo em memória."""
    if (nome_arquivo or "").lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw))
    amostra = raw[:4096].decode("utf-8", errors="ignore")
    cabecalho = amostra.splitlines()[0] if amostra else ""
    sep = ";" if cabecalho.count(";") > cabecalho.count(",") else ","
    try:
        return pd.read_csv(io.BytesIO(raw), sep=sep, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(raw), sep=sep, encoding="latin-1")


def _parse_alvo(serie: pd.Series) -> pd.Series:
    """0/1 com NaN onde o valor é vazio. Valor que não se sabe ler é erro, não palpite."""
    def um(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        t = str(v).strip().lower()
        if t == "" or t == "nan":
            return np.nan
        if t in _VERDADEIRO:
            return 1.0
        if t in _FALSO:
            return 0.0
        try:                                   # 1.0 / 0.0 vindos de planilha
            f = float(t.replace(",", "."))
            if f in (0.0, 1.0):
                return f
        except ValueError:
            pass
        return "?"
    r = serie.map(um)
    ruins = serie[r == "?"]
    if len(ruins):
        exemplos = sorted({str(x) for x in ruins.unique()[:5]})
        raise DadosInvalidos(
            f"A coluna de resultado tem valores que não sei interpretar: {exemplos}. "
            "Use sim/não, 1/0 ou verdadeiro/falso.")
    return r.astype(float)


def _preparar(df: pd.DataFrame) -> tuple:
    """Valida e devolve (df_limpo, y, datas|None, avisos, colunas_removidas)."""
    from model.train import _normalizar_colunas
    df = df.copy()
    df.columns = [_norm(c) for c in df.columns]
    avisos: list = []

    removidas = sorted(c for c in df.columns if c in IDENTIFICADORES)
    df = df.drop(columns=removidas)                      # antes de qualquer outra coisa
    df = _normalizar_colunas(df)

    alvo_col = next((c for c in ALIAS_ALVO if c in df.columns), None)
    if alvo_col is None:
        raise DadosInvalidos(
            "Não encontrei a coluna de resultado (se o devedor pagou). Esperava uma destas: "
            f"{', '.join(ALIAS_ALVO)}. Sem pagamento real não há o que treinar — "
            "o sistema não usa resultado simulado para treinar o modelo de um cliente.")
    falt = [c for c in ("valor_divida", "dias_em_atraso") if c not in df.columns]
    if falt:
        raise DadosInvalidos(f"Colunas obrigatórias ausentes: {falt}. Colunas recebidas: {list(df.columns)[:30]}")

    y = _parse_alvo(df[alvo_col])
    datas = None
    data_col = next((c for c in ALIAS_DATA if c in df.columns), None)
    if data_col is not None:
        d = pd.to_datetime(df[data_col], errors="coerce", dayfirst=True)
        if d.notna().mean() >= 0.8:
            datas = d
        else:
            avisos.append(f"A coluna '{data_col}' tem muitas datas ilegíveis; a validação não será temporal.")

    sem_alvo = int(y.isna().sum())
    manter = y.notna()
    if sem_alvo:
        avisos.append(f"{sem_alvo} linhas sem resultado foram ignoradas.")
    df, y = df.loc[manter].reset_index(drop=True), y.loc[manter].astype(int).reset_index(drop=True)
    if datas is not None:
        datas = datas.loc[manter].reset_index(drop=True)

    saida = [c for c in df.columns if c in POS_DESFECHO]
    if saida:
        avisos.append(f"Colunas que descrevem o que aconteceu depois da cobrança ficaram fora das variáveis: {saida}.")
    df = df.drop(columns=[alvo_col, data_col] if data_col else [alvo_col], errors="ignore")
    df = df.drop(columns=saida)

    n, pos = len(y), int(y.sum())
    if n < MIN_LINHAS:
        raise DadosInvalidos(f"Poucas linhas com resultado: {n} (mínimo {MIN_LINHAS}).")
    if min(pos, n - pos) < MIN_POR_CLASSE:
        raise DadosInvalidos(
            f"Resultado muito desbalanceado: {pos} pagaram e {n - pos} não pagaram "
            f"(mínimo {MIN_POR_CLASSE} de cada).")
    return df, y, datas, avisos, removidas


def _suspeitas_de_vazamento(X: pd.DataFrame, y: np.ndarray) -> list:
    """Variável que, sozinha, separa pagantes de não pagantes quase perfeitamente."""
    achadas = []
    for col in X.columns:
        try:
            v = X[col].astype(float).to_numpy()
            if np.nanstd(v) == 0:
                continue
            auc = roc_auc_score(y, np.nan_to_num(v))
            if max(auc, 1 - auc) >= LIMITE_VAZAMENTO:
                achadas.append(col)
        except Exception:
            continue
    return achadas


def _ajustar(df: pd.DataFrame, y: np.ndarray):
    """Treina KMeans + HistGB (+ Platt) e devolve (clf, kmeans, meta, X_clf)."""
    from model.retrain import _preprocessar, _escolher_k, MODEL_VERSION
    from model.train import _gerar_labels_clusters
    X, numericas, cat_cols, medians, modes = _preprocessar(df.copy())
    # Mediana e quartis de uma amostra de 50 mil linhas são praticamente os da
    # base inteira; ajustar o scaler na base toda copiava e ordenava cada coluna
    # (medido: +68 MB em 160 mil linhas) por uma diferença que não importa.
    rng = np.random.default_rng(42)
    scaler = RobustScaler().fit(X.iloc[rng.choice(len(X), size=min(len(X), AMOSTRA_ESCALA), replace=False)])
    Xs = scaler.transform(X)

    idx = rng.choice(len(Xs), size=min(len(Xs), AMOSTRA_PARA_K), replace=False)
    k = _escolher_k(Xs[idx])
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs[idx])
    clusters = kmeans.predict(Xs)

    df_cl = df.copy()
    if "comprometimento_renda" in X.columns:
        df_cl["comprometimento_renda"] = X["comprometimento_renda"].values
    df_cl["cluster"] = clusters
    labels = _gerar_labels_clusters(df_cl, k)

    X_clf = np.column_stack([Xs, clusters])
    n = len(y)
    params = dict(max_iter=200, max_depth=4, learning_rate=0.05,
                  min_samples_leaf=max(5, min(20, n // 50)), l2_regularization=1.0,
                  class_weight="balanced", random_state=42)
    clf = HistGradientBoostingClassifier(**params).fit(X_clf, y)
    final = clf
    if n >= 150:
        try:
            folds = max(2, min(5, int(y.sum()), int(n - y.sum())))
            final = CalibratedClassifierCV(HistGradientBoostingClassifier(**params),
                                           method="sigmoid", cv=folds).fit(X_clf, y)
        except Exception as e:
            log.warning("calibração ignorada: %s", e)
    meta = {
        "scaler": scaler, "cat_cols": cat_cols, "features_numericas": numericas,
        "features_categoricas": list(modes.keys()), "medians": medians, "modes": modes,
        "feature_names": list(X.columns) + ["cluster"], "cluster_labels": labels,
        "k": k, "model_version": MODEL_VERSION,
    }
    return final, kmeans, meta, X_clf, X


def _pontuar(clf, kmeans, meta, df: pd.DataFrame) -> np.ndarray:
    from model.score import _preprocessar_para_score
    Xs = meta["scaler"].transform(_preprocessar_para_score(df, meta))
    c = kmeans.predict(Xs)
    return clf.predict_proba(np.column_stack([Xs, c]))[:, 1]


def _metricas(y_true, p) -> dict:
    from model.diagnostico import _ks_gini
    y_true = np.asarray(y_true).astype(int)
    p = np.asarray(p, dtype=float)
    out = {"n_teste": int(len(y_true)), "taxa_pagamento_teste": round(float(y_true.mean()), 4)}
    kg = _ks_gini(y_true, p)
    out["ks"] = kg.get("ks")
    out["gini"] = kg.get("gini")
    out["auc"] = round(float(roc_auc_score(y_true, p)), 4)
    out["brier"] = round(float(brier_score_loss(y_true, p)), 4)
    return out


def treinar(conteudo: bytes, nome_arquivo: str, empresa_id: str, usuario_email: str = "",
            df: "pd.DataFrame | None" = None) -> dict:
    """Treina o modelo da empresa e o deixa guardado, inativo. Descarta os dados.

    Devolve o registro da versão. Levanta DadosInvalidos para erro do arquivo.
    """
    from model import modelos_empresa as me
    from model.psi import construir_referencia
    from model.score import score_carteira

    empresa_id = str(empresa_id or "").strip().lower()
    if not empresa_id:
        raise DadosInvalidos("Informe a empresa.")
    me.slug(empresa_id)                                # recusa id impossível antes de gastar tempo

    impressao = hashlib.sha256(conteudo).hexdigest()
    try:
        bruto = df if df is not None else ler_tabela(conteudo, nome_arquivo)
        n_recebidas, colunas_recebidas = len(bruto), len(bruto.columns)
        d, y, datas, avisos, removidas = _preparar(bruto)
        del bruto
    except DadosInvalidos:
        raise
    except Exception as e:
        raise DadosInvalidos(f"Não consegui ler o arquivo: {e}")
    # O arquivo cru não é mais necessário. `conteudo` pertence ao chamador, que o solta.

    y = y.to_numpy()
    n_validas = len(y)
    if n_validas > MAX_LINHAS:
        manter = np.sort(np.random.default_rng(42).choice(n_validas, size=MAX_LINHAS, replace=False))
        d, y = d.iloc[manter].reset_index(drop=True), y[manter]
        if datas is not None:
            datas = datas.iloc[manter].reset_index(drop=True)
        avisos.append(f"O arquivo tem {n_validas:,} linhas com resultado; o treino usou uma amostra "
                      f"aleatória de {MAX_LINHAS:,} (limite de memória do servidor).".replace(",", "."))
    n = len(y)
    if datas is not None:
        ordem = np.argsort(datas.to_numpy(), kind="stable")
        d, y, datas = d.iloc[ordem].reset_index(drop=True), y[ordem], datas.iloc[ordem].reset_index(drop=True)
        corte = int(n * (1 - FRACAO_TESTE))
        i_tr, i_te = np.arange(corte), np.arange(corte, n)
        validacao = "temporal"
    else:
        rng = np.random.default_rng(42)
        perm = rng.permutation(n)
        corte = int(n * (1 - FRACAO_TESTE))
        i_tr, i_te = perm[:corte], perm[corte:]
        validacao = "aleatoria"
        avisos.append("Sem coluna de data: a validação usa uma fatia aleatória, que tende a ser "
                      "mais favorável que a validação no tempo. Envie a data para uma medida mais honesta.")
    if min(int(y[i_tr].sum()), int(len(i_tr) - y[i_tr].sum())) < 2 or len(np.unique(y[i_te])) < 2:
        raise DadosInvalidos("O período de teste ficou com um só tipo de resultado; não dá para medir o modelo. "
                             "Envie um histórico mais longo.")

    # 1) o modelo "de teste": só viu o passado
    clf_t, km_t, meta_t, _, _ = _ajustar(d.iloc[i_tr], y[i_tr])
    p_novo = _pontuar(clf_t, km_t, meta_t, d.iloc[i_te])
    m_novo = _metricas(y[i_te], p_novo)

    # 2) o modelo que a empresa usa hoje, na MESMA fatia
    try:
        base = score_carteira(d.iloc[i_te].copy(), empresa_id)
        m_atual = _metricas(y[i_te], base["score_recuperabilidade"].to_numpy() / 100.0)
        m_atual["origem"] = "proprio" if me.tem_modelo_proprio(empresa_id) else "global"
    except Exception as e:
        m_atual = {"indisponivel": f"{type(e).__name__}"}

    # 3) o modelo que fica: aprende com tudo
    clf, kmeans, meta, X_clf, X = _ajustar(d, y)
    suspeitas = _suspeitas_de_vazamento(X, y)
    if suspeitas:
        avisos.append(f"Variáveis que separam pagantes de não pagantes quase sozinhas: {suspeitas}. "
                      "Podem conter a resposta; confirme com o banco antes de ativar.")
    if (m_novo.get("ks") or 0) > 50:
        avisos.append("KS acima de 50 costuma indicar vazamento de dados, não um modelo excelente.")

    meta["psi_referencia"] = construir_referencia(
        (clf.predict_proba(X_clf)[:, 1] * 100).round(1).tolist())
    versao = me.proxima_versao(empresa_id)
    meta["versao"] = versao
    me.salvar_artefatos(empresa_id, versao, clf, kmeans, meta)

    registro = {
        "versao": versao,
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "empresa_id": empresa_id,
        "treinado_por": usuario_email,
        "tipo_alvo": "real",
        "arquivo": {"nome": nome_arquivo, "sha256": impressao, "linhas_recebidas": n_recebidas,
                    "colunas_recebidas": colunas_recebidas},
        "n_amostras": n,
        "linhas_com_resultado": n_validas,
        "taxa_pagamento": round(float(y.mean()), 4),
        "periodo": ({"inicio": datas.min().date().isoformat(), "fim": datas.max().date().isoformat()}
                    if datas is not None else None),
        "validacao": validacao,
        "colunas_do_modelo": meta["feature_names"],
        "identificadores_removidos": removidas,
        "metricas": {"novo": m_novo, "atual": m_atual},
        "avisos": avisos,
        "promovido": False,
        "promovido_em": None,
        "dados_descartados": True,
    }
    dados = me.carregar_versoes(empresa_id)
    dados["versoes"].append(registro)
    me.salvar_versoes(empresa_id, dados)
    try:
        from storage_ml import upload_empresa
        upload_empresa(me.slug(empresa_id), me.pasta(empresa_id))
    except Exception as e:
        log.warning("upload ao Storage falhou: %s", e)
    return registro
