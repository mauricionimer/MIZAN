"""Revisão da frente dos agentes analíticos (Estrategista, Acompanhamento,
Supervisor, passagem, Cientista e api). Um teste por correção, com dados fictícios."""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

for _v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_IA_PAPEIS",
           "MIZAN_ESTRATEGISTA_MAX"):
    os.environ.pop(_v, None)

from agente import api, auditor, ciencia, cientista, estrategista, passagem
from agente import orquestrador as orq
from agente.bateria.motor import DIA, devedor, em
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso
from agente.repositorio import RepoMemoria

REGRAS = auditor.POLITICA_DEMONSTRACAO
AGORA = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
falhas = 0


def checar(cond, texto, extra=""):
    global falhas
    print(("ok    " if cond else "FALHA ") + texto + (f" ({extra})" if extra and not cond else ""))
    if not cond:
        falhas += 1


def com_papeis(papeis):
    os.environ["MIZAN_IA_PAPEIS"] = ",".join(("triagem", "negociador") + tuple(papeis))


def sem_papeis():
    os.environ.pop("MIZAN_IA_PAPEIS", None)


# ── 1. grupo de entrada fixo: quem fechou acordo não some do Cientista ──────

def t_grupo_entrada():
    repo, fonte = RepoMemoria(), FonteMemoria([devedor(id="p1", probabilidade_pagamento=0.4)])
    repo.gravar_politica("emp", 1, {**REGRAS, "percentual_controle": 0})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "contato" and c["dados"]["grupo_entrada"] == "contato", "1. primeiro plano grava grupo_entrada")
    repo.salvar_caso(c["id"], {"situacao": "acordo_ativo"})
    estrategista.plano(repo, fonte, "emp", aplicar=True, agora=em(DIA + timedelta(days=1)))
    c = repo.caso_de("emp", "p1")
    checar(c["grupo"] == "so_lembrete" and c["dados"]["grupo_entrada"] == "contato",
           "1. plano seguinte muda o grupo, mas não o de entrada", str((c["grupo"], c["dados"].get("grupo_entrada"))))
    checar(len(cientista.observacoes(repo, fonte, "emp")) == 1, "1. caso com acordo continua na conta do Cientista")


TESTES = [t_grupo_entrada]

if __name__ == "__main__":
    for t in TESTES:
        try:
            t()
        except Exception as e:                          # um teste quebrado não esconde os outros
            import traceback
            traceback.print_exc()
            checar(False, f"{t.__name__} levantou {type(e).__name__}: {e}")
        finally:
            sem_papeis()
    print(f"\n{'TUDO OK' if not falhas else f'{falhas} falha(s)'}")
    sys.exit(falhas)
