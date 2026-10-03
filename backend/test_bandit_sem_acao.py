"""O bandit só aprende com ação que foi recomendada ao devedor (D2), e o log não leva CPF.

    python test_bandit_sem_acao.py

Antes, um pagamento sem recomendação prévia fazia o bandit escolher na hora a
ação que "teria" recomendado e creditá-la com o resultado, como se tivesse sido
feita. Isso inflava as taxas por oferta que alimentam as propostas.
"""
import contextlib, io, os, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                       # noqa: E402
import model.bandit as bandit     # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CHAMADAS = []
bandit.registrar_resultado = lambda **k: CHAMADAS.append(k)
# se o código voltar a inventar a ação, esta é a que ele inventaria
bandit.recomendar = lambda *a, **k: {"acao_id": 9, "contexto": [0.0] * 14}

RECS = []
class Q:
    def __init__(s): s.l = list(RECS)
    def select(s, *a): return s
    def eq(s, c, v): s.l = [r for r in s.l if r.get(c) == v]; return s
    def order(s, *a, **k): return s
    def limit(s, n): s.l = s.l[:n]; return s
    def execute(s): return type("R", (), {"data": s.l})()
DB = type("DB", (), {"table": staticmethod(lambda n: Q())})()
PRED = {"id": "p1", "valor_divida": 1000.0, "renda_estimada": 3000.0, "dias_em_atraso": 90, "produto": "cartao"}

saida = io.StringIO()
with contextlib.redirect_stdout(saida):
    main._fechar_loop_bandit(DB, "12345678901", True, 500.0, PRED, "alfa")
checar(CHAMADAS == [], "sem recomendação registrada, o bandit NÃO aprende", str(CHAMADAS))

RECS.append({"cpf": "12345678901", "empresa_id": "beta", "acao_id": 7, "contexto": [0.1] * 14})
main._fechar_loop_bandit(DB, "12345678901", True, 500.0, PRED, "alfa")
checar(CHAMADAS == [], "a recomendação de OUTRA empresa para o mesmo CPF não conta", str(CHAMADAS))

RECS.append({"cpf": "12345678901", "empresa_id": "alfa", "acao_id": 3, "contexto": [0.2] * 14})
main._fechar_loop_bandit(DB, "12345678901", True, 500.0, PRED, "alfa")
checar(len(CHAMADAS) == 1 and CHAMADAS[0]["acao_id"] == 3 and CHAMADAS[0]["empresa_id"] == "alfa",
       "com recomendação desta empresa, aprende na ação recomendada", str(CHAMADAS))
checar(abs(CHAMADAS[0]["recompensa"] - 0.5) < 1e-9 and CHAMADAS[0]["pagou"] is True,
       "recompensa = recuperado ÷ dívida", str(CHAMADAS[0]["recompensa"]))

def explode(**k): raise RuntimeError("cpf 12345678901 no erro")
bandit.registrar_resultado = explode
saida = io.StringIO()
with contextlib.redirect_stdout(saida):
    main._fechar_loop_bandit(DB, "12345678901", True, 500.0, PRED, "alfa")
checar("12345678901" not in saida.getvalue(), "erro no bandit não põe o CPF no log", saida.getvalue().strip())

checar(main._cpf_no_log("123.456.789-01") == "***01" and main._cpf_no_log(None) == "—",
       "CPF no log: só os dois últimos dígitos")

print("\n— zerar o aprendizado de uma empresa —")
import importlib, numpy as np
importlib.reload(bandit)                       # o de verdade, sem os dublês acima
SALVOS = {}
bandit._salvar_supabase = lambda chave, b: SALVOS.__setitem__(chave, b)
bandit._carregar_supabase = lambda chave: SALVOS.get(chave)
bandit._arquivo_bandit = lambda chave: Path("/nonexistent") / chave
b = bandit.LinUCB(alpha=2.0); b.atualizar(3, np.ones(bandit.D), 1.0); SALVOS["alfa"] = b
b2 = bandit.LinUCB(); b2.atualizar(1, np.ones(bandit.D), 1.0); SALVOS["beta"] = b2
from fastapi.testclient import TestClient
from auth import criar_token
main._registrar_auditoria = lambda **k: AUD.append(k)
AUD = []
U = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": "", "email": "c@c"},
     "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa", "email": "a@a"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": U[u]["email"], "nome": "N",
                                                          "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}
c = TestClient(main.app, raise_server_exceptions=False)
r = c.post("/admin/bandit/zerar", headers=H("ua"), json={"empresa_id": "alfa", "confirmacao": "ZERAR"})
checar(r.status_code == 403, "admin da empresa não zera", r.status_code)
r = c.post("/admin/bandit/zerar", headers=H("uc"), json={"empresa_id": "alfa", "confirmacao": "sim"})
checar(r.status_code == 422, "sem digitar ZERAR: recusa", r.status_code)
r = c.post("/admin/bandit/zerar", headers=H("uc"), json={"empresa_id": "ALFA", "confirmacao": "zerar"})
checar(r.status_code == 200 and r.json()["interacoes_descartadas"] == 1, "COMANDO zera a alfa", r.text[:120])
checar(sum(SALVOS["alfa"].n_tentativas) == 0 and SALVOS["alfa"].alpha == 2.0, "alfa recomeça do zero, com o mesmo alpha")
checar(sum(SALVOS["beta"].n_tentativas) == 1, "a beta não é tocada")
checar(AUD and AUD[-1]["acao"] == "bandit_zerado", "fica na auditoria")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
