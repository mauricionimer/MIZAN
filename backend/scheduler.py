"""
Verificação automática de treino do Mizan, empresa por empresa.

Roda no mesmo processo do FastAPI — sem Redis, sem Celery, sem custo externo.
Usa APScheduler (BackgroundScheduler) para não bloquear o event loop do servidor.

Comportamento:
  1. A cada SCHEDULER_INTERVALO_HORAS horas, conta, para cada empresa, os
     pagamentos registrados desde o último treino dela com esses pagamentos
  2. Se a empresa tem SCHEDULER_MIN_FEEDBACKS ou mais novos, treina uma versão
     do modelo DELA com os pagamentos DELA (model/treino_feedbacks.py)
  3. Nada é ativado: a versão fica guardada para o COMANDO conferir as métricas
     e ativar em "Treinar modelo de uma empresa". O modelo geral não é tocado.

Antes, o agendador retreinava o modelo geral com os pagamentos de todas as
empresas juntos e o promovia sozinho (achado D1 do mapa do sistema).
"""

import os
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


# Nome da trava e por quanto tempo ela vale. O prazo cobre um retreino demorado
# com folga; passar disso significa que o processo morreu, e aí outra instância
# deve poder assumir em vez de o retreino parar para sempre.
# Pagamentos novos de uma empresa, desde o último treino dela, para treinar de
# novo. Sobe por SCHEDULER_MIN_FEEDBACKS. O treino ainda exige 300 devedores com
# resultado (treino_empresa.MIN_LINHAS); este número só evita gerar uma versão
# nova a cada punhado de pagamentos.
MIN_NOVOS_PADRAO = 30

TRAVA_RETREINO = "retreino"
DURACAO_TRAVA_MIN = 30


# A mesma trava do treino manual (main._TRAVA_TREINO): dois treinos ao mesmo
# tempo não cabem na memória do servidor.
TRAVA_TREINO_EMPRESA = "treino_modelo_empresa"


def verificar_e_retreinar(min_feedbacks: int = MIN_NOVOS_PADRAO) -> dict:
    """
    Treina, inativa, uma versão nova para cada empresa com pagamentos novos suficientes.
    Função síncrona — roda em thread de background (BackgroundScheduler).
    """
    from db import get_db
    from model import treino_feedbacks as tf
    from model.treino_empresa import DadosInvalidos
    from travas import adquirir, liberar

    agora = datetime.now(timezone.utc)
    estado["ultima_verificacao"] = agora.isoformat()
    estado["n_verificacoes"] += 1

    # Este agendador vive dentro do processo do app. Com duas instâncias, os
    # dois acordam no mesmo intervalo e disparariam o mesmo treino. A trava
    # elege um; os outros pulam o ciclo e tentam no próximo.
    if not adquirir(TRAVA_RETREINO, duracao_min=DURACAO_TRAVA_MIN):
        estado["ultimo_resultado"] = {"acao": "pulado", "motivo": "outra instância está verificando"}
        return {"acao": "pulado", "motivo": "trava em uso por outra instância"}

    try:
        por_empresa: dict = {}
        for empresa, (df, datas, precos) in sorted(tf.datasets(get_db()).items()):
            novos = tf.novos_desde(datas, tf.ultimo_treino(empresa))
            if novos < min_feedbacks:
                por_empresa[empresa] = {"acao": "aguardando", "novos": novos,
                                        "mensagem": f"Aguardando {min_feedbacks - novos} pagamentos novos."}
                continue
            if not adquirir(TRAVA_TREINO_EMPRESA, duracao_min=DURACAO_TRAVA_MIN):
                por_empresa[empresa] = {"acao": "pulado", "novos": novos,
                                        "mensagem": "Outro treino em andamento; tenta no próximo ciclo."}
                continue
            try:
                reg = tf.treinar(df, empresa, "treino automático", precos)
                por_empresa[empresa] = {"acao": "treinou", "novos": novos, "versao": reg["versao"],
                                        "mensagem": f"Versão {reg['versao']} treinada e guardada, inativa."}
                estado["n_retreinamentos"] += 1
            except DadosInvalidos as e:
                por_empresa[empresa] = {"acao": "dados_insuficientes", "novos": novos, "mensagem": str(e)}
            except Exception as e:
                por_empresa[empresa] = {"acao": "erro", "novos": novos, "mensagem": type(e).__name__}
                print(f"[Scheduler] Erro no treino de {empresa}: {type(e).__name__}")
            finally:
                liberar(TRAVA_TREINO_EMPRESA)
            del df, precos

        treinadas = [e for e, r in por_empresa.items() if r["acao"] == "treinou"]
        print(f"[Scheduler] {agora.strftime('%H:%M:%S')} — {len(por_empresa)} empresa(s) com pagamentos; "
              f"{len(treinadas)} treinada(s) (mínimo: {min_feedbacks})")
        if treinadas:
            admin_email = os.getenv("ADMIN_EMAIL", "")
            if admin_email:
                try:
                    from email_utils import email_retreino
                    email_retreino(admin_email, {e: por_empresa[e] for e in treinadas})
                except Exception as e:
                    print(f"[Scheduler] Erro ao enviar e-mail de treino: {type(e).__name__}")

        resultado = {
            "verificado_em": agora.isoformat(),
            "acao": "treinou" if treinadas else "aguardando",
            "min_feedbacks": min_feedbacks,
            "empresas": por_empresa,
            "mensagem": (f"Versões novas, ainda inativas, para: {', '.join(treinadas)}. "
                         "Confira e ative em Treinar modelo de uma empresa."
                         if treinadas else "Nenhuma empresa com pagamentos novos suficientes."),
        }
        estado["ultimo_resultado"] = resultado
        return resultado

    except Exception as e:
        resultado = {
            "verificado_em": agora.isoformat(),
            "acao":          "erro",
            "retreinou":     False,
            "erro":          type(e).__name__,
        }
        estado["ultimo_resultado"] = resultado
        print(f"[Scheduler] Erro: {type(e).__name__}")
        return resultado

    finally:
        # Devolve a trava mesmo quando o treino estoura: sem isto, um erro
        # bloquearia a verificação até o prazo vencer.
        liberar(TRAVA_RETREINO)
