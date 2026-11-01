"""Experimento limitado, com grupo estável e observação de contatos reais."""
from aprendizado.dados import agora, data, identidade, hash_json


def sortear(empresa, id, pessoa):
    return 'tratamento' if int(identidade(empresa, f'{id}:{pessoa}')[:8], 16) % 2 else 'controle'


def selecionar(bandit, contexto, devedor, empresa, acao_base, scores, db=None):
    """Falha no armazenamento cancela a intervenção desta recomendação."""
    if not empresa or not devedor.get('cpf'): return acao_base, scores, {}
    from db import get_db
    import numpy as np
    db = db or get_db()
    rs = db.table('cientista_acoes').select('*').eq('empresa_id', empresa).eq('tipo', 'experimento_bandit').eq('status', 'em_observacao').limit(1).execute().data or []
    if not rs: return acao_base, scores, {}
    r = rs[0]
    if data(r['dados']['fim']) <= agora(): return acao_base, scores, {}
    pessoa = identidade(empresa, devedor['cpf'])
    def ler():
        return db.table('cientista_exposicoes').select('*').eq('empresa_id', empresa).eq('experimento_id', r['id']).eq('pessoa', pessoa).limit(1).execute().data or []
    anterior = ler()
    grupo = anterior[0]['grupo'] if anterior else sortear(empresa, r['id'], pessoa)
    if grupo == 'tratamento':
        fator = r['dados']['multiplicador_exploracao']
        if not 1 <= fator <= 1.2: raise ValueError('Exploração fora dos limites')
        x = contexto.astype(float)
        scores = [float((np.linalg.inv(bandit.A[a]) @ bandit.b[a]) @ x) +
                  bandit.alpha * fator * float(np.sqrt(np.clip(x @ np.linalg.inv(bandit.A[a]) @ x, 0, None)))
                  for a in range(bandit.n_acoes)]
        acao_base = int(np.argmax(scores))
    if anterior:
        e = anterior[0]
        return e['acao_id'], scores, {'experimento_id': r['id'], 'exposicao_id': e['id'], 'grupo_experimento': e['grupo']}
    db.table('cientista_exposicoes').upsert({'empresa_id': empresa, 'experimento_id': r['id'],
        'pessoa': pessoa, 'grupo': grupo, 'acao_id': acao_base,
        'contexto': {k: devedor.get(k) for k in ('score_recuperabilidade', 'valor_divida', 'dias_em_atraso')}},
        on_conflict='empresa_id,experimento_id,pessoa', ignore_duplicates=True).execute()
    e = ler()[0]  # concorrência: devolve a mesma ação que ganhou o insert
    return e['acao_id'], scores, {'experimento_id': r['id'], 'exposicao_id': e['id'], 'grupo_experimento': e['grupo']}


def observar(db, empresa, cpf, rec, contato, pagou, valor, instante=None, fonte_id=None):
    """Sem contato após a recomendação, o pagamento não é atribuído ao teste.
    A ação efetiva fica registrada inclusive quando diverge da recomendação.
    Eventos repetidos são idempotentes e não treinam o bandit novamente aqui.
    """
    instante = instante or agora()
    if not empresa or not rec.get('exposicao_id') or not contato: return
    from model.bandit import acao_id_de
    exposicoes = db.table('cientista_exposicoes').select('*').eq('id', rec['exposicao_id']).eq('empresa_id', empresa).eq('pessoa', identidade(empresa, cpf)).execute().data or []
    if not exposicoes: return
    e = exposicoes[0]
    dt = data(contato.get('created_at'))
    if not dt or dt < data(e['criado_em']): return
    acao = acao_id_de(contato.get('canal'), contato.get('oferta'))
    if acao is None: acao = contato.get('acao_bandit_id')
    if acao is None: return
    dados = {'pagou': bool(pagou), 'valor_recuperado': max(0, float(valor or 0)),
             'acao_real': acao, 'aderente': acao == e['acao_id'],
             'contato_em': dt.isoformat(), 'observado_em': instante.isoformat()}
    chave = hash_json([e['id'], fonte_id or dados['observado_em']])
    db.table('cientista_resultados').upsert({'empresa_id': empresa, 'exposicao_id': e['id'],
        'chave': chave, 'dados': dados}, on_conflict='empresa_id,chave', ignore_duplicates=True).execute()


def relatorio(exposicoes, resultados, instante=None, maturidade=30):
    from agente.ciencia import diferenca_taxas, composicao
    instante = instante or agora()
    por = {}
    for r in resultados:
        por.setdefault(r['exposicao_id'], []).append(r['dados'])
    obs, pendentes, nao_aderentes = [], 0, 0
    for e in exposicoes:
        inicio = data(e['criado_em'])
        rs = [r for r in por.get(e['id'], []) if data(r['observado_em']) and data(r['observado_em']) <= instante]
        if not inicio or (instante - inicio).days < maturidade:
            pendentes += 1; continue
        pagos = [r for r in rs if r['pagou']]
        negativos = [r for r in rs if not r['pagou'] and (data(r['observado_em']) - inicio).days >= maturidade]
        if not pagos and not negativos:
            pendentes += 1; continue
        r = max(pagos or negativos, key=lambda x: x['observado_em'])
        nao_aderentes += not r['aderente']
        c = e['contexto']
        obs.append({'grupo': e['grupo'], 'pagou': bool(pagos), 'recuperado': r['valor_recuperado'],
                    'divida': float(c.get('valor_divida') or 0), 'chance': c.get('score_recuperabilidade'),
                    'dias': float(c.get('dias_em_atraso') or 0)})
    t, c = ([o for o in obs if o['grupo'] == g] for g in ('tratamento', 'controle'))
    diferenca = diferenca_taxas(sum(o['pagou'] for o in t), len(t), sum(o['pagou'] for o in c), len(c))
    def resumo(grupo):
        return {'n': len(grupo), 'taxa_pagamento': sum(o['pagou'] for o in grupo) / len(grupo) if grupo else None,
                'recuperacao_sobre_divida': sum(o['recuperado'] for o in grupo) / sum(o['divida'] for o in grupo) if sum(o['divida'] for o in grupo) else None}
    suficientes = min(len(t), len(c)) >= 30
    dano = suficientes and diferenca[2] is not None and diferenca[2] < -.05
    return {'controle': resumo(c), 'tratamento': resumo(t), 'diferenca_taxa_ic95': diferenca,
            'composicao': composicao([{**o, 'grupo': 'agente' if o['grupo'] == 'tratamento' else 'sorteado'} for o in obs]), 'pendentes': pendentes, 'nao_aderentes': nao_aderentes,
            'parar_por_dano': dano, 'suficientes': suficientes,
            'conclusao': 'interromper e revisar' if dano else 'continuar observando' if not suficientes else 'revisar resultados antes de propor expansão',
            'limitacoes': ['Ausência de feedback não conta como não pagamento.',
                          'Resultados observados podem ter viés de resposta; não comprovam causalidade nem autorizam expansão automática.']}


def monitorar(empresa, repo=None):
    from aprendizado.repositorio import fabrica
    from model.treino_feedbacks import _paginar
    repo = repo or fabrica()
    saida = []
    for r in repo.listar(empresa):
        if r['tipo'] != 'experimento_bandit' or r['status'] not in ('em_observacao', 'encerrada'): continue
        es = _paginar(lambda: repo.db.table('cientista_exposicoes').select('*').eq('empresa_id', empresa).eq('experimento_id', r['id']))
        # Resultados filtrados pela empresa; ids de outra experiência não entram no relatório.
        rs = _paginar(lambda: repo.db.table('cientista_resultados').select('*').eq('empresa_id', empresa))
        rel = relatorio(es, rs, maturidade=r['dados']['maturidade_dias'])
        prazo = data(r['dados']['fim']) <= agora()
        status = 'encerrada' if prazo or rel['parar_por_dano'] else 'em_observacao'
        if r['status'] == 'encerrada':
            status = 'encerrada'
        if r['dados'].get('monitoramento') != rel or status != r['status']:
            repo.transicao(empresa, r['id'], r['status'], status, {'monitoramento': rel}, 'cientista:monitor',
                           'Intervenção encerrada; relatório inclui desfechos maduros recebidos depois do encerramento' if status == 'encerrada' else 'Resultados e composição atualizados')
        saida.append({'id': r['id'], 'relatorio': rel})
    return saida


def reconciliar(empresa, repo=None):
    """Reprocessa a fonte persistida após falha de escrita da observação.
    Só usa contato registrado depois da exposição e feedback depois do contato.
    Cada resultado tem chave idempotente; nunca chama registrar_resultado.
    """
    from aprendizado.repositorio import fabrica
    from model.treino_feedbacks import _paginar
    repo = repo or fabrica()
    db = repo.db
    recs = _paginar(lambda: db.table('recomendacoes').select('*').eq('empresa_id', empresa).not_.is_('exposicao_id', 'null'))
    carteiras = _paginar(lambda: db.table('carteiras').select('id').eq('empresa_id', empresa))
    vistos = set()
    for rec in sorted(recs, key=lambda r: r['created_at']):
        if rec['exposicao_id'] in vistos: continue
        vistos.add(rec['exposicao_id'])
        # CPF fica apenas em memória durante a junção operacional.
        cts = _paginar(lambda: db.table('contatos').select('id,created_at,canal,oferta,acao_bandit_id')
                      .eq('empresa_id', empresa).eq('cpf', rec['cpf']).gte('created_at', rec['created_at']))
        if not cts: continue
        for inicio in range(0, len(carteiras), 100):
            ids = [c['id'] for c in carteiras[inicio:inicio + 100]]
            ps = _paginar(lambda: db.table('predicoes').select('id').eq('cpf', rec['cpf']).in_('carteira_id', ids))
            for p in ps:
                fs = _paginar(lambda: db.table('feedbacks').select('id,pagou,valor_recuperado,created_at').eq('predicao_id', p['id']).gte('created_at', rec['created_at']))
                for f in fs:
                    anteriores = [ct for ct in cts if data(ct['created_at']) <= data(f['created_at'])]
                    if type(f.get('pagou')) is bool and anteriores:
                        ct = max(anteriores, key=lambda ct: ct['created_at'])
                        observar(db, empresa, rec['cpf'], rec, ct, f['pagou'], f.get('valor_recuperado'), data(f['created_at']), fonte_id=f['id'])
