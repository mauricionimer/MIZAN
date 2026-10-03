"""
Diagnóstico de qualidade do modelo de crédito Mizan: mede o modelo EM USO.

Responde às perguntas que importam antes de mostrar o modelo pra um banco:
  - O modelo que pontua esta empresa separa quem paga de quem não paga?
  - A probabilidade que ele dá é confiável (calibração), ou só "parece" score?
  - Onde ele erra mais: falso positivo (achou que pagava e não pagou) ou o contrário?
  - O desempenho de agora bate com o medido no treino, ou caiu?

Antes, o diagnóstico treinava um modelo NOVO com os pagamentos de todas as
empresas e media esse modelo: dizia "como seria um modelo deste tipo com estes
dados", não "como está o modelo que decide hoje" (achado D6). Agora ele pontua,
com o modelo ativo da empresa (o próprio ou o geral), os devedores dela que têm
pagamento registrado, e compara com o que aconteceu.

Pagamentos que o modelo já viu no treino não servem para medi-lo: quando o
modelo ativo foi treinado com os pagamentos do Mizan, só entram os registrados
DEPOIS desse treino.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score, brier_score_loss, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score,
)

_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

MIN_AMOSTRAS_DIAGNOSTICO = 30

# Regra prática: gradient boosting raso (max_depth=4) pede >= ~20 amostras por
# feature codificada pra não decorar ruído. Abaixo disso, desconfie de qualquer métrica.
AMOSTRAS_POR_FEATURE_MINIMO = 20


def _matriz_confusao_dict(y_true, y_pred) -> dict:
    """Confusão 2x2 nomeada — mais legível que uma matriz crua no front."""
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "verdadeiro_positivo":  int(tp),   # previu que pagava, pagou
        "falso_positivo":       int(fp),   # previu que pagava, não pagou (custo: esforço de cobrança desperdiçado)
        "verdadeiro_negativo":  int(tn),   # previu que não pagava, não pagou
        "falso_negativo":       int(fn),   # previu que não pagava, pagou (custo: oportunidade perdida)
    }


def _ks_gini(y_true, y_proba) -> dict:
    """KS e Gini — o vocabulário que uma mesa de crédito usa para julgar modelo.

    KS (Kolmogorov-Smirnov): maior distância entre as curvas acumuladas de quem
    pagou e de quem não pagou, em escala 0–100. Responde "o modelo separa os
    dois grupos?", que é a pergunta que importa numa operação de fila: não se
    liga para a carteira inteira, liga-se para o topo dela.

    Gini: derivado do AUC por Gini = 2 × AUC − 1, em escala 0–100. Mesma
    informação do AUC, no vocabulário que o mercado pede.

    Réguas conforme o material de referência (design/MIZAN_REDESIGN não cobre
    isso; vem do documento de fundamentos de crédito):
      KS   < 20 fraco · 20–30 regular · 30–40 bom · 40–50 forte · > 50 suspeito
      Gini < 20 fraco · 20–40 regular · 40–60 bom · > 60 forte

    KS acima de 50 costuma indicar vazamento de dados — alguma variável que
    carrega a resposta —, por isso é sinalizado como suspeito, não como ótimo.
    """
    y_true = np.asarray(y_true).astype(int)
    y_proba = np.asarray(y_proba, dtype=float)

    if len(np.unique(y_true)) < 2:
        return {"ok": False, "motivo": "Holdout tem uma única classe; KS e Gini não se aplicam."}

    ordem = np.argsort(y_proba)
    y_ord = y_true[ordem]

    n_bons = int(y_ord.sum())          # pagou
    n_maus = int(len(y_ord) - n_bons)  # não pagou
    if n_bons == 0 or n_maus == 0:
        return {"ok": False, "motivo": "Holdout sem os dois desfechos; KS e Gini não se aplicam."}

    acum_bons = np.cumsum(y_ord) / n_bons
    acum_maus = np.cumsum(1 - y_ord) / n_maus
    distancias = np.abs(acum_bons - acum_maus)
    ks = round(float(distancias.max()) * 100, 1)

    auc = float(roc_auc_score(y_true, y_proba))
    gini = round((2 * auc - 1) * 100, 1)

    if ks > 50:
        leitura_ks = "suspeito"
    elif ks >= 40:
        leitura_ks = "forte"
    elif ks >= 30:
        leitura_ks = "bom"
    elif ks >= 20:
        leitura_ks = "regular"
    else:
        leitura_ks = "fraco"

    if gini >= 60:
        leitura_gini = "forte"
    elif gini >= 40:
        leitura_gini = "bom"
    elif gini >= 20:
        leitura_gini = "regular"
    else:
        leitura_gini = "fraco"

    return {
        "ok": True,
        "ks": ks,
        "ks_leitura": leitura_ks,
        "gini": gini,
        "gini_leitura": leitura_gini,
        "n_pagou": n_bons,
        "n_nao_pagou": n_maus,
    }


def _calibracao_por_faixa(y_true, y_proba, n_faixas: int = 5) -> list[dict]:
    """
    Reliability diagram simplificado: divide as previsões em faixas de probabilidade
    e compara a média prevista com a taxa real observada em cada faixa.
    Modelo bem calibrado: previsto ≈ observado em toda faixa.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_proba = np.asarray(y_proba, dtype=float)
    ordem = np.argsort(y_proba)
    faixas = np.array_split(ordem, min(n_faixas, len(ordem)))
    resultado = []
    for idx in faixas:
        if len(idx) == 0:
            continue
        resultado.append({
            "n":                 int(len(idx)),
            "prob_media_prevista": round(float(y_proba[idx].mean()), 3),
            "taxa_real_observada": round(float(y_true[idx].mean()), 3),
        })
    return resultado


def _modelo_em_uso(empresa_id: str) -> dict:
    """Qual modelo pontua a empresa hoje, e desde quando os pagamentos são inéditos para ele."""
    from model import modelos_empresa as me
    from model.retrain import _carregar_versoes
    ativa = me.versao_ativa(empresa_id) if me.tem_modelo_proprio(empresa_id) else None
    if ativa:
        reg = next((v for v in me.carregar_versoes(empresa_id).get("versoes", []) if v.get("versao") == ativa), {})
        viu_pagamentos = reg.get("origem") == "feedbacks"
        auc_treino = ((reg.get("metricas") or {}).get("novo") or {}).get("auc")
        return {"origem": "proprio", "versao": ativa, "tipo_alvo": reg.get("tipo_alvo"),
                "n_treino": reg.get("n_amostras"), "auc_no_treino": auc_treino,
                "inedito_desde": reg.get("criado_em") if viu_pagamentos else None}
    g = _carregar_versoes()
    ativa = g.get("versao_ativa", "v1_inicial")
    reg = next((v for v in g.get("versoes", []) if v.get("versao") == ativa), {})
    # versão geral de alvo real = treinada pelo retreino antigo, com os pagamentos do Mizan
    real = reg.get("tipo_alvo") == "real"
    return {"origem": "geral", "versao": ativa, "tipo_alvo": reg.get("tipo_alvo", "simulado"),
            "n_treino": reg.get("n_amostras"), "auc_no_treino": None,
            "inedito_desde": reg.get("criado_em") if real else None}


def avaliar_modelo_ativo(db, empresa_id: str) -> dict:
    """Mede o modelo que pontua `empresa_id` nos devedores dela com pagamento registrado."""
    from model import treino_feedbacks as tf
    from model.score import _carregar_modelos, score_carteira

    empresa = str(empresa_id or "").strip().lower()
    modelo = _modelo_em_uso(empresa)
    df, datas, _ = tf.datasets(db, [empresa]).get(empresa, (None, [], []))
    if df is not None and modelo["inedito_desde"]:
        novos = [d > modelo["inedito_desde"] for d in datas]
        df = df[novos].reset_index(drop=True)
    n = 0 if df is None else len(df)
    base = "depois_do_treino" if modelo["inedito_desde"] else "todos"
    if n < MIN_AMOSTRAS_DIAGNOSTICO or df["pagou"].nunique() < 2:
        return {
            "ok": False, "empresa_id": empresa, "modelo": modelo, "base": base, "n_amostras": n,
            "motivo": (
                f"Dados insuficientes para medir o modelo em uso: {n} devedores com pagamento registrado"
                + (" depois do treino dele" if base == "depois_do_treino" else "")
                + f" (mínimo: {MIN_AMOSTRAS_DIAGNOSTICO}, com quem pagou e quem não pagou)."
            ),
        }

    y = df["pagou"].astype(int).to_numpy()
    entrada = df.drop(columns=["pagou", "data_referencia"], errors="ignore")
    p = score_carteira(entrada, empresa or None)["score_recuperabilidade"].astype(float).to_numpy() / 100.0
    y_pred = (p >= 0.5).astype(int)
    precisao, revocacao, f1, _ = precision_recall_fscore_support(y, y_pred, average="binary", zero_division=0)
    auc = round(float(roc_auc_score(y, p)), 4)

    _, _, meta = _carregar_modelos(empresa or None)
    n_variaveis = len(meta.get("feature_names") or []) or None
    n_treino = modelo.get("n_treino")
    por_variavel = round(n_treino / n_variaveis, 1) if (n_treino and n_variaveis) else None

    return {
        "ok": True,
        "empresa_id": empresa,
        "modelo": modelo,
        "base": base,
        "n_amostras": n,
        "medicao": {
            "n_amostras": n,
            "acuracia": round(float(accuracy_score(y, y_pred)), 4),
            "auc_roc": auc,
            "precisao": round(float(precisao), 4),
            "revocacao": round(float(revocacao), 4),
            "f1": round(float(f1), 4),
            "brier_score": round(float(brier_score_loss(y, p)), 4),
            "matriz_confusao": _matriz_confusao_dict(y, y_pred),
            "taxa_pagamento": round(float(y.mean()), 4),
        },
        # o mesmo modelo, no teste feito quando foi treinado: se caiu muito, o
        # modelo decorou o treino ou a carteira mudou
        "comparacao_com_o_treino": ({"auc_no_treino": modelo["auc_no_treino"], "auc_agora": auc,
                                     "diferenca": round(modelo["auc_no_treino"] - auc, 4)}
                                    if modelo.get("auc_no_treino") is not None else None),
        "dados_do_treino": {"n_treino": n_treino, "n_variaveis": n_variaveis,
                            "amostras_por_variavel": por_variavel,
                            "adequado": (por_variavel >= AMOSTRAS_POR_FEATURE_MINIMO) if por_variavel else None},
        "separacao": _ks_gini(y, p),
        "calibracao_por_faixa": _calibracao_por_faixa(y, p),
    }
