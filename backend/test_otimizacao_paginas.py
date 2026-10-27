"""Regressões de volume de leitura; banco falso com projeção e paginação reais."""
import json
import os
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main


class Banco:
    def __init__(self, linhas):
        self.linhas = linhas
        self.consultas = []

    def table(self, nome):
        banco = self
        class Consulta:
            def __init__(self):
                self.linhas = deepcopy(banco.linhas.get(nome, []))
                self.colunas, self.ordens, self.faixa = '*', [], None
            def select(self, colunas): self.colunas = colunas; return self
            def eq(self, campo, valor):
                self.linhas = [p for p in self.linhas if p.get(campo) == valor]; return self
            def in_(self, campo, valores):
                self.linhas = [p for p in self.linhas if p.get(campo) in valores]; return self
            def order(self, campo): self.ordens.append(campo); return self
            def limit(self, n): self.faixa = (0, n-1); return self
            def range(self, inicio, fim): self.faixa = (inicio, fim); return self
            def execute(self):
                linhas = self.linhas
                for campo in reversed(self.ordens):
                    linhas = sorted(linhas, key=lambda p: (p.get(campo) is None, p.get(campo)))
                if self.faixa:
                    linhas = linhas[self.faixa[0]:self.faixa[1]+1]
                if self.colunas != '*':
                    campos = [c.strip() for c in self.colunas.split(',')]
                    linhas = [{k: p[k] for k in campos if k in p} for p in linhas]
                banco.consultas.append({'tabela': nome, 'colunas': self.colunas,
                                         'linhas': len(linhas), 'bytes': len(json.dumps(linhas))})
                return SimpleNamespace(data=linhas)
        return Consulta()


class OtimizacaoPaginas(unittest.TestCase):
    def carteira(self, antigas=False):
        return Banco({'carteiras': [{'id': 'c1', 'empresa_id': 'emp'}], 'predicoes': [
            {'id': f'p{i:04}', 'carteira_id': 'c1', 'rank': None if antigas else i+1,
             'nome': f'Pessoa {i}', 'cpf': str(i), 'detalhes_extras': 'x'*2000,
             'uf': 'GO' if i%2 else 'SP', 'produto': 'Crédito', 'perfil_cluster': 'Perfil',
             'valor_divida': 1000+i, 'score_recuperabilidade': 50,
             'valor_esperado_recuperacao': None if i%3 else 100,
             'valor_esperado_liquido': i+1, 'dias_em_atraso': i%200} for i in range(1203)]})

    def carregar(self, db, completa):
        with patch.object(main, 'get_db', return_value=db), \
             patch.object(main, '_usuario_autenticado', return_value={'empresa_id':'emp'}), \
             patch.object(main, '_exige_carteira_da_empresa'), \
             patch.object(main, '_extra_empresa', return_value={}):
            return main.carregar_carteira('c1', completa, None)

    def test_resumo_identico_sem_hidratar_a_carteira_inteira(self):
        for antigas in (False, True):
            with self.subTest(antigas=antigas):
                db = self.carteira(antigas)
                completa = self.carregar(db, True)
                bytes_antes = sum(c['bytes'] for c in db.consultas)
                db.consultas.clear()
                reduzida = self.carregar(db, False)
                self.assertEqual(reduzida, {k:v for k,v in completa.items() if k!='ranking_completo'})
                self.assertEqual(sum(c['linhas'] for c in db.consultas if c['tabela']=='predicoes' and c['colunas']=='*'), 10)
                self.assertFalse(any(c['colunas']=='produto, uf' for c in db.consultas))
                bytes_depois = sum(c['bytes'] for c in db.consultas)
                self.assertLess(bytes_depois, bytes_antes * .25)
                print(f'Carteira sintética: {bytes_antes} -> {bytes_depois} bytes lidos; mesmas respostas.')

    def test_acesso_negado_antes_de_ler_predicoes(self):
        db = self.carteira()
        with patch.object(main, 'get_db', return_value=db), \
             patch.object(main, '_usuario_autenticado', return_value={'empresa_id':'outra'}), \
             patch.object(main, '_exige_carteira_da_empresa', side_effect=main.HTTPException(403)):
            with self.assertRaises(main.HTTPException): main.carregar_carteira('c1', False, None)
        self.assertEqual(db.consultas, [])

    def test_json_grande_comprimido_sem_alterar_conteudo_ou_cors(self):
        from fastapi.testclient import TestClient
        db = self.carteira()
        esperado = self.carregar(db, False)
        with patch.object(main, 'get_db', return_value=db), \
             patch.object(main, '_usuario_autenticado', return_value={'empresa_id':'emp'}), \
             patch.object(main, '_exige_carteira_da_empresa'), \
             patch.object(main, '_extra_empresa', return_value={}):
            client = TestClient(main.app)
            headers={'Authorization':'Bearer qa','Origin':'https://mizan-sand.vercel.app','Accept-Encoding':'gzip'}
            r=client.get('/carteiras/c1?incluir_ranking=false',headers=headers)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json(),esperado)
            self.assertEqual(r.headers['content-encoding'],'gzip')
            self.assertEqual(r.headers['access-control-allow-origin'],headers['Origin'])
            self.assertLess(int(r.headers['content-length']),len(r.content))
            r=client.get('/health',headers=headers)
            self.assertEqual(r.json(),{'status':'ok'})
            self.assertNotIn('content-encoding',r.headers)

    def test_resumo_agenda_le_so_datas_e_mantem_escopo(self):
        from agenda import hoje, contar_niveis
        from datetime import timedelta
        ref = hoje()
        linhas = [{'id':str(i), 'empresa_id':'emp', 'operador_id':'op', 'situacao':'pendente',
                   'data':(ref+timedelta(days=d)).isoformat(), 'observacao':'x'*3000}
                  for i,d in enumerate((-3,0,1,5))]
        linhas += [{**linhas[0], 'id':'outro', 'empresa_id':'outra'},
                   {**linhas[0], 'id':'outro-op', 'operador_id':'outro'}]
        db=Banco({'agenda':linhas})
        with patch.object(main,'get_db',return_value=db), patch.object(main,'_usuario_autenticado',
            return_value={'empresa_id':'emp','role':'operador','sub':'op'}):
            resposta=main.resumo_agenda('equipe',None,None)
        self.assertEqual(resposta, {'ativo':True,**contar_niveis([ref+timedelta(days=d) for d in (-3,0,1,5)],ref)})
        self.assertTrue(all(c['colunas']=='data' for c in db.consultas))


if __name__ == '__main__': unittest.main()
