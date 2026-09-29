"""Regressão: carteira de outra empresa não pode vazar pelos endpoints
que aceitam carteira_id na query string.

Roda sem banco — o Supabase é substituído por um duplo em memória onde
"c-alfa" pertence ao banco_alfa e "c-beta" à credtotal. O usuário do teste
é operador do banco_alfa, então "c-beta" tem de dar 403 e "c-alfa" 200.

    python -m pytest test_escopo_carteira.py      (ou execute direto)
"""
import sys, types, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.update(SUPABASE_URL='http://127.0.0.1:1', SUPABASE_KEY='x', JWT_SECRET='teste')
import main
from fastapi.testclient import TestClient

# ── banco falso: carteira "c-alfa" é do banco_alfa; "c-beta" é da credtotal
class Q:
    def __init__(s, tbl): s.tbl, s.f = tbl, {}
    def select(s, *a, **k): return s
    def eq(s, col, val): s.f[col] = val; return s
    def in_(s, col, vals): s.f[col] = vals; return s
    def is_(s, *a): return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s

    # O código lê em páginas (range), então o stub precisa recortar de verdade:
    # devolver sempre tudo faria o laço de paginação nunca terminar.
    def range(s, ini, fim):
        s._corte = (ini, fim)
        return s

    def _pagina(s, linhas):
        ini, fim = getattr(s, "_corte", (None, None))
        return linhas if ini is None else linhas[ini:fim + 1]

    def execute(s):
        if s.tbl == 'carteiras':
            dono = {'c-alfa': 'banco_alfa', 'c-beta': 'credtotal'}
            if 'id' in s.f:
                d = dono.get(s.f['id'])
                return types.SimpleNamespace(data=[{'empresa_id': d}] if d else [])
            return types.SimpleNamespace(data=s._pagina([{'id': k} for k, v in dono.items() if v == s.f.get('empresa_id')]))
        if s.tbl == 'predicoes':
            return types.SimpleNamespace(data=s._pagina([{'id': 'p-beta', 'score_recuperabilidade': 55.0, 'valor_divida': 1000.0, 'cpf': '99988877700', 'carteira_id': 'c-beta', 'nome': 'X'}]))
        if s.tbl == 'feedbacks':
            return types.SimpleNamespace(data=s._pagina([{'cpf': '99988877700', 'pagou': True,
                'valor_recuperado': 5000, 'data_pagamento': '2026-09-01',
                'predicao_id': 'p-beta', 'empresa': 'credtotal',
                'created_at': '2026-09-01', 'registrado_por': 'x'}]))
        return types.SimpleNamespace(data=s._pagina([]))

main.get_db = lambda: types.SimpleNamespace(table=lambda t: Q(t))
main._cache_get = lambda *a, **k: None
main._cache_set = lambda *a, **k: None
main.buscar_usuario_por_id = lambda uid: {'ativo': True, 'id': uid}

from auth import criar_token
tok = criar_token({'sub': 'u1', 'email': 'op@alfa.com', 'nome': 'Op Alfa',
                   'role': 'operador', 'empresa_id': 'banco_alfa'})
h = {'Authorization': f'Bearer {tok}'}
c = TestClient(main.app)

falhas = 0
for rota in ['/feedbacks/status', '/performance', '/performance/pagamentos']:
    r = c.get(f'{rota}?carteira_id=c-beta', headers=h)     # carteira ALHEIA
    ok_bloq = r.status_code == 403
    r2 = c.get(f'{rota}?carteira_id=c-alfa', headers=h)    # carteira PRÓPRIA
    ok_perm = r2.status_code == 200
    print(f'{rota:28} alheia={r.status_code} {"BLOQUEADA" if ok_bloq else "VAZOU"}  |  própria={r2.status_code} {"ok" if ok_perm else "QUEBROU"}')
    if not (ok_bloq and ok_perm): falhas += 1

print('\nRESULTADO:', 'todos os três protegidos' if falhas == 0 else f'{falhas} endpoint(s) com problema')
assert falhas == 0, f'{falhas} endpoint(s) deixam vazar carteira de outra empresa'
