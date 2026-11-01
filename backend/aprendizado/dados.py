"""Coorte reproduzível de resultados reais; não preenche ausência como inadimplência."""
import hashlib
import hmac
import json
import math
import os
from datetime import datetime, timezone


def agora():
    return datetime.now(timezone.utc)


def data(v):
    try:
        d = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    except (ValueError, TypeError):
        return None


def hash_json(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, default=str,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def identidade(empresa, identificador):
    segredo = os.getenv('MIZAN_ENCRYPTION_KEY') or os.getenv('SUPABASE_KEY')
    if not segredo:
        if os.getenv('SUPABASE_URL'):
            raise RuntimeError('Chave para pseudonimização ausente')
        segredo = 'somente-testes-locais'
    return hmac.new(segredo.encode(), f'{empresa}:{identificador}'.encode(), hashlib.sha256).hexdigest()


def preparar(empresa, dataset, desde=None, min_novos=30, instante=None):
    import pandas as pd
    from model.treino_empresa import MIN_LINHAS, MIN_POR_CLASSE
    instante = instante or agora()
    df, datas, pares = dataset or (None, [], [])
    dias = max(1, int(os.getenv('CIENTISTA_MATURIDADE_DIAS', '30')))
    excluidos, aceitos, vistos = {}, [], set()
    def excluir(motivo):
        excluidos[motivo] = excluidos.get(motivo, 0) + 1
    # Escolhe uma observação por pessoa, pela predição mais recente, antes de
    # inspecionar o alvo; impede a mesma pessoa em treino e teste.
    candidatos = sorted(zip([] if df is None else df.to_dict('records'), datas, pares),
                        key=lambda x: (str(x[2][1].get('created_at') or ''), str(x[2][1].get('id'))), reverse=True)
    for linha, dt, (f, p) in candidatos:
        if not f.get('id') or not p.get('cpf') or not p.get('id') or str(f.get('predicao_id')) != str(p['id']):
            excluir('sem_identidade_ou_vinculo'); continue
        pessoa = identidade(empresa, p['cpf'])
        if pessoa in vistos:
            excluir('pessoa_repetida'); continue
        vistos.add(pessoa)
        dp, d = data(p.get('created_at')), data(dt)
        if not dp or not d or d < dp or d > instante:
            excluir('data_invalida'); continue
        if (instante - dp).days < dias or (f.get('pagou') is False and (d - dp).days < dias):
            excluir('desfecho_imaturo'); continue
        if type(f.get('pagou')) is not bool:
            excluir('alvo_nao_confirmado'); continue
        try:
            if not all(math.isfinite(float(linha[k])) and float(linha[k]) >= 0 for k in ('valor_divida', 'dias_em_atraso')) or float(linha['valor_divida']) <= 0:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            excluir('variaveis_invalidas'); continue
        linha = {k: (None if pd.isna(v) else v) for k, v in linha.items()}
        linha['pagou'] = int(f['pagou'])
        aceitos.append((linha, d, f, p, pessoa))
    aceitos.sort(key=lambda x: (str(x[3]['created_at']), str(x[3]['id'])))
    n = len(aceitos)
    positivos = sum(x[0]['pagou'] for x in aceitos)
    novos = sum(1 for x in aceitos if not desde or x[1] > data(desde))
    qualidade = n / len(candidatos) if candidatos else 0
    qualidade_min = float(os.getenv('CIENTISTA_QUALIDADE_MINIMA', '0.8'))
    if not 0 < qualidade_min <= 1: raise ValueError('Qualidade mínima deve estar entre 0 e 1.')
    motivos = []
    if qualidade < qualidade_min: motivos.append(f'Fração elegível {qualidade:.0%} abaixo de {qualidade_min:.0%}; corrigir qualidade dos feedbacks.')
    if n < MIN_LINHAS: motivos.append(f'Faltam {MIN_LINHAS - n} resultados maduros de pessoas distintas.')
    if min(positivos, n - positivos) < MIN_POR_CLASSE: motivos.append(f'Exigidos {MIN_POR_CLASSE} pagamentos e {MIN_POR_CLASSE} não pagamentos confirmados.')
    if novos < min_novos: motivos.append(f'Faltam {min_novos - novos} resultados novos desde o último treino.')
    corte = int(n * .8)
    while 0 < corte < n and aceitos[corte - 1][0]['data_referencia'] == aceitos[corte][0]['data_referencia']:
        corte -= 1
    if n and (len({x[0]['pagou'] for x in aceitos[:corte]}) < 2 or len({x[0]['pagou'] for x in aceitos[corte:]}) < 2):
        motivos.append('As duas classes precisam estar presentes no treino e no teste temporal.')
    snapshot = [{'pessoa': x[4], 'predicao': identidade(empresa, x[3]['id']),
                 'feedback': identidade(empresa, x[2]['id']), 'valor_recuperado': x[2].get('valor_recuperado'), 'score_anterior': x[3].get('score_recuperabilidade'), 'modelo_origem': x[3].get('modelo_versao'), 'observado_em': x[1].isoformat(), 'variaveis': x[0]} for x in aceitos]
    resumo = {'versao_criterios': 1, 'total_recebido': len(candidatos), 'elegiveis': n,
              'pagaram': positivos, 'nao_pagaram': n - positivos, 'novos': novos,
              'minimos': {'total': MIN_LINHAS, 'por_classe': MIN_POR_CLASSE, 'novos': min_novos, 'maturidade_dias': dias, 'qualidade': qualidade_min},
              'fracao_elegivel': qualidade, 'excluidos': excluidos, 'apto': not motivos, 'faltas': motivos,
              'periodo': {'inicio': aceitos[0][0]['data_referencia'], 'fim': aceitos[-1][0]['data_referencia']} if n else None,
              'sha256': hash_json(snapshot), 'avaliado_em': instante.isoformat(),
              'limitacoes': ['Cobertura restrita a predições com feedback explícito; ausência não significa não pagamento.',
                             'Uma predição por pessoa; seleção observacional pode ter viés. Mínimos são travas de engenharia.']}
    tabela = pd.DataFrame([x[0] for x in aceitos])
    tabela.attrs['manifesto_cientista'] = snapshot
    return (tabela, [x[1].isoformat() for x in aceitos], [(x[2], x[3]) for x in aceitos]), resumo
