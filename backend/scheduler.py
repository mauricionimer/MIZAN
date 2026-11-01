"""Agenda avaliações do Cientista. Treino só acontece por execução aprovada."""
from datetime import datetime, timezone

MIN_NOVOS_PADRAO = 30
TRAVA_RETREINO = 'retreino'
DURACAO_TRAVA_MIN = 30
TRAVA_TREINO_EMPRESA = 'treino_modelo_empresa'
estado = {'ativo': False, 'intervalo_horas': None, 'min_feedbacks_para_treino': None,
          'ultima_verificacao': None, 'ultimo_resultado': None, 'proxima_verificacao': None,
          'n_verificacoes': 0, 'n_retreinamentos': 0}


def verificar_e_retreinar(min_feedbacks=MIN_NOVOS_PADRAO):
    """Nome mantido para compatibilidade com lifespan/status; não treina sozinho."""
    from db import get_db
    from model import treino_feedbacks as tf
    from aprendizado import servico, experimentos
    from aprendizado.dados import preparar
    from aprendizado.repositorio import Repositorio
    from travas import adquirir, liberar
    instante = datetime.now(timezone.utc)
    estado['ultima_verificacao'] = instante.isoformat()
    estado['n_verificacoes'] += 1
    if not adquirir(TRAVA_RETREINO, duracao_min=DURACAO_TRAVA_MIN):
        return {'acao': 'pulado', 'motivo': 'outra instância está verificando'}
    try:
        db = get_db()
        repo = Repositorio(db)
        datasets = tf.datasets(db)
        empresas = {str(c['empresa_id']).strip().lower() for c in tf._paginar(lambda: db.table('carteiras').select('id,empresa_id')) if c.get('empresa_id')}
        empresas |= set(datasets)
        por_empresa = {}
        for empresa in sorted(empresas):
            try:
                coorte = preparar(empresa, datasets.get(empresa), tf.ultimo_treino(empresa), min_feedbacks, instante)
                r = servico.avaliar(empresa, min_novos=min_feedbacks, repo=repo, coorte=coorte)
                experimentos.reconciliar(empresa, repo)
                experimentos.monitorar(empresa, repo)
                servico.monitorar_modelos(empresa, repo)
                por_empresa[empresa] = {'acao': r['tipo'], 'proposta_id': r['id'], 'status': r['status'], 'mensagem': r['dados']['por_que']}
            except Exception as e:
                por_empresa[empresa] = {'acao': 'erro', 'mensagem': type(e).__name__}
        resultado = {'acao': 'avaliado', 'verificado_em': instante.isoformat(), 'empresas': por_empresa,
                     'min_feedbacks': min_feedbacks, 'mensagem': 'Avaliações registradas. Treinos e experimentos exigem aprovação e execução no Laboratório.'}
    except Exception as e:
        resultado = {'acao': 'erro', 'erro': type(e).__name__, 'retreinou': False}
    finally:
        liberar(TRAVA_RETREINO)
    estado['ultimo_resultado'] = resultado
    return resultado
