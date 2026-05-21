import asyncio
import io
import json
import os
import time as _time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

import pandas as pd
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Security, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from db import get_db
from model.score import score_carteira, _cache as _score_cache
from auth import (
    criar_token, validar_token,
    buscar_usuario, criar_usuario, listar_usuarios, alterar_senha,
    verificar_senha, toggle_usuario_ativo, alterar_role, garantir_admin,
    criar_reset_token, redefinir_senha_com_token,
)

load_dotenv()

_scheduler: BackgroundScheduler | None = None

_auto_sync_estado: dict = {
    "ultima_execucao":  None,
    "ultimo_resultado": None,
    "n_execucoes":      0,
}

# ---------------------------------------------------------------------------
# Rate limiting de login (in-memory, 5 tentativas / 15 min por IP+email)
# ---------------------------------------------------------------------------
_tentativas_login: dict[str, list[float]] = defaultdict(list)
_RATE_JANELA = 15 * 60
_RATE_MAX    = 5


def _checar_rate_limit(chave: str) -> None:
    agora = _time.time()
    _tentativas_login[chave] = [t for t in _tentativas_login[chave] if agora - t < _RATE_JANELA]
    if len(_tentativas_login[chave]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Muitas tentativas de login. Aguarde 15 minutos.")


def _registrar_tentativa(chave: str) -> None:
    _tentativas_login[chave].append(_time.time())


def _limpar_tentativas(chave: str) -> None:
    _tentativas_login.pop(chave, None)

# ---------------------------------------------------------------------------
# Criptografia de senhas salvas
# ---------------------------------------------------------------------------
_FERNET_KEY = os.getenv("MIZAN_ENCRYPTION_KEY", "")
_fernet = None


def _get_fernet():
    global _fernet
    if not _FERNET_KEY:
        return None
    if _fernet is None:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_FERNET_KEY.encode())
    return _fernet


def _encrypt(text: str | None) -> str | None:
    if not text:
        return text
    f = _get_fernet()
    return f.encrypt(text.encode()).decode() if f else text


def _decrypt(text: str | None) -> str | None:
    if not text:
        return text
    f = _get_fernet()
    if f is None:
        return text
    try:
        return f.decrypt(text.encode()).decode()
    except Exception:
        return text  # fallback: plaintext (migração de dados antigos)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    from scheduler import verificar_e_retreinar, estado as sched_estado

    intervalo = int(os.getenv("SCHEDULER_INTERVALO_HORAS", 24))
    min_fb    = int(os.getenv("SCHEDULER_MIN_FEEDBACKS", 30))

    sched_estado["ativo"]                     = True
    sched_estado["intervalo_horas"]           = intervalo
    sched_estado["min_feedbacks_para_treino"] = min_fb

    from db_sync import sincronizar as db_sync_sincronizar

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        verificar_e_retreinar,
        IntervalTrigger(hours=intervalo),
        kwargs={"min_feedbacks": min_fb},
        id="auto_retrain",
        replace_existing=True,
    )
    _scheduler.add_job(
        db_sync_sincronizar,
        IntervalTrigger(hours=intervalo),
        id="db_sync",
        replace_existing=True,
    )
    _scheduler.add_job(
        _auto_sync_todas_conexoes,
        IntervalTrigger(hours=intervalo),
        id="auto_sync_conexoes",
        replace_existing=True,
    )
    _scheduler.start()

    garantir_admin()

    # Garante que o modelo existe e é compatível; gera com dados sintéticos se necessário
    try:
        from model.score import _carregar_modelos
        _carregar_modelos()
        print("[Model] Modelos carregados com sucesso")
    except FileNotFoundError:
        print("[Model] Modelos não encontrados — gerando modelo inicial com dados sintéticos...")
        from model.score import _cache as _score_cache
        _score_cache.clear()
        from model.train import treinar_sintetico
        treinar_sintetico()
        print("[Model] Modelo inicial gerado.")

    job = _scheduler.get_job("auto_retrain")
    if job and job.next_run_time:
        sched_estado["proxima_verificacao"] = job.next_run_time.isoformat()

    print(f"[Scheduler] Iniciado — verificação a cada {intervalo}h | mínimo {min_fb} feedbacks")
    yield

    _scheduler.shutdown(wait=False)
    sched_estado["ativo"] = False
    print("[Scheduler] Encerrado")


def _get_versao_ativa() -> str:
    """Lê a versão ativa do modelo em versions.json. Retorna 'v1_inicial' se não existir."""
    try:
        from model.retrain import _carregar_versoes
        return _carregar_versoes().get("versao_ativa", "v1_inicial")
    except Exception:
        return "v1_inicial"


COLUNAS_OBRIGATORIAS = ["cpf", "valor_divida", "dias_em_atraso"]

COLUNAS_COM_DEFAULT = {
    "nome":           "Desconhecido",
    "produto":        "pessoal",
    "status":         "inadimplente",
    "uf":             "SP",
    "renda_estimada": 0,
}

CAMPO_ALIASES: dict = {
    "cpf":            ["cpf", "documento", "doc", "cnpj", "nr_cpf", "num_cpf", "id_cliente",
                       "cod_cliente", "identificacao", "nr_documento", "cpf_cnpj"],
    "nome":           ["nome", "name", "cliente", "devedor", "razao_social", "nom_cliente",
                       "nm_cliente", "denominacao", "nome_devedor", "ds_nome", "nome_cliente"],
    "produto":        ["produto", "tipo", "tipo_divida", "categoria", "tipo_produto",
                       "contrato", "modalidade", "ds_produto", "tp_divida", "tp_produto"],
    "status":         ["status", "situacao", "situacao_contrato", "estado_contrato",
                       "st_contrato", "ds_status", "fl_status", "situacao_divida"],
    "uf":             ["uf", "estado", "sg_estado", "sig_uf", "uf_cliente",
                       "estado_uf", "ds_uf", "nm_uf"],
    "valor_divida":   ["valor_divida", "valor", "saldo", "saldo_devedor", "divida", "montante",
                       "valor_total", "vlr_divida", "vl_divida", "saldo_em_aberto",
                       "valor_saldo", "vl_saldo", "vl_devedor"],
    "renda_estimada": ["renda_estimada", "renda", "salario", "renda_mensal", "vlr_renda",
                       "rendimento", "vl_renda", "ds_renda", "nm_renda"],
    "dias_em_atraso": ["dias_em_atraso", "dias", "atraso", "dias_atraso", "dias_vencido",
                       "qtd_dias", "nr_dias_atraso", "prazo_atraso", "qt_dias_atraso",
                       "nr_dias", "dias_inadimplencia"],
}


def _auto_mapear_colunas(colunas: list) -> dict:
    """Mapeia automaticamente colunas do banco externo para campos Mizan (case-insensitive)."""
    colunas_norm = {c.lower().replace(" ", "_"): c for c in colunas}
    mapeamento: dict = {}
    for campo, aliases in CAMPO_ALIASES.items():
        for alias in aliases:
            if alias in colunas_norm:
                mapeamento[campo] = colunas_norm[alias]
                break
        if campo not in mapeamento:
            for alias in aliases:
                matches = [orig for norm, orig in colunas_norm.items() if alias in norm]
                if len(matches) == 1:
                    mapeamento[campo] = matches[0]
                    break
    return mapeamento

app = FastAPI(
    title="Mizan API",
    description="Plataforma de análise de carteira de crédito com IA",
    version="0.3.0",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = [
    "https://mizan-sand.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer          = HTTPBearer()
bearer_opcional = HTTPBearer(auto_error=False)


def _usuario_do_token(credentials) -> tuple:
    """Extrai (usuario_id, usuario_email, empresa_id) do JWT, ou (None, None, None) se sem token."""
    if not credentials:
        return None, None, None
    try:
        payload = validar_token(credentials.credentials)
        return payload.get("sub"), payload.get("email"), payload.get("empresa_id", "")
    except ValueError:
        return None, None, None


class FeedbackIn(BaseModel):
    cpf: str
    pagou: bool
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[date] = None
    empresa: Optional[str] = None


class ConexaoDB(BaseModel):
    tipo: str   # postgres | mysql | mariadb | sqlserver | oracle | sqlite | sheets
    host: Optional[str] = None
    porta: Optional[int] = None
    banco: Optional[str] = None
    usuario: Optional[str] = None
    senha: Optional[str] = None
    instance_name: Optional[str] = None   # SQL Server named instance
    service_name: Optional[str] = None    # Oracle service name
    sheets_id: Optional[str] = None       # Google Sheets spreadsheet ID
    sheets_aba: Optional[str] = None      # Nome da aba (default: primeira)
    sheets_credenciais: Optional[dict] = None  # service account JSON
    query: Optional[str] = None
    nome_fonte: Optional[str] = "consulta_db"
    mapeamento: Optional[dict] = None  # {campo_mizan: coluna_banco}
    conexao_id: Optional[str] = None  # ID de conexão salva — senha buscada no servidor


def _resolver_credenciais(conn: ConexaoDB) -> None:
    """Se conexao_id está presente e senha está vazia, busca e decripta do banco."""
    if not conn.conexao_id or conn.senha:
        return
    try:
        res = get_db().table("conexoes_db").select("senha").eq("id", conn.conexao_id).execute()
        if res.data and res.data[0].get("senha"):
            conn.senha = _decrypt(res.data[0]["senha"])
    except Exception:
        pass


_MIZAN_PROJECT_ID = "qbdxdtdxujluklyrtmjx"
_MIZAN_TABELAS_INTERNAS = {"predicoes", "carteiras", "feedbacks", "conexoes_db", "usuarios", "bandit_estado", "api_keys", "contatos"}

def _bloquear_autoconexao(conn: ConexaoDB) -> None:
    """Bloqueia consultas às tabelas internas do Mizan para evitar loop de duplicação.

    Permite conectar ao mesmo Supabase desde que a query não acesse tabelas internas.
    """
    host = (conn.host or "").lower()
    user = (conn.usuario or "").lower()
    if _MIZAN_PROJECT_ID not in host and _MIZAN_PROJECT_ID not in user:
        return  # banco externo diferente — sem restrição

    # É o Supabase do Mizan — verifica se a query acessa tabelas internas
    query_lower = (conn.query or "").lower()
    for tabela in _MIZAN_TABELAS_INTERNAS:
        if tabela in query_lower:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Consulta bloqueada: a tabela '{tabela}' é interna do Mizan. "
                    "Use uma tabela própria de origem (ex: 'minha_carteira', 'clientes') "
                    "para importar seus devedores. Tabelas internas bloqueadas: "
                    + ", ".join(sorted(_MIZAN_TABELAS_INTERNAS))
                ),
            )
    # Também bloqueia a tabela 'devedores' que causou o loop histórico
    if "devedores" in query_lower:
        raise HTTPException(
            status_code=400,
            detail=(
                "Consulta bloqueada: a tabela 'devedores' neste Supabase acumula dados "
                "de análises anteriores e causaria duplicação. "
                "Crie uma nova tabela de origem (ex: 'clientes', 'carteira_fonte') e "
                "importe seus dados lá."
            ),
        )



def _exigir_comando(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    if payload.get("role") != "comando":
        raise HTTPException(status_code=403, detail="Acesso restrito ao painel COMANDO.")
    return payload


@app.get("/comando/visao-geral")
def comando_visao_geral(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    db = get_db()

    _VAZIO = {"empresas": [], "totais": {"total_empresas": 0, "total_devedores": 0, "valor_face_total": 0, "valor_recuperado_real": 0, "n_suspeitas": 0}}

    try:
        cart_res = db.table("carteiras").select(
            "id, empresa_id, usuario_email, total_devedores, valor_face, valor_esperado, score_medio, created_at"
        ).execute()
    except Exception:
        # colunas empresa_id/usuario_email ainda não existem — fallback sem agrupamento por empresa
        try:
            cart_res = db.table("carteiras").select(
                "id, total_devedores, valor_face, valor_esperado, score_medio, created_at"
            ).execute()
        except Exception:
            return _VAZIO

    if not cart_res.data:
        return _VAZIO

    empresas: dict = {}
    cart_id_to_empresa: dict = {}

    for c in cart_res.data:
        eid = c.get("empresa_id") or c.get("usuario_email") or "sem_empresa"
        cart_id_to_empresa[c["id"]] = eid
        if eid not in empresas:
            empresas[eid] = {
                "empresa_id": eid,
                "usuario_email": c.get("usuario_email") or "",
                "total_carteiras": 0, "total_devedores": 0,
                "valor_face_total": 0.0, "valor_esperado_total": 0.0,
                "_scores": [], "n_feedbacks": 0, "n_pagamentos": 0,
                "valor_recuperado_real": 0.0, "ultima_atividade": None,
            }
        e = empresas[eid]
        e["total_carteiras"]      += 1
        e["total_devedores"]      += int(c.get("total_devedores") or 0)
        e["valor_face_total"]     += float(c.get("valor_face") or 0)
        e["valor_esperado_total"] += float(c.get("valor_esperado") or 0)
        if c.get("score_medio"):
            e["_scores"].append(float(c["score_medio"]))
        ca = c.get("created_at")
        if ca and (e["ultima_atividade"] is None or ca > e["ultima_atividade"]):
            e["ultima_atividade"] = ca

    try:
        fb_res = db.table("feedbacks").select("predicao_id, pagou, valor_recuperado").execute()
        fb_data = fb_res.data or []
    except Exception:
        try:
            fb_res = db.table("feedbacks").select("predicao_id, pagou").execute()
            fb_data = fb_res.data or []
        except Exception:
            fb_data = []

    pred_ids = [f["predicao_id"] for f in fb_data if f.get("predicao_id")]

    if pred_ids:
        pred_to_cart: dict = {}
        try:
            for i in range(0, len(pred_ids), 100):
                pr = db.table("predicoes").select("id, carteira_id").in_("id", pred_ids[i:i+100]).execute()
                for p in (pr.data or []):
                    pred_to_cart[p["id"]] = p.get("carteira_id")
        except Exception:
            pred_to_cart = {}
        for f in fb_data:
            pid = f.get("predicao_id")
            if not pid or pid not in pred_to_cart:
                continue
            eid = cart_id_to_empresa.get(pred_to_cart[pid])
            if not eid or eid not in empresas:
                continue
            e = empresas[eid]
            e["n_feedbacks"] += 1
            if f.get("pagou"):
                e["n_pagamentos"] += 1
                e["valor_recuperado_real"] += float(f.get("valor_recuperado") or 0)

    result = []
    for e in empresas.values():
        vf = e["valor_face_total"]
        vr = e["valor_recuperado_real"]
        td = e["total_devedores"]
        taxa_fb = round(e["n_feedbacks"] / td * 100, 1) if td > 0 else 0
        result.append({
            "empresa_id":            e["empresa_id"],
            "usuario_email":         e["usuario_email"],
            "total_carteiras":       e["total_carteiras"],
            "total_devedores":       td,
            "valor_face_total":      round(vf, 2),
            "valor_esperado_total":  round(e["valor_esperado_total"], 2),
            "score_medio":           round(sum(e["_scores"]) / len(e["_scores"]), 1) if e["_scores"] else None,
            "n_feedbacks":           e["n_feedbacks"],
            "n_pagamentos":          e["n_pagamentos"],
            "valor_recuperado_real": round(vr, 2),
            "taxa_recuperacao_real": round(vr / vf * 100, 2) if vf > 0 else 0,
            "taxa_feedback":         taxa_fb,
            "flag_suspeita":         td >= 50 and taxa_fb < 5,
            "ultima_atividade":      e["ultima_atividade"],
        })

    result.sort(key=lambda x: x["valor_face_total"], reverse=True)

    totais = {
        "total_empresas":        len(result),
        "total_devedores":       sum(r["total_devedores"] for r in result),
        "valor_face_total":      round(sum(r["valor_face_total"] for r in result), 2),
        "valor_recuperado_real": round(sum(r["valor_recuperado_real"] for r in result), 2),
        "n_suspeitas":           sum(1 for r in result if r["flag_suspeita"]),
    }
    return {"empresas": result, "totais": totais}


@app.get("/comando/carteiras")
def comando_carteiras(
    empresa_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    _exigir_comando(credentials)
    db = get_db()
    try:
        q = db.table("carteiras").select(
            "id, empresa_id, usuario_email, nome_arquivo, total_devedores, valor_face, valor_esperado, score_medio, created_at, updated_at, modelo_versao"
        )
        if empresa_id:
            q = q.eq("empresa_id", empresa_id)
        res = q.order("created_at", desc=True).limit(200).execute()
        return res.data or []
    except Exception:
        q = db.table("carteiras").select(
            "id, nome_arquivo, total_devedores, valor_face, valor_esperado, score_medio, created_at, modelo_versao"
        )
        res = q.order("created_at", desc=True).limit(200).execute()
        return res.data or []


def _calcular_oferta(score: float, valor_divida: float) -> dict:
    score = float(score or 0)
    valor = float(valor_divida or 0)
    if score >= 75:
        desc, parcelas, estrategia = 0,  3,  "Cobrança padrão — sem desconto necessário"
    elif score >= 50:
        desc, parcelas, estrategia = 15, 6,  "Desconto de 15% + parcelamento em até 6x"
    elif score >= 30:
        desc, parcelas, estrategia = 35, 12, "Desconto de 35% + parcelamento em até 12x"
    else:
        desc, parcelas, estrategia = 55, 24, "Proposta de quitação com 55% de desconto"
    return {
        "desconto_sugerido_pct": desc,
        "valor_proposta":        round(valor * (1 - desc / 100), 2),
        "parcelas_max":          parcelas,
        "estrategia_oferta":     estrategia,
    }


def _aging_label(dias: int) -> str:
    if dias < 30:
        return "0-29 dias"
    if dias < 60:
        return "30-59 dias"
    if dias < 90:
        return "60-89 dias"
    if dias < 180:
        return "90-179 dias"
    return "180+ dias"


def _validar_api_key(credentials: HTTPAuthorizationCredentials) -> dict:
    """Aceita JWT do frontend OU api_key legada do Supabase."""
    token = credentials.credentials

    # Tenta JWT primeiro
    try:
        payload = validar_token(token)
        return {"empresa_nome": payload.get("nome", ""), "role": payload.get("role", "operador"), "jwt": payload}
    except ValueError:
        pass

    # Fallback: api_key legada no Supabase
    db = get_db()
    res = (
        db.table("api_keys")
        .select("*")
        .eq("api_key", token)
        .eq("ativa", True)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=401, detail="Não autorizado. Faça login ou use uma API key válida.")
    return res.data[0]

def _exigir_admin(credentials: HTTPAuthorizationCredentials):
    info = _validar_api_key(credentials)
    role = info.get("role") or info.get("jwt", {}).get("role", "")
    if role not in ("admin",) and not info.get("api_key"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return info


# ── Modelos de auth ───────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    senha: str

class RegistrarIn(BaseModel):
    email: str
    nome:  str
    senha: str
    role:  str = "operador"

class AlterarSenhaIn(BaseModel):
    senha_atual: str
    nova_senha:  str


# ── Endpoints de autenticação ─────────────────────────────────

@app.post("/auth/login")
def auth_login(body: LoginIn, request: Request):
    chave = f"{request.client.host}:{body.email}"
    _checar_rate_limit(chave)
    usuario = buscar_usuario(body.email)
    senha_ok = bool(usuario and usuario.get("ativo") and verificar_senha(body.senha, usuario.get("senha_hash", "")))
    if not senha_ok:
        _registrar_tentativa(chave)
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    _limpar_tentativas(chave)
    token = criar_token({"sub": usuario["id"], "email": usuario["email"],
                         "nome": usuario["nome"], "role": usuario["role"],
                         "empresa_id": usuario.get("empresa_id", "")})
    return {"token": token, "usuario": {k: v for k, v in usuario.items() if k != "senha_hash"}}

@app.get("/auth/me")
def auth_me(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
        return {"email": payload["email"], "nome": payload["nome"], "role": payload["role"]}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/auth/usuarios")
def auth_listar(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_admin(credentials)
    return listar_usuarios()

@app.post("/auth/registrar")
def auth_registrar(body: RegistrarIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_admin(credentials)
    try:
        payload = validar_token(credentials.credentials)
        empresa_id = payload.get("empresa_id", "")
        novo = criar_usuario(body.email, body.nome, body.senha, body.role, empresa_id)
        return {"ok": True, "usuario": novo}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/alterar-senha")
def auth_alterar_senha(body: AlterarSenhaIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    if not alterar_senha(payload["email"], body.senha_atual, body.nova_senha):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    return {"ok": True}


class AtivoIn(BaseModel):
    ativo: bool

class RoleIn(BaseModel):
    role: str

class ConexaoSalvarIn(BaseModel):
    nome: str
    tipo: str
    host: Optional[str] = None
    porta: Optional[int] = None
    banco: Optional[str] = None
    usuario: Optional[str] = None
    senha: Optional[str] = None
    instance_name: Optional[str] = None
    service_name: Optional[str] = None
    sheets_id: Optional[str] = None
    sheets_aba: Optional[str] = None
    query: Optional[str] = None
    mapeamento: Optional[dict] = None


class ConexaoUpdateIn(BaseModel):
    nome: Optional[str] = None
    query: Optional[str] = None
    mapeamento: Optional[dict] = None
    carteira_id: Optional[str] = None

class WebhookPagamentoIn(BaseModel):
    cpf: str
    pagou: bool
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[str] = None
    empresa: Optional[str] = None

class EsqueciSenhaIn(BaseModel):
    email: str

class RedefinirSenhaIn(BaseModel):
    token: str
    nova_senha: str

@app.patch("/auth/usuarios/{usuario_id}/ativo")
def auth_toggle_ativo(usuario_id: str, body: AtivoIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_admin(credentials)
    resultado = toggle_usuario_ativo(usuario_id, body.ativo)
    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"ok": True, "usuario": resultado}

@app.patch("/auth/usuarios/{usuario_id}/role")
def auth_alterar_role(usuario_id: str, body: RoleIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_admin(credentials)
    try:
        resultado = alterar_role(usuario_id, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"ok": True, "usuario": resultado}


@app.post("/auth/esqueci-senha")
def auth_esqueci_senha(body: EsqueciSenhaIn, background_tasks: BackgroundTasks):
    from email_utils import email_redefinir_senha
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://mizan-sand.vercel.app")
    token = criar_reset_token(body.email)
    if token:
        usuario = buscar_usuario(body.email)
        nome = usuario.get("nome", "usuário") if usuario else "usuário"
        link = f"{FRONTEND_URL}/redefinir-senha?token={token}"
        background_tasks.add_task(email_redefinir_senha, body.email, nome, link)
    return {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá as instruções em breve."}

@app.get("/conexoes")
def listar_conexoes(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    # Duas queries separadas para evitar problemas com caracteres especiais no or_()
    seen: set = set()
    rows: list = []
    if eid:
        r1 = db.table("conexoes_db").select("*").eq("empresa_id", eid).order("created_at", desc=True).execute()
        for r in (r1.data or []):
            seen.add(r["id"]); rows.append(r)
    r2 = db.table("conexoes_db").select("*").eq("usuario_id", uid).order("created_at", desc=True).execute()
    for r in (r2.data or []):
        if r["id"] not in seen:
            rows.append(r)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    for row in rows:
        row["senha"] = ""
    return rows

@app.post("/conexoes")
def salvar_conexao(body: ConexaoSalvarIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    # Filtra nulos para não enviar colunas que podem não existir na tabela
    row = {k: v for k, v in body.model_dump().items() if v is not None}
    row["usuario_id"] = payload["sub"]
    row["empresa_id"] = payload.get("empresa_id") or None
    row["senha"] = _encrypt(body.senha)  # cifra antes de armazenar
    try:
        res = db.table("conexoes_db").insert(row).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar conexão no banco: {e}")
    if not res.data:
        raise HTTPException(status_code=500, detail="Falha ao inserir conexão — verifique o schema da tabela conexoes_db no Supabase.")
    saved = res.data[0]
    saved["senha"] = ""  # não retorna a senha cifrada
    return {"ok": True, "conexao": saved}

class ContatoIn(BaseModel):
    cpf: str
    canal: str        # whatsapp | telefone | carta
    resultado: str    # contactado | sem_resposta | prometeu_pagar | pagou | nao_quis
    data_contato: Optional[str] = None
    observacao: Optional[str] = None
    valor_recuperado: Optional[float] = None
    desconto_oferecido_pct: Optional[float] = None
    acao_bandit_id: Optional[int] = None


_CONTATO_RECOMPENSA: dict = {
    "pagou":          None,  # calculado de valor_recuperado / valor_divida
    "prometeu_pagar": 0.2,
    "contactado":     0.05,
    "sem_resposta":   0.0,
    "nao_quis":       0.0,
}


@app.post("/contatos")
def registrar_contato(body: ContatoIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    row = body.model_dump()
    row["usuario_id"]   = payload["sub"]
    row["usuario_nome"] = payload.get("nome", "")
    row["empresa_id"]   = payload.get("empresa_id", "")
    res = db.table("contatos").insert(row).execute()

    # Fecha o loop do bandit: aprende com o resultado real do contato
    if body.resultado in _CONTATO_RECOMPENSA:
        try:
            rec_res = (db.table("recomendacoes").select("acao_id, contexto")
                       .eq("cpf", body.cpf).order("created_at", desc=True).limit(1).execute())
            if rec_res.data:
                acao_id  = body.acao_bandit_id if body.acao_bandit_id is not None else rec_res.data[0]["acao_id"]
                contexto = rec_res.data[0]["contexto"]
                recomp   = _CONTATO_RECOMPENSA[body.resultado]
                if recomp is None:
                    pred_r = (db.table("predicoes").select("valor_divida").eq("cpf", body.cpf)
                              .order("created_at", desc=True).limit(1).execute())
                    vd = float(pred_r.data[0].get("valor_divida") or 0) if pred_r.data else 0
                    recomp = min(1.0, float(body.valor_recuperado or 0) / vd) if vd > 0 and body.valor_recuperado else 0.5
                from model.bandit import registrar_resultado
                registrar_resultado(acao_id=acao_id, contexto=contexto, recompensa=recomp)
        except Exception as _be:
            print(f"[Bandit/Contato] {_be}")

    return {"ok": True, "contato": res.data[0]}


@app.get("/contatos/{cpf}")
def listar_contatos_cpf(cpf: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    q = db.table("contatos").select("*").eq("cpf", cpf)
    empresa_id = payload.get("empresa_id", "")
    if empresa_id:
        q = q.eq("empresa_id", empresa_id)
    res = q.order("created_at", desc=True).limit(50).execute()
    return res.data


@app.delete("/auth/me")
def deletar_conta(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """LGPD — usuário solicita exclusão da própria conta e dados."""
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    usuario_id = payload["sub"]
    db = get_db()
    db.table("contatos").delete().eq("usuario_id", usuario_id).execute()
    db.table("conexoes_db").delete().eq("usuario_id", usuario_id).execute()
    db.table("usuarios").delete().eq("id", usuario_id).execute()
    return {"ok": True, "mensagem": "Conta e dados pessoais removidos."}


@app.patch("/conexoes/{conexao_id}")
def atualizar_conexao(conexao_id: str, body: ConexaoUpdateIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Atualiza campos de uma conexão salva (mapeamento, query, etc.)."""
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    chk = db.table("conexoes_db").select("id, empresa_id, usuario_id").eq("id", conexao_id).execute()
    if not chk.data:
        return {"ok": True}
    r = chk.data[0]
    if not ((eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    db.table("conexoes_db").update(updates).eq("id", conexao_id).execute()
    return {"ok": True}


@app.delete("/conexoes/{conexao_id}")
def deletar_conexao(conexao_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    chk = db.table("conexoes_db").select("id, empresa_id, usuario_id").eq("id", conexao_id).execute()
    if not chk.data:
        return {"ok": True}
    r = chk.data[0]
    if not ((eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    db.table("conexoes_db").delete().eq("id", conexao_id).execute()
    return {"ok": True}


def _sincronizar_conexao_row(row: dict, uemail: str, uid: str, eid: str) -> dict:
    """Core de sync de uma conexão. Levanta ValueError (dados inválidos) ou Exception (falha de conexão)."""
    conexao_id = row["id"]
    senha_decriptada = _decrypt(row.get("senha"))

    conn = ConexaoDB(
        tipo=row["tipo"],
        host=row.get("host"),
        porta=row.get("porta"),
        banco=row.get("banco"),
        usuario=row.get("usuario"),
        senha=senha_decriptada,
        instance_name=row.get("instance_name"),
        service_name=row.get("service_name"),
        sheets_id=row.get("sheets_id"),
        sheets_aba=row.get("sheets_aba"),
        query=row.get("query") or "SELECT * FROM devedores",
        nome_fonte=row.get("nome") or row.get("nome_fonte") or "sync",
        mapeamento=row.get("mapeamento"),
    )

    _bloquear_autoconexao(conn)

    if conn.tipo == "sheets":
        if not conn.sheets_id:
            raise ValueError("Conexão do tipo Sheets sem sheets_id.")
        sheets_creds = row.get("sheets_credenciais")
        if sheets_creds and isinstance(sheets_creds, str):
            import json as _json
            conn.sheets_credenciais = _json.loads(sheets_creds)
        else:
            conn.sheets_credenciais = sheets_creds
        df = _ler_google_sheets(conn)
    else:
        q = (conn.query or "").strip()
        if not q.lower().startswith("select"):
            raise ValueError("A query salva não é um SELECT válido.")
        if conn.tipo == "sqlserver":
            with _sqlserver_connect(conn) as tds_conn:
                df = pd.read_sql(q, tds_conn)
        else:
            from sqlalchemy import create_engine, text
            url = _construir_url_db(conn)
            timeout_args = {"connect_timeout": 10} if conn.tipo in ("postgres", "postgresql", "mysql", "mariadb") else {}
            engine = create_engine(url, connect_args=timeout_args)
            with engine.connect() as connection:
                df = pd.read_sql(text(q), connection)
            engine.dispose()

    if conn.mapeamento:
        rename = {col_banco: campo for campo, col_banco in conn.mapeamento.items() if col_banco in df.columns}
        df = df.rename(columns=rename)

    nome = conn.nome_fonte or f"sync_{conexao_id[:8]}"

    db = get_db()
    carteira_id_existente = row.get("carteira_id")
    dados_anteriores = None
    if carteira_id_existente:
        try:
            prev = db.table("carteiras").select("total_devedores, score_medio, valor_face") \
                     .eq("id", carteira_id_existente).execute()
            if prev.data:
                dados_anteriores = prev.data[0]
        except Exception:
            pass

    resultado = _analisar_df(df, nome, _usuario_id=uid, _usuario_email=uemail, _empresa_id=eid,
                             _carteira_id_existente=carteira_id_existente)

    nova_carteira_id = resultado.get("resumo", {}).get("carteira_id")
    try:
        updates = {"ultimo_sync": datetime.utcnow().isoformat()}
        if nova_carteira_id and not carteira_id_existente:
            updates["carteira_id"] = nova_carteira_id
        db.table("conexoes_db").update(updates).eq("id", conexao_id).execute()
    except Exception:
        pass

    if uemail:
        try:
            from email_utils import email_sync_mudancas
            email_sync_mudancas(
                destinatario=uemail,
                nome_conexao=nome,
                dados_novos=resultado.get("resumo", {}),
                dados_anteriores=dados_anteriores,
                frontend_url=os.getenv("FRONTEND_URL", "https://mizan-sand.vercel.app"),
            )
        except Exception as e:
            print(f"[Sync] Aviso: falha ao enviar email: {e}")

    return resultado


def _auto_sync_todas_conexoes() -> None:
    """Job do scheduler: sincroniza todas as conexões com mapeamento configurado e envia email se mudou."""
    from datetime import timezone
    agora = datetime.now(timezone.utc).isoformat()
    _auto_sync_estado["ultima_execucao"] = agora
    _auto_sync_estado["n_execucoes"] = _auto_sync_estado.get("n_execucoes", 0) + 1

    db = get_db()
    try:
        rows = db.table("conexoes_db").select("*").execute().data
    except Exception as e:
        print(f"[AutoSync] Erro ao listar conexões: {e}")
        _auto_sync_estado["ultimo_resultado"] = {"erro": str(e), "executado_em": agora}
        return

    ativas = [r for r in rows if r.get("mapeamento") and (r.get("query") or r.get("tipo") == "sheets")]
    print(f"[AutoSync] {len(ativas)} conexões para sincronizar automaticamente")

    resultados = []
    for row in ativas:
        cid = row.get("id", "?")
        try:
            uid   = row.get("usuario_id", "")
            eid   = row.get("empresa_id", "") or ""
            uemail = ""
            try:
                u = db.table("usuarios").select("email").eq("id", uid).limit(1).execute()
                if u.data:
                    uemail = u.data[0].get("email", "")
            except Exception:
                pass

            res = _sincronizar_conexao_row(row, uemail, uid, eid)
            n = res.get("resumo", {}).get("total_devedores", 0)
            resultados.append({"conexao_id": cid, "ok": True, "n_devedores": n})
            print(f"[AutoSync] Conexão {cid} ok ({n} devedores)")
        except Exception as e:
            print(f"[AutoSync] Erro na conexão {cid}: {e}")
            resultados.append({"conexao_id": cid, "ok": False, "erro": str(e)})

    _auto_sync_estado["ultimo_resultado"] = {
        "executado_em": agora,
        "n_conexoes": len(ativas),
        "resultados": resultados,
    }
    print(f"[AutoSync] Concluído: {len(resultados)} conexões processadas")


@app.post("/conexoes/{conexao_id}/sincronizar")
async def sincronizar_conexao(conexao_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Re-lê o banco externo salvo e cria uma nova carteira com todos os devedores atuais."""
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    res = db.table("conexoes_db").select("*").eq("id", conexao_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")
    r = res.data[0]
    if not ((eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid):
        raise HTTPException(status_code=403, detail="Acesso negado.")

    uemail = payload.get("email", "")

    try:
        resultado = await asyncio.to_thread(_sincronizar_conexao_row, r, uemail, uid, eid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao conectar no banco: {e}")

    n_dev = resultado.get("resumo", {}).get("total_devedores", 0)
    return {"ok": True, "n_devedores": n_dev, "carteira": resultado}

@app.post("/auth/redefinir-senha")
def auth_redefinir_senha(body: RedefinirSenhaIn):
    if len(body.nova_senha) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")
    if not redefinir_senha_com_token(body.token, body.nova_senha):
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite um novo.")
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/carteiras")
def listar_carteiras(credentials=Security(bearer_opcional)):
    usuario_id, _, empresa_id = _usuario_do_token(credentials)
    try:
        db = get_db()
        q = db.table("carteiras").select("id, nome_arquivo, created_at, total_devedores, valor_face, valor_esperado, score_medio")
        if empresa_id:
            q = q.eq("empresa_id", empresa_id)
        elif usuario_id:
            q = q.eq("usuario_id", usuario_id)
        res = q.order("created_at", desc=True).limit(50).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/carteiras/{carteira_id}")
def carregar_carteira(carteira_id: str, credentials=Security(bearer_opcional)):
    _, _, empresa_id = _usuario_do_token(credentials)
    db = get_db()

    q = db.table("carteiras").select("*").eq("id", carteira_id)
    if empresa_id:
        q = q.eq("empresa_id", empresa_id)
    cart_res = q.execute()
    if not cart_res.data:
        raise HTTPException(status_code=404, detail="Carteira não encontrada.")

    pred_res = (
        db.table("predicoes")
        .select("*")
        .eq("carteira_id", carteira_id)
        .order("score_recuperabilidade", desc=True)
        .execute()
    )
    predicoes = pred_res.data
    if not predicoes:
        raise HTTPException(status_code=404, detail="Nenhuma predição encontrada para esta carteira.")

    # Reconstrói ranking_completo
    ranking = []
    for rank, p in enumerate(predicoes, start=1):
        d = {**p, "rank": rank}
        if d.get("valor_esperado_recuperacao") is None and d.get("valor_divida") and d.get("score_recuperabilidade"):
            d["valor_esperado_recuperacao"] = round(
                d["score_recuperabilidade"] / 100 * d["valor_divida"], 2
            )
        ranking.append(d)

    # Resumo
    total_face = sum((d.get("valor_divida") or 0) for d in ranking)
    total_ver  = sum((d.get("valor_esperado_recuperacao") or 0) for d in ranking)
    scores     = [d["score_recuperabilidade"] for d in ranking if d.get("score_recuperabilidade") is not None]
    resumo = {
        "total_devedores": len(ranking),
        "total_em_risco": round(total_face, 2),
        "score_medio": round(sum(scores) / len(scores), 1) if scores else 0,
        "valor_esperado_recuperacao_total": round(total_ver, 2),
        "taxa_recuperacao_esperada": round(total_ver / total_face * 100, 1) if total_face else 0,
    }

    # Distribuição aging
    aging_buckets: dict[str, dict] = {}
    for d in ranking:
        label = _aging_label(int(d.get("dias_em_atraso") or 0))
        b = aging_buckets.setdefault(label, {"aging": label, "total_devedores": 0, "valor_total": 0.0, "_s": []})
        b["total_devedores"] += 1
        b["valor_total"] += d.get("valor_divida") or 0
        b["_s"].append(d.get("score_recuperabilidade") or 0)

    aging_dist = []
    for b in aging_buckets.values():
        sc = b.pop("_s")
        b["score_medio"] = round(sum(sc) / len(sc), 2) if sc else 0
        b["valor_total"] = round(b["valor_total"], 2)
        aging_dist.append(b)

    # Distribuição cluster
    cluster_buckets: dict[str, dict] = {}
    for d in ranking:
        perfil = d.get("perfil_cluster") or "Desconhecido"
        b = cluster_buckets.setdefault(perfil, {"perfil_cluster": perfil, "total_devedores": 0, "valor_total": 0.0, "_s": []})
        b["total_devedores"] += 1
        b["valor_total"] += d.get("valor_divida") or 0
        b["_s"].append(d.get("score_recuperabilidade") or 0)

    cluster_dist = []
    for b in cluster_buckets.values():
        sc = b.pop("_s")
        b["score_medio"] = round(sum(sc) / len(sc), 2) if sc else 0
        b["valor_total"] = round(b["valor_total"], 2)
        cluster_dist.append(b)

    return {
        "resumo": resumo,
        "distribuicao_aging": aging_dist,
        "distribuicao_cluster": cluster_dist,
        "top10_prioritarios": ranking[:10],
        "ranking_completo": ranking,
    }


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um CSV.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao processar CSV: {e}")

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": df.columns.tolist(),
    }


@app.post("/analisar")
async def analisar(
    file: UploadFile = File(...),
    credentials=Security(bearer_opcional),
):
    nome = (file.filename or "").lower()
    if not (nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Arquivo deve ser CSV ou Excel (.xlsx / .xls).")

    contents = await file.read()
    try:
        if nome.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao ler arquivo: {e}")

    uid, uemail, eid = _usuario_do_token(credentials)
    return _analisar_df(df, file.filename, _usuario_id=uid, _usuario_email=uemail, _empresa_id=eid)


def _construir_url_db(conn: ConexaoDB) -> str:
    """Monta a connection string do SQLAlchemy a partir dos parâmetros."""
    from urllib.parse import quote_plus
    host  = conn.host or "localhost"
    banco = conn.banco or ""
    user  = quote_plus(conn.usuario or "")
    senha = quote_plus(conn.senha or "")

    if conn.tipo in ("postgres", "postgresql"):
        porta = conn.porta or 5432
        local = host in ("localhost", "127.0.0.1", "::1")
        ssl = "" if local else "?sslmode=require"
        return f"postgresql+psycopg://{user}:{senha}@{host}:{porta}/{banco}{ssl}"

    if conn.tipo in ("mysql", "mariadb"):
        porta = conn.porta or 3306
        return f"mysql+pymysql://{user}:{senha}@{host}:{porta}/{banco}"

    if conn.tipo == "oracle":
        porta = conn.porta or 1521
        dsn = conn.service_name or banco
        return f"oracle+oracledb://{user}:{senha}@{host}:{porta}/?service_name={dsn}"

    if conn.tipo == "sqlite":
        return f"sqlite:///{conn.banco}"

    raise ValueError(f"Tipo de banco não suportado: {conn.tipo}")


def _sqlserver_connect(conn: ConexaoDB):
    """Retorna conexão pytds para SQL Server (sem SQLAlchemy)."""
    import pytds
    kwargs = dict(
        server=conn.host or "localhost",
        database=conn.banco or "",
        user=conn.usuario or "",
        password=conn.senha or "",
        timeout=10,
        login_timeout=10,
    )
    if conn.instance_name:
        kwargs["instance"] = conn.instance_name
    else:
        kwargs["port"] = conn.porta or 1433
    return pytds.connect(**kwargs)


def _ler_google_sheets(conn: ConexaoDB) -> pd.DataFrame:
    """Lê uma planilha Google Sheets e retorna DataFrame."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(conn.sheets_credenciais, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(conn.sheets_id)
    ws = sh.worksheet(conn.sheets_aba) if conn.sheets_aba else sh.sheet1
    dados = ws.get_all_records()
    return pd.DataFrame(dados)


def _analisar_df(df: pd.DataFrame, nome_fonte: str, _usuario_id: str = None, _usuario_email: str = None, _empresa_id: str = None, _carteira_id_existente: str = None) -> dict:
    """Executa o pipeline de scoring em um DataFrame já carregado e persiste no Supabase."""
    # Aplica CAMPO_ALIASES para mapear colunas de qualquer fonte (CSV, Excel, DB)
    _cols_norm = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    _rename: dict = {}
    for campo, aliases in CAMPO_ALIASES.items():
        if campo not in df.columns:
            for alias in aliases:
                if alias in _cols_norm:
                    _rename[_cols_norm[alias]] = campo
                    break
    if _rename:
        df = df.rename(columns=_rename)

    from model.train import _normalizar_colunas
    df = _normalizar_colunas(df)

    # Enriquece com histórico de contatos anteriores do mesmo CPF
    try:
        cpfs = df["cpf"].astype(str).unique().tolist() if "cpf" in df.columns else []
        if cpfs:
            db_ct = get_db()
            ct_raw: list[dict] = []
            for _i in range(0, len(cpfs), 100):
                res = db_ct.table("contatos").select("cpf, resultado, created_at").in_("cpf", cpfs[_i:_i+100]).execute()
                ct_raw.extend(res.data or [])
            if ct_raw:
                ct_df = pd.DataFrame(ct_raw)
                ct_df["created_at"] = pd.to_datetime(ct_df["created_at"], utc=True, errors="coerce")
                _now = pd.Timestamp.now(tz="UTC")
                ct_agg = ct_df.groupby("cpf").agg(
                    hist_n_contatos        =("resultado", "count"),
                    hist_resultado_positivo=("resultado", lambda x: int(x.str.lower().isin(["pagamento_confirmado", "acordo_fechado"]).any())),
                    hist_dias_ultimo_contato=("created_at", lambda x: int((_now - x.dropna().max()).days) if x.dropna().any() else 9999),
                ).reset_index()
                df = df.merge(ct_agg, on="cpf", how="left")
                df["hist_n_contatos"]         = df["hist_n_contatos"].fillna(0).astype(int)
                df["hist_resultado_positivo"]  = df["hist_resultado_positivo"].fillna(0).astype(int)
                df["hist_dias_ultimo_contato"] = df["hist_dias_ultimo_contato"].fillna(9999).astype(int)
    except Exception as _ct_err:
        print(f"[Contact enrichment] {_ct_err}")

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=422,
            detail=f"Colunas obrigatórias ausentes: {faltantes}. Encontradas: {df.columns.tolist()}",
        )
    # Preenche colunas opcionais ausentes com defaults
    for col, default in COLUNAS_COM_DEFAULT.items():
        if col not in df.columns:
            df[col] = default

    try:
        resultado = score_carteira(df)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Modelos não encontrados ({e.filename}).")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {e}")

    resultado["valor_esperado_recuperacao"] = (
        resultado["score_recuperabilidade"] / 100 * resultado["valor_divida"]
    ).round(2)

    resultado_sorted = resultado.sort_values("score_recuperabilidade", ascending=False)

    devedores = []
    for rank, (_, row) in enumerate(resultado_sorted.iterrows(), start=1):
        score_val = float(row["score_recuperabilidade"])
        devedor = {"rank": rank,
                   "score_recuperabilidade": score_val,
                   "perfil_cluster": row["perfil_cluster"],
                   "valor_esperado_recuperacao": float(row["valor_esperado_recuperacao"]),
                   **_calcular_oferta(score_val, row.get("valor_divida", 0))}
        for col in df.columns:
            val = row[col]
            devedor[col] = None if pd.isna(val) else val
        devedores.append(devedor)

    total_em_risco = float(resultado["valor_divida"].sum())
    ver_total      = float(resultado["valor_esperado_recuperacao"].sum())
    media_score    = float(resultado["score_recuperabilidade"].mean().round(1))

    resultado["aging"] = resultado["dias_em_atraso"].apply(_aging_label)
    aging_dist = (resultado.groupby("aging")
        .agg(total_devedores=("valor_divida","count"), valor_total=("valor_divida","sum"), score_medio=("score_recuperabilidade","mean"))
        .round(2).reset_index().to_dict(orient="records"))

    cluster_dist = (resultado.groupby("perfil_cluster")
        .agg(total_devedores=("valor_divida","count"), valor_total=("valor_divida","sum"), score_medio=("score_recuperabilidade","mean"))
        .round(2).reset_index().to_dict(orient="records"))

    resumo = {
        "total_devedores": len(resultado),
        "total_em_risco": round(total_em_risco, 2),
        "score_medio": media_score,
        "valor_esperado_recuperacao_total": round(ver_total, 2),
        "taxa_recuperacao_esperada": round(ver_total / total_em_risco * 100, 1) if total_em_risco else 0,
    }

    try:
        db = get_db()

        def _py(val):
            if val is None: return None
            if hasattr(val, "item"): return val.item()
            return val

        if _carteira_id_existente:
            # ── Modo atualização: substitui predicoes, preserva feedbacks ──
            carteira_id = _carteira_id_existente
            pred_res = db.table("predicoes").select("id").eq("carteira_id", carteira_id).execute()
            pred_ids = [p["id"] for p in (pred_res.data or [])]
            for i in range(0, len(pred_ids), 100):
                lote = pred_ids[i:i+100]
                if lote:
                    db.table("feedbacks").update({"predicao_id": None}).in_("predicao_id", lote).execute()
            db.table("predicoes").delete().eq("carteira_id", carteira_id).execute()
            db.table("carteiras").update({
                "nome_arquivo":    nome_fonte,
                "total_devedores": resumo["total_devedores"],
                "valor_face":      resumo["total_em_risco"],
                "valor_esperado":  resumo["valor_esperado_recuperacao_total"],
                "score_medio":     resumo["score_medio"],
                "modelo_versao":   _get_versao_ativa(),
                "updated_at":      datetime.utcnow().isoformat(),
            }).eq("id", carteira_id).execute()
        else:
            # ── Modo criação: nova carteira ──
            cart_row = {
                "nome_arquivo":    nome_fonte,
                "total_devedores": resumo["total_devedores"],
                "valor_face":      resumo["total_em_risco"],
                "valor_esperado":  resumo["valor_esperado_recuperacao_total"],
                "score_medio":     resumo["score_medio"],
                "modelo_versao":   _get_versao_ativa(),
            }
            if _usuario_id:
                cart_row["usuario_id"]    = _usuario_id
                cart_row["usuario_email"] = _usuario_email
            if _empresa_id:
                cart_row["empresa_id"] = _empresa_id
            cart_res = db.table("carteiras").insert(cart_row).execute()
            carteira_id = cart_res.data[0]["id"]

        resumo["carteira_id"] = carteira_id

        predicoes_rows = [
            {"carteira_id": carteira_id, "cpf": str(d.get("cpf") or ""),
             "nome": d.get("nome"), "produto": d.get("produto"), "status": d.get("status"),
             "uf": d.get("uf"), "valor_divida": _py(d.get("valor_divida")),
             "renda_estimada": _py(d.get("renda_estimada")), "dias_em_atraso": _py(d.get("dias_em_atraso")),
             "score_recuperabilidade": _py(d.get("score_recuperabilidade")),
             "valor_esperado_recuperacao": _py(d.get("valor_esperado_recuperacao")),
             "perfil_cluster": d.get("perfil_cluster"), "cluster_id": _py(d.get("cluster_id"))}
            for d in devedores
        ]
        pred_id_map: dict[str, str] = {}
        for i in range(0, len(predicoes_rows), 100):
            res_pred = db.table("predicoes").insert(predicoes_rows[i:i+100]).execute()
            for row in (res_pred.data or []):
                if row.get("cpf") and row.get("id"):
                    pred_id_map[str(row["cpf"])] = row["id"]
    except Exception as _e:
        print(f"[Supabase] Erro ao salvar: {_e}")
        pred_id_map = {}

    # Se o arquivo trouxer coluna 'pagou', registra feedbacks automaticamente linkados às predições
    n_feedbacks_auto = 0
    if "pagou" in df.columns:
        try:
            fb_rows = []
            for _, row in df.iterrows():
                p = row.get("pagou")
                if p is None or (isinstance(p, float) and pd.isna(p)):
                    continue
                if isinstance(p, str):
                    pagou_val = p.strip().lower() in ("true", "1", "sim", "s", "yes", "verdadeiro")
                else:
                    pagou_val = bool(p)
                vr = row.get("valor_recuperado")
                cpf_str = str(row["cpf"])
                fb_row: dict = {
                    "cpf":             cpf_str,
                    "pagou":           pagou_val,
                    "valor_recuperado": float(vr) if vr is not None and not pd.isna(vr) else 0.0,
                }
                if cpf_str in pred_id_map:
                    fb_row["predicao_id"] = pred_id_map[cpf_str]
                if _usuario_id:
                    fb_row["usuario_id"] = _usuario_id
                fb_rows.append(fb_row)
            if fb_rows:
                db2 = get_db()
                for i in range(0, len(fb_rows), 100):
                    db2.table("feedbacks").insert(fb_rows[i:i+100]).execute()
                n_feedbacks_auto = len(fb_rows)
                print(f"[Auto-feedback] {n_feedbacks_auto} feedbacks registrados com predicao_id")
        except Exception as _fe:
            print(f"[Auto-feedback] Erro: {_fe}")

    resumo["feedbacks_registrados_automaticamente"] = n_feedbacks_auto

    return {"resumo": resumo, "distribuicao_aging": aging_dist,
            "distribuicao_cluster": cluster_dist, "top10_prioritarios": devedores[:10],
            "ranking_completo": devedores}


@app.post("/listar-tabelas")
async def listar_tabelas(conn: ConexaoDB):
    """Lista as tabelas disponíveis no banco externo — sem precisar escrever SQL."""
    _resolver_credenciais(conn)
    _bloquear_autoconexao(conn)
    if conn.tipo == "sheets":
        raise HTTPException(status_code=400, detail="Google Sheets não tem tabelas SQL.")
    try:
        if conn.tipo == "sqlserver":
            q = "SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE' ORDER BY table_name"
            with _sqlserver_connect(conn) as tds_conn:
                df = pd.read_sql(q, tds_conn)
            tabelas = df["table_name"].tolist()
        else:
            from sqlalchemy import create_engine, text
            url = _construir_url_db(conn)
            timeout_args = {"connect_timeout": 10} if conn.tipo in ("postgres", "postgresql", "mysql", "mariadb") else {}
            engine = create_engine(url, connect_args=timeout_args)
            with engine.connect() as connection:
                if conn.tipo in ("postgres", "postgresql"):
                    q = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
                elif conn.tipo in ("mysql", "mariadb"):
                    q = "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name"
                elif conn.tipo == "oracle":
                    q = "SELECT table_name FROM user_tables ORDER BY table_name"
                elif conn.tipo == "sqlite":
                    q = "SELECT name AS table_name FROM sqlite_master WHERE type='table' ORDER BY name"
                else:
                    raise ValueError(f"Tipo não suportado: {conn.tipo}")
                result = connection.execute(text(q))
                tabelas = [row[0] for row in result]
            engine.dispose()
        return {"ok": True, "tabelas": tabelas}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao conectar: {str(e)}")


@app.post("/testar-db")
async def testar_db(conn: ConexaoDB):
    """Testa conexão, executa query limitada e retorna colunas + preview + mapeamento sugerido."""
    _resolver_credenciais(conn)
    _bloquear_autoconexao(conn)
    try:
        if conn.tipo == "sheets":
            if not conn.sheets_id or not conn.sheets_credenciais:
                raise HTTPException(status_code=400, detail="sheets_id e sheets_credenciais são obrigatórios.")
            df_preview = _ler_google_sheets(conn).head(5)
        else:
            q = (conn.query or "").strip()
            if not q.lower().startswith("select"):
                raise HTTPException(status_code=400, detail="Apenas consultas SELECT são permitidas.")
            if conn.tipo == "sqlserver":
                preview_q = f"SELECT TOP 5 * FROM ({q}) AS _mizan_preview"
                with _sqlserver_connect(conn) as tds_conn:
                    try:
                        df_preview = pd.read_sql(preview_q, tds_conn)
                    except Exception:
                        df_preview = pd.read_sql(q, tds_conn).head(5)
            else:
                from sqlalchemy import create_engine, text
                url = _construir_url_db(conn)
                timeout_args = {"connect_timeout": 10} if conn.tipo in ("postgres", "postgresql", "mysql", "mariadb") else {}
                engine = create_engine(url, connect_args=timeout_args)
                with engine.connect() as connection:
                    if conn.tipo == "oracle":
                        preview_q = f"SELECT * FROM ({q}) WHERE ROWNUM <= 5"
                    else:
                        preview_q = f"SELECT * FROM ({q}) AS _mizan_preview LIMIT 5"
                    try:
                        df_preview = pd.read_sql(text(preview_q), connection)
                    except Exception:
                        df_preview = pd.read_sql(text(q), connection).head(5)
                engine.dispose()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao conectar: {str(e)}")

    colunas = df_preview.columns.tolist()
    mapeamento = _auto_mapear_colunas(colunas)
    preview = df_preview.head(3).fillna("").astype(str).to_dict(orient="records")

    return {
        "ok": True,
        "total_colunas": len(colunas),
        "colunas": colunas,
        "preview": preview,
        "mapeamento_sugerido": mapeamento,
        "campos_mapeados": list(mapeamento.keys()),
        "campos_faltando": [c for c in COLUNAS_OBRIGATORIAS if c not in mapeamento],
    }


@app.post("/analisar/db")
async def analisar_db(conn: ConexaoDB, credentials=Security(bearer_opcional)):
    """Analisa uma carteira carregada diretamente de um banco de dados externo."""
    _resolver_credenciais(conn)
    _bloquear_autoconexao(conn)
    try:
        if conn.tipo == "sheets":
            if not conn.sheets_id or not conn.sheets_credenciais:
                raise HTTPException(status_code=400, detail="sheets_id e sheets_credenciais são obrigatórios.")
            df = _ler_google_sheets(conn)
        else:
            q = (conn.query or "").strip()
            if not q.lower().startswith("select"):
                raise HTTPException(status_code=400, detail="Apenas consultas SELECT são permitidas.")
            if conn.tipo == "sqlserver":
                with _sqlserver_connect(conn) as tds_conn:
                    df = pd.read_sql(q, tds_conn)
            else:
                from sqlalchemy import create_engine, text
                url = _construir_url_db(conn)
                timeout_args = {"connect_timeout": 10} if conn.tipo in ("postgres", "postgresql", "mysql", "mariadb") else {}
                engine = create_engine(url, connect_args=timeout_args)
                with engine.connect() as connection:
                    df = pd.read_sql(text(q), connection)
                engine.dispose()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao conectar no banco: {e}")

    if conn.mapeamento:
        rename = {col_banco: campo for campo, col_banco in conn.mapeamento.items() if col_banco in df.columns}
        df = df.rename(columns=rename)

    uid, uemail, eid = _usuario_do_token(credentials)
    nome = conn.nome_fonte or "consulta_db"
    resultado = _analisar_df(df, nome, _usuario_id=uid, _usuario_email=uemail, _empresa_id=eid)

    # Vincula a carteira criada à conexão salva (para sincronizações futuras atualizarem no lugar)
    nova_carteira_id = resultado.get("resumo", {}).get("carteira_id")
    if conn.conexao_id and nova_carteira_id:
        try:
            get_db().table("conexoes_db").update({"carteira_id": nova_carteira_id}).eq("id", conn.conexao_id).execute()
        except Exception:
            pass

    return resultado


@app.post("/feedback")
async def receber_feedback(
    payload: FeedbackIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Endpoint para empresas parceiras enviarem resultados reais de pagamento."""
    empresa_info = _validar_api_key(credentials)

    db = get_db()

    # Busca a predição mais recente para este CPF
    pred_res = (
        db.table("predicoes")
        .select("id, score_recuperabilidade")
        .eq("cpf", payload.cpf)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    predicao_id = pred_res.data[0]["id"] if pred_res.data else None

    fb_row = {
        "cpf": payload.cpf,
        "pagou": payload.pagou,
        "valor_recuperado": payload.valor_recuperado or 0,
        "empresa": payload.empresa or empresa_info.get("empresa_nome"),
    }
    if payload.data_pagamento:
        fb_row["data_pagamento"] = payload.data_pagamento.isoformat()
    if predicao_id:
        fb_row["predicao_id"] = predicao_id

    res = db.table("feedbacks").insert(fb_row).execute()
    feedback_id = res.data[0]["id"]

    # Fecha o loop do bandit: atualiza com a recompensa real
    try:
        rec_res = (
            db.table("recomendacoes")
            .select("acao_id, contexto")
            .eq("cpf", payload.cpf)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if rec_res.data:
            ultima_rec = rec_res.data[0]
            valor_divida = float((pred_res.data[0].get("valor_divida") or 0)) if pred_res.data else 0
            if payload.pagou and valor_divida > 0:
                recompensa = min(1.0, float(payload.valor_recuperado or valor_divida) / valor_divida)
            elif payload.pagou:
                recompensa = 0.5
            else:
                recompensa = 0.0

            from model.bandit import registrar_resultado
            registrar_resultado(
                acao_id=ultima_rec["acao_id"],
                contexto=ultima_rec["contexto"],
                recompensa=recompensa,
            )
    except Exception as _be:
        print(f"[Bandit] Erro ao atualizar com feedback: {_be}")

    return {"ok": True, "feedback_id": feedback_id, "predicao_id": predicao_id}


@app.post("/webhook/pagamento")
async def webhook_pagamento(body: WebhookPagamentoIn, request: Request):
    """
    Webhook para receber pagamentos em tempo real do sistema do cliente.
    Autenticação: header X-API-Key com a api_key cadastrada no Mizan.
    Exemplo: POST /webhook/pagamento com header X-API-Key: mizan_test_xxx
    """
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="Header X-API-Key obrigatório.")

    db = get_db()
    key_res = db.table("api_keys").select("*").eq("api_key", api_key).eq("ativa", True).execute()
    if not key_res.data:
        raise HTTPException(status_code=401, detail="API key inválida ou inativa.")

    empresa = body.empresa or key_res.data[0].get("empresa_nome", "webhook")

    pred_res = (
        db.table("predicoes").select("id, score_recuperabilidade, valor_divida")
        .eq("cpf", body.cpf).order("created_at", desc=True).limit(1).execute()
    )
    predicao_id = pred_res.data[0]["id"] if pred_res.data else None

    fb_row = {
        "cpf": body.cpf,
        "pagou": body.pagou,
        "valor_recuperado": body.valor_recuperado or 0,
        "empresa": empresa,
    }
    if body.data_pagamento:
        fb_row["data_pagamento"] = body.data_pagamento
    if predicao_id:
        fb_row["predicao_id"] = predicao_id

    res = db.table("feedbacks").insert(fb_row).execute()
    feedback_id = res.data[0]["id"]

    # Atualiza o bandit
    try:
        rec_res = (
            db.table("recomendacoes").select("acao_id, contexto")
            .eq("cpf", body.cpf).order("created_at", desc=True).limit(1).execute()
        )
        if rec_res.data and pred_res.data:
            valor_divida = float(pred_res.data[0].get("valor_divida") or 0)
            if body.pagou and valor_divida > 0:
                recompensa = min(1.0, float(body.valor_recuperado or valor_divida) / valor_divida)
            elif body.pagou:
                recompensa = 0.5
            else:
                recompensa = 0.0
            from model.bandit import registrar_resultado
            registrar_resultado(
                acao_id=rec_res.data[0]["acao_id"],
                contexto=rec_res.data[0]["contexto"],
                recompensa=recompensa,
            )
    except Exception as e:
        print(f"[Webhook] Erro ao atualizar bandit: {e}")

    print(f"[Webhook] Pagamento recebido — CPF: {body.cpf}, pagou: {body.pagou}, empresa: {empresa}")
    return {"ok": True, "feedback_id": feedback_id}


@app.post("/feedback/lote")
async def feedback_lote(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Importa feedbacks em lote a partir de CSV ou Excel."""
    empresa_info = _validar_api_key(credentials)
    empresa = empresa_info.get("empresa_nome")

    nome = (file.filename or "").lower()
    contents = await file.read()
    try:
        if nome.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        elif nome.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Arquivo deve ser CSV ou Excel (.csv / .xlsx).")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao ler arquivo: {e}")

    df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]

    # Aceita aliases de coluna comuns
    if "cpf" not in df.columns:
        for alias in ["documento", "doc", "cnpj", "nr_cpf"]:
            if alias in df.columns:
                df = df.rename(columns={alias: "cpf"})
                break
    if "pagou" not in df.columns:
        for alias in ["pagamento", "pago", "status_pagamento", "situacao"]:
            if alias in df.columns:
                df = df.rename(columns={alias: "pagou"})
                break

    faltantes = [c for c in ["cpf", "pagou"] if c not in df.columns]
    if faltantes:
        raise HTTPException(status_code=422, detail=f"Colunas obrigatórias ausentes: {faltantes}. Encontradas: {df.columns.tolist()}")

    db = get_db()
    n_ok = 0
    n_erro = 0
    detalhes = []

    for idx, row in df.iterrows():
        linha = int(idx) + 2
        cpf_raw = str(row.get("cpf", "")).strip()
        cpf = cpf_raw.replace(".", "").replace("-", "").replace("/", "")

        if not cpf or len(cpf) < 3:
            detalhes.append({"linha": linha, "cpf": cpf_raw, "ok": False, "erro": "CPF inválido"})
            n_erro += 1
            continue

        p = row.get("pagou")
        if p is None or (isinstance(p, float) and pd.isna(p)):
            detalhes.append({"linha": linha, "cpf": cpf, "ok": False, "erro": "Campo 'pagou' vazio"})
            n_erro += 1
            continue
        pagou = p.strip().lower() in ("true", "1", "sim", "s", "yes", "verdadeiro") if isinstance(p, str) else bool(p)

        # valor_recuperado — aceita coluna "valor" também
        vr_raw = row.get("valor_recuperado") or row.get("valor") or 0
        try:
            valor_recuperado = float(str(vr_raw).replace(",", ".")) if vr_raw and not (isinstance(vr_raw, float) and pd.isna(vr_raw)) else 0.0
        except Exception:
            valor_recuperado = 0.0

        # data_pagamento — aceita "data" também, múltiplos formatos
        data_pag = None
        dp = row.get("data_pagamento") or row.get("data")
        if dp is not None and not (isinstance(dp, float) and pd.isna(dp)):
            try:
                if isinstance(dp, str):
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            data_pag = datetime.strptime(dp.strip(), fmt).date().isoformat()
                            break
                        except ValueError:
                            pass
                else:
                    data_pag = pd.Timestamp(dp).date().isoformat()
            except Exception:
                pass

        try:
            pred_res = (
                db.table("predicoes")
                .select("id, score_recuperabilidade, valor_divida")
                .eq("cpf", cpf)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            predicao_id = pred_res.data[0]["id"] if pred_res.data else None

            fb_row = {"cpf": cpf, "pagou": pagou, "valor_recuperado": valor_recuperado, "empresa": empresa}
            if data_pag:
                fb_row["data_pagamento"] = data_pag
            if predicao_id:
                fb_row["predicao_id"] = predicao_id

            res = db.table("feedbacks").insert(fb_row).execute()
            feedback_id = res.data[0]["id"]

            # Atualiza bandit
            try:
                rec_res = (
                    db.table("recomendacoes")
                    .select("acao_id, contexto")
                    .eq("cpf", cpf)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if rec_res.data:
                    valor_divida = float((pred_res.data[0].get("valor_divida") or 0)) if pred_res.data else 0
                    if pagou and valor_divida > 0:
                        recompensa = min(1.0, valor_recuperado / valor_divida) if valor_recuperado > 0 else 0.5
                    elif pagou:
                        recompensa = 0.5
                    else:
                        recompensa = 0.0
                    from model.bandit import registrar_resultado
                    registrar_resultado(
                        acao_id=rec_res.data[0]["acao_id"],
                        contexto=rec_res.data[0]["contexto"],
                        recompensa=recompensa,
                    )
            except Exception:
                pass

            detalhes.append({"linha": linha, "cpf": cpf, "ok": True, "feedback_id": feedback_id})
            n_ok += 1

        except Exception as e:
            detalhes.append({"linha": linha, "cpf": cpf, "ok": False, "erro": str(e)})
            n_erro += 1

    return {"total": n_ok + n_erro, "importados": n_ok, "erros": n_erro, "detalhes": detalhes}


@app.get("/performance")
async def performance(credentials=Security(bearer_opcional)):
    """Métricas de acurácia do modelo baseadas nos feedbacks reais — filtrados por empresa."""
    _, _, empresa_id = _usuario_do_token(credentials)
    db = get_db()

    # Filtra feedbacks pela empresa via carteira_id → empresa_id
    empresa_pred_ids: set | None = None
    if empresa_id:
        try:
            cart_res = db.table("carteiras").select("id").eq("empresa_id", empresa_id).execute()
            cart_ids = [c["id"] for c in (cart_res.data or [])]
            if not cart_ids:
                return {"mensagem": "Nenhum feedback recebido ainda.", "total_feedbacks": 0}
            pred_res_all: list = []
            for i in range(0, len(cart_ids), 100):
                pr = db.table("predicoes").select("id").in_("carteira_id", cart_ids[i:i+100]).execute()
                pred_res_all.extend(pr.data or [])
            empresa_pred_ids = {p["id"] for p in pred_res_all}
        except Exception:
            empresa_pred_ids = None

    fb_res = db.table("feedbacks").select("pagou, predicao_id").execute()
    feedbacks = fb_res.data

    if empresa_pred_ids is not None:
        feedbacks = [f for f in feedbacks if f.get("predicao_id") in empresa_pred_ids]

    if not feedbacks:
        return {"mensagem": "Nenhum feedback recebido ainda.", "total_feedbacks": 0}

    pred_ids = [f["predicao_id"] for f in feedbacks if f.get("predicao_id")]
    scores_map: dict[str, float] = {}

    if pred_ids:
        pred_res = (
            db.table("predicoes")
            .select("id, score_recuperabilidade")
            .in_("id", pred_ids)
            .execute()
        )
        scores_map = {p["id"]: p["score_recuperabilidade"] for p in pred_res.data}

    bands: dict[str, dict] = {
        "Alta (≥ 70)": {"total": 0, "pagou": 0, "nao_pagou": 0},
        "Média (40–69)": {"total": 0, "pagou": 0, "nao_pagou": 0},
        "Baixa (< 40)": {"total": 0, "pagou": 0, "nao_pagou": 0},
        "Sem score": {"total": 0, "pagou": 0, "nao_pagou": 0},
    }

    total_corretos = 0
    total_com_score = 0

    for fb in feedbacks:
        pid = fb.get("predicao_id")
        score = scores_map.get(pid) if pid else None
        pagou = fb["pagou"]

        if score is None:
            band = "Sem score"
        elif score >= 70:
            band = "Alta (≥ 70)"
        elif score >= 40:
            band = "Média (40–69)"
        else:
            band = "Baixa (< 40)"

        bands[band]["total"] += 1
        if pagou:
            bands[band]["pagou"] += 1
        else:
            bands[band]["nao_pagou"] += 1

        if score is not None:
            total_com_score += 1
            acertou = (score >= 50 and pagou) or (score < 50 and not pagou)
            if acertou:
                total_corretos += 1

    metricas = [
        {
            "faixa": band_name,
            "total_feedbacks": counts["total"],
            "pagaram": counts["pagou"],
            "nao_pagaram": counts["nao_pagou"],
            "taxa_pagamento": round(counts["pagou"] / counts["total"] * 100, 1),
        }
        for band_name, counts in bands.items()
        if counts["total"] > 0
    ]

    acuracia_geral = (
        round(total_corretos / total_com_score * 100, 1) if total_com_score else None
    )

    return {
        "total_feedbacks": len(feedbacks),
        "total_com_predicao_associada": len(pred_ids),
        "acuracia_geral": acuracia_geral,
        "metricas_por_faixa": metricas,
    }


@app.get("/performance/pagamentos")
async def performance_pagamentos(credentials=Security(bearer_opcional)):
    """Lista individual de quem pagou, com nome, CPF e valor recuperado."""
    _, _, empresa_id = _usuario_do_token(credentials)
    db = get_db()

    empresa_pred_ids: set | None = None
    if empresa_id:
        try:
            cart_res = db.table("carteiras").select("id").eq("empresa_id", empresa_id).execute()
            cart_ids = [c["id"] for c in (cart_res.data or [])]
            if not cart_ids:
                return []
            pred_res_all: list = []
            for i in range(0, len(cart_ids), 100):
                pr = db.table("predicoes").select("id").in_("carteira_id", cart_ids[i:i+100]).execute()
                pred_res_all.extend(pr.data or [])
            empresa_pred_ids = {p["id"] for p in pred_res_all}
        except Exception:
            empresa_pred_ids = None

    fb_res = db.table("feedbacks").select("cpf, pagou, valor_recuperado, data_pagamento, predicao_id, created_at").order("created_at", desc=True).limit(500).execute()
    feedbacks = fb_res.data or []

    if empresa_pred_ids is not None:
        feedbacks = [f for f in feedbacks if f.get("predicao_id") in empresa_pred_ids]

    if not feedbacks:
        return []

    pred_ids = [f["predicao_id"] for f in feedbacks if f.get("predicao_id")]
    pred_map: dict = {}
    if pred_ids:
        for i in range(0, len(pred_ids), 100):
            pr = db.table("predicoes").select("id, nome, cpf, valor_divida, score_recuperabilidade").in_("id", pred_ids[i:i+100]).execute()
            for p in (pr.data or []):
                pred_map[p["id"]] = p

    result = []
    for fb in feedbacks:
        pred = pred_map.get(fb.get("predicao_id") or "")
        result.append({
            "cpf":               fb.get("cpf") or (pred or {}).get("cpf", ""),
            "nome":              (pred or {}).get("nome", "—"),
            "valor_divida":      (pred or {}).get("valor_divida"),
            "score":             (pred or {}).get("score_recuperabilidade"),
            "pagou":             fb.get("pagou", False),
            "valor_recuperado":  fb.get("valor_recuperado") or 0,
            "data_pagamento":    fb.get("data_pagamento") or fb.get("created_at", "")[:10],
        })
    return result


@app.get("/admin/drift")
async def detectar_drift(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _validar_api_key(credentials)
    db = get_db()

    res = db.table("predicoes").select("score_recuperabilidade, created_at").execute()
    todas = res.data

    if len(todas) < 50:
        return {"status": "dados_insuficientes", "mensagem": "Mínimo de 50 predições necessário.", "drift_detectado": False}

    scores_todos = [float(p["score_recuperabilidade"]) for p in todas if p.get("score_recuperabilidade") is not None]

    cutoff = (datetime.now().astimezone().replace(microsecond=0) - __import__("datetime").timedelta(days=30)).isoformat()
    recentes = [p for p in todas if (p.get("created_at") or "") >= cutoff]

    if len(recentes) < 10:
        return {"status": "dados_insuficientes", "mensagem": "Menos de 10 predições nos últimos 30 dias.", "drift_detectado": False}

    scores_recentes = [float(p["score_recuperabilidade"]) for p in recentes if p.get("score_recuperabilidade") is not None]

    media_historica = round(sum(scores_todos) / len(scores_todos), 1)
    media_recente   = round(sum(scores_recentes) / len(scores_recentes), 1)
    diferenca       = round(abs(media_recente - media_historica), 1)
    drift           = diferenca > 10

    if drift:
        admin_email = os.getenv("ADMIN_EMAIL", "")
        if admin_email:
            try:
                from email_utils import email_drift
                email_drift(admin_email, media_recente, media_historica)
            except Exception as e:
                print(f"[Drift] Erro ao enviar e-mail: {e}")

    return {
        "status":            "drift_detectado" if drift else "normal",
        "drift_detectado":   drift,
        "media_historica":   media_historica,
        "media_recente_30d": media_recente,
        "diferenca":         diferenca,
        "total_predicoes":   len(scores_todos),
        "predicoes_30d":     len(scores_recentes),
        "mensagem": f"Score médio variou {diferenca} pontos nos últimos 30 dias — verifique o modelo." if drift else "Modelo estável.",
    }


@app.get("/recomendacao/{cpf}")
async def recomendacao_devedor(cpf: str):
    """
    Retorna a melhor abordagem de cobrança para o CPF via LinUCB.
    Salva a recomendação no Supabase para fechar o loop de aprendizado via POST /feedback.
    Não requer autenticação — acessível pelo frontend.
    """
    db = get_db()

    pred_res = (
        db.table("predicoes")
        .select("cpf, nome, produto, uf, valor_divida, renda_estimada, dias_em_atraso, score_recuperabilidade, perfil_cluster, cluster_id")
        .eq("cpf", cpf)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not pred_res.data:
        raise HTTPException(status_code=404, detail=f"Nenhuma predição encontrada para CPF: {cpf}")

    pred = pred_res.data[0]
    valor_divida = float(pred.get("valor_divida") or 0)
    renda = float(pred.get("renda_estimada") or 0)
    comprometimento = valor_divida / renda if renda > 0 else 1.0

    devedor = {**pred, "comprometimento_renda": comprometimento}

    from model.bandit import recomendar as _bandit_recomendar
    rec = _bandit_recomendar(devedor)

    try:
        db.table("recomendacoes").insert({
            "cpf":      cpf,
            "acao_id":  rec["acao_id"],
            "canal":    rec["canal"],
            "oferta":   rec["oferta"],
            "score_ucb": rec["score_ucb"],
            "contexto": rec["contexto"],
        }).execute()
    except Exception as _e:
        print(f"[Bandit] Erro ao salvar recomendacao: {_e}")

    return {**rec, "cpf": cpf, "nome": pred.get("nome")}


@app.get("/admin/bandit/stats")
async def bandit_stats(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estatísticas do bandit por ação: tentativas, recompensa média, convergência."""
    _validar_api_key(credentials)
    from model.bandit import carregar_bandit
    bandit = carregar_bandit()
    total = sum(bandit.n_tentativas)
    return {
        "total_interacoes": total,
        "alpha": bandit.alpha,
        "fase": "exploração_inicial" if total == 0 else "aprendendo" if total < 50 else "calibrado",
        "acoes": bandit.stats(),
    }


@app.get("/admin/feature-importance")
async def feature_importance(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Retorna a importância de cada feature no modelo ativo — mostra o que drive o score."""
    _validar_api_key(credentials)
    from model.score import _carregar_modelos
    try:
        clf, _, meta = _carregar_modelos()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Modelo não encontrado.")

    feature_names = meta.get("feature_names", [])
    if not hasattr(clf, "feature_importances_"):
        raise HTTPException(status_code=400, detail="Modelo não suporta feature importance.")

    importances = clf.feature_importances_
    pares = sorted(zip(feature_names, importances.tolist()), key=lambda x: -x[1])

    return {
        "model_version":  meta.get("model_version", 1),
        "total_features": len(feature_names),
        "features": [
            {"nome": n, "importancia": round(v, 4), "percentual": round(v * 100, 1)}
            for n, v in pares
        ],
    }


@app.get("/admin/modelos")
async def listar_modelos(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """
    Lista todas as versões do modelo com:
    - Métricas de treino (acurácia e AUC-ROC por cross-validation)
    - Performance real (acurácia calculada com feedbacks reais recebidos enquanto essa versão era ativa)
    """
    _validar_api_key(credentials)

    # Carrega versions.json
    try:
        from model.retrain import _carregar_versoes
        versoes_meta = _carregar_versoes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar versions.json: {e}")

    versao_ativa = versoes_meta.get("versao_ativa", "v1_inicial")
    versoes_treino = {v["versao"]: v for v in versoes_meta.get("versoes", [])}

    db = get_db()

    # Busca todas as carteiras (paginado)
    cart_versao: dict[str, str] = {}
    n_carteiras: dict[str, int] = defaultdict(int)
    n_predicoes_map: dict[str, int] = defaultdict(int)
    offset = 0
    while True:
        cart_res = (
            db.table("carteiras")
            .select("id, modelo_versao, total_devedores")
            .range(offset, offset + 999)
            .execute()
        )
        for c in cart_res.data:
            v = c.get("modelo_versao") or "v1_inicial"
            cart_versao[c["id"]] = v
            n_carteiras[v] += 1
            n_predicoes_map[v] += c.get("total_devedores") or 0
        if len(cart_res.data) < 1000:
            break
        offset += 1000

    # Busca feedbacks com predicao_id (paginado)
    feedbacks: list[dict] = []
    offset = 0
    while True:
        fb_res = (
            db.table("feedbacks")
            .select("predicao_id, pagou")
            .not_.is_("predicao_id", "null")
            .range(offset, offset + 999)
            .execute()
        )
        feedbacks.extend(fb_res.data)
        if len(fb_res.data) < 1000:
            break
        offset += 1000

    # Busca predicoes para obter score e carteira_id
    pred_ids = [f["predicao_id"] for f in feedbacks if f.get("predicao_id")]
    pred_map: dict[str, dict] = {}
    for i in range(0, len(pred_ids), 500):
        res = (
            db.table("predicoes")
            .select("id, carteira_id, score_recuperabilidade")
            .in_("id", pred_ids[i: i + 500])
            .execute()
        )
        for p in res.data:
            pred_map[p["id"]] = p

    # Calcula acurácia real por versão
    acertos: dict[str, int] = defaultdict(int)
    totais: dict[str, int] = defaultdict(int)
    for fb in feedbacks:
        pred = pred_map.get(fb.get("predicao_id"))
        if not pred:
            continue
        versao = cart_versao.get(pred["carteira_id"], "v1_inicial")
        score = pred.get("score_recuperabilidade")
        pagou = fb["pagou"]
        if score is not None:
            totais[versao] += 1
            if (score >= 50 and pagou) or (score < 50 and not pagou):
                acertos[versao] += 1

    # Monta resposta por versão
    resultado = []
    for versao_id, meta in versoes_treino.items():
        n_fb = totais.get(versao_id, 0)
        resultado.append({
            "versao":                  versao_id,
            "ativa":                   versao_id == versao_ativa,
            "tipo_alvo":               meta.get("tipo_alvo", "simulado"),
            "criado_em":               meta.get("criado_em"),
            "n_amostras_treino":       meta.get("n_amostras"),
            "metricas_treino":         meta.get("metricas"),
            "n_carteiras_analisadas":  n_carteiras.get(versao_id, 0),
            "n_predicoes_feitas":      n_predicoes_map.get(versao_id, 0),
            "n_feedbacks_recebidos":   n_fb,
            "acuracia_real":           round(acertos[versao_id] / n_fb, 4) if n_fb else None,
            "promovido":               meta.get("promovido", False),
            "promovido_em":            meta.get("promovido_em"),
        })

    return {
        "versao_ativa":  versao_ativa,
        "total_versoes": len(resultado),
        "versoes":       resultado,
    }


class PromoverIn(BaseModel):
    versao: str


@app.post("/admin/retreinar")
async def admin_retreinar(
    min_feedbacks: int = 30,
    auto_promover: bool = False,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """
    Dispara o pipeline de retreinamento com dados reais de feedback.
    Requer API key válida. Promoção automática opcional via ?auto_promover=true.
    """
    _validar_api_key(credentials)

    try:
        from model.retrain import retreinar
        resultado = retreinar(min_feedbacks=min_feedbacks, auto_promover=auto_promover)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no retreinamento: {e}")

    if resultado.get("promovido"):
        _score_cache.clear()

    return resultado


@app.post("/admin/retreinar/promover")
async def admin_promover(
    payload: PromoverIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Promove uma versão específica como modelo ativo."""
    _validar_api_key(credentials)

    try:
        from model.retrain import promover_versao
        promover_versao(payload.versao)
        _score_cache.clear()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao promover: {e}")

    return {"ok": True, "versao_promovida": payload.versao}


@app.get("/admin/retreinar/status")
async def admin_status_retreinamento(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Lista versões de modelo disponíveis e a versão ativa."""
    _validar_api_key(credentials)

    from pathlib import Path
    versions_file = Path(__file__).parent / "model" / "versions.json"
    if not versions_file.exists():
        return {"versao_ativa": "v1_inicial", "versoes": [], "mensagem": "Nenhum retreinamento realizado ainda."}

    with open(versions_file, encoding="utf-8") as f:
        return json.load(f)


@app.get("/admin/scheduler/status")
async def scheduler_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estado atual do scheduler: última verificação, próxima, quantos retreinamentos automáticos."""
    _validar_api_key(credentials)
    from scheduler import estado as sched_estado
    resultado = dict(sched_estado)
    if _scheduler:
        job = _scheduler.get_job("auto_retrain")
        if job and job.next_run_time:
            resultado["proxima_verificacao"] = job.next_run_time.isoformat()
    return resultado


@app.post("/admin/scheduler/verificar")
async def scheduler_verificar_agora(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """
    Dispara verificação imediata sem aguardar o próximo intervalo.
    Útil para testar ou forçar retreinamento fora do horário programado.
    """
    _validar_api_key(credentials)
    min_fb = int(os.getenv("SCHEDULER_MIN_FEEDBACKS", 30))
    from scheduler import verificar_e_retreinar
    resultado = await asyncio.to_thread(verificar_e_retreinar, min_fb)
    return resultado


@app.get("/admin/auto-sync/status")
async def auto_sync_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estado do auto-sync de conexões: última execução, conexões sincronizadas, erros."""
    _validar_api_key(credentials)
    resultado = dict(_auto_sync_estado)
    job = _scheduler.get_job("auto_sync_conexoes") if _scheduler else None
    if job and getattr(job, "next_run_time", None):
        resultado["proxima_execucao"] = job.next_run_time.isoformat()
    return resultado


@app.post("/admin/auto-sync/executar")
async def auto_sync_executar(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Dispara sync imediato de todas as conexões sem aguardar o próximo intervalo."""
    _validar_api_key(credentials)
    await asyncio.to_thread(_auto_sync_todas_conexoes)
    return _auto_sync_estado


class DBSyncConfigIn(BaseModel):
    ativo: bool = False
    tipo: str = "postgres"
    host: Optional[str] = None
    porta: Optional[int] = None
    banco: Optional[str] = None
    usuario: Optional[str] = None
    senha: Optional[str] = None
    query: str = "SELECT cpf, pagou, valor_recuperado FROM pagamentos WHERE updated_at > :ultimo_sync"
    coluna_cpf: str = "cpf"
    coluna_pagou: str = "pagou"
    coluna_valor: str = "valor_recuperado"


@app.get("/admin/db-sync/config")
async def db_sync_get_config(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Retorna config atual da sincronização automática (senha omitida)."""
    _validar_api_key(credentials)
    from db_sync import carregar_config
    cfg = carregar_config()
    return {**cfg, "senha": "***" if cfg.get("senha") else ""}


@app.post("/admin/db-sync/config")
async def db_sync_set_config(
    payload: DBSyncConfigIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Salva ou atualiza a configuração de sincronização automática."""
    _validar_api_key(credentials)
    from db_sync import carregar_config, salvar_config
    cfg = carregar_config()
    update = payload.model_dump(exclude_none=False)
    if update.get("senha") == "***":
        update.pop("senha")
    cfg.update(update)
    salvar_config(cfg)
    return {"ok": True, "ativo": cfg["ativo"]}


@app.post("/admin/db-sync/executar")
async def db_sync_executar(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Dispara sincronização imediata com o banco externo."""
    _validar_api_key(credentials)
    from db_sync import sincronizar
    resultado = await asyncio.to_thread(sincronizar)
    return resultado


@app.get("/admin/db-sync/status")
async def db_sync_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Retorna status da última sincronização."""
    _validar_api_key(credentials)
    from db_sync import carregar_config
    cfg = carregar_config()
    return {
        "ativo": cfg["ativo"],
        "ultimo_sync": cfg["ultimo_sync"],
        "n_sincronizacoes": cfg["n_sincronizacoes"],
        "ultimo_resultado": cfg["ultimo_resultado"],
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
