"""Revisão do núcleo (18/10): cada correção da área 1 com o seu teste.

Retomada com o rascunho, esperas por evento, receber idempotente, falhas
momentâneas da IA (Gemini e Anthropic), teto que espera a meia-noite, dia de
Brasília, trava por execução no relógio real, fila por empresa, disponivel_em
explícito, evento preso em "processando" e o contrato do RepoSupabase com um
banco falso. Sem banco, sem IA, dados fictícios.

    python test_revisao_nucleo.py
"""
import http.client
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_PRECOS", "MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import auditor, llm                                   # noqa: E402
from agente import orquestrador as orq                             # noqa: E402
from agente.api import grafos                                      # noqa: E402
from agente.bateria.motor import DIA, ID_OK, Cenario, T, em, executar, tri  # noqa: E402
from agente.llm import ClienteFalso                                # noqa: E402
from agente.repositorio import (PRONTO_JA, EventoDuplicado, RepoMemoria,  # noqa: E402
                                RepoSupabase, agora_utc)

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

AGORA = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


class Ocupado(ClienteFalso):
    """Cota estourada na primeira chamada do negociador (ou nas `vezes` primeiras)."""
    def __init__(self, roteiro, vezes=1):
        super().__init__(roteiro)
        self.falta = vezes

    def gerar(self, **kw):
        if kw.get("papel") == "negociador" and self.falta > 0:
            self.falta -= 1
            raise llm.IaOcupada("Gemini HTTP 429", esperar_s=40)
        return super().gerar(**kw)


def textos(chamada) -> str:
    out = []
    for m in chamada["mensagens"]:
        c = m["content"]
        out.append(c if isinstance(c, str) else " ".join(b.get("text", "") for b in c))
    return "\n".join(out)


def pendentes(repo):
    return [e for e in repo.eventos.values() if e["situacao"] == "pendente"]


print("— 1. retomada depois da cota: o negociador recebe a mensagem e a triagem —")
c = Cenario("t", "t", "t", dados=dict(ID_OK), passos=[("mensagem", "ZEBRA quanto fica à vista?")], conferir=[])
cli = Ocupado({"triagem": [tri("pagar_negociar", ironia=True)], "negociador": [T("Posso simular para você.")]})
r = executar(c, cli)
caso = r.repo.casos[r.caso["id"]]
ck = (caso["dados"].get("_checkpoints") or {})
checar(len(ck) == 1 and list(ck.values())[0]["proximo"] == "negociar"
       and list(ck.values())[0]["saida"].get("texto", "").startswith("ZEBRA")
       and list(ck.values())[0]["saida"].get("triagem", {}).get("intencao") == "pagar_negociar",
       "checkpoint do evento guarda o próximo nó, o texto e a triagem")
checar(json.dumps(caso["dados"], default=None) is not None, "checkpoint é JSON puro (vai para o Supabase)")
pend = pendentes(r.repo)
orq.processar_fila(r.repo, grafos(r.fonte), cli, limite=5, agora=pend[0]["disponivel_em"] + timedelta(seconds=1))
neg = [ch for ch in cli.chamadas if ch["papel"] == "negociador"]
t = textos(neg[-1]) if neg else ""
checar("ZEBRA" in t, "a mensagem do devedor chega à IA depois da retomada")
briefing = json.loads(t.split("<briefing>")[1].split("</briefing>")[0]) if "<briefing>" in t else {}
checar(briefing.get("intencao_da_mensagem") == "pagar_negociar", "a triagem também volta",
       str(briefing.get("intencao_da_mensagem")))
checar(sum(1 for ch in cli.chamadas if ch["papel"] == "triagem") == 1, "a triagem não roda de novo (sem gasto a mais)")
caso = r.repo.casos[r.caso["id"]]
checar("_checkpoints" not in caso["dados"] and "_esperas_ia" not in caso["dados"],
       "ao terminar, checkpoint e contagem de esperas do evento somem")
checar(r.saidas or [m for m in r.repo.mensagens if m["direcao"] == "saida"], "o devedor recebe a resposta")
checar(sum(1 for m in r.repo.mensagens if m["direcao"] == "entrada") == 1, "a mensagem de entrada fica gravada uma vez só")

print("— 1b. segunda mensagem durante a espera não apaga o checkpoint da primeira —")
c = Cenario("t", "t", "t", dados=dict(ID_OK), passos=[("mensagem", "PRIMEIRA quanto fica?")], conferir=[])
cli = Ocupado({"triagem": [tri("pagar_negociar"), tri("duvida")],
               "negociador": [T("resposta B."), T("resposta A.")]})
r = executar(c, cli)
cid = r.caso["id"]
ev1 = pendentes(r.repo)[0]
orq.registrar_evento(r.repo, "emp", cid, "mensagem_devedor", "m2", {"texto": "SEGUNDA e aí?"})
orq.processar_fila(r.repo, grafos(r.fonte), cli, limite=5, agora=em(DIA) + timedelta(seconds=10))
ck = r.repo.casos[cid]["dados"].get("_checkpoints") or {}
checar(str(ev1["id"]) in ck and ck[str(ev1["id"])]["saida"].get("texto", "").startswith("PRIMEIRA"),
       "o checkpoint do primeiro evento continua lá")
checar((r.repo.casos[cid]["dados"].get("_esperas_ia") or {}).get(str(ev1["id"])) == 1,
       "a conta de esperas do primeiro evento continua lá")
orq.processar_fila(r.repo, grafos(r.fonte), cli, limite=5, agora=ev1["disponivel_em"] + timedelta(seconds=1))
neg = [ch for ch in cli.chamadas if ch["papel"] == "negociador"]
checar(any("PRIMEIRA" in textos(ch).split("<mensagem_do_devedor>")[-1] for ch in neg[-1:]),
       "na retomada, a IA responde à primeira mensagem")
checar(r.repo.eventos[ev1["id"]]["situacao"] == "feito" and r.repo.casos[cid]["situacao"] != "com_pessoa",
       "primeiro evento termina, sem passar para uma pessoa")

print("— 1c. esperas contadas por evento —")
repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
evs = [orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", f"k{i}")[0] for i in range(2)]
def sempre_ocupada(ctx):
    raise llm.IaOcupada("cota", esperar_s=30)
g = orq.Grafo("g", "a").no("a", sempre_ocupada, agente="negociador")
for _ in range(2):
    orq.processar_fila(repo, {"mensagem_devedor": g}, ClienteFalso(), agora=AGORA + timedelta(hours=_))
esperas = repo.casos[caso["id"]]["dados"].get("_esperas_ia") or {}
checar(esperas == {str(evs[0]["id"]): 2, str(evs[1]["id"]): 2}, "cada evento tem a sua conta", str(esperas))

print("— 1d. receber idempotente: a mesma entrada do mesmo evento não duplica —")
repo = RepoMemoria()
for _ in range(2):
    repo.gravar_mensagem("emp", "c1", "entrada", "oi", trace_id="t1")
repo.gravar_mensagem("emp", "c1", "entrada", "oi", trace_id="t2")
repo.gravar_mensagem("emp", "c1", "saida", "olá", trace_id="t1")
checar([m["trace_id"] for m in repo.mensagens] == ["t1", "t2", "t1"], "uma entrada por evento; saída não é afetada")

print("— 2. Gemini: falha momentânea vira IaOcupada (adia, não transfere) —")
import time as _time                                       # noqa: E402
_sleep_original = _time.sleep
_time.sleep = lambda s: None
_urlopen_original = urllib.request.urlopen


class Corpo:
    def __init__(self, bruto): self.bruto = bruto
    def read(self): return self.bruto
    def __enter__(self): return self
    def __exit__(self, *a): return False


def com_urlopen(acao):
    """Roda _enviar_http com urlopen falso; devolve ('ok'|nome da exceção, exceção)."""
    def falso(req, timeout=None):
        return acao()
    urllib.request.urlopen = falso
    try:
        llm._enviar_http("http://x", {}, "chave-ficticia", 1.0)
        return "ok", None
    except Exception as e:
        return type(e).__name__, e
    finally:
        urllib.request.urlopen = _urlopen_original


def http_erro(codigo, corpo: bytes):
    def f():
        raise urllib.error.HTTPError("http://x", codigo, "erro", {}, io.BytesIO(corpo))
    return f


def levanta(e):
    def f():
        raise e
    return f


casos = {
    "tempo esgotado": levanta(TimeoutError("timed out")),
    "URLError (DNS)": levanta(urllib.error.URLError("nome não resolvido")),
    "ConnectionResetError": levanta(ConnectionResetError()),
    "RemoteDisconnected": levanta(http.client.RemoteDisconnected("fechou")),
    "502 json": http_erro(502, b'{"error": {"status": "BAD_GATEWAY"}}'),
    "504 json": http_erro(504, b'{"error": {"status": "GATEWAY_TIMEOUT"}}'),
    "503 corpo HTML": http_erro(503, b"<html>Service Unavailable</html>"),
    "429 json": http_erro(429, b'{"error": {"status": "RESOURCE_EXHAUSTED"}}'),
    "200 corpo não JSON": lambda: Corpo(b"<html>proxy</html>"),
}
for nome, acao in casos.items():
    tipo, e = com_urlopen(acao)
    checar(tipo == "IaOcupada" and e.esperar_s >= 60, f"{nome} -> IaOcupada", tipo)
tipo, _ = com_urlopen(http_erro(400, b'{"error": {"status": "INVALID_ARGUMENT"}}'))
checar(tipo == "ErroGemini", "400 (pedido errado) continua ErroGemini", tipo)
tipo, _ = com_urlopen(http_erro(403, b"<html>proibido</html>"))
checar(tipo == "ErroGemini", "403 com corpo HTML não quebra com JSONDecodeError", tipo)
tipo, _ = com_urlopen(lambda: Corpo(b'{"candidates": []}'))
checar(tipo == "ok", "resposta normal passa")
conta = {"n": 0}
def falha_uma_vez():
    conta["n"] += 1
    if conta["n"] == 1:
        raise ConnectionResetError()
    return Corpo(b'{"candidates": []}')
tipo, _ = com_urlopen(falha_uma_vez)
# Sem nova tentativa dentro da requisição (_enviar_http: "o único responsável pela repetição é a
# fila"): a queda vira IaOcupada e a fila retoma do checkpoint. test_agente_latencia confere o mesmo.
checar(tipo == "IaOcupada" and conta["n"] == 1, "rede caiu: vira IaOcupada e a fila tenta de novo (sem repetir aqui)")
_time.sleep = _sleep_original

print("— 2b. Anthropic: cota, servidor, conexão e tempo esgotado viram IaOcupada —")
try:
    import anthropic
    import httpx
    req = httpx.Request("POST", "https://api.anthropic.invalid/v1/messages")
    resp = lambda c, h=None: httpx.Response(c, request=req, headers=h or {})
    erros = {
        "RateLimitError": anthropic.RateLimitError("cota", response=resp(429, {"retry-after": "120"}), body=None),
        "InternalServerError": anthropic.InternalServerError("caiu", response=resp(500), body=None),
        "APIConnectionError": anthropic.APIConnectionError(request=req),
        "APITimeoutError": anthropic.APITimeoutError(request=req),
    }

    class Sdk:
        def __init__(self, erro):
            self.messages = self
            self.erro = erro
        def create(self, **kw):
            raise self.erro

    os.environ["MIZAN_AGENTE_PRECOS"] = '{"modelo-ficticio": [1, 1]}'
    for nome, erro in erros.items():
        try:
            llm.ClienteAnthropic(sdk=Sdk(erro)).gerar(sistema="s", mensagens=[], modelo="modelo-ficticio")
            tipo, esp = "nada", None
        except Exception as e:
            tipo, esp = type(e).__name__, getattr(e, "esperar_s", None)
        checar(tipo == "IaOcupada", f"{nome} -> IaOcupada", tipo)
        if nome == "RateLimitError":
            checar(esp == 120.0, "retry-after da Anthropic vira o tempo de espera", str(esp))
    ruim = anthropic.BadRequestError("pedido ruim", response=resp(400), body=None)
    try:
        llm.ClienteAnthropic(sdk=Sdk(ruim)).gerar(sistema="s", mensagens=[], modelo="modelo-ficticio")
        tipo = "nada"
    except Exception as e:
        tipo = type(e).__name__
    checar(tipo == "BadRequestError", "pedido errado (400) não vira espera", tipo)
    os.environ.pop("MIZAN_AGENTE_PRECOS")
except ImportError:
    checar(True, "SDK da Anthropic ausente: conferência pulada")
guardado = sys.modules.get("anthropic")
sys.modules["anthropic"] = None                    # import passa a falhar
checar(llm._erros_momentaneos_anthropic() == (), "sem o SDK, a lista de erros fica vazia (import tolerante)")
if guardado is not None:
    sys.modules["anthropic"] = guardado
else:
    sys.modules.pop("anthropic")

print("— 3. teto do dia: espera a meia-noite de Brasília, sem transferir —")
os.environ["MIZAN_AGENTE_TETO_DIA_USD"] = "0"
noite = datetime(2026, 10, 16, 22, 30, tzinfo=auditor.BRASILIA).astimezone(timezone.utc)   # 01h30 UTC do dia 17
repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
repo.salvar_caso(caso["id"], {"situacao": "em_contato"})
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k1", {"texto": "oi"})
visto = {}
def guarda(ctx):
    ctx.saida["texto"] = "oi"; visto["hoje"] = ctx.hoje
def usa_ia(ctx):
    ctx.ia("negociador", "s", [{"role": "user", "content": "oi"}])
g = orq.Grafo("g", "a").no("a", guarda, seguinte="b").no("b", usa_ia, agente="negociador")
r = orq.processar_proximo(repo, {"mensagem_devedor": g}, ClienteFalso(), noite)
e = repo.eventos[ev["id"]]
meia_noite = datetime(2026, 10, 17, 0, 0, tzinfo=auditor.BRASILIA)
checar(r["ok"] and repo.casos[caso["id"]]["situacao"] == "em_contato", "caso continua com o agente")
checar(e["situacao"] == "pendente" and e["disponivel_em"] == meia_noite, "evento espera a meia-noite de Brasília",
       str(e["disponivel_em"]))
checar(any(p["no"] == "aguardar_teto" for p in repo.passos), "a espera aparece no rastreio")
ck = repo.casos[caso["id"]]["dados"]["_checkpoints"][str(ev["id"])]
checar(ck["proximo"] == "b" and ck["saida"].get("texto") == "oi", "e recomeça do nó da IA, com o rascunho")
checar(visto["hoje"] == date(2026, 10, 16), "ctx.hoje às 22h30 de Brasília ainda é o dia 16", str(visto["hoje"]))
os.environ.pop("MIZAN_AGENTE_TETO_DIA_USD")
checar(orq.proxima_meia_noite(datetime(2026, 10, 16, 2, 59, tzinfo=timezone.utc)) == datetime(2026, 10, 16, tzinfo=auditor.BRASILIA),
       "23h59 de Brasília: a meia-noite é a do dia seguinte de lá")

print("— 4. custo do dia de Brasília —")
repo = RepoMemoria()
repo.passos.append({"empresa_id": "emp", "custo_usd": 0.5,
                    "criado_em": datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)})   # 22h do dia 16 em Brasília
checar(repo.custo_do_dia("emp", date(2026, 10, 16)) == 0.5 and repo.custo_do_dia("emp", date(2026, 10, 17)) == 0,
       "passo das 22h de Brasília conta no dia de Brasília (memória)")


class Q:
    """Consulta falsa do supabase-py: guarda a cadeia e devolve a resposta da vez."""
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
    def ops(s, i=-1): return s.log[i][1]
    def nomes(s, i=-1): return [n for n, _ in s.log[i][1]]


db = DB(); rs = RepoSupabase(db)
db.resposta = [[{"custo_usd": 0.001}] * 1000, [{"custo_usd": 0.001}] * 500]
checar(rs.custo_do_dia("emp", date(2026, 10, 16)) == 1.5, "custo do Supabase soma todas as páginas (1500 linhas)")
checar([a for n, a in db.ops(0) if n == "range"] == [(0, 999)] and [a for n, a in db.ops(1) if n == "range"] == [(1000, 1999)],
       "pagina com .range de 1000 em 1000")
gte = [a[1] for n, a in db.ops(0) if n == "gte"][0]
checar(datetime.fromisoformat(gte) == datetime(2026, 10, 16, 3, 0, tzinfo=timezone.utc),
       "o dia começa à meia-noite de Brasília (03h UTC)", gte)

print("— 5. trava: dono por execução, relógio real, renovada a cada checkpoint —")
checar(orq.novo_dono() != orq.novo_dono() and orq.novo_dono().startswith(orq.DONO), "cada execução tem o seu dono")
repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k1")
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k2")
donos, travas = [], []
original = repo.travar_caso
def espia(caso_id, dono, ate, agora):
    donos.append(dono); return original(caso_id, dono, ate, agora)
repo.travar_caso = espia
relogio = {"t": datetime(2030, 1, 1, tzinfo=timezone.utc)}
def tique():
    relogio["t"] += timedelta(minutes=1); return relogio["t"]
real_original = orq.agora_real
orq.agora_real = tique
def anota(ctx):
    travas.append(repo.casos[caso["id"]]["trava_ate"])
g = orq.Grafo("g", "a").no("a", anota, seguinte="b").no("b", anota)
orq.processar_fila(repo, {"mensagem_devedor": g}, ClienteFalso(), agora=AGORA)
orq.agora_real = real_original
checar(len(donos) == 2 and donos[0] != donos[1], "processar_fila: um dono por evento processado")
checar(travas[0] > datetime(2030, 1, 1, tzinfo=timezone.utc), "a trava usa o relógio real, não o `agora` do evento")
checar(travas[1] > travas[0], "a trava é renovada no checkpoint entre os nós")
repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
real = orq.agora_real()
repo.travar_caso(caso["id"], "A", real + timedelta(minutes=5), real)
checar(not repo.travar_caso(caso["id"], "B", real + timedelta(minutes=5), real), "outra execução não pega trava válida")
checar(not repo.salvar_caso(caso["id"], {"situacao": "em_contato"}, dono="B"), "nem grava checkpoint por cima")

print("— 6. fila por empresa —")
repo = RepoMemoria()
ca, cb = repo.obter_ou_criar_caso("A", "p1"), repo.obter_ou_criar_caso("B", "p2")
ea, _ = orq.registrar_evento(repo, "A", ca["id"], "mensagem_devedor", "a1")
eb, _ = orq.registrar_evento(repo, "B", cb["id"], "pedido_parar", "b1")       # prioridade maior
g = orq.Grafo("g", "a").no("a", lambda ctx: None)
feitos = orq.processar_fila(repo, {"mensagem_devedor": g, "pedido_parar": g}, ClienteFalso(), agora=AGORA, empresa_id="A")
checar([f["evento_id"] for f in feitos] == [ea["id"]] and repo.eventos[eb["id"]]["situacao"] == "pendente",
       "rota da empresa A processa só a fila de A")
checar(len(repo.candidatos(AGORA)) == 1, "sem empresa, continua vendo todas (agendador)")

print("— 7. disponivel_em sempre explícito —")
class RepoComoSupabase(RepoMemoria):
    """Como o banco: sem disponivel_em no insert, vale o NOW() da hora do insert."""
    def inserir_evento(self, evento):
        evento = dict(evento)
        evento.setdefault("disponivel_em", agora_utc())
        return super().inserir_evento(evento)
repo = RepoComoSupabase(); caso = repo.obter_ou_criar_caso("emp", "p1")
agora = agora_utc()                                   # calculado ANTES de registrar (avisar_pagamento)
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "pagamento", "pg1", {"valor": 10.0})
feitos = orq.processar_fila(repo, {"pagamento": orq.Grafo("g", "a").no("a", lambda ctx: None)}, ClienteFalso(), agora=agora)
checar(len(feitos) == 1, "evento registrado depois do `agora` do chamador é processado na mesma chamada")
checar(ev["disponivel_em"] == PRONTO_JA, "sem data: 'pronto já', igual ao padrão do RepoMemoria")
ev2, _ = orq.registrar_evento(repo, "emp", caso["id"], "pagamento", "pg2", agora=AGORA)
checar(ev2["disponivel_em"] == AGORA, "com o agora do app, vale ele")
db = DB(); db.resposta = [[{"id": "e1"}]]
orq.registrar_evento(RepoSupabase(db), "emp", "c1", "pagamento", "pg3")
ins = [a[0] for n, a in db.ops() if n == "insert"][0]
checar(ins.get("disponivel_em") == PRONTO_JA.isoformat(), "no Supabase o insert leva disponivel_em", str(ins.get("disponivel_em")))

print("— 8. evento preso em 'processando' volta para a fila —")
repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k1")
checar(repo.reservar_evento(ev["id"]) and repo.eventos[ev["id"]]["disponivel_em"] > agora_utc(),
       "a reserva guarda até quando vale")
repo.eventos[ev["id"]]["disponivel_em"] = agora_utc() - timedelta(seconds=1)      # o processo morreu
g = orq.Grafo("g", "a").no("a", lambda ctx: None)
# A devolução usa o relógio real; o "agora" da fila precisa vir depois dele (AGORA é uma data fixa do passado).
feitos = orq.processar_fila(repo, {"mensagem_devedor": g}, ClienteFalso(), agora=agora_utc() + timedelta(minutes=1))
e = repo.eventos[ev["id"]]
checar(len(feitos) == 1 and e["situacao"] == "feito" and e["tentativas"] == 1, "reserva vencida: volta e é processado",
       f"{e['situacao']} {e['tentativas']}")
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k2")
repo.eventos[ev["id"]].update(situacao="processando", tentativas=1, disponivel_em=agora_utc() - timedelta(seconds=1))
orq.processar_fila(repo, {"mensagem_devedor": g}, ClienteFalso(), agora=AGORA)
checar(repo.eventos[ev["id"]]["situacao"] == "falhou", "na segunda vez, vira 'falhou' e aparece na Central")
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k3")
repo.reservar_evento(ev["id"])
checar(repo.devolver_presos(agora_utc(), 2) == 0 and repo.eventos[ev["id"]]["situacao"] == "processando",
       "reserva ainda valendo: não mexe")

repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k1")
orig = repo.reservar_evento
def quebra(eid, trace_id=None):
    if trace_id:                                   # o trace_id vai na mesma gravação da reserva
        raise ConnectionError("banco fora do ar")
    return orig(eid, trace_id)
repo.reservar_evento = quebra
r = orq.processar_proximo(repo, {"mensagem_devedor": g}, ClienteFalso(), AGORA)
checar(r is None and repo.eventos[ev["id"]]["situacao"] == "pendente",
       "banco cai ao gravar o trace_id (na reserva): o evento fica na fila (não fica preso)")

repo = RepoMemoria(); caso = repo.obter_ou_criar_caso("emp", "p1")
ev, _ = orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "k1", disponivel_em=AGORA)
real = orq.agora_real()
repo.travar_caso(caso["id"], "outro", real + timedelta(minutes=5), real)
orq.processar_proximo(repo, {"mensagem_devedor": g}, ClienteFalso(), AGORA)
checar(repo.eventos[ev["id"]]["situacao"] == "pendente" and repo.eventos[ev["id"]]["disponivel_em"] == AGORA,
       "caso ocupado: o evento volta como estava (sem atraso da reserva)")

print("— 9 e 10. contrato do RepoSupabase com banco falso —")
db = DB(); rs = RepoSupabase(db)
db.resposta = [[{"direcao": "entrada", "texto": "oi", "trace_id": "t1", "criado_em": "x"}]]
ms = rs.ultimas_mensagens("emp", "c1")
sel = [a[0] for n, a in db.ops() if n == "select"][0]
checar("trace_id" in sel and ms[0]["trace_id"] == "t1", "ultimas_mensagens traz o trace_id", sel)
db.resposta = [[]]
checar(rs.travar_caso("c1", "eu", AGORA + timedelta(minutes=5), AGORA) is False, "trava ocupada devolve False")
filtro = [a[0] for n, a in db.ops() if n == "or_"][0]
checar("trava_ate.is.null" in filtro and "trava_ate.lt.2026-10-16T12:00:00.000000Z" in filtro and "+" not in filtro,
       "trava: or_ com livre ou vencida, em UTC com Z, no mesmo UPDATE", filtro)
db.resposta = [[{"id": "e1"}]]
checar(rs.reservar_evento("e1") and ("eq", ("situacao", "pendente")) in db.ops(),
       "reservar_evento exige situacao pendente")
upd = [a[0] for n, a in db.ops() if n == "update"][0]
checar(upd["situacao"] == "processando" and datetime.fromisoformat(upd["disponivel_em"]) > agora_utc(),
       "e grava até quando a reserva vale")
db.resposta = [[]]
rs.salvar_caso("c1", {"situacao": "em_contato", "trava_ate": AGORA}, dono="eu")
checar(("eq", ("trava_dono", "eu")) in db.ops(), "salvar_caso com dono filtra pelo dono")
upd = [a[0] for n, a in db.ops() if n == "update"][0]
checar(upd["trava_ate"] == AGORA.isoformat(), "renovação da trava vai como texto ISO")
db.duplicar = True; db.resposta = [[{"id": "e1", "chave": "k"}]]
try:
    rs.inserir_evento({"empresa_id": "emp", "chave": "k", "caso_id": "c1", "tipo": "x"}); dup = False
except EventoDuplicado:
    dup = True
checar(dup, "chave repetida no banco vira EventoDuplicado")
db.duplicar = False
db.resposta = [[]]
rs.candidatos(AGORA, empresa_id="A")
checar(("eq", ("empresa_id", "A")) in db.ops() and ("eq", ("situacao", "pendente")) in db.ops(),
       "candidatos filtra pela empresa quando pedida")
db.resposta = [[{"id": "e9", "tentativas": 0, "disponivel_em": "2026-10-16T11:00:00+00:00"}], [{"id": "e9"}]]
n = rs.devolver_presos(AGORA, 2)
checar(n == 1 and ("eq", ("situacao", "processando")) in db.ops(-2) and ("eq", ("situacao", "processando")) in db.ops(-1)
       and [a[0] for nn, a in db.ops(-1) if nn == "update"][0]["situacao"] == "pendente",
       "devolver_presos: só o que ainda está processando, com update condicional")
db.resposta = [[]]
rs.devolver_evento("e1", AGORA)
checar(("eq", ("situacao", "processando")) in db.ops(), "devolver_evento só mexe em evento ainda reservado")
db.resposta = [[{"id": "m1"}]]
rs.gravar_mensagem("emp", "c1", "entrada", "oi", trace_id="t1")
checar(len(db.log) and not any(n == "insert" for n, _ in db.ops()), "entrada já gravada para o trace: não insere de novo")
db.resposta = [[]]
rs.gravar_mensagem("emp", "c1", "entrada", "oi", trace_id="t1")
checar(any(n == "insert" for n, _ in db.ops()), "primeira vez: insere")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
