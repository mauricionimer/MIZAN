"""Cifra campos internos com a mesma chave Fernet da Mizan (MIZAN_ENCRYPTION_KEY).

Mesma regra de backend/main.py (_encrypt): em produção (SUPABASE_URL definida) não
grava nada em claro sem chave; em desenvolvimento, sem chave, guarda marcado como
"claro:" para não exigir chave de quem roda local. A chave nunca vai para log nem resposta.
"""
import os

_PREFIXO_CIFRA = "fernet:"
_PREFIXO_CLARO = "claro:"


def _fernet():
    chave = os.getenv("MIZAN_ENCRYPTION_KEY", "").strip()
    if not chave:
        return None
    from cryptography.fernet import Fernet
    return Fernet(chave.encode())


def cifrar(texto: str | None) -> str | None:
    if texto is None:
        return None
    f = _fernet()
    if f is None:
        if os.getenv("SUPABASE_URL"):
            raise RuntimeError("MIZAN_ENCRYPTION_KEY não configurada: nada é gravado em claro em produção.")
        return _PREFIXO_CLARO + texto
    return _PREFIXO_CIFRA + f.encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(texto: str | None) -> str | None:
    if not texto:
        return texto
    if texto.startswith(_PREFIXO_CLARO):
        return texto[len(_PREFIXO_CLARO):]
    if texto.startswith(_PREFIXO_CIFRA):
        f = _fernet()
        if f is None:
            return None                      # sem a chave, não há como ler (e não se inventa)
        try:
            return f.decrypt(texto[len(_PREFIXO_CIFRA):].encode("ascii")).decode("utf-8")
        except Exception:
            return None
    return texto
