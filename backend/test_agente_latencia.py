"""Regressões de resposta lenta e passagem humana. Sem banco/IA reais."""
import io
import json
import os
import unittest
from datetime import timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from agente import api, llm, orquestrador as orq
from agente.bateria.motor import ID_OK, Cenario, T, executar, tri, devedor, DIA, em
from agente.fonte import FonteMemoria, FonteSupabase
from agente.grafos import grafo_mensagem
from agente.publicador import Publicador
from agente.repositorio import RepoMemoria, RepoSupabase


class RegressaoLatencia(unittest.TestCase):
    def test_telemetria_lenta_nao_bloqueia_a_conversa_e_agrega_snapshots(self):
        pub = Publicador(limite=2)
        entrou, liberar, pronto = Event(), Event(), Event()
        gravados = []
        def gravar(d):
            entrou.set()
            liberar.wait(3)
            gravados.append(d)
            if d == 99:
                pronto.set()
        try:
            self.assertTrue(pub.publicar('evento', gravar, 0))
            self.assertTrue(entrou.wait(1))
            for i in range(1,100):
                self.assertTrue(pub.publicar('evento', gravar, i))
            self.assertEqual(gravados, [])
            self.assertLessEqual(pub._fila.qsize(), 2)
            liberar.set()
            self.assertTrue(pronto.wait(2))
            self.assertEqual(gravados, [0,99])
        finally:
            liberar.set()

    def test_fila_de_telemetria_cheia_descarta_apenas_observacao(self):
        pub = Publicador(limite=1)
        entrou, liberar, terminou = Event(), Event(), Event()
        def gravar(_):
            entrou.set(); liberar.wait(3); terminou.set()
        try:
            pub.publicar('ocupado', gravar, {})
            self.assertTrue(entrou.wait(1))
            self.assertTrue(pub.publicar('pendente', gravar, {}))
            self.assertFalse(pub.publicar('descartavel', gravar, {}))
        finally:
            liberar.set()
        self.assertTrue(terminou.wait(1))

    def test_gravacao_observacional_nao_muda_situacao_e_nao_sobrescreve_snapshot_novo(self):
        calls=[]
        class Query:
            def __getattr__(self, nome):
                def fn(*args, **kw):
                    calls.append((nome,args,kw))
                    return SimpleNamespace(data=[]) if nome=='execute' else self
                return fn
        class Sincrono:
            def publicar(self, chave, fn, dados):
                fn(dados)
        dados={'texto':'entrada preservada','_escritorio':{'atualizado_em':'2026-10-22T12:00:00.000000Z'}}
        with patch('agente.publicador.publicador', Sincrono()):
            RepoSupabase(Query()).publicar_escritorio('empresa','evento','trace',dados)
        self.assertEqual(next(c[1][0] for c in calls if c[0]=='update'), {'dados':dados})
        self.assertIn(('eq',('empresa_id','empresa'),{}), calls)
        self.assertIn(('eq',('trace_id','trace'),{}), calls)
        self.assertIn('atualizado_em.lte.', next(c[1][0] for c in calls if c[0]=='or_'))

    def test_timeout_ou_cota_tem_uma_tentativa_sem_dormir_na_requisicao(self):
        cota=HTTPError('http://teste',429,'cota',{},io.BytesIO(json.dumps({'error':{'details':[{'retryDelay':'90s'}]}}).encode()))
        for erro in [cota,URLError('offline'),TimeoutError('demora')]:
            with self.subTest(erro=type(erro).__name__), patch('urllib.request.urlopen',side_effect=erro) as enviar, patch('time.sleep') as dormir:
                with self.assertRaises(llm.IaOcupada) as ctx:
                    llm._enviar_http('http://teste',{},'segredo',60)
                self.assertEqual(enviar.call_count,1)
                dormir.assert_not_called()
                self.assertGreaterEqual(ctx.exception.esperar_s,60)

    def test_http_permanente_nao_vira_repeticao_infinita(self):
        erro=HTTPError('http://teste',403,'proibido',{},io.BytesIO(b'{}'))
        with patch('urllib.request.urlopen',side_effect=erro):
            with self.assertRaises(llm.ErroGemini) as ctx:
                llm._enviar_http('http://teste',{},'segredo',60)
        self.assertNotIsInstance(ctx.exception,llm.IaOcupada)

    def test_anthropic_deixa_as_repeticoes_para_o_orquestrador(self):
        from unittest.mock import Mock
        construir=Mock(return_value=SimpleNamespace())
        with patch.dict('sys.modules',{'anthropic':SimpleNamespace(Anthropic=construir)}):
            llm.ClienteAnthropic()
        self.assertEqual(construir.call_args.kwargs['max_retries'],0)

    def test_evento_pendente_e_encontrado_mesmo_com_muitos_outros_casos(self):
        repo=RepoMemoria();caso=repo.obter_ou_criar_caso('emp','p1')
        ev,_=orq.registrar_evento(repo,'emp',caso['id'],'mensagem_devedor','p1',{'texto':'mensagem'})
        for i in range(310):
            outro=repo.obter_ou_criar_caso('emp',f'outro{i}')
            orq.registrar_evento(repo,'emp',outro['id'],'relogio',f'e{i}')
        self.assertEqual(api.ver_caso('emp','p1',repo)['evento']['id'],ev['id'])
        self.assertIsNone(repo.ultimo_evento_caso('outra',caso['id']))

    def test_espera_tecnica_nao_e_descrita_como_resposta_final_ou_transferencia(self):
        mensagem=api._por_que_calou([{'no':'negociar','resultado':'erro'}, {'no':'aguardar_ia'}])
        self.assertIn('nova tentativa automática',mensagem)
        self.assertNotIn('equipe',mensagem)

    def test_envio_da_tela_nao_processa_casos_de_outros_clientes(self):
        repo=RepoMemoria(); fonte=FonteMemoria([devedor(),devedor(id='p2')])
        repo.gravar_politica('emp',1,api.auditor.POLITICA_DEMONSTRACAO)
        outro=repo.obter_ou_criar_caso('emp','p2')
        ev,_=orq.registrar_evento(repo,'emp',outro['id'],'mensagem_devedor','outro',{'texto':'como funciona?'})
        cli=llm.ClienteFalso({'triagem':[tri('duvida')],'negociador':[T('Posso te ajudar com isso.')]})
        with patch.dict(os.environ,{'MIZAN_AGENTE_ATIVO':'1'}), patch.object(api,'fabrica_repo',lambda:repo), patch.object(api,'fabrica_fonte',lambda:fonte), patch.object(api,'fabrica_cliente',lambda:cli):
            r=api.simular_mensagem('emp','p1','como funciona?',em(DIA))
        self.assertEqual(r['evento']['situacao'],'feito')
        self.assertEqual(repo.eventos[ev['id']]['situacao'],'pendente')
        self.assertEqual(repo.obter_caso(outro['id'])['situacao'],'novo')

    def test_falha_tecnica_cria_demanda_humana_antes_de_confirmar_transferencia(self):
        cli=llm.ClienteFalso({'triagem':[tri('duvida')],'negociador':[llm.Resposta(parada='recusa')]*2})
        r=executar(Cenario('t','t','t',dados=dict(ID_OK),conferir=[],passos=[('mensagem','como funciona?')]),cli)
        self.assertEqual(r.caso['situacao'],'com_pessoa')
        tarefas=[a for a in r.fonte.agenda if a['observacao'].startswith('Transferido pelo assistente')]
        self.assertEqual(len(tarefas),1)
        self.assertIn('falha',tarefas[0]['observacao'])
        self.assertTrue(r.caso['dados'].get('passagem'))

    def test_erro_na_agenda_nao_promete_passagem_nem_abandona_caso_com_pessoa(self):
        repo=RepoMemoria();fonte=FonteMemoria([devedor()]);caso=repo.obter_ou_criar_caso('emp','p1')
        repo.gravar_politica('emp',1,api.auditor.POLITICA_DEMONSTRACAO)
        ev,_=orq.registrar_evento(repo,'emp',caso['id'],'mensagem_devedor','m1',{'texto':'como funciona?'})
        cli=llm.ClienteFalso({'triagem':[tri('duvida')],'negociador':[llm.Resposta(parada='recusa')]*4})
        with patch.object(fonte,'criar_agenda',side_effect=RuntimeError('banco indisponível')):
            r=orq.processar_proximo(repo,{'mensagem_devedor':grafo_mensagem(fonte)},cli,em(DIA))
        self.assertEqual(r['situacao_evento'],'pendente')
        self.assertNotEqual(repo.obter_caso(caso['id'])['situacao'],'com_pessoa')
        self.assertFalse(any(m['direcao']=='saida' for m in repo.mensagens))
        depois=repo.eventos[ev['id']]['disponivel_em']+timedelta(seconds=1)
        orq.processar_proximo(repo,{'mensagem_devedor':grafo_mensagem(fonte)},cli,depois)
        self.assertEqual(repo.obter_caso(caso['id'])['situacao'],'com_pessoa')
        self.assertEqual(len(fonte.agenda),1)

    def test_passagem_explicita_nao_espera_resumo_opcional_da_ia(self):
        cli=llm.ClienteFalso({'supervisor':[RuntimeError('não deve chamar')]})
        r=executar(Cenario('t','t','t',papeis=('supervisor',),dados=dict(ID_OK),conferir=[],passos=[('mensagem','Quero falar com um atendente')]),cli)
        self.assertEqual(r.caso['situacao'],'com_pessoa')
        self.assertFalse(cli.chamadas)
        self.assertEqual(len(r.fonte.agenda),1)

    def test_falha_em_vencimento_tambem_cria_demanda_humana(self):
        repo=RepoMemoria();fonte=FonteMemoria([devedor()]);caso=repo.obter_ou_criar_caso('emp','p1')
        repo.gravar_politica('emp',1,api.auditor.POLITICA_DEMONSTRACAO)
        orq.registrar_evento(repo,'emp',caso['id'],'vencimento','v1',{})
        r=orq.processar_proximo(repo,api.grafos(fonte),llm.ClienteFalso(),em(DIA))
        self.assertFalse(r['ok'])
        self.assertEqual(repo.obter_caso(caso['id'])['situacao'],'com_pessoa')
        self.assertEqual(len(fonte.agenda),1)

    def test_erro_permanente_do_pedido_nao_chama_modelo_duas_vezes(self):
        cli=llm.ClienteFalso({'triagem':[llm.ErroGemini('HTTP 403')]*2})
        r=executar(Cenario('t','t','t',conferir=[],passos=[('mensagem','como funciona?')]),cli)
        self.assertEqual(len(cli.chamadas),1)
        self.assertEqual(r.caso['situacao'],'com_pessoa')
        self.assertEqual(len(r.fonte.agenda),1)

    def test_consulta_de_agenda_de_producao_le_observacao_para_deduplicar(self):
        class Query:
            def __init__(self): self.campos=''
            def select(self,campos): self.campos=campos;return self
            def __getattr__(self,nome): return lambda *a,**k: SimpleNamespace(data=[]) if nome=='execute' else self
        q=Query();FonteSupabase(q).agenda_pendente('emp','p1')
        self.assertIn('observacao',q.campos)

    def test_pedido_repetido_nao_duplica_demanda_de_transferencia(self):
        from agente import ferramentas
        from agente.rastreio import Rastreio
        repo=RepoMemoria();fonte=FonteMemoria([devedor()]);caso=repo.obter_ou_criar_caso('emp','p1')
        repo.gravar_politica('emp',1,api.auditor.POLITICA_DEMONSTRACAO)
        ctx=orq.Contexto(caso,{'id':'e'},repo,Rastreio('emp',repo.gravar_passo),llm.ClienteFalso(),DIA,em(DIA))
        for _ in range(2):
            self.assertTrue(ferramentas.executar(ctx,fonte,'transferir_para_humano',{'motivo':'pedido_do_devedor','resumo':'Pediu uma pessoa.'})['ok'])
        self.assertEqual(len(fonte.agenda),1)


if __name__=='__main__':
    unittest.main()
