"""Contrato e volume das pastas, feedbacks e métricas com teto real por resposta."""
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste", MIZAN_AGENTE_ATIVO="1")
import main
from agente import api, semaforo
from agente.repositorio import RepoSupabase


class Banco:
    def __init__(self, tabelas, teto=1000):
        self.tabelas, self.teto, self.consultas = tabelas, teto, []

    def table(self, tabela):
        banco = self
        class Q:
            def __init__(self):
                self.l = list(banco.tabelas.get(tabela, []))
                self.campos, self.ordens, self.filtros = '*', [], []
                self.faixa, self.maximo, self.contar, self.neg = None, None, False, False
            def select(self, campos, count=None): self.campos=campos; self.contar=count=='exact'; return self
            def eq(self, c, v):
                self.filtros.append((c, v)); self.l=[r for r in self.l if r.get(c)==v]; return self
            def gte(self, c, v): self.l=[r for r in self.l if r.get(c)>=v]; return self
            def in_(self, c, vs):
                assert len(vs)<=100, 'URL não pode levar todos os ids'
                self.l=[r for r in self.l if (r.get(c) in vs) != self.neg]; self.neg=False; return self
            @property
            def not_(self): self.neg=True; return self
            def or_(self, texto):
                pares=[p.split('.',2) for p in texto.split(',')]
                self.l=[r for r in self.l if any(v.strip('*').lower() in str(r.get(c) or '').lower() for c,_,v in pares)]
                return self
            def order(self, campo, desc=False): self.ordens.append((campo,desc)); return self
            def range(self, a, b): self.faixa=(a,b); return self
            def limit(self, n): self.maximo=n; return self
            def execute(self):
                linhas=self.l
                for campo,desc in reversed(self.ordens):
                    linhas=sorted(linhas,key=lambda r:(r.get(campo) is None,r.get(campo)),reverse=desc)
                total=len(linhas)
                if self.faixa: linhas=linhas[self.faixa[0]:self.faixa[1]+1]
                if self.maximo is not None: linhas=linhas[:self.maximo]
                linhas=linhas[:banco.teto]
                if self.campos!='*':
                    def projetar(r):
                        out={}
                        for campo in self.campos.split(','):
                            alias,_,expressao=campo.strip().partition(':')
                            v=r
                            for parte in (expressao or alias).split('->'):
                                v=v.get(parte) if isinstance(v,dict) else None
                            out[alias]=v
                        return out
                    linhas=[projetar(r) for r in linhas]
                banco.consultas.append({'tabela':tabela,'campos':self.campos,'faixa':self.faixa,
                                         'filtros':self.filtros,'linhas':len(linhas),'bytes':len(json.dumps(linhas))})
                return SimpleNamespace(data=linhas,count=total if self.contar else None)
        return Q()


class DesempenhoEscala(unittest.TestCase):
    def setUp(self):
        self.agora=datetime.now(timezone.utc)
        preds=[{'id':f'p{i:05}', 'carteira_id':'c1', 'rank':i, 'nome':f'Pessoa {i}',
                'cpf':f'{i:011}', 'valor_divida':i+100, 'dias_em_atraso':i%100,
                'score_recuperabilidade':50} for i in range(6000)]
        casos=[{'predicao_id':p['id'],'empresa_id':'emp','situacao':'atrasado' if i%2 else 'negociando',
                'dados':{'caderno':['x'*5000], 'leitura':{'quando':self.agora.isoformat(),'emocao':'calmo'}}}
               for i,p in enumerate(preds[1000:1240])]
        casos += [{'predicao_id':'outro','empresa_id':'outra','situacao':'atrasado','dados':{}}]
        self.db=Banco({'predicoes':preds,'agente_casos':casos})
        self.repo=RepoSupabase(self.db)

    def pastas(self, **kw):
        args=dict(carteira_id='c1',busca=None,cor=None,limit=24,offset=0,empresa_id=None,credentials=None)
        args.update(kw)
        with patch.object(main,'get_db',return_value=self.db), \
             patch.object(main,'_usuario_autenticado',return_value={'empresa_id':'emp','role':'admin'}), \
             patch.object(main,'_exige_carteira_da_empresa'), patch.object(api,'fabrica_repo',return_value=self.repo):
            return main.agente_pastas(**args)

    def test_pastas_hidratam_so_a_pagina_e_preservam_cores_contagens_e_arquivos(self):
        resposta=self.pastas()
        self.assertEqual(resposta['contagem'],{'vermelho':120,'amarelo':120,'branco':5760,'total':6000})
        esperados=[f'p{i:05}' for i in range(1001,1049,2)]
        self.assertEqual([p['id'] for p in resposta['itens']],esperados)
        self.assertTrue(all(p['semaforo']['cor']=='vermelho' for p in resposta['itens']))
        self.assertTrue(all(any(a['name']=='Caderno do caso' for a in p['arquivos']) for p in resposta['itens']))
        self.assertEqual(sum(q['linhas'] for q in self.db.consultas if q['tabela']=='predicoes' and 'nome' in q['campos']),24)
        self.assertEqual(sum(q['linhas'] for q in self.db.consultas if q['tabela']=='agente_casos' and q['campos']=='*'),24)
        self.assertTrue(all(('empresa_id','emp') in q['filtros'] for q in self.db.consultas if q['tabela']=='agente_casos'))

    def test_brancos_param_ao_completar_pagina_sem_varrer_carteira(self):
        resposta=self.pastas(cor='branco',offset=24)
        self.assertEqual([p['id'] for p in resposta['itens']],[f'p{i:05}' for i in range(24,48)])
        varreduras=[q for q in self.db.consultas if q['tabela']=='predicoes' and q['faixa']]
        self.assertEqual(sum(q['linhas'] for q in varreduras),256)
        print('Pastas brancas: 256 linhas de fila lidas em vez de 6.000; detalhes de 24 pastas.')

    def test_busca_limite_entre_cores_e_fim_da_lista(self):
        d=self.pastas(offset=115)
        self.assertEqual([p['semaforo']['cor'] for p in d['itens']],['vermelho']*5+['amarelo']*19)
        d=self.pastas(busca='Pessoa 1001')
        self.assertEqual([p['id'] for p in d['itens']],['p01001'])
        self.assertEqual(d['contagem']['total'],1)
        self.assertEqual(self.pastas(offset=6000)['itens'],[])
        self.assertEqual(self.pastas(busca='não existe')['itens'],[])

    def test_semaforo_nao_trunca_no_teto_da_api(self):
        self.db.teto=37
        casos=self.repo.casos_semaforo('emp')
        self.assertEqual(len(casos),240)
        self.assertNotIn('caderno',casos[0]['dados'])
        self.assertEqual(semaforo.para_tela(casos[0]),semaforo.para_tela(self.db.tabelas['agente_casos'][0]))

    def test_feedbacks_sem_consulta_vazia_e_sem_perder_linhas_com_teto_baixo(self):
        linhas=[{'id':str(i),'predicao_id':f'p{i//7}', 'created_at':f'{i:05}', 'pagou':bool(i%2)} for i in range(350)]
        for teto, consultas in ((1000,1),(37,10)):
            db=Banco({'feedbacks':linhas},teto)
            l=main._feedbacks_das_predicoes(db,'id,predicao_id,created_at,pagou',[f'p{i}' for i in range(50)])
            self.assertEqual(l,sorted(linhas,key=lambda f:f['created_at'],reverse=True))
            self.assertEqual(len(db.consultas),consultas)

    def test_metricas_mesmo_resumo_sem_detalhes_pesados_e_com_paginacao(self):
        linhas=[{'id':f'{i:05}', 'empresa_id':'emp', 'criado_em':(self.agora-timedelta(seconds=i)).isoformat(),
                 'no':'negociar','agente':'negociador','caso_id':f'c{i}', 'resultado':'ok',
                 'duracao_ms':i+1,'modelo':'modelo-teste','versao_prompt':'v1','tokens_entrada':10,
                 'tokens_saida':20,'custo_usd':.01,'detalhe':{'origem':'codigo','ok':True,'texto':'x'*5000}}
                for i in range(1250)]
        db=Banco({'agente_passos':linhas},teto=137)
        novos=RepoSupabase(db).passos_metricas('emp',self.agora-timedelta(days=1),1100)
        originais=list(reversed(linhas[:1100]))
        self.assertEqual(len(novos),1100)
        self.assertEqual(api._resumo_agente('Negociador',novos),api._resumo_agente('Negociador',originais))
        self.assertLess(sum(q['bytes'] for q in db.consultas),len(json.dumps(originais))*.15)
        self.assertTrue(all(('empresa_id','emp') in q['filtros'] for q in db.consultas))

    def test_tempos_e_logs_nao_expoem_identificadores_ou_parametros(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from desempenho import MedirDesempenho
        app=FastAPI()
        @app.get('/casos/{id}')
        def caso(id): return {'ok':True}
        app.add_middleware(MedirDesempenho,limite_ms=0)
        with self.assertLogs('uvicorn.error',level='INFO') as logs:
            r=TestClient(app).get('/casos/12345678900?token=SEGREDO')
            TestClient(app).get('/desconhecido/12345678900')
        self.assertEqual(r.json(),{'ok':True})
        self.assertIn('app;dur=',r.headers['server-timing'])
        self.assertEqual(len(r.headers['x-request-id']),16)
        self.assertNotIn('12345678900',str(logs.output))
        self.assertNotIn('SEGREDO',str(logs.output))
        self.assertIn('/casos/{id}',str(logs.output))


if __name__=='__main__': unittest.main()
