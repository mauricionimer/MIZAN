"""F4 — roteiros de abordagem.

    python test_roteiros.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
import roteiros                                    # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

print("— validação —")
ok = roteiros.validar(" Oi ", "whatsapp", "", " Olá {primeiro_nome}, aqui é {operador}. ")
checar(ok == {"titulo": "Oi", "canal": "whatsapp", "oferta": None, "texto": "Olá {primeiro_nome}, aqui é {operador}."},
       "limpa espaços e oferta vazia vira nenhuma")
for args, msg in [(("x", "whatsapp", None, "Olá, tudo bem?"), "título curto"),
                  (("Oi", "fax", None, "Olá, tudo bem?"), "canal desconhecido"),
                  (("Oi", "sms", "brinde", "Olá, tudo bem?"), "oferta fora do catálogo"),
                  (("Oi", "sms", None, "Oi"), "texto curto"),
                  (("Oi", "sms", None, "x" * 2001), "texto longo"),
                  (("Oi", "sms", None, "Olá {cpf}, pague {valor_divida}"), "variável desconhecida")]:
    try:
        roteiros.validar(*args); checar(False, f"recusa {msg}")
    except ValueError as e:
        checar(True, f"recusa {msg}", str(e)[:70] if msg == "variável desconhecida" else "")
padroes = roteiros.padroes()
checar(len(padroes) == len(roteiros.CANAIS) * len(roteiros.OFERTAS), "um modelo do Mizan por canal e oferta")
checar(all(roteiros.validar(p["titulo"], p["canal"], p["oferta"], p["texto"]) for p in padroes),
       "os modelos do Mizan passam na própria validação")
checar(not any(ch.isdigit() for p in padroes for ch in p["texto"]), "os modelos não trazem número fixo (tudo vem da proposta)")

TAB = {"roteiros": []}
MODO = {"sem_tabela": False}

class R:
    def __init__(s, data): s.data = data

class Q:
    def __init__(s, t): s.t = t; s.f = []; s.ins = None; s.patch = None; s.apagar = False; s.lim = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append(lambda l: l.get(c) == v); return s
    def is_(s, c, v): s.f.append(lambda l: l.get(c) is None); return s
    def limit(s, n): s.lim = n; return s
    def order(s, *a, **k): return s
    def insert(s, l): s.ins = l; return s
    def update(s, p): s.patch = p; return s
    def delete(s): s.apagar = True; return s
    def execute(s):
        if MODO["sem_tabela"]:
            raise Exception('relation "public.roteiros" does not exist')
        tab = TAB.setdefault(s.t, [])
        if s.ins is not None:
            novo = dict(s.ins, id=f"r{len(tab) + 1}"); tab.append(novo); return R([novo])
        alvo = [l for l in tab if all(f(l) for f in s.f)]
        if s.patch is not None:
            for l in alvo: l.update(s.patch)
            return R([dict(l) for l in alvo])
        if s.apagar:
            TAB[s.t] = [l for l in tab if l not in alvo]; return R(alvo)
        return R([dict(l) for l in (alvo[:s.lim] if s.lim else alvo)])

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="operador", sub="op-ana"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ANA, BETO, ADM = jwt("goias"), jwt("goias", sub="op-beto"), jwt("goias", "admin", "adm")
OUTRA, CMD = jwt("beta", sub="op-x"), jwt("", "comando", "cmd")
R1 = {"titulo": "Cobrança amigável", "canal": "whatsapp", "texto": "Oi {primeiro_nome}, aqui é {operador}."}

print("— criar —")
r = c.post("/roteiros", json={**R1, "escopo": "empresa"}, headers=ADM)
checar(r.status_code == 200 and r.json()["roteiro"].get("dono_id") is None, "admin cria roteiro da empresa", r.text[:100])
id_emp = r.json()["roteiro"]["id"]
checar(c.post("/roteiros", json={**R1, "escopo": "empresa"}, headers=ANA).status_code == 403, "operador não cria da empresa")
r = c.post("/roteiros", json={**R1, "titulo": "Meu jeito", "canal": "sms"}, headers=ANA)
checar(r.status_code == 200 and r.json()["roteiro"]["dono_id"] == "op-ana", "operador cria o pessoal")
id_ana = r.json()["roteiro"]["id"]
r = c.post("/roteiros", json={**R1, "texto": "Pague {cpf} agora"}, headers=ANA)
checar(r.status_code == 422 and "{cpf}" in r.json()["detail"], "variável desconhecida: 422 com o nome dela")
checar(c.post("/roteiros", json={**R1, "escopo": "geral"}, headers=ADM).status_code == 422, "escopo inválido")
checar(c.post("/roteiros", json=R1, headers=CMD).status_code == 403, "comando não escreve roteiro")
c.post("/roteiros", json={**R1, "titulo": "Do Beto"}, headers=BETO)
c.post("/roteiros", json={**R1, "titulo": "Outra empresa", "escopo": "empresa"}, headers=jwt("beta", "admin", "adm-b"))

print("— listar —")
r = c.get("/roteiros", headers=ANA).json()
titulos = [x["titulo"] for x in r["roteiros"]]
checar(titulos == ["Cobrança amigável", "Meu jeito"], "operador vê os da empresa e os dele, da empresa primeiro", str(titulos))
checar("Do Beto" not in titulos and "Outra empresa" not in titulos, "não vê o pessoal do colega nem outra empresa")
checar(len(r["padroes"]) == 16 and set(r["variaveis"]) == set(roteiros.VARIAVEIS), "traz os modelos do Mizan e as variáveis")
r = c.get("/roteiros?canal=sms", headers=ANA).json()
checar([x["titulo"] for x in r["roteiros"]] == ["Meu jeito"] and all(p["canal"] == "sms" for p in r["padroes"]), "filtra por canal")
checar(c.get("/roteiros?canal=fax", headers=ANA).status_code == 422, "canal inválido: 422")
checar(c.get("/roteiros", headers=CMD).status_code == 400, "comando escolhe a empresa")
r = c.get("/roteiros?empresa_id=goias", headers=CMD).json()
checar([x["titulo"] for x in r["roteiros"]] == ["Cobrança amigável"], "comando lê só os da empresa (sem pessoais)")

print("— editar e apagar —")
novo = {**R1, "titulo": "Cobrança amigável v2"}
checar(c.put(f"/roteiros/{id_emp}", json=novo, headers=ANA).status_code == 403, "operador não edita o da empresa")
checar(c.put(f"/roteiros/{id_emp}", json=novo, headers=ADM).json()["roteiro"]["titulo"] == "Cobrança amigável v2", "admin edita")
checar(c.put(f"/roteiros/{id_ana}", json={**R1, "titulo": "Editado"}, headers=BETO).status_code == 404, "colega não edita o pessoal (nem sabe que existe)")
checar(c.put(f"/roteiros/{id_ana}", json={**R1, "titulo": "Editado"}, headers=ANA).status_code == 200, "dono edita o pessoal")
checar(c.put(f"/roteiros/{id_ana}", json={**R1, "texto": "{x}"}, headers=ANA).status_code == 422, "edição também valida")
checar(c.put(f"/roteiros/{id_emp}", json=novo, headers=OUTRA).status_code == 404, "outra empresa: 404")
checar(c.delete(f"/roteiros/{id_ana}", headers=BETO).status_code == 404, "colega não apaga")
checar(c.delete(f"/roteiros/{id_ana}", headers=ANA).status_code == 200 and not any(x["id"] == id_ana for x in TAB["roteiros"]), "dono apaga")
checar(c.delete(f"/roteiros/{id_emp}", headers=ANA).status_code == 403, "operador não apaga o da empresa")

print("— SQL ainda não rodado —")
MODO["sem_tabela"] = True
r = c.get("/roteiros", headers=ANA)
checar(r.status_code == 200 and r.json()["ativo"] is False and len(r.json()["padroes"]) == 16,
       "lista avisa e continua dando os modelos do Mizan")
checar(c.post("/roteiros", json=R1, headers=ANA).status_code == 409, "criar: 409 com o aviso")
MODO["sem_tabela"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
