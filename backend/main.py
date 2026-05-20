import asyncio
import io
import json
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

import pandas as pd
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Security
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
    _scheduler.start()

    garantir_admin()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer          = HTTPBearer()
bearer_opcional = HTTPBearer(auto_error=False)


def _usuario_do_token(credentials) -> tuple:
    """Extrai (usuario_id, usuario_email) do JWT, ou (None, None) se sem token."""
    if not credentials:
        return None, None
    try:
        payload = validar_token(credentials.credentials)
        return payload.get("sub"), payload.get("email")
    except ValueError:
        return None, None


class FeedbackIn(BaseModel):
    cpf: str
    pagou: bool
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[date] = None
    empresa: Optional[str] = None


class ConexaoDB(BaseModel):
    tipo: str                          # postgres | mysql | sqlserver | sqlite
    host: Optional[str] = None
    porta: Optional[int] = None
    banco: Optional[str] = None
    usuario: Optional[str] = None
    senha: Optional[str] = None
    query: str
    nome_fonte: Optional[str] = "consulta_db"
    mapeamento: Optional[dict] = None  # {campo_mizan: coluna_banco}



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
def auth_login(body: LoginIn):
    usuario = buscar_usuario(body.email)
    if not usuario or not usuario.get("ativo"):
        raise HTTPException(status_code=401, detail="E-mail não encontrado.")
    if not verificar_senha(body.senha, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Senha incorreta.")
    token = criar_token({"sub": usuario["id"], "email": usuario["email"],
                         "nome": usuario["nome"], "role": usuario["role"]})
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
        novo = criar_usuario(body.email, body.nome, body.senha, body.role)
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
def auth_esqueci_senha(body: EsqueciSenhaIn):
    from email_utils import email_redefinir_senha
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://mizan-sand.vercel.app")
    token = criar_reset_token(body.email)
    if token:
        usuario = buscar_usuario(body.email)
        nome = usuario.get("nome", "usuário") if usuario else "usuário"
        link = f"{FRONTEND_URL}/redefinir-senha?token={token}"
        email_redefinir_senha(body.email, nome, link)
    return {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá as instruções em breve."}

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
    usuario_id, _ = _usuario_do_token(credentials)
    try:
        db = get_db()
        q = db.table("carteiras").select("id, nome_arquivo, created_at, total_devedores, valor_face, valor_esperado, score_medio")
        if usuario_id:
            q = q.eq("usuario_id", usuario_id)
        res = q.order("created_at", desc=True).limit(50).execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/carteiras/{carteira_id}")
def carregar_carteira(carteira_id: str):
    db = get_db()

    cart_res = db.table("carteiras").select("*").eq("id", carteira_id).execute()
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

    uid, uemail = _usuario_do_token(credentials)
    return _analisar_df(df, file.filename, _usuario_id=uid, _usuario_email=uemail)


def _construir_url_db(conn: ConexaoDB) -> str:
    """Monta a connection string do SQLAlchemy a partir dos parâmetros."""
    host  = conn.host or "localhost"
    banco = conn.banco or ""
    user  = conn.usuario or ""
    senha = conn.senha or ""
    if conn.tipo == "postgres":
        porta = conn.porta or 5432
        return f"postgresql+psycopg://{user}:{senha}@{host}:{porta}/{banco}"
    if conn.tipo == "mysql":
        porta = conn.porta or 3306
        return f"mysql+pymysql://{user}:{senha}@{host}:{porta}/{banco}"
    if conn.tipo == "sqlserver":
        porta = conn.porta or 1433
        driver = "ODBC+Driver+17+for+SQL+Server"
        return f"mssql+pyodbc://{user}:{senha}@{host}:{porta}/{banco}?driver={driver}"
    if conn.tipo == "sqlite":
        return f"sqlite:///{conn.banco}"
    raise ValueError(f"Tipo de banco não suportado: {conn.tipo}")


def _analisar_df(df: pd.DataFrame, nome_fonte: str, _usuario_id: str = None, _usuario_email: str = None) -> dict:
    """Executa o pipeline de scoring em um DataFrame já carregado e persiste no Supabase."""
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
        devedor = {"rank": rank,
                   "score_recuperabilidade": float(row["score_recuperabilidade"]),
                   "perfil_cluster": row["perfil_cluster"],
                   "valor_esperado_recuperacao": float(row["valor_esperado_recuperacao"])}
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
        cart_res = db.table("carteiras").insert(cart_row).execute()
        carteira_id = cart_res.data[0]["id"]

        def _py(val):
            if val is None: return None
            if hasattr(val, "item"): return val.item()
            return val

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
        for i in range(0, len(predicoes_rows), 100):
            db.table("predicoes").insert(predicoes_rows[i:i+100]).execute()
    except Exception as _e:
        print(f"[Supabase] Erro ao salvar: {_e}")

    # Opção A: se o arquivo/query trouxer coluna 'pagou', registra feedbacks automaticamente
    n_feedbacks_auto = 0
    if "pagou" in df.columns:
        try:
            db_fb = get_db()
            fb_rows = []
            for _, row in df.iterrows():
                p = row.get("pagou")
                if p is None or (isinstance(p, float) and pd.isna(p)):
                    continue
                if isinstance(p, str):
                    pagou = p.strip().lower() in ("true", "1", "sim", "s", "yes", "verdadeiro")
                else:
                    pagou = bool(p)
                vr = row.get("valor_recuperado")
                fb_rows.append({
                    "cpf": str(row["cpf"]),
                    "pagou": pagou,
                    "valor_recuperado": float(vr) if vr is not None and not pd.isna(vr) else 0.0,
                })
            if fb_rows:
                for i in range(0, len(fb_rows), 100):
                    db_fb.table("feedbacks").insert(fb_rows[i:i+100]).execute()
                n_feedbacks_auto = len(fb_rows)
                print(f"[Auto-feedback] {n_feedbacks_auto} feedbacks registrados automaticamente")
        except Exception as _fe:
            print(f"[Auto-feedback] Erro: {_fe}")

    resumo["feedbacks_registrados_automaticamente"] = n_feedbacks_auto

    return {"resumo": resumo, "distribuicao_aging": aging_dist,
            "distribuicao_cluster": cluster_dist, "top10_prioritarios": devedores[:10],
            "ranking_completo": devedores}


@app.post("/testar-db")
async def testar_db(conn: ConexaoDB):
    """Testa conexão, executa query limitada e retorna colunas + preview + mapeamento sugerido."""
    q = conn.query.strip()
    if not q.lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Apenas consultas SELECT são permitidas.")

    try:
        from sqlalchemy import create_engine, text
        url = _construir_url_db(conn)
        engine = create_engine(url, connect_args={"connect_timeout": 10} if conn.tipo in ("postgres", "mysql") else {})
        with engine.connect() as connection:
            if conn.tipo == "sqlserver":
                preview_q = f"SELECT TOP 5 * FROM ({q}) AS _mizan_preview"
            else:
                preview_q = f"SELECT * FROM ({q}) AS _mizan_preview LIMIT 5"
            try:
                df_preview = pd.read_sql(text(preview_q), connection)
            except Exception:
                df_preview = pd.read_sql(text(q), connection).head(5)
        engine.dispose()
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
    q = conn.query.strip()
    if not q.lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Apenas consultas SELECT são permitidas.")

    try:
        from sqlalchemy import create_engine, text
        url = _construir_url_db(conn)
        engine = create_engine(url, connect_args={"connect_timeout": 10} if conn.tipo in ("postgres", "mysql") else {})
        with engine.connect() as connection:
            df = pd.read_sql(text(q), connection)
        engine.dispose()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao conectar no banco: {e}")

    if conn.mapeamento:
        rename = {col_banco: campo for campo, col_banco in conn.mapeamento.items() if col_banco in df.columns}
        df = df.rename(columns=rename)

    uid, uemail = _usuario_do_token(credentials)
    nome = conn.nome_fonte or "consulta_db"
    return _analisar_df(df, nome, _usuario_id=uid, _usuario_email=uemail)


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
async def performance():
    """Métricas de acurácia do modelo baseadas nos feedbacks reais recebidos."""
    db = get_db()

    fb_res = db.table("feedbacks").select("pagou, predicao_id").execute()
    feedbacks = fb_res.data

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
