"""Regressão: erro interno não vaza segredo, e deixa rastro para você.

    python test_erros_internos.py

Numa simulação de banco recusando conexão, a resposta da API trazia o host
interno e a senha — o texto bruto da exceção ia para o cliente. Eram 39
`detail=f"...{e}"`, e qualquer exceção não tratada caía no mesmo caminho.

O que precisa ser verdade agora:

  1. Nada do interior do servidor aparece na resposta, só um código.
  2. O mesmo código está no log, com o traceback — mascarado.
  3. O 500 sai com cabeçalho CORS. Sem isso o navegador esconde o corpo e o
     cliente vê "Failed to fetch": o código existiria e ninguém o leria.
  4. O que NÃO é erro interno continua igual: 4xx de validação e o 503 do
     assistente de conexão, que vem do banco do próprio cliente.
"""
import io
import json
import logging
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import erros                                       # noqa: E402
import main                                        # noqa: E402
from fastapi import HTTPException                  # noqa: E402
from fastapi.responses import JSONResponse         # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from auth import criar_token                       # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


# ── captura o que vai para o log ─────────────────────────────────────────
saida = io.StringIO()
erros.log.handlers.clear()          # sem o stdout do módulo: só a captura do teste
manipulador = logging.StreamHandler(saida)
manipulador.setFormatter(logging.Formatter("%(message)s"))
erros.log.addHandler(manipulador)


def linhas_de_log():
    return [json.loads(l) for l in saida.getvalue().splitlines() if l.strip().startswith("{")]


SEGREDO = "hunter2-senha-do-banco"
HOST = "db.interno.acme:5432"

main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}

# Rotas de teste que levantam o erro direto. Injetar via get_db em rota real não
# serve: listar_carteiras tem um `except Exception` que reembrulha TUDO em
# HTTPException(500), então a exceção nunca chegava não tratada e o middleware
# de captura não era exercitado — o teste passava pelo caminho errado.
_MODO = {"f": None}


@main.app.get("/_teste/erro")
def _rota_de_teste(cpf: str = ""):
    return _MODO["f"]()


@main.app.get("/_teste/contato/{cpf}")
def _rota_com_cpf(cpf: str):
    return _MODO["f"]()


c = TestClient(main.app, raise_server_exceptions=False)
ORIGEM = "https://mizan-sand.vercel.app"
H = {"Authorization": "Bearer " + criar_token(
        {"sub": "u-42", "email": "a@a.com", "nome": "A", "role": "admin", "empresa_id": "banco_alfa"}),
     "Origin": ORIGEM}


# ── 1. exceção não tratada ───────────────────────────────────────────────
print("— exceção não tratada —")


def banco_quebrado(*a, **k):
    raise RuntimeError(f"connection to {HOST} refused, password={SEGREDO}")


_MODO["f"] = banco_quebrado
r = c.get("/_teste/erro", headers=H)
corpo = r.text

checar(r.status_code == 500, "responde 500", str(r.status_code))
checar(SEGREDO not in corpo, "a senha não vai na resposta", corpo[:80])
checar(HOST not in corpo, "o host interno também não")
checar("RuntimeError" not in corpo, "nem o nome da exceção")
codigo = r.json().get("codigo_erro", "")
checar(len(codigo) == 8 and codigo in r.json()["detail"],
       "a resposta traz um código curto, repetido na mensagem", codigo)

ev = [e for e in linhas_de_log() if e.get("codigo") == codigo]
checar(len(ev) == 1, "e o mesmo código está no log", f"{len(ev)} evento(s)")
if ev:
    e = ev[0]
    checar(e["tipo"] == "RuntimeError", "o log guarda o tipo do erro",
           "RuntimeError = chegou não tratada, pelo middleware; HTTPException = pelo handler")
    checar("Traceback" in e["traceback"] and "banco_quebrado" in e["traceback"],
           "e o traceback completo", "é ele que responde 'onde quebrou'")
    checar(SEGREDO not in json.dumps(e), "mas a senha foi mascarada no próprio log",
           e["mensagem"][:70])
    checar(e["usuario"] == "u-42" and e["empresa_id"] == "banco_alfa",
           "sabe quem chamou", f"{e['usuario']} / {e['empresa_id']}")
    checar(e["rota"] == "/_teste/erro", "e qual rota", e["rota"])


# ── 2. o CORS: sem ele o navegador esconde o código ──────────────────────
print("\n— o navegador consegue ler? —")
checar(r.headers.get("access-control-allow-origin") == ORIGEM,
       "o 500 sai com cabeçalho CORS",
       "sem isto o navegador mostra 'Failed to fetch' e o código não chega")

r2 = c.get("/carteiras", headers={**H, "Origin": "https://site-de-terceiro.com"})
checar("access-control-allow-origin" not in r2.headers,
       "e origem desconhecida continua sem CORS", "a lista de permitidas não mudou")


# ── 2b. o controle: por que não bastava um exception_handler(Exception) ──
print("\n— controle: o handler comum de Exception —")
from fastapi import FastAPI                          # noqa: E402
from fastapi.middleware.cors import CORSMiddleware   # noqa: E402

ingenuo = FastAPI()
ingenuo.add_middleware(CORSMiddleware, allow_origins=[ORIGEM], allow_methods=["*"], allow_headers=["*"])


@ingenuo.exception_handler(Exception)
async def _so_um_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "erro interno"})


@ingenuo.get("/x")
def _x():
    raise RuntimeError("boom")


ri = TestClient(ingenuo, raise_server_exceptions=False).get("/x", headers={"Origin": ORIGEM})
checar(ri.status_code == 500 and "access-control-allow-origin" not in ri.headers,
       "um handler comum de Exception devolve 500 SEM cabeçalho CORS",
       "é a premissa do módulo: sem isto o navegador esconde o corpo")


# ── 3. HTTPException 500 com o texto da exceção ──────────────────────────
print("\n— HTTPException(500) com detail vazando —")
saida.truncate(0); saida.seek(0)


def levanta_500(*a, **k):
    try:
        raise ValueError(f"postgresql://app:{SEGREDO}@{HOST}/prod falhou")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {e}")


_MODO["f"] = levanta_500
r = c.get("/_teste/erro", headers=H)
checar(r.status_code == 500 and SEGREDO not in r.text and HOST not in r.text,
       "o texto da exceção deixa de sair", r.text[:80])
ev = linhas_de_log()
checar(len(ev) == 1 and SEGREDO not in json.dumps(ev[0]),
       "e vai para o log, com a credencial da URL mascarada",
       ev[0]["mensagem"][:60] if ev else "sem evento")
checar(ev and "ValueError" in ev[0]["traceback"],
       "o traceback encadeado mostra a causa original",
       "o `raise ... from` implícito preserva o erro de dentro")


# ── 4. o que não é erro interno segue igual ──────────────────────────────
print("\n— o que não mudou —")


def levanta(status, msg):
    def f(*a, **k):
        raise HTTPException(status_code=status, detail=msg)
    return f


saida.truncate(0); saida.seek(0)
_MODO["f"] = levanta(400, "Senha fraca: use letras e números.")
r = c.get("/_teste/erro", headers=H)
checar(r.status_code == 400 and r.json()["detail"] == "Senha fraca: use letras e números.",
       "4xx de validação passa intacto", r.text[:60])

_MODO["f"] = levanta(503, "Erro ao conectar no banco: password authentication failed for user \"joao\"")
r = c.get("/_teste/erro", headers=H)
checar(r.status_code == 503 and "password authentication failed" in r.json()["detail"],
       "503 do banco do cliente passa intacto",
       "o assistente de conexão precisa mostrar por que falhou")
checar(linhas_de_log() == [], "e nenhum deles é registrado como erro interno")

_MODO["f"] = levanta(401, "Token inválido")
r = c.get("/_teste/erro", headers=H)
checar(r.status_code == 401, "401 segue 401")


# ── 5. o caminho de rota não pode carregar CPF ───────────────────────────
print("\n— CPF no caminho —")
saida.truncate(0); saida.seek(0)
_MODO["f"] = banco_quebrado
c.get("/_teste/contato/12345678900", headers=H)
ev = linhas_de_log()
checar(ev and "12345678900" not in json.dumps(ev[0]),
       "o CPF da URL não vai para o log",
       ev[0]["rota"] if ev else "sem evento")
checar(ev and "{cpf}" in ev[0]["rota"], "vai o modelo da rota, não o caminho real",
       ev[0]["rota"] if ev else "")


# ── 6. mascaramento ──────────────────────────────────────────────────────
print("\n— mascaramento —")
casos = [
    ("CPF formatado",   "titular 123.456.789-00 não encontrado", "123.456.789-00"),
    ("CPF só dígitos",  "cpf=12345678900 sem feedback",          "12345678900"),
    ("senha chave=val", "falha com password=abc123 no host",     "abc123"),
    ("senha em pt",     "senha: minhaSenha9 inválida",           "minhaSenha9"),
    ("URL com senha",   "postgresql://app:s3nh4@db:5432/x",      "s3nh4"),
    ("token bearer",    "Authorization: Bearer eyJhbGciOi.abc.def", "eyJhbGciOi"),
    ("api key",         "api_key=sk_live_ABCDEF caiu",           "sk_live_ABCDEF"),
]
for nome, entrada, segredo in casos:
    checar(segredo not in erros.mascarar(entrada), f"mascara {nome}", erros.mascarar(entrada)[:55])

comuns = ["Erro na linha 42 do arquivo", "score 61.2 e valor 4821.55", "12345 devedores",
          "protocolo 1234567890"]        # dez dígitos: não é CPF
for t in comuns:
    checar(erros.mascarar(t) == t, f"não mexe em texto comum: {t!r}")


# ── 7. o log não duplica ─────────────────────────────────────────────────
print("\n— o log —")
antes = len(erros.log.handlers)
erros.configurar_log(); erros.configurar_log()
checar(len(erros.log.handlers) == antes, "configurar o log duas vezes não duplica as linhas")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
