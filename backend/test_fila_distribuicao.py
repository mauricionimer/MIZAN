"""F1 — divisão da fila entre operadores.

    python test_fila_distribuicao.py
"""
import os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fila_operadores import serpentina             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

print("— serpentina —")
p = serpentina(list(range(1, 10)), ["a", "b", "c"])
checar(p == {"a": [1, 6, 7], "b": [2, 5, 8], "c": [3, 4, 9]}, "reparte em serpente 1,2,3,3,2,1…", str(p))
p = serpentina(list(range(1000)), ["a", "b", "c", "d"])
todos = sum(p.values(), [])
checar(sorted(todos) == list(range(1000)), "a soma das partes é a fila inteira, sem repetir")
checar(max(map(len, p.values())) - min(map(len, p.values())) <= 1, "partes do mesmo tamanho (±1)")
somas = [sum(v) for v in p.values()]
checar((max(somas) - min(somas)) / max(somas) < 0.01, "cada um recebe a mesma fatia da ordem (posições somadas ≈ iguais)")
try:
    serpentina([1], []); checar(False, "sem operador recusa")
except ValueError:
    checar(True, "sem operador recusa")

CARTEIRAS = [{"id": "c-g", "empresa_id": "goias"}, {"id": "c-b", "empresa_id": "beta"}]
USUARIOS = [
    {"id": "op-ana",  "nome": "Ana",  "email": "ana@g",  "role": "operador", "ativo": True,  "empresa_id": "goias"},
    {"id": "op-beto", "nome": "Beto", "email": "beto@g", "role": "operador", "ativo": True,  "empresa_id": "goias"},
    {"id": "op-ex",   "nome": "Ex",   "email": "ex@g",   "role": "operador", "ativo": False, "empresa_id": "goias"},
    {"id": "adm",     "nome": "Adm",  "email": "adm@g",  "role": "admin",    "ativo": True,  "empresa_id": "goias"},
    {"id": "op-bb",   "nome": "BB",   "email": "bb@b",   "role": "operador", "ativo": True,  "empresa_id": "beta"},
]
PREDICOES = [{"id": f"p{i:02d}", "carteira_id": "c-g", "cpf": f"{i:011d}", "nome": f"D{i}", "rank": i,
              "valor_esperado_liquido": 100.0 - i, "responsavel_id": None, "responsavel_nome": None}
             for i in range(1, 11)]
PREDICOES.append({"id": "pb1", "carteira_id": "c-b", "cpf": "9", "nome": "B", "rank": 1,
                  "valor_esperado_liquido": 5.0, "responsavel_id": None, "responsavel_nome": None})
MODO = {"sem_coluna": False}

class R:
    def __init__(s, data, count=None): s.data = data; s.count = count

class Q:
    def __init__(s, t):
        s.t = t; s.lim = None; s.patch = None; s.contar = False
        s.linhas = list({"predicoes": PREDICOES, "carteiras": CARTEIRAS, "usuarios": USUARIOS}.get(t, []))
        s.ordem = []
    def select(s, cols="*", count=None, **k):
        s.contar = count == "exact"
        if MODO["sem_coluna"] and "responsavel" in cols:
            s.erro = "column predicoes.responsavel_id does not exist"
        return s
    def eq(s, c, v):
        if MODO["sem_coluna"] and c.startswith("responsavel"):
            s.erro = "column predicoes.responsavel_id does not exist"
        s.linhas = [l for l in s.linhas if l.get(c) == v]; return s
    def is_(s, c, v):
        if MODO["sem_coluna"] and c.startswith("responsavel"):
            s.erro = "column predicoes.responsavel_id does not exist"
        s.linhas = [l for l in s.linhas if l.get(c) is None]; return s
    def in_(s, c, vs): vs = set(vs); s.linhas = [l for l in s.linhas if l.get(c) in vs]; return s
    def gte(s, c, v): s.linhas = [l for l in s.linhas if (l.get(c) or 0) >= v]; return s
    def lte(s, c, v): s.linhas = [l for l in s.linhas if (l.get(c) or 0) <= v]; return s
    def order(s, col, desc=False):
        s.ordem.append(col); return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.rng = (i, f); return s
    def update(s, patch):
        if MODO["sem_coluna"]:
            s.erro = "column predicoes.responsavel_id does not exist"
        s.patch = patch; return s
    def execute(s):
        if getattr(s, "erro", None):
            raise Exception(s.erro)
        if s.patch is not None:
            for l in s.linhas: l.update(s.patch)
            return R(s.linhas)
        d = sorted(s.linhas, key=lambda l: tuple(str(l.get(c) or "").zfill(8) for c in s.ordem)) if s.ordem else s.linhas
        n = len(d)
        if hasattr(s, "rng"): d = d[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: d = d[:s.lim]
        return R([dict(x) for x in d], n if s.contar else None)

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
AUD = []
main._registrar_auditoria = lambda **k: AUD.append(k)
main.buscar_usuario_por_id = lambda uid: {"id": uid, "ativo": True}
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": empresa})}
ADM, ANA, BETO = jwt("goias"), jwt("goias", "operador", "op-ana"), jwt("goias", "operador", "op-beto")
ADM_B, CMD = jwt("beta"), jwt("", "comando", "cmd")
dono = lambda: {p["id"]: p["responsavel_id"] for p in PREDICOES if p["carteira_id"] == "c-g"}

print("— distribuir —")
r = c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-ana", "op-beto"]}, headers=ADM)
checar(r.status_code == 200, "admin distribui", r.text[:120])
d = dono()
checar(all(v in ("op-ana", "op-beto") for v in d.values()), "todo devedor da carteira ganhou um dono")
checar([d[f"p{i:02d}"] for i in range(1, 7)] == ["op-ana", "op-beto", "op-beto", "op-ana", "op-ana", "op-beto"],
       "na ordem da fila, em serpente")
checar(sorted(x["devedores"] for x in r.json()["por_operador"]) == [5, 5], "devolve quantos cada um recebeu")
checar(next(p for p in PREDICOES if p["id"] == "pb1")["responsavel_id"] is None, "não toca carteira de outra empresa")
checar(next(p for p in PREDICOES if p["id"] == "p01")["responsavel_nome"] == "Ana", "grava o nome também")
checar(AUD and AUD[-1]["acao"] == "fila_distribuida", "fica na auditoria")

checar(c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-ana"]}, headers=ANA).status_code == 403,
       "operador não reparte (403)")
checar(c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-ex"]}, headers=ADM).status_code == 422,
       "operador inativo é recusado")
checar(c.post("/carteiras/c-g/distribuir", json={"operadores": ["adm"]}, headers=ADM).status_code == 422,
       "admin não entra como operador da fila")
checar(c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-bb"]}, headers=ADM).status_code == 422,
       "operador de outra empresa é recusado")
checar(c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-bb"]}, headers=ADM_B).status_code == 403,
       "admin de outra empresa não mexe nesta carteira")
checar(c.post("/carteiras/c-g/distribuir", json={"operadores": []}, headers=ADM).status_code == 422,
       "lista vazia é recusada")

for p in PREDICOES[:3]: p["responsavel_id"] = None; p["responsavel_nome"] = None
r = c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-beto"], "somente_sem_responsavel": True}, headers=ADM)
checar(r.json()["distribuidos"] == 3 and all(dono()[f"p0{i}"] == "op-beto" for i in (1, 2, 3)),
       "'só sem responsável' reparte só os livres")
checar(dono()["p04"] == "op-ana", "e mantém o dono de quem já tinha")
r = c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-ana", "op-beto"]}, headers=CMD)
checar(r.status_code == 200, "comando também distribui")

print("— reatribuir —")
r = c.post("/carteiras/c-g/responsavel", json={"cpfs": ["00000000001"], "operador_id": "op-beto"}, headers=ADM)
checar(r.status_code == 200 and dono()["p01"] == "op-beto", "admin troca o dono de um devedor")
r = c.post("/carteiras/c-g/responsavel", json={"cpfs": ["00000000001"], "operador_id": None}, headers=ADM)
checar(r.status_code == 200 and dono()["p01"] is None, "e pode deixar sem responsável")
checar(c.post("/carteiras/c-g/responsavel", json={"cpfs": ["00000000002"], "operador_id": "op-ana"},
              headers=ANA).status_code == 403, "operador não reatribui (403)")
checar(c.post("/carteiras/c-g/responsavel", json={"cpfs": ["00000000002"], "operador_id": "op-bb"},
              headers=ADM).status_code == 422, "não passa para operador de outra empresa")

print("— fila filtrada —")
def fila(h, resp):
    r = c.get(f"/carteiras/c-g/ranking?responsavel={resp}&limit=50", headers=h)
    return r.status_code, [x["id"] for x in r.json().get("itens", [])] if r.status_code == 200 else r.text
st, ids = fila(ANA, "me")
checar(st == 200 and ids and all(dono()[i] == "op-ana" for i in ids), "operador vê só a fila dele", str(ids))
st2, ids2 = fila(BETO, "me")
checar(not set(ids) & set(ids2), "dois operadores nunca recebem o mesmo devedor")
st, ids = fila(ADM, "sem")
checar(ids == ["p01"], "admin vê quem está sem responsável", str(ids))
st, ids = fila(ADM, "op-beto")
checar(ids == ids2, "admin vê a fila de um operador")
r = c.get("/carteiras/c-g/ranking?responsavel=me", headers=ANA).json()["itens"]
checar(all(x.get("responsavel_nome") == "Ana" for x in r), "cada linha traz o nome do responsável")

print("— resumo —")
r = c.get("/carteiras/c-g/distribuicao", headers=ADM).json()
checar(r["ativo"] and r["total"] == 10, "resumo conta a carteira inteira")
checar(sum(g["devedores"] for g in r["por_operador"]) + r["sem_responsavel"]["devedores"] == 10,
       "a soma das partes é a carteira")
checar(r["sem_responsavel"]["devedores"] == 1, "conta quem está sem responsável")
checar(c.get("/carteiras/c-g/distribuicao", headers=ADM_B).status_code == 403, "outra empresa não lê o resumo")
checar([o["id"] for o in r["operadores"]] == ["op-ana", "op-beto"], "admin recebe os operadores ativos da empresa da carteira")
r = c.get("/carteiras/c-g/distribuicao", headers=CMD).json()
checar([o["id"] for o in r["operadores"]] == ["op-ana", "op-beto"], "comando também, pela empresa da carteira")
r = c.get("/carteiras/c-g/distribuicao", headers=ANA).json()
checar("operadores" not in r and r["meus"] == sum(1 for v in dono().values() if v == "op-ana"),
       "operador recebe só quantos são dele, sem a lista da equipe")

print("— SQL ainda não rodado —")
MODO["sem_coluna"] = True
r = c.post("/carteiras/c-g/distribuir", json={"operadores": ["op-ana"]}, headers=ADM)
checar(r.status_code == 409 and "migracao_operador" in r.json()["detail"], "distribuir avisa que falta o SQL (409)", r.text[:100])
r = c.get("/carteiras/c-g/ranking?responsavel=me", headers=ANA)
checar(r.status_code == 409, "a fila filtrada avisa que falta o SQL (409)")
r = c.get("/carteiras/c-g/distribuicao", headers=ADM).json()
checar(r["ativo"] is False, "o resumo diz que ainda não está ativo, sem 500")
MODO["sem_coluna"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
