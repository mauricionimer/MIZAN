"""F3 — painel do operador: contagens reais por período.

    python test_painel_operador.py
"""
import os, sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import agenda, painel                              # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

HOJE = date(2026, 10, 14)
agenda.hoje = lambda: HOJE

def em(dias_atras, hora=12):
    """created_at em UTC de um horário de Brasília `dias_atras` dias antes de hoje."""
    local = datetime.combine(HOJE - timedelta(days=dias_atras), time(hora, 0), tzinfo=agenda.FUSO)
    return local.astimezone(timezone.utc).isoformat()

print("— período —")
checar(painel.inicio_do_periodo("hoje", HOJE) == HOJE, "hoje começa hoje")
checar(painel.inicio_do_periodo("7d", HOJE) == HOJE - timedelta(days=6), "7 dias inclui hoje")
checar(painel.meia_noite_utc(HOJE) == "2026-10-14T03:00:00+00:00", "meia-noite de Brasília em UTC")
try:
    painel.inicio_do_periodo("ano", HOJE); checar(False, "período inválido recusa")
except ValueError:
    checar(True, "período inválido recusa")
checar(painel._dia_local(em(0, 23)) == HOJE, "23h de Brasília continua sendo hoje (já é amanhã em UTC)")

TAB = {
    "usuarios": [
        {"id": "op-ana", "nome": "Ana", "role": "operador", "ativo": True, "empresa_id": "goias"},
        {"id": "op-beto", "nome": "Beto", "role": "operador", "ativo": True, "empresa_id": "goias"},
        {"id": "op-ex", "nome": "Ex", "role": "operador", "ativo": False, "empresa_id": "goias"},
        {"id": "adm", "nome": "Adm", "role": "admin", "ativo": True, "empresa_id": "goias"},
    ],
    "contatos": [
        {"id": 1, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "contactado", "created_at": em(0, 9)},
        {"id": 2, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "sem_resposta", "created_at": em(0, 10)},
        {"id": 3, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "prometeu_pagar", "created_at": em(0, 23)},
        {"id": 4, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "contactado", "created_at": em(3)},
        {"id": 5, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "nao_quis", "created_at": em(20)},
        {"id": 6, "empresa_id": "goias", "usuario_id": "op-beto", "resultado": "contactado", "created_at": em(0)},
        {"id": 7, "empresa_id": "beta", "usuario_id": "op-ana", "resultado": "contactado", "created_at": em(0)},
        {"id": 8, "empresa_id": "goias", "usuario_id": "op-ana", "resultado": "contactado", "created_at": em(1, 22)},
    ],
    "agenda": [
        {"id": "a1", "empresa_id": "goias", "operador_id": "op-ana", "tipo": "promessa", "situacao": "pendente", "valor": 500, "created_at": em(0)},
        {"id": "a2", "empresa_id": "goias", "operador_id": "op-ana", "tipo": "promessa", "situacao": "cumprida", "valor": 300, "created_at": em(4)},
        {"id": "a3", "empresa_id": "goias", "operador_id": "op-ana", "tipo": "promessa", "situacao": "quebrada", "valor": 200, "created_at": em(5)},
        {"id": "a4", "empresa_id": "goias", "operador_id": "op-ana", "tipo": "retorno", "situacao": "pendente", "created_at": em(0)},
        {"id": "a5", "empresa_id": "goias", "operador_id": "op-beto", "tipo": "promessa", "situacao": "pendente", "valor": 90, "created_at": em(0)},
    ],
    "feedbacks": [
        {"id": "f1", "empresa": "goias", "pagou": True, "valor_recuperado": 300, "predicao_id": "p1", "created_at": em(2)},
        {"id": "f2", "empresa": "goias", "pagou": True, "valor_recuperado": 1000, "predicao_id": "p2", "created_at": em(0)},
        {"id": "f3", "empresa": "goias", "pagou": False, "valor_recuperado": 0, "predicao_id": "p1", "created_at": em(0)},
        {"id": "f4", "empresa": "goias", "pagou": True, "valor_recuperado": 70, "predicao_id": "p3", "created_at": em(0)},
        {"id": "f5", "empresa": "beta", "pagou": True, "valor_recuperado": 999, "predicao_id": "p1", "created_at": em(0)},
        {"id": "f6", "empresa": "goias", "pagou": True, "valor_recuperado": 40, "predicao_id": "p1", "created_at": em(40)},
    ],
    "predicoes": [
        {"id": "p1", "responsavel_id": "op-ana"}, {"id": "p2", "responsavel_id": "op-beto"}, {"id": "p3", "responsavel_id": None},
    ],
}
MODO = {"sem_agenda": False, "sem_responsavel": False}
EXTRA = {"goias": {"meta_contatos_dia": 4}}
main._extra_empresa = lambda emp: EXTRA.get(emp, {})

class R:
    def __init__(s, data): s.data = data; s.count = None

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.rng = None; s.lim = None; s.cols = ""
    def select(s, cols="*", **k): s.cols = cols; return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def gte(s, c, v): s.f.append(lambda l: str(l.get(c) or "") >= v); return s
    def in_(s, c, vs): vs = set(vs); s.f.append(lambda l: l.get(c) in vs); return s
    def order(s, *a, **k): return s
    def range(s, i, f): s.rng = (i, f); return s
    def limit(s, n): s.lim = n; return s
    def execute(s):
        if MODO["sem_agenda"] and s.t == "agenda":
            raise Exception('relation "public.agenda" does not exist')
        if MODO["sem_responsavel"] and s.t == "predicoes" and "responsavel" in s.cols:
            raise Exception("column predicoes.responsavel_id does not exist")
        d = [dict(l) for l in TAB.get(s.t, []) if all(f(l) for f in s.f)]
        if s.rng: d = d[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: d = d[:s.lim]
        return R(d)

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="operador", sub="op-ana"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ANA, BETO, ADM, CMD = jwt("goias"), jwt("goias", sub="op-beto"), jwt("goias", "admin", "adm"), jwt("", "comando", "cmd")

print("— meu painel —")
r = c.get("/painel/operador?periodo=hoje", headers=ANA).json()
checar(r["contatos"] == 3, "hoje: 3 contatos da Ana (o das 23h conta; outra empresa e o colega não)", str(r["contatos"]))
checar(r["contatos_efetivos"] == 2 and r["taxa_contato_efetivo"] == round(2 / 3, 4), "contato efetivo exclui 'sem resposta'")
checar(r["acordos"] == 1 and r["acordos_valor"] == 500, "acordos = promessas registradas hoje (retorno não conta)")
checar(r["recebido"] == 0 and r["pagamentos"] == 0, "hoje não entrou nada da carteira dela")
checar(r["meta_dia"] == 4 and r["contatos_hoje"] == 3 and r["meta_pct"] == 0.75, "meta: 3 de 4")
r = c.get("/painel/operador?periodo=7d", headers=ANA).json()
checar(r["contatos"] == 5 and r["contatos_hoje"] == 3, "7 dias: 5 contatos; a meta continua sendo a de hoje", str(r["contatos"]))
checar((r["acordos"], r["promessas_cumpridas"], r["promessas_quebradas"], r["promessas_pendentes"]) == (3, 1, 1, 1),
       "promessas por situação")
checar(r["recebido"] == 300 and r["pagamentos"] == 1,
       "recebido: só pagamento confirmado de devedor dela (não pago, outra empresa e fora do período não entram)")
r = c.get("/painel/operador?periodo=30d", headers=ANA).json()
checar(r["contatos"] == 6 and r["recebido"] == 300, "30 dias", f'{r["contatos"]} {r["recebido"]}')
checar(c.get("/painel/operador?periodo=ano", headers=ANA).status_code == 422, "período inválido: 422")
checar(c.get("/painel/operador", headers=CMD).status_code == 403, "comando não tem painel próprio")
EXTRA["goias"] = {}
r = c.get("/painel/operador", headers=ANA).json()
checar(r["meta_dia"] is None and r["meta_pct"] is None, "sem meta em Premissas, sem barra")
EXTRA["goias"] = {"meta_contatos_dia": 4}

print("— equipe —")
checar(c.get("/painel/equipe", headers=ANA).status_code == 403, "operador não vê a equipe")
r = c.get("/painel/equipe?periodo=7d", headers=ADM).json()
nomes = [l["nome"] for l in r["operadores"]]
checar(nomes == ["Beto", "Ana"], "uma linha por operador ativo, ordenada pelo recebido", str(nomes))
beto = r["operadores"][0]
checar(beto["recebido"] == 1000 and beto["contatos"] == 1 and beto["acordos"] == 1, "números do Beto")
checar(r["recebido_sem_responsavel"] == 70, "pagamento de devedor sem responsável aparece à parte")
checar(r["total"]["recebido"] == 1370 and r["total"]["contatos"] == 6, "total da equipe", str(r["total"]["recebido"]))
checar(c.get("/painel/equipe", headers=CMD).status_code == 400, "comando precisa escolher a empresa")
checar(c.get("/painel/equipe?empresa_id=goias", headers=CMD).status_code == 200, "comando lê a empresa escolhida")

print("— um operador por vez (visão do administrador) —")
for l in TAB["contatos"]:
    l["cpf"] = {1: "111", 2: "111", 3: "222", 4: "333", 5: "333", 6: "444", 8: "555"}.get(l["id"])
TAB["ofertas_feitas"] = [
    {"id": "o1", "empresa_id": "goias", "operador_id": "op-ana", "resposta": "aceitou", "created_at": em(0)},
    {"id": "o2", "empresa_id": "goias", "operador_id": "op-ana", "resposta": "recusou", "created_at": em(1)},
    {"id": "o3", "empresa_id": "goias", "operador_id": "op-ana", "resposta": "vai_pensar", "created_at": em(2)},
    {"id": "o4", "empresa_id": "goias", "operador_id": "op-beto", "resposta": "aceitou", "created_at": em(0)},
    {"id": "o5", "empresa_id": "goias", "operador_id": "op-ana", "resposta": "aceitou", "created_at": em(40)}]
r = c.get("/painel/operador/op-ana?periodo=7d", headers=ADM)
j = r.json()
checar(r.status_code == 200 and j["operador"]["nome"] == "Ana", "admin abre o painel de um operador", r.text[:100])
checar(j["contatos"] == 5 and j["devedores_trabalhados"] == 4, "contatos e devedores trabalhados (cpfs distintos) só dele", str((j["contatos"], j["devedores_trabalhados"])))
checar(j["ofertas"] == {"feitas": 3, "aceitas": 1, "vai_pensar": 1, "recusadas": 1, "ativo": True}, "ofertas feitas, aceitas, a pensar e recusadas no período", str(j["ofertas"]))
checar(j["retornos"]["marcados"] == 1 and j["retornos"]["pendentes"] == 1, "retornos marcados e pendentes", str(j["retornos"]))
checar(j["recebido"] == 300 and j["acordos"] == 3, "recebido e promessas dele", str((j["recebido"], j["acordos"])))
checar(c.get("/painel/operador/op-beto?periodo=7d", headers=ADM).json()["ofertas"]["feitas"] == 1, "cada operador com os seus números")
checar(c.get("/painel/operador/op-ana", headers=ANA).status_code in (403, 404, 405) or c.get("/painel/operador/op-ana", headers=ANA).status_code == 403, "operador não abre o painel de outro")
checar(c.get("/painel/operador/adm", headers=ADM).status_code == 404, "quem não é operador: 404")
checar(c.get("/painel/operador/op-ana?periodo=7d", headers=jwt("beta", "admin", "adm2")).status_code == 404, "admin de outra empresa: 404")
checar(c.get("/painel/operador/op-ana?periodo=7d&empresa_id=goias", headers=CMD).status_code == 200, "comando lê pela empresa escolhida")

print("— sem o SQL novo —")
MODO.update(sem_agenda=True, sem_responsavel=True)
r = c.get("/painel/operador?periodo=7d", headers=ANA)
j = r.json()
checar(r.status_code == 200 and j["contatos"] == 5, "contatos continuam valendo")
checar(j["agenda_ativa"] is False and j["acordos"] == 0, "sem agenda: acordos zerados e marcados")
checar(j["divisao_ativa"] is False and j["recebido"] == 0, "sem divisão: recebido da carteira dele não é atribuído")
MODO.update(sem_agenda=False, sem_responsavel=False)

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
