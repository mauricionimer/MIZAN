"""Inserção de predições em lotes grandes e paralelos.

    python test_insercao_lotes.py
"""
import os, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

estado = {"lotes": [], "ativos": 0, "pico": 0, "falhar_no": None}
trava = threading.Lock()

class Ins:
    def __init__(s, linhas): s.l = linhas
    def execute(s):
        with trava:
            estado["ativos"] += 1
            estado["pico"] = max(estado["pico"], estado["ativos"])
            n = len(estado["lotes"]); estado["lotes"].append(len(s.l))
        time.sleep(0.02)
        try:
            if estado["falhar_no"] == n:
                raise RuntimeError("falha simulada")
            return type("R", (), {"data": [{"cpf": l["cpf"], "id": "id-" + l["cpf"]} for l in s.l]})()
        finally:
            with trava: estado["ativos"] -= 1
class T:
    def insert(s, linhas): return Ins(linhas)
db = type("DB", (), {"table": staticmethod(lambda n: T())})()

N = 9000
linhas = [{"cpf": f"{i:011d}"} for i in range(N)]
m = main._inserir_predicoes_em_lotes(db, linhas)
checar(len(m) == N and m["00000000005"] == "id-00000000005", "devolve o id de todas as predições", str(len(m)))
checar(sum(estado["lotes"]) == N, "todas as linhas foram enviadas, uma vez cada")
checar(len(estado["lotes"]) == 5 and max(estado["lotes"]) == main.LOTE_INSERCAO,
       f"{N} linhas em {len(estado['lotes'])} idas (era {N // 500 + 1} com 500)", str(estado["lotes"]))
checar(1 < estado["pico"] <= main.INSERCOES_PARALELAS, f"paralelo, mas com teto: pico {estado['pico']}")

estado.update(lotes=[], falhar_no=2)
try:
    main._inserir_predicoes_em_lotes(db, linhas)
    checar(False, "falha de um lote sobe como erro")
except RuntimeError:
    checar(True, "falha de um lote sobe como erro")
checar(len(estado["lotes"]) == 5, "os demais lotes terminam antes de o erro subir", str(estado["lotes"]))
checar(main._inserir_predicoes_em_lotes(db, []) == {}, "lista vazia não chama o banco")
print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
