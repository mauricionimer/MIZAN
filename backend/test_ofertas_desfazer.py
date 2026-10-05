"""Desfazer uma oferta registrada por engano.

    python test_ofertas_desfazer.py
"""
import os, sys
from datetime import datetime, timedelta
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

TAB = {}
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)

class R:
    def __init__(s, d): s.data = d

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.apagar = False; s.lim = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def limit(s, n): s.lim = n; return s
    def delete(s): s.apagar = True; return s
    def execute(s):
        tab = TAB.setdefault(s.t, [])
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        if s.apagar:
            TAB[s.t] = [l for l in tab if l not in alvo]
        return R([dict(l) for l in (alvo[:s.lim] if s.lim else alvo)])

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(role="operador", sub="op-ana", empresa="goias"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ANA, BETO, ADM, OUTRA, CMD = jwt(), jwt(sub="op-beto"), jwt("admin", "adm"), jwt(empresa="beta", sub="op-x"), jwt("comando", "cmd", "")

def cenario(minutos=1, situacao="pendente", com_agenda=True):
    quando = (datetime.utcnow() - timedelta(minutes=minutos)).isoformat()
    TAB["ofertas_feitas"] = [{"id": "o1", "empresa_id": "goias", "operador_id": "op-ana", "cpf": "111",
                              "resposta": "aceitou", "contato_id": "c1", "created_at": quando}]
    TAB["contatos"] = [{"id": "c1", "empresa_id": "goias", "cpf": "111"}, {"id": "c2", "empresa_id": "goias", "cpf": "111"}]
    TAB["agenda"] = ([{"id": "a1", "empresa_id": "goias", "contato_id": "c1", "situacao": situacao}] if com_agenda else []) + \
                    [{"id": "a2", "empresa_id": "goias", "contato_id": "c2", "situacao": "pendente"}]
D = lambda h, id_="o1": c.delete(f"/ofertas/{id_}", headers=h)

print("— desfazer —")
cenario()
r = D(ANA)
checar(r.status_code == 200 and r.json()["agenda_removida"] == 1, "quem registrou desfaz dentro do prazo", r.text[:120])
checar(TAB["ofertas_feitas"] == [], "a oferta sai do histórico")
checar([x["id"] for x in TAB["contatos"]] == ["c2"], "o contato que ela criou sai; os outros ficam")
checar([x["id"] for x in TAB["agenda"]] == ["a2"], "a promessa dela sai da Agenda; as outras ficam")
checar(AUD and AUD[-1]["acao"] == "oferta_desfeita" and AUD[-1]["detalhes"]["resposta"] == "aceitou", "fica na auditoria")
checar(D(ANA).status_code == 404, "desfazer duas vezes: a segunda recebe 404")

print("— limites —")
cenario(minutos=main.JANELA_DESFAZER_MIN + 1)
r = D(ANA)
checar(r.status_code == 409 and "prazo" in r.json()["detail"], "operador depois do prazo: 409", r.text[:120])
checar(len(TAB["ofertas_feitas"]) == 1, "e nada é apagado")
checar(D(ADM).status_code == 200, "o administrador desfaz depois do prazo")
cenario()
checar(D(BETO).status_code == 403, "outro operador não desfaz (403)")
checar(D(OUTRA).status_code == 404, "outra empresa: 404")
checar(D(CMD).status_code == 403, "comando não desfaz")
cenario(situacao="cumprida")
r = D(ANA)
checar(r.status_code == 409 and "Agenda" in r.json()["detail"], "promessa já resolvida na Agenda: 409 sem apagar nada", r.text[:120])
checar(len(TAB["ofertas_feitas"]) == 1 and len(TAB["contatos"]) == 2, "e o histórico fica intacto")
cenario(com_agenda=False)
checar(D(ANA).status_code == 200 and TAB["ofertas_feitas"] == [], "oferta recusada (sem compromisso na Agenda) também desfaz")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
