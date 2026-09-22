"""Regressão: a API key é reconhecida pelo hash, nunca pelo texto guardado.

    python test_api_key.py      (ou python -m pytest test_api_key.py)

A chave ficava em texto puro no banco: qualquer dump, backup ou acesso de
leitura entregava credencial funcional. Agora o banco guarda o SHA-256 —
reconhece a chave apresentada, mas não consegue produzi-la.
"""
import hashlib
import os
import sys
import types
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                    # noqa: E402
from gerar_api_key import gerar                # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


CHAVE_NOVA, HASH_NOVA = gerar("banco_alfa")
CHAVE_ANTIGA = "mizan_legado_sem_hash"

atualizacoes = []


def banco(linhas):
    """Duplo do Supabase sobre uma lista de linhas de api_keys."""
    class Q:
        def __init__(s, tbl): s.tbl, s.f, s.cols = tbl, {}, ""
        def select(s, c="*", **k): s.cols = c; return s
        def eq(s, c, v): s.f[c] = v; return s
        def limit(s, *a): return s
        def update(s, d): s.upd = d; return s
        def execute(s):
            if getattr(s, "upd", None) is not None:
                atualizacoes.append((s.f, s.upd))
                return types.SimpleNamespace(data=[])
            achadas = [l for l in linhas
                       if all(l.get(k) == v for k, v in s.f.items())]
            # o banco real não tem a coluna antes da migração
            if "api_key_hash" in s.f and not any("api_key_hash" in l for l in linhas):
                raise Exception("column api_keys.api_key_hash does not exist")
            vis = [{k: v for k, v in l.items() if k != "api_key"} for l in achadas]
            return types.SimpleNamespace(data=vis)
    return types.SimpleNamespace(table=lambda t: Q(t))


# ── chave nova: só o hash está no banco ───────────────────────────────────
db = banco([{"id": "k1", "empresa_nome": "Alfa", "empresa_id": "banco_alfa",
             "api_key_hash": HASH_NOVA, "ativa": True}])
linha = main._buscar_api_key(db, CHAVE_NOVA)
checar(linha is not None, "chave correta é reconhecida pelo hash")
checar(linha and "api_key" not in linha,
       "a chave em texto nunca sai do banco para a aplicação",
       str(sorted(linha.keys())) if linha else "")
checar(main._buscar_api_key(db, CHAVE_NOVA + "x") is None, "chave errada é recusada")
checar(main._hash_api_key(CHAVE_NOVA) == hashlib.sha256(CHAVE_NOVA.encode()).hexdigest()
       and main._hash_api_key(CHAVE_NOVA) == HASH_NOVA,
       "o hash da aplicação bate com o do gerador e com o SHA-256 padrão")

# ── chave revogada não entra ──────────────────────────────────────────────
db_rev = banco([{"id": "k1", "empresa_nome": "Alfa", "empresa_id": "banco_alfa",
                 "api_key_hash": HASH_NOVA, "ativa": False}])
checar(main._buscar_api_key(db_rev, CHAVE_NOVA) is None,
       "chave revogada (ativa=false) para de autenticar na hora")

# ── retaguarda: banco ainda sem a coluna de hash ──────────────────────────
db_velho = banco([{"id": "k0", "empresa_nome": "MIZAN",
                   "api_key": CHAVE_ANTIGA, "ativa": True}])
checar(main._buscar_api_key(db_velho, CHAVE_ANTIGA) is not None,
       "chave antiga continua funcionando antes da migração rodar")
checar(main._buscar_api_key(db_velho, "outra") is None,
       "e a retaguarda não aceita qualquer coisa")

# ── rastro de uso ─────────────────────────────────────────────────────────
atualizacoes.clear()
main._marcar_uso_api_key(db, {"id": "k1"})
checar(len(atualizacoes) == 1 and "ultimo_uso" in atualizacoes[0][1],
       "o uso é registrado, para dar para saber se a chave ainda está viva",
       str(atualizacoes[0][1]) if atualizacoes else "nada gravado")

class QuebraTudo:
    def table(s, t): raise Exception("banco fora do ar")
main._marcar_uso_api_key(QuebraTudo(), {"id": "k1"})
checar(True, "e falhar ao gravar o rastro não derruba a requisição válida")

# ── o gerador ─────────────────────────────────────────────────────────────
c1, h1 = gerar("x")
c2, _ = gerar("x")
checar(c1 != c2, "cada chave gerada é diferente")
checar(len(c1) >= 40 and c1.startswith("mizan_"), "chave tem tamanho e prefixo esperados",
       f"{len(c1)} caracteres")
checar(hashlib.sha256(c1.encode()).hexdigest() == h1,
       "o gerador entrega o hash correspondente à chave")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
