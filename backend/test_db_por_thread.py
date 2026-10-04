"""Cada thread tem o próprio cliente do Supabase (HTTP/2 não é seguro entre threads).

    python test_db_por_thread.py
"""
import os, sys, threading
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x")
import db  # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

criados = []
db.create_client = lambda url, key: criados.append(object()) or criados[-1]

a, b = db.get_db(), db.get_db()
checar(a is b and len(criados) == 1, "na mesma thread, o mesmo cliente (não recria a cada chamada)")

por_thread = {}
def pega(i):
    por_thread[i] = (db.get_db(), db.get_db())
ts = [threading.Thread(target=pega, args=(i,)) for i in range(8)]
[t.start() for t in ts]; [t.join() for t in ts]
checar(all(x is y for x, y in por_thread.values()), "cada thread reaproveita o seu")
ids = {id(x) for x, _ in por_thread.values()} | {id(a)}
checar(len(ids) == 9, "threads diferentes não dividem cliente", f"{len(ids)} clientes para 9 threads")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
