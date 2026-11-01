"""Limite de tentativas de login (e do código de 2FA) que sobrevive a reinícios.

Antes, a contagem ficava na memória do servidor e só ia ao banco quando batia o
limite, em segundo plano: no Render gratuito, que reinicia com frequência, 4 erros +
reinício zeravam a conta. Agora cada erro vira uma linha em `login_tentativas` na hora,
e a contagem é sempre lida do banco (somada à da memória).

- A chave guardada é um HMAC (e-mail e IP não ficam em texto no banco).
- Banco fora ou tabela ausente: vale a contagem em memória, como antes. Nada é liberado
  por falha do banco.
- Linhas com mais de um dia são apagadas de vez em quando, no próprio registro.
- Tabela: sql/migracao_seguranca_2fa.sql (RLS ligado, só o backend acessa).
"""
import hashlib
import hmac
import os
import random
from datetime import datetime, timedelta, timezone

TABELA = "login_tentativas"
GUARDA_S = 24 * 3600
_avisado = {"falha": False}


def _segredo() -> bytes:
    from auth import SECRET_KEY
    return ("limite-login:" + (os.getenv("MIZAN_ENCRYPTION_KEY") or SECRET_KEY)).encode()


def chave_protegida(chave: str) -> str:
    return hmac.new(_segredo(), (chave or "").encode(), hashlib.sha256).hexdigest()[:48]


def _aviso(e: Exception) -> None:
    if not _avisado["falha"]:
        _avisado["falha"] = True
        print(f"[Login] limite no banco indisponível ({type(e).__name__}); valendo a contagem em memória")


def contar(db, chave: str, janela_s: int, agora: datetime | None = None) -> int | None:
    """Erros desta chave na janela, segundo o banco; None se o banco não respondeu."""
    agora = agora or datetime.now(timezone.utc)
    try:
        res = (db.table(TABELA).select("id", count="exact").eq("chave", chave_protegida(chave))
               .gte("criado_em", (agora - timedelta(seconds=janela_s)).isoformat()).limit(1).execute())
        return int(res.count or 0)
    except Exception as e:
        _aviso(e)
        return None


def registrar(db, chave: str, agora: datetime | None = None) -> bool:
    agora = agora or datetime.now(timezone.utc)
    try:
        db.table(TABELA).insert({"chave": chave_protegida(chave), "criado_em": agora.isoformat()}).execute()
        if random.random() < 0.05:                       # faxina ocasional, sem tarefa à parte
            db.table(TABELA).delete().lt("criado_em", (agora - timedelta(seconds=GUARDA_S)).isoformat()).execute()
        return True
    except Exception as e:
        _aviso(e)
        return False


def limpar(db, chave: str) -> None:
    try:
        db.table(TABELA).delete().eq("chave", chave_protegida(chave)).execute()
    except Exception as e:
        _aviso(e)
