"""
Contextual Bandit para recomendação de abordagem de cobrança — Mizan.

Algoritmo: LinUCB (Linear Upper Confidence Bound)
  Contexto (d=8): score, dias_atraso, comprometimento, produto (one-hot × 4), bias
  Ações (12): 3 canais × 4 ofertas
  Recompensa: valor_recuperado / valor_divida  (0 se não pagou)

Persistência: Supabase (tabela bandit_estado) + arquivo local bandit.pkl como fallback.
O estado no Supabase garante que o aprendizado não se perde entre deploys.
"""

import os
from pathlib import Path

import joblib
import numpy as np

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR   = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent
BANDIT_FILE = MODEL_DIR / "bandit.pkl"

# ---------------------------------------------------------------------------
# Definição das 12 ações  (canal × oferta)
# ---------------------------------------------------------------------------

ACOES: list[dict] = [
    {"id":  0, "canal": "whatsapp", "oferta": "avista_10pct",   "label": "WhatsApp + 10% de desconto à vista"},
    {"id":  1, "canal": "whatsapp", "oferta": "parcelado_4x",   "label": "WhatsApp + parcelamento em 4x sem juros"},
    {"id":  2, "canal": "whatsapp", "oferta": "desconto_30pct", "label": "WhatsApp + 30% de desconto à vista"},
    {"id":  3, "canal": "whatsapp", "oferta": "parcelado_12x",  "label": "WhatsApp + parcelamento em 12x"},
    {"id":  4, "canal": "telefone", "oferta": "avista_10pct",   "label": "Telefone + 10% de desconto à vista"},
    {"id":  5, "canal": "telefone", "oferta": "parcelado_4x",   "label": "Telefone + parcelamento em 4x sem juros"},
    {"id":  6, "canal": "telefone", "oferta": "desconto_30pct", "label": "Telefone + 30% de desconto à vista"},
    {"id":  7, "canal": "telefone", "oferta": "parcelado_12x",  "label": "Telefone + parcelamento em 12x"},
    {"id":  8, "canal": "carta",    "oferta": "avista_10pct",   "label": "Carta/E-mail + 10% de desconto à vista"},
    {"id":  9, "canal": "carta",    "oferta": "parcelado_4x",   "label": "Carta/E-mail + parcelamento em 4x sem juros"},
    {"id": 10, "canal": "carta",    "oferta": "desconto_30pct", "label": "Carta/E-mail + 30% de desconto à vista"},
    {"id": 11, "canal": "carta",    "oferta": "parcelado_12x",  "label": "Carta/E-mail + parcelamento em 12x"},
]

N_ACOES = len(ACOES)
D       = 8   # dimensão do vetor de contexto

CANAL_LABELS = {
    "whatsapp": "WhatsApp",
    "telefone": "Ligação Telefônica",
    "carta":    "Carta / E-mail",
}
OFERTA_LABELS = {
    "avista_10pct":   "10% de desconto à vista",
    "parcelado_4x":   "Parcelamento em 4x sem juros",
    "desconto_30pct": "30% de desconto à vista",
    "parcelado_12x":  "Parcelamento em 12x",
}


# ---------------------------------------------------------------------------
# Algoritmo LinUCB
# ---------------------------------------------------------------------------

class LinUCB:
    """
    Linear Upper Confidence Bound para bandit contextual.
    Seleção: argmax_a [ theta_a · x  +  alpha * sqrt(x · A_a⁻¹ · x) ]
    """

    def __init__(self, n_acoes: int = N_ACOES, d: int = D, alpha: float = 1.0):
        self.n_acoes = n_acoes
        self.d       = d
        self.alpha   = alpha
        self.A       = [np.identity(d) for _ in range(n_acoes)]
        self.b       = [np.zeros(d)    for _ in range(n_acoes)]
        self.n_tentativas         = [0]   * n_acoes
        self.recompensa_acumulada = [0.0] * n_acoes

    def recomendar(self, contexto: np.ndarray) -> tuple[int, list[float]]:
        x      = contexto.astype(float)
        scores = []
        for a in range(self.n_acoes):
            A_inv   = np.linalg.inv(self.A[a])
            theta   = A_inv @ self.b[a]
            exploit = float(theta @ x)
            explore = self.alpha * float(np.sqrt(np.clip(x @ A_inv @ x, 0, None)))
            scores.append(exploit + explore)
        return int(np.argmax(scores)), scores

    def atualizar(self, acao: int, contexto: np.ndarray, recompensa: float) -> None:
        x            = contexto.astype(float)
        self.A[acao] += np.outer(x, x)
        self.b[acao] += recompensa * x
        self.n_tentativas[acao]         += 1
        self.recompensa_acumulada[acao] += recompensa

    def stats(self) -> list[dict]:
        return [
            {
                **ACOES[a],
                "n_tentativas":    self.n_tentativas[a],
                "recompensa_media": round(
                    self.recompensa_acumulada[a] / self.n_tentativas[a], 4
                ) if self.n_tentativas[a] > 0 else None,
            }
            for a in range(self.n_acoes)
        ]


# ---------------------------------------------------------------------------
# Serialização para JSON (Supabase)
# ---------------------------------------------------------------------------

def _bandit_para_json(bandit: LinUCB) -> dict:
    return {
        "A":                   [a.tolist() for a in bandit.A],
        "b":                   [b.tolist() for b in bandit.b],
        "n_tentativas":        bandit.n_tentativas,
        "recompensa_acumulada": bandit.recompensa_acumulada,
        "alpha":               bandit.alpha,
        "n_acoes":             bandit.n_acoes,
        "d":                   bandit.d,
    }


def _bandit_de_json(data: dict) -> LinUCB:
    bandit                      = LinUCB(n_acoes=data.get("n_acoes", N_ACOES),
                                         d=data.get("d", D),
                                         alpha=data.get("alpha", 1.0))
    bandit.A                    = [np.array(a) for a in data["A"]]
    bandit.b                    = [np.array(b) for b in data["b"]]
    bandit.n_tentativas         = data["n_tentativas"]
    bandit.recompensa_acumulada = data["recompensa_acumulada"]
    return bandit


# ---------------------------------------------------------------------------
# Persistência no Supabase
# ---------------------------------------------------------------------------

def _salvar_supabase(bandit: LinUCB) -> None:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from db import get_db
        get_db().table("bandit_estado").upsert(
            {"id": 1, "estado": _bandit_para_json(bandit)}
        ).execute()
    except Exception as e:
        print(f"[Bandit] Aviso: falha ao salvar no Supabase: {e}")


def _carregar_supabase() -> LinUCB | None:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from db import get_db
        res = get_db().table("bandit_estado").select("estado").eq("id", 1).execute()
        if res.data:
            return _bandit_de_json(res.data[0]["estado"])
    except Exception as e:
        print(f"[Bandit] Aviso: falha ao carregar do Supabase: {e}")
    return None


# ---------------------------------------------------------------------------
# Vetor de contexto
# ---------------------------------------------------------------------------

def construir_contexto(devedor: dict) -> np.ndarray:
    score  = float(devedor.get("score_recuperabilidade") or 50) / 100.0
    dias   = min(float(devedor.get("dias_em_atraso") or 0), 360) / 360.0
    comp   = min(float(devedor.get("comprometimento_renda") or 1.0), 3.0) / 3.0
    produto = str(devedor.get("produto") or "").lower()
    consignado = 1.0 if "consignado" in produto else 0.0
    veiculo    = 1.0 if "veiculo"    in produto else 0.0
    pessoal    = 1.0 if "pessoal"    in produto else 0.0
    cartao     = 1.0 if "cartao"     in produto else 0.0
    if not any([consignado, veiculo, pessoal, cartao]):
        pessoal = 1.0
    return np.array([score, dias, comp, consignado, veiculo, pessoal, cartao, 1.0])


# ---------------------------------------------------------------------------
# Singleton em memória + persistência dupla (Supabase + arquivo)
# ---------------------------------------------------------------------------

_bandit_cache: LinUCB | None = None


def carregar_bandit() -> LinUCB:
    global _bandit_cache
    if _bandit_cache is not None:
        return _bandit_cache
    # Supabase tem prioridade — persiste entre deploys
    bandit = _carregar_supabase()
    if bandit is None:
        bandit = joblib.load(BANDIT_FILE) if BANDIT_FILE.exists() else LinUCB()
    _bandit_cache = bandit
    return _bandit_cache


def salvar_bandit(bandit: LinUCB) -> None:
    global _bandit_cache
    try:
        joblib.dump(bandit, BANDIT_FILE)
    except Exception:
        pass
    _bandit_cache = bandit
    _salvar_supabase(bandit)


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def recomendar(devedor: dict) -> dict:
    bandit   = carregar_bandit()
    contexto = construir_contexto(devedor)
    acao_id, scores = bandit.recomendar(contexto)
    acao     = ACOES[acao_id]

    total_interacoes = sum(bandit.n_tentativas)
    n_acao           = bandit.n_tentativas[acao_id]

    if total_interacoes == 0:
        modo         = "exploração_inicial"
        justificativa = (
            "O sistema ainda está na fase de exploração — ainda não recebeu feedbacks reais. "
            "Esta recomendação é a melhor estimativa inicial com base no perfil do devedor."
        )
    elif n_acao < 3:
        modo         = "aprendendo"
        justificativa = (
            f"Recomendação com {total_interacoes} interações registradas. "
            f"Esta combinação ({CANAL_LABELS[acao['canal']]} + {OFERTA_LABELS[acao['oferta']]}) "
            "ainda tem poucas amostras — o sistema está explorando para calibrar."
        )
    else:
        recomp_media = bandit.recompensa_acumulada[acao_id] / n_acao
        modo         = "calibrado"
        justificativa = (
            f"Baseado em {n_acao} interações com perfis similares, "
            f"{CANAL_LABELS[acao['canal']]} + {OFERTA_LABELS[acao['oferta']]} "
            f"apresentou taxa de recuperação média de {recomp_media:.0%}. "
            "O sistema continua aprendendo com cada feedback recebido."
        )

    return {
        "acao_id":           acao_id,
        "canal":             acao["canal"],
        "canal_label":       CANAL_LABELS[acao["canal"]],
        "oferta":            acao["oferta"],
        "oferta_label":      OFERTA_LABELS[acao["oferta"]],
        "label":             acao["label"],
        "score_ucb":         round(scores[acao_id], 4),
        "contexto":          contexto.tolist(),
        "modo":              modo,
        "justificativa":     justificativa,
        "total_interacoes":  total_interacoes,
        "n_tentativas_acao": n_acao,
    }


def registrar_resultado(acao_id: int, contexto: list[float], recompensa: float) -> None:
    bandit = carregar_bandit()
    bandit.atualizar(acao_id, np.array(contexto, dtype=float), float(recompensa))
    salvar_bandit(bandit)
