from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from agente.juridico.consulta import _dispositivo
from agente.juridico import decisao
from agente import juridico_orq, ferramentas


def test_conferencia_isolada_e_legado_incompleto():
    r={'id':'correto','rotulo':'art','norma_id':'n','artigo':'1','texto':'texto','situacao':'vigente'}
    conf={'status':'divergente','divergentes':['outro'],'conferidos':['correto']}
    assert _dispositivo(r,'teste',conf)['conferencia']=='conferida'
    assert _dispositivo({**r,'id':'outro'},'teste',conf)['conferencia']=='divergente'
    # Conferências antigas podem ter lista truncada; não inventa aprovação.
    assert _dispositivo(r,'teste',{**conf,'conferidos':[]})['conferencia']=='nao_conferida'


def test_sem_registro_bloqueia_e_nao_cacheia(monkeypatch):
    class Repo:
        def gravar_consulta_juridica(self,r): raise OSError()
    monkeypatch.setattr(decisao,'avaliar',lambda *a,**k:{'decisao':'prosseguir','acao':'teste','incertezas':[], 'justificativa':'permitido', 'consultado_em':'agora'})
    monkeypatch.setattr(juridico_orq,'_versao_indice',lambda:'v1')
    juridico_orq.limpar_cache()
    r=juridico_orq.da_empresa(Repo(),'a','teste',{})
    assert r['decisao']=='revisao_humana' and r['registro_id'] is None
    assert not juridico_orq._CACHE


def fatos(textos, criacao=True):
    dt=datetime.now(timezone.utc)
    msgs=[{'direcao':'saida','texto':t,'criado_em':dt+timedelta(seconds=i+1)} for i,t in enumerate(textos)]
    ctx=SimpleNamespace(caso={'id':'1','empresa_id':'a','dados':{}},saida={},repo=SimpleNamespace(ultimas_mensagens=lambda *a:msgs))
    sim={'condicoes':{'n_parcelas':12},'conta':{'total_pago':1200,'parcela':100,'entrada':0}}
    if criacao: sim['criada_em']=dt.isoformat()
    return ferramentas._fatos_oferta(ctx,sim)


def test_numero_parcelas_e_oferta_coerente():
    assert not fatos(['Total R$ 1.200,00. Cada parcela R$ 100,00.'])['informa_parcelas']
    assert not fatos(['Total R$ 1.200,00.', '12 parcelas de R$ 100,00.'])['informa_parcelas']
    assert not fatos(['Total R$ 1.200,00. 6 parcelas de R$ 100,00.'])['informa_parcelas']
    assert fatos(['Total R$ 1.200,00 em 12 parcelas de R$ 100,00.'])['informa_parcelas']
    assert not fatos(['Total R$ 1.200,00 em 12 parcelas de R$ 100,00.'],False)['informa_total']
    assert not fatos(['Total R$ 1.200,00 em 12 parcelas de R$ 100,00.', 'Outra proposta: total R$ 600,00 em 6 parcelas de R$ 100,00.'])['informa_total']
