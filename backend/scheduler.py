"""
Scheduler de retreinamento automático do Mizan.

Roda no mesmo processo do FastAPI — sem Redis, sem Celery, sem custo externo.
Usa APScheduler (BackgroundScheduler) para não bloquear o event loop do servidor.

Comportamento:
  1. A cada SCHEDULER_INTERVALO_HORAS horas, conta feedbacks novos desde o último treino
  2. Se n_novos >= SCHEDULER_MIN_FEEDBACKS → dispara retreinamento com auto_promover=True
  3. Estado em memória (reseta no restart) + log no console
"""

from datetime import datetime, timezone

# Estado em memória — consultado via GET /admin/scheduler/status
estado: dict = {
    "ativo":                     False,
    "intervalo_horas":           None,
    "min_feedbacks_para_treino": None,
    "ultima_verificacao":        None,
    "ultimo_resultado":          None,
    "proxima_verificacao":       None,
    "n_verificacoes":            0,
    "n_retreinamentos":          0,
}


def verificar_e_retreinar(min_feedbacks: int = 30) -> dict:
    """
    Verifica se há feedbacks suficientes desde o último retreinamento e retreina se necessário.
    Função síncrona — roda em thread de background (BackgroundScheduler).
    """
    from model.retrain import retreinar, _carregar_versoes
    from db import get_db

    agora = datetime.now(timezone.utc)
    estado["ultima_verificacao"] = agora.isoformat()
    estado["n_verificacoes"] += 1

    try:
        db = get_db()
        versoes = _carregar_versoes()

        # Timestamp do último retreinamento real (tipo_alvo = "real")
        ultimo_treino_em = None
        for v in reversed(versoes.get("versoes", [])):
            if v.get("tipo_alvo") == "real" and v.get("criado_em"):
                ultimo_treino_em = v["criado_em"]
                break

        # Conta feedbacks novos desde o último treino
        query = db.table("feedbacks").select("id", count="exact")
        if ultimo_treino_em:
            query = query.gt("created_at", ultimo_treino_em)
        res = query.execute()
        n_novos = res.count if res.count is not None else len(res.data)

        base = {
            "verificado_em":    agora.isoformat(),
            "n_feedbacks_novos": n_novos,
            "min_feedbacks":    min_feedbacks,
            "ultimo_treino_em": ultimo_treino_em,
        }

        print(f"[Scheduler] {agora.strftime('%H:%M:%S')} — {n_novos} feedbacks novos (mínimo: {min_feedbacks})")

        if n_novos < min_feedbacks:
            faltam = min_feedbacks - n_novos
            resultado = {**base, "acao": "aguardando", "retreinou": False,
                         "mensagem": f"Aguardando {faltam} feedbacks para próximo treino."}
            estado["ultimo_resultado"] = resultado
            return resultado

        print("[Scheduler] Disparando retreinamento automático...")
        retrain_result = retreinar(min_feedbacks=min_feedbacks, auto_promover=True)

        if retrain_result.get("ok") and retrain_result.get("promovido"):
            estado["n_retreinamentos"] += 1
            try:
                from model.score import _cache as _score_cache
                _score_cache.clear()
            except Exception:
                pass

        resultado = {
            **base,
            "acao":     "retreinou" if retrain_result.get("ok") else "falhou",
            "retreinou": retrain_result.get("ok", False),
            "retrain":  retrain_result,
        }
        estado["ultimo_resultado"] = resultado
        return resultado

    except Exception as e:
        resultado = {
            "verificado_em": agora.isoformat(),
            "acao":          "erro",
            "retreinou":     False,
            "erro":          str(e),
        }
        estado["ultimo_resultado"] = resultado
        print(f"[Scheduler] Erro: {e}")
        return resultado
