"""Regressão: a oferta negociada na tela alimenta o bandit.

    python test_loop_oferta.py     (ou python -m pytest test_loop_oferta.py)

O aprendizado por oferta só sai do lugar se o resultado do contato chegar ao
bandit com a oferta que foi DE FATO apresentada. Antes, o loop era pulado
inteiro quando não havia uma recomendação prévia gravada para o CPF — então
quem negociava direto pela tela de propostas nunca gerava aprendizado, por
mais contatos que registrasse.
"""
import os
import sys
import tempfile
import types
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x",
                  JWT_SECRET="teste", MIZAN_DATA_DIR=tempfile.mkdtemp())
Path(os.environ["MIZAN_DATA_DIR"], "model").mkdir(parents=True, exist_ok=True)

import main                                   # noqa: E402
from model import bandit as B                 # noqa: E402
from fastapi.testclient import TestClient     # noqa: E402
from auth import criar_token                  # noqa: E402

B._salvar_supabase = lambda e, b: None
B._carregar_supabase = lambda e: None
# joblib.dump escreveria bandit_<empresa>.pkl dentro do repositório
_salvar_real = B.salvar_bandit
B.salvar_bandit = lambda emp, bandit: (
    B._bandit_cache.__setitem__(B._chave(emp), bandit),
    B._bandit_cache_ts.__setitem__(B._chave(emp), __import__('time').monotonic()),
)

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# Banco falso SEM nenhuma linha em "recomendacoes": é o cenário do operador
# que negocia direto pela tela de propostas, sem passar pelo bandit antes.
class Q:
    def __init__(s, tbl): s.tbl, s.f = tbl, {}
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f[c] = v; return s
    def in_(s, c, v): s.f[c] = v; return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s
    def insert(s, row): s.row = row; return s

    # O código lê em páginas, então o banco falso precisa recortar de verdade:
    # devolver sempre as mesmas linhas faria o laço de paginação não terminar.
    def range(s, ini, fim):
        s._corte = (ini, fim)
        return s

    def _pagina(s, linhas):
        ini, fim = getattr(s, "_corte", (None, None))
        return linhas if ini is None else linhas[ini:fim + 1]

    def execute(s):
        if s.tbl == "recomendacoes":
            return types.SimpleNamespace(data=[])          # nada gravado antes
        if s.tbl == "carteiras":
            # Uma predição não existe sem a carteira que a contém. O banco falso
            # antigo tinha a predição e NENHUMA carteira para a empresa — estado
            # impossível, que só funcionava porque o recorte por empresa falhava
            # aberto (`if cart_ids:` descartava o filtro com a lista vazia).
            return types.SimpleNamespace(data=s._pagina([{"id": "c-alfa"}]))
        if s.tbl == "predicoes":
            return types.SimpleNamespace(data=s._pagina([{
                "id": "p1", "carteira_id": "c-alfa", "created_at": "2026-01-01",
                "cpf": "11122233344", "nome": "Maria", "produto": "cartao", "uf": "GO",
                "valor_divida": 10000.0, "renda_estimada": 4000.0,
                "dias_em_atraso": 120, "score_recuperabilidade": 60.0}]))
        if s.tbl == "contatos":
            return types.SimpleNamespace(data=[{"id": "ct-1", **getattr(s, "row", {})}])
        return types.SimpleNamespace(data=[])


main.get_db = lambda: types.SimpleNamespace(table=lambda t: Q(t))
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
EMP = "banco_alfa"
h = {"Authorization": "Bearer " + criar_token(
    {"sub": "u1", "email": "op@alfa.com", "nome": "Op", "role": "operador",
     "empresa_id": EMP})}
c = TestClient(main.app)


def contar(oferta):
    b = B.carregar_bandit(EMP)
    ids = [a["id"] for a in B.ACOES if a["oferta"] == oferta]
    return sum(b.n_tentativas[i] for i in ids), sum(b.n_pagamentos[i] for i in ids)


# ── sem recomendação prévia, registrando a oferta apresentada ──────────────
antes = contar("parcelado_12x")
r = c.post("/contatos", headers=h, json={
    "cpf": "11122233344", "canal": "telefone", "resultado": "pagou",
    "oferta": "parcelado_12x", "valor_recuperado": 9000})
checar(r.status_code in (200, 201), "aceita o contato com a oferta apresentada",
       f"{r.status_code} {r.text[:90]}")
depois = contar("parcelado_12x")
checar(depois[0] == antes[0] + 1,
       "sem recomendação prévia, o contato AGORA chega ao bandit",
       f"tentativas {antes[0]} -> {depois[0]}")
checar(depois[1] == antes[1] + 1, "e conta como pagamento",
       f"pagamentos {antes[1]} -> {depois[1]}")

# ── a oferta certa é creditada, não outra ─────────────────────────────────
outras = {o: contar(o)[0] for o in B.OFERTAS if o != "parcelado_12x"}
checar(all(v == 0 for v in outras.values()),
       "nenhuma outra oferta é creditada por engano", str(outras))

# ── canal muda a ação, mas a oferta continua sendo a mesma ────────────────
c.post("/contatos", headers=h, json={
    "cpf": "11122233344", "canal": "whatsapp", "resultado": "pagou",
    "oferta": "parcelado_12x", "valor_recuperado": 5000})
b = B.carregar_bandit(EMP)
checar(b.n_tentativas[B.acao_id_de("telefone", "parcelado_12x")] == 1
       and b.n_tentativas[B.acao_id_de("whatsapp", "parcelado_12x")] == 1,
       "cada canal entra na própria ação")
checar(contar("parcelado_12x")[0] == 2,
       "e a PoP da oferta agrega os canais", str(contar("parcelado_12x")[0]))

# ── quem não quis conta como tentativa sem pagamento ──────────────────────
antes4 = contar("parcelado_4x")
c.post("/contatos", headers=h, json={
    "cpf": "11122233344", "canal": "telefone", "resultado": "nao_quis",
    "oferta": "parcelado_4x"})
depois4 = contar("parcelado_4x")
checar(depois4[0] == antes4[0] + 1 and depois4[1] == antes4[1],
       "recusa entra como tentativa e não como pagamento",
       f"{depois4[1]}/{depois4[0]}")

# ── a PoP da oferta reflete o que foi registrado ──────────────────────────
pops = B.pop_por_oferta(EMP, 0.50)
checar(pops["parcelado_12x"]["n_pagamentos"] == 2
       and pops["parcelado_12x"]["origem"] == "bandit",
       "a PoP por oferta passa a se apoiar nesses registros",
       f'{pops["parcelado_12x"]["n_pagamentos"]}/{pops["parcelado_12x"]["n_tentativas"]}')
checar(pops["parcelado_12x"]["pop"] > pops["parcelado_4x"]["pop"],
       "a oferta que foi paga fica com chance maior que a recusada",
       f'12x={pops["parcelado_12x"]["pop"]} vs 4x={pops["parcelado_4x"]["pop"]}')

# ── oferta fora do catálogo é recusada, não gravada torta ─────────────────
r = c.post("/contatos", headers=h, json={
    "cpf": "11122233344", "canal": "telefone", "resultado": "pagou",
    "oferta": "parcelado_99x", "valor_recuperado": 100})
checar(r.status_code == 422, "oferta fora do catálogo é recusada", str(r.status_code))

# ── sem informar oferta, o contato continua funcionando ───────────────────
r = c.post("/contatos", headers=h, json={
    "cpf": "11122233344", "canal": "carta", "resultado": "contactado"})
checar(r.status_code in (200, 201),
       "contato sem oferta continua aceito (campo é opcional)", str(r.status_code))

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
