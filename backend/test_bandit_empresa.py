"""Regressão: o bandit de uma empresa não pode aprender com a outra.

    python test_bandit_empresa.py     (ou python -m pytest test_bandit_empresa.py)

O bandit era global: uma tabela com uma linha só, compartilhada por todos os
clientes. Na prática, o feedback do Banco A mudava a recomendação que o
Banco B recebia — e o mesmo CPF pode dever aos dois. Agora cada empresa tem
o seu estado, e quem chega sem empresa no contexto cai numa chave separada,
nunca na de um cliente real.
"""
import os
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ["MIZAN_DATA_DIR"] = tempfile.mkdtemp()
Path(os.environ["MIZAN_DATA_DIR"], "model").mkdir(parents=True, exist_ok=True)

from model import bandit as B  # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# Banco em memória: uma linha por empresa, igual ao Supabase depois da migração
_tabela: dict = {}
B._salvar_supabase = lambda emp, bandit: _tabela.__setitem__(emp, B._bandit_para_json(bandit))
B._carregar_supabase = lambda emp: (B._bandit_de_json(_tabela[emp]) if emp in _tabela else None)

CTX = [0.5] * B.D
ALFA, BETA = "banco_alfa", "goias_bank"

# ── Alfa dá 5 feedbacks na ação 0; Beta não dá nenhum ──────────────────────
for _ in range(5):
    B.registrar_resultado(acao_id=0, contexto=CTX, recompensa=1.0, empresa_id=ALFA)

alfa = B.carregar_bandit(ALFA)
beta = B.carregar_bandit(BETA)

checar(alfa.n_tentativas[0] == 5, "o feedback conta para a empresa que o registrou",
       f"alfa={alfa.n_tentativas[0]}")
checar(sum(beta.n_tentativas) == 0, "a outra empresa continua zerada",
       f"beta={sum(beta.n_tentativas)} interações — se fosse >0, o bandit estaria vazando")

# ── Beta aprende outra coisa: as duas políticas seguem separadas ───────────
for _ in range(3):
    B.registrar_resultado(acao_id=7, contexto=CTX, recompensa=1.0, empresa_id=BETA)

alfa = B.carregar_bandit(ALFA)
beta = B.carregar_bandit(BETA)
checar(alfa.n_tentativas[7] == 0 and beta.n_tentativas[7] == 3,
       "cada empresa aprende só a própria ação",
       f"ação 7: alfa={alfa.n_tentativas[7]}, beta={beta.n_tentativas[7]}")
checar(alfa.n_tentativas[0] == 5 and beta.n_tentativas[0] == 0,
       "o aprendizado anterior não foi sobrescrito pela outra empresa")
checar(set(_tabela) == {ALFA, BETA}, "uma linha por empresa no banco",
       ", ".join(sorted(_tabela)))

# ── alpha é por empresa ────────────────────────────────────────────────────
B.ajustar_alpha(2.5, empresa_id=ALFA)
checar(B.carregar_bandit(ALFA).alpha == 2.5 and B.carregar_bandit(BETA).alpha != 2.5,
       "alterar a exploração de uma empresa não mexe na outra",
       f"alfa={B.carregar_bandit(ALFA).alpha}, beta={B.carregar_bandit(BETA).alpha}")

# ── sem empresa no contexto: chave separada, nunca a de um cliente ─────────
B.registrar_resultado(acao_id=11, contexto=CTX, recompensa=1.0, empresa_id=None)
checar(B.EMPRESA_PADRAO in _tabela, "empresa ausente cai na chave reservada",
       B.EMPRESA_PADRAO)
checar(B.carregar_bandit(ALFA).n_tentativas[11] == 0
       and B.carregar_bandit(BETA).n_tentativas[11] == 0,
       "o que chega sem empresa não contamina nenhum cliente")

# ── a chave é normalizada, senão " Alfa " viraria um terceiro cliente ──────
checar(B._chave("  Banco_Alfa  ") == ALFA, "empresa_id é normalizado (espaço e caixa)")
checar(B.carregar_bandit("  BANCO_ALFA ").n_tentativas[0] == 5,
       "a mesma empresa escrita diferente cai no mesmo bandit")

# ── recomendar respeita a empresa ──────────────────────────────────────────
devedor = {"score_recuperabilidade": 60, "dias_em_atraso": 90, "valor_divida": 5000,
           "renda_estimada": 3000, "produto": "cartao", "uf": "GO"}
r_alfa = B.recomendar(devedor, empresa_id=ALFA)
r_beta = B.recomendar(devedor, empresa_id=BETA)
checar(r_alfa["total_interacoes"] == 5 and r_beta["total_interacoes"] == 3,
       "a recomendação enxerga só o histórico da própria empresa",
       f"alfa={r_alfa['total_interacoes']}, beta={r_beta['total_interacoes']}")

# ── nenhuma função pública aceita chamada sem empresa ──────────────────────
import inspect  # noqa: E402
sem_empresa = [
    nome for nome in ("carregar_bandit", "salvar_bandit", "recomendar",
                      "registrar_resultado", "convergencia_stats", "ajustar_alpha")
    if "empresa_id" not in inspect.signature(getattr(B, nome)).parameters
]
checar(not sem_empresa, "toda função pública do bandit exige a empresa",
       "sem empresa_id: " + ", ".join(sem_empresa) if sem_empresa else "6 conferidas")

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
