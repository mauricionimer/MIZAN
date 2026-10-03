"""Busca e rotas da Central de Ajuda.

    python test_ajuda_busca.py

O que se garante:
  - a qualidade medida no conjunto de TESTE (perguntas que nunca serviram para
    ajustar a busca) não cai abaixo do piso;
  - a busca recusa pergunta fora do assunto em vez de responder com confiança;
  - cada perfil só encontra respostas das telas que tem — por busca, por índice
    e por acesso direto;
  - o detalhe técnico (fontes no código) só chega ao COMANDO;
  - a pergunta não vai para o log.
"""
import io
import contextlib
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import ajuda                                       # noqa: E402
import ajuda_avaliacao as av                       # noqa: E402
from ajuda_busca import Buscador, buscador_para    # noqa: E402
from avaliar_busca import medir                    # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── qualidade, no conjunto que nunca serviu para ajustar ─────────────────
r = medir("teste")
print(f"      teste: 1º lugar {r['top1']:.1%} · entre os 3 {r['top3']:.1%} · "
      f"precisão com certeza {r['precisao_com_certeza']:.1%} · recusa {r['recusa']:.1%}")
checar(r["top3"] >= 0.85, "a resposta certa está entre as 3 primeiras em 85%+ das perguntas de teste", f"{r['top3']:.1%}")
checar(r["top1"] >= 0.65, "e em 1º lugar em 65%+", f"{r['top1']:.1%}")
checar(r["recusa"] >= 0.80, "recusa 80%+ das perguntas fora do assunto", f"{r['recusa']:.1%}")
checar(r["precisao_com_certeza"] >= 0.80, "quando diz que tem certeza, acerta 80%+", f"{r['precisao_com_certeza']:.1%}")
rd = medir("dev")
checar(rd["recusa"] >= 0.90, "e no conjunto de ajuste, 90%+ de recusa", f"{rd['recusa']:.1%}")

# ── perfil ───────────────────────────────────────────────────────────────
b_op, b_cm = buscador_para("operador"), buscador_para("comando")
ids_op = {e.id for e in b_op.entradas}
checar("psi" not in ids_op and "treino-por-empresa" not in ids_op and "precificacao-simulador" not in ids_op,
       "o índice do operador não contém PSI, treino nem precificação")
res = b_op.buscar("o que é psi estabilidade da população", k=3)
checar(all(x["id"] != "psi" for x in res["resultados"]), "perguntar por PSI ao operador não devolve a resposta de PSI")
res = b_cm.buscar("o que é psi estabilidade da população", k=3)
checar(res["resultados"] and res["resultados"][0]["id"] == "psi", "o COMANDO encontra", str(res["resultados"][:1]))

# ── rotas ────────────────────────────────────────────────────────────────
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

U = {"op": {"ativo": True, "id": "op", "role": "operador", "empresa_id": "alfa"},
     "ad": {"ativo": True, "id": "ad", "role": "admin", "empresa_id": "alfa"},
     "co": {"ativo": True, "id": "co", "role": "comando", "empresa_id": ""}}
main.buscar_usuario_por_id = lambda uid: U[uid]
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token(
    {"sub": u, "email": "e@e.com", "nome": "N", "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}

checar(c.post("/ajuda/buscar", json={"pergunta": "o que é a fila"}).status_code in (401, 403), "sem login não busca")
r = c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "por que esse devedor está em primeiro na lista"})
j = r.json()
checar(r.status_code == 200 and j["resultados"] and j["resultados"][0]["id"] == "fila-ordem",
       "a busca responde pela API", f"{r.status_code} {[x['id'] for x in j.get('resultados', [])]}")
checar(all("fontes" not in x for x in j["resultados"]), "o operador não recebe as fontes do código")
checar({"titulo", "curta", "calculo", "fazer", "cuidado", "telas", "em_revisao"} <= set(j["resultados"][0]),
       "e recebe o conteúdo completo da resposta")
r = c.post("/ajuda/buscar", headers=H("co"), json={"pergunta": "por que esse devedor está em primeiro na lista"})
checar(all("fontes" in x for x in r.json()["resultados"]), "o COMANDO recebe as fontes")
r = c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "x" * 301})
checar(r.status_code == 422, "pergunta com mais de 300 caracteres: 422")
r = c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": "qual a previsão do tempo"})
checar(r.status_code == 200 and r.json()["certeza"] is False, "fora do assunto: sem certeza", str(r.json().get("certeza")))

checar(c.get("/ajuda/entradas/psi", headers=H("op")).status_code == 404, "operador acessando PSI direto: 404")
checar(c.get("/ajuda/entradas/psi", headers=H("ad")).status_code == 200, "admin vê o PSI")
checar(c.get("/ajuda/entradas/ks", headers=H("ad")).status_code == 404, "admin não vê o KS (tela do COMANDO)")
r = c.get("/ajuda/entradas/ks", headers=H("co"))
checar(r.status_code == 200 and r.json().get("fontes"), "o COMANDO vê o KS, com fontes")
checar(c.get("/ajuda/entradas/nao-existe", headers=H("co")).status_code == 404, "entrada inexistente: 404")

idx_op = c.get("/ajuda/indice", headers=H("op")).json()
idx_cm = c.get("/ajuda/indice", headers=H("co")).json()
n_op, n_cm = sum(len(g["entradas"]) for g in idx_op), sum(len(g["entradas"]) for g in idx_cm)
checar(0 < n_op < n_cm == len(ajuda.carregar()), f"o índice do operador tem {n_op} e o do COMANDO {n_cm} (todas)")
checar(all(g["assunto"] in ajuda.ASSUNTOS.values() for g in idx_cm), "todo assunto tem nome na tabela de assuntos")

est = c.get("/ajuda/estado-do-modelo", headers=H("op")).json()
checar(est.get("nivel") in ("sintetico", "insuficiente", "ok") and "aviso" in est, "o estado do modelo é entregue a qualquer perfil", str(est)[:80])

# ── a pergunta não vai para o log ────────────────────────────────────────
pergunta = "pergunta-sigilosa-do-operador-xyz-123"
saida, erro = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
    c.post("/ajuda/buscar", headers=H("op"), json={"pergunta": pergunta})
checar(pergunta not in saida.getvalue() + erro.getvalue(), "o texto da pergunta não aparece na saída do servidor")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
