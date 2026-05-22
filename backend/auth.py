"""
Autenticação JWT para o Mizan.
Usuários armazenados no Supabase (tabela: usuarios).
JWT usando apenas built-ins Python (hmac, hashlib, base64, secrets).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SECRET_KEY   = os.getenv("JWT_SECRET", "mizan_jwt_secret_mude_em_producao_2026")
TOKEN_EXPIRE = 30 * 24 * 3600  # 30 dias


# ── JWT ─────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_dec(s: str) -> bytes:
    pad = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)

def _assinar(msg: str) -> str:
    h = hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod=hashlib.sha256)
    return _b64url(h.digest())

def criar_token(payload: dict) -> str:
    header      = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    corpo       = {**payload, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_EXPIRE}
    payload_enc = _b64url(json.dumps(corpo, ensure_ascii=False).encode())
    msg         = f"{header}.{payload_enc}"
    return f"{msg}.{_assinar(msg)}"

def validar_token(token: str) -> dict:
    try:
        partes = token.split(".")
        if len(partes) != 3:
            raise ValueError("formato inválido")
        h, p, sig = partes
        msg = f"{h}.{p}"
        if not secrets.compare_digest(sig, _assinar(msg)):
            raise ValueError("assinatura inválida")
        payload = json.loads(_b64url_dec(p))
        if payload.get("exp", 0) < time.time():
            raise ValueError("token expirado")
        return payload
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"token inválido: {e}")


# ── Senha ────────────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"

def verificar_senha(senha: str, hash_str: str) -> bool:
    try:
        salt, h_stored = hash_str.split("$", 1)
        h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
        return secrets.compare_digest(h.hex(), h_stored)
    except Exception:
        return False


# ── Usuários (Supabase) ──────────────────────────────────────────────────

def _db():
    from db import get_db
    return get_db()

def _sem_hash(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "senha_hash"}

def _empresa_do_email(email: str) -> str:
    return email.split('@')[1] if '@' in email else 'mizan_default'


def garantir_admin():
    """Cria o admin padrão se a tabela estiver vazia. Chamado no startup."""
    try:
        db = _db()
        res = db.table("usuarios").select("id").limit(1).execute()
        if not res.data:
            email = os.getenv("ADMIN_EMAIL", "admin@mizan.com")
            admin = {
                "id":         secrets.token_hex(8),
                "email":      email,
                "nome":       "Administrador",
                "senha_hash": hash_senha("mizan123"),
                "role":       "comando",
                "ativo":      True,
                "empresa_id": "",
            }
            db.table("usuarios").insert(admin).execute()
            print("\n[Auth] *** Primeiro acesso — usuário padrão criado ***")
            print(f"[Auth]     E-mail: {email}")
            print("[Auth]     Senha:  mizan123")
            print("[Auth]     Troque a senha após o primeiro login.\n")
    except Exception as e:
        print(f"[Auth] Aviso: não foi possível verificar admin padrão: {e}")

def buscar_usuario(email: str) -> dict | None:
    res = _db().table("usuarios").select("*").eq("email", email).limit(1).execute()
    return res.data[0] if res.data else None

def criar_usuario(email: str, nome: str, senha: str, role: str = "operador", empresa_id: str = "") -> dict:
    db = _db()
    if db.table("usuarios").select("id").eq("email", email).execute().data:
        raise ValueError("E-mail já cadastrado.")
    novo = {
        "id":         secrets.token_hex(8),
        "email":      email,
        "nome":       nome,
        "senha_hash": hash_senha(senha),
        "role":       role,
        "ativo":      True,
        "empresa_id": empresa_id or _empresa_do_email(email),
    }
    db.table("usuarios").insert(novo).execute()
    return _sem_hash(novo)

def listar_usuarios(empresa_id: str = "") -> list:
    q = _db().table("usuarios").select("id, email, nome, role, ativo, empresa_id, created_at").order("created_at")
    if empresa_id:
        q = q.eq("empresa_id", empresa_id)
    return q.execute().data

def alterar_senha(email: str, senha_atual: str, nova_senha: str) -> bool:
    db = _db()
    res = db.table("usuarios").select("*").eq("email", email).limit(1).execute()
    if not res.data:
        return False
    if not verificar_senha(senha_atual, res.data[0]["senha_hash"]):
        return False
    db.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("email", email).execute()
    return True

def criar_reset_token(email: str) -> str | None:
    """Gera token de reset de senha válido por 1 hora. Retorna None se e-mail não existe."""
    db = _db()
    if not db.table("usuarios").select("id").eq("email", email).execute().data:
        return None
    token = secrets.token_urlsafe(32)
    from datetime import datetime, timedelta, timezone
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    db.table("reset_tokens").insert({"token": token, "email": email, "expires_at": expires}).execute()
    return token

def redefinir_senha_com_token(token: str, nova_senha: str) -> bool:
    """Valida o token e redefine a senha. Retorna False se inválido/expirado."""
    from datetime import datetime, timezone
    db = _db()
    res = db.table("reset_tokens").select("*").eq("token", token).eq("usado", False).execute()
    if not res.data:
        return False
    rec = res.data[0]
    if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
        return False
    db.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("email", rec["email"]).execute()
    db.table("reset_tokens").update({"usado": True}).eq("token", token).execute()
    return True

def toggle_usuario_ativo(usuario_id: str, ativo: bool) -> dict | None:
    db = _db()
    db.table("usuarios").update({"ativo": ativo}).eq("id", usuario_id).execute()
    res = db.table("usuarios").select("id, email, nome, role, ativo").eq("id", usuario_id).limit(1).execute()
    return res.data[0] if res.data else None

def alterar_role(usuario_id: str, role: str) -> dict | None:
    if role not in ("admin", "operador"):
        raise ValueError("Role inválido. Use 'admin' ou 'operador'.")
    db = _db()
    atual = db.table("usuarios").select("role").eq("id", usuario_id).limit(1).execute()
    if atual.data and atual.data[0].get("role") == "comando":
        raise ValueError("Não é possível alterar a role de um usuário COMANDO.")
    db.table("usuarios").update({"role": role}).eq("id", usuario_id).execute()
    res = db.table("usuarios").select("id, email, nome, role, ativo").eq("id", usuario_id).limit(1).execute()
    return res.data[0] if res.data else None
