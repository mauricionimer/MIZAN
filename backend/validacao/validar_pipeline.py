"""
Valida a máquina de métricas do Mizan numa base pública com desfecho conhecido.

Por que isto existe: o modelo do Mizan é treinado em dados simulados enquanto
não há resultado real de cliente. Métrica de modelo sintético não prova nada —
o gerador cria o alvo a partir das mesmas variáveis que o modelo lê, então ele
recupera a própria fórmula (AUC 0,998, que a tela marca como suspeito).

O que esta validação prova, e só isto: que o cálculo de KS, Gini e calibração
do Mizan produz números corretos quando aplicado a dados reais, e que o
algoritmo escolhido (HistGradientBoosting calibrado) rende mais do que uma
regressão logística no mesmo recorte.

O que NÃO prova: desempenho do Mizan em cobrança. A base usada é de concessão
— prevê calote de solicitante, não recuperação de inadimplente. São alvos
diferentes. Nenhum número daqui deve ser apresentado como performance do
produto na carteira de um cliente.

Base: Statlog German Credit Data. 1.000 casos, 20 atributos, alvo binário com
700 bons e 300 maus pagadores. A integridade é conferida em tempo de execução
contra esses valores publicados — se não bater, a validação aborta.

Uso:  python validacao/validar_pipeline.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.diagnostico import _ks_gini  # noqa: E402

URL = "https://raw.githubusercontent.com/selva86/datasets/master/GermanCredit.csv"
CACHE = Path(__file__).parent / "german_credit.csv"

# Valores publicados da base. Servem de verificação de integridade: se o
# arquivo baixado não bater com isto, não é o German Credit e a validação para.
ESPERADO = {"linhas": 1000, "colunas": 21, "bons": 700, "maus": 300}


def carregar() -> pd.DataFrame:
    if CACHE.exists():
        df = pd.read_csv(CACHE)
        print(f"Base em cache: {CACHE}")
    else:
        print(f"Baixando {URL}")
        df = pd.read_csv(URL)
        CACHE.write_text(df.to_csv(index=False))

    contagem = df["credit_risk"].value_counts().to_dict()
    real = {
        "linhas": len(df),
        "colunas": len(df.columns),
        "bons": contagem.get(1, 0),
        "maus": contagem.get(0, 0),
    }
    if real != ESPERADO:
        raise SystemExit(f"Base não confere com o German Credit publicado.\n  esperado: {ESPERADO}\n  obtido:   {real}")
    print(f"Integridade conferida: {real['linhas']} casos, {real['bons']} bons / {real['maus']} maus\n")
    return df


def preparar(df: pd.DataFrame):
    y = df["credit_risk"].astype(int).to_numpy()
    X = pd.get_dummies(df.drop(columns=["credit_risk"]), drop_first=False)
    return X.to_numpy(dtype=float), y


def avaliar(nome: str, y_true, y_proba) -> dict:
    sep = _ks_gini(y_true, y_proba)
    auc = roc_auc_score(y_true, y_proba)
    brier = brier_score_loss(y_true, y_proba)
    print(f"{nome}")
    print(f"  KS    {sep['ks']:5.1f}  ({sep['ks_leitura']})")
    print(f"  Gini  {sep['gini']:5.1f}  ({sep['gini_leitura']})")
    print(f"  AUC   {auc:5.3f}")
    print(f"  Brier {brier:5.3f}  (quanto menor, melhor calibrado)")
    print()
    return {"ks": sep["ks"], "gini": sep["gini"], "auc": auc, "brier": brier}


def main() -> None:
    df = carregar()
    X, y = preparar(df)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
    print(f"Treino: {len(y_tr)} · Teste: {len(y_te)} (nunca visto)\n")

    # Baseline: regressão logística, o padrão histórico de scorecard.
    esc = StandardScaler().fit(X_tr)
    lr = LogisticRegression(max_iter=2000).fit(esc.transform(X_tr), y_tr)
    base = avaliar("Baseline — regressão logística", y_te, lr.predict_proba(esc.transform(X_te))[:, 1])

    # Reprodução fiel do que model/train.py faz em produção: mesmos
    # hiperparâmetros, e — o que mais importa — a calibração ajustada num
    # recorte separado, nunca nos mesmos dados em que o modelo treinou.
    # Calibrar sobre a própria base de treino ensina o calibrador a confiar em
    # previsões já decoradas, e a calibração sai pior do que sem nenhuma.
    min_leaf = max(5, len(y_tr) // 30)
    params = dict(
        max_iter=200, max_depth=4, learning_rate=0.05,
        min_samples_leaf=min_leaf, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    )
    cal = CalibratedClassifierCV(
        HistGradientBoostingClassifier(**params), method="sigmoid", cv=5,
    ).fit(X_tr, y_tr)
    mizan = avaliar("Pipeline do Mizan — HistGradientBoosting calibrado (cv=5)", y_te, cal.predict_proba(X_te)[:, 1])

    # Método anterior, mantido como referência: o modelo base treinava em 80% e
    # os 20% restantes serviam só para calibrar. Foi esta comparação que
    # motivou a troca — a diferença não está no Platt, que é monotônico e não
    # altera ordenação, e sim nos dados que o modelo base deixa de ver.
    X_fit, X_cal, y_fit, y_cal = train_test_split(
        X_tr, y_tr, test_size=0.2, stratify=y_tr, random_state=42,
    )
    antigo = HistGradientBoostingClassifier(**params).fit(X_fit, y_fit)
    avaliar("  (referência) método anterior, holdout de 20%", y_te,
            CalibratedClassifierCV(FrozenEstimator(antigo), method="sigmoid").fit(X_cal, y_cal).predict_proba(X_te)[:, 1])

    print("─" * 62)
    print(f"Ganho de KS sobre o baseline: {mizan['ks'] - base['ks']:+.1f} pontos")
    print(f"Ganho de Gini:                {mizan['gini'] - base['gini']:+.1f} pontos")
    print(f"Diferença de Brier:           {mizan['brier'] - base['brier']:+.3f}")
    print()
    print("Lembrete: base de CONCESSÃO. Valida o cálculo das métricas e a")
    print("escolha do algoritmo, não o desempenho do Mizan em cobrança.")


if __name__ == "__main__":
    main()
