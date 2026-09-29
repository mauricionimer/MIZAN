"""Regressão: a conexão do cliente não pode apontar para dentro do servidor.

    python test_destino_conexao.py

A tela de conexões existe para o cliente apontar o banco DELE. Sem validação,
aceitava duas coisas que nunca são isso:

  tipo=sqlite, banco=/etc/passwd  →  sqlite:////etc/passwd
  host=169.254.169.254            →  postgresql://...@169.254.169.254/...

O SQLite abre — e cria, quando não existe — um arquivo do servidor, não da
máquina do cliente: hospedado, "arquivo local" do lado de cá é o container. E
como a mesma tela aceita consulta livre, um endereço interno viraria leitura
de serviço da rede de dentro.

Em desenvolvimento nada disso vale: apontar para o Postgres da própria máquina
é o fluxo normal de quem está programando.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")

import main                                        # noqa: E402
from fastapi import HTTPException                  # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


def recusa(**kw):
    """Devolve a mensagem de recusa, ou None se passou."""
    try:
        main._construir_url_db(main.ConexaoDB(**kw))
        return None
    except HTTPException as e:
        return e.detail
    except ValueError:
        return None   # erro de configuração é outra coisa; aqui só interessa a recusa


# ── SQLite ───────────────────────────────────────────────────────────────
print("— SQLite em serviço hospedado —")
for caminho in ("/etc/passwd", "model/mizan_model.pkl", "../../etc/shadow", "novo.db"):
    checar(recusa(tipo="sqlite", banco=caminho) is not None,
           f"recusa sqlite apontando para {caminho!r}")
checar("CSV" in (recusa(tipo="sqlite", banco="x.db") or ""),
       "e a mensagem diz o que fazer no lugar",
       "recusar sem alternativa vira chamado de suporte")


# ── Endereços internos ───────────────────────────────────────────────────
print("\n— endereços que não podem ser o banco do cliente —")
internos = [
    ("127.0.0.1",       "loopback"),
    ("localhost",       "loopback por nome"),
    ("169.254.169.254", "metadata da nuvem"),
    ("10.0.0.5",        "rede privada"),
    ("192.168.1.10",    "rede privada"),
    ("172.16.0.1",      "rede privada"),
    ("0.0.0.0",         "não especificado"),
    ("::1",             "loopback IPv6"),
]
for host, porque in internos:
    checar(recusa(tipo="postgres", host=host, banco="d", usuario="u", senha="p") is not None,
           f"recusa {host}", porque)


# ── O que deve continuar passando ────────────────────────────────────────
print("\n— o que é uso legítimo —")
url = main._construir_url_db(main.ConexaoDB(
    tipo="postgres", host="8.8.8.8", banco="cobranca", usuario="u", senha="p"))
checar(url.startswith("postgresql+psycopg://"), "endereço público é aceito")
checar("sslmode=require" in url, "e continua exigindo TLS")

checar(recusa(tipo="sheets", host=None) is None,
       "Google Sheets não tem host e não é barrado")


# ── SQL Server tem caminho próprio e não pode escapar ────────────────────
print("\n— SQL Server conecta por fora do construtor de URL —")
try:
    main._sqlserver_connect(main.ConexaoDB(tipo="sqlserver", host="10.0.0.9", banco="d"))
    checar(False, "SQL Server também valida o destino", "passou direto")
except HTTPException as e:
    checar("interna" in e.detail, "SQL Server também valida o destino", e.detail[:40])
except Exception as e:
    checar(False, "SQL Server também valida o destino",
           f"erro inesperado: {type(e).__name__}")


# ── Desenvolvimento local segue livre ────────────────────────────────────
print("\n— desenvolvimento local —")
supabase = os.environ.pop("SUPABASE_URL")
try:
    url = main._construir_url_db(main.ConexaoDB(
        tipo="postgres", host="localhost", banco="d", usuario="u", senha="p"))
    checar("localhost" in url, "local conecta no Postgres da própria máquina",
           "quem está programando não pode ser barrado")
    checar(main._construir_url_db(main.ConexaoDB(tipo="sqlite", banco="teste.db"))
           == "sqlite:///teste.db", "e SQLite local segue funcionando")
finally:
    os.environ["SUPABASE_URL"] = supabase


print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
