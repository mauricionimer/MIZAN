"""Regressão: limite de taxa e portão de análises simultâneas.

    python test_limite.py

Só o login tinha freio. Upload, backtest e as sondas de banco de dados não
tinham nenhum, e "esqueci minha senha" disparava e-mail em massa.

O que este teste vigia é o que falha em SILÊNCIO:

  1. As regras apontarem para rota que não existe. Um typo ou uma rota
     renomeada desligaria o freio sem erro nenhum — a regra continuaria lá,
     bonita, sem proteger nada.
  2. O portão de simultâneas não devolver a vaga quando a requisição falha.
     Duas análises que quebram e o sistema recusa análise para sempre.
  3. O 429 sair sem CORS. O navegador esconderia o corpo e o usuário veria
     "Failed to fetch" em vez de "aguarde 40 s".
  4. O limite do "esqueci a senha" mudar a resposta. Um 429 ali revelaria que
     o e-mail existe.
"""
import asyncio
import io
import logging
import os
import sys
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import httpx                                       # noqa: E402
import limite                                      # noqa: E402
import main                                        # noqa: E402
from auth import criar_token                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


class Relogio:
    """Tempo controlado: o teste avança a janela sem esperar."""
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


# ── 1. o limitador ───────────────────────────────────────────────────────
print("— janela deslizante —")
rel = Relogio()
L = limite.Limitador(rel)

res = [L.tentar("a", 3, 600) for _ in range(3)]
checar(all(ok for ok, _ in res), "deixa passar até o máximo")
ok, espera = L.tentar("a", 3, 600)
checar(not ok and espera > 0, "recusa a seguinte e diz quanto esperar", f"{espera} s")

rel.t += 100
ok, espera = L.tentar("a", 3, 600)
checar(not ok and 495 <= espera <= 505,
       "a espera é até a MAIS ANTIGA sair da janela, não a janela inteira",
       f"{espera} s (esperado ~501)")

rel.t += 501
checar(L.tentar("a", 3, 600)[0], "passada a espera, libera")

checar(L.tentar("b", 3, 600)[0], "outra chave tem cota própria")

rel.t = 5000.0
L2 = limite.Limitador(rel)
for _ in range(2):
    L2.tentar("x", 2, 10)
rel.t += 4
checar(not L2.tentar("x", 2, 10)[0], "dentro da janela ainda recusa")
rel.t += 7
checar(L2.tentar("x", 2, 10)[0], "e a janela DESLIZA: não espera o bloco inteiro zerar")

# Concorrência: 8 threads disputando a mesma cota
L3 = limite.Limitador()
permitidas = []


def martela():
    for _ in range(50):
        permitidas.append(L3.tentar("k", 100, 60)[0])


ts = [threading.Thread(target=martela) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
checar(sum(permitidas) == 100, "com 8 threads disputando, passam exatamente 100 de 400",
       f"passaram {sum(permitidas)}")

# Teto de chaves
limite.MAX_CHAVES = 50
L4 = limite.Limitador(rel)
for i in range(200):
    L4.tentar(f"lixo-{i}", 5, 60)
checar(len(L4._marcas) <= 50, "tokens inventados não fazem a memória crescer sem fim",
       f"{len(L4._marcas)} chaves")
L4.tentar("recente", 1, 60)
checar(not L4.tentar("recente", 1, 60)[0],
       "e, estourado o teto, chave nova continua sendo limitada",
       "o contrário desligaria o freio justamente sob inundação")
limite.MAX_CHAVES = 20_000


# ── 2. as regras apontam para rotas que existem ──────────────────────────
print("\n— regras e rotas reais —")
rotas = {(m, r.path) for r in main.app.routes for m in getattr(r, "methods", set())}
for (metodo, caminho), regra in limite.REGRAS.items():
    checar((metodo, caminho) in rotas,
           f"{metodo} {caminho} existe de verdade",
           "senão a regra ficaria lá sem proteger nada")
checar(len(limite.REGRAS) >= 5, "e há regras suficientes para o que interessa")


# ── 3. integração no app real ────────────────────────────────────────────
print("\n— no app real —")
erros_log = io.StringIO()
import erros                                       # noqa: E402
erros.log.handlers.clear()
erros.log.addHandler(logging.StreamHandler(erros_log))
limite.log.handlers.clear()
limite.log.addHandler(logging.StreamHandler(io.StringIO()))

main.buscar_usuario_por_id = lambda uid: {"ativo": True, "id": uid}
c = TestClient(main.app, raise_server_exceptions=False)
ORIGEM = "https://mizan-sand.vercel.app"


def cab(sub):
    return {"Authorization": "Bearer " + criar_token(
        {"sub": sub, "email": f"{sub}@x.com", "nome": sub, "role": "admin", "empresa_id": "e"}),
        "Origin": ORIGEM}


limite.LIMITADOR.limpar()
regra = limite.REGRAS[("POST", "/testar-db")]
codigos = [c.post("/testar-db", headers=cab("u1"), json={}).status_code for _ in range(regra.maximo)]
checar(all(cod == 422 for cod in codigos),
       f"as primeiras {regra.maximo} chegam à rota (422 de validação, sem stub nenhum)",
       str(set(codigos)))

r = c.post("/testar-db", headers=cab("u1"), json={})
checar(r.status_code == 429, "a seguinte é recusada com 429", str(r.status_code))
checar(int(r.headers.get("retry-after", 0)) >= 1, "com Retry-After", r.headers.get("retry-after"))
checar("Aguarde" in r.json()["detail"] and r.json()["espera_s"] >= 1,
       "e uma mensagem que o usuário entende", r.json()["detail"])
checar(r.headers.get("access-control-allow-origin") == ORIGEM,
       "o 429 sai COM cabeçalho CORS",
       "sem isto o navegador mostra 'Failed to fetch' em vez de 'aguarde 40 s'")
checar('"evento": "erro_interno"' not in erros_log.getvalue(),
       "e não é registrado como erro interno", "429 é comportamento, não falha")

checar(c.post("/testar-db", headers=cab("u2"), json={}).status_code == 422,
       "outro usuário não é afetado", "cada um tem a própria cota")

# o balde é compartilhado entre as duas sondas
r = c.post("/listar-tabelas", headers=cab("u1"), json={})
checar(r.status_code == 429, "/listar-tabelas divide o balde com /testar-db",
       "senão bastaria alternar entre as duas para dobrar a cota")

# rotas sem regra
limite.LIMITADOR.limpar()
cods = {c.get("/health").status_code for _ in range(150)}
checar(cods == {200}, "rota sem regra nunca é limitada", str(cods))

# sem credencial: passa, a rota recusa
cods = {c.post("/testar-db", json={}).status_code for _ in range(60)}
checar(429 not in cods and cods <= {401, 403},
       "sem credencial não vira 429: a rota recusa como sempre", str(cods))

# chave de API (não é JWT): identificada pelo hash, cada uma com a sua cota
limite.LIMITADOR.limpar()
for _ in range(regra.maximo):
    c.post("/testar-db", headers={"Authorization": "Bearer chave-api-1", "Origin": ORIGEM}, json={})
r1 = c.post("/testar-db", headers={"Authorization": "Bearer chave-api-1"}, json={})
r2 = c.post("/testar-db", headers={"Authorization": "Bearer chave-api-2"}, json={})
checar(r1.status_code == 429, "credencial que não é JWT também é limitada")
checar(r2.status_code != 429, "e outra credencial tem cota própria")


# ── 4. o portão de análises simultâneas ──────────────────────────────────
print("\n— portão de simultâneas —")


async def cenario_portao():
    liberar = asyncio.Event()
    quebra = {"sim": False}

    async def lenta(scope, receive, send):
        if scope["type"] != "http":
            return
        if quebra["sim"]:
            raise RuntimeError("a análise quebrou")
        await liberar.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    rel2 = Relogio()
    lim = limite.Limitador(rel2)
    regras = {("POST", "/analisar"): limite.Regra(
        "analise", 100, 600, "muitas {espera}", pesada=True)}
    app = limite.LimiteDeRequisicoes(lenta, regras=regras, simultaneas=1, limitador=lim)
    h = {"Authorization": "Bearer " + criar_token(
        {"sub": "u1", "email": "a@a.com", "nome": "A", "role": "admin", "empresa_id": "e"})}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cl:
        primeira = asyncio.create_task(cl.post("/analisar", headers=h))
        await asyncio.sleep(0.05)               # a primeira está segurando o portão

        segunda = await cl.post("/analisar", headers=h)
        checar(segunda.status_code == 429 and "andamento" in segunda.json()["detail"],
               "a segunda, com o portão ocupado, é recusada", str(segunda.status_code))
        checar(int(segunda.headers["retry-after"]) >= 1, "com Retry-After")

        # quem esbarra no portão não gasta cota de taxa
        gasto = len(lim._marcas.get("analise:u:u1", []))
        checar(gasto == 1, "e a recusa do portão NÃO gasta cota de taxa",
               f"{gasto} marca(s): só a da primeira. Gastar puniria quem só quer a vez")

        liberar.set()
        r1 = await primeira
        checar(r1.status_code == 200, "a primeira termina normalmente")

        terceira = await cl.post("/analisar", headers=h)
        checar(terceira.status_code == 200, "terminada a primeira, a vaga volta")

        # a vaga também volta quando a requisição QUEBRA
        quebra["sim"] = True
        for _ in range(3):
            try:
                await cl.post("/analisar", headers=h)
            except Exception:
                pass
        quebra["sim"] = False
        ok = await cl.post("/analisar", headers=h)
        checar(ok.status_code == 200,
               "depois de três análises que quebraram, ainda aceita a próxima",
               "sem o finally o sistema recusaria análise para sempre")


asyncio.run(cenario_portao())

# a regra não pesada nunca passa pelo portão
async def cenario_leve():
    n = {"vivas": 0, "pico": 0}

    async def app_(scope, receive, send):
        n["vivas"] += 1; n["pico"] = max(n["pico"], n["vivas"])
        await asyncio.sleep(0.02)
        n["vivas"] -= 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    regras = {("POST", "/leve"): limite.Regra("leve", 1000, 60, "x")}
    app = limite.LimiteDeRequisicoes(app_, regras=regras, simultaneas=1,
                                     limitador=limite.Limitador(Relogio()))
    h = {"Authorization": "Bearer " + criar_token(
        {"sub": "u9", "email": "a@a.com", "nome": "A", "role": "admin", "empresa_id": "e"})}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cl:
        rs = await asyncio.gather(*[cl.post("/leve", headers=h) for _ in range(6)])
    checar(all(r.status_code == 200 for r in rs) and n["pico"] > 1,
           "regra sem 'pesada' não passa pelo portão", f"pico simultâneo: {n['pico']}")


asyncio.run(cenario_leve())


# ── 5. "esqueci a senha" ─────────────────────────────────────────────────
print("\n— esqueci a senha —")
import email_utils                                  # noqa: E402

enviados = []
email_utils.email_redefinir_senha = lambda e, n, l: enviados.append(e)
main.criar_reset_token = lambda e: "tok"
main.buscar_usuario = lambda e: {"nome": "Fulano"}
limite.LIMITADOR.limpar()


def esqueci(email):
    return c.post("/auth/esqueci-senha", json={"email": email})


corpos = [esqueci("alvo@banco.com").text for _ in range(6)]
checar(len(set(corpos)) == 1,
       "a resposta é a MESMA com e sem limite",
       "um 429 aqui revelaria que o e-mail existe")
checar(len(enviados) == 3, "mas só 3 e-mails saem por hora para o mesmo endereço",
       f"saíram {len(enviados)}")

esqueci("  ALVO@banco.com ")
checar(len(enviados) == 3, "maiúscula e espaço não contornam o limite")

esqueci("outro@banco.com")
checar(len(enviados) == 4, "outro endereço não é afetado")

# quem martela UM e-mail não pode esgotar a cota global
limite.LIMITADOR.limpar(); enviados.clear()
for _ in range(400):
    esqueci("vitima@banco.com")
esqueci("legitimo@banco.com")
checar("legitimo@banco.com" in enviados,
       "martelar um endereço não bloqueia a redefinição dos outros",
       "o teto global só conta quando o do e-mail deixou passar")

# o teto global existe
limite.LIMITADOR.limpar(); enviados.clear()
for i in range(230):
    esqueci(f"pessoa{i}@x.com")
checar(len(enviados) == 200, "e há um teto global por hora", f"saíram {len(enviados)}")


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
