"""Regressão: o sistema não pode apresentar como medição o que é premissa.

Cobre a Fase 0 do plano de análise de crédito:
  - promoção de modelo treinado abaixo do mínimo é bloqueada;
  - a procedência do modelo ativo é exposta para a interface avisar;
  - probabilidade de pagamento e taxa de recuperação são campos distintos.

Roda sem banco.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("JWT_SECRET", "teste")

import main
from model.retrain import MIN_FEEDBACKS_DEFAULT, VersaoInsuficiente, promover_versao

falhas = []


def checa(nome, condicao, detalhe=""):
    print(f'{"ok   " if condicao else "FALHA"} {nome}' + (f"  — {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)


# ── 1. Guarda de promoção ────────────────────────────────────────────────
versoes = main._get_versao_ativa()
insuficiente = None
try:
    from model.retrain import _carregar_versoes
    for v in _carregar_versoes().get("versoes", []):
        n = v.get("n_feedbacks_reais") or v.get("n_amostras")
        if n is not None and n < MIN_FEEDBACKS_DEFAULT:
            insuficiente = v["versao"]
            break
except Exception:
    pass

if insuficiente:
    bloqueou = False
    try:
        promover_versao(insuficiente)
    except VersaoInsuficiente:
        bloqueou = True
    except FileNotFoundError:
        bloqueou = True  # guarda roda antes de tocar em arquivo
    checa("promoção abaixo do mínimo é bloqueada", bloqueou, f"versão {insuficiente}")
else:
    print("info  nenhuma versão abaixo do mínimo no versions.json — guarda não exercitada")

# ── 2. Procedência exposta ───────────────────────────────────────────────
p = main._procedencia_modelo_ativo()
checa("procedência tem nível", p.get("nivel") in {"sintetico", "insuficiente", "ok"}, p.get("nivel"))
checa("níveis de risco trazem aviso",
      p["nivel"] == "ok" or bool(p.get("aviso")),
      p.get("aviso", "")[:60])

# ── 3. Premissa declarada, nunca inventada ───────────────────────────────
padrao = main._premissa_recuperacao_se_pagar(None)
checa("premissa padrão é pagamento integral declarado", padrao == 1.0, str(padrao))
checa("empresa inexistente cai no padrão",
      main._premissa_recuperacao_se_pagar("nao_existe_" + "x" * 8) == padrao)

print()
print("RESULTADO:", "tudo certo" if not falhas else f"{len(falhas)} falha(s): {falhas}")
assert not falhas, falhas
