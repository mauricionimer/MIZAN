"""Transições e eventos são atômicos no PostgreSQL. Sem banco, não executa ações."""
class Conflito(ValueError):
    pass


class Repositorio:
    def __init__(self, db):
        self.db = db

    def listar(self, empresa):
        from model.treino_feedbacks import _paginar
        rows = _paginar(lambda: self.db.table('cientista_acoes').select('*').eq('empresa_id', empresa))
        return sorted(rows, key=lambda r: r['criado_em'], reverse=True)

    def obter(self, empresa, id):
        import uuid
        try: uuid.UUID(str(id))
        except ValueError: raise LookupError('Ação inexistente nesta empresa.')
        r = self.db.table('cientista_acoes').select('*').eq('empresa_id', empresa).eq('id', id).execute().data
        if not r: raise LookupError('Ação inexistente nesta empresa.')
        return r[0]

    def criar(self, empresa, tipo, chave, dados, ator):
        return self.db.rpc('cientista_criar', {'p_empresa': empresa, 'p_tipo': tipo, 'p_chave': chave,
                                            'p_dados': dados, 'p_ator': ator}).execute().data

    def transicao(self, empresa, id, esperado, status, dados, ator, motivo):
        r = self.db.rpc('cientista_transicao', {'p_empresa': empresa, 'p_id': id, 'p_esperado': esperado,
                'p_status': status, 'p_dados': dados, 'p_ator': ator, 'p_motivo': motivo}).execute().data
        if not r: raise Conflito('Ação já alterada por outro processo; atualize a tela.')
        return r

    def eventos(self, empresa, id):
        self.obter(empresa, id)
        # Paginação para não truncar silenciosamente a auditoria.
        from model.treino_feedbacks import _paginar
        return _paginar(lambda: self.db.table('cientista_eventos').select('*').eq('empresa_id', empresa).eq('acao_id', id))

    def base(self, empresa, id):
        from agente.cripto import decifrar
        from aprendizado.dados import hash_json
        import json
        r = self.obter(empresa, id)
        sha = (r['dados'].get('coorte') or {}).get('sha256')
        if not sha: raise LookupError('Ação sem base de treinamento.')
        rows = self.db.table('cientista_bases').select('conteudo_cifrado').eq('empresa_id', empresa).eq('sha256', sha).execute().data
        if not rows: raise LookupError('Base não encontrada.')
        manifesto = json.loads(decifrar(rows[0]['conteudo_cifrado']))
        if hash_json(manifesto) != sha: raise ValueError('A integridade da base não confere.')
        return {'sha256': sha, 'manifesto': manifesto}


def fabrica():
    from db import get_db
    return Repositorio(get_db())
