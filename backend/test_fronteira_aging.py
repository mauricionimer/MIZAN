"""Aging e fase do ciclo concordam na fronteira (D7).

    python test_fronteira_aging.py

Antes o dia 30 caía em "30-59 dias" no aging e na fase administrativa no ciclo.
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main                       # noqa: E402
from model import ciclo           # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

esperado = {0: "0-30 dias", 30: "0-30 dias", 31: "31-60 dias", 60: "31-60 dias", 61: "61-90 dias",
            90: "61-90 dias", 91: "91-180 dias", 180: "91-180 dias", 181: "181+ dias", 900: "181+ dias"}
obtido = {d: main._aging_label(d) for d in esperado}
checar(obtido == esperado, "faixas fechadas à direita: até 30, 31 a 60, 61 a 90, 91 a 180, 181+", str(obtido))
for d in range(0, 400):
    adm = ciclo.fase_de(d) == "administrativa"
    if adm != (main._aging_label(d) == "0-30 dias"):
        checar(False, f"dia {d}: aging e fase discordam", f"{main._aging_label(d)} / {ciclo.fase_de(d)}")
        break
else:
    checar(True, "de 0 a 399 dias, a primeira faixa do aging é exatamente a fase administrativa")
front = Path(__file__).resolve().parent.parent / "frontend/src/pages/Dashboard.jsx"
checar(all(r in front.read_text(encoding="utf-8") for r in set(esperado.values())),
       "a tela ordena pelos mesmos rótulos")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
