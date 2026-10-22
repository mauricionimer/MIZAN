import copy
import unittest
from datetime import datetime, timezone

from agente.fluxo import para_tela, unificar, operacao_para_tela, carregar_registros
from agente import api, auditor, orquestrador
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria


class FluxoTest(unittest.TestCase):
    def caso(self, situacao='novo', **dados):
        return {'situacao': situacao, 'dados': dados}

    def test_cinco_fases_e_sem_caso(self):
        tela = para_tela(None)
        self.assertEqual(tela['fase_atual'], 'nao_iniciado')
        self.assertEqual([f['nome'] for f in tela['fases']],
                         ['Não iniciado', 'Contactado', 'Negociando', 'Acordo', 'Pagamento em andamento'])

    def test_contato_negociacao_acordo(self):
        for situacao, fase in [('novo', 'nao_iniciado'), ('em_contato', 'contactado'),
                               ('negociando', 'negociando'), ('acordo_ativo', 'acordo')]:
            self.assertEqual(para_tela(self.caso(situacao))['fase_atual'], fase)

    def test_planejar_lembrete_nao_prova_contato(self):
        self.assertEqual(para_tela(self.caso('so_lembrete'))['fase_atual'], 'nao_iniciado')
        self.assertEqual(para_tela(self.caso('so_lembrete'), True)['fase_atual'], 'contactado')

    def test_informar_pagamento_nao_confirma(self):
        caso = self.caso('pagamento_em_conferencia', acordo={'id': 'a'}, pagamento_informado={'valor': 100})
        tela = para_tela(caso)
        self.assertEqual(tela['fase_atual'], 'acordo')
        self.assertEqual(tela['pagamentos_confirmados'], 0)
        self.assertIn('conferência', tela['aviso']['texto'])

    def test_pagamentos_invalidos_nao_avancam(self):
        for valor in [0, -1, None, '', 'nan', 'inf', 'erro', True]:
            tela = para_tela(self.caso('acordo_ativo', pagamentos=[{'valor': valor}]))
            self.assertEqual(tela['fase_atual'], 'acordo')

    def test_primeiro_pagamento_e_avisos_sem_sexta_fase(self):
        for situacao, aviso in [('acordo_ativo', None), ('atrasado', 'Pagamento em atraso'),
                               ('quebrado', 'Acordo quebrado'), ('quitado', 'Quitado')]:
            caso = self.caso(situacao, acordo={'id': 'a'}, pagamentos=[{'valor': 100, 'data': '2026-10-21'}])
            anterior = copy.deepcopy(caso)
            tela = para_tela(caso)
            self.assertEqual(tela['fase_atual'], 'pagamento')
            self.assertEqual((tela['aviso'] or {}).get('texto'), aviso)
            self.assertEqual(len(tela['fases']), 5)
            self.assertEqual(caso, anterior)

    def test_situacao_desconhecida_nao_inventa_fase(self):
        self.assertIsNone(para_tela(self.caso('situacao-futura'))['fase_atual'])

    def test_nova_negociacao_prevalece_sobre_pagamento_antigo(self):
        tela = para_tela(self.caso('negociando', acordo={'id': 'antigo'}, pagamentos=[{'valor': 100}]))
        self.assertEqual(tela['fase_atual'], 'negociando')

    def test_consulta_isola_empresa_sem_criar_caso(self):
        repo = RepoMemoria()
        caso = repo.obter_ou_criar_caso('empresa-a', 'p1')
        repo.salvar_caso(caso['id'], {'situacao': 'negociando'})
        self.assertEqual(api.fluxo_devedor('empresa-a', 'p1', repo)['fase_atual'], 'negociando')
        self.assertEqual(api.fluxo_devedor('empresa-b', 'p1', repo)['fase_atual'], 'nao_iniciado')
        self.assertEqual(len(repo.casos), 1)

    def test_atualizacao_real_pelo_grafo_do_acompanhamento(self):
        repo = RepoMemoria()
        dev = {'id': 'p1', 'empresa_id': 'emp', 'cpf': '123', 'nome': 'Teste', 'valor_divida': 600}
        fonte = FonteMemoria([dev])
        caso = repo.obter_ou_criar_caso('emp', 'p1')
        repo.salvar_caso(caso['id'], {'situacao': 'acordo_ativo', 'dados': {'acordo': {'condicoes': {'n_parcelas': 6}}}})
        repo.gravar_politica('emp', 1, auditor.POLITICA_DEMONSTRACAO)
        self.assertEqual(api.fluxo_devedor('emp', 'p1', repo)['fase_atual'], 'acordo')
        agora = datetime(2026, 10, 21, 17, tzinfo=timezone.utc)
        orquestrador.registrar_evento(repo, 'emp', caso['id'], 'pagamento', 'teste-pagamento',
                                     {'valor': 100, 'data': '2026-10-21', 'promessas': []}, origem='banco')
        orquestrador.processar_fila(repo, api.grafos(fonte), ClienteFalso(), agora=agora)
        self.assertEqual(api.fluxo_devedor('emp', 'p1', repo)['fase_atual'], 'pagamento')

    def test_contato_sem_resposta_nao_avanca_e_promessa_nao_e_acordo(self):
        self.assertIsNone(operacao_para_tela({'contatos': [{'resultado': 'sem_resposta'}]})['fase_atual'])
        self.assertEqual(operacao_para_tela({'contatos': [{'resultado': 'prometeu_pagar'}]})['fase_atual'], 'negociando')
        self.assertEqual(operacao_para_tela({'ofertas': [{'resposta': 'aceitou'}]})['fase_atual'], 'acordo')

    def test_pagou_no_contato_nao_e_baixa(self):
        tela = unificar(None, registros={'contatos': [{'resultado': 'pagou'}]})
        self.assertEqual(tela['fase_atual'], 'contactado')
        self.assertFalse(tela['pode_marcar_pagamento'])
        tela = unificar(None, registros={'feedbacks': [{'pagou': True, 'valor_recuperado': 80}]})
        self.assertEqual(tela['fase_atual'], 'pagamento')

    def test_divergencia_pede_decisao_sem_inventar_prioridade(self):
        caso = self.caso('negociando')
        registros = {'ofertas': [{'resposta': 'aceitou'}]}
        tela = unificar(caso, registros=registros)
        self.assertTrue(tela['conflito'])
        self.assertIsNone(tela['fase_atual'])
        caso['dados']['fluxo_manual'] = {'fase': 'acordo', 'nome': 'Operador'}
        self.assertEqual(unificar(caso, registros=registros)['fase_atual'], 'acordo')

    def test_contato_antigo_nao_bloqueia_progresso_posterior(self):
        caso = {**self.caso('negociando'), 'atualizado_em': '2026-10-21T12:00:00Z'}
        registros = {'contatos': [{'resultado': 'contactado', 'created_at': '2026-10-20T12:00:00Z'}]}
        self.assertFalse(unificar(caso, registros=registros)['conflito'])

    def test_fase_manual_nao_altera_decisao_do_agente_e_pode_voltar_automatico(self):
        repo = RepoMemoria()
        caso = repo.obter_ou_criar_caso('emp', 'p1')
        repo.salvar_caso(caso['id'], {'situacao': 'negociando', 'dados': {'divida': 300}})
        user = {'role': 'operador', 'empresa_id': 'emp', 'sub': 'u1', 'nome': 'Operador'}
        api.definir_fase_devedor('emp', 'p1', 'acordo', user, repo=repo)
        repo.salvar_caso(caso['id'], {'situacao': 'em_contato'})
        self.assertEqual(api.fluxo_devedor('emp', 'p1', repo)['fase_atual'], 'acordo')
        self.assertEqual(repo.obter_caso(caso['id'])['dados']['divida'], 300)
        tela = api.definir_fase_devedor('emp', 'p1', None, user, repo=repo)
        self.assertEqual(tela['fase_atual'], 'contactado')
        self.assertIsNone(tela['manual'])

    def test_manual_nao_permite_confirmar_dinheiro_nem_empresa_alheia(self):
        repo = RepoMemoria()
        user = {'role': 'operador', 'empresa_id': 'emp', 'sub': 'u1'}
        with self.assertRaises(ValueError):
            api.definir_fase_devedor('emp', 'p1', 'pagamento', user, repo=repo)
        with self.assertRaises(PermissionError):
            api.definir_fase_devedor('outra', 'p1', 'acordo', user, repo=repo)
        with self.assertRaises(PermissionError):
            api.definir_fase_devedor('emp', 'p1', 'acordo', {**user, 'role': 'comando'}, repo=repo)
        self.assertEqual(len(repo.casos), 0)

    def test_fonte_ausente_nao_parece_nao_iniciado(self):
        self.assertIsNone(unificar(None, registros={'indisponiveis': ['ofertas_feitas']})['fase_atual'])

    def test_parcelas_reutilizam_regra_real_de_atraso(self):
        from datetime import date
        ps = [{'feedback_id': 'f', 'total': 2, 'situacao': 'paga', 'valor': 50, 'vencimento': '2026-09-01'},
              {'feedback_id': 'f', 'total': 2, 'situacao': 'pendente', 'valor': 50, 'vencimento': '2026-10-20'}]
        tela = operacao_para_tela({'parcelas': ps}, date(2026, 10, 21))
        self.assertEqual(tela['fase_atual'], 'pagamento')
        self.assertEqual(tela['avisos'][0]['texto'], 'Pagamento em atraso')

    def test_leituras_financeiras_nao_misturam_empresa_ou_predicao(self):
        from types import SimpleNamespace
        class Query:
            def __init__(self, rows): self.rows = rows
            def select(self, *_): return self
            def eq(self, k, v): self.rows = [r for r in self.rows if r.get(k) == v]; return self
            def in_(self, k, values): self.rows = [r for r in self.rows if r.get(k) in values]; return self
            def order(self, *_ , **__): return self
            def limit(self, n): self.rows = self.rows[:n]; return self
            def execute(self): return SimpleNamespace(data=self.rows)
        rows = [{'empresa_id': 'emp', 'empresa': 'emp', 'cpf': '123', 'predicao_id': 'p1', 'resultado': 'contactado'},
                {'empresa_id': 'outra', 'empresa': 'outra', 'cpf': '123', 'predicao_id': 'p1', 'resultado': 'contactado'},
                {'empresa_id': 'emp', 'empresa': 'emp', 'cpf': '456', 'predicao_id': 'p2', 'resultado': 'contactado'}]
        class DB:
            def table(self, _): return Query(rows.copy())
        r = carregar_registros(DB(), 'emp', {'id': 'p1', 'cpf': '123'})
        self.assertTrue(all(len(r[k]) == 1 for k in ('contatos', 'ofertas', 'feedbacks', 'parcelas')))

    def test_caso_ocupado_nao_perde_dados(self):
        from datetime import timedelta
        repo = RepoMemoria()
        caso = repo.obter_ou_criar_caso('emp', 'p1')
        agora = datetime.now(timezone.utc)
        repo.travar_caso(caso['id'], 'outro', agora + timedelta(minutes=1), agora)
        user = {'role': 'operador', 'empresa_id': 'emp', 'sub': 'u1'}
        with self.assertRaises(api.CasoOcupado):
            api.definir_fase_devedor('emp', 'p1', 'acordo', user, repo=repo)
        self.assertNotIn('fluxo_manual', repo.obter_caso(caso['id'])['dados'])


if __name__ == '__main__':
    unittest.main()
