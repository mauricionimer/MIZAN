"""O Cientista propõe, um administrador aprova, código executa e registra."""
from datetime import timedelta
from aprendizado.dados import agora, data, preparar, hash_json
from aprendizado.repositorio import Conflito, fabrica


def modelo_referencia(empresa):
    from model import modelos_empresa as me
    ativa = me.carregar_versoes(empresa).get('versao_ativa')
    if ativa:
        return ativa
    from model.retrain import _carregar_versoes
    return 'global:' + str(_carregar_versoes().get('versao_ativa') or 'v1_inicial')


def carregar_coorte(empresa, min_novos=30, instante=None):
    from db import get_db
    from model import treino_feedbacks as tf
    return preparar(empresa, tf.datasets(get_db(), [empresa]).get(empresa),
                    tf.ultimo_treino(empresa), min_novos, instante)


def avaliar(empresa, ator='cientista:agendador', min_novos=30, repo=None, coorte=None, recomendacao=None):
    from model import modelos_empresa as me
    repo = repo or fabrica()
    conjunto, resumo = coorte if coorte is not None else carregar_coorte(empresa, min_novos)
    baseline = modelo_referencia(empresa)
    tipo = 'retreino_score' if resumo['apto'] else 'coleta_dados'
    dados = {'coorte': resumo, 'baseline': baseline,
             'recomendacao_origem': ({'id': recomendacao['id'], 'texto': recomendacao['texto'], 'selo': recomendacao['selo']} if recomendacao else None),
             'o_que_mudou': f"{resumo['novos']} resultados novos; {resumo['elegiveis']} pessoas elegíveis.",
             'o_que_fazer': 'Treinar uma versão candidata inativa e comparar no teste temporal.' if resumo['apto'] else 'Coletar e conferir os desfechos faltantes; nenhum treino autorizado.',
             'por_que': 'Critérios mínimos satisfeitos.' if resumo['apto'] else ' '.join(resumo['faltas']),
             'criterios': {'ativacao': 'exclusiva do COMANDO', 'auc_minima': .5, 'brier_maximo': .25,
                          'tolerancia_queda_auc': .02, 'tolerancia_aumento_brier': .02},
             'validade_ate': (agora() + timedelta(days=7)).isoformat()}
    import json
    from agente.cripto import cifrar
    dados['_snapshot_cifrado'] = cifrar(json.dumps(conjunto[0].attrs.get('manifesto_cientista', []), sort_keys=True, ensure_ascii=False, allow_nan=False))
    return repo.criar(empresa, tipo, hash_json([resumo['sha256'], resumo['minimos'], resumo['excluidos'], resumo['novos'], baseline, tipo, agora().date().isoformat()]), dados, ator)


def propor_experimento(empresa, ator, repo=None):
    from model import bandit
    repo = repo or fabrica()
    stats = bandit.convergencia_stats(empresa)
    # Explora apenas a seleção entre as ações existentes. Não altera limites de
    # negociação nem escreve recompensas inventadas no LinUCB.
    dados = {'hipotese': 'Aumentar moderadamente a exploração melhora recuperação sem reduzir pagamentos.',
             'o_que_mudou': 'Nova proposta de comparação controlada da exploração do LinUCB.',
             'o_que_fazer': 'Sortear pessoas entre LinUCB atual e exploração 10% maior por 60 dias.',
             'por_que': 'Medir com resultados reais antes de recomendar mudança permanente.',
             'metricas': ['taxa_pagamento', 'recuperacao_sobre_divida'], 'segmento': 'empresa inteira',
             'duracao_dias': 60, 'maturidade_dias': 30, 'multiplicador_exploracao': 1.1,
             'min_por_grupo': 30, 'queda_maxima': .05, 'stats_antes': stats,
             'parada': 'Prazo, solicitação humana ou IC95% de diferença de pagamentos inteiramente abaixo de -5 p.p.',
             'validade_ate': (agora() + timedelta(days=7)).isoformat()}
    # Uma proposta por empresa/dia; não duplica em clique repetido.
    return repo.criar(empresa, 'experimento_bandit', agora().date().isoformat(), dados, ator)


def decidir(empresa, id, decisao, ator, repo=None):
    if decisao not in ('aprovada', 'recusada'): raise ValueError('Escolha aprovada ou recusada.')
    repo = repo or fabrica()
    r = repo.obter(empresa, id)
    if r['tipo'] == 'coleta_dados' and decisao == 'aprovada':
        raise ValueError('Esta análise pede mais dados. Gere nova avaliação após coletá-los.')
    return repo.transicao(empresa, id, 'proposta', decisao, {'decidido_por': ator, 'decidido_em': agora().isoformat()}, ator, 'Decisão humana sobre a proposta registrada')


def comparar(reg, criterios):
    novo, atual = reg['metricas']['novo'], reg['metricas']['atual']
    faltas = []
    if reg.get('validacao') != 'temporal': faltas.append('Validação não temporal.')
    if (novo.get('auc') or 0) < criterios['auc_minima']: faltas.append('AUC abaixo do mínimo.')
    if novo.get('brier', 1) > criterios['brier_maximo']: faltas.append('Brier acima do máximo.')
    if any('vazamento' in a.lower() or 'KS acima' in a for a in reg.get('avisos', [])):
        faltas.append('Suspeita de vazamento de dados exige revisão.')
    comparavel = not atual.get('indisponivel') and not atual.get('em_amostra') and atual.get('auc') is not None
    if comparavel:
        if novo['auc'] < atual['auc'] - criterios['tolerancia_queda_auc']: faltas.append('Queda de AUC frente ao ativo.')
        if novo['brier'] > atual['brier'] + criterios['tolerancia_aumento_brier']: faltas.append('Piora de Brier frente ao ativo.')
    else:
        faltas.append('Baseline sem teste independente: não há evidência de melhora frente ao ativo.')
    return {'recomendacao': 'revisar' if faltas else 'avaliar_ativacao_comando', 'motivos': faltas,
            'metricas': reg['metricas'], 'avisos': reg.get('avisos', []), 'ativado': False}


def executar(empresa, id, ator, repo=None, carregar=None, treinar=None):
    from model import treino_feedbacks as tf, modelos_empresa as me
    from travas import adquirir, liberar
    repo = repo or fabrica()
    r = repo.obter(empresa, id)
    if r['status'] in ('concluida', 'em_observacao', 'encerrada'): return r
    if r['status'] not in ('aprovada', 'erro', 'executando'):
        raise Conflito('A execução exige aprovação humana.')
    if r['tipo'] == 'coleta_dados': raise ValueError('Coleta não autoriza treino.')
    trava = 'treino_modelo_empresa' if r['tipo'] == 'retreino_score' else f'cientista_experimento:{empresa}'
    if not adquirir(trava, duracao_min=120): raise Conflito('Outra execução em andamento; tente novamente depois.')
    try:
        # Recupera conclusão após queda entre persistir o modelo e registrar o
        # relatório; não repete um treino que já produziu artefato versionado.
        versoes = me.carregar_versoes(empresa)
        existente = next((v for v in versoes['versoes'] if v.get('cientista_acao_id') == id), None)
        if existente:
            if r['status'] != 'executando':
                r = repo.transicao(empresa, id, r['status'], 'executando', {}, ator, 'Recuperação do artefato já produzido')
            return _concluir(repo, r, existente, ator)
        if r['status'] == 'executando':
            # Uma execução interrompida sem artefato concluído fica visível e
            # exige nova tentativa explícita, após registrar a interrupção.
            return repo.transicao(empresa, id, 'executando', 'erro', {'erro': 'Execução interrompida sem artefato concluído.'}, ator, 'Recuperação; a próxima tentativa será explícita')
        d = r['dados']
        expirou = data(d['validade_ate']) < agora()
        coorte = None
        if r['tipo'] == 'retreino_score':
            coorte, resumo = (carregar or carregar_coorte)(empresa, d['coorte']['minimos']['novos'])
            expirou = expirou or not resumo['apto'] or resumo['sha256'] != d['coorte']['sha256'] or resumo['minimos'] != d['coorte']['minimos'] or modelo_referencia(empresa) != d['baseline']
        if expirou:
            return repo.transicao(empresa, id, r['status'], 'expirada', {}, ator, 'Prazo, dados ou baseline mudaram: gere nova proposta')
        r = repo.transicao(empresa, id, r['status'], 'executando', {'iniciado_em': agora().isoformat()}, ator, 'Execução da proposta aprovada')
        try:
            if r['tipo'] == 'experimento_bandit':
                inicio = agora()
                return repo.transicao(empresa, id, 'executando', 'em_observacao',
                    {'inicio': inicio.isoformat(), 'fim': (inicio + timedelta(days=d['duracao_dias'])).isoformat(),
                     'relatorio_execucao': 'Experimento ativado com sorteio estável por pessoa. LinUCB base preservado; nenhuma recompensa sintética.'}, ator, 'Experimento iniciado')
            df, _, precos = coorte
            df.attrs.clear()  # manifesto já persistido; não duplicar nas cópias do pandas durante treino
            reg = (treinar or tf.treinar)(df, empresa, ator, precos, cientista_acao_id=id)
            return _concluir(repo, r, reg, ator)
        except Exception as e:
            repo.transicao(empresa, id, 'executando', 'erro', {'erro': type(e).__name__}, ator, 'Falha na execução; nenhuma ativação autorizada')
            raise
    finally:
        liberar(trava)


def _concluir(repo, r, reg, ator):
    return repo.transicao(r['empresa_id'], r['id'], 'executando', 'concluida',
        {'erro': None, 'versao_modelo': reg['versao'], 'resultado': comparar(reg, r['dados']['criterios']),
         'relatorio_execucao': f"Versão {reg['versao']} treinada e mantida inativa com {reg['n_amostras']} resultados. Motivo: critérios da proposta aprovada.",
         'concluido_em': agora().isoformat()}, ator, 'Modelo candidato produzido; ativação depende do COMANDO')


def encerrar(empresa, id, ator, repo=None):
    repo = repo or fabrica()
    r = repo.obter(empresa, id)
    if r['tipo'] != 'experimento_bandit': raise ValueError('Ação não é experimento.')
    return repo.transicao(empresa, id, 'em_observacao', 'encerrada',
                         {'encerrado_em': agora().isoformat()}, ator,
                         'Experimento encerrado: recomendações voltam à seleção original do LinUCB')


def registrar_ativacao(empresa, antes, depois, ator, fase, repo=None):
    """Registra intenção ANTES do efeito, e confirmação depois; não esconde falha."""
    repo = repo or fabrica()
    from model import modelos_empresa as me
    ids = {v['cientista_acao_id'] for v in me.carregar_versoes(empresa)['versoes']
           if v.get('cientista_acao_id') and v['versao'] in (antes, depois)}
    for id in ids:
        r = repo.obter(empresa, id)
        if r['status'] != 'concluida':
            raise Conflito('Conclua ou recupere a execução do Cientista antes de ativar o modelo.')
        repo.transicao(empresa, r['id'], 'concluida', 'concluida',
            {'ultima_ativacao': {'antes': antes, 'depois': depois, 'fase': fase, 'em': agora().isoformat()}}, ator,
            f'{fase}: troca de versão {antes or "global"} para {depois or "global"}; permite auditar rollback')


def monitorar_modelos(empresa, repo=None):
    from model import modelos_empresa as me, treino_feedbacks as tf
    from aprendizado.dados import preparar
    repo = repo or fabrica()
    vs = me.carregar_versoes(empresa)
    ativa = vs.get('versao_ativa')
    reg = next((v for v in vs['versoes'] if v['versao'] == ativa), None)
    if not reg or not reg.get('cientista_acao_id'): return None
    r = repo.obter(empresa, reg['cientista_acao_id'])
    if r['status'] != 'concluida': return None
    # Medir as probabilidades realmente emitidas após a ativação, não refazer
    # o score hoje sobre dados usados anteriormente para treinar.
    ds = tf.datasets(repo.db, [empresa]).get(empresa)
    coorte, resumo = preparar(empresa, ds, instante=agora())
    pares = [(f,p) for f,p in coorte[2] if p.get('modelo_versao') == ativa and data(p['created_at']) >= data(reg['promovido_em']) and p.get('score_recuperabilidade') is not None]
    rel = {'versao_ativa': ativa, 'n': len(pares), 'sha256': resumo['sha256'], 'acao': 'aguardar desfechos maduros'}
    if len(pares) >= 30 and len({f['pagou'] for f,p in pares}) == 2:
        from model.treino_empresa import _metricas
        metricas = _metricas([int(f['pagou']) for f,p in pares], [float(p['score_recuperabilidade']) / 100 for f,p in pares])
        antes = reg['metricas']['novo']
        piorou = metricas['auc'] < antes['auc'] - .05 or metricas['brier'] > antes['brier'] + .05
        rel.update(metricas=metricas, referencia=antes, acao='revisar e considerar rollback no COMANDO' if piorou else 'manter observação',
                   limitacao='Comparação de períodos diferentes; mudança de composição pode explicar a variação.')
    if rel != r['dados'].get('monitoramento_modelo'):
        repo.transicao(empresa, r['id'], 'concluida', 'concluida', {'monitoramento_modelo': rel}, 'cientista:monitor', 'Acompanhamento dos resultados após ativação')
    return rel
