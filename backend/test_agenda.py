"""F2 — agenda de retornos e promessas.

    python test_agenda.py
"""
import os, sys, inspect
from datetime import date, timedelta
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
d = lambda n: (HOJE + timedelta(days=n)).isoformat()

print("— níveis —")
checar(agenda.nivel(HOJE - timedelta(days=1), HOJE) == "alto", "ontem e pendente: alto")
checar(agenda.nivel(HOJE, HOJE) == "medio", "hoje: médio")
checar(agenda.nivel(HOJE + timedelta(days=1), HOJE) == "medio", "amanhã: médio")
checar(agenda.nivel(HOJE + timedelta(days=2), HOJE) == "safe", "depois de amanhã: safe")
checar(agenda.contar_niveis([HOJE - timedelta(days=3), HOJE, HOJE + timedelta(days=9)], HOJE)
       == {"alto": 1, "medio": 1, "safe": 1}, "contagem por nível")

TABELAS = {"agenda": [], "contatos": [], "recomendacoes": [], "carteiras": [{"id": "c-g", "empresa_id": "goias"}]}
MODO = {"sem_tabela": False}
PRED = {("goias", "111"): {"id": "p1", "nome": "Maria Dias", "carteira_id": "c-g"},
        ("goias", "222"): {"id": "p2", "nome": "João Souza", "carteira_id": "c-g"}}
main._predicao_do_cpf = lambda db, cpf, emp, colunas=None: PRED.get((emp, cpf))

class R:
    def __init__(s, data): s.data = data; s.count = None

class Q:
    def __init__(s, t):
        s.t = t; s.filtros = []; s.ins = None; s.patch = None; s.lim = None; s.rng = None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.filtros.append(lambda l: l.get(c) == v); return s
    def in_(s, c, vs): vs = set(vs); s.filtros.append(lambda l: l.get(c) in vs); return s
    def order(s, *a, **k): return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, linha): s.ins = linha; return s
    def update(s, patch): s.patch = patch; return s
    def execute(s):
        if MODO["sem_tabela"] and s.t == "agenda":
            raise Exception("relation \"public.agenda\" does not exist")
        tab = TABELAS.setdefault(s.t, [])
        if s.ins is not None:
            novo = dict(s.ins, id=f"{s.t}-{len(tab) + 1}"); tab.append(novo); return R([novo])
        alvo = [l for l in tab if all(f(l) for f in s.filtros)]
        if s.patch is not None:
            for l in alvo: l.update(s.patch)
            return R([dict(l) for l in alvo])
        if s.rng: alvo = alvo[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: alvo = alvo[:s.lim]
        return R([dict(l) for l in alvo])

main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="operador", sub="op-ana", nome="Ana"):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x", "nome": nome, "role": role, "empresa_id": empresa})}
ANA, BETO = jwt("goias"), jwt("goias", sub="op-beto", nome="Beto")
ADM, OUTRA, CMD = jwt("goias", "admin", "adm", "Adm"), jwt("beta", sub="op-x"), jwt("", "comando", "cmd")

print("— criar —")
r = c.post("/agenda", json={"cpf": "111", "tipo": "promessa", "data": d(0), "valor": 350.5}, headers=ANA)
checar(r.status_code == 200, "operador agenda uma promessa", r.text[:120])
it = r.json()["item"]
checar(it["nome"] == "Maria Dias" and it["carteira_id"] == "c-g" and it["operador_nome"] == "Ana",
       "o item guarda devedor, carteira e operador")
checar(it["nivel"] == "medio", "vence hoje: médio")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(-1)}, headers=ANA).status_code == 422,
       "data no passado é recusada")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(400)}, headers=ANA).status_code == 422,
       "data longe demais (ano errado) é recusada")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "visita", "data": d(1)}, headers=ANA).status_code == 422,
       "tipo desconhecido é recusado")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(1), "hora": "25:00"}, headers=ANA).status_code == 422,
       "hora inválida é recusada")
checar(c.post("/agenda", json={"cpf": "999", "tipo": "retorno", "data": d(1)}, headers=ANA).status_code == 404,
       "devedor fora das carteiras da empresa: 404")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(1)}, headers=OUTRA).status_code == 404,
       "outra empresa não agenda devedor desta")
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(1)}, headers=CMD).status_code == 403,
       "comando não cria compromisso (não trabalha fila)")
c.post("/agenda", json={"cpf": "222", "tipo": "retorno", "data": d(5), "hora": "14:30"}, headers=ANA)
c.post("/agenda", json={"cpf": "222", "tipo": "retorno", "data": d(1)}, headers=BETO)
TABELAS["agenda"].append({"id": "velho", "empresa_id": "goias", "cpf": "111", "nome": "Maria Dias", "tipo": "promessa",
                          "data": d(-3), "situacao": "pendente", "operador_id": "op-ana", "operador_nome": "Ana"})

print("— listar e resumo —")
r = c.get("/agenda", headers=ANA).json()
checar([i["data"] for i in r["itens"]] == [d(-3), d(0), d(5)], "operador vê só os dele, por data", str([i["data"] for i in r["itens"]]))
checar([i["nivel"] for i in r["itens"]] == ["alto", "medio", "safe"], "cada item com o nível")
r = c.get("/agenda?escopo=equipe", headers=ANA).json()
checar(all(i["operador_id"] == "op-ana" for i in r["itens"]), "operador pedindo a equipe continua vendo só os dele")
r = c.get("/agenda?escopo=equipe", headers=ADM).json()
checar(len(r["itens"]) == 4, "admin vê a equipe")
checar(c.get("/agenda/resumo", headers=ANA).json() == {"ativo": True, "alto": 1, "medio": 1, "safe": 1}, "resumo do operador")
checar(c.get("/agenda/resumo?escopo=equipe", headers=ADM).json()["medio"] == 2, "resumo da equipe")
checar(c.get("/agenda", headers=OUTRA).json()["itens"] == [], "outra empresa não vê nada")
checar(c.get("/agenda", headers=CMD).status_code == 400, "comando precisa escolher a empresa")
checar(len(c.get("/agenda?empresa_id=goias", headers=CMD).json()["itens"]) == 4, "comando lê a empresa escolhida")
checar(len(c.get("/agenda?cpf=222&escopo=equipe", headers=ADM).json()["itens"]) == 2, "filtra por devedor")

print("— resolver —")
id_hoje = next(i["id"] for i in TABELAS["agenda"] if i["data"] == d(0))
id_beto = next(i["id"] for i in TABELAS["agenda"] if i["operador_id"] == "op-beto")
checar(c.patch(f"/agenda/{id_beto}", json={"acao": "cumprir"}, headers=ANA).status_code == 403,
       "operador não mexe no compromisso do colega")
r = c.patch(f"/agenda/{id_hoje}", json={"acao": "remarcar", "data": d(3), "hora": "09:00"}, headers=ANA)
checar(r.status_code == 200 and r.json()["item"]["nivel"] == "safe", "remarcar muda a data e o nível")
checar(c.patch(f"/agenda/{id_hoje}", json={"acao": "remarcar"}, headers=ANA).status_code == 422, "remarcar sem data: 422")
checar(c.patch(f"/agenda/{id_hoje}", json={"acao": "remarcar", "data": d(-2)}, headers=ANA).status_code == 422,
       "remarcar para o passado: 422")
r = c.patch("/agenda/velho", json={"acao": "quebrar"}, headers=ANA)
checar(r.status_code == 200 and r.json()["item"]["situacao"] == "quebrada" and r.json()["item"]["nivel"] is None,
       "'não pagou' marca a promessa como quebrada")
checar(c.patch("/agenda/velho", json={"acao": "cumprir"}, headers=ANA).status_code == 409, "resolvido não muda de novo")
checar(c.patch(f"/agenda/{id_beto}", json={"acao": "cancelar"}, headers=ADM).status_code == 200, "admin resolve o da equipe")
checar(c.patch(f"/agenda/{id_hoje}", json={"acao": "cumprir"}, headers=OUTRA).status_code == 404, "outra empresa: 404")
checar(c.patch(f"/agenda/{id_hoje}", json={"acao": "apagar"}, headers=ANA).status_code == 422, "ação desconhecida: 422")

print("— contato cria o compromisso junto —")
main._fechar_loop_bandit = lambda *a, **k: None
antes = len(TABELAS["agenda"])
r = c.post("/contatos", json={"cpf": "222", "canal": "telefone", "resultado": "prometeu_pagar",
                              "agenda": {"tipo": "promessa", "data": d(7), "valor": 900}}, headers=ANA)
checar(r.status_code == 200 and r.json().get("agenda", {}).get("tipo") == "promessa", "contato com promessa grava os dois", r.text[:160])
checar(len(TABELAS["agenda"]) == antes + 1 and TABELAS["agenda"][-1]["contato_id"] == r.json()["contato"]["id"],
       "o compromisso aponta para o contato")
checar("agenda" not in TABELAS["contatos"][-1], "o contato não leva a agenda como coluna")
r = c.post("/contatos", json={"cpf": "222", "canal": "telefone", "resultado": "contactado",
                              "agenda": {"tipo": "retorno", "data": d(-1)}}, headers=ANA)
checar(r.status_code == 422, "data inválida na agenda recusa o contato antes de gravar")

print("— pagamento confirmado cumpre a promessa —")
TABELAS["agenda"].append({"id": "pr2", "empresa_id": "goias", "cpf": "222", "tipo": "promessa", "data": d(2),
                          "situacao": "pendente", "operador_id": "op-ana"})
TABELAS["agenda"].append({"id": "ret2", "empresa_id": "goias", "cpf": "222", "tipo": "retorno", "data": d(2),
                          "situacao": "pendente", "operador_id": "op-ana"})
TABELAS["agenda"].append({"id": "prB", "empresa_id": "beta", "cpf": "222", "tipo": "promessa", "data": d(2),
                          "situacao": "pendente", "operador_id": "op-x"})
main._cumprir_promessas(main.get_db(), "goias", "222")
sit = {i["id"]: i["situacao"] for i in TABELAS["agenda"]}
checar(sit["pr2"] == "cumprida", "a promessa pendente do CPF vira cumprida")
checar(sit["ret2"] == "pendente", "retorno não é tocado")
checar(sit["prB"] == "pendente", "a promessa do mesmo CPF em outra empresa não é tocada")
fonte = inspect.getsource(main)
checar(fonte.count("_cumprir_promessas(db,") >= 4,
       "as quatro entradas de pagamento confirmado chamam _cumprir_promessas")

print("— fila mostra o próximo compromisso —")
itens = main._anexar_agenda(main.get_db(), [{"cpf": "222", "rank": 1}, {"cpf": "333", "rank": 2}],
                            {"empresa_id": "goias", "role": "operador"}, "c-g")
checar("agenda" in itens[0] and itens[0]["agenda"]["nivel"] in agenda.NIVEIS, "linha com compromisso ganha o selo", str(itens[0].get("agenda")))
proxima = min(i["data"] for i in TABELAS["agenda"] if i["cpf"] == "222" and i["empresa_id"] == "goias" and i["situacao"] == "pendente")
checar(itens[0]["agenda"]["data"] == proxima, "e é o mais próximo mesmo")
checar("agenda" not in itens[1], "linha sem compromisso fica como estava")

print("— SQL ainda não rodado —")
MODO["sem_tabela"] = True
checar(c.post("/agenda", json={"cpf": "111", "tipo": "retorno", "data": d(1)}, headers=ANA).status_code == 409, "criar: 409 com o aviso")
checar(c.get("/agenda", headers=ANA).json()["ativo"] is False, "listar: avisa que não está ativa, sem 500")
checar(c.get("/agenda/resumo", headers=ANA).json()["ativo"] is False, "resumo idem")
r = c.post("/contatos", json={"cpf": "222", "canal": "telefone", "resultado": "contactado",
                              "agenda": {"tipo": "retorno", "data": d(1)}}, headers=ANA)
checar(r.status_code == 200 and "migracao_operador" in r.json().get("agenda_erro", ""), "o contato é gravado e a agenda avisa")
main._cumprir_promessas(main.get_db(), "goias", "222")
checar(True, "baixa de pagamento não quebra sem a tabela")
checar(main._anexar_agenda(main.get_db(), [{"cpf": "222"}], {"empresa_id": "goias"}, "c-g") == [{"cpf": "222"}],
       "a fila sai como antes")
MODO["sem_tabela"] = False

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
