"""
Contextual Bandit para recomendação de abordagem de cobrança — Mizan.

Algoritmo: LinUCB (Linear Upper Confidence Bound)
  Contexto (d=14): score, dias_atraso, comprometimento, produto (one-hot × 4),
                   região (one-hot × 5), renda (log-normalizada), bias
  Ações (12): 3 canais × 4 ofertas
  Recompensa: valor_recuperado / valor_divida  (0 se não pagou)

Escopo: um bandit por empresa. Cada cliente aprende a própria política e os
feedbacks de um nunca influenciam as recomendações do outro.

Persistência: Supabase (bandit_estado, uma linha por empresa) + arquivo local
bandit_<empresa>.pkl como fallback. Cache em memória por empresa, TTL de 5 min,
para sincronizar entre réplicas via Supabase.
"""

import os
import threading
import time
from pathlib import Path

import joblib
import numpy as np

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
MODEL_DIR   = Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent

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
D       = 14  # score, dias, comprometimento, 4×produto, 5×região, renda, bias

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

_LOG_RENDA_MAX = np.log1p(10000.0)  # normalização log: log(R$10k)


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
        # recompensa_acumulada/n_tentativas é TAXA DE RECUPERAÇÃO esperada,
        # não probabilidade de pagamento: quem pagou metade da dívida entra
        # como 0,5. Para a PoP — P(pagou | oferta) — é preciso contar quantos
        # pagaram alguma coisa, que é o que n_pagamentos guarda.
        self.n_pagamentos         = [0]   * n_acoes

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

    def atualizar(self, acao: int, contexto: np.ndarray, recompensa: float,
                  pagou: "bool | None" = None) -> None:
        """`pagou` diz se houve pagamento. Sem ele, vale "recompensa > 0".

        Esse padrão contava como pagamento qualquer resultado com recompensa
        positiva, e os contatos "contactado" (0,05) e "prometeu pagar" (0,2) têm
        recompensa positiva sem ninguém ter pago. A chance de pagamento por oferta
        (`pop_por_oferta`) sai de n_pagamentos, então saía inflada por contatos.
        """
        x            = contexto.astype(float)
        self.A[acao] += np.outer(x, x)
        self.b[acao] += recompensa * x
        self.n_tentativas[acao]         += 1
        self.recompensa_acumulada[acao] += recompensa
        if (recompensa > 0) if pagou is None else pagou:
            self.n_pagamentos[acao]     += 1

    def stats(self) -> list[dict]:
        return [
            {
                **ACOES[a],
                "n_tentativas":     self.n_tentativas[a],
                "n_pagamentos":     self.n_pagamentos[a],
                "recompensa_media": round(
                    self.recompensa_acumulada[a] / self.n_tentativas[a], 4
                ) if self.n_tentativas[a] > 0 else None,
                "taxa_pagamento":   round(
                    self.n_pagamentos[a] / self.n_tentativas[a], 4
                ) if self.n_tentativas[a] > 0 else None,
            }
            for a in range(self.n_acoes)
        ]


# ---------------------------------------------------------------------------
# Serialização para JSON (Supabase)
# ---------------------------------------------------------------------------

def acao_id_de(canal: "str | None", oferta: "str | None") -> "int | None":
    """Id da ação do bandit para um par canal × oferta.

    É por aqui que a oferta escolhida na tela vira aprendizado: sem esse
    mapeamento o operador registra "ofereci 12x" e o bandit não tem como
    saber a qual das doze ações isso corresponde.
    """
    canal = (canal or "").strip().lower()
    oferta = (oferta or "").strip().lower()
    for a in ACOES:
        if a["canal"] == canal and a["oferta"] == oferta:
            return a["id"]
    return None


OFERTAS = [o for o in dict.fromkeys(a["oferta"] for a in ACOES)]


def _bandit_para_json(bandit: LinUCB) -> dict:
    return {
        "A":                    [a.tolist() for a in bandit.A],
        "b":                    [b.tolist() for b in bandit.b],
        # Cópias, não referências: sem isto o dicionário entregue ao cliente
        # HTTP compartilha as listas com o bandit vivo, e uma atualização em
        # outra thread pode ser serializada pela metade. Também fazia dois
        # bandits lidos do mesmo estado compartilharem contadores.
        "n_tentativas":         list(bandit.n_tentativas),
        "recompensa_acumulada": list(bandit.recompensa_acumulada),
        "n_pagamentos":         list(bandit.n_pagamentos),
        "alpha":                bandit.alpha,
        "n_acoes":              bandit.n_acoes,
        "d":                    bandit.d,
    }


def _bandit_de_json(data: dict) -> LinUCB:
    bandit                      = LinUCB(n_acoes=data.get("n_acoes", N_ACOES),
                                         d=data.get("d", D),
                                         alpha=data.get("alpha", 1.0))
    bandit.A                    = [np.array(a) for a in data["A"]]
    bandit.b                    = [np.array(b) for b in data["b"]]
    bandit.n_tentativas         = list(data["n_tentativas"])
    bandit.recompensa_acumulada = list(data["recompensa_acumulada"])
    # Estado gravado antes deste contador existir não sabe quantos pagaram.
    # Zerar seria mentir para menos, então fica ausente e a PoP daquelas
    # ofertas segue vindo do modelo até chegar feedback novo.
    bandit.n_pagamentos = list(data.get("n_pagamentos") or [0] * bandit.n_acoes)
    return bandit


# ---------------------------------------------------------------------------
# Persistência no Supabase
# ---------------------------------------------------------------------------

# Cada empresa aprende a sua própria política: o que funciona na carteira de
# um banco não vale para a de outro, e misturar os feedbacks vazaria
# comportamento de um cliente para outro. Quem chega sem empresa no contexto
# cai numa chave separada, nunca na de um cliente real.
EMPRESA_PADRAO = "_global"


def _chave(empresa_id: "str | None") -> str:
    return (empresa_id or "").strip().lower() or EMPRESA_PADRAO


def _arquivo_bandit(empresa_id: "str | None") -> Path:
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in _chave(empresa_id))
    return MODEL_DIR / f"bandit_{seguro}.pkl"


def _salvar_supabase(empresa_id: "str | None", bandit: LinUCB) -> None:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from db import get_db
        get_db().table("bandit_estado").upsert(
            {"empresa_id": _chave(empresa_id), "estado": _bandit_para_json(bandit)},
            on_conflict="empresa_id",
        ).execute()
    except Exception as e:
        print(f"[Bandit] Aviso: falha ao salvar no Supabase: {e}")


def _carregar_supabase(empresa_id: "str | None") -> "LinUCB | None":
    bandit, _ = _carregar_com_versao(empresa_id)
    return bandit


def _carregar_com_versao(empresa_id: "str | None") -> "tuple[LinUCB | None, int]":
    """O estado e a versão em que ele estava. A versão é o que permite gravar
    sem sobrescrever o trabalho de outro processo."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from db import get_db
        res = (get_db().table("bandit_estado").select("estado, versao")
               .eq("empresa_id", _chave(empresa_id)).limit(1).execute())
        if res.data:
            linha = res.data[0]
            return _bandit_de_json(linha["estado"]), int(linha.get("versao") or 0)
    except Exception as e:
        print(f"[Bandit] Aviso: falha ao carregar do Supabase: {e}")
    return None, 0


def _gravar_se_versao(empresa_id: "str | None", bandit: LinUCB, versao: int) -> bool:
    """Grava só se a versão ainda for a que foi lida. Devolve se conseguiu.

    O lock em memória protege uma máquina. Com duas instâncias, os dois
    processos leem o mesmo estado, cada um soma o próprio feedback e o último
    upsert apaga o do outro — sem erro, sem log, o aprendizado simplesmente
    some. Conferir a versão na cláusula do UPDATE transforma isso num conflito
    detectável, que o chamador refaz.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from db import get_db
        chave = _chave(empresa_id)
        db = get_db()
        res = (db.table("bandit_estado")
               .update({"estado": _bandit_para_json(bandit), "versao": versao + 1})
               .eq("empresa_id", chave).eq("versao", versao).execute())
        if res.data:
            return True
        # Nada atualizado: ou a linha ainda não existe, ou outro processo já
        # gravou. Só o primeiro caso é nosso para resolver.
        existe = (db.table("bandit_estado").select("empresa_id")
                  .eq("empresa_id", chave).limit(1).execute())
        if not existe.data:
            db.table("bandit_estado").insert(
                {"empresa_id": chave, "estado": _bandit_para_json(bandit), "versao": 1}
            ).execute()
            return True
        return False
    except Exception as e:
        print(f"[Bandit] Aviso: falha ao gravar no Supabase: {e}")
        # Falha de rede não é conflito: insistir refazendo a conta duplicaria o
        # feedback se a gravação tiver chegado. Encerra como sucesso e deixa o
        # cache em memória com o estado novo.
        return True


# ---------------------------------------------------------------------------
# Vetor de contexto
# ---------------------------------------------------------------------------

_UF_REGIAO: dict[str, str] = {
    "AC": "norte", "AM": "norte", "AP": "norte", "PA": "norte",
    "RO": "norte", "RR": "norte", "TO": "norte",
    "AL": "nordeste", "BA": "nordeste", "CE": "nordeste", "MA": "nordeste",
    "PB": "nordeste", "PE": "nordeste", "PI": "nordeste", "RN": "nordeste",
    "SE": "nordeste",
    "DF": "centro_oeste", "GO": "centro_oeste", "MS": "centro_oeste", "MT": "centro_oeste",
    "ES": "sudeste", "MG": "sudeste", "RJ": "sudeste", "SP": "sudeste",
    "PR": "sul", "RS": "sul", "SC": "sul",
}


def construir_contexto(devedor: dict) -> np.ndarray:
    """Constrói vetor de contexto d=14 para o LinUCB. Robusto a valores nulos."""
    def _safe_float(val, default: float) -> float:
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    score = _safe_float(devedor.get("score_recuperabilidade"), 50.0) / 100.0
    score = max(0.0, min(1.0, score))

    dias  = min(_safe_float(devedor.get("dias_em_atraso"), 0.0), 360.0) / 360.0

    comp  = min(_safe_float(devedor.get("comprometimento_renda"), 1.0), 3.0) / 3.0

    produto = str(devedor.get("produto") or "").lower()
    consignado = 1.0 if "consignado" in produto else 0.0
    veiculo    = 1.0 if "veiculo"    in produto else 0.0
    pessoal    = 1.0 if "pessoal"    in produto else 0.0
    cartao     = 1.0 if "cartao"     in produto else 0.0
    if not any([consignado, veiculo, pessoal, cartao]):
        pessoal = 1.0

    regiao       = _UF_REGIAO.get(str(devedor.get("uf") or "").upper(), "sudeste")
    norte        = 1.0 if regiao == "norte"        else 0.0
    nordeste     = 1.0 if regiao == "nordeste"     else 0.0
    centro_oeste = 1.0 if regiao == "centro_oeste" else 0.0
    sudeste      = 1.0 if regiao == "sudeste"      else 0.0
    sul          = 1.0 if regiao == "sul"           else 0.0

    # Normalização logarítmica: preserva informação acima de R$10k (não satura)
    renda_raw = max(0.0, _safe_float(devedor.get("renda_estimada"), 0.0))
    renda = min(np.log1p(renda_raw) / _LOG_RENDA_MAX, 1.0)

    return np.array([
        score, dias, comp,
        consignado, veiculo, pessoal, cartao,
        norte, nordeste, centro_oeste, sudeste, sul,
        renda,
        1.0,  # bias
    ], dtype=float)


# ---------------------------------------------------------------------------
# Singleton em memória com TTL — sincroniza entre replicas via Supabase
# ---------------------------------------------------------------------------

_bandit_cache: "dict[str, LinUCB]" = {}
_bandit_cache_ts: "dict[str, float]" = {}
_BANDIT_TTL: float = 300.0  # 5 minutos

# O bandit é um objeto global com ciclo ler -> alterar -> gravar
# (registrar_resultado, ajustar_alpha). Enquanto os endpoints eram async sem
# await, o event loop serializava tudo sozinho; rodando em threadpool, duas
# requisições simultâneas se sobrescreveriam e um feedback seria perdido.
# RLock porque registrar_resultado chama carregar_bandit e salvar_bandit,
# que também pegam o lock.
_bandit_lock = threading.RLock()

# Quantas vezes refazer a conta quando outro processo grava primeiro. Cada
# tentativa relê o estado atual, então poucas bastam: só perde a corrida de
# novo quem esbarra num terceiro feedback no mesmo instante.
MAX_TENTATIVAS_GRAVACAO = 5


def carregar_bandit(empresa_id: "str | None") -> LinUCB:
    chave = _chave(empresa_id)
    with _bandit_lock:
        agora = time.monotonic()
        em_cache = _bandit_cache.get(chave)
        if em_cache is not None and (agora - _bandit_cache_ts.get(chave, 0.0)) < _BANDIT_TTL:
            return em_cache
        # Cache expirado ou primeira carga — recarrega do Supabase
        bandit = _carregar_supabase(chave)
        if bandit is None:
            # Supabase indisponível: usa cache em memória se existir, senão arquivo local
            if em_cache is not None:
                return em_cache
            arq = _arquivo_bandit(chave)
            bandit = joblib.load(arq) if arq.exists() else LinUCB()
        _bandit_cache[chave] = bandit
        _bandit_cache_ts[chave] = agora
        return bandit


def salvar_bandit(empresa_id: "str | None", bandit: LinUCB) -> None:
    chave = _chave(empresa_id)
    with _bandit_lock:
        try:
            joblib.dump(bandit, _arquivo_bandit(chave))
        except Exception:
            pass
        _bandit_cache[chave]    = bandit
        _bandit_cache_ts[chave] = time.monotonic()  # reseta TTL após salvar
        _salvar_supabase(chave, bandit)


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------

def recomendar(devedor: dict, empresa_id: "str | None") -> dict:
    contexto = construir_contexto(devedor)
    # Leitura sob lock: atualizar() altera A, b e os contadores in-place, então
    # sem isso uma recomendação poderia ler A já atualizado e b ainda antigo.
    # Medido em 0,2ms — serializar aqui não é gargalo.
    with _bandit_lock:
        bandit = carregar_bandit(empresa_id)
        acao_id, scores = bandit.recomendar(contexto)
        total_interacoes = sum(bandit.n_tentativas)
        n_acao           = bandit.n_tentativas[acao_id]
        recomp_acumulada = bandit.recompensa_acumulada[acao_id]

    acao = ACOES[acao_id]

    if total_interacoes == 0:
        modo          = "exploração_inicial"
        justificativa = (
            "O sistema ainda está na fase de exploração — ainda não recebeu feedbacks reais. "
            "Esta recomendação é a melhor estimativa inicial com base no perfil do devedor."
        )
    elif n_acao < 3:
        modo          = "aprendendo"
        justificativa = (
            f"Recomendação com {total_interacoes} interações registradas. "
            f"Esta combinação ({CANAL_LABELS[acao['canal']]} + {OFERTA_LABELS[acao['oferta']]}) "
            "ainda tem poucas amostras — o sistema está explorando para calibrar."
        )
    else:
        recomp_media  = recomp_acumulada / n_acao
        modo          = "calibrado"
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


def registrar_resultado(acao_id: int, contexto: list[float], recompensa: float,
                        empresa_id: "str | None", pagou: "bool | None" = None) -> None:
    if not (0 <= acao_id < N_ACOES):
        print(f"[Bandit] ERRO: acao_id inválido: {acao_id} (válidos: 0–{N_ACOES-1}). Feedback ignorado.")
        return
    ctx = np.array(contexto, dtype=float)
    if len(ctx) != D:
        print(
            f"[Bandit] ERRO: contexto com {len(ctx)} dimensões (esperado D={D}). "
            "Feedback ignorado. Se D mudou, execute: DELETE FROM bandit_estado;"
        )
        return
    premio = float(np.clip(recompensa, 0.0, 1.0))
    chave = _chave(empresa_id)

    # Duas camadas, porque são dois problemas diferentes.
    #
    # O lock serializa as threads DESTE processo — sem ele, duas requisições no
    # threadpool leem o mesmo objeto em memória e uma sobrescreve a outra.
    #
    # A versão resolve o caso de duas INSTÂNCIAS: o lock de uma máquina não
    # significa nada para a outra. Cada tentativa relê do banco, refaz a conta
    # sobre o estado atual e só grava se ninguém tiver gravado no meio.
    with _bandit_lock:
        for tentativa in range(MAX_TENTATIVAS_GRAVACAO):
            bandit, versao = _carregar_com_versao(chave)
            if bandit is None:
                # Ainda não existe linha para esta empresa (ou o banco não
                # respondeu). Parte do que houver em memória e deixa
                # _gravar_se_versao decidir: ele insere quando a linha falta.
                bandit, versao = carregar_bandit(chave), 0
            bandit.atualizar(acao_id, ctx, premio, pagou=pagou)
            if _gravar_se_versao(chave, bandit, versao):
                _bandit_cache[chave]    = bandit
                _bandit_cache_ts[chave] = time.monotonic()
                try:
                    joblib.dump(bandit, _arquivo_bandit(chave))
                except Exception:
                    pass
                return
            # Perdeu a corrida: o próximo giro relê o estado já com o feedback
            # do outro processo dentro, e soma o nosso em cima.
        print(f"[Bandit] {MAX_TENTATIVAS_GRAVACAO} conflitos seguidos em {chave}; "
              "feedback não gravado no Supabase.")


# ---------------------------------------------------------------------------
# Funções de monitoramento
# ---------------------------------------------------------------------------

# Quantas observações "de mentira" o modelo vale ao estimar a PoP de uma
# oferta. Com zero feedback real, a estimativa é exatamente a do modelo; com
# K observações reais, fica na metade do caminho entre modelo e taxa medida;
# com muitas, a taxa medida domina.
#
# Isto é escolha de engenharia, não vem da referência técnica: ela diz que a
# PoP sai de um modelo treinado em resultado de renegociação, sem dizer como
# estimá-la com pouco dado. A suavização existe para não deixar "1 pagamento
# em 1 tentativa" virar 100% de chance, que é o que uma taxa crua faria.
K_SUAVIZACAO_POP = 10.0


def pop_por_oferta(empresa_id: "str | None", pop_base: float,
                   k: float = K_SUAVIZACAO_POP) -> dict:
    """Probabilidade de pagamento por tipo de oferta, a partir do feedback real.

    Agrega os três canais: a pergunta aqui é "qual a chance de pagar com esta
    oferta", não "por qual canal falar" — essa segunda o bandit responde
    separadamente em recomendar().

    Cada oferta volta com a origem e o número de observações que a sustentam,
    para a tela poder mostrar em que a estimativa se apoia em vez de exibir um
    número solto.
    """
    pop_base = float(min(1.0, max(0.0, pop_base)))
    with _bandit_lock:
        bandit = carregar_bandit(empresa_id)
        tentativas = list(bandit.n_tentativas)
        pagamentos = list(bandit.n_pagamentos)

    agregado: dict = {}
    for a in ACOES:
        o = agregado.setdefault(a["oferta"], {"n_tentativas": 0, "n_pagamentos": 0})
        o["n_tentativas"] += tentativas[a["id"]]
        o["n_pagamentos"] += pagamentos[a["id"]]

    saida = {}
    for oferta, o in agregado.items():
        n, pagos = o["n_tentativas"], o["n_pagamentos"]
        pop = (pagos + k * pop_base) / (n + k) if (n + k) > 0 else pop_base
        saida[oferta] = {
            "pop":            round(float(min(1.0, max(0.0, pop))), 4),
            "origem":         "bandit" if n > 0 else "modelo",
            "n_tentativas":   n,
            "n_pagamentos":   pagos,
            "taxa_observada": round(pagos / n, 4) if n > 0 else None,
            "pop_base":       round(pop_base, 4),
        }
    return saida


def convergencia_stats(empresa_id: "str | None") -> list[dict]:
    """
    Calcula incerteza (diagonal de A^{-1}) por ação para monitorar convergência.
    Incerteza alta = bandit ainda explorando. Abaixo de 0.01 com ≥10 tentativas = convergido.
    """
    result = []
    with _bandit_lock:
        bandit = carregar_bandit(empresa_id)
        for a in range(bandit.n_acoes):
            A_inv   = np.linalg.inv(bandit.A[a])
            theta   = A_inv @ bandit.b[a]
            incerteza = float(np.mean(np.diag(A_inv)))
            recomp_media = (
                bandit.recompensa_acumulada[a] / bandit.n_tentativas[a]
                if bandit.n_tentativas[a] > 0 else None
            )
            result.append({
                **ACOES[a],
                "n_tentativas":     bandit.n_tentativas[a],
                "recompensa_media": round(recomp_media, 4) if recomp_media is not None else None,
                "theta_norm":       round(float(np.linalg.norm(theta)), 4),
                "incerteza_media":  round(incerteza, 6),
                "convergido":       incerteza < 0.01 and bandit.n_tentativas[a] >= 10,
            })
    return result


def ajustar_alpha(novo_alpha: float, empresa_id: "str | None") -> float:
    """Ajusta o parâmetro de exploração e persiste. Retorna o valor efetivo aplicado."""
    alpha_efetivo = float(np.clip(novo_alpha, 0.1, 5.0))
    with _bandit_lock:
        bandit = carregar_bandit(empresa_id)
        bandit.alpha = alpha_efetivo
        salvar_bandit(empresa_id, bandit)
    return alpha_efetivo
