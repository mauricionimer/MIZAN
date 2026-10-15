"""Agentes, Parte 1 — orquestrador: fila, prioridade, idempotência, trava,
grafo, checkpoint, nó de erro e fila de falhas. Sem banco e sem IA.

    python test_agente_orquestrador.py
"""
import os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_PRECOS", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import orquestrador as orq             # noqa: E402
from agente.llm import ClienteFalso                # noqa: E402
from agente.repositorio import RepoMemoria, RepoSupabase, EventoDuplicado  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

AGORA = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)

def novo(repo, pid="p1"):
    return repo.obter_ou_criar_caso("emp", pid)

def grafo_simples(log):
    def contato(ctx):
        log.append("contato"); ctx.mudar_situacao("em_contato")
    def negociar(ctx):
        log.append("negociar"); ctx.mudar_situacao("negociando")
    return (orq.Grafo("mensagem", "contato")
            .no("contato", contato, seguinte="negociar")
            .no("negociar", negociar, agente="negociador"))

print("— idempotência e prioridade —")
repo = RepoMemoria(); caso = novo(repo)
e1, n1 = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "wa:msg-1")
e2, n2 = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "wa:msg-1")
checar(n1 and not n2 and e1["id"] == e2["id"] and len(repo.eventos) == 1, "mesma chave vira um evento só")
repo = RepoMemoria(); c1 = novo(repo, "p1"); c2 = novo(repo, "p2")
orq.registrar_evento(repo, "emp", c1["id"], "relogio", "r1")
orq.registrar_evento(repo, "emp", c2["id"], "mensagem_devedor", "m1")
ordem = [orq.processar_proximo(repo, {"relogio": grafo_simples([]), "mensagem_devedor": grafo_simples([])},
                               ClienteFalso(), AGORA)["evento_id"] for _ in range(2)]
checar([repo.eventos[i]["tipo"] for i in ordem] == ["mensagem_devedor", "relogio"],
       "mensagem do devedor passa na frente do relógio")
checar(orq.PRIORIDADE["pedido_parar"] > orq.PRIORIDADE["contestacao"] > orq.PRIORIDADE["mensagem_devedor"]
       > orq.PRIORIDADE["pagamento"] > orq.PRIORIDADE["vencimento"] > orq.PRIORIDADE["relogio"],
       "parar > contestação > mensagem > pagamento > vencimento > relógio")
checar(orq.processar_proximo(repo, {}, ClienteFalso(), AGORA) is None, "fila vazia: nada a fazer")

print("— grafo, rastreio e checkpoint —")
repo = RepoMemoria(); caso = novo(repo); log = []
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
r = orq.processar_proximo(repo, {"mensagem_devedor": grafo_simples(log)}, ClienteFalso(), AGORA)
c = repo.obter_caso(caso["id"])
checar(r["ok"] and log == ["contato", "negociar"] and c["situacao"] == "negociando", "percorre os nós em ordem")
checar(repo.eventos[ev["id"]]["situacao"] == "feito" and repo.eventos[ev["id"]]["trace_id"] == r["trace_id"],
       "evento feito, com trace")
checar([p["no"] for p in repo.passos] == ["contato", "negociar"] and repo.passos[1]["agente"] == "negociador"
       and all(p["trace_id"] == r["trace_id"] for p in repo.passos), "um passo por nó, no mesmo trace")
checar("_checkpoint" not in c["dados"] and c["ultimo_passo"] == "negociar", "checkpoint limpo ao terminar")
checar(c["trava_dono"] is None, "trava solta ao terminar")

repo = RepoMemoria(); caso = novo(repo); log = []
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
repo.salvar_caso(caso["id"], {"situacao": "em_contato",
                              "dados": {"_checkpoint": {"evento_id": ev["id"], "proximo": "negociar"}}})
orq.processar_proximo(repo, {"mensagem_devedor": grafo_simples(log)}, ClienteFalso(), AGORA)
checar(log == ["negociar"], "depois de cair, o mesmo evento recomeça do nó seguinte ao último concluído")
repo = RepoMemoria(); caso = novo(repo); log = []
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m2")
repo.salvar_caso(caso["id"], {"dados": {"_checkpoint": {"evento_id": "outro", "proximo": "negociar"}}})
orq.processar_proximo(repo, {"mensagem_devedor": grafo_simples(log)}, ClienteFalso(), AGORA)
checar(log == ["contato", "negociar"], "checkpoint de outro evento não vale para este")

print("— nó de erro —")
def com_no(funcao, situacao="em_contato"):
    repo = RepoMemoria(); caso = novo(repo)
    repo.salvar_caso(caso["id"], {"situacao": situacao})
    ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
    g = orq.Grafo("g", "a").no("a", funcao)
    r = orq.processar_proximo(repo, {"mensagem_devedor": g}, ClienteFalso(["resposta"]), AGORA)
    return repo, repo.obter_caso(caso["id"]), repo.eventos[ev["id"]], r

conta = {"n": 0}
def falha_uma_vez(ctx):
    conta["n"] += 1
    if conta["n"] == 1:
        raise TimeoutError()
repo, c, e, r = com_no(falha_uma_vez)
checar(r["ok"] and c["situacao"] == "em_contato" and [p["resultado"] for p in repo.passos] == ["erro", "ok"],
       "falhou uma vez: tenta de novo e segue")

def sempre_falha(ctx):
    raise TimeoutError()
repo, c, e, r = com_no(sempre_falha)
checar(not r["ok"] and c["situacao"] == "com_pessoa", "falhou duas vezes: vai para uma pessoa")
checar(e["situacao"] == "feito" and e["erro"] == "TimeoutError", "evento fechado com o motivo")
checar([p["no"] for p in repo.passos] == ["a", "a", "erro"] and repo.passos[-1]["detalhe"] == {"motivo": "TimeoutError"},
       "nó de erro registrado no rastreio")
repo, c, e, r = com_no(sempre_falha, situacao="suspenso")
checar(c["situacao"] == "suspenso", "caso suspenso continua suspenso (não vira 'com pessoa' por cima)")

def proibido(ctx):
    ctx.mudar_situacao("quitado")
repo, c, e, r = com_no(proibido)
checar(c["situacao"] == "com_pessoa" and r["erro"] == "TransicaoProibida" and len(repo.passos) == 2,
       "mudança proibida: sem nova tentativa, vai para uma pessoa")

os.environ["MIZAN_AGENTE_TETO_DIA_USD"] = "0"
chamou = {"ia": False}
def usa_ia(ctx):
    ctx.ia("negociador", "s", [{"conteudo": "oi"}]); chamou["ia"] = True
repo, c, e, r = com_no(usa_ia)
checar(r["erro"] == "TetoExcedido" and not chamou["ia"] and c["situacao"] == "com_pessoa",
       "teto de custo atingido: não chama a IA, vai para uma pessoa")
os.environ.pop("MIZAN_AGENTE_TETO_DIA_USD")
repo, c, e, r = com_no(usa_ia)
checar(r["ok"] and repo.passos[0]["tokens_entrada"] > 0 and repo.passos[0]["modelo"] == "falso",
       "abaixo do teto: chama e registra tokens no passo")

repo = RepoMemoria(); caso = novo(repo)
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
laco = orq.Grafo("g", "a").no("a", lambda ctx: None, seguinte="a")
r = orq.processar_proximo(repo, {"mensagem_devedor": laco}, ClienteFalso(), AGORA)
checar(r["erro"] == "LacoNoGrafo" and repo.obter_caso(caso["id"])["situacao"] == "com_pessoa", "laço no grafo para")
repo = RepoMemoria(); caso = novo(repo)
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
torto = orq.Grafo("g", "a").no("a", lambda ctx: None, seguinte=lambda ctx: "sumiu")
r = orq.processar_proximo(repo, {"mensagem_devedor": torto}, ClienteFalso(), AGORA)
checar(r["erro"] == "ValueError" and repo.obter_caso(caso["id"])["situacao"] == "com_pessoa",
       "aresta para nó inexistente vai para uma pessoa")
try:
    orq.Grafo("g", "a").no("a", lambda ctx: None, seguinte="b").validar(); ok = False
except ValueError:
    ok = True
checar(ok, "validar() acha aresta quebrada antes de rodar")

print("— trava por caso —")
repo = RepoMemoria(); caso = novo(repo); log = []
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
repo.travar_caso(caso["id"], "outro-processo", AGORA + timedelta(minutes=3), AGORA)
r = orq.processar_proximo(repo, {"mensagem_devedor": grafo_simples(log)}, ClienteFalso(), AGORA)
checar(r is None and log == [] and list(repo.eventos.values())[0]["situacao"] == "pendente",
       "caso ocupado: o evento espera na fila")
r = orq.processar_proximo(repo, {"mensagem_devedor": grafo_simples(log)}, ClienteFalso(), AGORA + timedelta(minutes=4))
checar(r is not None and r["ok"], "trava vencida (processo morreu): outro assume")

repo = RepoMemoria(); caso = novo(repo)
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
def rouba_trava(ctx):
    repo.casos[caso["id"]]["trava_dono"] = "intruso"
g = orq.Grafo("g", "a").no("a", rouba_trava)
r = orq.processar_proximo(repo, {"mensagem_devedor": g}, ClienteFalso(), AGORA)
checar(not r["ok"] and r["situacao_evento"] == "pendente", "perdeu a trava no meio: não grava por cima, volta para a fila")

print("— fila de falhas —")
repo = RepoMemoria(); caso = novo(repo)
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "desconhecido", "x1")
r1 = orq.processar_proximo(repo, {}, ClienteFalso(), AGORA)
checar(r1["situacao_evento"] == "pendente" and repo.eventos[ev["id"]]["tentativas"] == 1, "primeira falha: volta para a fila")
checar(orq.processar_proximo(repo, {}, ClienteFalso(), AGORA) is None, "e espera antes de tentar de novo")
r2 = orq.processar_proximo(repo, {}, ClienteFalso(), AGORA + timedelta(minutes=2))
checar(r2["situacao_evento"] == "falhou" and repo.eventos[ev["id"]]["erro"] == "LookupError",
       "segunda falha: 'falhou', com o motivo, para a Central")
checar(repo.casos[caso["id"]]["trava_dono"] is None, "trava solta mesmo na falha")

repo = RepoMemoria(); c1 = novo(repo, "p1"); c2 = novo(repo, "p2")
for i, c in enumerate((c1, c2, c1)):
    orq.registrar_evento(repo, "emp", c["id"], "mensagem_devedor", f"m{i}")
feitos = orq.processar_fila(repo, {"mensagem_devedor": grafo_simples([])}, ClienteFalso(), agora=AGORA)
checar(len(feitos) == 3, "processar_fila esvazia a fila")

print("— Supabase: reservas condicionais (sem banco de verdade) —")
class Q:
    def __init__(s, db, t): s.db, s.t, s.ops = db, t, []
    def __getattr__(s, nome):
        def f(*a, **k):
            s.ops.append((nome, a)); return s
        return f
    def insert(s, d):
        s.ops.append(("insert", (d,)))
        if s.db.duplicar:
            raise Exception("duplicate key value violates unique constraint")
        return s
    def execute(s):
        s.db.log.append((s.t, s.ops))
        class R: pass
        r = R(); r.data = s.db.resposta.pop(0) if s.db.resposta else []
        return r
class DB:
    def __init__(s): s.log, s.resposta, s.duplicar = [], [], False
    def table(s, t): return Q(s, t)
db = DB(); rs = RepoSupabase(db)
db.resposta = [[]]
checar(rs.travar_caso("c1", "eu", AGORA + timedelta(minutes=5), AGORA) is False, "trava ocupada devolve False")
ops = db.log[-1][1]
filtro = [a[0] for n, a in ops if n == "or_"][0]
checar("trava_ate.is.null" in filtro and "trava_ate.lt.2026-10-16T12:00:00.000000Z" in filtro and "+" not in filtro,
       "trava só pega caso livre ou vencido, no mesmo UPDATE")
db.resposta = [[{"id": "e1"}]]
checar(rs.reservar_evento("e1") and ("eq", ("situacao", "pendente")) in db.log[-1][1],
       "reserva do evento exige que ainda esteja pendente")
db.resposta = [[]]
rs.salvar_caso("c1", {"situacao": "em_contato"}, dono="eu")
checar(("eq", ("trava_dono", "eu")) in db.log[-1][1], "checkpoint só grava se a trava ainda é deste processo")
db.duplicar = True; db.resposta = [[{"id": "e1", "chave": "k"}]]
try:
    rs.inserir_evento({"empresa_id": "emp", "chave": "k", "caso_id": "c1", "tipo": "x"}); dup = False
except EventoDuplicado:
    dup = True
checar(dup, "chave repetida no banco vira EventoDuplicado")
db.duplicar = False; db.resposta = [[{"custo_usd": "0.0012"}, {"custo_usd": 0.0008}]]
checar(rs.custo_do_dia("emp", AGORA.date()) == 0.002, "custo do dia soma os passos da empresa")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
