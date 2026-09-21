"""Regressão das métricas de crédito da Fase 1: KS, Gini, PSI e reason codes.

Roda sem banco — exercita as funções puras com casos construídos.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("JWT_SECRET", "teste")

from model import psi
from model.diagnostico import _ks_gini
from model.score import REASON_CODES, _reason_codes

falhas = []


def checa(nome, cond, detalhe=""):
    print(f'{"ok   " if cond else "FALHA"} {nome}' + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas.append(nome)


rng = np.random.default_rng(42)

# ── KS e Gini ────────────────────────────────────────────────────────────
perfeito = _ks_gini(np.array([0] * 50 + [1] * 50), np.array([0.1] * 50 + [0.9] * 50))
checa("KS de separação perfeita é 100", perfeito["ks"] == 100.0)
checa("KS perfeito é sinalizado como suspeito, não como ótimo",
      perfeito["ks_leitura"] == "suspeito",
      "acima de 50 costuma ser vazamento de dados")

y = rng.integers(0, 2, 3000)
aleatorio = _ks_gini(y, rng.random(3000))
checa("KS de modelo aleatório fica perto de zero", aleatorio["ks"] < 10, f"KS={aleatorio['ks']}")
checa("Gini de modelo aleatório fica perto de zero", abs(aleatorio["gini"]) < 10, f"Gini={aleatorio['gini']}")

checa("Gini é coerente com AUC (2×AUC−1)",
      abs(perfeito["gini"] - 100.0) < 0.1)

checa("classe única é recusada, não estimada",
      _ks_gini(np.ones(30, dtype=int), rng.random(30))["ok"] is False)

# ── PSI ──────────────────────────────────────────────────────────────────
treino = list(rng.normal(50, 18, 3000).clip(0, 100))
ref = psi.construir_referencia(treino)
checa("referência bem distribuída é aceita", ref["ok"], f"{ref.get('n_faixas')} faixas")

igual = psi.calcular(list(rng.normal(50, 18, 1500).clip(0, 100)), ref)
checa("população igual dá PSI estável", igual["nivel"] == "estavel", f"PSI={igual['psi']}")

deslocada = psi.calcular(list(rng.normal(70, 18, 1500).clip(0, 100)), ref)
checa("população deslocada dispara crítico", deslocada["nivel"] == "critico", f"PSI={deslocada['psi']}")

degenerada = psi.construir_referencia(list(np.concatenate([np.zeros(1500), np.full(1500, 100.0)])))
checa("referência concentrada nos extremos é rejeitada",
      degenerada["ok"] is False and degenerada.get("degenerada") is True,
      "senão o alarme tocaria sempre")
checa("PSI sobre referência degenerada explica o motivo",
      "concentrada" in psi.calcular(treino, degenerada).get("motivo", ""))

# ── Reason codes ─────────────────────────────────────────────────────────
contribs = [
    {"variavel": "dias_em_atraso", "impacto_pontos": -88.1},
    {"variavel": "score_bureau", "impacto_pontos": -77.5},
    {"variavel": "produto", "impacto_pontos": -31.7},
    {"variavel": "renda_estimada", "impacto_pontos": 12.0},
    {"variavel": "mes_analise", "impacto_pontos": 0.2},
    {"variavel": "variavel_nova_sem_traducao", "impacto_pontos": -5.0},
]
rc = _reason_codes(contribs)
checa("limita a três motivos desfavoráveis", len(rc["desfavoraveis"]) == 3)
checa("ordena do mais forte para o mais fraco",
      rc["desfavoraveis"][0]["variavel"] == "dias_em_atraso")
checa("traduz para linguagem de negócio",
      rc["desfavoraveis"][0]["motivo"] == "Tempo de inadimplência elevado")
checa("separa o que sustentou o score",
      len(rc["favoraveis"]) == 1 and rc["favoraveis"][0]["variavel"] == "renda_estimada")
checa("descarta impacto irrelevante",
      all(c["variavel"] != "mes_analise" for c in rc["desfavoraveis"] + rc["favoraveis"]))

sem_traducao = _reason_codes([{"variavel": "variavel_nova_sem_traducao", "impacto_pontos": -5.0}])
checa("variável sem tradução aparece mesmo assim",
      sem_traducao["desfavoraveis"][0]["traduzido"] is False
      and sem_traducao["desfavoraveis"][0]["motivo"] != "",
      "nunca sumir da explicação em silêncio")

vazio = _reason_codes([{"variavel": "dias_em_atraso", "impacto_pontos": 0.0}])
checa("score saturado explica por que não há motivos", "motivo" in vazio)

checa("todo reason code tem as duas leituras",
      all({"negativo", "positivo"} <= set(v) for v in REASON_CODES.values()))

print()
print("RESULTADO:", "tudo certo" if not falhas else f"{len(falhas)} falha(s): {falhas}")
assert not falhas, falhas
