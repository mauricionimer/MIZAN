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
TOKEN_EXPIRE = 7 * 24 * 3600  # 7 dias


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

def validar_forca_senha(senha: str) -> None:
    """Garante uma política mínima de senha. Lança ValueError se fraca."""
    if not senha or len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    if senha.isdigit() or senha.isalpha():
        raise ValueError("A senha deve combinar letras e números.")


def versao_da_senha(usuario: dict) -> "str | None":
    """Impressão curta do hash da senha atual, que vai dentro do token.

    Trocar ou redefinir a senha muda o hash, e com ele esta impressão: todo
    token emitido antes deixa de valer. Sem isso, quem tivesse um token roubado
    continuava dentro por até sete dias depois de a vítima trocar a senha.
    Não revela nada da senha: é um pedaço do SHA-256 de um hash com sal.
    """
    h = (usuario or {}).get("senha_hash")
    return hashlib.sha256(h.encode()).hexdigest()[:16] if h else None


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


def _senha_do_primeiro_admin() -> tuple:
    """(senha, de_onde). Em produção nunca é uma senha conhecida.

    Antes, banco novo (ou limpo) ganhava um COMANDO com a senha fixa
    'mizan123', escrita no código e impressa no log. Agora, com SUPABASE_URL
    definido (produção), vale ADMIN_SENHA do ambiente, se for forte; sem ela,
    uma senha aleatória que ninguém vê: o acesso sai pelo "esqueci a senha".
    Só sem SUPABASE_URL (máquina de desenvolvimento) fica a senha de sempre.
    """
    if not os.getenv("SUPABASE_URL"):
        return "mizan123", "padrao_dev"
    do_ambiente = os.getenv("ADMIN_SENHA", "")
    if do_ambiente:
        try:
            validar_forca_senha(do_ambiente)
            return do_ambiente, "ambiente"
        except ValueError:
            print("[Auth] ADMIN_SENHA fraca: ignorada; criada senha aleatória.")
    return secrets.token_urlsafe(24), "aleatoria"


def garantir_admin():
    """Cria o admin padrão se a tabela estiver vazia. Chamado no startup."""
    try:
        db = _db()
        res = db.table("usuarios").select("id").limit(1).execute()
        if not res.data:
            email = os.getenv("ADMIN_EMAIL", "admin@mizan.com").strip().lower()
            senha, origem = _senha_do_primeiro_admin()
            admin = {
                "id":         secrets.token_hex(8),
                "email":      email,
                "nome":       "Administrador",
                "senha_hash": hash_senha(senha),
                "role":       "comando",
                "ativo":      True,
                "empresa_id": "",
            }
            db.table("usuarios").insert(admin).execute()
            print("\n[Auth] *** Primeiro acesso — usuário padrão criado ***")
            print(f"[Auth]     E-mail: {email}")
            if origem == "padrao_dev":
                print("[Auth]     Senha:  mizan123 (só em desenvolvimento)")
                print("[Auth]     Troque a senha após o primeiro login.\n")
            elif origem == "ambiente":
                print("[Auth]     Senha:  a de ADMIN_SENHA.\n")
            else:
                # A senha não vai para o log: o log do Render fica guardado.
                print("[Auth]     Senha aleatória (não exibida). Use \"esqueci a senha\" "
                      "ou defina ADMIN_SENHA antes do primeiro deploy.\n")
    except Exception as e:
        print(f"[Auth] Aviso: não foi possível verificar admin padrão: {e}")

def buscar_usuario(email: str) -> dict | None:
    res = _db().table("usuarios").select("*").eq("email", email.strip().lower()).limit(1).execute()
    return res.data[0] if res.data else None

def buscar_usuario_por_id(usuario_id: str) -> dict | None:
    res = _db().table("usuarios").select("*").eq("id", usuario_id).limit(1).execute()
    return res.data[0] if res.data else None

def criar_usuario(email: str, nome: str, senha: str, role: str = "operador", empresa_id: str = "") -> dict:
    email = email.strip().lower()
    validar_forca_senha(senha)
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
        # Comando é papel de plataforma e não pertence a empresa cliente. Sem
        # este caso, passar vazio não zerava nada: caía no palpite pelo domínio
        # do e-mail e o comando nascia dentro de uma empresa — exatamente o
        # estado que a regra de "não mover comando para empresa" evita.
        "empresa_id": "" if role == "comando" else (empresa_id or _empresa_do_email(email)),
    }
    db.table("usuarios").insert(novo).execute()
    return _sem_hash(novo)

def listar_usuarios(empresa_id: str = "") -> list:
    q = _db().table("usuarios").select("id, email, nome, role, ativo, empresa_id, created_at").order("created_at").limit(1000)
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
    validar_forca_senha(nova_senha)
    db.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("email", email).execute()
    return True

def criar_reset_token(email: str) -> str | None:
    """Gera token de reset de senha válido por 1 hora. Retorna None se e-mail não existe."""
    # E-mail gravado em minúsculo: "Ana@X.com" achava ninguém e o link nunca saía.
    email = (email or "").strip().lower()
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
    validar_forca_senha(nova_senha)
    db.table("usuarios").update({"senha_hash": hash_senha(nova_senha)}).eq("email", rec["email"]).execute()
    # Todos os links pedidos para este e-mail morrem juntos, não só o usado: um
    # link antigo que vazou não pode servir para trocar a senha de novo.
    db.table("reset_tokens").update({"usado": True}).eq("email", rec["email"]).execute()
    return True

ROLES_VALIDOS = ("comando", "admin", "operador")


def _ultimo_comando_ativo(db, usuario_id: str) -> bool:
    """O usuário é comando ativo e não sobraria nenhum outro depois da mudança?

    O COMANDO é o papel de plataforma: é quem cria empresas, cria usuários e
    promove modelo. Zerar os comandos ativos tranca a plataforma inteira do
    lado de fora, e não há tela para desfazer — só acesso direto ao banco.

    Antes esta trava não existia porque era impossível chegar lá: nenhuma
    rota mexia num comando. Agora que promover e rebaixar são possíveis, ela
    passa a ser necessária.
    """
    atual = db.table("usuarios").select("role, ativo").eq("id", usuario_id).limit(1).execute()
    if not atual.data:
        return False
    if atual.data[0].get("role") != "comando" or not atual.data[0].get("ativo"):
        return False
    outros = (db.table("usuarios").select("id")
              .eq("role", "comando").eq("ativo", True).neq("id", usuario_id)
              .limit(1).execute())
    return not (outros.data or [])


def toggle_usuario_ativo(usuario_id: str, ativo: bool) -> dict | None:
    db = _db()
    if not ativo and _ultimo_comando_ativo(db, usuario_id):
        raise ValueError(
            "Este é o único COMANDO ativo. Desativá-lo trancaria a plataforma: "
            "promova outro usuário a comando antes.")
    db.table("usuarios").update({"ativo": ativo}).eq("id", usuario_id).execute()
    res = db.table("usuarios").select("id, email, nome, role, ativo").eq("id", usuario_id).limit(1).execute()
    return res.data[0] if res.data else None

def alterar_role(usuario_id: str, role: str) -> dict | None:
    if role not in ROLES_VALIDOS:
        raise ValueError("Role inválido. Use 'comando', 'admin' ou 'operador'.")
    db = _db()
    if role != "comando" and _ultimo_comando_ativo(db, usuario_id):
        raise ValueError(
            "Este é o único COMANDO ativo. Rebaixá-lo trancaria a plataforma: "
            "promova outro usuário a comando antes.")
    if role == "comando":
        # Comando é papel de plataforma, não de cliente. O sistema já recusa
        # mover um comando para dentro de uma empresa; promover alguém sem
        # tirá-lo da empresa deixaria o estado que aquela regra evita.
        db.table("usuarios").update({"role": role, "empresa_id": ""}).eq("id", usuario_id).execute()
    else:
        db.table("usuarios").update({"role": role}).eq("id", usuario_id).execute()
    res = db.table("usuarios").select("id, email, nome, role, ativo").eq("id", usuario_id).limit(1).execute()
    return res.data[0] if res.data else None
