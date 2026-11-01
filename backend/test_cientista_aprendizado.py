"""Regressões do ciclo: isolamento, maturidade, consentimento e recuperação."""
import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import threading

import pandas as pd
import pytest
from aprendizado import dados, servico, experimentos
from aprendizado.repositorio import Conflito

AGORA = datetime(2026, 10, 31, tzinfo=timezone.utc)


def dataset(n=320):
    rows, datas, pares = [], [], []
    for i in range(n):
        dt = AGORA - timedelta(days=500-i)
        p = {'id': str(i), 'cpf': f'{i:011}', 'created_at': dt.isoformat(), 'score_recuperabilidade': 50}
        f = {'id': 'f'+str(i), 'predicao_id': str(i), 'pagou': bool(i % 2), 'created_at': (dt + timedelta(days=40)).isoformat(), 'valor_recuperado': 100 if i%2 else 0}
        rows.append({'pagou': int(f['pagou']), 'data_referencia': dt.date().isoformat(), 'valor_divida': 500+i, 'dias_em_atraso': 60+i%30, 'produto': 'cartao', 'uf': 'SP', 'status': 'aberto', 'renda_estimada': 1500})
        datas.append(f['created_at']); pares.append((f,p))
    return pd.DataFrame(rows), datas, pares


class Memoria:
    def __init__(self):
        self.rows, self.history = {}, []
        self.lock = threading.Lock()
    def criar(self, empresa, tipo, chave, d, ator):
        with self.lock:
            old = next((r for r in self.rows.values() if (r['empresa_id'],r['tipo'],r['chave'])==(empresa,tipo,chave)), None)
            if old: return copy.deepcopy(old)
            id = str(len(self.rows)+1)
            r = {'id': id,'empresa_id':empresa,'tipo':tipo,'chave':chave,'dados':{k:copy.deepcopy(v) for k,v in d.items() if k!='_snapshot_cifrado'},'status':'proposta'}
            self.rows[id] = r
            self.history.append(copy.deepcopy(r))
            return copy.deepcopy(r)
    def obter(self, empresa, id):
        r = self.rows.get(id)
        if not r or r['empresa_id'] != empresa: raise LookupError()
        return copy.deepcopy(r)
    def listar(self, empresa):
        return [copy.deepcopy(r) for r in self.rows.values() if r['empresa_id']==empresa]
    def transicao(self, empresa, id, esperado, status, d, ator, motivo):
        with self.lock:
            r = self.obter(empresa,id)
            if r['status']!=esperado: raise Conflito()
            r['status']=status; r['dados'].update(copy.deepcopy(d))
            self.rows[id]=r; self.history.append(copy.deepcopy(r))
            return copy.deepcopy(r)


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    from model import modelos_empresa as me
    import travas
    from cryptography.fernet import Fernet
    monkeypatch.setenv('MIZAN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(me, 'EMPRESAS_DIR', tmp_path/'modelos')
    monkeypatch.setattr(travas, 'adquirir', lambda *a,**k: True)
    monkeypatch.setattr(travas, 'liberar', lambda *a: None)
    monkeypatch.setattr(servico, 'agora', lambda: AGORA)
    return Memoria()


def test_coorte_madura_unica_fingerprint_e_sem_identificadores():
    ds = dataset()
    limpa, r = dados.preparar('a', ds, instante=AGORA)
    assert r['apto'] and r['elegiveis']==320 and r['pagaram']==160
    assert 'cpf' not in limpa[0].columns and '00000000001' not in str(r)
    _, outro = dados.preparar('b', ds, instante=AGORA)
    assert outro['sha256'] != r['sha256']
    ds[2][0][0]['valor_recuperado']=5
    assert dados.preparar('a', ds, instante=AGORA)[1]['sha256'] != r['sha256']


def test_exclui_imaturos_repetidos_invalidos_e_sem_confirmacao():
    df, datas, pares = dataset()
    pares[0][1]['cpf']=pares[1][1]['cpf']
    pares[2][0]['pagou']=None
    pares[3][1]['created_at']=(AGORA-timedelta(days=2)).isoformat()
    datas[3]=AGORA.isoformat()
    df.loc[4,'valor_divida']=-2
    pares[5][1]['cpf']=None
    _, r = dados.preparar('a',(df,datas,pares),instante=AGORA)
    assert r['elegiveis']==315
    assert r['excluidos']=={'sem_identidade_ou_vinculo':1,'variaveis_invalidas':1,'desfecho_imaturo':1,'alvo_nao_confirmado':1,'pessoa_repetida':1}


def test_negativo_precoce_e_ausencia_nao_sao_resultados():
    df, datas, pares = dataset(2)
    datas[0]=(dados.data(pares[0][1]['created_at'])+timedelta(days=3)).isoformat()
    _, r = dados.preparar('a',(df,datas,pares),instante=AGORA)
    assert r['elegiveis']==1 and not r['apto']
    assert dados.preparar('a',None,instante=AGORA)[1]['elegiveis']==0


def test_poucos_novos_impede_proposta_treino(ambiente):
    coorte = dados.preparar('a', dataset(), desde=AGORA.isoformat(), instante=AGORA)
    r = servico.avaliar('a',repo=ambiente,coorte=coorte)
    assert r['tipo']=='coleta_dados'
    with pytest.raises(ValueError): servico.decidir('a',r['id'],'aprovada','admin',ambiente)


def proposta(repo):
    c = dados.preparar('a',dataset(),instante=AGORA)
    return servico.avaliar('a',repo=repo,coorte=c),c


def modelo():
    return {'versao':'e1','n_amostras':320,'validacao':'temporal','metricas':{'novo':{'auc':.7,'brier':.2},'atual':{'auc':.65,'brier':.22}}, 'avisos':[]}


def test_aprovacao_isolamento_execucao_e_repeticao(ambiente):
    r,c = proposta(ambiente)
    assert proposta(ambiente)[0]['id']==r['id']
    with pytest.raises(Conflito): servico.executar('a',r['id'],'admin',ambiente)
    with pytest.raises(LookupError): servico.decidir('b',r['id'],'aprovada','intruso',ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    chamadas=[]
    def treinar(*a,**kw): chamadas.append(kw); return modelo()
    fim=servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,treinar)
    assert fim['status']=='concluida' and not fim['dados']['resultado']['ativado']
    assert fim['dados']['resultado']['recomendacao']=='avaliar_ativacao_comando'
    servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,treinar)
    assert len(chamadas)==1 and chamadas[0]['cientista_acao_id']==r['id']
    assert [e['status'] for e in ambiente.history]==['proposta','aprovada','executando','concluida']


def test_dados_mudaram_expira_sem_treinar(ambiente):
    r,c=proposta(ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    c[1]['sha256']='mudou'
    fim=servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,lambda *a,**k:pytest.fail('treino indevido'))
    assert fim['status']=='expirada'


def test_duas_aprovacoes_so_uma_vence(ambiente):
    r,_=proposta(ambiente)
    def decidir(_):
        try: servico.decidir('a',r['id'],'aprovada','admin',ambiente); return True
        except Conflito: return False
    with ThreadPoolExecutor(2) as ex: assert sum(ex.map(decidir,range(2)))==1


def test_falha_fica_auditada_e_pode_reexecutar(ambiente):
    r,c=proposta(ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    def falhar(*a,**k): raise RuntimeError('segredo não deve ir ao log')
    with pytest.raises(RuntimeError): servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,falhar)
    assert ambiente.obter('a',r['id'])['dados']['erro']=='RuntimeError'
    fim=servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,lambda *a,**k:modelo())
    assert fim['status']=='concluida'


def test_recupera_modelo_sem_retreinar(ambiente,monkeypatch):
    from model import modelos_empresa as me
    r,c=proposta(ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    ambiente.transicao('a',r['id'],'aprovada','executando',{},'admin','teste')
    monkeypatch.setattr(me,'carregar_versoes',lambda e:{'versoes':[{**modelo(),'cientista_acao_id':r['id']}],'versao_ativa':None})
    assert servico.executar('a',r['id'],'admin',ambiente,treinar=lambda *a,**k:pytest.fail())['status']=='concluida'


def test_baseline_contaminada_nao_afirma_melhora():
    m=modelo(); m['metricas']['atual']={'indisponivel':'mesma base','em_amostra':True}
    criterios={'auc_minima':.5,'brier_maximo':.25,'tolerancia_queda_auc':.02,'tolerancia_aumento_brier':.02}
    assert servico.comparar(m,criterios)['recomendacao']=='revisar'


def test_sorteio_estavel_e_separado_por_empresa():
    a=[experimentos.sortear('a','id',str(i)) for i in range(100)]
    assert a==[experimentos.sortear('a','id',str(i)) for i in range(100)]
    assert a!=[experimentos.sortear('b','id',str(i)) for i in range(100)]
    assert set(a)=={'controle','tratamento'}


def test_monitor_nao_imputa_nao_pagamento_e_interrompe_dano():
    es,rs=[],[]
    for i in range(100):
        es.append({'id':str(i),'grupo':'controle' if i<50 else 'tratamento','criado_em':(AGORA-timedelta(days=40)).isoformat(),'contexto':{'valor_divida':100,'score_recuperabilidade':50,'dias_em_atraso':30}})
        rs.append({'exposicao_id':str(i),'dados':{'pagou':i<50,'valor_recuperado':100 if i<50 else 0,'observado_em':AGORA.isoformat(),'aderente':True}})
    vazio=experimentos.relatorio(es,[],AGORA)
    assert vazio['pendentes']==100 and vazio['controle']['n']==0 and not vazio['parar_por_dano']
    rel=experimentos.relatorio(es,rs,AGORA)
    assert rel['parar_por_dano'] and rel['composicao']['comparaveis']


def test_falha_auditoria_nao_executa(ambiente,monkeypatch):
    r,c=proposta(ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    def falhar(*a,**k): raise OSError()
    monkeypatch.setattr(ambiente,'transicao',falhar)
    with pytest.raises(OSError): servico.executar('a',r['id'],'admin',ambiente,lambda *a:c,lambda *a,**k:pytest.fail())


def test_bandit_evento_real_idempotente(monkeypatch):
    from model import bandit as b
    state = {'modelo': b.LinUCB(), 'versao': 0}
    monkeypatch.setattr(b,'_carregar_com_versao',lambda e:(b._copia(state['modelo']),state['versao']))
    def gravar(e,modelo,versao):
        assert versao==state['versao']
        state.update(modelo=modelo,versao=versao+1); return True
    monkeypatch.setattr(b,'_gravar_se_versao',gravar)
    monkeypatch.setattr(b,'_gravar_arquivo',lambda *a:None)
    b.registrar_resultado(0,[.1]*b.D,.5,'a',True,'pessoa',evento_id='feedback-123')
    b.registrar_resultado(0,[.1]*b.D,.5,'a',True,'pessoa',evento_id='feedback-123')
    assert state['modelo'].n_tentativas[0]==1
    assert len(b._bandit_para_json(state['modelo'])['eventos_processados'])==1


def test_treino_real_produz_candidato_inativo(ambiente,monkeypatch):
    from model import modelos_empresa as me
    import storage_ml
    monkeypatch.setattr(storage_ml,'upload_empresa',lambda *a:None)
    r,c=proposta(ambiente)
    servico.decidir('a',r['id'],'aprovada','admin',ambiente)
    fim=servico.executar('a',r['id'],'admin',ambiente,lambda *a:c)
    assert fim['status']=='concluida'
    vs=me.carregar_versoes('a')
    assert vs['versao_ativa'] is None and len(vs['versoes'])==1
    assert vs['versoes'][0]['cientista_acao_id']==r['id']
    assert vs['versoes'][0]['validacao']=='temporal'
    assert me.carregar_versoes('outra')['versoes']==[]


class BancoExperimento:
    def __init__(self, rows): self.rows=rows
    def table(self,t):
        db=self
        class Q:
            def __init__(self): self.filtros=[]; self.valor=None
            def select(self,*a): return self
            def eq(self,k,v): self.filtros.append((k,v)); return self
            def limit(self,n): return self
            def upsert(self,v,**k): self.valor=v; return self
            def execute(self):
                ls=db.rows.setdefault(t,[])
                if self.valor:
                    v=self.valor
                    campos=['empresa_id','experimento_id','pessoa'] if t=='cientista_exposicoes' else ['empresa_id','chave']
                    if not any(all(r.get(k)==v.get(k) for k in campos) for r in ls):
                        ls.append({**v,'id':str(len(ls)+1),'criado_em':(AGORA-timedelta(days=40)).isoformat()})
                return SimpleNamespace(data=[r for r in ls if all(r.get(k)==v for k,v in self.filtros)])
        return Q()


def test_experimento_nao_muda_parametros_e_registra_acao_estavel(monkeypatch):
    import numpy as np
    from model.bandit import LinUCB, D
    monkeypatch.setattr(experimentos,'agora',lambda:AGORA)
    exp={'id':'ex','empresa_id':'a','tipo':'experimento_bandit','status':'em_observacao','dados':{'fim':(AGORA+timedelta(days=2)).isoformat(),'multiplicador_exploracao':1.1}}
    db=BancoExperimento({'cientista_acoes':[exp]})
    b=LinUCB(); x=np.ones(D)
    base,scores=b.recomendar(x)
    before=[a.copy() for a in b.A]
    escolha=experimentos.selecionar(b,x,{'cpf':'123'},'a',base,scores,db)
    assert escolha[2]['experimento_id']=='ex'
    assert escolha==experimentos.selecionar(b,x,{'cpf':'123'},'a',base,scores,db)
    assert len(db.rows['cientista_exposicoes'])==1
    assert all(np.array_equal(a,c) for a,c in zip(b.A,before)) and sum(b.n_tentativas)==0
    assert experimentos.selecionar(b,x,{'cpf':'123'},'b',base,scores,db)[2]=={}
    exp['dados']['fim']=(AGORA-timedelta(days=1)).isoformat()
    assert experimentos.selecionar(b,x,{'cpf':'123'},'a',base,scores,db)[2]=={}


def test_observacao_exige_contato_real_e_deduplica_feedback():
    exp={'id':'e','empresa_id':'a','pessoa':dados.identidade('a','cpf'),'acao_id':0,'criado_em':(AGORA-timedelta(days=40)).isoformat()}
    db=BancoExperimento({'cientista_exposicoes':[exp]})
    rec={'exposicao_id':'e'}
    experimentos.observar(db,'a','cpf',rec,None,True,100,AGORA,fonte_id='f1')
    assert not db.rows.get('cientista_resultados')
    ct={'id':'c','acao_bandit_id':0,'created_at':(AGORA-timedelta(days=20)).isoformat()}
    for i in range(2): experimentos.observar(db,'a','cpf',rec,ct,True,100,AGORA,fonte_id='f1')
    assert len(db.rows['cientista_resultados'])==1
    assert db.rows['cientista_resultados'][0]['dados']['aderente']
    experimentos.observar(db,'b','cpf',rec,ct,True,100,AGORA,fonte_id='f2')
    assert len(db.rows['cientista_resultados'])==1
