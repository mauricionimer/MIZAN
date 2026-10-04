"""Dúvidas ao COMANDO: mascaradas, isoladas por perfil e com resposta que chega a quem perguntou.

    python test_duvidas.py
"""
import os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
import limite                                      # noqa: E402
from ajuda_duvidas import mascarar_pii             # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

# ── máscara ──────────────────────────────────────────────────────────────
print("— máscara —")
casos = {
    "devedor 123.456.789-09 com nota 12": "[CPF]", "cpf 12345678909": "[CPF]",
    "cnpj 12.345.678/0001-95": "[CNPJ]", "fulano.silva@banco.com.br ligou": "[e-mail]",
    "tel (62) 99999-8888": "[telefone]", "tel +55 62 99999 8888": "[telefone]", "contrato 1234567890123": "[número]",
}
for texto, esperado in casos.items():
    out, n = mascarar_pii(texto)
    checar(esperado in out and n >= 1 and not any(ch.isdigit() for ch in out.replace("12", "")) or esperado in out,
           f"mascara: {texto!r}", out)
for ok in ["prazo de 365 dias", "score 85 e nota 12", "R$ 1.234,56", "arquivo de 25 MB", "30% de comissão", "10000 linhas", "em 2026", "taxa 0,25"]:
    checar(mascarar_pii(ok) == (ok, 0), f"não mexe em número comum: {ok!r}")
once, _ = mascarar_pii("cpf 123.456.789-09 e a@b.com")
checar(mascarar_pii(once)[0] == once, "mascarar duas vezes não muda nada")

# ── banco de mentira ─────────────────────────────────────────────────────
TAB = {"duvidas": []}
AUD = []
class Q:
    def __init__(s, t): s.t, s.f, s.nulos, s.op, s.d, s.ord, s.rng, s.lim, s.cont = t, {}, [], "select", None, None, None, None, False
    def select(s, *a, **k):
        s.cont = k.get("count") == "exact"
        s.cols = None if (not a or a[0] == "*") else [c.strip() for c in a[0].split(",")]
        return s
    def eq(s, c, v): s.f[c] = v; return s
    def is_(s, c, _): s.nulos.append(c); return s
    def order(s, c, desc=False): s.ord = (c, desc); return s
    def limit(s, n): s.lim = n; return s
    def range(s, i, f): s.rng = (i, f); return s
    def insert(s, d): s.op, s.d = "insert", d; return s
    def update(s, d): s.op, s.d = "update", d; return s
    def _casa(s, r): return all(r.get(k) == v for k, v in s.f.items()) and all(r.get(c) is None for c in s.nulos)
    def execute(s):
        linhas = TAB[s.t]
        if s.op == "insert":
            r = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), "estado": "aberta",
                 "resposta": None, "respondida_em": None, "respondida_por": None, "visto_em": None,
                 "sugestao_estado": None, "sugestao_titulo": None, **s.d}
            linhas.append(r); return type("R", (), {"data": [dict(r)], "count": None})()
        if s.op == "update":
            for r in linhas:
                if s._casa(r): r.update(s.d)
            return type("R", (), {"data": [], "count": None})()
        d = [r for r in linhas if s._casa(r)]
        if s.ord: d = sorted(d, key=lambda r: r.get(s.ord[0]) or "", reverse=s.ord[1])
        total = len(d)
        if s.rng: d = d[s.rng[0]:s.rng[1] + 1]
        if s.lim is not None: d = d[:s.lim]
        proj = (lambda r: {k: r.get(k) for k in s.cols}) if getattr(s, "cols", None) else dict
        return type("R", (), {"data": [proj(r) for r in d], "count": total if s.cont else None})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
U = {"op1": {"ativo": True, "id": "op1", "role": "operador", "empresa_id": "alfa", "nome": "Ana"},
     "op2": {"ativo": True, "id": "op2", "role": "operador", "empresa_id": "alfa", "nome": "Beto"},
     "opb": {"ativo": True, "id": "opb", "role": "operador", "empresa_id": "beta", "nome": "Caio"},
     "ad":  {"ativo": True, "id": "ad", "role": "admin", "empresa_id": "alfa", "nome": "Diretora"},
     "co":  {"ativo": True, "id": "co", "role": "comando", "empresa_id": "", "nome": "Sócio"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
main._registrar_auditoria = lambda *a, **k: AUD.append(k)
c = TestClient(main.app, raise_server_exceptions=False)
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": f"{u}@x.com", "nome": U[u]["nome"], "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}

# ── enviar ───────────────────────────────────────────────────────────────
print("\n— enviar —")
r = c.post("/ajuda/duvidas", headers=H("op1"), json={"pergunta": "o devedor 123.456.789-09 (fulano@x.com) está com nota 12, por quê?", "tela": "/devedor/3", "buscou": "nota do cpf 12345678909"})
checar(r.status_code == 201 and r.json()["mascarado"] is True, "operador envia; o aviso de máscara vem na resposta", f"{r.status_code} {r.text[:60]}")
linha = TAB["duvidas"][0]
tudo = " ".join(str(v) for v in linha.values())
checar("123.456.789-09" not in tudo and "12345678909" not in tudo and "fulano@x.com" not in tudo,
       "nada de CPF nem e-mail em NENHUM campo gravado", tudo[:120])
checar(linha["empresa_id"] == "alfa" and linha["autor_id"] == "op1" and linha["estado"] == "aberta", "empresa e autor vêm do token, não do corpo")
r = c.post("/ajuda/duvidas", headers=H("op1"), json={"pergunta": "como funciona a fila?"})
checar(r.status_code == 201 and r.json()["mascarado"] is False, "pergunta sem dado pessoal: sem aviso")
checar(c.post("/ajuda/duvidas", headers=H("op1"), json={"pergunta": "ab"}).status_code == 422, "curta demais: 422")
checar(c.post("/ajuda/duvidas", headers=H("op1"), json={"pergunta": "x" * 2001}).status_code == 422, "longa demais: 422")
checar(c.post("/ajuda/duvidas", json={"pergunta": "sem login"}).status_code in (401, 403), "sem login: recusado")
checar(("POST", "/ajuda/duvidas") in limite.REGRAS, "há limite de envios por hora")
c.post("/ajuda/duvidas", headers=H("op2"), json={"pergunta": "dúvida do Beto sobre o alcance"})
c.post("/ajuda/duvidas", headers=H("opb"), json={"pergunta": "dúvida da outra empresa"})
c.post("/ajuda/duvidas", headers=H("co"), json={"pergunta": "dúvida do próprio comando"})

# ── ver ──────────────────────────────────────────────────────────────────
print("\n— quem vê o quê —")
mine = c.get("/ajuda/duvidas/minhas", headers=H("op1")).json()
checar(len(mine) == 2 and all("autor_email" not in x for x in mine), "cada um vê as próprias (2), sem dados do autor", str(len(mine)))
checar(all("Beto" not in x["pergunta"] for x in mine), "e nada de colegas")
eq = c.get("/ajuda/duvidas/equipe", headers=H("ad"))
checar(eq.status_code == 200 and len(eq.json()) == 3 and {x["autor_nome"] for x in eq.json()} == {"Ana", "Beto"},
       "o administrador vê as 3 da equipe dele (Ana e Beto)", str(len(eq.json())))
checar(all("outra empresa" not in x["pergunta"] and "comando" not in x["pergunta"] for x in eq.json()), "e nenhuma de outra empresa nem do COMANDO")
checar(c.get("/ajuda/duvidas/equipe", headers=H("op1")).status_code == 403, "operador não vê a da equipe")
checar(c.get("/ajuda/duvidas/equipe", headers=H("co")).status_code == 403, "COMANDO usa a rota própria")
checar(c.get("/comando/duvidas", headers=H("ad")).status_code == 403 and c.get("/comando/duvidas", headers=H("op1")).status_code == 403,
       "administrador e operador não entram na fila do COMANDO")
lista = c.get("/comando/duvidas", headers=H("co")).json()
checar(lista["total"] == 5 and lista["abertas"] == 5 and len(lista["itens"]) == 5, "o COMANDO vê as 5, de todas as empresas", f"{lista['total']} / abertas {lista['abertas']}")
checar(all(a["created_at"] <= b["created_at"] for a, b in zip(lista["itens"], lista["itens"][1:])), "abertas: a mais antiga primeiro")
checar(c.get("/comando/duvidas", headers=H("co"), params={"empresa_id": "beta"}).json()["total"] == 1, "filtra por empresa")
checar(c.get("/comando/duvidas", headers=H("co"), params={"estado": "x"}).status_code == 422, "estado inválido: 422")

# ── responder ────────────────────────────────────────────────────────────
print("\n— responder —")
id_ana = next(x["id"] for x in TAB["duvidas"] if "devedor" in x["pergunta"])
checar(c.get("/ajuda/duvidas/novidades", headers=H("op1")).json()["respondidas_nao_vistas"] == 0, "antes de responder: nenhuma novidade")
checar(c.post(f"/comando/duvidas/{id_ana}/responder", headers=H("ad"), json={"resposta": "tentativa"}).status_code == 403, "administrador não responde")
checar(c.post("/comando/duvidas/nao-e-uuid/responder", headers=H("co"), json={"resposta": "ok ok"}).status_code == 404, "id inválido: 404, não 500")
checar(c.post(f"/comando/duvidas/{uuid.uuid4()}/responder", headers=H("co"), json={"resposta": "ok ok"}).status_code == 404, "dúvida inexistente: 404")
AUD.clear()
r = c.post(f"/comando/duvidas/{id_ana}/responder", headers=H("co"), json={"resposta": "A nota 12 vem de dados incompletos: veja o aviso."})
checar(r.status_code == 200, "o COMANDO responde")
d = next(x for x in TAB["duvidas"] if x["id"] == id_ana)
checar(d["estado"] == "respondida" and d["respondida_por"] == "co@x.com" and d["respondida_em"] and d["visto_em"] is None, "estado, autor da resposta e data gravados")
checar(AUD and AUD[0]["acao"] == "duvida_respondida" and "nota 12" not in str(AUD[0]), "ficou na auditoria, sem o texto")
checar(c.get("/ajuda/duvidas/novidades", headers=H("op1")).json()["respondidas_nao_vistas"] == 1, "quem perguntou tem 1 resposta nova")
checar(c.get("/ajuda/duvidas/novidades", headers=H("op2")).json()["respondidas_nao_vistas"] == 0, "e o colega, nenhuma")
mine = c.get("/ajuda/duvidas/minhas", headers=H("op1")).json()
checar(any(x["resposta"] and "dados incompletos" in x["resposta"] for x in mine), "a resposta aparece nas dúvidas dele")
c.post("/ajuda/duvidas/vistas", headers=H("op2"))
checar(c.get("/ajuda/duvidas/novidades", headers=H("op1")).json()["respondidas_nao_vistas"] == 1, "o colega marcar como visto não apaga o aviso dele")
c.post("/ajuda/duvidas/vistas", headers=H("op1"))
checar(c.get("/ajuda/duvidas/novidades", headers=H("op1")).json()["respondidas_nao_vistas"] == 0, "ele abriu: o aviso some")
c.post(f"/comando/duvidas/{id_ana}/responder", headers=H("co"), json={"resposta": "Correção: o aviso fica na linha da fila."})
checar(c.get("/ajuda/duvidas/novidades", headers=H("op1")).json()["respondidas_nao_vistas"] == 1, "resposta corrigida avisa de novo")
checar(c.get("/comando/duvidas", headers=H("co")).json()["abertas"] == 4, "a fila do COMANDO diminui (4 abertas)")

# ── virar ajuda ──────────────────────────────────────────────────────────
print("\n— sugerir para a Central (com revisão) —")
id_beto = next(x["id"] for x in TAB["duvidas"] if "Beto" in x["pergunta"])
checar(c.post(f"/comando/duvidas/{id_beto}/sugerir", headers=H("co"), json={"titulo": "x"}).status_code == 409, "só se sugere o que já foi respondido")
checar(c.post(f"/comando/duvidas/{id_ana}/sugerir", headers=H("op1"), json={}).status_code == 403, "operador não sugere")
checar(c.post(f"/comando/duvidas/{id_ana}/sugerir", headers=H("co"), json={"titulo": "Por que a nota é baixa com dados faltando"}).status_code == 200, "COMANDO marca para sugestão")
checar(c.get("/comando/duvidas", headers=H("co"), params={"estado": "sugestao"}).json()["total"] == 1, "aparece na fila de sugestões")
checar(c.get("/comando/duvidas", headers=H("co")).json()["sugestoes_pendentes"] == 1, "e no contador")
checar(c.post(f"/comando/duvidas/{id_ana}/sugestao", headers=H("co"), json={"estado": "publicada"}).status_code == 422, "estado de revisão inválido: 422")
checar(c.post(f"/comando/duvidas/{id_ana}/sugestao", headers=H("co"), json={"estado": "aprovada"}).status_code == 200, "revisão aprova")
d = next(x for x in TAB["duvidas"] if x["id"] == id_ana)
checar(d["sugestao_estado"] == "aprovada" and d["sugestao_revisada_por"] == "co@x.com", "quem revisou fica registrado")
checar(c.post(f"/comando/duvidas/{id_ana}/sugestao", headers=H("co"), json={"estado": "descartada"}).status_code == 409, "sem sugestão pendente não há o que revisar")
c.post(f"/comando/duvidas/{id_ana}/sugerir", headers=H("co"), json={"sugerir": False})
checar(next(x for x in TAB["duvidas"] if x["id"] == id_ana)["sugestao_estado"] is None, "dá para retirar a sugestão")

# ── FAQ ──────────────────────────────────────────────────────────────────
print("\n— publicar no FAQ —")
checar(c.post(f"/comando/duvidas/{id_beto}/faq", headers=H("co"), json={}).status_code == 409, "só se publica o que já foi respondido")
checar(c.post(f"/comando/duvidas/{id_ana}/faq", headers=H("ad"), json={}).status_code == 403, "administrador não publica")
checar(c.get("/ajuda/faq", headers=H("opb")).json() == [], "FAQ vazio antes de publicar")
r = c.post(f"/comando/duvidas/{id_ana}/faq", headers=H("co"), json={"titulo": "Por que a nota cai com dados faltando?"})
checar(r.status_code == 200, "COMANDO publica no FAQ")
faq = c.get("/ajuda/faq", headers=H("opb")).json()
checar(len(faq) == 1 and faq[0]["pergunta"] == "Por que a nota cai com dados faltando?" and "linha da fila" in faq[0]["resposta"],
       "o FAQ aparece para usuário de OUTRA empresa, com o título e a resposta", str(faq)[:120])
checar(set(faq[0]) == {"id", "pergunta", "resposta"}, "sem autor, e-mail ou empresa de quem perguntou", str(set(faq[0])))
checar(c.get("/comando/duvidas", headers=H("co"), params={"estado": "faq"}).json()["total"] == 1, "COMANDO lista o que está no FAQ")
checar(c.get("/ajuda/faq").status_code in (401, 403), "sem login não lê o FAQ")
c.post(f"/comando/duvidas/{id_ana}/faq", headers=H("co"), json={"publicar": False})
checar(c.get("/ajuda/faq", headers=H("opb")).json() == [], "tirar do FAQ some para todos")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
