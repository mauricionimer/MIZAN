"""Tarefas internas como compromissos sem devedor, na tabela agenda existente.

CPF vazio identifica ausência de cliente; nunca é um CPF fictício. As consultas
também exigem predicao_id/carteira_id nulos e sempre filtram a empresa.
"""
from datetime import datetime, timezone


def autorizar(payload, empresa_alvo=None, escrita=False):
    role = payload.get('role')
    if role not in ('admin', 'comando') or (escrita and role != 'admin'):
        raise PermissionError('Somente o administrador da empresa pode gerenciar tarefas administrativas.')
    empresa = empresa_alvo if role == 'comando' else payload.get('empresa_id')
    if not empresa:
        raise ValueError('Escolha a empresa.')
    return empresa


def consulta(db, empresa):
    return (db.table('agenda').select('*', count='exact').eq('empresa_id', empresa)
            .eq('cpf', '').is_('predicao_id', 'null').is_('carteira_id', 'null'))


def listar(db, empresa, situacao='pendente', offset=0, limite=100):
    if situacao not in ('pendente', 'cumprida'):
        raise ValueError('Situação inválida.')
    r = (consulta(db, empresa).eq('situacao', situacao).order('data')
         .order('created_at', desc=True).range(offset, offset + limite - 1).execute())
    return {'itens': r.data or [], 'total': r.count or 0, 'offset': offset}


def criar(db, empresa, usuario, titulo, descricao, data):
    titulo = titulo.strip()
    if not 3 <= len(titulo) <= 120:
        raise ValueError('Informe um título entre 3 e 120 caracteres.')
    if len(descricao or '') > 2000:
        raise ValueError('A descrição deve ter até 2000 caracteres.')
    r = db.table('agenda').insert({
        'empresa_id': empresa, 'cpf': '', 'nome': titulo,
        'carteira_id': None, 'predicao_id': None, 'tipo': 'retorno',
        'operador_id': usuario['sub'], 'operador_nome': usuario.get('email', ''),
        'data': data.isoformat(), 'observacao': (descricao or '').strip(),
        'situacao': 'pendente',
    }).execute()
    if not r.data:
        raise RuntimeError('Não foi possível salvar a tarefa.')
    return r.data[0]


def mudar(db, empresa, item_id, concluir, quem):
    anterior, nova = ('pendente', 'cumprida') if concluir else ('cumprida', 'pendente')
    campos = {'situacao': nova,
              'resolvido_em': datetime.now(timezone.utc).isoformat() if concluir else None,
              'resolvido_por': quem if concluir else None}
    r = (db.table('agenda').update(campos).eq('empresa_id', empresa).eq('id', item_id)
         .eq('cpf', '').is_('predicao_id', 'null').is_('carteira_id', 'null')
         .eq('situacao', anterior).execute())
    if not r.data:
        raise LookupError('Tarefa não encontrada ou alterada por outro administrador. Atualize a lista.')
    return r.data[0]
