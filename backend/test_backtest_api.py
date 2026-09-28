"""Regressão: o endpoint de backtest analisa sem gravar, e só para quem deve.

    python test_backtest_api.py

A carteira histórica de um cliente entra para ser analisada, não para virar
base. Se o backtest criasse carteira ou gravasse predições, um teste feito
numa reunião contaminaria o sistema do cliente — e pior, misturaria dados de
um banco com os de outro.
"""
import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                    # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402
from auth import criar_token                   # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# Qualquer toque no banco é falha: o backtest não pode gravar nada.
tocou_o_banco = []
main.get_db = lambda: tocou_o_banco.append("get_db") or (_ for _ in ()).throw(
    AssertionError("o backtest não pode acessar o banco"))
main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}

c = TestClient(main.app)


def token(role):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "x@x.com", "nome": "X", "role": role,
         "empresa_id": "banco_alfa"})}


def carteira(n=600, semente=3):
    rng = np.random.default_rng(semente)
    valor = rng.lognormal(8.2, 0.9, n).round(2)
    prob = rng.random(n)
    return pd.DataFrame({
        "cpf": [f"{i:011d}" for i in range(n)],
        "valor_divida": valor,
        "renda_estimada": rng.lognormal(7.9, 0.6, n).round(2),
        "dias_em_atraso": rng.integers(15, 900, n),
        "produto": rng.choice(["cartao", "consignado"], n),
        "uf": rng.choice(["GO", "SP"], n),
        "pagou": (rng.random(n) < prob).astype(int),
    })


def enviar(df, headers, nome="hist.csv"):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return c.post("/backtest", headers=headers,
                  files={"file": (nome, buf.getvalue(), "text/csv")})


# ── quem pode rodar ───────────────────────────────────────────────────────
r = enviar(carteira(), token("operador"))
checar(r.status_code == 403, "operador não roda backtest", str(r.status_code))
checar(not tocou_o_banco, "e a recusa acontece antes de qualquer acesso ao banco")

r = c.post("/backtest", files={"file": ("h.csv", "a,b\n1,2\n", "text/csv")})
checar(r.status_code in (401, 403), "sem token, recusa", str(r.status_code))

# ── o caminho feliz ───────────────────────────────────────────────────────
r = enviar(carteira(), token("comando"))
checar(r.status_code == 200, "comando roda", f"{r.status_code} {r.text[:120]}")
checar(not tocou_o_banco, "e NADA foi gravado — nenhum acesso ao banco",
       str(tocou_o_banco))

b = r.json() if r.status_code == 200 else {}
checar(b.get("n_devedores") == 600, "devolve o tamanho da carteira",
       str(b.get("n_devedores")))
checar(b.get("arquivo") == "hist.csv", "e o nome do arquivo analisado")
for campo in ("separacao", "decis", "filas", "ganho_sobre_pratica_atual", "avisos"):
    checar(campo in b, f"traz '{campo}' na resposta")
checar(len(b.get("decis", [])) == 10, "dez decis", str(len(b.get("decis", []))))
for fila in ("mizan_ev", "mizan_score", "maior_divida", "aleatorio", "oraculo"):
    checar(fila in b.get("filas", {}), f"compara com a fila '{fila}'")

# ── entradas ruins viram mensagem, não erro 500 ───────────────────────────
r = enviar(carteira().drop(columns=["pagou"]), token("comando"))
checar(r.status_code == 422, "carteira sem 'pagou' é recusada com explicação",
       str(r.status_code))
checar("pagou" in r.text, "e a mensagem diz qual coluna falta")

so_pagantes = carteira()
so_pagantes["pagou"] = 1
r = enviar(so_pagantes, token("comando"))
checar(r.status_code == 422, "carteira com um só desfecho é recusada",
       str(r.status_code))

r = c.post("/backtest", headers=token("comando"),
           files={"file": ("h.txt", "nada", "text/plain")})
checar(r.status_code == 400, "formato não suportado é recusado", str(r.status_code))

# ── o vazamento de dados é barrado ────────────────────────────────────────
com_vazamento = carteira()
com_vazamento["data_pagamento"] = "2026-01-15"
r = enviar(com_vazamento, token("comando"))
b2 = r.json()
checar(r.status_code == 200 and any("data_pagamento" in a for a in b2.get("avisos", [])),
       "coluna que entrega o desfecho é removida e avisada",
       str(b2.get("avisos", []))[:90])

checar(not tocou_o_banco, "ao fim de tudo, o banco segue intocado", str(tocou_o_banco))

print("\nRESULTADO: " + ("tudo certo" if not falhas else f"{falhas} falha(s)"))
sys.exit(1 if falhas else 0)
