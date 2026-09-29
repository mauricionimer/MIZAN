"""Regressão: as rotas de retenção, com banco simulado.

    python test_retencao_api.py

Duas coisas precisam ser verdade aqui, e a segunda é a que assusta:

  1. Sem prazo configurado, executar é recusado. A prévia continua
     respondendo — é preciso ver o que um prazo levaria antes de escolher um.
  2. A anonimização não pode vazar entre clientes. Cada tabela guarda o dono
     de um jeito diferente: predições só por meio da carteira, feedbacks numa
     coluna `empresa`, contatos e recomendações em `empresa_id`. Errar o
     escopo em qualquer uma delas significa apagar o CPF do banco errado.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                    # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402
from auth import criar_token                   # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


AGORA = datetime.now(timezone.utc)


def quando(dias):
    return (AGORA - timedelta(days=dias)).isoformat()


# ── Banco simulado ───────────────────────────────────────────────────────
# Duas empresas com dados velhos. Se o escopo falhar, o teste vê linha de
# banco_beta sendo anonimizada num pedido de banco_alfa.
BASE = {
    "carteiras": [
        {"id": "cart-alfa", "empresa_id": "banco_alfa"},
        {"id": "cart-beta", "empresa_id": "banco_beta"},
    ],
    "predicoes": [
        {"id": "p-alfa-velha", "carteira_id": "cart-alfa", "cpf": "111", "created_at": quando(500), "anonimizado_em": None},
        {"id": "p-alfa-nova",  "carteira_id": "cart-alfa", "cpf": "222", "created_at": quando(10),  "anonimizado_em": None},
        {"id": "p-beta-velha", "carteira_id": "cart-beta", "cpf": "333", "created_at": quando(500), "anonimizado_em": None},
    ],
    "feedbacks": [
        {"id": "f-alfa", "empresa": "banco_alfa", "cpf": "111", "created_at": quando(490), "anonimizado_em": None},
        {"id": "f-beta", "empresa": "banco_beta", "cpf": "333", "created_at": quando(490), "anonimizado_em": None},
    ],
    "contatos": [
        {"id": "c-alfa", "empresa_id": "banco_alfa", "cpf": "111", "created_at": quando(480), "anonimizado_em": None},
        {"id": "c-beta", "empresa_id": "banco_beta", "cpf": "333", "created_at": quando(480), "anonimizado_em": None},
    ],
    "recomendacoes": [
        {"id": "r-alfa", "empresa_id": "banco_alfa", "cpf": "111", "created_at": quando(470), "anonimizado_em": None},
    ],
    "empresa_config": [],
}

gravacoes = []   # (tabela, patch, ids)


class Q:
    def __init__(self, tabela, linhas):
        self.tabela, self.linhas = tabela, list(linhas)
        self._patch = None

    def select(self, *a, **k):  return self
    def limit(self, n):          return self
    def order(self, *a, **k):    return self
    def range(self, *a, **k):    return self

    def eq(self, col, val):
        self.linhas = [l for l in self.linhas if l.get(col) == val]
        return self

    def in_(self, col, vals):
        vals = set(vals)
        self.linhas = [l for l in self.linhas if l.get(col) in vals]
        return self

    def is_(self, col, _null):
        self.linhas = [l for l in self.linhas if l.get(col) is None]
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def execute(self):
        if self._patch is not None:
            ids = [l["id"] for l in self.linhas]
            gravacoes.append((self.tabela, self._patch, ids))
            for l in self.linhas:
                l.update(self._patch)
            return type("R", (), {"data": self.linhas})()
        return type("R", (), {"data": self.linhas})()


class DB:
    def table(self, nome):
        return Q(nome, BASE.get(nome, []))


main.get_db = lambda: DB()
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
main._registrar_auditoria = lambda *a, **k: None

POLITICA = {}
main._extra_empresa = lambda eid: POLITICA.get(eid, {})

c = TestClient(main.app)


def token(role="admin", empresa="banco_alfa"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "a@a.com", "nome": "A", "role": role, "empresa_id": empresa})}


# ── 1. sem configuração ──────────────────────────────────────────────────
print("— sem prazo configurado —")

r = c.get("/retencao", headers=token())
checar(r.status_code == 200, "a prévia responde mesmo sem política", str(r.status_code))
corpo = r.json()
checar(corpo["politica"]["ativa"] is False, "a política vem desligada")
checar(corpo["prazo_simulado"] > 0, "mas a prévia simula um prazo para dar o número")
checar(corpo["previa"]["predicoes"]["vencidas"] == 1,
       "a prévia conta só a predição velha da empresa certa",
       str(corpo["previa"]))
checar(gravacoes == [], "a prévia não grava nada")

r = c.post("/retencao/executar", headers=token())
checar(r.status_code == 400, "executar sem prazo é recusado", str(r.status_code))
checar(gravacoes == [], "e nada foi tocado")


# ── 2. o operador não manda nisso ────────────────────────────────────────
print("\n— permissão —")
checar(c.get("/retencao", headers=token("operador")).status_code == 403,
       "operador não vê a retenção")
checar(c.post("/retencao/executar", headers=token("operador")).status_code == 403,
       "operador não executa")


# ── 3. prazo inválido é recusado ─────────────────────────────────────────
print("\n— prazo fora dos limites —")
POLITICA["banco_alfa"] = {"retencao": {"ativa": True, "dias": 5}}
r = c.post("/retencao/executar", headers=token())
checar(r.status_code == 400, "5 dias é recusado na execução", str(r.status_code))
checar(gravacoes == [], "e nada foi tocado")


# ── 4. execução, e o escopo por empresa ──────────────────────────────────
print("\n— execução —")
POLITICA["banco_alfa"] = {"retencao": {"ativa": True, "dias": 365}}
r = c.post("/retencao/executar", headers=token())
checar(r.status_code == 200, "executa com prazo válido", str(r.status_code))
corpo = r.json()
checar(corpo["anonimizadas"]["predicoes"] == 1, "uma predição anonimizada")
checar(corpo["anonimizadas"]["feedbacks"] == 1, "um feedback anonimizado")
checar(corpo["anonimizadas"]["contatos"] == 1, "um contato anonimizado")
checar(corpo["anonimizadas"]["recomendacoes"] == 1, "uma recomendação anonimizada")

por_id = {l["id"]: l for t in ("predicoes", "feedbacks", "contatos", "recomendacoes")
          for l in BASE[t]}

checar(por_id["p-alfa-velha"]["cpf"] is None, "a predição velha perdeu o CPF")
checar(por_id["p-alfa-nova"]["cpf"] == "222", "a predição recente manteve o CPF")
checar(por_id["p-beta-velha"]["cpf"] == "333",
       "a predição do OUTRO banco não foi tocada",
       "escopo por carteira — é aqui que um erro vazaria entre clientes")
checar(por_id["f-beta"]["cpf"] == "333", "o feedback do outro banco não foi tocado")
checar(por_id["c-beta"]["cpf"] == "333", "o contato do outro banco não foi tocado")

patch_pred = [g for g in gravacoes if g[0] == "predicoes"][0][1]
checar("valor_divida" not in patch_pred and "score_recuperabilidade" not in patch_pred,
       "o patch não toca nas variáveis do modelo",
       "é o que mantém o treino vivo depois da anonimização")

# rodar de novo não deve reescrever nada
antes = len(gravacoes)
r = c.post("/retencao/executar", headers=token())
checar(r.json()["total"] == 0, "a segunda execução não encontra nada",
       "linha anonimizada não volta à fila")


# ── 5. pedido do titular ─────────────────────────────────────────────────
print("\n— pedido do titular (art. 18) —")
# O CPF é gravado como veio do arquivo do cliente. As três formas que
# aparecem de verdade: com pontuação, só dígitos, e sem o zero à esquerda que
# o Excel comeu. O titular manda uma; a base tem outra.
BASE["predicoes"] += [
    {"id": "p-pontuado", "carteira_id": "cart-alfa", "cpf": "012.345.678-90",
     "created_at": quando(3), "anonimizado_em": None},
    {"id": "p-digitos",  "carteira_id": "cart-alfa", "cpf": "01234567890",
     "created_at": quando(3), "anonimizado_em": None},
    {"id": "p-sem-zero", "carteira_id": "cart-alfa", "cpf": "1234567890",
     "created_at": quando(3), "anonimizado_em": None},
]

r = c.post("/retencao/titular", headers=token(), json={"cpf": "012.345.678-90"})
checar(r.status_code == 200, "aceita o CPF com pontuação", str(r.status_code))

por_pred = {l["id"]: l for l in BASE["predicoes"]}
checar(por_pred["p-pontuado"]["cpf"] is None, "acha a linha gravada com pontuação")
checar(por_pred["p-digitos"]["cpf"] is None, "acha a mesma pessoa gravada só com dígitos")
checar(por_pred["p-sem-zero"]["cpf"] is None,
       "e a linha que perdeu o zero à esquerda no Excel",
       "procurar uma forma só deixaria o titular sem resposta")
checar(por_pred["p-alfa-nova"]["cpf"] == "222",
       "e não leva junto o CPF de outra pessoa")
checar(por_pred["p-pontuado"]["anonimizado_em"] is not None,
       "o CPF sai mesmo com 3 dias de base",
       "o titular pediu; o prazo não vem ao caso")

r = c.post("/retencao/titular", headers=token(), json={"cpf": "abc"})
checar(r.status_code == 400, "CPF sem dígito é recusado")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
