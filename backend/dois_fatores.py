"""Verificação em duas etapas (2FA) com código de 6 dígitos de um app autenticador.

- TOTP do RFC 6238 (HMAC-SHA1, passo de 30 s, 6 dígitos): funciona com Google
  Authenticator, Microsoft Authenticator, Authy, 1Password etc. Implementado aqui,
  sem dependência nova; os vetores de teste do RFC estão em test_dois_fatores.py.
- O segredo fica cifrado no banco com a chave Fernet da Mizan (agente/cripto.py).
- Um código vale uma vez: guardamos o último passo usado e recusamos repetir.
- Códigos de recuperação (10, de uso único) para quem perde o celular. O banco guarda
  só o hash com sal de cada um.
- Obrigatório para os papéis de MIZAN_2FA_OBRIGATORIO (padrão: admin e comando). Com
  "0" ou "nenhum", ninguém é obrigado (interruptor de emergência). A obrigação só
  vale depois da migração (sql/migracao_seguranca_2fa.sql): sem as colunas no banco,
  ninguém é trancado do lado de fora.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

PASSO_S = 30
DIGITOS = 6
JANELA = 1                       # aceita o passo anterior e o seguinte (relógio do celular)
EMISSOR = "Mizan"
N_RECUPERACAO = 10
PENDENTE_VALIDADE_S = 15 * 60    # tempo para concluir o cadastro depois de ler o QR
DESAFIO_VALIDADE_S = 5 * 60      # tempo entre a senha certa e o código

MSG_OBRIGATORIO = ("Configure a verificação em duas etapas para continuar: "
                   "ela é obrigatória para administradores.")
MSG_SESSAO_SEM_2FA = "Sessão sem a verificação em duas etapas. Entre de novo."
MSG_SENHA_PARA_CONFIGURAR = "Por segurança, digite sua senha para configurar."
LOGIN_RECENTE_S = 15 * 60          # configurar sem pedir a senha de novo só logo depois de entrar
COLUNAS = ("totp_ativo", "totp_segredo", "totp_pendente", "totp_pendente_em",
           "totp_ativado_em", "totp_ultimo_passo", "totp_recuperacao")


# ── TOTP ─────────────────────────────────────────────────────────────────

def novo_segredo() -> str:
    """160 bits em base32, sem o "=" do fim (o formato que os apps leem)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _chave(segredo_b32: str) -> bytes:
    s = (segredo_b32 or "").strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def codigo(segredo_b32: str, passo: int, digitos: int = DIGITOS, algoritmo=hashlib.sha1) -> str:
    h = hmac.new(_chave(segredo_b32), struct.pack(">Q", passo), algoritmo).digest()
    o = h[-1] & 0x0F
    n = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digitos)
    return str(n).zfill(digitos)


def passo_de(agora: float | None = None) -> int:
    return int((time.time() if agora is None else agora) // PASSO_S)


def verificar(segredo_b32: str, informado: str, ultimo_passo: int | None = None,
              agora: float | None = None) -> int | None:
    """O passo do código, se ele vale agora e ainda não foi usado; senão None."""
    cod = "".join(ch for ch in str(informado or "") if ch.isdigit())
    if len(cod) != DIGITOS or not segredo_b32:
        return None
    atual = passo_de(agora)
    for p in range(atual - JANELA, atual + JANELA + 1):
        if ultimo_passo is not None and p <= int(ultimo_passo):
            continue                                   # código já usado (ou mais antigo que o último)
        if hmac.compare_digest(codigo(segredo_b32, p), cod):
            return p
    return None


def qr(endereco: str) -> str | None:
    """QR code do endereço otpauth:// como imagem SVG (data URI). None sem a biblioteca:
    a tela mostra a chave para digitar no app."""
    try:
        import segno
        return segno.make(endereco, error="m").svg_data_uri(scale=5, border=2, dark="#000000", light="#ffffff")
    except Exception as e:
        print(f"[2FA] QR indisponível: {type(e).__name__}")
        return None


def uri(segredo_b32: str, email: str) -> str:
    """otpauth:// que o app lê pelo QR (ou pelo link, no próprio celular)."""
    rotulo = quote(f"{EMISSOR}:{email}")
    return (f"otpauth://totp/{rotulo}?secret={segredo_b32}&issuer={quote(EMISSOR)}"
            f"&algorithm=SHA1&digits={DIGITOS}&period={PASSO_S}")


# ── códigos de recuperação ──────────────────────────────────────────────

_ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"          # sem 0/o, 1/l/i


def _normalizar_recuperacao(cod: str) -> str:
    return "".join(ch for ch in str(cod or "").lower() if ch in _ALFABETO)


def _hash_recuperacao(cod: str, sal: str) -> str:
    return hashlib.sha256((sal + _normalizar_recuperacao(cod)).encode()).hexdigest()


def novos_codigos_recuperacao(n: int = N_RECUPERACAO) -> tuple:
    """(códigos para mostrar uma vez, hashes para guardar)."""
    codigos, hashes = [], []
    for _ in range(n):
        bruto = "".join(secrets.choice(_ALFABETO) for _ in range(10))
        cod = f"{bruto[:5]}-{bruto[5:]}"
        sal = secrets.token_hex(8)
        codigos.append(cod)
        hashes.append(f"{sal}${_hash_recuperacao(cod, sal)}")
    return codigos, hashes


def usar_recuperacao(hashes: list | None, informado: str) -> list | None:
    """A lista sem o código usado, se ele confere; senão None."""
    if len(_normalizar_recuperacao(informado)) != 10:
        return None
    restantes, achou = [], False
    for h in hashes or []:
        sal, _, alvo = str(h).partition("$")
        if not achou and hmac.compare_digest(_hash_recuperacao(informado, sal), alvo):
            achou = True
            continue
        restantes.append(h)
    return restantes if achou else None


# ── segredo cifrado ─────────────────────────────────────────────────────

def cifrar(segredo: str) -> str:
    from agente import cripto
    return cripto.cifrar(segredo)


def decifrar(valor: str | None) -> str | None:
    from agente import cripto
    return cripto.decifrar(valor) if valor else None


# ── regra de quem precisa ──────────────────────────────────────────────

def papeis_obrigados() -> frozenset:
    bruto = os.getenv("MIZAN_2FA_OBRIGATORIO", "admin,comando").strip().lower()
    if bruto in ("", "0", "nenhum", "false", "nao", "não"):
        return frozenset()
    return frozenset(p.strip() for p in bruto.split(",") if p.strip())


def migrado(usuario: dict | None) -> bool:
    """As colunas do 2FA existem no cadastro (a migração rodou)?"""
    return bool(usuario) and "totp_ativo" in usuario


def ativo(usuario: dict | None) -> bool:
    return bool((usuario or {}).get("totp_ativo")) and bool((usuario or {}).get("totp_segredo"))


def obrigatorio(usuario: dict | None) -> bool:
    return migrado(usuario) and (usuario or {}).get("role") in papeis_obrigados()


def codigo_ja_usado(usuario: dict, informado: str, agora: float | None = None) -> bool:
    """O código é do app e vale agora, mas já foi usado (para a mensagem certa)."""
    segredo = decifrar(usuario.get("totp_segredo"))
    return bool(segredo) and verificar(segredo, informado, None, agora=agora) is not None


def conferir_codigo(usuario: dict, informado: str, agora: float | None = None) -> dict | None:
    """Confere um código do app OU de recuperação. Devolve o que gravar no cadastro
    (último passo usado, ou a lista de recuperação sem o código usado), ou None."""
    segredo = decifrar(usuario.get("totp_segredo"))
    p = verificar(segredo, informado, usuario.get("totp_ultimo_passo"), agora=agora) if segredo else None
    if p is not None:
        return {"totp_ultimo_passo": p}
    restantes = usar_recuperacao(usuario.get("totp_recuperacao"), informado)
    if restantes is not None:
        return {"totp_recuperacao": restantes}
    return None
