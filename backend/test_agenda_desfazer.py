"""Desfazer na Agenda: reabrir um compromisso resolvido por engano.

    python test_agenda_desfazer.py
"""
import os, sys
from datetime import date, datetime, timedelta
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import agenda                                      # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

HOJE = date(2026, 10, 14)
agenda.hoje = lambda: HOJE
TAB = {"agenda": []}
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)
ANTES_DO_UPDATE = []          # gancho para simular outra pessoa mexendo no meio

class R:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.patch = None; s.lim = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def limit(s, n): s.lim = n; return s
    def update(s, p): s.patch = p; return s
    def execute(s):
        if s.patch is not None:
            while ANTES_DO_UPDATE:
                ANTES_DO_UPDATE.pop(0)()
        alvo = [l for l in TAB[s.t] if all(f(l) for f in s.f)]
        if s.patch is not None:
            for l in alvo: l.update(s.patch)
        alvo = [dict(l) for l in alvo]
        return R(alvo[:s.lim] if s.lim else alvo)

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(role="operador", sub="op-ana", empresa="goias"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ANA, BETO, ADM, OUTRA = jwt(), jwt(sub="op-beto"), jwt("admin", "adm"), jwt(empresa="beta", sub="op-x")

def novo(id_, **k):
    TAB["agenda"].append({"id": id_, "empresa_id": "goias", "operador_id": "op-ana", "tipo": "promessa",
                          "data": (HOJE + timedelta(days=1)).isoformat(), "situacao": "pendente", **k})
def item(id_): return next(l for l in TAB["agenda"] if l["id"] == id_)
P = lambda id_, h, **b: c.patch(f"/agenda/{id_}", json=b, headers=h)

print("— resolver e desfazer —")
novo("a1")
r = P("a1", ANA, acao="quebrar")
checar(r.status_code == 200 and r.json()["anterior"] == "pendente" and r.json()["desfazer_ate_min"] == main.JANELA_DESFAZER_MIN,
       "resolver devolve o estado anterior e a janela de desfazer")
r = P("a1", ANA, acao="reabrir", situacao_esperada="quebrada")
checar(r.status_code == 200 and item("a1")["situacao"] == "pendente" and item("a1")["resolvido_em"] is None
       and item("a1")["resolvido_por"] is None, "desfazer volta ao estado anterior no banco", r.text[:100])
checar(r.json()["item"]["nivel"] == "medio", "e o item volta com o nível (para reaparecer na coluna certa)")
checar(AUD and AUD[-1]["acao"] == "agenda_reaberta" and AUD[-1]["detalhes"]["estava"] == "quebrada", "a reabertura fica na auditoria")
for acao, sit in [("cumprir", "cumprida"), ("cancelar", "cancelada")]:
    P("a1", ANA, acao=acao)
    r = P("a1", ANA, acao="reabrir", situacao_esperada=sit)
    checar(r.status_code == 200 and item("a1")["situacao"] == "pendente", f"desfazer '{acao}'")

print("— cliques repetidos e concorrência —")
P("a1", ANA, acao="quebrar")
checar(P("a1", ANA, acao="quebrar").status_code == 409, "clicar duas vezes em 'Não pagou': o segundo recebe 409")
P("a1", ANA, acao="reabrir", situacao_esperada="quebrada")
checar(P("a1", ANA, acao="reabrir", situacao_esperada="quebrada").status_code == 409, "clicar duas vezes em 'Desfazer': o segundo recebe 409")
checar(item("a1")["situacao"] == "pendente", "e o estado fica certo")
P("a1", ANA, acao="cumprir")
r = P("a1", ANA, acao="reabrir", situacao_esperada="quebrada")
checar(r.status_code == 409 and "Outra pessoa" in r.json()["detail"], "desfazer com estado diferente do que a tela viu: 409")
checar(item("a1")["situacao"] == "cumprida", "e não mexe no que a outra pessoa fez")
P("a1", ADM, acao="reabrir")
# outra pessoa resolve entre a leitura e a gravação
ANTES_DO_UPDATE.append(lambda: item("a1").update(situacao="cancelada", resolvido_em=datetime.utcnow().isoformat()))
r = P("a1", ANA, acao="quebrar")
checar(r.status_code == 409 and item("a1")["situacao"] == "cancelada", "corrida entre duas pessoas: a gravação é condicional e a segunda recebe 409")

print("— limites —")
novo("a2")
checar(P("a2", ANA, acao="reabrir").status_code == 409, "reabrir o que já está em aberto: 409")
P("a2", ANA, acao="quebrar")
item("a2")["resolvido_em"] = (datetime.utcnow() - timedelta(minutes=main.JANELA_DESFAZER_MIN + 1)).isoformat()
r = P("a2", ANA, acao="reabrir", situacao_esperada="quebrada")
checar(r.status_code == 409 and "prazo" in r.json()["detail"], "operador depois do prazo: 409 explicando", r.text[:120])
r = P("a2", ADM, acao="reabrir", situacao_esperada="quebrada")
checar(r.status_code == 200 and item("a2")["situacao"] == "pendente", "admin reabre a qualquer momento")
novo("a3", situacao="cumprida", resolvido_por="pagamento confirmado", resolvido_em=datetime.utcnow().isoformat())
r = P("a3", ADM, acao="reabrir")
checar(r.status_code == 409 and "Pagamentos" in r.json()["detail"], "promessa cumprida por pagamento confirmado não reabre por aqui")
novo("a4", operador_id="op-beto")
P("a4", BETO, acao="quebrar")
checar(P("a4", ANA, acao="reabrir").status_code == 403, "operador não reabre o compromisso do colega")
checar(P("a4", OUTRA, acao="reabrir").status_code == 404, "outra empresa: 404")
checar(P("a4", jwt("comando", "cmd", ""), acao="reabrir").status_code == 403, "comando não mexe")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
