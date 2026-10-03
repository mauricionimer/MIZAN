"""Regressão: os endpoints não podem voltar a bloquear o event loop, e o
estado global do bandit não pode perder feedback sob concorrência.

    python test_concorrencia.py       (ou python -m pytest test_concorrencia.py)

Dois problemas diferentes, ligados pela mesma causa:

1. Um `async def` sem nenhum `await` roda o corpo inteiro DENTRO do event
   loop. Como o cliente do Supabase é síncrono, cada consulta congelava o
   processo todo: as requisições viravam fila. Tirando o `async`, o FastAPI
   passa a rodar o endpoint em threadpool e elas andam em paralelo.

2. Com os endpoints em paralelo de verdade, o ciclo ler -> alterar -> gravar
   do bandit (registrar_resultado) deixou de ser protegido pelo event loop e
   passou a precisar de lock explícito — senão dois feedbacks simultâneos
   leem o mesmo estado e um sobrescreve o outro, em silêncio.
"""
import ast
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ---------------------------------------------------------------------------
# 1. Nenhum endpoint async sem await
# ---------------------------------------------------------------------------

# lifespan é um @asynccontextmanager com yield: tem de continuar async.
MANTER_ASYNC = {"lifespan"}


class _TemAwait(ast.NodeVisitor):
    def __init__(self):
        self.found = False

    def visit_Await(self, n):
        self.found = True

    def visit_AsyncFor(self, n):
        self.found = True
        self.generic_visit(n)

    def visit_AsyncWith(self, n):
        self.found = True
        self.generic_visit(n)

    # não desce em funções aninhadas: o await delas é delas
    def visit_AsyncFunctionDef(self, n):
        pass

    def visit_FunctionDef(self, n):
        pass


def _async_sem_await(caminho: Path) -> list[str]:
    tree = ast.parse(caminho.read_text())
    achados = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef) or node.name in MANTER_ASYNC:
            continue
        v = _TemAwait()
        for filho in node.body:
            v.visit(filho)
        if not v.found:
            achados.append(f"{node.name} (linha {node.lineno})")
    return achados


culpados = _async_sem_await(AQUI / "main.py")
checar(
    not culpados,
    "nenhum endpoint é async sem await",
    "cada um desses bloqueia o event loop: " + ", ".join(culpados) if culpados else
    "quem não usa await roda em threadpool",
)


# ---------------------------------------------------------------------------
# 1b. Quem é async de verdade tira o trabalho pesado do event loop
# ---------------------------------------------------------------------------

# Estes ficaram async porque precisam de `await file.read()` — mas o que vem
# depois (parsear planilha, pontuar carteira, gravar no Supabase) é bloqueante
# e tem de rodar em asyncio.to_thread, senão o await não adianta nada.
PRECISAM_TO_THREAD = {
    "analisar", "upload_csv", "upload_empresa_foto", "feedback_lote",
    "sincronizar_conexao", "scheduler_verificar_agora", "auto_sync_executar",
    "db_sync_executar",
}


def _chama_to_thread(node) -> bool:
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "to_thread"):
            return True
    return False


_tree = ast.parse((AQUI / "main.py").read_text())
_assincronos = {n.name: n for n in ast.walk(_tree)
                if isinstance(n, ast.AsyncFunctionDef)}
sem_thread = sorted(
    nome for nome in PRECISAM_TO_THREAD
    if nome in _assincronos and not _chama_to_thread(_assincronos[nome])
)
ausentes = sorted(PRECISAM_TO_THREAD - set(_assincronos))
checar(not sem_thread, "endpoint async manda o trabalho pesado para threadpool",
       "ainda bloqueiam o event loop: " + ", ".join(sem_thread) if sem_thread else
       f"{len(PRECISAM_TO_THREAD)} conferidos")
checar(not ausentes, "a lista conferida corresponde ao código",
       "sumiram ou deixaram de ser async: " + ", ".join(ausentes) if ausentes else
       "nenhum nome órfão")


# ---------------------------------------------------------------------------
# 2. O bandit não perde feedback concorrente
# ---------------------------------------------------------------------------

os.environ["MIZAN_DATA_DIR"] = tempfile.mkdtemp()
Path(os.environ["MIZAN_DATA_DIR"], "model").mkdir(parents=True, exist_ok=True)

import numpy as np                                          # noqa: E402
from model import bandit as B                               # noqa: E402

B._salvar_supabase = lambda e, b: None                      # isola de rede
B._carregar_supabase = lambda e: None

N = 40
CTX = [0.5] * B.D
EMP = "empresa_teste"

# O atualizar real faz "self.n_tentativas[a] += 1" e "self.A[a] += ...".
# Nenhum dos dois é atômico — são ler, somar, gravar. Abaixo é a MESMA
# sequência, só escrita passo a passo com uma pausa no meio, para a colisão
# ser determinística no teste em vez de rara por operação. Em produção a
# janela é de microssegundos: a perda é menor, mas existe e é silenciosa.
def _atualizar_lento(self, acao, contexto, recompensa, pagou=None):
    x = contexto.astype(float)
    a_lido, b_lido = self.A[acao], self.b[acao]
    n_lido, r_lido = self.n_tentativas[acao], self.recompensa_acumulada[acao]
    time.sleep(0.002)
    self.A[acao] = a_lido + np.outer(x, x)
    self.b[acao] = b_lido + recompensa * x
    self.n_tentativas[acao] = n_lido + 1
    self.recompensa_acumulada[acao] = r_lido + recompensa


class _SemLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _rodar(com_lock: bool) -> int:
    B._bandit_cache[EMP], B._bandit_cache_ts[EMP] = B.LinUCB(), time.monotonic()
    original = B._bandit_lock
    if not com_lock:
        B._bandit_lock = _SemLock()
    try:
        with ThreadPoolExecutor(max_workers=N) as ex:
            list(ex.map(lambda _: B.registrar_resultado(0, CTX, 0.5, EMP), range(N)))
    finally:
        B._bandit_lock = original
    return sum(B._bandit_cache[EMP].n_tentativas)


_atualizar_original = B.LinUCB.atualizar
B.LinUCB.atualizar = _atualizar_lento
try:
    sem_lock = _rodar(com_lock=False)
    com_lock = _rodar(com_lock=True)
finally:
    B.LinUCB.atualizar = _atualizar_original

checar(com_lock == N, "todo feedback concorrente é contabilizado",
       f"{com_lock} de {N}")
checar(sem_lock < N, "sem o lock a corrida realmente acontece",
       f"{N - sem_lock} de {N} feedbacks perdidos — senão este teste não provaria nada")

# o lock não pode ter quebrado o caminho normal
B._bandit_cache[EMP], B._bandit_cache_ts[EMP] = B.LinUCB(), time.monotonic()
B.registrar_resultado(3, CTX, 0.8, EMP)
checar(B._bandit_cache[EMP].n_tentativas[3] == 1, "feedback isolado continua funcionando")
rec = B.recomendar({"score_recuperabilidade": 60, "dias_em_atraso": 90,
                    "valor_divida": 5000, "renda_estimada": 3000,
                    "produto": "cartao", "uf": "GO"}, EMP)
checar(0 <= rec["acao_id"] < B.N_ACOES, "recomendar continua funcionando sob lock",
       rec["label"])

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
