"""Corpo grande é recusado antes de virar memória.

    python test_limite_tamanho.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

from fastapi import FastAPI, File, UploadFile, Request   # noqa: E402
from fastapi.testclient import TestClient                # noqa: E402
import limite                                            # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

MB = limite.MB
alcancou = {"n": 0, "lidos": 0}
app = FastAPI()

@app.post("/analisar")
async def a(file: UploadFile = File(...)):
    alcancou["n"] += 1
    d = await file.read()
    alcancou["lidos"] = len(d)
    return {"bytes": len(d)}

@app.post("/empresa/foto")
async def f(file: UploadFile = File(...)):
    return {"bytes": len(await file.read())}

@app.post("/outra")
async def o(req: Request):
    return {"bytes": len(await req.body())}

@app.get("/analisar")
def g(): return {"ok": 1}

limite.instalar(app)
c = TestClient(app, raise_server_exceptions=False)

def up(rota, n):
    return c.post(rota, files={"file": ("x.csv", b"a" * n)})

r = up("/analisar", 1 * MB)
checar(r.status_code == 200 and r.json()["bytes"] == MB, "arquivo dentro do teto passa", str(r.status_code))
r = up("/analisar", 24 * MB)
checar(r.status_code == 200, "24 MB passa (teto 25)", str(r.status_code))

alcancou["n"] = 0
r = up("/analisar", 26 * MB)
checar(r.status_code == 413, "26 MB: 413 por Content-Length", str(r.status_code))
checar(alcancou["n"] == 0, "a rota nem foi chamada")
checar("25 MB" in r.text, "mensagem cita o limite", r.text[:80])

r = up("/empresa/foto", 6 * MB)
checar(r.status_code == 413 and "5 MB" in r.text, "foto de 6 MB: 413 com teto de 5", str(r.status_code))
r = up("/empresa/foto", 4 * MB)
checar(r.status_code == 200, "foto de 4 MB passa", str(r.status_code))

r = c.post("/outra", content=b"x" * (3 * MB))
checar(r.status_code == 413, "rota sem teto próprio: padrão de 2 MB", str(r.status_code))
r = c.post("/outra", content=b"x" * 1000)
checar(r.status_code == 200, "JSON pequeno passa")
r = c.get("/analisar")
checar(r.status_code == 200, "GET não é afetado")

# sem Content-Length (chunked): conta os bytes
def gerador():
    for _ in range(30):
        yield b"a" * MB
alcancou["n"] = 0
r = c.post("/outra", content=gerador())
checar(r.status_code == 413, "chunked acima do teto: 413 contando bytes", str(r.status_code))

body = (b"--B\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.csv\"\r\n"
        b"Content-Type: text/csv\r\n\r\n" + b"a" * (27 * MB) + b"\r\n--B--\r\n")
def gen2():
    for i in range(0, len(body), MB):
        yield body[i:i + MB]
r = c.post("/analisar", content=gen2(), headers={"Content-Type": "multipart/form-data; boundary=B"})
checar(r.status_code == 413, "multipart chunked de 27 MB: 413 (não 400/422)", str(r.status_code))

# Content-Length declarado grande: nenhum byte do corpo é lido
import asyncio
chamadas = {"receive": 0}
async def inner(scope, receive, send):
    await receive()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b""})
mw = limite.LimiteDeTamanho(inner)
saida = []
async def rec():
    chamadas["receive"] += 1
    return {"type": "http.request", "body": b"x", "more_body": False}
async def env(m): saida.append(m)
scope = {"type": "http", "method": "POST", "path": "/analisar",
         "headers": [(b"content-length", str(40 * MB).encode())]}
asyncio.run(mw(scope, rec, env))
checar(saida and saida[0]["status"] == 413 and chamadas["receive"] == 0,
       "Content-Length de 40 MB: 413 sem ler corpo", f"{saida[:1]} leituras={chamadas['receive']}")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
