"""Permissões e empresa verificadas nas rotas reais (sem banco externo)."""
from fastapi.testclient import TestClient
import pytest
import main
from aprendizado import repositorio, servico
from test_cientista_aprendizado import Memoria, proposta


@pytest.fixture
def cliente(monkeypatch,tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SUPABASE_KEY", "x")
    from model import modelos_empresa as me
    from cryptography.fernet import Fernet
    monkeypatch.setenv('MIZAN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    repo=Memoria()
    monkeypatch.setattr(me,'EMPRESAS_DIR',tmp_path)
    monkeypatch.setattr(repositorio,'fabrica',lambda:repo)
    monkeypatch.setattr(servico,'fabrica',lambda:repo)
    monkeypatch.setattr(main,'_usuario_autenticado',lambda c:{'role':'admin','empresa_id':'a','sub':'u','email':'a@a'})
    c=TestClient(main.app,raise_server_exceptions=False)
    return c,repo


H={'Authorization':'Bearer teste'}


def test_admin_nao_acessa_empresa_alheia(cliente):
    c,repo=cliente
    for method,path,kwargs in [('get','/agente/aprendizado?empresa_id=b',{}),('post','/agente/aprendizado/avaliar',{'json':{'empresa_id':'b'}})]:
        assert getattr(c,method)(path,headers=H,**kwargs).status_code==403


def test_operador_nao_aprova_nem_le_auditoria(cliente,monkeypatch):
    c,repo=cliente
    monkeypatch.setattr(main,'_usuario_autenticado',lambda c:{'role':'operador','empresa_id':'a','sub':'op'})
    assert c.get('/agente/aprendizado',headers=H).status_code==403
    assert c.post('/agente/aprendizado/x/decidir',headers=H,json={'decisao':'aprovada'}).status_code==403


def test_api_exige_aprovacao_e_nao_permite_acesso_cruzado(cliente,monkeypatch):
    c,repo=cliente
    r,_=proposta(repo)
    assert c.post(f"/agente/aprendizado/{r['id']}/executar",headers=H,json={}).status_code==409
    assert c.post('/agente/aprendizado/inexistente/decidir',headers=H,json={'decisao':'aprovada'}).status_code==404
    assert c.post(f"/agente/aprendizado/{r['id']}/decidir",headers=H,json={'decisao':'aprovada'}).status_code==200
    assert c.post(f"/agente/aprendizado/{r['id']}/decidir",headers=H,json={'decisao':'recusada'}).status_code==409


def test_indisponibilidade_nao_parece_lista_vazia(cliente,monkeypatch):
    c,repo=cliente
    def falha(*a):raise OSError('senha de exemplo')
    monkeypatch.setattr(repo,'listar',falha)
    r=c.get('/agente/aprendizado',headers=H)
    assert r.status_code==503 and 'senha' not in r.text
