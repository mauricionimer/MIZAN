"""Cobertura regressiva do log operacional dos agentes.

Rode: python test_agente_logs.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from agente import api, orquestrador as orq  # noqa: E402
from agente.llm import ClienteFalso  # noqa: E402
from agente.repositorio import RepoMemoria  # noqa: E402

FALHAS = 0
AGORA = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def checar(condicao, texto):
    global FALHAS
    print(f"{'ok  ' if condicao else 'FALHA'}  {texto}")
    FALHAS += 0 if condicao else 1


def caso(repo):
    return repo.obter_ou_criar_caso("empresa", "predicao")


print("— falha de nó e passagem para equipe —")
repo = RepoMemoria(); c = caso(repo)
orq.registrar_evento(repo, "empresa", c["id"], "mensagem_devedor", "falha-no")

def falhar(_ctx):
    # Nunca deve aparecer no log, nem como parte de uma mensagem de exceção.
    raise TimeoutError("conteúdo confidencial do devedor")

grafo = orq.Grafo("teste", "negociar").no("negociar", falhar, agente="negociador")
r = orq.processar_proximo(repo, {"mensagem_devedor": grafo}, ClienteFalso(), AGORA)
logs = repo.logs_operacionais("empresa")
categorias = [l["categoria"] for l in logs]
checar(not r["ok"] and {"no_falhou", "falha_final", "encaminhado_equipe"}.issubset(categorias),
       "cada tentativa, falha final e passagem para equipe ficam registradas")
checar(all("confidencial" not in str(l) and "devedor" not in str(l.get("detalhe")) for l in logs),
       "log operacional não guarda texto nem dado do devedor")
checar(all(set(l["detalhe"]).issubset({"no", "erro", "evento_tipo", "tentativa", "esperar_s", "vez", "quantidade"}) for l in logs),
       "detalhe tem somente campos técnicos permitidos")

print("— reserva segura da IA —")
repo = RepoMemoria(); c = caso(repo)
orq.registrar_evento(repo, "empresa", c["id"], "mensagem_devedor", "reserva-ia")

def reserva_ia(ctx):
    retorno = ctx.ia_ou_codigo("negociador", lambda: (_ for _ in ()).throw(ConnectionError("texto externo")),
                               lambda: "reserva")
    assert retorno == "reserva"

grafo = orq.Grafo("teste", "negociar").no("negociar", reserva_ia, agente="negociador")
orq.processar_proximo(repo, {"mensagem_devedor": grafo}, ClienteFalso(), AGORA)
logs = repo.logs_operacionais("empresa")
checar(any(l["categoria"] == "ia_reserva" and l["agente"] == "negociador" for l in logs),
       "falha da IA com reserva em código aparece no monitoramento do agente")

print("— falha fora do grafo e Central —")
repo = RepoMemoria(); c = caso(repo)
orq.registrar_evento(repo, "empresa", c["id"], "desconhecido", "evento-invalido")
orq.processar_proximo(repo, {}, ClienteFalso(), AGORA)
orq.processar_proximo(repo, {}, ClienteFalso(), AGORA.replace(minute=2))
logs = repo.logs_operacionais("empresa")
checar({"evento_retentativa", "evento_falhou"}.issubset({l["categoria"] for l in logs}),
       "a primeira e a última falha do evento são distinguíveis")
anterior = api.fabrica_repo
api.fabrica_repo = lambda: repo
try:
    central = api.central("empresa", AGORA)
finally:
    api.fabrica_repo = anterior
checar(central["monitoramento"]["disponivel"] and central["monitoramento"]["logs"],
       "Central entrega os logs para a tela")

print()
print(f"{FALHAS} falha(s)")
sys.exit(1 if FALHAS else 0)
