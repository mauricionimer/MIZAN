"""Agentes, Parte 1 — situações do caso e mudanças permitidas.

    python test_agente_estado.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agente import estado                          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

def proibida(atual, nova, por="agente"):
    try:
        estado.mudar(atual, nova, por)
        return False
    except estado.TransicaoProibida:
        return True

print("— caminho normal —")
s = "novo"
for nova in ("em_contato", "negociando", "acordo_ativo", "atrasado", "acordo_ativo", "quitado"):
    s = estado.mudar(s, nova)
checar(s == "quitado", "novo → contato → negociação → acordo → atraso → acordo → quitado")

print("— o agente sempre pode parar, registrar contestação ou chamar uma pessoa —")
for s in ("novo", "em_contato", "negociando", "acordo_ativo", "atrasado", "quebrado"):
    checar(all(n in estado.permitidas(s) for n in ("suspenso", "contestado", "com_pessoa")), f"de {s}")

print("— só uma pessoa tira o caso destas situações —")
for s in ("suspenso", "contestado", "com_pessoa"):
    checar(estado.permitidas(s) == set(), f"agente não sai de {s}")
    checar(estado.mudar(s, "em_contato", por="pessoa") == "em_contato", f"pessoa tira de {s}")

print("— proibidas —")
checar(proibida("novo", "acordo_ativo"), "acordo sem negociar")
checar(proibida("novo", "quitado"), "quitado sem pagamento")
checar(proibida("quitado", "em_contato"), "agente reabre quitado")
checar(proibida("quitado", "em_contato", por="pessoa"), "nem a pessoa reabre quitado")
checar(proibida("em_contato", "em_contato"), "mesma situação não é mudança")
checar(proibida("novo", "inventada"), "situação desconhecida")
checar(proibida("inventada", "novo"), "origem desconhecida")

print("— quem pode falar com o devedor —")
checar(not any(estado.pode_falar(s) for s in ("novo", "suspenso", "contestado", "com_pessoa", "quitado")),
       "não fala: novo, suspenso, contestado, com pessoa, quitado")
checar(all(estado.pode_falar(s) for s in ("em_contato", "negociando", "atrasado")), "fala nas demais")

print("— coerência com o SQL —")
sql = (Path(__file__).resolve().parent / "sql" / "migracao_agente.sql").read_text(encoding="utf-8")
checar(all(f"'{s}'" in sql for s in estado.SITUACOES), "toda situação do código está no CHECK do SQL")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
