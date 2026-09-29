"""Regressão: duas instâncias não se atropelam.

    python test_duas_instancias.py

O lock em memória (threading.RLock) protege uma máquina. Com duas, ele não
significa nada para a outra, e dois problemas aparecem:

  bandit      o estado é ler-alterar-gravar e o upsert é "o último vence".
              Dois feedbacks simultâneos em máquinas diferentes: um some, sem
              erro e sem log.
  agendador   roda dentro do processo do app. Os dois acordam no mesmo
              intervalo e disparam o mesmo retreino, disputando o estado das
              versões e o bucket de modelos.

O teste simula o banco compartilhado que as duas instâncias enxergam, e as
intercala no pior momento possível: entre a leitura e a gravação.
"""
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import numpy as np                                 # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── O banco que as duas instâncias compartilham ──────────────────────────
BANCO = {"bandit_estado": [], "travas": []}
_lock_banco = threading.Lock()


class Q:
    def __init__(self, tabela):
        self.tabela = tabela
        self.filtros = []
        self._op = None
        self._dados = None

    def select(self, *a, **k): self._op = "select"; return self
    def limit(self, n):        return self

    def eq(self, col, val):  self.filtros.append((col, "eq", val)); return self
    def lt(self, col, val):  self.filtros.append((col, "lt", val)); return self

    def insert(self, linha):  self._op, self._dados = "insert", linha; return self
    def update(self, patch):  self._op, self._dados = "update", patch; return self
    def delete(self):         self._op = "delete"; return self

    def _casa(self, linha):
        for col, modo, val in self.filtros:
            v = linha.get(col)
            if modo == "eq" and v != val:
                return False
            if modo == "lt" and not (v is not None and str(v) < str(val)):
                return False
        return True

    def execute(self):
        with _lock_banco:
            linhas = BANCO.setdefault(self.tabela, [])
            if self._op == "insert":
                chave = "empresa_id" if self.tabela == "bandit_estado" else "nome"
                if any(l.get(chave) == self._dados.get(chave) for l in linhas):
                    raise Exception("duplicate key value violates unique constraint")
                linhas.append(dict(self._dados))
                return type("R", (), {"data": [self._dados]})()
            casadas = [l for l in linhas if self._casa(l)]
            if self._op == "update":
                for l in casadas:
                    l.update(self._dados)
                return type("R", (), {"data": casadas})()
            if self._op == "delete":
                for l in casadas:
                    linhas.remove(l)
                return type("R", (), {"data": casadas})()
            return type("R", (), {"data": casadas})()


class DB:
    def table(self, nome): return Q(nome)


import db as _db_mod                                # noqa: E402
_db_mod.get_db = lambda: DB()

from model import bandit as B                       # noqa: E402
# Diretório limpo a cada execução: salvar_bandit também grava um .pkl local, e
# o resíduo de uma rodada anterior entraria como estado inicial desta.
import shutil                                       # noqa: E402
B.MODEL_DIR = Path("/tmp/bandit_teste")
shutil.rmtree(B.MODEL_DIR, ignore_errors=True)
B.MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. o feedback de ninguém se perde ────────────────────────────────────
print("— dois feedbacks, duas instâncias —")

CTX = [0.5] * B.D

# Instância A lê, e só então B lê, altera e grava. Depois A grava — é aqui que
# o estado de B seria apagado.
bandit_a, versao_a = B._carregar_com_versao("emp")
if bandit_a is None:
    bandit_a, versao_a = B.LinUCB(), 0
    B._gravar_se_versao("emp", bandit_a, 0)
    bandit_a, versao_a = B._carregar_com_versao("emp")

bandit_b, versao_b = B._carregar_com_versao("emp")
bandit_b.atualizar(0, np.array(CTX), 1.0)
ok_b = B._gravar_se_versao("emp", bandit_b, versao_b)
checar(ok_b, "a instância B grava primeiro")

bandit_a.atualizar(1, np.array(CTX), 1.0)
ok_a = B._gravar_se_versao("emp", bandit_a, versao_a)
checar(not ok_a, "e a A é recusada, porque leu uma versão que já mudou",
       "sem isto, a gravação da A apagaria o feedback da B em silêncio")

final, _ = B._carregar_com_versao("emp")
checar(final.n_tentativas[0] == 1, "o feedback da B está lá")
checar(final.n_tentativas[1] == 0, "e o da A ainda não — cabe ao chamador refazer")


# ── 2. registrar_resultado refaz sozinho ─────────────────────────────────
print("\n— o ciclo completo refaz o que perdeu —")
BANCO["bandit_estado"].clear()
B._bandit_cache.clear()
B._bandit_cache_ts.clear()

B.registrar_resultado(0, CTX, 1.0, "emp2")
B.registrar_resultado(1, CTX, 1.0, "emp2")

# agora um conflito de verdade: alguém grava entre a leitura e a gravação
original = B._gravar_se_versao
chamadas = {"n": 0}


def _com_interferencia(empresa_id, bandit, versao):
    chamadas["n"] += 1
    if chamadas["n"] == 1:
        # Outro processo grava primeiro, bem no meio do nosso ciclo.
        outro, v = B._carregar_com_versao(empresa_id)
        outro.atualizar(2, np.array(CTX), 1.0)
        original(empresa_id, outro, v)
    return original(empresa_id, bandit, versao)


B._gravar_se_versao = _com_interferencia
B.registrar_resultado(3, CTX, 1.0, "emp2")
B._gravar_se_versao = original

final, _ = B._carregar_com_versao("emp2")
checar(chamadas["n"] >= 2, "tentou de novo depois do conflito", f"{chamadas['n']} tentativas")
checar(final.n_tentativas[0] == 1 and final.n_tentativas[1] == 1,
       "os feedbacks anteriores continuam lá")
checar(final.n_tentativas[2] == 1, "o feedback do outro processo sobreviveu",
       "é exatamente o que o upsert apagava")
checar(final.n_tentativas[3] == 1, "e o nosso também",
       "nenhum dos dois se perdeu")


# ── 3. a trava do agendador ──────────────────────────────────────────────
print("\n— a trava do retreino —")
import travas                                        # noqa: E402

BANCO["travas"].clear()
checar(travas.adquirir("retreino") is True, "a primeira instância pega a trava")
checar(travas.adquirir("retreino") is False, "a segunda não pega",
       "senão os dois retreinariam ao mesmo tempo")

travas.liberar("retreino")
checar(travas.adquirir("retreino") is True, "liberada, a próxima pega")

# processo morto segurando a trava
BANCO["travas"][0]["expira_em"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
checar(travas.adquirir("retreino") is True, "trava vencida é tomada por outro",
       "sem prazo, um processo morto travaria o retreino para sempre")

# dois tentando tomar a mesma trava vencida: só um leva
BANCO["travas"][0]["expira_em"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
resultados = []


def tenta():
    resultados.append(travas.adquirir("retreino"))


ts = [threading.Thread(target=tenta) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
checar(sum(resultados) == 1, "com oito instâncias disputando, exatamente uma leva",
       f"levaram {sum(resultados)}")

# liberar não pode derrubar a trava de outro dono
dono_original = travas.DONO
travas.DONO = "outra-maquina:999"
travas.liberar("retreino")
travas.DONO = dono_original
checar(len(BANCO["travas"]) == 1, "liberar não derruba a trava de outro dono",
       "senão qualquer instância poderia soltar a trava alheia")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
