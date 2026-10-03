"""Marca da empresa no login, pelo domínio do e-mail.

    python test_marca_login.py

A resposta depende só do domínio, nunca de a pessoa ter conta; domínio público
nunca mapeia; só o COMANDO cadastra domínios, e cada domínio é de uma empresa.
"""
import os, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                   # noqa: E402
import marca                                  # noqa: E402
from auth import criar_token                  # noqa: E402
from fastapi.testclient import TestClient     # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

CFG = [{"id": "1", "empresa_id": "goias_bank", "nome_exibicao": "Goiás Bank", "foto_url": "https://x/goias.png",
        "cor_primaria": "#0a7d3b", "extra": {"dominios_email": ["goiasbank.com.br"], "retencao": {"ativa": True, "dias": 365}}},
       {"id": "2", "empresa_id": "alfa", "nome_exibicao": "Banco Alfa", "extra": {}}]
USUARIOS = [{"id": "u1", "email": "joao@goiasbank.com.br", "empresa_id": "goias_bank"}]

class Q:
    def __init__(s, t): s.t, s.f, s.op, s.d = t, [], "select", None
    def select(s, *a, **k): return s
    def eq(s, c, v): s.f.append((c, v)); return s
    def limit(s, n): return s
    def update(s, d): s.op, s.d = "update", d; return s
    def insert(s, d): s.op, s.d = "insert", d; return s
    def execute(s):
        linhas = [x for x in (CFG if s.t == "empresa_config" else USUARIOS) if all(x.get(c) == v for c, v in s.f)]
        if s.op == "update":
            for x in linhas: x.update(s.d)
        if s.op == "insert":
            CFG.append(dict(s.d)); linhas = [s.d]
        return type("R", (), {"data": [dict(x) for x in linhas]})()
main.get_db = lambda: type("DB", (), {"table": staticmethod(lambda n: Q(n))})()
main._registrar_auditoria = lambda *a, **k: None
U = {"uc": {"ativo": True, "id": "uc", "role": "comando", "empresa_id": ""},
     "ua": {"ativo": True, "id": "ua", "role": "admin", "empresa_id": "alfa"}}
main.buscar_usuario_por_id = lambda uid: U[uid]
H = lambda u: {"Authorization": "Bearer " + criar_token({"sub": u, "email": "x@x", "nome": "N",
                                                          "role": U[u]["role"], "empresa_id": U[u]["empresa_id"]})}
c = TestClient(main.app, raise_server_exceptions=False)
marca_de = lambda e: c.get("/empresa/marca", params={"email": e}).json()

print("— login —")
r = marca_de("joao@goiasbank.com.br")
checar(r["empresa"] and r["empresa"]["nome_exibicao"] == "Goiás Bank" and r["empresa"]["foto_url"], "domínio cadastrado: nome e logo", str(r))
checar(marca_de("ninguem@goiasbank.com.br") == r, "a resposta é igual para quem NÃO tem conta (não revela quem tem acesso)")
checar(set(r["empresa"]) == {"nome_exibicao", "foto_url", "cor_primaria"}, "não devolve id nem configurações internas", str(r["empresa"]))
checar(marca_de("JOAO@GoiasBank.com.br")["empresa"] is not None, "maiúsculas não atrapalham")
checar(marca_de("x@gmail.com")["empresa"] is None and marca_de("x@outro.com.br")["empresa"] is None, "público ou desconhecido: só Mizan")
checar(marca_de("lixo")["empresa"] is None and marca_de("")["empresa"] is None, "texto sem domínio: só Mizan")

print("\n— cadastro de domínios —")
r = c.put("/comando/empresas/alfa/dominios", headers=H("ua"), json={"dominios": ["alfa.com.br"]})
checar(r.status_code == 403, "admin de empresa não cadastra (poderia pôr o domínio de outro cliente)", r.status_code)
r = c.put("/empresa/config", headers=H("ua"), json={"extra": {"dominios_email": ["goiasbank.com.br"]}})
checar(r.status_code == 400, "nem pela rota genérica de configuração", r.status_code)
checar(c.put("/comando/empresas/alfa/dominios", headers=H("uc"), json={"dominios": ["gmail.com"]}).status_code == 422, "e-mail público é recusado")
checar(c.put("/comando/empresas/alfa/dominios", headers=H("uc"), json={"dominios": ["nao é dominio"]}).status_code == 422, "formato inválido é recusado")
r = c.put("/comando/empresas/alfa/dominios", headers=H("uc"), json={"dominios": ["goiasbank.com.br"]})
checar(r.status_code == 409, "domínio de outra empresa é recusado", r.text[:100])
r = c.put("/comando/empresas/alfa/dominios", headers=H("uc"), json={"dominios": ["@Alfa.com.br", "alfa.com.br", "bancoalfa.com"]})
checar(r.status_code == 200 and r.json()["dominios"] == ["alfa.com.br", "bancoalfa.com"], "COMANDO cadastra; normaliza e tira repetido", r.text[:120])
checar(marca_de("maria@alfa.com.br")["empresa"]["nome_exibicao"] == "Banco Alfa", "e o login já mostra a marca nova (cache limpo)")
goias = next(x for x in CFG if x["empresa_id"] == "goias_bank")
c.put("/comando/empresas/goias_bank/dominios", headers=H("uc"), json={"dominios": ["goiasbank.com.br", "goias.com.br"]})
checar(goias["extra"].get("retencao") == {"ativa": True, "dias": 365}, "gravar domínios não apaga o resto da configuração")
checar(c.get("/comando/empresas/goias_bank/dominios", headers=H("uc")).json()["dominios"] == ["goiasbank.com.br", "goias.com.br"], "COMANDO lê os domínios")

print("\n— limite de consultas —")
checar(("GET", "/empresa/marca") in __import__("limite").REGRAS, "a rota pública tem limite de chamadas")

print("\nRESULTADO:", "tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
