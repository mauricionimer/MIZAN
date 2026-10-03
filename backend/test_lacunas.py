"""O que a Central não soube responder: registrado sem identificar ninguém, agrupado para o COMANDO.

    python test_lacunas.py
"""
import os, sys, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from ajuda_lacunas import agrupar, chave_de        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

# ── chave e agrupamento ──────────────────────────────────────────────────
print("— agrupar —")
checar(chave_de("Como vejo quem pagou?") == chave_de("quem pagou, como vejo") , "a ordem das palavras e a pontuação não separam a mesma pergunta")
checar(chave_de("COMISSÃO do escritório") == chave_de("comissao do escritorio"), "acento e caixa não separam")
checar(chave_de("como vejo quem pagou") != chave_de("como vejo a comissão"), "perguntas diferentes continuam diferentes")
agora = datetime.now(timezone.utc)
L = lambda chave, tipo, perfil="operador", entrada=None, minutos=0, tratada=None, pergunta=None: {
    "chave": chave, "tipo": tipo, "perfil": perfil, "entrada_id": entrada, "pergunta": pergunta or chave,
    "created_at": (agora - timedelta(minutes=minutos)).isoformat(), "tratada_em": tratada}
g = agrupar([L("a", "sem_resposta", minutos=5), L("a", "nao_resolveu", "admin", "fila-ordem", 3), L("a", "nao_resolveu", "operador", "fila-ordem", 2),
             L("a", "nao_resolveu", "operador", "aging", 1), L("b", "sem_resposta", minutos=1), L("c", "sem_resposta", minutos=9), L("c", "sem_resposta", minutos=8)])
checar([x["chave"] for x in g] == ["a", "c", "b"], "ordena da mais repetida para a menos; empate, a mais recente", str([x["chave"] for x in g]))
a = g[0]
checar(a["total"] == 4 and a["sem_resposta"] == 1 and a["nao_resolveu"] == 3, "conta cada tipo")
checar(a["perfis"] == {"operador": 3, "admin": 1}, "e por perfil")
checar(a["entradas_que_nao_resolveram"][0] == {"id": "fila-ordem", "vezes": 2}, "e quais respostas mais falharam")
t = agrupar([L("x", "sem_resposta", tratada="2026-01-01"), L("x", "sem_resposta", tratada="2026-01-01")])[0]
checar(t["tratada"] is True and t["reapareceu"] is False, "tudo tratado: tratada")
t = agrupar([L("x", "sem_resposta", tratada="2026-01-01"), L("x", "sem_resposta")])[0]
checar(t["tratada"] is False and t["reapareceu"] is True, "voltou a aparecer depois de tratada: reapareceu")

# ── banco de mentira ─────────────────────────────────────────────────────
TAB = {"ajuda_lacunas": []}
AUD = []
class Q:
    def __init__(s, t): s.t, s.f, s.nulos, s._gte, s._lt, s.op, s.d, s.rng = t, {}, [], None, None, "select", None, None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f[c] = v; return s
    def is_(s, c, _): s.nulos.append(c); return s
    def gte(s, c, v): s._gte = (c, v); return s
    def lt(s, c, v): s._lt = (c, v); return s
    def order(s, *a, **k): return s
    def limit(s, *a): return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, d): s.op, s.d = "insert", d; return s
    def update(s, d): s.op, s.d = "update", d; return s
    def delete(s): s.op = "delete"; return s
    def _casa(s, r):
        return (all(r.get(k) == v for k, v in s.f.items()) and all(r.get(c) is None for c in s.nulos)
                and (not s._gte or r[s._gte[0]] >= s._gte[1]) and (not s._lt or r[s._lt[0]] < s._lt[1]))
    def execute(s):
        L_ = TAB[s.t]
        if s.op == "insert":
            L_.append({"id": str(uuid.uuid4()), "created_at": datetime.utcnow().isoformat(), "tratada_em": None, "tratada_por": None, "entrada_id": None, **s.d})
            return type("R", (), {"data": [1], "count": None})()
        if s.op == "update":
            for r in L_:
                if s._casa(r): r.update(s.d)
            return type("R", (), {"data": [], "count": None})()
        if s.op == "delete":
            TAB[s.t][:] = [r for r in L_ if not s._casa(r)]
            return type("R", (), {"data": [], "count": None})()
        d = [r for r in L_ if s._casa(r)]
        if s.rng: d = d[s.rng[0]:s.rng[1] + 1]
        return type("R", (), {"data": d, "count": len(d)})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
U = {"op": {"ativo": True, "id": "op", "role": "operador", "empresa_id": "alfa"},
     "op2": {"ativo": True, "id": "op2", "role": "operador", "empresa_id": "alfa"},
     "ad": {"ativo": True, "id": "ad", "role": "admin", "empresa_id": "alfa"},
     "co": {"ativo": True, "id": "co", "role": "comando", "empresa_id": ""}}
main.buscar_usuario_por_id = lambda uid: U[uid]
main._registrar_auditoria = lambda *a, **k: AUD.append(k)
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": f"{u}@x.com", "nome": "N", "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}

# ── registro automático ──────────────────────────────────────────────────
print("\n— a busca sem resposta é registrada —")
main._LACUNAS_VISTAS.clear()
r = c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "qual a previsão do tempo para o devedor 123.456.789-09"})
checar(r.status_code == 200 and r.json()["certeza"] is False, "busca fora do assunto responde sem certeza")
checar(len(TAB["ajuda_lacunas"]) == 1, "e fica registrada", str(len(TAB["ajuda_lacunas"])))
linha = TAB["ajuda_lacunas"][0]
tudo = " ".join(str(v) for v in linha.values())
checar("123.456.789-09" not in tudo and "[CPF]" in linha["pergunta"], "o CPF digitado foi mascarado antes de gravar", linha["pergunta"])
checar(linha["perfil"] == "operador" and linha["tipo"] == "sem_resposta", "perfil e tipo gravados")
checar(not any(k in linha for k in ("autor_id", "usuario_id", "empresa_id", "email", "sub")) and "op" not in {str(v) for v in linha.values() if v == "op"},
       "e NADA que identifique quem buscou (nem usuário, nem empresa)", str(sorted(linha)))
r = c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "qual a previsão do tempo para o devedor 123.456.789-09"})
checar(len(TAB["ajuda_lacunas"]) == 1, "a mesma pessoa repetindo a pergunta não conta duas vezes")
c.post("/ajuda/buscar", headers=H("op2"), json={"pergunta": "qual a previsão do tempo para o devedor 123.456.789-09"})
checar(len(TAB["ajuda_lacunas"]) == 2, "outra pessoa com a mesma pergunta conta")
checar(not any("op2" in str(v) or "'op'" in str(v) for r_ in TAB["ajuda_lacunas"] for v in r_.values()), "o resumo de dedupe nunca vai para o banco")
n = len(TAB["ajuda_lacunas"])
c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "por que esse devedor está em primeiro na lista"})
checar(len(TAB["ajuda_lacunas"]) == n, "busca com certeza não vira lacuna")

# falha no banco não atrapalha a busca nem vaza a pergunta
main.get_db = lambda: (_ for _ in ()).throw(RuntimeError("banco fora"))
import io, contextlib
saida = io.StringIO()
with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
    r = c.post("/ajuda/buscar", headers=H("ad"), json={"pergunta": "pergunta-secreta-sem-resposta-qwerty"})
checar(r.status_code == 200, "banco fora: a busca responde igual")
checar("qwerty" not in saida.getvalue(), "e a falha não escreve a pergunta no log")
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()

# ── não resolveu ─────────────────────────────────────────────────────────
print("\n— 'isto não resolveu' —")
main._LACUNAS_VISTAS.clear(); TAB["ajuda_lacunas"].clear()
r = c.post("/ajuda/nao-resolveu", headers=H("op"), json={"pergunta": "como a fila é ordenada", "entrada_id": "fila-ordem"})
checar(r.status_code == 200 and TAB["ajuda_lacunas"][0]["tipo"] == "nao_resolveu" and TAB["ajuda_lacunas"][0]["entrada_id"] == "fila-ordem", "registra com a resposta que não resolveu")
c.post("/ajuda/nao-resolveu", headers=H("op2"), json={"pergunta": "outra pergunta qualquer", "entrada_id": "psi"})
checar(TAB["ajuda_lacunas"][1]["entrada_id"] is None, "resposta que o perfil nem pode ver não é gravada como 'a que falhou'")
checar(c.post("/ajuda/nao-resolveu", json={"pergunta": "sem login"}).status_code in (401, 403), "sem login: recusado")
checar(c.post("/ajuda/nao-resolveu", headers=H("op"), json={"pergunta": "x"}).status_code == 422, "pergunta curta demais: 422")

# ── o COMANDO vê e trata ─────────────────────────────────────────────────
print("\n— o COMANDO —")
TAB["ajuda_lacunas"].clear(); main._LACUNAS_VISTAS.clear()
def semear(pergunta, tipo, perfil="operador", entrada=None, dias=1, tratada=None):
    TAB["ajuda_lacunas"].append({"id": str(uuid.uuid4()), "created_at": (datetime.utcnow() - timedelta(days=dias)).isoformat(),
                                 "tipo": tipo, "pergunta": pergunta, "chave": chave_de(pergunta), "entrada_id": entrada, "perfil": perfil,
                                 "tratada_em": tratada, "tratada_por": None})
for _ in range(3): semear("como vejo quem pagou", "sem_resposta")
semear("quem pagou, como eu vejo", "nao_resolveu", entrada="quem-pagou")
semear("onde troco a comissão", "sem_resposta")
semear("pergunta muito antiga", "sem_resposta", dias=200)
for u in ("op", "ad"):
    checar(c.get("/comando/ajuda/lacunas", headers=H(u)).status_code == 403, f"{u} não vê as lacunas")
j = c.get("/comando/ajuda/lacunas", headers=H("co")).json()
checar(j["grupos"][0]["total"] == 4 and j["grupos"][0]["nao_resolveu"] == 1, "agrupa as duas formas da mesma pergunta e põe no topo", str([(g["exemplo"], g["total"]) for g in j["grupos"]]))
checar(all("antiga" not in g["exemplo"] for g in j["grupos"]), "respeita a janela de 90 dias")
checar(j["grupos"][0]["mais_perto"] and j["grupos"][0]["mais_perto"]["id"], "mostra a resposta do catálogo mais próxima (ponto de partida para escrever)", str(j["grupos"][0]["mais_perto"]))
checar(j["total_de_registros"] == 5, "e conta os registros da janela", str(j["total_de_registros"]))
checar(c.get("/comando/ajuda/lacunas", headers=H("co"), params={"dias": 365}).json()["total_de_registros"] == 6, "a janela pode ir a 365 dias")
checar(c.get("/comando/ajuda/lacunas", headers=H("co"), params={"estado": "x"}).status_code == 422, "estado inválido: 422")

chave = j["grupos"][0]["chave"]
AUD.clear()
checar(c.post("/comando/ajuda/lacunas/tratar", headers=H("op"), json={"chave": chave}).status_code == 403, "operador não trata")
checar(c.post("/comando/ajuda/lacunas/tratar", headers=H("co"), json={"chave": chave}).status_code == 200, "COMANDO marca como tratada")
checar(AUD and AUD[0]["acao"] == "lacuna_tratada", "e fica na auditoria")
checar(all(g["chave"] != chave for g in c.get("/comando/ajuda/lacunas", headers=H("co")).json()["grupos"]), "sai da lista de pendentes")
checar(any(g["chave"] == chave and g["tratada"] for g in c.get("/comando/ajuda/lacunas", headers=H("co"), params={"estado": "tratadas"}).json()["grupos"]), "e está em 'tratadas'")
semear("como vejo quem pagou", "sem_resposta")
g2 = next(g for g in c.get("/comando/ajuda/lacunas", headers=H("co")).json()["grupos"] if g["chave"] == chave)
checar(g2["reapareceu"] is True and g2["tratada"] is False, "se a pergunta voltar depois de tratada, reaparece marcada como 'reapareceu'")
c.post("/comando/ajuda/lacunas/tratar", headers=H("co"), json={"chave": chave, "tratada": False})
checar(all(r_["tratada_em"] is None for r_ in TAB["ajuda_lacunas"] if r_["chave"] == chave), "dá para reabrir")

checar(c.post("/comando/ajuda/lacunas/limpar", headers=H("co"), json={"dias": 10}).status_code == 422, "limpar exige no mínimo 30 dias")
checar(c.post("/comando/ajuda/lacunas/limpar", headers=H("op"), json={"dias": 90}).status_code == 403, "operador não limpa")
antes = len(TAB["ajuda_lacunas"])
checar(c.post("/comando/ajuda/lacunas/limpar", headers=H("co"), json={"dias": 90}).status_code == 200 and len(TAB["ajuda_lacunas"]) == antes - 1,
       "limpar apaga só o mais antigo que o prazo (a de 200 dias)", f"{antes} -> {len(TAB['ajuda_lacunas'])}")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
