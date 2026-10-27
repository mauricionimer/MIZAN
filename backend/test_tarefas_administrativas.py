"""Testes sem banco: autorização, isolamento, persistência e concorrência."""
import copy
import unittest
from datetime import date
from types import SimpleNamespace
import tarefas_administrativas as tarefas


class DB:
    def __init__(self): self.linhas = []
    def table(self, nome):
        assert nome == 'agenda'
        return Q(self)


class Q:
    def __init__(self, db): self.db, self.filtros, self.campos, self.nova, self.faixa = db, [], None, None, None
    def select(self, *a, **k): return self
    def eq(self, campo, valor): self.filtros.append(lambda l: l.get(campo) == valor); return self
    def is_(self, campo, valor):
        assert valor == 'null'
        return self.eq(campo, None)
    def order(self, *a, **k): return self
    def range(self, a, b): self.faixa = (a, b); return self
    def update(self, campos): self.campos = campos; return self
    def insert(self, nova): self.nova = nova; return self
    def execute(self):
        if self.nova is not None:
            linha = dict(self.nova, id=f't{len(self.db.linhas)}')
            self.db.linhas.append(linha)
            return SimpleNamespace(data=[copy.deepcopy(linha)])
        linhas = [l for l in self.db.linhas if all(f(l) for f in self.filtros)]
        if self.campos is not None:
            for linha in linhas: linha.update(self.campos)
        total = len(linhas)
        if self.faixa: linhas = linhas[self.faixa[0]:self.faixa[1] + 1]
        return SimpleNamespace(data=copy.deepcopy(linhas), count=total)


class TestTarefas(unittest.TestCase):
    def setUp(self):
        self.db = DB()
        self.usuario = {'role': 'admin', 'empresa_id': 'alfa', 'sub': 'adm1', 'email': 'adm@exemplo.com'}
    def criar(self, empresa='alfa'):
        return tarefas.criar(self.db, empresa, self.usuario, 'Conferir distribuição', 'Demanda interna', date(2026, 10, 21))
    def test_autorizacao_e_empresa(self):
        self.assertEqual(tarefas.autorizar(self.usuario, 'outra', True), 'alfa')
        with self.assertRaises(PermissionError): tarefas.autorizar({'role': 'operador', 'empresa_id': 'alfa'})
        with self.assertRaises(PermissionError): tarefas.autorizar({'role': 'comando'}, 'alfa', True)
        self.assertEqual(tarefas.autorizar({'role': 'comando'}, 'beta'), 'beta')
        with self.assertRaises(ValueError): tarefas.autorizar({'role': 'admin', 'sub': 'sem-empresa'})
    def test_cria_persiste_e_isola(self):
        item = self.criar()
        self.criar('beta')
        self.assertEqual(item['cpf'], '')
        self.assertEqual(tarefas.listar(self.db, 'alfa')['total'], 1)
        with self.assertRaises(LookupError): tarefas.mudar(self.db, 'beta', item['id'], True, 'admin')
    def test_concluir_reabrir_e_concorrencia(self):
        item = self.criar()
        tarefas.mudar(self.db, 'alfa', item['id'], True, 'admin')
        self.assertEqual(tarefas.listar(self.db, 'alfa')['total'], 0)
        self.assertEqual(tarefas.listar(self.db, 'alfa', 'cumprida')['total'], 1)
        with self.assertRaises(LookupError): tarefas.mudar(self.db, 'alfa', item['id'], True, 'admin2')
        tarefas.mudar(self.db, 'alfa', item['id'], False, 'admin')
        self.assertIsNone(tarefas.listar(self.db, 'alfa')['itens'][0]['resolvido_em'])
    def test_compromissos_de_clientes_nao_sao_tarefas(self):
        self.db.linhas.append({'id': 'cliente', 'empresa_id': 'alfa', 'cpf': '12345678900', 'situacao': 'pendente'})
        self.db.linhas.append({'id': 'ligado', 'empresa_id': 'alfa', 'cpf': '', 'predicao_id': 'p1', 'situacao': 'pendente'})
        self.assertEqual(tarefas.listar(self.db, 'alfa')['total'], 0)
        with self.assertRaises(LookupError): tarefas.mudar(self.db, 'alfa', 'cliente', True, 'admin')
    def test_validacao_e_paginacao(self):
        with self.assertRaises(ValueError): tarefas.criar(self.db, 'alfa', self.usuario, '   ', '', date.today())
        with self.assertRaises(ValueError): tarefas.listar(self.db, 'alfa', 'invalida')
        self.criar(); self.criar()
        r = tarefas.listar(self.db, 'alfa', offset=1, limite=1)
        self.assertEqual(r['total'], 2)
        self.assertEqual(len(r['itens']), 1)


if __name__ == '__main__': unittest.main()
