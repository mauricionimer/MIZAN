import asyncio
import io
import json
import math
import os
import threading
import time as _time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pandas as pd
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Security, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from db import get_db
from model.score import score_carteira, _cache as _score_cache
from auth import (
    criar_token, validar_token,
    buscar_usuario, buscar_usuario_por_id, criar_usuario, listar_usuarios, alterar_senha,
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
    # Complementa memória com registros persistidos (sobrevive a restart)
    if len(_tentativas_login[chave]) < _RATE_MAX:
        try:
            res = get_db().table("rate_limit_login").select("tentativas").eq("chave", chave).limit(1).execute()
            if res.data:
                externas = [t for t in res.data[0].get("tentativas", []) if agora - t < _RATE_JANELA]
                _tentativas_login[chave] = list(set(_tentativas_login[chave]) | set(externas))
        except Exception:
            pass
    if len(_tentativas_login[chave]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Muitas tentativas de login. Aguarde 15 minutos.")


def _registrar_tentativa(chave: str) -> None:
    agora = _time.time()
    _tentativas_login[chave].append(agora)
    # Persiste apenas quando chega no limite (evita DB call em toda tentativa)
    if len(_tentativas_login[chave]) >= _RATE_MAX:
        import threading
        def _persist():
            try:
                get_db().table("rate_limit_login").upsert(
                    {"chave": chave, "tentativas": _tentativas_login[chave], "updated_at": agora}
                ).execute()
            except Exception:
                pass
        threading.Thread(target=_persist, daemon=True).start()


def _limpar_tentativas(chave: str) -> None:
    _tentativas_login.pop(chave, None)
    try:
        get_db().table("rate_limit_login").delete().eq("chave", chave).execute()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Cache TTL simples em memória
# ---------------------------------------------------------------------------
_cache_store: dict[str, tuple[float, object]] = {}


def _cache_get(key: str, ttl: float):
    entry = _cache_store.get(key)
    if entry and (_time.time() - entry[0]) < ttl:
        return entry[1]
    _cache_store.pop(key, None)
    return None


def _cache_set(key: str, val):
    _cache_store[key] = (_time.time(), val)


def _cache_del_prefix(prefix: str):
    for k in list(_cache_store):
        if k.startswith(prefix):
            # pop em vez de del: em threadpool outra requisição pode já ter
            # removido a mesma chave entre o list() e aqui.
            _cache_store.pop(k, None)

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
    if f is None:
        # Em desenvolvimento segue em claro, para não exigir chave de quem só
        # está rodando local. Em produção isso nunca deve acontecer — o startup
        # já barra —, e se acontecer é melhor falhar do que gravar em claro.
        if os.getenv("SUPABASE_URL"):
            raise RuntimeError(
                "Tentativa de gravar credencial sem MIZAN_ENCRYPTION_KEY configurada.")
        return text
    return f.encrypt(text.encode()).decode()


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
    from scheduler import verificar_e_retreinar, estado as sched_estado, MIN_NOVOS_PADRAO

    intervalo = int(os.getenv("SCHEDULER_INTERVALO_HORAS", 24))
    min_fb    = int(os.getenv("SCHEDULER_MIN_FEEDBACKS", MIN_NOVOS_PADRAO))
    sync_min  = int(os.getenv("SYNC_CONEXOES_INTERVALO_MIN", 15))  # default 15min

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
        IntervalTrigger(minutes=sync_min),
        id="auto_sync_conexoes",
        replace_existing=True,
    )
    _scheduler.start()

    garantir_admin()

    # Em produção (Supabase real configurado), recusa subir com segredos default.
    _is_prod = bool(os.getenv("SUPABASE_URL"))
    if _is_prod:
        from auth import SECRET_KEY as _JWT_SECRET
        if _JWT_SECRET == "mizan_jwt_secret_mude_em_producao_2026":
            raise RuntimeError("JWT_SECRET não configurado em produção. Defina a variável de ambiente JWT_SECRET.")

    # A chave de criptografia precisa da mesma trava que o JWT_SECRET. Sem ela,
    # _encrypt devolvia o texto puro e o app subia normalmente — gravando
    # usuário e senha do banco de produção do cliente em claro, sem um aviso
    # sequer. Degradar em silêncio é pior do que não subir.
    if _is_prod and not _FERNET_KEY:
        raise RuntimeError(
            "MIZAN_ENCRYPTION_KEY não configurada em produção. Sem ela as "
            "credenciais de banco dos clientes seriam gravadas em texto puro. "
            "Gere uma com: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    if _FERNET_KEY:
        try:
            from cryptography.fernet import Fernet as _Fernet
            _Fernet(_FERNET_KEY.encode())
        except Exception as _fe:
            raise RuntimeError(f"MIZAN_ENCRYPTION_KEY inválida: {_fe}")

    # Garante que o modelo existe e é compatível; gera com dados sintéticos se necessário
    try:
        from model.score import _carregar_modelos
        _carregar_modelos()
        print("[Model] Modelos carregados com sucesso")
    except FileNotFoundError:
        print("[Model] Modelos não encontrados — gerando modelo inicial com dados sintéticos...")
        _score_cache.clear()
        from model.train import treinar_sintetico
        treinar_sintetico()
        print("[Model] Modelo inicial gerado.")

    # Restaura modelo do Supabase Storage em background (não bloqueia o startup)
    import threading
    def _restaurar_modelo_bg():
        try:
            from storage_ml import download_modelos
            if download_modelos():
                _score_cache.clear()
                from model.score import _carregar_modelos
                _carregar_modelos()
                print("[Model] Modelo atualizado do Supabase Storage.")
        except Exception as _se:
            print(f"[Storage] Download em background falhou: {_se}")
    threading.Thread(target=_restaurar_modelo_bg, daemon=True).start()

    job = _scheduler.get_job("auto_retrain")
    if job and job.next_run_time:
        sched_estado["proxima_verificacao"] = job.next_run_time.isoformat()

    print(f"[Scheduler] Iniciado — verificação a cada {intervalo}h | mínimo {min_fb} feedbacks")
    yield

    _scheduler.shutdown(wait=False)
    sched_estado["ativo"] = False
    print("[Scheduler] Encerrado")


def _read_csv_auto(raw: bytes) -> pd.DataFrame:
    """Lê CSV tentando UTF-8 primeiro, depois Latin-1 (ISO-8859-1 / CP-1252)."""
    try:
        return pd.read_csv(io.BytesIO(raw), encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(raw), encoding="latin-1")


def _get_versao_ativa(empresa_id: "str | None" = None) -> str:
    """Versão do modelo que pontua esta empresa: o próprio, se ativo; senão o global."""
    if empresa_id:
        try:
            from model import modelos_empresa as _me
            if _me.tem_modelo_proprio(empresa_id):
                return _me.versao_ativa(empresa_id) or "v1_inicial"
        except Exception:
            pass
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
    # sem coluna de renda, a renda é desconhecida (vazia), não zero: ver D9 em score._adicionar_derivadas
    "renda_estimada": None,
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

# Captura de erro ANTES do CORS, de propósito: no Starlette o último middleware
# adicionado é o mais externo, e a captura precisa ficar por dentro dele para o
# 500 sair com os cabeçalhos CORS — senão o navegador esconde o corpo e o
# cliente vê só "Failed to fetch", sem o código do erro. Ver erros.py.
import erros as _erros                                     # noqa: E402
import limite as _limite                                   # noqa: E402
import travas as _travas                                   # noqa: E402
# Ordem de instalação, da mais interna para a mais externa: limite, captura de
# erros, CORS. O limite rejeita antes de o corpo ser lido e precisa estar por
# dentro do CORS para o 429 sair com o cabeçalho. Ver limite.py.
_limite.instalar(app)
_erros.instalar_captura(app)
_erros.instalar_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer          = HTTPBearer()


def _conferir_versao_da_senha(payload: dict, user: dict) -> None:
    """Token emitido antes da última troca de senha não vale mais (ver auth.versao_da_senha)."""
    from auth import versao_da_senha
    atual = versao_da_senha(user)
    if atual is not None and payload.get("sv") != atual:
        raise HTTPException(status_code=401, detail="Sessão encerrada: a senha foi alterada. Entre de novo.")


def _usuario_autenticado(credentials: HTTPAuthorizationCredentials) -> dict:
    """Valida JWT e verifica que o usuário ainda está ativo no banco.
    Levanta 401 para token inválido/expirado ou usuário desativado."""
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    user = buscar_usuario_por_id(payload["sub"])
    if not user or not user.get("ativo"):
        raise HTTPException(status_code=401, detail="Usuário inativo ou não encontrado.")
    _conferir_versao_da_senha(payload, user)

    # O token prova QUEM é o usuário. O que ele pode fazer vem do cadastro, a
    # cada chamada. O JWT dura sete dias e carrega role e empresa_id de quando
    # foi emitido, então confiar neles deixava três coisas sem efeito até o
    # token expirar: rebaixar um admin, tirar um usuário de uma empresa e
    # desligá-lo. Reproduzido: com o cadastro dizendo "operador", "sem empresa"
    # ou "inativo", a rota de admin seguia respondendo 200 com os dados da
    # empresa antiga.
    if user.get("role"):
        payload["role"] = user["role"]
    if "empresa_id" in user:
        payload["empresa_id"] = user.get("empresa_id") or ""
    return payload


_COLUNAS_PREDICAO_CPF = ("id, carteira_id, created_at, score_recuperabilidade, valor_divida, "
                         "renda_estimada, dias_em_atraso, produto, uf")


def _predicao_do_cpf(db, cpf: str, empresa_id: "str | None",
                     colunas: "str | None" = None) -> "dict | None":
    """Predição mais recente de um CPF dentro de UMA empresa.

    Um mesmo CPF pode dever a mais de um cliente, então "a predição deste CPF"
    sem dizer de quem é ambígua — e resolvê-la pela mais recente de todas as
    empresas ligava o feedback de um cliente à carteira de outro.

    `empresa_id` vazio significa "sem escopo" e só é aceito por quem já
    verificou que a credencial é de comando. A falha é FECHADA: empresa sem
    carteira devolve None, em vez de tratar a lista vazia como "sem filtro".

    As carteiras vão em lotes de cem: uma empresa com centenas delas estouraria
    o tamanho da URL do PostgREST num único in_.
    """
    colunas = colunas or _COLUNAS_PREDICAO_CPF
    # created_at é o que decide a "mais recente" entre os lotes de carteiras, e
    # carteira_id é o que o chamador usa para invalidar cache: entram sempre.
    for obrigatoria in ("created_at", "carteira_id"):
        if obrigatoria not in colunas:
            colunas += f", {obrigatoria}"
    if not empresa_id:
        res = (db.table("predicoes").select(colunas).eq("cpf", cpf)
               .order("created_at", desc=True).limit(1).execute())
        return res.data[0] if res.data else None

    melhor = None
    carteiras = _ids_carteiras(db, empresa_id)
    for i in range(0, len(carteiras), ITENS_POR_IN):
        res = (db.table("predicoes").select(colunas).eq("cpf", cpf)
               .in_("carteira_id", carteiras[i:i + ITENS_POR_IN])
               .order("created_at", desc=True).limit(1).execute())
        if res.data and (melhor is None or (res.data[0].get("created_at") or "")
                         > (melhor.get("created_at") or "")):
            melhor = res.data[0]
    return melhor


def _exige_carteira_da_empresa(db, carteira_id: str, payload: dict) -> None:
    """Garante que a carteira pertence à empresa de quem chamou.

    Sem esta checagem, qualquer usuário autenticado podia passar o
    carteira_id de outra empresa na query string e ler os feedbacks dela —
    CPF, valor recuperado e data de pagamento. COMANDO enxerga tudo por
    definição; os demais ficam restritos à própria empresa.
    """
    if payload.get("role") == "comando":
        return
    empresa_id = payload.get("empresa_id", "")
    if not empresa_id:
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")
    try:
        res = db.table("carteiras").select("empresa_id").eq("id", carteira_id).limit(1).execute()
    except Exception:
        # Falha ao verificar não pode virar permissão: nega.
        raise HTTPException(status_code=503, detail="Não foi possível validar o acesso à carteira.")
    dono = (res.data or [{}])[0].get("empresa_id")
    if not dono or dono != empresa_id:
        raise HTTPException(status_code=403, detail="Acesso negado a esta carteira.")


# O PostgREST devolve no máximo ~1000 linhas por resposta, e não avisa: a
# resposta vem com 200 e um pedaço dos dados. Este projeto já convivia com isso
# em retrain.py (_BATCH = 1000) e em duas rotas de métricas, cada uma com o
# próprio laço. Onde faltava, o efeito era silencioso e grave: reabrir uma
# carteira de 5.000 devedores devolvia 1.000, e o resumo — total em risco,
# valor esperado, score médio — saía calculado sobre um quinto da carteira,
# sem nenhum sinal de que faltava algo.
LOTE_LEITURA = 1000

# Quantos valores cabem num in_(...). O filtro vai na URL, e cada id é um UUID de
# 36 caracteres: cem ids são ~3,7 KB, com folga sob o limite de 8 KB que muitos
# servidores e gateways aplicam. Não medi o limite real do Supabase daqui; o
# número é conservador de propósito, e é único para que ninguém reescolha outro
# (antes havia cem em uns lugares e duzentos em outros).
ITENS_POR_IN = 100


def _todas_as_linhas(construir_consulta, lote: int = LOTE_LEITURA) -> list:
    """Lê uma consulta inteira, página por página.

    Recebe uma função que monta a consulta do zero, porque o cliente do
    Supabase acumula estado: reaproveitar o mesmo objeto empilharia os filtros
    de range a cada volta.

    Para quando a página vem menor que o lote — é o fim dos dados. Se vier
    exatamente do tamanho do lote, pede a próxima; uma volta a mais que devolve
    zero linhas é barata perto de truncar a carteira em silêncio.
    """
    lote = max(1, min(lote, LOTE_LEITURA))
    linhas, offset = [], 0
    # Paginar por offset só é correto se a ordem for determinística entre uma
    # página e a seguinte. Sem ORDER BY o Postgres não promete ordem nenhuma, e
    # linhas podem ser puladas ou repetidas entre as páginas. `id` entra como
    # desempate no fim: o cliente acumula as ordenações (rank,id), então não
    # desfaz a que a consulta já pedia.
    # Se o outro lado ignorar o range — um proxy mal configurado, um cliente
    # substituído em teste — cada volta devolveria as mesmas linhas e o laço
    # nunca terminaria, prendendo a requisição para sempre. O limite transforma
    # isso em resposta incompleta com aviso no log, que é ruim, mas é visível.
    MAX_PAGINAS = 20_000
    for _ in range(MAX_PAGINAS):
        res = construir_consulta().order("id").range(offset, offset + lote - 1).execute()
        pagina = res.data or []
        if not pagina:
            return linhas
        linhas.extend(pagina)
        # Avança pelo que VEIO, não pelo que foi pedido, e só para quando uma
        # página vem vazia. Parar em "página menor que o lote" parecia
        # equivalente e economizava uma volta, mas depende de o teto do
        # servidor ser maior que o lote — e é justamente o teto do servidor que
        # este helper existe para não precisar conhecer. A volta extra no fim é
        # barata perto de truncar a carteira em silêncio.
        offset += len(pagina)
    print(f"[Leitura] {MAX_PAGINAS} páginas sem fim ao ler {len(linhas)} linhas — "
          "o servidor pode estar ignorando o range. Resultado possivelmente incompleto.")
    return linhas


def _ids_carteiras(db, empresa_id: str) -> list:
    """Carteiras da empresa. É por aqui que predições e feedbacks se ligam ao dono.

    Aparecia em onze lugares com três comportamentos diferentes: quatro com
    .limit(100), sete sem limite nenhum — e "sem limite" também trunca, porque
    o servidor corta em mil. Empresa que analisa uma carteira por dia passa de
    cem em três meses, e a partir daí parte dos dados dela simplesmente some
    das telas, sem erro.
    """
    return [c["id"] for c in _todas_as_linhas(
        lambda: db.table("carteiras").select("id").eq("empresa_id", empresa_id))]


def _ids_das_predicoes(db, carteira_id: str) -> set:
    """Ids das predições de uma carteira, TODAS. Sem paginar, o servidor entrega
    mil: uma carteira de 2.600 devedores perdia 1.600 do escopo, e os pagamentos
    dessas pessoas sumiam das telas de resultado."""
    return {p["id"] for p in _todas_as_linhas(
        lambda: db.table("predicoes").select("id").eq("carteira_id", carteira_id))}


def _feedbacks_das_predicoes(db, colunas: str, pred_ids) -> list:
    """Feedbacks ligados às predições dadas, do mais novo para o mais antigo.

    Lê em lotes de ITENS_POR_IN (a URL não aceita lista longa de UUIDs) e pagina
    cada lote. A versão anterior lia lotes de 500, sem medida de que a URL
    aguentava, e sem paginar cada resposta.
    """
    ids = list(pred_ids)
    saida: list = []
    for i in range(0, len(ids), ITENS_POR_IN):
        lote = ids[i:i + ITENS_POR_IN]
        saida.extend(_todas_as_linhas(
            lambda lote=lote: db.table("feedbacks").select(colunas).in_("predicao_id", lote)
                                .order("created_at", desc=True)))
    saida.sort(key=lambda f: f.get("created_at") or "", reverse=True)
    return saida


def _registrar_auditoria(
    acao: str,
    entidade: str | None = None,
    entidade_id: str | None = None,
    usuario_email: str | None = None,
    empresa_id: str | None = None,
    detalhes: dict | None = None,
    usuario_id: str | None = None,
) -> None:
    """Registra evento de auditoria em background — não bloqueia a resposta."""
    import threading
    def _bg():
        try:
            get_db().table("auditoria").insert({
                "acao":          acao,
                "entidade":      entidade,
                "entidade_id":   str(entidade_id) if entidade_id else None,
                "usuario_id":    usuario_id,
                "usuario_email": usuario_email or "",
                "empresa_id":    empresa_id or "",
                "detalhes":      detalhes,
            }).execute()
        except Exception as _ae:
            print(f"[Auditoria] Erro ao registrar '{acao}': {_ae}")
    threading.Thread(target=_bg, daemon=False).start()


class FeedbackIn(BaseModel):
    cpf: str
    pagou: bool
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[date] = None
    empresa: Optional[str] = None


class ConfirmarPagamentoIn(BaseModel):
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[date] = None


_confirmacoes_em_andamento: set[str] = set()
_rate_confirmacoes: dict[str, list[float]] = defaultdict(list)
_RATE_CONFIRM_MAX = 30
_RATE_CONFIRM_JANELA = 3600


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
    empresa_id_alvo: Optional[str] = None  # COMANDO pode especificar a empresa destino


def _conexao_usavel(db, conexao_id: str, payload: dict) -> dict:
    """Linha da conexão salva, se ESTE usuário pode usá-la; senão 404/403.

    comando usa qualquer uma; admin, as da própria empresa (ou que ele criou, ou
    em que tem permissão); operador, só as que o admin liberou para ele.
    """
    res = db.table("conexoes_db").select("*").eq("id", conexao_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")
    r = res.data[0]
    role, eid, uid = payload.get("role", "operador"), payload.get("empresa_id", ""), payload.get("sub")
    if role == "comando":
        return r
    if role == "admin" and ((eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid):
        return r
    perm = (db.table("conexao_permissoes").select("id")
            .eq("conexao_id", conexao_id).eq("operador_id", uid).limit(1).execute())
    if perm.data:
        return r
    raise HTTPException(status_code=403, detail="Sem permissão para usar esta conexão.")


def _exigir_conexao_da_empresa(db, conexao_id: str, payload: dict) -> dict:
    """Para gerir (editar, liberar a operadores): a conexão tem de ser da empresa
    de quem gere. Usar uma conexão por permissão não dá o direito de geri-la."""
    res = db.table("conexoes_db").select("id, empresa_id, usuario_id").eq("id", conexao_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")
    r = res.data[0]
    if payload.get("role") == "comando":
        return r
    eid, uid = payload.get("empresa_id", ""), payload.get("sub")
    if (eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid:
        return r
    raise HTTPException(status_code=403, detail="Acesso negado.")


def _cifrar_credencial_sheets(creds: dict) -> str:
    """O JSON da conta de serviço tem a chave privada: só entra no banco cifrado."""
    if not isinstance(creds, dict) or not creds.get("private_key") or not creds.get("client_email"):
        raise HTTPException(status_code=400, detail="Credencial do Google inválida: cole o JSON da conta de serviço "
                                                    "(com client_email e private_key).")
    return _encrypt(json.dumps(creds))


def _credencial_sheets_salva(r: dict) -> "dict | None":
    bruto = r.get("sheets_credenciais")
    if not bruto:
        return None
    if isinstance(bruto, dict):                     # gravada antes de ser cifrada
        return bruto
    return json.loads(_decrypt(bruto))              # _decrypt devolve o texto se não estiver cifrado


def _sem_segredos(row: dict) -> dict:
    """Linha de conexão para a tela: sem senha e sem credencial; diz só se a credencial existe."""
    row["senha"] = ""
    row["tem_credencial_sheets"] = bool(row.get("sheets_credenciais"))
    row.pop("sheets_credenciais", None)
    return row


def _resolver_credenciais(conn: ConexaoDB, payload: dict) -> None:
    """Autoriza o uso da conexão e, se for o caso, preenche a senha salva.

    Antes, qualquer usuário autenticado mandava `conexao_id` com a senha vazia e
    o servidor decifrava a senha SALVA, sem perguntar de quem era a conexão, e a
    usava contra o host que a requisição indicasse. Bastava apontar o host para
    um servidor próprio para receber a senha do cliente.

    Agora: a conexão tem de ser usável por quem pede, e o servidor dela (tipo,
    host, porta, banco, usuário) é o salvo, não o da requisição. Operador só usa
    conexão salva e liberada: digitar host e senha é de admin e comando.
    """
    role = payload.get("role", "operador")
    if not conn.conexao_id:
        if role == "operador":
            raise HTTPException(
                status_code=403,
                detail="Operadores usam apenas conexões salvas e liberadas para eles.")
        return
    r = _conexao_usavel(get_db(), conn.conexao_id, payload)
    senha_da_requisicao = bool(conn.senha)
    for campo in ("tipo", "host", "porta", "banco", "usuario", "instance_name", "service_name"):
        if campo in r and r.get(campo) is not None:
            setattr(conn, campo, r[campo])
    if not senha_da_requisicao and r.get("senha"):
        conn.senha = _decrypt(r["senha"])
    if r.get("tipo") == "sheets":
        for campo in ("sheets_id", "sheets_aba"):
            if r.get(campo):
                setattr(conn, campo, r[campo])
        if not conn.sheets_credenciais:
            conn.sheets_credenciais = _credencial_sheets_salva(r)


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



def _empresa_do_bandit(payload: dict, empresa_id: "str | None") -> str:
    """Empresa cujo bandit a rota administrativa vai ler ou alterar.

    O bandit é por empresa. COMANDO pode inspecionar o de um cliente
    específico passando ?empresa_id=; sem isso, usa a própria — mesmo padrão
    já adotado em /analisar.
    """
    if empresa_id:
        return empresa_id.strip().lower()
    return (payload.get("empresa_id") or "").strip().lower()


def _exigir_comando(credentials: HTTPAuthorizationCredentials) -> dict:
    # Via _usuario_autenticado, não validar_token: o painel COMANDO cria
    # empresas e usuários, muda papéis e promove modelo. Conferir só a
    # assinatura deixava um comando desligado, ou rebaixado, no controle da
    # plataforma até o token vencer.
    payload = _usuario_autenticado(credentials)
    if payload.get("role") != "comando":
        raise HTTPException(status_code=403, detail="Acesso restrito ao painel COMANDO.")
    return payload


@app.get("/comando/diagnostico-banco")
def comando_diagnostico_banco(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Mede, no Supabase real, três suposições de que a paginação depende.

    São suposições porque só o servidor real responde, e o ambiente de
    desenvolvimento não alcança o Supabase. Só leitura, sem dados de cliente:
    as listas de `in_` são UUIDs sorteados, que não casam com linha nenhuma.

      1. quantos itens cabem num in_ antes de a URL ser recusada;
      2. quantas linhas uma resposta devolve de fato (o teto silencioso);
      3. se `order=rank,id` (o desempate da paginação) é aceito.
    """
    _exigir_comando(credentials)
    import uuid
    db = get_db()
    out: dict = {"itens_por_in_adotado": ITENS_POR_IN, "lote_leitura_adotado": LOTE_LEITURA}

    maior_ok, primeira_falha = 0, None
    for n in (100, 200, 400, 500, 600, 800, 1600, 3200):
        ids = [str(uuid.uuid4()) for _ in range(n)]
        try:
            db.table("predicoes").select("id").in_("carteira_id", ids).limit(1).execute()
            maior_ok = n
        except Exception as e:
            primeira_falha = {"itens": n, "erro": str(e)[:160]}
            break
    out["in_"] = {"maior_testado_ok": maior_ok, "primeira_falha": primeira_falha,
                  "adotado_cabe": maior_ok >= ITENS_POR_IN}

    try:
        r = db.table("predicoes").select("id").range(0, 2999).execute()
        n = len(r.data or [])
        # Menos que o lote adotado pode ser teto menor OU tabela pequena: não dá
        # para afirmar nada, e dizer "ok" seria o erro que o teste existe para evitar.
        out["teto_resposta"] = {
            "pedidas": 3000, "recebidas": n,
            "veredito": ("lote adotado cabe" if n >= LOTE_LEITURA else "inconclusivo: a tabela tem menos linhas que o lote"),
        }
    except Exception as e:
        out["teto_resposta"] = {"erro": str(e)[:160]}

    try:
        db.table("predicoes").select("id, rank").order("rank").order("id").limit(5).execute()
        out["ordenacao_rank_id"] = {"aceita": True}
    except Exception as e:
        out["ordenacao_rank_id"] = {"aceita": False, "erro": str(e)[:160]}
    return out


@app.get("/comando/visao-geral")
def comando_visao_geral(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    db = get_db()

    _VAZIO = {"empresas": [], "totais": {"total_empresas": 0, "total_devedores": 0, "valor_face_total": 0, "valor_recuperado_real": 0, "n_suspeitas": 0}}

    # Paginado: sem isso o servidor entrega mil carteiras e o painel do COMANDO
    # somaria só essas — devedores, valor de face e empresas a menos, sem erro.
    try:
        cart_res = SimpleNamespace(data=_todas_as_linhas(lambda: db.table("carteiras").select(
            "id, empresa_id, usuario_email, total_devedores, valor_face, valor_esperado, score_medio, created_at")))
    except Exception:
        # colunas empresa_id/usuario_email ainda não existem — fallback sem agrupamento por empresa
        try:
            cart_res = SimpleNamespace(data=_todas_as_linhas(lambda: db.table("carteiras").select(
                "id, total_devedores, valor_face, valor_esperado, score_medio, created_at")))
        except Exception:
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

    # Todos os feedbacks, paginando: "valor recuperado real", o número de
    # feedbacks e a bandeira de empresa suspeita (< 5% de feedback) saem daqui.
    try:
        fb_data = _todas_as_linhas(
            lambda: db.table("feedbacks").select("predicao_id, pagou, valor_recuperado"))
    except Exception:
        try:
            fb_data = _todas_as_linhas(lambda: db.table("feedbacks").select("predicao_id, pagou"))
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

    # Adiciona empresas do cadastro de usuários que ainda não têm carteiras
    try:
        u_res = db.table("usuarios").select("empresa_id").neq("empresa_id", "").execute()
        for u in (u_res.data or []):
            eid = (u.get("empresa_id") or "").strip()
            if eid and eid not in empresas:
                empresas[eid] = {
                    "empresa_id": eid, "usuario_email": "",
                    "total_carteiras": 0, "total_devedores": 0,
                    "valor_face_total": 0.0, "valor_esperado_total": 0.0,
                    "_scores": [], "n_feedbacks": 0, "n_pagamentos": 0,
                    "valor_recuperado_real": 0.0, "ultima_atividade": None,
                }
    except Exception:
        pass

    # Busca nomes de exibição da empresa_config
    nome_exibicao_map: dict = {}
    try:
        cfg_res = db.table("empresa_config").select("empresa_id, nome_exibicao, foto_url").execute()
        for c in (cfg_res.data or []):
            eid = c.get("empresa_id") or ""
            if eid:
                nome_exibicao_map[eid] = {
                    "nome_exibicao": c.get("nome_exibicao") or eid,
                    "foto_url": c.get("foto_url"),
                }
    except Exception:
        pass

    result = []
    for e in empresas.values():
        vf = e["valor_face_total"]
        vr = e["valor_recuperado_real"]
        td = e["total_devedores"]
        taxa_fb = round(e["n_feedbacks"] / td * 100, 1) if td > 0 else 0
        eid = e["empresa_id"]
        cfg = nome_exibicao_map.get(eid, {})
        result.append({
            "empresa_id":            eid,
            "nome_exibicao":         cfg.get("nome_exibicao") or eid,
            "foto_url":              cfg.get("foto_url"),
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

    # Remove entradas sem empresa real (carteiras órfãs sem empresa_id)
    result = [r for r in result if r["empresa_id"] not in ("sem_empresa", "") and "@" not in r["empresa_id"]]

    totais = {
        "total_empresas":        len(result),
        "total_devedores":       sum(r["total_devedores"] for r in result),
        "valor_face_total":      round(sum(r["valor_face_total"] for r in result), 2),
        "valor_recuperado_real": round(sum(r["valor_recuperado_real"] for r in result), 2),
        "n_suspeitas":           sum(1 for r in result if r["flag_suspeita"]),
    }
    return {"empresas": result, "totais": totais}


@app.get("/comando/empresa/{empresa_id}")
def comando_empresa_detalhe(empresa_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    db = get_db()

    cfg = _get_empresa_config(empresa_id)

    usuarios = listar_usuarios(empresa_id=empresa_id)

    try:
        cx_res = db.table("conexoes_db").select(
            "id, nome, tipo, host, database, usuario_id, created_at"
        ).eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
        conexoes = cx_res.data or []
    except Exception:
        conexoes = []

    try:
        carteiras = _todas_as_linhas(lambda: db.table("carteiras").select(
            "id, nome_arquivo, total_devedores, valor_face, valor_esperado, score_medio, created_at"
        ).eq("empresa_id", empresa_id).order("created_at", desc=True))
    except Exception:
        carteiras = []

    return {
        "empresa_id": empresa_id,
        "config": cfg,
        "usuarios": usuarios,
        "conexoes": conexoes,
        "carteiras": carteiras,
    }


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


def _aging_label(dias: int) -> str:
    # Faixas fechadas à direita (até 30, 31 a 60...), como as fases do ciclo
    # (model/ciclo.py: administrativa até 30, especializada de 31 a 360). Antes
    # eram 0-29, 30-59...: o dia 30 caía em "30-59" no aging e na fase
    # administrativa no ciclo (achado D7).
    if dias <= 30:
        return "0-30 dias"
    if dias <= 60:
        return "31-60 dias"
    if dias <= 90:
        return "61-90 dias"
    if dias <= 180:
        return "91-180 dias"
    return "181+ dias"


def _cpf_no_log(cpf) -> str:
    """Só os dois últimos dígitos: o bastante para cruzar com a tela, sem pôr o CPF no log."""
    d = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    return f"***{d[-2:]}" if d else "—"


def _fechar_loop_bandit(db, cpf: str, pagou: bool, valor_recuperado: float, pred_data: dict | None,
                        empresa_id: str | None) -> None:
    """
    Atualiza o bandit com um pagamento confirmado (ou um não pagamento), na
    ação que foi feita com este devedor nesta empresa:

      1. a do último contato registrado com canal e oferta (o que o operador
         de fato apresentou);
      2. senão, a última recomendação registrada para ele.

    Sem nenhuma das duas, NÃO atualiza. Antes havia um "aprendizado offline":
    o bandit escolhia na hora a ação que teria recomendado e a creditava com o
    resultado, como se tivesse sido feita (achado D2).
    """
    from model.bandit import acao_id_de, construir_contexto, registrar_resultado

    valor_divida = float((pred_data or {}).get("valor_divida") or 0)
    if pagou and valor_divida > 0:
        recompensa = min(1.0, float(valor_recuperado or valor_divida) / valor_divida)
    elif pagou:
        recompensa = 0.5
    else:
        recompensa = 0.0

    try:
        # Escopo por empresa: o mesmo CPF pode dever a mais de um cliente, e
        # sem o filtro o pagamento de um treinaria o bandit com a abordagem do outro.
        def _ultimos(tabela, colunas, n):
            q = db.table(tabela).select(colunas).eq("cpf", cpf)
            if empresa_id:
                q = q.eq("empresa_id", empresa_id)
            return q.order("created_at", desc=True).limit(n).execute().data or []

        recs = _ultimos("recomendacoes", "acao_id, contexto", 1)
        acao_id = None
        try:
            contatos = _ultimos("contatos", "canal, oferta, acao_bandit_id", 20)
        except Exception:                 # banco ainda sem a coluna `oferta`
            contatos = _ultimos("contatos", "canal, acao_bandit_id", 20)
        for ct in contatos:
            acao_id = acao_id_de(ct.get("canal"), ct.get("oferta")) if ct.get("oferta") else None
            if acao_id is None:
                acao_id = ct.get("acao_bandit_id")
            if acao_id is not None:
                break
        contexto = recs[0]["contexto"] if recs else None
        if acao_id is None and recs:
            acao_id = recs[0]["acao_id"]
        if acao_id is None:
            return
        if contexto is None:
            if not pred_data:
                return
            vd = float(pred_data.get("valor_divida") or 0)
            rd = float(pred_data.get("renda_estimada") or 0)
            contexto = construir_contexto({**pred_data, "comprometimento_renda": (vd / rd) if rd > 0 else 1.0}).tolist()
        registrar_resultado(acao_id=acao_id, contexto=contexto, recompensa=recompensa,
                            empresa_id=empresa_id, pagou=bool(pagou))
    except Exception as _be:
        # sem o CPF: o log não é lugar de dado pessoal
        print(f"[Bandit] Erro ao fechar loop: {type(_be).__name__}")


# Colunas da api_keys que a aplicação precisa. Nunca inclui api_key: a chave
# em texto não tem por que circular na memória do processo nem nos logs.
_COLS_API_KEY = "id, empresa_nome, empresa_id, rotulo, ativa, created_at, ultimo_uso"


def _hash_api_key(chave: str) -> str:
    """SHA-256 da chave, que é o que fica guardado no banco.

    Guardar a chave em texto significa que qualquer dump, backup ou acesso de
    leitura ao banco entrega credencial funcional. Guardando o hash, o banco
    consegue reconhecer uma chave apresentada mas não consegue produzi-la.
    """
    import hashlib
    return hashlib.sha256((chave or "").encode("utf-8")).hexdigest()


def _buscar_api_key(db, token: str) -> "dict | None":
    """Linha da chave apresentada, ou None. Procura pelo hash."""
    try:
        res = (db.table("api_keys").select(_COLS_API_KEY)
               .eq("api_key_hash", _hash_api_key(token))
               .eq("ativa", True).limit(1).execute())
        if res.data:
            return res.data[0]
    except Exception as e:
        # Coluna de hash ainda não existe (migração não rodou): cai no texto.
        if "api_key_hash" not in str(e):
            raise
    # Retaguarda para chave gravada antes da migração do hash. Some sozinha
    # quando o texto for limpo do banco.
    try:
        res = (db.table("api_keys").select(_COLS_API_KEY)
               .eq("api_key", token).eq("ativa", True).limit(1).execute())
        return res.data[0] if res.data else None
    except Exception:
        return None


def _marcar_uso_api_key(db, linha: dict) -> None:
    """Registra o último uso. Sem isso não dá para saber se uma chave ainda
    está em uso antes de revogá-la — que foi exatamente a dúvida que travou a
    revogação da primeira chave."""
    try:
        db.table("api_keys").update(
            {"ultimo_uso": datetime.utcnow().isoformat()}
        ).eq("id", linha["id"]).execute()
    except Exception:
        pass  # rastro de uso nunca pode derrubar uma requisição válida


def _validar_api_key(credentials: HTTPAuthorizationCredentials) -> dict:
    """Aceita JWT do frontend OU api_key legada do Supabase."""
    token = credentials.credentials

    # Tenta JWT primeiro
    try:
        payload = validar_token(token)
    except ValueError:
        payload = None
    if payload is not None:
        # Pelo mesmo caminho do resto do sistema: usuário ativo E papel e
        # empresa lidos do cadastro. Conferir só "ativo" deixava a metade do
        # problema: um admin REBAIXADO a operador seguia registrando pagamentos
        # manuais, porque /feedback decide pelo role que veio no token, e um
        # usuário movido de empresa seguia gravando na antiga. O token dura sete
        # dias, e esses pagamentos alimentam o treino do modelo e do bandit.
        payload = _usuario_autenticado(credentials)
        return {"empresa_nome": payload.get("nome", ""), "role": payload.get("role", "operador"), "jwt": payload}

    # Fallback: api_key legada no Supabase
    db = get_db()
    linha = _buscar_api_key(db, token)
    if not linha:
        raise HTTPException(status_code=401, detail="Não autorizado. Faça login ou use uma API key válida.")
    _marcar_uso_api_key(db, linha)
    return linha

def _exigir_admin_ou_comando(credentials: HTTPAuthorizationCredentials) -> dict:
    # Mesma razão de _exigir_comando: gestão de equipe, retenção de dados e
    # configuração da empresa não podem sobreviver ao desligamento de quem as
    # exercia.
    payload = _usuario_autenticado(credentials)
    if payload.get("role") not in ("admin", "comando"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    # Admin SEM empresa não tem escopo, e várias rotas tratam empresa vazia como
    # "todas" — listar_usuarios("") devolve os usuários de todos os clientes.
    # "Remover da empresa" grava justamente empresa_id = "", então um admin
    # removido passava a enxergar e-mail, nome e papel de toda a plataforma
    # assim que o token era renovado. Só o comando atua sem empresa.
    if payload.get("role") == "admin" and not payload.get("empresa_id"):
        raise HTTPException(status_code=403, detail="Administrador sem empresa vinculada.")
    return payload


# ── Modelos de auth ───────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    senha: str

class RegistrarIn(BaseModel):
    email:      str
    nome:       str
    senha:      str
    role:       str = "operador"
    empresa_id: Optional[str] = None

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
    from auth import versao_da_senha
    token = criar_token({"sub": usuario["id"], "email": usuario["email"],
                         "nome": usuario["nome"], "role": usuario["role"],
                         "empresa_id": usuario.get("empresa_id", ""),
                         "sv": versao_da_senha(usuario)})
    return {"token": token, "usuario": {k: v for k, v in usuario.items() if k != "senha_hash"}}

@app.get("/auth/me")
def auth_me(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    # Pelo cadastro, não pelo token: é daqui que a tela decide o que mostrar, e
    # um papel desatualizado exibiria menus que o servidor já recusa.
    payload = _usuario_autenticado(credentials)
    return {"email": payload["email"], "nome": payload["nome"], "role": payload["role"]}

@app.post("/auth/refresh")
def auth_refresh(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Emite um novo token com os dados atuais do banco (corrige role desatualizada no JWT)."""
    try:
        payload = validar_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    user = buscar_usuario_por_id(payload["sub"])
    if not user or not user.get("ativo"):
        raise HTTPException(status_code=401, detail="Usuário inativo ou não encontrado.")
    # Renovar não pode ressuscitar um token de antes da troca de senha.
    _conferir_versao_da_senha(payload, user)
    from auth import versao_da_senha
    new_token = criar_token({
        "sub": user["id"], "email": user["email"],
        "nome": user["nome"], "role": user["role"],
        "empresa_id": user.get("empresa_id", ""),
        "sv": versao_da_senha(user),
    })
    return {"token": new_token, "usuario": {k: v for k, v in user.items() if k != "senha_hash"}}

@app.get("/auth/usuarios")
def auth_listar(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    if payload.get("role") == "comando":
        return listar_usuarios()
    return listar_usuarios(empresa_id=payload.get("empresa_id", ""))

@app.post("/auth/registrar")
def auth_registrar(body: RegistrarIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    # Comando pode criar outro comando. A rota inteira já exige comando, então
    # o admin de um banco cliente continua sem alcance nenhum aqui — ele não
    # chega a chamar isto.
    if body.role not in ("comando", "admin", "operador"):
        raise HTTPException(status_code=400, detail="Role inválido. Use 'comando', 'admin' ou 'operador'.")
    empresa_id = (body.empresa_id or "").strip().lower()
    if body.role == "comando":
        # Comando é papel de plataforma, não de cliente: o sistema já recusa
        # mover um comando para dentro de uma empresa, então nascer dentro de
        # uma seria criar justamente o estado que aquela regra evita.
        empresa_id = ""
    elif not empresa_id:
        raise HTTPException(status_code=400, detail="Informe a empresa do usuário.")
    try:
        novo = criar_usuario(body.email.strip().lower(), body.nome, body.senha, body.role, empresa_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _registrar_auditoria(
        acao="usuario_criado",
        entidade="usuario",
        entidade_id=novo["id"],
        usuario_email=payload.get("email"),
        empresa_id=empresa_id,
        detalhes={"email_novo": body.email, "role": body.role},
        usuario_id=payload.get("sub"),
    )
    return {"ok": True, "usuario": novo}

@app.post("/auth/alterar-senha")
def auth_alterar_senha(body: AlterarSenhaIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    try:
        ok = alterar_senha(payload["email"], body.senha_atual, body.nova_senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    _registrar_auditoria(
        acao="senha_alterada",
        entidade="usuario",
        entidade_id=payload["sub"],
        usuario_email=payload["email"],
        empresa_id=payload.get("empresa_id", ""),
        usuario_id=payload["sub"],
    )
    # O token de quem trocou a senha também caiu (a versão da senha mudou):
    # devolve um novo para a pessoa continuar onde está. As outras sessões dela
    # (outro aparelho, ou um token roubado) param de valer.
    from auth import versao_da_senha
    u = buscar_usuario_por_id(payload["sub"]) or {}
    novo = criar_token({"sub": payload["sub"], "email": payload["email"], "nome": payload.get("nome", ""),
                        "role": payload.get("role"), "empresa_id": payload.get("empresa_id", ""),
                        "sv": versao_da_senha(u)})
    return {"ok": True, "token": novo}


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
    sheets_credenciais: Optional[dict] = None  # JSON da conta de serviço; gravado cifrado
    query: Optional[str] = None
    mapeamento: Optional[dict] = None
    empresa_id: Optional[str] = None  # COMANDO pode especificar a empresa destino
    intervalo_sync_horas: Optional[float] = 1.0  # intervalo de auto-sync em horas
    writeback_habilitado: Optional[bool] = False  # OPT-IN: por padrão a conexão é SOMENTE-LEITURA
    coluna_writeback: Optional[str] = None   # coluna a atualizar no banco externo ao registrar pagamento
    valor_pago: Optional[str] = 'pago'       # valor a gravar quando pagou=True
    valor_nao_pago: Optional[str] = None     # valor a gravar quando pagou=False (None = não atualiza)


class ConexaoUpdateIn(BaseModel):
    nome: Optional[str] = None
    sheets_credenciais: Optional[dict] = None  # para completar conexões Sheets salvas sem ela
    query: Optional[str] = None
    mapeamento: Optional[dict] = None
    carteira_id: Optional[str] = None
    intervalo_sync_horas: Optional[float] = None
    writeback_habilitado: Optional[bool] = None
    coluna_writeback: Optional[str] = None
    valor_pago: Optional[str] = None
    valor_nao_pago: Optional[str] = None

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
    payload = _exigir_admin_ou_comando(credentials)
    if payload.get("role") == "admin":
        db = get_db()
        u = db.table("usuarios").select("empresa_id, role").eq("id", usuario_id).limit(1).execute()
        if not u.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if u.data[0].get("empresa_id") != payload.get("empresa_id", ""):
            raise HTTPException(status_code=403, detail="Sem permissão para alterar este usuário.")
        if u.data[0].get("role") == "comando":
            raise HTTPException(status_code=403, detail="Não é possível alterar um usuário COMANDO.")
    try:
        resultado = toggle_usuario_ativo(usuario_id, body.ativo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    _registrar_auditoria(
        acao="usuario_ativado" if body.ativo else "usuario_desativado",
        entidade="usuario",
        entidade_id=usuario_id,
        usuario_email=payload.get("email"),
        empresa_id=payload.get("empresa_id", ""),
        detalhes={"email_alvo": resultado.get("email"), "ativo": body.ativo},
        usuario_id=payload.get("sub"),
    )
    return {"ok": True, "usuario": resultado}

@app.patch("/auth/usuarios/{usuario_id}/role")
def auth_alterar_role(usuario_id: str, body: RoleIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    if body.role not in ("comando", "admin", "operador"):
        raise HTTPException(status_code=400, detail="Role inválido. Use 'comando', 'admin' ou 'operador'.")
    try:
        resultado = alterar_role(usuario_id, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    _registrar_auditoria(
        acao="role_alterado",
        entidade="usuario",
        entidade_id=usuario_id,
        usuario_email=payload.get("email"),
        empresa_id=payload.get("empresa_id", ""),
        detalhes={"email_alvo": resultado.get("email"), "nova_role": body.role},
        usuario_id=payload.get("sub"),
    )
    return {"ok": True, "usuario": resultado}


@app.post("/auth/esqueci-senha")
def auth_esqueci_senha(body: EsqueciSenhaIn, background_tasks: BackgroundTasks):
    from email_utils import email_redefinir_senha
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://mizan-sand.vercel.app")

    # Sem freio, qualquer um disparava e-mails de redefinição em massa para um
    # endereço conhecido. Chave por e-mail e não por IP: atrás do proxy o IP é
    # o mesmo para todos. Quando o limite pega a resposta é IDÊNTICA à normal —
    # um 429 aqui revelaria que o e-mail existe, desfazendo justamente a
    # proteção que a mensagem genérica dá.
    _email = (body.email or "").strip().lower()
    _ok_email, _ = _limite.LIMITADOR.tentar(f"esqueci:{_email}", 3, 3600)
    # O teto global só conta quando o do e-mail deixou passar. Contar sempre
    # faria quem martela UM endereço esgotar a cota de todos e bloquear a
    # redefinição de senha da plataforma inteira.
    _ok_geral = True
    if _ok_email:
        _ok_geral, _ = _limite.LIMITADOR.tentar("esqueci:_todos", 200, 3600)
    if not (_ok_email and _ok_geral):
        _limite.log.warning(json.dumps({"evento": "esqueci_senha_limitado",
                                        "global": not _ok_geral}))
        return {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá as instruções em breve."}

    token = criar_reset_token(body.email)
    if token:
        usuario = buscar_usuario(body.email)
        nome = usuario.get("nome", "usuário") if usuario else "usuário"
        link = f"{FRONTEND_URL}/redefinir-senha?token={token}"
        background_tasks.add_task(email_redefinir_senha, body.email, nome, link)
    return {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá as instruções em breve."}

@app.get("/conexoes")
def listar_conexoes(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    role = payload.get("role", "operador")

    rows: list = []

    if role == "comando":
        # Comando vê TODAS as conexões de todas as empresas
        r = db.table("conexoes_db").select("*").order("created_at", desc=True).execute()
        rows = r.data or []
    elif role == "admin":
        # Admin vê conexões da sua empresa + as que criou + as que recebeu permissão explícita
        seen: set = set()
        if eid:
            r1 = db.table("conexoes_db").select("*").eq("empresa_id", eid).order("created_at", desc=True).execute()
            for r in (r1.data or []):
                seen.add(r["id"]); rows.append(r)
        r2 = db.table("conexoes_db").select("*").eq("usuario_id", uid).order("created_at", desc=True).execute()
        for r in (r2.data or []):
            if r["id"] not in seen:
                seen.add(r["id"]); rows.append(r)
        perm = db.table("conexao_permissoes").select("conexao_id").eq("operador_id", uid).execute()
        ids_perm = [p["conexao_id"] for p in (perm.data or []) if p["conexao_id"] not in seen]
        if ids_perm:
            r3 = db.table("conexoes_db").select("*").in_("id", ids_perm).execute()
            for r in (r3.data or []):
                if r["id"] not in seen:
                    seen.add(r["id"]); rows.append(r)
    else:
        # Operador vê apenas conexões com permissão explícita
        perm = db.table("conexao_permissoes").select("conexao_id").eq("operador_id", uid).execute()
        ids_permitidos = [p["conexao_id"] for p in (perm.data or [])]
        if ids_permitidos:
            r = db.table("conexoes_db").select("*").in_("id", ids_permitidos).order("created_at", desc=True).execute()
            rows = r.data or []

    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return [_sem_segredos(row) for row in rows]

@app.post("/conexoes")
def salvar_conexao(body: ConexaoSalvarIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    # Filtra nulos para não enviar colunas que podem não existir na tabela
    row = {k: v for k, v in body.model_dump().items() if v is not None}
    row.pop("empresa_id", None)  # será definido abaixo
    row["usuario_id"] = payload["sub"]
    # COMANDO pode especificar a empresa destino; outros usam o JWT
    if payload.get("role") == "comando" and body.empresa_id:
        row["empresa_id"] = body.empresa_id.strip().lower()
    else:
        row["empresa_id"] = payload.get("empresa_id") or None
    row["senha"] = _encrypt(body.senha)  # cifra antes de armazenar
    if body.tipo == "sheets":
        if not body.sheets_id or not body.sheets_credenciais:
            raise HTTPException(status_code=400, detail="Para Google Sheets, informe o ID da planilha e a credencial da conta de serviço.")
        row["sheets_credenciais"] = _cifrar_credencial_sheets(body.sheets_credenciais)
    try:
        res = db.table("conexoes_db").insert(row).execute()
    except Exception as e:
        if "sheets_credenciais" in str(e):
            raise HTTPException(status_code=503, detail="O banco ainda não tem onde guardar a credencial do Google: "
                                                        "rode backend/sql/migracao_conexoes_sheets.sql no Supabase.")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar conexão no banco: {type(e).__name__}")
    if not res.data:
        raise HTTPException(status_code=500, detail="Falha ao inserir conexão — verifique o schema da tabela conexoes_db no Supabase.")
    return {"ok": True, "conexao": _sem_segredos(res.data[0])}   # nem senha nem credencial voltam

class ContatoIn(BaseModel):
    cpf: str
    canal: str
    resultado: str
    data_contato: Optional[str] = None
    observacao: Optional[str] = None
    valor_recuperado: Optional[float] = Field(None, ge=0)
    desconto_oferecido_pct: Optional[float] = Field(None, ge=0, le=100)
    acao_bandit_id: Optional[int] = None
    # Qual das ofertas do catálogo foi apresentada. É o que liga a escolha do
    # operador ao aprendizado: sem ela, o bandit só aprende sobre a oferta que
    # ele mesmo recomendou, não sobre a que foi de fato negociada.
    oferta: Optional[str] = None

    @field_validator('oferta')
    @classmethod
    def _val_oferta(cls, v):
        if v is None or v == '':
            return None
        from model.bandit import OFERTAS
        if v not in OFERTAS:
            raise ValueError(f'Oferta inválida. Use: {", ".join(OFERTAS)}.')
        return v

    @field_validator('canal')
    @classmethod
    def _val_canal(cls, v):
        if v not in ('whatsapp', 'telefone', 'carta'):
            raise ValueError('Canal inválido. Use: whatsapp, telefone ou carta.')
        return v

    @field_validator('resultado')
    @classmethod
    def _val_resultado(cls, v):
        validos = ('contactado', 'sem_resposta', 'prometeu_pagar', 'pagou', 'nao_quis')
        if v not in validos:
            raise ValueError(f'Resultado inválido. Use: {", ".join(validos)}.')
        return v

    @field_validator('data_contato')
    @classmethod
    def _val_data(cls, v):
        if v:
            try:
                from datetime import date as _date, datetime as _dt
                d = _dt.fromisoformat(v).date()
                if d > _date.today():
                    raise ValueError('Data de contato não pode ser futura.')
            except ValueError:
                raise
        return v


# "pagou" no contato é o que o operador ouviu do devedor, não um pagamento
# confirmado: fica fora daqui. O bandit recebe o pagamento quando ele é
# confirmado (baixa, webhook, sincronização), em _fechar_loop_bandit, creditado à
# oferta apresentada no contato (achado D11). Antes o contato "pagou" já dava a
# recompensa cheia, e a confirmação depois dava de novo.
_CONTATO_RECOMPENSA: dict = {
    "prometeu_pagar": 0.2,
    "contactado":     0.05,
    "sem_resposta":   0.0,
    "nao_quis":       0.0,
}


@app.post("/contatos")
def registrar_contato(body: ContatoIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    db = get_db()

    _emp = payload.get("empresa_id", "")
    if not _emp and payload.get("role") != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")

    if body.resultado == "pagou":
        # Falha FECHADA. O recorte antigo era `if cart_ids:` dentro de um
        # `except: pass`: empresa sem carteira, ou um erro ao listá-las, virava
        # "sem filtro" — e a resposta 404/200 passava a revelar se o CPF existia
        # em QUALQUER empresa.
        pred_check = _predicao_do_cpf(db, body.cpf, _emp, colunas="id")
        if not pred_check:
            raise HTTPException(
                status_code=404,
                detail=f"CPF {body.cpf} não encontrado nas predições. Só é possível registrar pagamentos de devedores presentes na carteira analisada.",
            )

    # Filtra None para não enviar colunas inexistentes ao Supabase
    row = {k: v for k, v in body.model_dump().items() if v is not None}
    row["usuario_id"]   = payload["sub"]
    row["usuario_nome"] = payload.get("nome", "")
    row["empresa_id"]   = payload.get("empresa_id", "")

    try:
        try:
            res = db.table("contatos").insert(row).execute()
        except Exception as e:
            # Banco sem a coluna `oferta` (sql/migracao_contatos_oferta.sql não
            # rodou): grava o contato sem ela em vez de perder o registro. O
            # aprendizado desta requisição ainda usa a oferta, que vem no corpo.
            if "oferta" not in row or "oferta" not in str(e):
                raise
            print("[Contato] coluna 'oferta' ausente em contatos; rode sql/migracao_contatos_oferta.sql")
            res = db.table("contatos").insert({k: v for k, v in row.items() if k != "oferta"}).execute()
        if not res.data:
            raise RuntimeError("insert retornou vazio")
    except Exception as e:
        print(f"[Contato] Erro ao inserir: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Erro ao registrar contato. Tente novamente.")

    # Fecha o loop do bandit: aprende com o resultado real do contato
    if body.resultado in _CONTATO_RECOMPENSA:
        try:
            _emp = payload.get("empresa_id", "")
            _rec_q = (db.table("recomendacoes").select("acao_id, contexto")
                      .eq("cpf", body.cpf))
            if _emp:
                _rec_q = _rec_q.eq("empresa_id", _emp)
            rec_res = _rec_q.order("created_at", desc=True).limit(1).execute()
            anterior = rec_res.data[0] if rec_res.data else None

            # A oferta que o operador diz ter apresentado tem precedência
            # sobre a que o bandit havia recomendado: é ela que foi negociada.
            from model.bandit import acao_id_de, registrar_resultado
            acao_id = acao_id_de(body.canal, body.oferta) if body.oferta else None
            if acao_id is None:
                acao_id = body.acao_bandit_id
            if acao_id is None and anterior:
                acao_id = anterior["acao_id"]

            # Sem recomendação prévia não havia contexto, e o loop inteiro era
            # pulado — por isso o aprendizado nunca saía do lugar quando o
            # operador negociava direto pela tela de propostas. O contexto é
            # reconstruído da predição quando falta.
            contexto = anterior["contexto"] if anterior else None
            pred_r = None
            if contexto is None:
                # Escopada à empresa: sem isso a predição mais recente de TODAS
                # as empresas servia de contexto, e o bandit de uma aprendia com
                # a renda e a dívida de um devedor de outra.
                _pr = _predicao_do_cpf(
                    db, body.cpf, _emp,
                    colunas="cpf, nome, produto, uf, valor_divida, renda_estimada, "
                            "dias_em_atraso, score_recuperabilidade")
                pred_r = type("R", (), {"data": [_pr] if _pr else []})()
            if contexto is None and pred_r and pred_r.data:
                from model.bandit import construir_contexto
                _p = pred_r.data[0]
                _vd = float(_p.get("valor_divida") or 0)
                _rd = float(_p.get("renda_estimada") or 0)
                contexto = construir_contexto(
                    {**_p, "comprometimento_renda": (_vd / _rd) if _rd > 0 else 1.0}
                ).tolist()

            if acao_id is not None and contexto is not None:
                registrar_resultado(acao_id=acao_id, contexto=contexto,
                                    recompensa=_CONTATO_RECOMPENSA[body.resultado],
                                    empresa_id=_emp, pagou=False)
            else:
                print(f"[Bandit/Contato] Sem ação ou contexto: "
                      f"acao_id={acao_id}, contexto={'ok' if contexto else 'ausente'}")
        except Exception as _be:
            print(f"[Bandit/Contato] {_be}")

    return {"ok": True, "contato": res.data[0]}


@app.get("/contatos/{cpf}")
def listar_contatos_cpf(cpf: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    db = get_db()
    q = db.table("contatos").select("*").eq("cpf", cpf)
    empresa_id = payload.get("empresa_id", "")
    # Falha fechada: antes, quem não tinha empresa caía em "sem filtro" e via os
    # contatos desse CPF em TODAS as empresas — incluindo o campo livre
    # "observação", onde o operador escreve telefone e nome de parente.
    if not empresa_id and payload.get("role") != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")
    if empresa_id:
        q = q.eq("empresa_id", empresa_id)
    res = q.order("created_at", desc=True).limit(50).execute()
    return res.data


@app.delete("/auth/me")
def deletar_conta(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """LGPD — usuário solicita exclusão da própria conta e dados."""
    payload = _usuario_autenticado(credentials)
    usuario_id = payload["sub"]
    db = get_db()
    from auth import _ultimo_comando_ativo
    if _ultimo_comando_ativo(db, usuario_id):
        raise HTTPException(status_code=400, detail="Você é o único COMANDO ativo: excluir a conta trancaria a "
                                                    "plataforma. Promova outro usuário a COMANDO antes.")
    # Saem os dados pessoais DE QUEM PEDIU: o cadastro, e o nome dele onde ficou
    # gravado. Ficam os registros que são da empresa: o histórico de contatos com
    # devedores e as conexões com o banco do cliente. Antes a rota apagava os
    # dois — um operador que saísse levava junto o histórico de cobrança e as
    # conexões que a empresa usa.
    db.table("contatos").update({"usuario_nome": "Usuário removido"}).eq("usuario_id", usuario_id).execute()
    try:
        db.table("duvidas").update({"autor_nome": "Usuário removido", "autor_email": ""}).eq("autor_id", usuario_id).execute()
    except Exception:
        pass                                   # tabela da Central ainda não criada
    db.table("usuarios").delete().eq("id", usuario_id).execute()
    # A trilha de auditoria guarda o fato, sem o e-mail (é ele o dado pessoal).
    _registrar_auditoria(acao="conta_excluida", entidade="usuario", entidade_id=usuario_id,
                         usuario_email="", empresa_id=payload.get("empresa_id", ""),
                         usuario_id=usuario_id, detalhes={})
    return {"ok": True, "mensagem": "Conta e dados pessoais removidos."}


@app.patch("/conexoes/{conexao_id}")
def atualizar_conexao(conexao_id: str, body: ConexaoUpdateIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Atualiza campos de uma conexão salva (mapeamento, query, etc.)."""
    # Editar conexão (consulta, mapeamento, escrita de volta) é de admin e comando:
    # a tela não oferece isso ao operador, e a rota aceitava qualquer usuário da empresa.
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}
    _exigir_conexao_da_empresa(db, conexao_id, payload)
    if "sheets_credenciais" in updates:
        updates["sheets_credenciais"] = _cifrar_credencial_sheets(updates["sheets_credenciais"])
    try:
        db.table("conexoes_db").update(updates).eq("id", conexao_id).execute()
    except Exception as e:
        if "sheets_credenciais" in str(e):
            raise HTTPException(status_code=503, detail="O banco ainda não tem onde guardar a credencial do Google: "
                                                        "rode backend/sql/migracao_conexoes_sheets.sql no Supabase.")
        raise
    return {"ok": True}


@app.delete("/conexoes/{conexao_id}")
def deletar_conexao(conexao_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    chk = db.table("conexoes_db").select("id, empresa_id, usuario_id").eq("id", conexao_id).execute()
    if not chk.data:
        return {"ok": True}
    r = chk.data[0]
    # COMANDO gere as conexões de todas as empresas (como em _exigir_conexao_da_empresa)
    if payload.get("role") != "comando" and not ((eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    db.table("conexoes_db").delete().eq("id", conexao_id).execute()
    return {"ok": True}



# ── Gestão de Empresas (comando only) ─────────────────────────────────────────

@app.get("/empresas")
def listar_empresas(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    db = get_db()
    todos = db.table("usuarios").select("id, nome, email, role, ativo, empresa_id").order("empresa_id").execute()
    empresas: dict = {}
    sem_empresa: list = []
    for u in (todos.data or []):
        if u.get("role") == "comando":
            continue
        eid = (u.get("empresa_id") or "").strip()
        if not eid:
            sem_empresa.append(u)
        else:
            if eid not in empresas:
                empresas[eid] = {"empresa_id": eid, "usuarios": [], "nome_exibicao": eid}
            empresas[eid]["usuarios"].append(u)
    # Enriquece com nome_exibicao da empresa_config
    try:
        cfg_res = db.table("empresa_config").select("empresa_id, nome_exibicao").execute()
        for c in (cfg_res.data or []):
            eid = (c.get("empresa_id") or "").strip()
            if eid and eid in empresas and c.get("nome_exibicao"):
                empresas[eid]["nome_exibicao"] = c["nome_exibicao"]
    except Exception:
        pass
    return {"empresas": list(empresas.values()), "sem_empresa": sem_empresa}


class AdicionarUsuarioEmpresaIn(BaseModel):
    email: str


@app.post("/empresas/{empresa_id}/usuarios")
def adicionar_usuario_empresa(empresa_id: str, body: AdicionarUsuarioEmpresaIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    # minúscula, como em todo o resto: "Goias_Bank" e "goias_bank" virariam duas
    # empresas, e o usuário movido não enxergaria as carteiras da dele
    empresa_id = empresa_id.strip().lower()
    if not empresa_id:
        raise HTTPException(status_code=400, detail="empresa_id inválido.")
    db = get_db()
    res = db.table("usuarios").select("id, email, nome, role, empresa_id").eq("email", body.email.strip().lower()).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    u = res.data[0]
    if u.get("role") == "comando":
        raise HTTPException(status_code=403, detail="Não é possível mover um usuário COMANDO para uma empresa.")
    db.table("usuarios").update({"empresa_id": empresa_id}).eq("id", u["id"]).execute()
    _registrar_auditoria(acao="usuario_movido_para_empresa", entidade="usuario", entidade_id=u["id"],
                         usuario_email=payload.get("email", ""), empresa_id=empresa_id, usuario_id=payload.get("sub", ""),
                         detalhes={"email_alvo": u.get("email"), "empresa_anterior": u.get("empresa_id") or ""})
    return {"ok": True, "usuario": {**u, "empresa_id": empresa_id}}


@app.delete("/empresas/{empresa_id}")
def deletar_empresa(empresa_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    db = get_db()
    membros = db.table("usuarios").select("id, role").eq("empresa_id", empresa_id).execute()
    for u in (membros.data or []):
        if u.get("role") == "comando":
            raise HTTPException(status_code=400, detail="Não é possível excluir empresa com usuário COMANDO.")
    db.table("usuarios").update({"empresa_id": ""}).eq("empresa_id", empresa_id).execute()
    _registrar_auditoria(acao="empresa_esvaziada", entidade="empresa", entidade_id=empresa_id,
                         usuario_email=payload.get("email", ""), empresa_id=empresa_id, usuario_id=payload.get("sub", ""),
                         detalhes={"usuarios_removidos": len(membros.data or [])})
    return {"ok": True, "removidos": len(membros.data or [])}

@app.delete("/empresas/{empresa_id}/usuarios/{usuario_id}")
def remover_usuario_empresa(empresa_id: str, usuario_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    db = get_db()
    chk = db.table("usuarios").select("role").eq("id", usuario_id).limit(1).execute()
    if chk.data and chk.data[0].get("role") == "comando":
        raise HTTPException(status_code=403, detail="Não é possível remover um usuário COMANDO.")
    db.table("usuarios").update({"empresa_id": ""}).eq("id", usuario_id).execute()
    _registrar_auditoria(acao="usuario_removido_da_empresa", entidade="usuario", entidade_id=usuario_id,
                         usuario_email=payload.get("email", ""), empresa_id=empresa_id, usuario_id=payload.get("sub", ""),
                         detalhes={})
    return {"ok": True}


# ── Branding / configuração visual por empresa ────────────────────────────────

class EmpresaConfigIn(BaseModel):
    nome_exibicao: Optional[str] = Field(None, max_length=80)
    # cor em #rrggbb: o valor vai para o estilo da tela de todos da empresa
    cor_primaria: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    # Flags/preferências extras (ex: {"permitir_upload_db": true}). Mescladas, nunca substituídas por inteiro.
    extra: Optional[dict] = None


def _get_empresa_config(empresa_id: str) -> dict:
    """Retorna a config de branding de uma empresa, com fallback."""
    if not empresa_id:
        return {"nome_exibicao": "Mizan", "foto_url": None, "cor_primaria": None, "extra": {}, "empresa_id": None}
    db = get_db()
    cfg_res = db.table("empresa_config").select("*").eq("empresa_id", empresa_id).limit(1).execute()
    if cfg_res.data:
        c = cfg_res.data[0]
        return {
            "empresa_id": empresa_id,
            "nome_exibicao": c.get("nome_exibicao") or empresa_id,
            "foto_url": c.get("foto_url"),
            "cor_primaria": c.get("cor_primaria") or "#1d4ed8",
            "extra": c.get("extra") or {},
        }
    return {"empresa_id": empresa_id, "nome_exibicao": empresa_id, "foto_url": None, "cor_primaria": "#1d4ed8", "extra": {}}


@app.get("/empresa/config-publica")
def get_empresa_config_publica(empresa_id: Optional[str] = None):
    """Branding público de uma empresa (sem autenticação), para o login do link
    `?empresa=`. Devolve só nome, logo e cor.

    Antes aceitava `?email=` e respondia com o branding da empresa dona dele: um
    oráculo que dizia, para qualquer endereço, se havia conta e de qual empresa.
    O parâmetro foi removido; um cliente antigo que ainda o envie recebe o
    branding genérico, idêntico para existente e inexistente. Também não devolve
    `extra` (flags internas da empresa), que ali não tem uso.
    """
    cfg = _get_empresa_config(empresa_id or "")
    return {k: cfg.get(k) for k in ("empresa_id", "nome_exibicao", "foto_url", "cor_primaria")}


_MARCAS_CACHE: dict = {}


def _marcas_por_dominio() -> dict:
    """{domínio: marca} de todas as empresas, guardado por 5 minutos."""
    import time as _t
    if _MARCAS_CACHE.get("expira", 0) > _t.time():
        return _MARCAS_CACHE["mapa"]
    mapa = {}
    for c in get_db().table("empresa_config").select("empresa_id, nome_exibicao, foto_url, cor_primaria, extra").execute().data or []:
        for d in (c.get("extra") or {}).get("dominios_email") or []:
            mapa[d] = {"nome_exibicao": c.get("nome_exibicao") or c.get("empresa_id"),
                       "foto_url": c.get("foto_url"), "cor_primaria": c.get("cor_primaria")}
    _MARCAS_CACHE.update(mapa=mapa, expira=_t.time() + 300)
    return mapa


@app.get("/empresa/marca")
def marca_por_email(email: str = ""):
    """Marca da empresa para o login, pelo domínio do e-mail (ver marca.py).

    Sem login. Responde igual para quem tem conta e para quem não tem, e não
    devolve o id da empresa nem as configurações internas.
    """
    import marca as _marca
    dominio = _marca.dominio_do_email(email)
    vazio = {"empresa": None}
    if not dominio or dominio in _marca.DOMINIOS_PUBLICOS:
        return vazio
    try:
        achada = _marcas_por_dominio().get(dominio)
    except Exception:
        return vazio                       # sem banco, o login segue com a marca do Mizan
    return {"empresa": achada} if achada else vazio


class DominiosIn(BaseModel):
    dominios: list = Field(default_factory=list)


@app.get("/comando/empresas/{empresa_id}/dominios")
def comando_ver_dominios(empresa_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    empresa = empresa_id.strip().lower()
    return {"empresa_id": empresa, "dominios": (_get_empresa_config(empresa).get("extra") or {}).get("dominios_email") or []}


@app.put("/comando/empresas/{empresa_id}/dominios")
def comando_dominios_da_empresa(empresa_id: str, body: DominiosIn,
                                credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Domínios de e-mail da empresa, para a marca no login. Só o COMANDO: um
    cliente que cadastrasse o domínio de outro passaria a aparecer no login dele."""
    payload = _exigir_comando(credentials)
    import marca as _marca
    empresa = empresa_id.strip().lower()
    limpos, erro = _marca.validar_dominios(body.dominios)
    if erro:
        raise HTTPException(status_code=422, detail=erro)
    db = get_db()
    for c in db.table("empresa_config").select("empresa_id, extra").execute().data or []:
        if (c.get("empresa_id") or "") == empresa:
            continue
        repetidos = set(limpos) & set((c.get("extra") or {}).get("dominios_email") or [])
        if repetidos:
            raise HTTPException(status_code=409, detail=f"{', '.join(sorted(repetidos))} já é de outra empresa ({c.get('empresa_id')}).")
    atual = _get_empresa_config(empresa).get("extra") or {}
    novo = {**atual, "dominios_email": limpos}
    updates = {"extra": novo, "updated_by": payload.get("email", ""), "updated_at": datetime.utcnow().isoformat()}
    existe = db.table("empresa_config").select("id").eq("empresa_id", empresa).limit(1).execute()
    if existe.data:
        db.table("empresa_config").update(updates).eq("empresa_id", empresa).execute()
    else:
        db.table("empresa_config").insert({"empresa_id": empresa, **updates}).execute()
    _MARCAS_CACHE.clear()
    _registrar_auditoria(acao="dominios_atualizados", entidade="empresa", entidade_id=empresa,
                         usuario_email=payload.get("email", ""), empresa_id=empresa, usuario_id=payload.get("sub", ""),
                         detalhes={"antes": atual.get("dominios_email") or [], "depois": limpos})
    return {"empresa_id": empresa, "dominios": limpos}


@app.get("/empresa/config")
def get_empresa_config(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    return _get_empresa_config(payload.get("empresa_id", ""))


@app.put("/empresa/config")
def put_empresa_config(body: EmpresaConfigIn, empresa_id_alvo: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    role = payload.get("role", "operador")
    if role not in ("admin", "comando"):
        raise HTTPException(status_code=403, detail="Apenas admin e comando podem editar configurações da empresa.")
    # Comando pode editar qualquer empresa via ?empresa_id_alvo=xxx
    if role == "comando" and empresa_id_alvo:
        empresa_id = empresa_id_alvo.strip().lower()
    else:
        empresa_id = payload.get("empresa_id", "")
    if not empresa_id:
        raise HTTPException(status_code=400, detail="Informe a empresa a configurar.")
    db = get_db()
    updates: dict = {"updated_by": payload.get("email", ""), "updated_at": datetime.utcnow().isoformat()}
    if body.nome_exibicao is not None:
        updates["nome_exibicao"] = body.nome_exibicao.strip()
    if body.cor_primaria is not None:
        updates["cor_primaria"] = body.cor_primaria.strip()
    if body.extra is not None:
        if "dominios_email" in body.extra:
            raise HTTPException(status_code=400, detail="Domínios de e-mail são definidos pelo COMANDO, em Usuários › empresa.")
        if "retencao" in body.extra and role != "comando":
            raise HTTPException(status_code=403, detail="O prazo de retenção é definido pelo COMANDO.")
        atual = _get_empresa_config(empresa_id).get("extra") or {}
        mesclado = {**atual, **body.extra}
        # As premissas (comissão, cessão, critério da fila...) têm limites: esta
        # rota genérica não pode ser o caminho para gravar um valor que a tela
        # de premissas recusaria.
        from model.premissas import PREMISSAS as _PREM, validar as _validar_prem
        _so_prem = {k: v for k, v in body.extra.items() if k in _PREM}
        if _so_prem:
            _limpos, _erros = _validar_prem(_so_prem)
            if _erros:
                raise HTTPException(status_code=400, detail="; ".join(f"{k}: {m}" for k, m in _erros.items()))
            mesclado = {**mesclado, **{k: v for k, v in _limpos.items() if v is not None}}
            for _k, _v in _limpos.items():
                if _v is None:
                    mesclado.pop(_k, None)
        # Um prazo de retenção inválido guardado aqui só apareceria na hora de
        # executar — quando já seria tarde para discutir. Recusa na gravação.
        if "retencao" in body.extra:
            from model.retencao import de_config as _retencao_de_config
            _pol = _retencao_de_config(mesclado)
            _erro = _pol.valida()
            if _erro:
                raise HTTPException(status_code=400, detail=_erro)
            if body.extra.get("retencao", {}).get("ativa") and not _pol.ativa:
                raise HTTPException(
                    status_code=400,
                    detail="Retenção ativa exige um prazo em dias: {\"retencao\": {\"ativa\": true, \"dias\": 365}}.")
        updates["extra"] = mesclado

    existing = db.table("empresa_config").select("id").eq("empresa_id", empresa_id).limit(1).execute()
    if existing.data:
        db.table("empresa_config").update(updates).eq("empresa_id", empresa_id).execute()
    else:
        db.table("empresa_config").insert({"empresa_id": empresa_id, **updates}).execute()

    _registrar_auditoria("config_empresa_atualizada", "empresa", empresa_id,
                         payload.get("email"), empresa_id, updates, payload["sub"])
    return _get_empresa_config(empresa_id)


def _empresa_das_premissas(payload: dict, alvo: "str | None") -> str:
    """Empresa cujas premissas se lê ou grava. Admin: a dele. Comando: a escolhida."""
    role = payload.get("role", "operador")
    if role not in ("admin", "comando"):
        raise HTTPException(status_code=403, detail="Apenas admin e comando acessam as premissas da empresa.")
    empresa = (alvo or "").strip().lower() if role == "comando" else payload.get("empresa_id", "")
    if not empresa:
        raise HTTPException(status_code=400, detail="Informe a empresa.")
    return empresa


@app.get("/empresa/premissas")
def get_premissas(empresa_id_alvo: Optional[str] = None,
                  credentials: HTTPAuthorizationCredentials = Security(bearer)):
    from model.premissas import descrever
    payload = _usuario_autenticado(credentials)
    empresa = _empresa_das_premissas(payload, empresa_id_alvo)
    return {"empresa_id": empresa, "premissas": descrever(_extra_empresa(empresa))}


class PremissasIn(BaseModel):
    # chave -> valor; null apaga e devolve ao padrão
    valores: dict


@app.put("/empresa/premissas")
def put_premissas(body: PremissasIn, empresa_id_alvo: Optional[str] = None,
                  credentials: HTTPAuthorizationCredentials = Security(bearer)):
    from model.premissas import aplicar, descrever, validar
    payload = _usuario_autenticado(credentials)
    empresa = _empresa_das_premissas(payload, empresa_id_alvo)
    limpos, erros = validar(body.valores)
    if erros:
        raise HTTPException(status_code=422, detail={"mensagem": "Há valores inválidos.", "erros": erros})
    db = get_db()
    # Leitura estrita: _extra_empresa devolve {} quando o banco falha, e gravar
    # por cima de {} apagaria o resto da configuração (retenção, por exemplo).
    try:
        lido = db.table("empresa_config").select("extra").eq("empresa_id", empresa).limit(1).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Não foi possível ler a configuração atual. Tente de novo.")
    antes = (lido.data or [{}])[0].get("extra") or {}
    depois = aplicar(antes, limpos)
    updates = {"extra": depois, "updated_by": payload.get("email", ""),
               "updated_at": datetime.utcnow().isoformat()}
    existente = db.table("empresa_config").select("id").eq("empresa_id", empresa).limit(1).execute()
    if existente.data:
        db.table("empresa_config").update(updates).eq("empresa_id", empresa).execute()
    else:
        db.table("empresa_config").insert({"empresa_id": empresa, **updates}).execute()
    _registrar_auditoria(
        acao="premissas_atualizadas", entidade="empresa", entidade_id=empresa,
        usuario_email=payload.get("email", ""), empresa_id=empresa, usuario_id=payload.get("sub", ""),
        detalhes={chave: {"antes": antes.get(chave), "depois": depois.get(chave)} for chave in limpos})
    return {"empresa_id": empresa, "premissas": descrever(depois)}


def _tipo_de_imagem(conteudo: bytes) -> "str | None":
    """Tipo da imagem pelos primeiros bytes (assinatura do formato)."""
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if conteudo[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    return None


@app.post("/empresa/foto")
async def upload_empresa_foto(file: UploadFile = File(...), empresa_id_alvo: Optional[str] = None, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    role = payload.get("role", "operador")
    if role not in ("admin", "comando"):
        raise HTTPException(status_code=403, detail="Apenas admin e comando podem alterar a foto da empresa.")
    if role == "comando" and empresa_id_alvo:
        empresa_id = empresa_id_alvo.strip().lower()
    else:
        empresa_id = payload.get("empresa_id", "")
    if not empresa_id:
        raise HTTPException(status_code=400, detail="Informe a empresa a configurar.")

    conteudo = await file.read()

    def _processar():
        if len(conteudo) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Foto muito grande. Máximo: 5 MB.")
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            raise HTTPException(status_code=400, detail="Formato não suportado. Use JPG, PNG ou WebP.")
        # O tipo vem do conteúdo, não do que o navegador declarou: um HTML com
        # nome "logo.png" e content-type text/html ficaria num bucket público
        # servido como página.
        tipo = _tipo_de_imagem(conteudo)
        if tipo is None:
            raise HTTPException(status_code=400, detail="O arquivo não é uma imagem JPG, PNG, WebP ou GIF válida.")

        db = get_db()
        caminho = f"empresa-fotos/{empresa_id}.{ext}"
        try:
            db.storage.from_("mizan-public").upload(
                caminho, conteudo,
                {"content-type": tipo, "upsert": "true"},
            )
            foto_url = db.storage.from_("mizan-public").get_public_url(caminho)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao salvar foto: {e}")

        updates = {"foto_url": foto_url, "updated_by": payload.get("email", ""), "updated_at": datetime.utcnow().isoformat()}
        existing = db.table("empresa_config").select("id").eq("empresa_id", empresa_id).limit(1).execute()
        if existing.data:
            db.table("empresa_config").update(updates).eq("empresa_id", empresa_id).execute()
        else:
            db.table("empresa_config").insert({"empresa_id": empresa_id, **updates}).execute()

        _registrar_auditoria("foto_empresa_atualizada", "empresa", empresa_id,
                             payload.get("email"), empresa_id, {"foto_url": foto_url}, payload["sub"])
        return {"ok": True, "foto_url": foto_url}

    # Upload para o storage e gravação no Supabase são bloqueantes.
    return await asyncio.to_thread(_processar)


@app.get("/conexoes/{conexao_id}/permissoes")
def listar_permissoes_conexao(conexao_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    _exigir_conexao_da_empresa(db, conexao_id, payload)
    perm = db.table("conexao_permissoes").select("operador_id").eq("conexao_id", conexao_id).execute()
    ids = [p["operador_id"] for p in (perm.data or [])]
    if not ids:
        return []
    operadores = db.table("usuarios").select("id, nome, email, role, ativo").in_("id", ids).execute()
    return operadores.data or []


@app.post("/conexoes/{conexao_id}/permissoes/{operador_id}")
def conceder_permissao_conexao(conexao_id: str, operador_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    conexao = _exigir_conexao_da_empresa(db, conexao_id, payload)
    # Só se libera a quem é da mesma empresa da conexão: sem isso, o admin de uma
    # empresa dava a um usuário de outra acesso à conexão da sua.
    alvo = db.table("usuarios").select("empresa_id").eq("id", operador_id).limit(1).execute()
    if not alvo.data or (alvo.data[0].get("empresa_id") or "") != (conexao.get("empresa_id") or ""):
        raise HTTPException(status_code=400, detail="O usuário precisa ser da mesma empresa da conexão.")
    existing = db.table("conexao_permissoes").select("id").eq("conexao_id", conexao_id).eq("operador_id", operador_id).execute()
    if not existing.data:
        db.table("conexao_permissoes").insert({"conexao_id": conexao_id, "operador_id": operador_id}).execute()
    return {"ok": True}


@app.delete("/conexoes/{conexao_id}/permissoes/{operador_id}")
def revogar_permissao_conexao(conexao_id: str, operador_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_admin_ou_comando(credentials)
    db = get_db()
    _exigir_conexao_da_empresa(db, conexao_id, payload)
    db.table("conexao_permissoes").delete().eq("conexao_id", conexao_id).eq("operador_id", operador_id).execute()
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
        conn.sheets_credenciais = _credencial_sheets_salva(row)
        if not conn.sheets_credenciais:
            raise ValueError("Conexão Sheets salva sem a credencial da conta de serviço. "
                             "Edite a conexão e cole o JSON da credencial.")
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
            engine = create_engine(url, connect_args=_external_connect_args(conn))
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
        updates = {"ultimo_sync": datetime.utcnow().isoformat(), "ultimo_sync_por": uemail or ""}
        if nova_carteira_id and not carteira_id_existente:
            updates["carteira_id"] = nova_carteira_id
        db.table("conexoes_db").update(updates).eq("id", conexao_id).execute()
    except Exception:
        pass
    _registrar_auditoria(
        acao="banco_sincronizado",
        entidade="conexao",
        entidade_id=conexao_id,
        usuario_email=uemail,
        empresa_id=eid,
        detalhes={"n_devedores": resultado.get("resumo", {}).get("total_devedores", 0)},
    )

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
    """Job do scheduler: sincroniza todas as conexões cujo intervalo configurado já passou."""
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

    from datetime import timedelta
    agora_dt = datetime.now(timezone.utc)

    def _deve_sincronizar(r: dict) -> bool:
        if not (r.get("query") or r.get("tipo") == "sheets"):
            return False
        intervalo_h = float(r.get("intervalo_sync_horas") or 1.0)
        ultimo = r.get("ultimo_sync")
        if not ultimo:
            return True
        try:
            ultimo_dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
            if ultimo_dt.tzinfo is None:
                ultimo_dt = ultimo_dt.replace(tzinfo=timezone.utc)
            return (agora_dt - ultimo_dt) >= timedelta(hours=intervalo_h)
        except Exception:
            return True

    ativas = [r for r in rows if _deve_sincronizar(r)]
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
    payload = _usuario_autenticado(credentials)

    db = get_db()
    eid = payload.get("empresa_id", "")
    uid = payload["sub"]
    role = payload.get("role", "operador")
    res = db.table("conexoes_db").select("*").eq("id", conexao_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")
    r = res.data[0]

    if role == "comando":
        pass  # comando vê tudo
    elif role == "admin":
        tem_acesso = (eid and r.get("empresa_id") == eid) or r.get("usuario_id") == uid
        if not tem_acesso:
            perm = db.table("conexao_permissoes").select("id").eq("conexao_id", conexao_id).eq("operador_id", uid).execute()
            tem_acesso = bool(perm.data)
        if not tem_acesso:
            raise HTTPException(status_code=403, detail="Acesso negado.")
    else:
        # Operador precisa de permissão explícita
        perm = db.table("conexao_permissoes").select("id").eq("conexao_id", conexao_id).eq("operador_id", uid).execute()
        if not perm.data:
            raise HTTPException(status_code=403, detail="Sem permissão para sincronizar esta conexão.")

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
    try:
        ok = redefinir_senha_com_token(body.token, body.nova_senha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite um novo.")
    return {"ok": True}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/carteiras")
def listar_carteiras(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    usuario_id = payload.get("sub")
    empresa_id = payload.get("empresa_id", "")
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


# Os mesmos cortes de frontend/src/utils/prioridade.js. Prioridade é posição na
# fila, não faixa de score: "Alta" é o topo que cabe num ciclo de cobrança.
CORTE_ALTA_FILA  = 0.20
CORTE_MEDIA_FILA = 0.50


def _faixa_de_ranks(prioridade: str, total: int) -> "tuple[int, int] | None":
    """Converte a etiqueta de prioridade no intervalo de posições que ela cobre.

    Filtrar por prioridade sem trazer a carteira inteira só é possível porque a
    etiqueta é uma função da posição: ela vira um recorte de rank, que o banco
    resolve com o índice.
    """
    if total <= 0:
        return None
    # O front compara rank/total <= corte. A forma inteira equivalente é
    # rank*100 <= corte*100*total, e ela evita o arredondamento binário que
    # faria as duas implementações discordarem na fronteira. Arredondar para
    # cima aqui (ceil) classificava o 2º de uma fila de 7 como Alta, enquanto a
    # tela dizia Média.
    alta  = (total * int(CORTE_ALTA_FILA * 100)) // 100
    media = (total * int(CORTE_MEDIA_FILA * 100)) // 100
    return {
        "Alta":  (1, alta),
        "Média": (alta + 1, media),
        "Baixa": (media + 1, total),
    }.get(prioridade)


def _valores_de_filtro(db, carteira_id: str) -> dict:
    """Produtos e UFs distintos da carteira, para os seletores da tela.

    A tela montava essas listas percorrendo o ranking inteiro. Sem o ranking
    inteiro no navegador, elas passam a vir daqui — e são duas colunas curtas,
    não a carteira toda.
    """
    try:
        linhas = _todas_as_linhas(
            lambda: db.table("predicoes").select("produto, uf").eq("carteira_id", carteira_id))
    except Exception:
        return {"produtos": [], "ufs": []}
    return {
        "produtos": sorted({p["produto"] for p in linhas if p.get("produto")}),
        "ufs":      sorted({p["uf"] for p in linhas if p.get("uf")}),
    }


@app.get("/carteiras/{carteira_id}/alcance")
def alcance_da_operacao(
    carteira_id: str,
    capacidade: int = 0,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Quanto vale o topo da fila que a equipe consegue trabalhar no ciclo.

    A fila está ordenada por valor esperado, então o alcance de uma capacidade
    é a soma acumulada dos N primeiros. É o número que o gerente leva para a
    reunião, então é somado de verdade — não interpolado numa curva amostrada.
    Uma coluna só atravessa a rede, não a carteira.
    """
    payload = _usuario_autenticado(credentials)
    db = get_db()
    _exige_carteira_da_empresa(db, carteira_id, payload)

    total = (db.table("predicoes").select("id", count="exact")
             .eq("carteira_id", carteira_id).limit(1).execute()).count or 0
    n = max(0, min(total, int(capacidade or 0)))
    if not n:
        return {"n": 0, "ate": 0, "valor": 0.0, "pct": None, "pctBase": 0.0,
                "restam": total, "total_devedores": total}

    # .limit(n) não basta: acima de mil o servidor corta e o alcance sairia
    # menor do que é — justamente o número que vai para a reunião.
    linhas = _todas_as_linhas(
        lambda: db.table("predicoes").select("rank, valor_esperado_recuperacao, valor_esperado_liquido")
                  .eq("carteira_id", carteira_id).order("rank"),
        lote=min(n, LOTE_LEITURA))[:n]
    ate = max((int(l.get("rank") or 0) for l in linhas), default=n)
    bruto = sum(float(l.get("valor_esperado_recuperacao") or 0) for l in linhas)

    total_ver = (db.table("carteiras").select("valor_esperado")
                 .eq("id", carteira_id).limit(1).execute())
    ver = float((total_ver.data or [{}])[0].get("valor_esperado") or 0)

    # A fila é ordenada pelo LÍQUIDO (o que sobra para o banco depois da
    # comissão da fase), então o alcance soma o líquido, contra o líquido da
    # carteira inteira (achado D5). Carteiras analisadas antes do líquido não o
    # têm gravado: aí vale o bruto, e o campo `base` diz qual foi.
    if any(l.get("valor_esperado_liquido") is not None for l in linhas):
        soma = sum(float(l.get("valor_esperado_liquido") if l.get("valor_esperado_liquido") is not None
                         else l.get("valor_esperado_recuperacao") or 0) for l in linhas)
        chave = f"alcance_liq:{carteira_id}:{ver}"
        total_valor = _cache_get(chave, 600)
        if total_valor is None:
            todas = _todas_as_linhas(lambda: db.table("predicoes")
                                     .select("id, valor_esperado_liquido, valor_esperado_recuperacao")
                                     .eq("carteira_id", carteira_id))
            total_valor = sum(float(l.get("valor_esperado_liquido") if l.get("valor_esperado_liquido") is not None
                                    else l.get("valor_esperado_recuperacao") or 0) for l in todas)
            _cache_set(chave, total_valor)
        base = "liquido"
    else:
        soma, total_valor, base = bruto, ver, "bruto"

    return {
        "n": n,
        "ate": ate,
        "valor": round(soma, 2),
        "valor_bruto": round(bruto, 2),
        "total": round(total_valor, 2),
        "base": base,
        # Sem o total da carteira não dá para dizer que fração é essa; devolver
        # 0 seria inventar um número, então o campo fica nulo e a tela decide.
        "pct": round(soma / total_valor * 100, 2) if total_valor > 0 else None,
        "pctBase": round(n / total * 100, 2) if total else 0.0,
        "restam": total - n,
        "total_devedores": total,
    }


@app.get("/carteiras/{carteira_id}/ranking")
def pagina_do_ranking(
    carteira_id: str,
    offset: int = 0,
    limit: int = 50,
    busca: Optional[str] = None,
    produto: Optional[str] = None,
    uf: Optional[str] = None,
    prioridade: Optional[str] = None,
    status: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Uma página da fila, já filtrada, sem trazer a carteira inteira.

    A resposta de /carteiras/{id} carrega o ranking completo: 581 bytes por
    devedor em JSON, ou seja 29 MB para 50 mil e 116 MB para 200 mil. A tabela
    mostra 50 por vez. Esta rota entrega as 50.

    O filtro por status vem dos feedbacks, que ficam em outra tabela e não dão
    para juntar no PostgREST. Ele é aplicado por lista de CPF — o conjunto é
    limitado por quantas pessoas foram efetivamente trabalhadas, que é ordem de
    grandeza menor que a carteira.
    """
    payload = _usuario_autenticado(credentials)
    db = get_db()
    _exige_carteira_da_empresa(db, carteira_id, payload)

    limit  = min(max(limit, 1), 500)
    offset = max(offset, 0)

    def base():
        return db.table("predicoes").select("*", count="exact").eq("carteira_id", carteira_id)

    # Total da carteira: é o denominador da etiqueta de prioridade, e precisa
    # ser o da fila inteira — não o do resultado filtrado, senão filtrar por
    # produto reclassificaria a prioridade de quem sobrou.
    total = (db.table("predicoes").select("id", count="exact")
             .eq("carteira_id", carteira_id).limit(1).execute()).count or 0

    vazio = {"itens": [], "total": total, "filtrado": 0, "offset": offset, "limit": limit}
    faixa = None
    if prioridade:
        faixa = _faixa_de_ranks(prioridade, total)
        if faixa is None:
            return vazio

    def filtrar(q):
        if produto:
            q = q.eq("produto", produto)
        if uf:
            q = q.eq("uf", uf)
        if busca:
            alvo = busca.strip().replace("*", "").replace(",", "")
            if alvo:
                q = q.or_(f"nome.ilike.*{alvo}*,cpf.ilike.*{alvo}*")
        if faixa:
            q = q.gte("rank", faixa[0]).lte("rank", faixa[1])
        return q

    if status in ("pago", "nao_pago", "pendente"):
        # O status é decidido aqui, e não com uma lista de CPFs na consulta: com
        # milhares de feedbacks a URL estoura. Lê só id/cpf/rank da fila já
        # filtrada, escolhe a página e busca as linhas completas só dela.
        pagos, nao_pagos = _cpfs_por_status(db, carteira_id)
        if status == "pago":
            quer = lambda c: c in pagos
        elif status == "nao_pago":
            quer = lambda c: c in nao_pagos
        else:
            quer = lambda c: c not in pagos and c not in nao_pagos
        leves = _todas_as_linhas(lambda: filtrar(
            db.table("predicoes").select("id, cpf, rank").eq("carteira_id", carteira_id)))
        certos = sorted((l for l in leves if quer(l["cpf"])), key=lambda l: (l.get("rank") is None, l.get("rank") or 0, l["id"]))
        pagina = [l["id"] for l in certos[offset:offset + limit]]
        linhas = []
        for i in range(0, len(pagina), ITENS_POR_IN):
            linhas += db.table("predicoes").select("*").in_("id", pagina[i:i + ITENS_POR_IN]).execute().data or []
        linhas.sort(key=lambda r: (r.get("rank") is None, r.get("rank") or 0, r["id"]))
        return _sem_nan({
            "itens": _reconstruir_ranking(linhas, payload.get("empresa_id", "")),
            "total": total, "filtrado": len(certos), "offset": offset, "limit": limit,
        })

    q = filtrar(base())
    res = q.order("rank").range(offset, offset + limit - 1).execute()
    itens = _reconstruir_ranking(res.data or [], payload.get("empresa_id", ""))

    # Um NaN gravado numa coluna numérica derrubava a resposta inteira (500) e
    # a tabela aparecia vazia.
    return _sem_nan({
        "itens": itens,
        "total": total,
        "filtrado": res.count if res.count is not None else len(itens),
        "offset": offset,
        "limit": limit,
    })


def _cpfs_por_status(db, carteira_id: str) -> "tuple[set, set]":
    """CPFs com feedback nesta carteira, separados entre quem pagou e quem não.

    O escopo vem das predições da própria carteira, como em /feedbacks/status:
    é o que impede a consulta de alcançar feedback de outra empresa. Quem
    chama já validou a carteira com _exige_carteira_da_empresa.

    Só o feedback mais recente de cada CPF conta — um devedor pode ter sido
    marcado como não pago e ter pago depois.
    """
    pred_ids = [p["id"] for p in _todas_as_linhas(
        lambda: db.table("predicoes").select("id").eq("carteira_id", carteira_id))]
    if not pred_ids:
        return set(), set()

    linhas = _feedbacks_das_predicoes(db, "cpf, pagou, created_at", pred_ids)

    visto, pagos, nao_pagos = set(), set(), set()
    for f in linhas:                      # já vem do mais recente para o mais antigo
        cpf = str(f.get("cpf") or "")
        if not cpf or cpf in visto:
            continue
        visto.add(cpf)
        (pagos if f.get("pagou") else nao_pagos).add(cpf)
    return pagos, nao_pagos


def _reconstruir_ranking(predicoes: list, empresa_id: "str | None") -> list:
    """Devolve a carteira na ordem da fila, com o rank de cada devedor.

    A posição de um devedor é resultado da política de priorização da empresa
    sobre o valor esperado líquido — não do score. Reabrir a carteira ordenando
    por score desfazia a decisão inteira: numa carteira de teste, 1 em cada 20
    devedores ficava na mesma posição e 11 em 20 mudavam de faixa de
    prioridade. O rank agora é gravado na análise e é ele que manda.

    Carteiras analisadas antes dessa gravação não têm rank. Para elas a ordem é
    recomputada aqui com a mesma política — o que reproduz a intenção, embora
    não necessariamente o que o usuário viu na época, já que a política pode
    ter mudado desde então.
    """
    if any(p.get("rank") is not None for p in predicoes):
        # Já vem ordenado do banco; as poucas linhas sem rank (gravadas antes do
        # ALTER TABLE) vão para o fim em vez de embaralhar o começo da fila.
        ordenadas = sorted(
            predicoes,
            key=lambda p: (p.get("rank") is None, p.get("rank") or 0),
        )
    else:
        import numpy as _np
        from model.priorizacao import de_config as _criterio_de_config, ordenar as _ordenar_fila

        def _valor(p):
            for campo in ("valor_esperado_liquido", "valor_esperado_recuperacao"):
                v = p.get(campo)
                if v is not None:
                    return float(v)
            # Sem nenhum valor gravado sobra o score, que é o que o sistema
            # antigo usava — pior, porém melhor do que ordem arbitrária.
            return float(p.get("score_recuperabilidade") or 0)

        ve = _np.array([_valor(p) for p in predicoes], dtype=float)
        ufs = [p.get("uf") for p in predicoes]
        idx = _ordenar_fila(ve, _np.ones(len(ve)), pd.Series(ufs),
                            _criterio_de_config(_extra_empresa(empresa_id)))
        ordenadas = [predicoes[i] for i in idx]

    ranking = []
    for posicao, p in enumerate(ordenadas, start=1):
        d = {**p, "rank": p.get("rank") or posicao}
        if d.get("valor_esperado_recuperacao") is None and d.get("valor_divida") and d.get("score_recuperabilidade"):
            d["valor_esperado_recuperacao"] = round(
                d["score_recuperabilidade"] / 100 * d["valor_divida"], 2
            )
        ranking.append(d)
    return ranking


@app.get("/carteiras/{carteira_id}")
def carregar_carteira(carteira_id: str, incluir_ranking: bool = True,
                      credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Abre uma carteira gravada.

    `incluir_ranking=false` devolve tudo menos a fila — 581 bytes por devedor,
    ou 29 MB numa carteira de 50 mil. A tela pede assim e busca as 50 linhas
    visíveis em /carteiras/{id}/ranking. O padrão continua mandando a fila
    inteira porque há integrações por API key consumindo este formato, e mudar
    isso em silêncio quebraria o cliente do outro lado.
    """
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    usuario_id = payload.get("sub")
    db = get_db()

    q = db.table("carteiras").select("*").eq("id", carteira_id)
    if empresa_id:
        q = q.eq("empresa_id", empresa_id)
    elif usuario_id:
        q = q.eq("usuario_id", usuario_id)
    cart_res = q.execute()
    if not cart_res.data:
        raise HTTPException(status_code=404, detail="Carteira não encontrada.")

    predicoes = _todas_as_linhas(
        lambda: db.table("predicoes").select("*").eq("carteira_id", carteira_id).order("rank"))
    if not predicoes:
        raise HTTPException(status_code=404, detail="Nenhuma predição encontrada para esta carteira.")

    ranking = _reconstruir_ranking(predicoes, empresa_id)

    # Resumo
    total_face = sum((d.get("valor_divida") or 0) for d in ranking)
    total_ver  = sum((d.get("valor_esperado_recuperacao") or 0) for d in ranking)
    scores     = [d["score_recuperabilidade"] for d in ranking if d.get("score_recuperabilidade") is not None]
    _cart_row  = cart_res.data[0]
    resumo = {
        "carteira_id": carteira_id,
        "total_devedores": len(ranking),
        "total_em_risco": round(total_face, 2),
        "score_medio": round(sum(scores) / len(scores), 1) if scores else 0,
        "valor_esperado_recuperacao_total": round(total_ver, 2),
        "taxa_recuperacao_esperada": round(total_ver / total_face * 100, 1) if total_face else 0,
        "criado_por": _cart_row.get("usuario_email") or "",
        "criado_em":  _cart_row.get("created_at") or "",
        **_valores_de_filtro(db, carteira_id),
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
        **({"ranking_completo": ranking} if incluir_ranking else {}),
    }


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...),
                     credentials: HTTPAuthorizationCredentials = Security(bearer)):
    # Era a única rota de trabalho pesado sem credencial: qualquer um na internet
    # mandava um CSV de 100 MB para ser lido e interpretado, fora do limite de
    # taxa e do portão de análises. O frontend não a chama, e ela só devolve
    # nome, número de linhas e colunas — então exigir login não tira nada de quem
    # a usa de verdade.
    _usuario_autenticado(credentials)
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um CSV.")

    contents = await file.read()

    def _processar():
        try:
            df = _read_csv_auto(contents)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Erro ao processar CSV: {e}")
        return {
            "filename": file.filename,
            "rows": len(df),
            "columns": df.columns.tolist(),
        }

    # Parsear CSV é CPU-bound: fora do event loop, senão segura todo mundo.
    return await asyncio.to_thread(_processar)


@app.post("/backtest")
async def rodar_backtest(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Backtest de carteira histórica: o Mizan teria recuperado mais?

    Recebe uma carteira em que a cobrança já aconteceu e o desfecho é
    conhecido, pontua como se fosse antes e compara a fila que o Mizan
    formaria com a que a operação usa hoje.

    NÃO GRAVA NADA. A carteira histórica de um cliente entra para ser
    analisada, não para virar base: nenhuma carteira é criada, nenhuma
    predição é persistida, nenhum feedback é registrado. O resultado volta
    na resposta e morre ali.
    """
    payload = _usuario_autenticado(credentials)
    if payload.get("role") not in ("admin", "comando"):
        raise HTTPException(
            status_code=403,
            detail="Backtest é restrito a admin e comando: ele analisa a carteira "
                   "histórica de um cliente, fora do fluxo de cobrança.",
        )

    nome = (file.filename or "").lower()
    if not (nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Arquivo deve ser CSV ou Excel (.csv / .xlsx / .xls).")

    contents = await file.read()
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo muito grande. Limite: 25 MB.")

    def _processar():
        try:
            if nome.endswith(".csv"):
                df = _read_csv_auto(contents)
            else:
                df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Erro ao ler arquivo: {e}")

        from backtest import rodar
        try:
            resultado = rodar(df)
        except ValueError as e:
            # Coluna faltando ou carteira sem os dois desfechos: é erro de
            # entrada do usuário, e a mensagem já diz o que falta.
            raise HTTPException(status_code=422, detail=str(e))
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="Modelos não encontrados no servidor.")
        resultado["arquivo"] = file.filename
        return resultado

    # Pontuar a carteira inteira é trabalho pesado: fora do event loop.
    return await asyncio.to_thread(_processar)


@app.post("/analisar")
async def analisar(
    file: UploadFile = File(...),
    empresa_id: Optional[str] = Form(None),
    incluir_ranking: bool = True,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Analisa uma carteira.

    `incluir_ranking=false` devolve tudo menos a fila, que a tela busca depois
    em páginas. O padrão continua mandando a fila inteira: há integrações por
    API key consumindo este formato.
    """
    payload = _usuario_autenticado(credentials)
    uid   = payload.get("sub")
    uemail = payload.get("email")
    eid   = payload.get("empresa_id", "")
    # COMANDO pode especificar a empresa destino da análise
    if payload.get("role") == "comando" and empresa_id:
        eid = empresa_id.strip().lower()

    nome = (file.filename or "").lower()
    if not (nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Arquivo deve ser CSV ou Excel (.xlsx / .xls).")

    contents = await file.read()
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo muito grande. Limite: 25 MB.")

    def _processar():
        try:
            if nome.endswith(".csv"):
                df = _read_csv_auto(contents)
            else:
                df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Erro ao ler arquivo: {e}")
        return _analisar_df(df, file.filename, _usuario_id=uid, _usuario_email=uemail, _empresa_id=eid,
                            _incluir_ranking=incluir_ranking)

    # O caminho pesado do sistema: ler a planilha, pontuar a carteira inteira e
    # gravar as predições. Segundos de trabalho bloqueante numa carteira grande
    # — no event loop, congelaria todas as outras requisições até terminar.
    return await asyncio.to_thread(_processar)


def _external_connect_args(conn: ConexaoDB) -> dict:
    """connect_args para bancos externos: timeout + TLS obrigatório em conexões remotas.

    Evita que credenciais e dados de devedores trafeguem em texto claro pela rede.
    - Postgres: TLS é forçado via sslmode=require na própria URL (ver _construir_url_db).
    - MySQL/MariaDB: pymysql ativa TLS quando 'ssl' é um dict não-vazio.
    Conexões a localhost são isentas (o tráfego não sai da máquina).
    """
    args: dict = {}
    tipo = conn.tipo
    host = (conn.host or "").lower()
    local = host in ("localhost", "127.0.0.1", "::1", "")
    if tipo in ("postgres", "postgresql", "mysql", "mariadb"):
        args["connect_timeout"] = 10
    if not local and tipo in ("mysql", "mariadb"):
        args["ssl"] = {"check_hostname": False}
    return args


def _validar_destino_externo(conn: ConexaoDB) -> None:
    """Recusa destinos que não podem ser o banco de um cliente.

    A tela de conexões existe para o cliente apontar o próprio banco, que está
    na rede dele. Sem validação nenhuma, ela aceitava duas coisas que nunca
    são isso:

    SQLite — `sqlite:///{caminho}` abre um arquivo do SERVIDOR, não da máquina
    do cliente. Hospedado, "arquivo local" não existe do lado de cá: o que dá
    para alcançar é caminho do container. Pior, o driver CRIA o arquivo quando
    não existe, então virava também escrita em caminho arbitrário.

    Endereço interno — o Mizan conecta saindo para a internet, então um IP de
    loopback, privado ou de link-local jamais é o banco do cliente; é a rede
    de dentro. Somado à consulta livre que a mesma tela aceita, seria leitura
    de serviço interno.

    Em desenvolvimento (sem Supabase configurado) nada disso vale: apontar
    para o Postgres da própria máquina é o fluxo normal de quem está
    programando.
    """
    if not os.getenv("SUPABASE_URL"):
        return

    if (conn.tipo or "").lower() == "sqlite":
        raise HTTPException(
            status_code=400,
            detail="Conexão SQLite não é possível no serviço hospedado: o arquivo "
                   "precisaria estar no servidor do Mizan, não na sua máquina. "
                   "Exporte os dados para CSV ou use uma conexão de rede "
                   "(PostgreSQL, MySQL, SQL Server, Oracle ou Google Sheets).",
        )

    host = (conn.host or "").strip()
    if not host:
        return

    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Host não encontrado: {host}")

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        # Nota: o driver resolve o nome de novo na hora de conectar, então um
        # DNS que responda diferente entre as duas consultas fura esta checagem.
        # Cobrir isso exigiria fixar o IP resolvido aqui na conexão, o que os
        # drivers não expõem de forma uniforme.
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise HTTPException(
                status_code=400,
                detail=f"Endereço {ip} é de rede interna e não pode ser o destino "
                       "de uma conexão. Informe o endereço público do seu banco.",
            )


def _construir_url_db(conn: ConexaoDB) -> str:
    """Monta a connection string do SQLAlchemy a partir dos parâmetros."""
    from urllib.parse import quote_plus

    _validar_destino_externo(conn)

    if conn.tipo == "sqlite":
        if not conn.banco:
            raise ValueError("Caminho do arquivo SQLite não configurado.")
        return f"sqlite:///{conn.banco}"

    host = conn.host or ""
    if not host and conn.tipo not in ("sqlite",):
        raise ValueError("Host não configurado para esta conexão.")
    if not conn.banco and conn.tipo not in ("oracle",):
        raise ValueError("Nome do banco de dados não configurado.")

    host  = host or "localhost"
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
        if not dsn:
            raise ValueError("Nome do serviço Oracle (service_name) ou banco não configurado.")
        return f"oracle+oracledb://{user}:{senha}@{host}:{porta}/?service_name={dsn}"

    raise ValueError(f"Tipo de banco não suportado: {conn.tipo}")


def _sqlserver_connect(conn: ConexaoDB):
    """Retorna conexão pytds para SQL Server (sem SQLAlchemy)."""
    import pytds
    # Não passa por _construir_url_db, então a validação de destino é aqui.
    _validar_destino_externo(conn)
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


# Premissa: quanto do saldo devedor entra quando o devedor efetivamente paga.
# 1.0 = pagamento integral. É o que o sistema já assumia de forma implícita ao
# usar score/100 como taxa de recuperação; agora fica declarado, visível e
# ajustável por empresa em empresa_config.extra.recuperacao_se_pagar.
#
# Não há valor "de mercado" chutado aqui de propósito: enquanto a empresa não
# declarar o seu, vale 1.0 e a interface mostra que é premissa, não medição.
PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO = 1.0


def _psi_da_carteira(scores: list, empresa_id: "str | None" = None) -> dict:
    """PSI desta carteira contra a distribuição de score congelada no treino.

    Roda a cada análise porque é aí que existe a população atual. Nunca derruba
    a análise: sem referência utilizável, devolve o motivo e a tela mostra isso
    em vez de um número.
    """
    try:
        from model.psi import calcular
        from model.score import _carregar_modelos
        # Usa o cache de modelos do score.py em vez de reler scaler.pkl do
        # disco: a análise já carregou esses artefatos para pontuar a carteira.
        # A referência do PSI é a do modelo que pontuou: o da empresa, se houver.
        _, _, meta = _carregar_modelos(empresa_id)
        return calcular(scores, meta.get("psi_referencia"))
    except Exception as e:
        return {"ok": False, "motivo": f"Não foi possível calcular o PSI: {e}"}


# Colunas de predicoes acrescentadas depois que o sistema já estava no ar. Não
# há migração automática no boot: o ALTER TABLE de sql/schema.sql é rodado à
# mão no Supabase. Se o código subir antes do SQL, o insert inteiro falharia e
# nenhuma análise seria gravada — perder o enriquecimento é ruim, perder a
# carteira é bem pior. Aqui a gravação cai para o conjunto antigo de colunas e
# avisa no log, em vez de derrubar a análise.
_COLUNAS_PREDICAO_OPCIONAIS = ("probabilidade_pagamento", "origem_taxa", "perda_esperada",
                               "lgd", "despesas_mensais", "fase_cobranca",
                               "valor_esperado_liquido", "rank")


def _inserir_predicoes(db, linhas: list[dict]):
    """Insere predições; se uma coluna nova ainda não existir, tenta sem ela."""
    try:
        return db.table("predicoes").insert(linhas).execute()
    except Exception as e:
        citadas = [c for c in _COLUNAS_PREDICAO_OPCIONAIS if c in str(e)]
        if not citadas:
            raise
        # O PostgREST reclama de uma coluna por vez. Tirar só a citada levaria a
        # uma nova falha na coluna seguinte, então removemos todas as opcionais
        # de uma vez: uma tentativa, resultado garantido.
        print(
            f"[Supabase] Coluna ausente em predicoes: {citadas}. Gravando sem "
            f"{list(_COLUNAS_PREDICAO_OPCIONAIS)} — rode os ALTER TABLE de sql/schema.sql."
        )
        enxutas = [
            {k: v for k, v in linha.items() if k not in _COLUNAS_PREDICAO_OPCIONAIS}
            for linha in linhas
        ]
        return db.table("predicoes").insert(enxutas).execute()


LOTE_INSERCAO = 2000       # ~1 MB de JSON por requisição; 200 mil devedores = 100 idas
INSERCOES_PARALELAS = 4    # poucas: o Supabase tem teto de conexões por projeto


def _inserir_predicoes_em_lotes(db, linhas: list[dict]) -> dict:
    """Grava todas as predições e devolve {cpf: id}.

    Era um laço de 500 em 500, uma ida ao banco por vez: 400 idas para 200 mil
    devedores. Agora lotes de 2000, quatro em paralelo. Qualquer lote que falhe
    derruba o conjunto (a exceção sobe depois de os demais terminarem), para o
    chamador tratar a gravação como incompleta em vez de seguir como se nada.
    """
    from concurrent.futures import ThreadPoolExecutor
    lotes = [linhas[i:i + LOTE_INSERCAO] for i in range(0, len(linhas), LOTE_INSERCAO)]
    mapa: dict[str, str] = {}
    if not lotes:
        return mapa
    with ThreadPoolExecutor(max_workers=min(INSERCOES_PARALELAS, len(lotes))) as ex:
        futuros = [ex.submit(_inserir_predicoes, db, lote) for lote in lotes]
        erro = None
        for f in futuros:
            try:
                res = f.result()
            except Exception as e:      # espera todos terminarem antes de relançar
                erro = erro or e
                continue
            for row in (res.data or []):
                if row.get("cpf") and row.get("id"):
                    mapa[str(row["cpf"])] = row["id"]
    if erro is not None:
        raise erro
    return mapa


def _premissa_recuperacao_se_pagar(empresa_id: str | None) -> float:
    """Lê a premissa da empresa; cai no padrão declarado se não houver."""
    if not empresa_id:
        return PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO
    try:
        res = (
            get_db().table("empresa_config")
            .select("extra").eq("empresa_id", empresa_id).limit(1).execute()
        )
        extra = (res.data or [{}])[0].get("extra") or {}
        valor = float(extra.get("recuperacao_se_pagar"))
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO
    except Exception:
        return PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO
    if not (0 < valor <= 1):
        return PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO
    return valor


def _extra_empresa(empresa_id: "str | None") -> dict:
    """Bloco `extra` da configuração da empresa; vazio se não houver."""
    if not empresa_id:
        return {}
    try:
        res = (get_db().table("empresa_config")
               .select("extra").eq("empresa_id", empresa_id).limit(1).execute())
        return (res.data or [{}])[0].get("extra") or {}
    except Exception:
        return {}


def _politica_proposta(empresa_id: "str | None"):
    """Política de renegociação da empresa; cai no padrão declarado se não houver.

    Buffer da margem e teto de comprometimento são regra do banco, não
    constante do Mizan — a própria referência os descreve como "regra do
    banco diz". Por isso ficam em empresa_config.extra.
    """
    from model.proposta import PoliticaProposta
    if not empresa_id:
        return PoliticaProposta()
    try:
        res = (
            get_db().table("empresa_config")
            .select("extra").eq("empresa_id", empresa_id).limit(1).execute()
        )
        extra = (res.data or [{}])[0].get("extra") or {}
        return PoliticaProposta.de_config(extra)
    except Exception:
        return PoliticaProposta()


def _sem_nan(obj):
    """NaN e infinito viram None (null), em dicts e listas aninhados. O JSON não tem NaN."""
    if isinstance(obj, dict):
        return {k: _sem_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sem_nan(v) for v in obj]
    if isinstance(obj, (float, np.floating)) and not math.isfinite(float(obj)):
        return None
    return obj


def _analisar_df(df: pd.DataFrame, nome_fonte: str, _usuario_id: str = None, _usuario_email: str = None,
                 _empresa_id: str = None, _carteira_id_existente: str = None,
                 _incluir_ranking: bool = True) -> dict:
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
        resultado = score_carteira(df, _empresa_id or None)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Modelos não encontrados ({e.filename}).")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {e}")

    # ── Taxa de recuperação: duas grandezas distintas ───────────────────────
    # O sistema tratava como uma só o que são duas perguntas diferentes:
    #
    #   probabilidade_pagamento  P(o devedor paga alguma coisa)  → classificador
    #   recuperacao_se_pagar     quanto do saldo entra quando paga → premissa/modelo
    #
    # A taxa de recuperação ESPERADA é o produto das duas, e é ela que
    # multiplica o saldo devedor para virar valor esperado de recuperação.
    #
    # Com o price model treinado, ele já devolve a taxa esperada incondicional
    # (quem não pagou entra no treino com 0), então não se multiplica de novo
    # pela probabilidade — seria contar duas vezes.
    #
    # Sem ele, a taxa vem de uma premissa declarada por empresa, e o campo
    # origem_taxa registra qual dos dois caminhos produziu o número, para a
    # interface poder dizer em que o valor se apoia.
    resultado["probabilidade_pagamento"] = (
        resultado["score_recuperabilidade"].astype(float) / 100
    ).clip(0, 1).round(4)

    _precificacao_ml = False
    try:
        from model.price_model import prever as _prever_taxa
        _taxas = _prever_taxa(resultado.to_dict("records"), _empresa_id)
        if _taxas is not None:
            resultado["taxa_recuperacao_prevista"] = _taxas
            resultado["origem_taxa"] = "modelo"
            _precificacao_ml = True
    except Exception:
        pass

    if not _precificacao_ml:
        _rec_se_pagar = _premissa_recuperacao_se_pagar(_empresa_id)
        resultado["taxa_recuperacao_prevista"] = (
            resultado["probabilidade_pagamento"] * _rec_se_pagar
        ).round(4)
        resultado["origem_taxa"] = "premissa"

    _ead = resultado["valor_divida"].fillna(0).astype(float).clip(lower=0)
    resultado["valor_esperado_recuperacao"] = (
        _ead * resultado["taxa_recuperacao_prevista"].astype(float)
    ).round(2)

    # Perda esperada, no vocabulário de Basileia que a mesa de risco usa:
    #   EAD  exposição — o saldo devedor, que aqui é dado, não estimativa,
    #        porque o default já aconteceu
    #   LGD  perda dado o default — 1 menos a taxa de recuperação
    #   EL   perda esperada — EAD × LGD
    # Numa carteira já inadimplente não há PD a prever: o que interessa é
    # quanto do exposto não volta.
    resultado["lgd"] = (1 - resultado["taxa_recuperacao_prevista"].astype(float)).clip(0, 1).round(4)
    resultado["perda_esperada"] = (_ead - resultado["valor_esperado_recuperacao"]).round(2)

    # Fase do ciclo de cobrança e o que ela custa (ver model/ciclo.py). Entre
    # 31 e 360 dias a cobrança é terceirizada e o banco paga comissão sobre o
    # recuperado: o valor esperado bruto superestima o que sobra para ele, e é
    # o líquido que deve ordenar a fila. Sem comissão configurada o líquido é
    # igual ao bruto e o resumo diz que está bruto — aplicar uma taxa que
    # ninguém informou erraria justamente na direção que favorece o produto.
    from model import ciclo as _ciclo

    _extra_emp = _extra_empresa(_empresa_id)
    _custos = _ciclo.custos_de_config(_extra_emp)
    resultado["fase_cobranca"] = resultado["dias_em_atraso"].apply(_ciclo.fase_de)
    resultado["valor_esperado_liquido"] = [
        round(_ciclo.liquido(ve, fase, _custos), 2)
        for ve, fase in zip(resultado["valor_esperado_recuperacao"],
                            resultado["fase_cobranca"])
    ]
    resultado["origem_custo_cobranca"] = _custos["origem"]

    # A fila é ordenada por VALOR ESPERADO, não por score.
    #
    # O score é probabilidade de pagar; o banco quer valor recuperado, e quem
    # paga com mais frequência costuma dever menos. Medido em backtest (ver
    # backtest.py) numa carteira onde o pagamento segue exatamente o score:
    # trabalhando 10% da base, a fila por valor esperado recupera 39,2% do
    # total contra 32,8% de "maior dívida primeiro" — enquanto a fila por
    # score puro recupera 15,8%, perdendo até para a prática mais simples da
    # operação. Ordenar por probabilidade manda o operador ligar primeiro
    # para quem paga fácil e deve pouco.
    # O critério é política da empresa (ver model/priorizacao.py). O padrão
    # maximiza recuperação; a alternativa proporcional equaliza a fatia de
    # esforço por região, custando recuperação. Medir equidade mostrou que a
    # ordenação por valor esperado desprioriza a região de dívidas menores
    # mesmo quando ela paga igual — é escolha de política, não defeito, e o
    # sistema não deve tomá-la sozinho.
    from model.priorizacao import de_config as _criterio_de_config, ordenar as _ordenar_fila

    _criterio = _criterio_de_config(_extra_emp)
    if "valor_esperado_recuperacao" in resultado.columns:
        # ordenar() recebe valor e probabilidade e multiplica internamente;
        # passar o valor esperado com probabilidade 1 dá o mesmo resultado e
        # evita reconstruir a probabilidade por divisão.
        # líquido, não bruto: é o que sobra para o banco depois da comissão
        _ve = resultado["valor_esperado_liquido"].fillna(0).astype(float).to_numpy()
        _idx = _ordenar_fila(
            _ve, np.ones(len(_ve)),
            resultado["uf"] if "uf" in resultado.columns else None,
            _criterio,
        )
        resultado_sorted = resultado.iloc[_idx].reset_index(drop=True)
    else:
        resultado_sorted = resultado.sort_values(
            "score_recuperabilidade", ascending=False).reset_index(drop=True)
    resultado_sorted.insert(0, "rank", range(1, len(resultado_sorted) + 1))
    resultado_sorted["criterio_fila"] = _criterio

    # Oferta sugerida: o mesmo catálogo de arquétipos que a tela do devedor
    # usa (model/proposta.py), escolhido por maior valor esperado.
    #
    # A versão anterior era uma escada de limiares — score acima de 75 não
    # ganha desconto, acima de 50 ganha 15% em 6x, e assim por diante. Aqueles
    # números não vieram de lugar nenhum, e o Excel exportado trazia uma oferta
    # enquanto a tela do devedor trazia outra, calculada de verdade.
    #
    # Aqui a conta é vetorizada, uma coluna por arquétipo, porque rodar o
    # motor linha a linha numa carteira de dezenas de milhares custaria caro.
    # A verificação de capacidade de pagamento não entra: ela exige a margem
    # livre do devedor, que a carteira quase nunca traz. Quem abre o devedor
    # vê a análise completa, com margem e o porquê de cada proposta.
    from model.proposta import ARQUETIPOS_PADRAO

    _v = (resultado_sorted["valor_divida"].fillna(0).astype(float).clip(lower=0)
          if "valor_divida" in resultado_sorted.columns
          else pd.Series(0.0, index=resultado_sorted.index))
    _pop = (resultado_sorted["probabilidade_pagamento"].fillna(0).astype(float)
            if "probabilidade_pagamento" in resultado_sorted.columns
            else (resultado_sorted["score_recuperabilidade"].fillna(0).astype(float) / 100).clip(0, 1))

    try:
        from model.bandit import pop_por_oferta as _pop_of
        _pops = _pop_of(_empresa_id, float(_pop.mean()) if len(_pop) else 0.5)
    except Exception:
        _pops = {}

    _ev = np.column_stack([
        _v.to_numpy() * (1 - a["desconto_pct"] / 100)
        * (_pops.get(a["oferta"], {}).get("pop") or _pop.to_numpy())
        for a in ARQUETIPOS_PADRAO
    ])
    _melhor = _ev.argmax(axis=1)
    _desc = np.array([ARQUETIPOS_PADRAO[i]["desconto_pct"] for i in _melhor])
    _parc = np.array([ARQUETIPOS_PADRAO[i]["n_parcelas"] for i in _melhor])

    resultado_sorted["desconto_sugerido_pct"] = _desc.astype(int)
    resultado_sorted["valor_proposta"]        = (_v.to_numpy() * (1 - _desc / 100)).round(2)
    resultado_sorted["parcelas_max"]          = _parc.astype(int)
    resultado_sorted["estrategia_oferta"]     = [
        ARQUETIPOS_PADRAO[i]["rotulo"] for i in _melhor
    ]

    # Sem feedback por oferta, todas as propostas dividem a mesma chance de
    # pagamento, e a de maior valor esperado é sempre a sem desconto — porque
    # descontar sem evidência de que isso aumenta o pagamento é perda pura.
    # A conclusão é correta, mas é da carteira inteira, não de cada devedor:
    # numa planilha, linha a linha, pareceria análise individual. Daí a
    # procedência, no mesmo espírito de origem_taxa da Fase 0.
    _ofertas_distintas = len({round(v.get("pop", 0), 6) for v in _pops.values()}) > 1
    resultado_sorted["origem_oferta"] = "bandit" if _ofertas_distintas else "sem_evidencia"
    _oferta_uniforme = len(set(_melhor.tolist())) == 1
    resultado_sorted["dados_incompletos"] = resultado_sorted.get("dados_incompletos", False).fillna(False).astype(bool)
    resultado_sorted["aviso_dados"]       = resultado_sorted.get("aviso_dados", "").fillna("").astype(str)

    # _sem_nan e não .where(notna, None): no pandas 3 o where devolve NaN de volta
    # nas colunas numéricas, e um NaN na resposta derrubava a análise inteira
    # (Starlette recusa NaN no JSON). Uma célula de renda em branco bastava.
    devedores = [_sem_nan(d) for d in resultado_sorted.to_dict(orient="records")]

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

    n_incompletos = int(resultado["dados_incompletos"].sum()) if "dados_incompletos" in resultado.columns else 0
    resumo = {
        "total_devedores": len(resultado),
        "total_em_risco": round(total_em_risco, 2),
        "score_medio": media_score,
        "valor_esperado_recuperacao_total": round(ver_total, 2),
        "taxa_recuperacao_esperada": round(ver_total / total_em_risco * 100, 1) if total_em_risco else 0,
        "devedores_dados_incompletos": n_incompletos,
        "criado_por":       _usuario_email or "",
        "criado_em":        datetime.utcnow().isoformat(),
        "precificacao_ml":  _precificacao_ml,
        # Esta carteira ainda parece com aquela em que o modelo aprendeu?
        "psi":              _psi_da_carteira(resultado["score_recuperabilidade"].tolist(), _empresa_id or None),
        # Perda esperada da carteira — o número que vai para a provisão.
        "ead_total":            round(total_em_risco, 2),
        "perda_esperada_total": round(total_em_risco - ver_total, 2),
        "lgd_medio_ponderado":  round(
            (total_em_risco - ver_total) / total_em_risco, 4
        ) if total_em_risco else 0.0,
        # Valores dos seletores da tela. A tela os montava percorrendo o
        # ranking inteiro; sem o ranking no navegador, vêm daqui — e aqui os
        # dados já estão em memória, então não custa consulta nenhuma.
        "produtos": sorted({str(p) for p in resultado.get("produto", pd.Series(dtype=str)).dropna().unique()}),
        "ufs":      sorted({str(u) for u in resultado.get("uf", pd.Series(dtype=str)).dropna().unique()}),
    }

    # Distribuição por fase do ciclo e, acima de 360 dias, a comparação que o
    # banco precisa fazer: cobrar ou vender. Se o esperado líquido de uma
    # dívida é menor do que ela valeria cedida a fundo de NPL, cobrar destrói
    # valor — e essa conta ninguém fazia porque o sistema não conhecia a fase.
    _por_fase = []
    for _fid, _f in _ciclo.FASES.items():
        _m = resultado["fase_cobranca"] == _fid
        if not _m.any():
            continue
        _por_fase.append({
            "fase": _fid,
            "rotulo": _f.rotulo,
            "descricao": _f.descricao,
            "devedores": int(_m.sum()),
            "valor_face": round(float(resultado.loc[_m, "valor_divida"].sum()), 2),
            "valor_esperado_liquido": round(
                float(resultado.loc[_m, "valor_esperado_liquido"].sum()), 2),
            "tem_comissao": _f.tem_comissao,
        })
    resumo["ciclo_cobranca"] = _por_fase
    resumo["custo_cobranca"] = {k: v for k, v in _custos.items() if k != "origem"} | {
        "origem": _custos["origem"]}

    _aviso_ciclo = _ciclo.aviso(_custos)
    if _aviso_ciclo:
        resumo["aviso_ciclo"] = _aviso_ciclo

    _wo = resultado["fase_cobranca"] == "write_off"
    if _wo.any() and _custos.get("cessao_pct") is not None:
        _esperado_wo = float(resultado.loc[_wo, "valor_esperado_liquido"].sum())
        _cessao_wo = _ciclo.valor_cessao(float(resultado.loc[_wo, "valor_divida"].sum()), _custos)
        resumo["write_off"] = {
            "devedores": int(_wo.sum()),
            "esperado_cobrando": round(_esperado_wo, 2),
            "valor_se_vendida": round(_cessao_wo, 2),
            "vale_mais_vender": _cessao_wo > _esperado_wo,
        }

    # A oferta da planilha é da CARTEIRA, não de cada devedor: o que varia
    # entre as propostas é a chance de pagamento por tipo de oferta, que o
    # bandit aprende para a empresa inteira. A escolha por devedor, essa sim
    # contextual, está na tela dele. Repetida linha a linha numa planilha, uma
    # sugestão uniforme pareceria análise individual — daí o aviso.
    if _oferta_uniforme:
        if _ofertas_distintas:
            resumo["aviso_oferta"] = (
                "A oferta sugerida é a mesma para toda a carteira: ela sai da chance "
                "de pagamento por tipo de proposta, que vale para a empresa e não "
                "para cada devedor. Abra o devedor para a análise individual, com "
                "margem livre e o porquê de cada proposta."
            )
        else:
            resumo["aviso_oferta"] = (
                "As ofertas ainda não se diferenciam entre si: não há feedback de "
                "renegociação suficiente para estimar a chance de pagamento por tipo "
                "de proposta. Enquanto isso, a de maior valor esperado é sempre a sem "
                "desconto, porque descontar sem evidência de que isso aumenta o "
                "pagamento é perda pura. Registrar a oferta apresentada em cada "
                "contato alimenta essa estimativa."
            )

    try:
        db = get_db()
        versao_modelo = _get_versao_ativa(_empresa_id or None)  # captura uma vez para update e insert usarem a mesma versão

        def _py(val):
            if val is None: return None
            if hasattr(val, "item"): val = val.item()
            if isinstance(val, float) and not math.isfinite(val): return None   # NaN não é JSON
            return val

        if _carteira_id_existente:
            # ── Modo atualização: substitui predicoes, preserva feedbacks ──
            carteira_id = _carteira_id_existente
            # Truncado, os feedbacks ligados às predições além da milésima
            # continuariam apontando para linhas apagadas.
            pred_ids = [p["id"] for p in _todas_as_linhas(
                lambda: db.table("predicoes").select("id").eq("carteira_id", carteira_id))]
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
                "modelo_versao":   versao_modelo,
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
                "modelo_versao":   versao_modelo,
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
             "perfil_cluster": d.get("perfil_cluster"), "cluster_id": _py(d.get("cluster_id")),
             "dados_incompletos": bool(d.get("dados_incompletos", False)),
             "aviso_dados": str(d.get("aviso_dados") or ""),
             "taxa_recuperacao_prevista": _py(d.get("taxa_recuperacao_prevista")),
             "probabilidade_pagamento": _py(d.get("probabilidade_pagamento")),
             "origem_taxa": str(d.get("origem_taxa") or ""),
             "perda_esperada": _py(d.get("perda_esperada")),
             "lgd": _py(d.get("lgd")),
             "despesas_mensais": _py(d.get("despesas_mensais")),
             "fase_cobranca": d.get("fase_cobranca"),
             "valor_esperado_liquido": _py(d.get("valor_esperado_liquido")),
             # A posição na fila é resultado da POLÍTICA de priorização, não do
             # score. Sem gravá-la, reabrir a carteira reordenava por score e
             # desfazia em silêncio a decisão de ordenar por valor.
             "rank": _py(d.get("rank"))}
            for d in devedores
        ]
        pred_id_map = _inserir_predicoes_em_lotes(db, predicoes_rows)
    except Exception as _e:
        print(f"[Supabase] Erro ao salvar: {_e}")
        pred_id_map = {}
        # Gravação pela metade: a análise em si está certa e segue na resposta,
        # mas o que ficou no banco está incompleto e o usuário precisa saber.
        resumo["salvamento_incompleto"] = True
        if not _carteira_id_existente and resumo.get("carteira_id"):
            # Carteira nova que não terminou de gravar: não deixa uma casca com
            # parte dos devedores aparecendo como se fosse a carteira inteira.
            try:
                db.table("predicoes").delete().eq("carteira_id", resumo["carteira_id"]).execute()
                db.table("carteiras").delete().eq("id", resumo["carteira_id"]).execute()
                resumo["carteira_id"] = None
            except Exception as _e2:
                print(f"[Supabase] Não consegui desfazer a carteira parcial: {_e2}")
    else:
        _registrar_auditoria(
            acao="carteira_sincronizada" if _carteira_id_existente else "carteira_criada",
            entidade="carteira",
            entidade_id=carteira_id,
            usuario_email=_usuario_email,
            empresa_id=_empresa_id,
            detalhes={"total_devedores": resumo["total_devedores"], "nome_arquivo": nome_fonte},
            usuario_id=_usuario_id,
        )

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

    return _sem_nan({"resumo": resumo, "distribuicao_aging": aging_dist,
                     "distribuicao_cluster": cluster_dist, "top10_prioritarios": devedores[:10],
                     # Sem carteira gravada não há o que paginar no servidor: a
                     # fila vai na resposta, senão a tabela abriria vazia.
                     **({"ranking_completo": devedores}
                        if _incluir_ranking or not resumo.get("carteira_id") else {})})


@app.post("/listar-tabelas")
def listar_tabelas(conn: ConexaoDB, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Lista as tabelas disponíveis no banco externo — sem precisar escrever SQL."""
    _resolver_credenciais(conn, _usuario_autenticado(credentials))
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
            engine = create_engine(url, connect_args=_external_connect_args(conn))
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
def testar_db(conn: ConexaoDB, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Testa conexão, executa query limitada e retorna colunas + preview + mapeamento sugerido."""
    _resolver_credenciais(conn, _usuario_autenticado(credentials))
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
                engine = create_engine(url, connect_args=_external_connect_args(conn))
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
def analisar_db(conn: ConexaoDB, incluir_ranking: bool = True,
                credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Analisa uma carteira carregada diretamente de um banco de dados externo."""
    _payload = _usuario_autenticado(credentials)  # valida o token ANTES de conectar
    _resolver_credenciais(conn, _payload)
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
            # Protege contra queries sem LIMIT que podem carregar milhões de linhas
            _MAX_ROWS = 50_000
            if conn.tipo == "sqlserver":
                safe_q = f"SELECT TOP {_MAX_ROWS} * FROM ({q}) AS _mizan_safe"
                with _sqlserver_connect(conn) as tds_conn:
                    df = pd.read_sql(safe_q, tds_conn)
            else:
                from sqlalchemy import create_engine, text
                url = _construir_url_db(conn)
                engine = create_engine(url, connect_args=_external_connect_args(conn))
                with engine.connect() as connection:
                    if conn.tipo == "oracle":
                        safe_q = f"SELECT * FROM ({q}) WHERE ROWNUM <= {_MAX_ROWS}"
                    else:
                        safe_q = f"SELECT * FROM ({q}) AS _mizan_safe LIMIT {_MAX_ROWS}"
                    df = pd.read_sql(text(safe_q), connection)
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

    uid, uemail, eid = _payload["sub"], _payload.get("email", ""), _payload.get("empresa_id", "")
    # COMANDO pode especificar a empresa destino da análise
    if _payload.get("role") == "comando" and conn.empresa_id_alvo:
        eid = conn.empresa_id_alvo.strip().lower()
    nome = conn.nome_fonte or "consulta_db"
    resultado = _analisar_df(df, nome, _usuario_id=uid, _usuario_email=uemail, _empresa_id=eid,
                             _incluir_ranking=incluir_ranking)

    # Vincula a carteira criada à conexão salva (para sincronizações futuras atualizarem no lugar)
    nova_carteira_id = resultado.get("resumo", {}).get("carteira_id")
    if conn.conexao_id and nova_carteira_id:
        try:
            get_db().table("conexoes_db").update({"carteira_id": nova_carteira_id}).eq("id", conn.conexao_id).execute()
        except Exception:
            pass

    return resultado


def _writeback_pagamento(empresa_id: str, cpf: str, pagou: bool) -> str | None:
    """Atualiza a coluna de status no banco externo da empresa quando um pagamento é registrado."""
    import re as _re
    db = get_db()
    try:
        rows = db.table("conexoes_db").select("*").eq("empresa_id", empresa_id).execute().data
    except Exception:
        return None
    # Write-back é OPT-IN: por padrão toda conexão é somente-leitura.
    # Só grava no banco do cliente se o admin habilitou explicitamente E configurou a coluna.
    conn_row = next((r for r in sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)
                     if r.get("writeback_habilitado") and r.get("coluna_writeback")), None)
    if not conn_row:
        return None

    coluna = conn_row["coluna_writeback"]
    valor_pago = conn_row.get("valor_pago") or "pago"
    valor_nao_pago = conn_row.get("valor_nao_pago")

    novo_valor = valor_pago if pagou else valor_nao_pago
    if novo_valor is None:
        return None  # não atualiza para "não pagou" se não configurado

    # Extrai o nome da tabela da query SELECT
    query = conn_row.get("query") or ""
    m = _re.search(r'\bFROM\b\s+([\w\."]+)', query, _re.IGNORECASE)
    if not m:
        return None
    tabela = m.group(1).strip('"')

    # Descobre o nome real da coluna CPF no banco externo (via mapeamento)
    mapeamento = conn_row.get("mapeamento") or {}
    coluna_cpf = mapeamento.get("cpf", "cpf")

    # Valida nomes para evitar injeção SQL via valores armazenados
    if not _re.match(r'^[\w.]+$', tabela):
        print(f"[Writeback] Nome de tabela inválido: {tabela!r}")
        return None
    if not _re.match(r'^\w+$', coluna):
        print(f"[Writeback] Nome de coluna inválido: {coluna!r}")
        return None
    if not _re.match(r'^\w+$', coluna_cpf):
        print(f"[Writeback] Nome de coluna CPF inválido: {coluna_cpf!r}")
        return None

    senha_dec = _decrypt(conn_row.get("senha"))
    conn = ConexaoDB(
        tipo=conn_row["tipo"], host=conn_row.get("host"), porta=conn_row.get("porta"),
        banco=conn_row.get("banco"), usuario=conn_row.get("usuario"), senha=senha_dec,
        instance_name=conn_row.get("instance_name"), service_name=conn_row.get("service_name"),
        query=query,
    )
    try:
        if conn.tipo == "sqlserver":
            with _sqlserver_connect(conn) as tds_conn:
                cur = tds_conn.cursor()
                cur.execute(f"UPDATE {tabela} SET {coluna} = ? WHERE {coluna_cpf} = ?", (novo_valor, cpf))
                tds_conn.commit()
        else:
            from sqlalchemy import create_engine, text
            url = _construir_url_db(conn)
            engine = create_engine(url, connect_args=_external_connect_args(conn))
            with engine.begin() as connection:
                connection.execute(
                    text(f"UPDATE {tabela} SET {coluna} = :val WHERE {coluna_cpf} = :cpf"),
                    {"val": novo_valor, "cpf": cpf},
                )
            engine.dispose()
        print(f"[Writeback] CPF {_cpf_no_log(cpf)} → {tabela}.{coluna} = '{novo_valor}'")
        return f"{tabela}.{coluna} = '{novo_valor}'"
    except Exception as e:
        print(f"[Writeback] Erro ao atualizar banco externo: {e}")
        return None


@app.post("/feedback")
def receber_feedback(
    payload: FeedbackIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Registra pagamento manualmente. Apenas admin/comando podem usar este endpoint."""
    empresa_info = _validar_api_key(credentials)

    jwt_check = empresa_info.get("jwt") or {}
    if jwt_check.get("role") == "operador":
        raise HTTPException(status_code=403, detail="Operadores não podem registrar pagamentos manualmente. Os pagamentos são atualizados automaticamente via sincronização com o banco de dados.")

    db = get_db()

    jwt_payload = empresa_info.get("jwt") or {}
    _e_comando = jwt_payload.get("role") == "comando"
    # Comando não pertence a empresa; quando informa uma no corpo, é nela que a
    # predição é procurada. Sem isso o CPF casaria com a de qualquer cliente.
    _escopo = (jwt_payload.get("empresa_id") or empresa_info.get("empresa_id")
               or (payload.empresa if _e_comando else None))
    if not _escopo and not _e_comando:
        raise HTTPException(status_code=403, detail="Credencial sem empresa vinculada.")

    # A predição mais recente deste CPF DENTRO da empresa de quem chamou. Antes
    # a busca era só por CPF: o predicao_id de outro cliente era gravado no
    # feedback, o bandit desta empresa aprendia com o contexto de uma predição
    # alheia, e o painel do outro cliente passava a exibir um pagamento que ele
    # não registrou.
    pred_dict = _predicao_do_cpf(db, payload.cpf, _escopo)
    predicao_id = pred_dict["id"] if pred_dict else None

    usuario_role = jwt_payload.get("role", "operador")
    usuario_nome = jwt_payload.get("nome") or jwt_payload.get("email") or empresa_info.get("empresa_nome", "")
    empresa_nome = (
        jwt_payload.get("empresa_id")
        or empresa_info.get("empresa_id")
        or payload.empresa
        or empresa_info.get("empresa_nome")
    )
    fb_row = {
        "cpf": payload.cpf,
        "pagou": payload.pagou,
        "valor_recuperado": payload.valor_recuperado or 0,
        "empresa": empresa_nome,
        "registrado_por": usuario_nome,
    }
    if payload.data_pagamento:
        fb_row["data_pagamento"] = payload.data_pagamento.isoformat()
    if predicao_id:
        fb_row["predicao_id"] = predicao_id

    res = db.table("feedbacks").insert(fb_row).execute()
    feedback_id = res.data[0]["id"]

    _fechar_loop_bandit(
        db, payload.cpf, payload.pagou,
        float(payload.valor_recuperado or 0),
        pred_dict,
        empresa_nome,
    )

    # Write-back: só para admin/comando — operador não pode alterar banco externo diretamente
    empresa_id_jwt = jwt_payload.get("empresa_id", "")
    writeback_info = None
    if empresa_id_jwt and usuario_role in ("admin", "comando"):
        import threading
        def _wb():
            nonlocal writeback_info
            writeback_info = _writeback_pagamento(empresa_id_jwt, payload.cpf, payload.pagou)
        t = threading.Thread(target=_wb, daemon=True)
        t.start()
        t.join(timeout=8)

    return {"ok": True, "feedback_id": feedback_id, "predicao_id": predicao_id, "writeback": writeback_info}


@app.post("/devedores/{cpf}/confirmar-pagamento")
def confirmar_pagamento(
    cpf: str,
    body: ConfirmarPagamentoIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Confirma pagamento manualmente. Apenas admin/comando. Idempotente — bloqueia duplo registro."""
    payload = _usuario_autenticado(credentials)
    role = payload.get("role", "")
    if role not in ("admin", "comando"):
        raise HTTPException(status_code=403, detail="Apenas administradores podem confirmar pagamentos.")

    empresa_id = payload.get("empresa_id", "")
    usuario_nome = payload.get("nome") or payload.get("email") or "admin"
    usuario_id = payload.get("sub", "")

    # Rate limiting por usuário: 30 confirmações/hora
    rate_key = f"{usuario_id}:confirmar"
    agora = _time.time()
    _rate_confirmacoes[rate_key] = [t for t in _rate_confirmacoes[rate_key] if agora - t < _RATE_CONFIRM_JANELA]
    if len(_rate_confirmacoes[rate_key]) >= _RATE_CONFIRM_MAX:
        raise HTTPException(status_code=429, detail="Limite de confirmações atingido. Aguarde 1 hora.")
    _rate_confirmacoes[rate_key].append(agora)

    # Trava contra confirmações simultâneas do mesmo CPF
    lock_key = f"{empresa_id}:{cpf}"
    if lock_key in _confirmacoes_em_andamento:
        raise HTTPException(status_code=409, detail="Já existe uma confirmação em andamento para este devedor.")
    _confirmacoes_em_andamento.add(lock_key)

    print(f"[Confirmar] Tentativa — CPF: {_cpf_no_log(cpf)}, role: {role}")

    try:
        db = get_db()

        # Idempotência: verifica se já foi confirmado para este CPF + empresa
        existing = (
            db.table("feedbacks")
            .select("id, created_at, registrado_por")
            .eq("cpf", cpf)
            .eq("pagou", True)
            .eq("empresa", empresa_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data:
            fb = existing.data[0]
            ts = (fb.get("created_at") or "")[:16].replace("T", " ")
            raise HTTPException(
                status_code=409,
                detail=f"Pagamento já confirmado por {fb.get('registrado_por', 'sistema')} em {ts}.",
            )

        # Busca predição mais recente para este CPF — escopo restrito à empresa
        pred_res = None
        predicao_id = None
        try:
            # Falha fechada, como em /feedback: empresa sem carteira não casa
            # com a predição de ninguém. O `if cart_ids:` antigo descartava o
            # filtro quando a lista vinha vazia.
            if not empresa_id and role != "comando":
                raise HTTPException(status_code=403, detail="Credencial sem empresa vinculada.")
            _pd = _predicao_do_cpf(db, cpf, empresa_id,
                                   colunas="id, carteira_id, score_recuperabilidade, valor_divida")
            pred_res = type("R", (), {"data": [_pd] if _pd else []})()
            predicao_id   = _pd["id"]              if _pd else None
            _pred_cart_id = _pd.get("carteira_id") if _pd else None
        except HTTPException:
            raise
        except Exception as _pe:
            _pred_cart_id = None
            print(f"[Confirmar] Aviso — não encontrou predicao para CPF {_cpf_no_log(cpf)}: {type(_pe).__name__}")

        if not predicao_id:
            raise HTTPException(
                status_code=404,
                detail=f"CPF {cpf} não encontrado na carteira ativa. Só é possível registrar pagamentos de devedores analisados pelo Mizan.",
            )

        fb_row: dict = {
            "cpf":             cpf,
            "pagou":           True,
            "valor_recuperado": body.valor_recuperado or 0,
            "empresa":         empresa_id,
            "registrado_por":  usuario_nome,
        }
        if body.data_pagamento:
            fb_row["data_pagamento"] = body.data_pagamento.isoformat()
        if predicao_id:
            fb_row["predicao_id"] = predicao_id

        print(f"[Confirmar] Gravando Supabase — CPF: {_cpf_no_log(cpf)}, empresa: {empresa_id}, predicao_id: {predicao_id}")
        res = db.table("feedbacks").insert(fb_row).execute()
        if not res.data:
            raise Exception("Supabase insert retornou vazio — verifique permissões RLS ou coluna 'registrado_por' ausente na tabela feedbacks")
        feedback_id = res.data[0]["id"]
        registrado_em = res.data[0].get("created_at", "")
        print(f"[Confirmar] Supabase gravado com sucesso — feedback_id: {feedback_id}")

        # Operações pós-INSERT: falhas aqui não revertem o INSERT já commitado
        try:
            _fechar_loop_bandit(
                db, cpf, True,
                float(body.valor_recuperado or 0),
                pred_res.data[0] if (pred_res and pred_res.data) else None,
                empresa_id,
            )
        except Exception as _be:
            print(f"[Confirmar] Aviso — _fechar_loop_bandit falhou (não crítico): {_be}")

        # Write-back para banco externo da empresa (non-blocking, 8s timeout)
        writeback_info = None
        if empresa_id:
            import threading
            _wb_result: list = [None]
            def _wb():
                try:
                    _wb_result[0] = _writeback_pagamento(empresa_id, cpf, True)
                except Exception as _wbe:
                    print(f"[Confirmar] Aviso — write-back falhou (não crítico): {_wbe}")
            t = threading.Thread(target=_wb, daemon=True)
            t.start()
            t.join(timeout=8)
            writeback_info = _wb_result[0]

        print(f"[Confirmar] SUCESSO — CPF: {_cpf_no_log(cpf)}, id: {feedback_id}, writeback: {writeback_info}")

        _cache_del_prefix(f"fb_status:{empresa_id}")
        _cache_del_prefix(f"pagamentos:{empresa_id}")
        _cache_del_prefix(f"perf:{empresa_id}")
        if _pred_cart_id:
            _cache_del_prefix(f"fb_status:{_pred_cart_id}")
            _cache_del_prefix(f"pagamentos:{_pred_cart_id}")
            _cache_del_prefix(f"perf:{_pred_cart_id}")

        try:
            _registrar_auditoria(
                acao="confirmar_pagamento",
                entidade="feedback",
                entidade_id=feedback_id,
                usuario_email=payload.get("email", ""),
                empresa_id=empresa_id,
                # só o final do CPF: a trilha de auditoria não é apagada pelo pedido de
                # eliminação do titular, então não pode guardar o identificador inteiro
                detalhes={"cpf_final": "".join(ch for ch in str(cpf) if ch.isdigit())[-4:],
                          "valor_recuperado": body.valor_recuperado, "writeback": writeback_info},
                usuario_id=usuario_id,
            )
        except Exception as _ae:
            print(f"[Confirmar] Aviso — auditoria falhou (não crítico): {_ae}")

        return {
            "ok":            True,
            "feedback_id":   feedback_id,
            "registrado_por": usuario_nome,
            "registrado_em": registrado_em,
            "writeback":     writeback_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Confirmar] ERRO — CPF: {_cpf_no_log(cpf)}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=f"Erro ao confirmar pagamento: {str(e)}")
    finally:
        _confirmacoes_em_andamento.discard(lock_key)


@app.post("/webhook/pagamento")
def webhook_pagamento(body: WebhookPagamentoIn, request: Request):
    """
    Webhook para receber pagamentos em tempo real do sistema do cliente.
    Autenticação: header X-API-Key com a api_key cadastrada no Mizan.
    Exemplo: POST /webhook/pagamento com header X-API-Key: mizan_test_xxx
    """
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        raise HTTPException(status_code=401, detail="Header X-API-Key obrigatório.")

    db = get_db()
    linha_key = _buscar_api_key(db, api_key)
    if not linha_key:
        raise HTTPException(status_code=401, detail="API key inválida ou inativa.")
    _marcar_uso_api_key(db, linha_key)

    # A empresa é a DA CHAVE, nunca a do corpo. Antes `body.empresa` vinha
    # primeiro, então uma chave da empresa A que enviasse "empresa": "beta"
    # gravava o pagamento no escopo da B, ligado a uma predição da B — e o
    # bandit da B aprendia com ele. Reproduzido: R$ 9.000 de pagamento caiu no
    # painel de outro cliente com a chave errada.
    empresa = (linha_key.get("empresa_id") or "").strip()
    if not empresa:
        raise HTTPException(status_code=403, detail="Chave de API sem empresa vinculada.")
    if body.empresa and body.empresa.strip().lower() != empresa.lower():
        # Não é recusado: um cliente pode mandar o nome de exibição ("Banco
        # Alfa") em vez do identificador, e rejeitar quebraria a integração
        # dele. O campo é ignorado e a divergência fica registrada.
        print(f"[Webhook] corpo diz empresa={body.empresa!r}, chave é de {empresa!r}; "
              "usando a da chave.")

    # Falha fechada: empresa sem carteira não casa com a predição de ninguém, e
    # erro ao listar as carteiras vira 500 em vez de "sem filtro". O recorte
    # antigo engolia a exceção e seguia sem filtro algum.
    pred_dict     = _predicao_do_cpf(db, body.cpf, empresa)
    predicao_id   = pred_dict["id"]              if pred_dict else None
    _pred_cart_id = pred_dict.get("carteira_id") if pred_dict else None

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

    _fechar_loop_bandit(
        db, body.cpf, body.pagou,
        float(body.valor_recuperado or 0),
        pred_dict,
        empresa,
    )

    _cache_del_prefix(f"fb_status:{empresa}")
    _cache_del_prefix(f"pagamentos:{empresa}")
    _cache_del_prefix(f"perf:{empresa}")
    if _pred_cart_id:
        _cache_del_prefix(f"fb_status:{_pred_cart_id}")
        _cache_del_prefix(f"pagamentos:{_pred_cart_id}")
        _cache_del_prefix(f"perf:{_pred_cart_id}")

    print(f"[Webhook] Pagamento recebido — CPF: {_cpf_no_log(body.cpf)}, pagou: {body.pagou}, empresa: {empresa}")
    return {"ok": True, "feedback_id": feedback_id}


@app.post("/feedback/lote")
async def feedback_lote(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Importa feedbacks em lote a partir de CSV ou Excel."""
    empresa_info = _validar_api_key(credentials)
    # Mesma regra de /feedback: operador não registra pagamento. A tela só
    # esconde o botão; sem esta barreira, qualquer operador com o token chamava
    # a rota direto e gravava pagamentos em lote.
    if (empresa_info.get("jwt") or {}).get("role") == "operador":
        raise HTTPException(status_code=403, detail="Operadores não podem registrar pagamentos manualmente. Os pagamentos são atualizados automaticamente via sincronização com o banco de dados.")
    # A coluna feedbacks.empresa guarda o empresa_id em todo o resto do
    # sistema; _validar_api_key devolve em "empresa_nome" o nome do usuário
    # quando a autenticação é por JWT, então gravar esse campo aqui fazia os
    # feedbacks importados em lote ficarem fora do escopo da empresa.
    _jwt = empresa_info.get("jwt") or {}
    empresa = (
        _jwt.get("empresa_id")
        or empresa_info.get("empresa_id")
        or empresa_info.get("empresa_nome")
    )

    nome = (file.filename or "").lower()
    contents = await file.read()

    def _processar():
        try:
            if nome.endswith(".csv"):
                df = _read_csv_auto(contents)
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

        # Comando não pertence a empresa e não tem escopo; qualquer outra
        # credencial sem empresa é recusada. O recorte antigo, `if lista:`,
        # caía para "sem filtro" justamente quando a lista vinha vazia — cliente
        # novo, sem carteira — e o CPF voltava a casar com qualquer empresa.
        if not empresa and _jwt.get("role") != "comando":
            raise HTTPException(status_code=403, detail="Credencial sem empresa vinculada.")

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
                pred_dict = _predicao_do_cpf(db, cpf, empresa)
                predicao_id = pred_dict["id"] if pred_dict else None

                fb_row = {"cpf": cpf, "pagou": pagou, "valor_recuperado": valor_recuperado, "empresa": empresa}
                if data_pag:
                    fb_row["data_pagamento"] = data_pag
                if predicao_id:
                    fb_row["predicao_id"] = predicao_id

                res = db.table("feedbacks").insert(fb_row).execute()
                feedback_id = res.data[0]["id"]

                _fechar_loop_bandit(
                    db, cpf, pagou, valor_recuperado,
                    pred_dict,
                    empresa,
                )

                detalhes.append({"linha": linha, "cpf": cpf, "ok": True, "feedback_id": feedback_id})
                n_ok += 1

            except Exception as e:
                detalhes.append({"linha": linha, "cpf": cpf, "ok": False, "erro": str(e)})
                n_erro += 1

        _eid = empresa_info.get("empresa_id") or (empresa_info.get("jwt") or {}).get("empresa_id") or ""
        if n_ok > 0:
            _registrar_auditoria(
                acao="feedback_importado",
                entidade="feedback",
                usuario_email=empresa_info.get("email") or (empresa_info.get("jwt") or {}).get("email"),
                empresa_id=_eid,
                detalhes={"importados": n_ok, "erros": n_erro},
            )
            _cache_del_prefix(f"pagamentos:{_eid}")
            _cache_del_prefix(f"perf:{_eid}")
            _cache_del_prefix(f"fb_status:{_eid}")
        return {"total": n_ok + n_erro, "importados": n_ok, "erros": n_erro, "detalhes": detalhes}

    # Parse da planilha mais uma gravação no Supabase por linha do lote:
    # trabalho bloqueante que cresce com o arquivo, então sai do event loop.
    return await asyncio.to_thread(_processar)


@app.get("/performance")
def performance(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    carteira_id: Optional[str] = None,
):
    """Métricas de acurácia do modelo baseadas nos feedbacks reais — filtrados por empresa."""
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    role       = payload.get("role", "")

    if not empresa_id and role != "comando":
        return {"mensagem": "Nenhum feedback recebido ainda.", "total_feedbacks": 0}

    cache_key = f"perf:{carteira_id or empresa_id}"
    cached = _cache_get(cache_key, ttl=300)
    if cached is not None:
        return cached

    db = get_db()

    if carteira_id:
        _exige_carteira_da_empresa(db, carteira_id, payload)

    # Quando carteira_id fornecido, filtra apenas por aquela carteira específica
    empresa_pred_ids: set | None = None
    if carteira_id:
        try:
            empresa_pred_ids = _ids_das_predicoes(db, carteira_id)
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")
    elif empresa_id:
        try:
            cart_ids = _ids_carteiras(db, empresa_id)
            if not cart_ids:
                return {"mensagem": "Nenhum feedback recebido ainda.", "total_feedbacks": 0}
            pred_res_all: list = []
            for i in range(0, len(cart_ids), 100):
                # Cem carteiras por vez cabem na URL, mas as predições delas
                # passam de mil com folga — daí o lote interno também paginar.
                pr = type("R", (), {"data": _todas_as_linhas(
                    lambda lote=cart_ids[i:i+100]:
                        db.table("predicoes").select("id").in_("carteira_id", lote))})()
                pred_res_all.extend(pr.data or [])
            empresa_pred_ids = {p["id"] for p in pred_res_all}
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")

    # Com escopo, lê só os feedbacks das predições dele. Antes lia os 5.000
    # (na prática mil) mais novos DE TODAS AS EMPRESAS e filtrava na memória:
    # com mais de mil feedbacks recentes de outros clientes, esta empresa via
    # quase nada. Sem escopo (COMANDO olhando tudo), lê todos, paginando.
    if empresa_pred_ids is not None:
        feedbacks = _feedbacks_das_predicoes(db, "pagou, predicao_id, created_at", empresa_pred_ids)
    else:
        feedbacks = _todas_as_linhas(
            lambda: db.table("feedbacks").select("pagou, predicao_id").order("created_at", desc=True))

    if not feedbacks:
        return {"mensagem": "Nenhum feedback recebido ainda.", "total_feedbacks": 0}

    pred_ids = [f["predicao_id"] for f in feedbacks if f.get("predicao_id")]
    scores_map: dict[str, float] = {}

    for i in range(0, len(pred_ids), ITENS_POR_IN):
        for p in _todas_as_linhas(
                lambda lote=pred_ids[i:i + ITENS_POR_IN]:
                    db.table("predicoes").select("id, score_recuperabilidade").in_("id", lote)):
            scores_map[p["id"]] = p["score_recuperabilidade"]

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
            acertou = (score >= 40 and pagou) or (score < 40 and not pagou)
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

    result = {
        "total_feedbacks": len(feedbacks),
        "total_com_predicao_associada": len(pred_ids),
        "acuracia_geral": acuracia_geral,
        "metricas_por_faixa": metricas,
    }
    _cache_set(cache_key, result)
    return result


@app.get("/performance/pagamentos")
def performance_pagamentos(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    carteira_id: Optional[str] = None,
):
    """Lista individual de quem pagou, com nome, CPF e valor recuperado."""
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    role       = payload.get("role", "")

    if not empresa_id and role != "comando":
        return []

    cache_key = f"pagamentos:{carteira_id or empresa_id}"
    cached = _cache_get(cache_key, ttl=300)
    if cached is not None:
        return cached

    db = get_db()

    if carteira_id:
        _exige_carteira_da_empresa(db, carteira_id, payload)

    empresa_pred_ids: set | None = None
    if carteira_id:
        try:
            empresa_pred_ids = _ids_das_predicoes(db, carteira_id)
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")
    elif empresa_id:
        try:
            cart_ids = _ids_carteiras(db, empresa_id)
            if not cart_ids:
                return []
            pred_res_all: list = []
            for i in range(0, len(cart_ids), 100):
                # Cem carteiras por vez cabem na URL, mas as predições delas
                # passam de mil com folga — daí o lote interno também paginar.
                pr = type("R", (), {"data": _todas_as_linhas(
                    lambda lote=cart_ids[i:i+100]:
                        db.table("predicoes").select("id").in_("carteira_id", lote))})()
                pred_res_all.extend(pr.data or [])
            empresa_pred_ids = {p["id"] for p in pred_res_all}
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")

    _COLS = "cpf, pagou, valor_recuperado, data_pagamento, predicao_id, created_at, registrado_por"
    if empresa_pred_ids is not None:
        # Filtra no banco por predicao_id para não trazer dados de outras empresas
        # Os 5.000 mais recentes de verdade: ordenados depois de ler tudo.
        feedbacks = _feedbacks_das_predicoes(db, _COLS, empresa_pred_ids)[:5000]
    else:
        # Apenas pagamentos vinculados a predições reais — sem predicao_id são dados órfãos
        feedbacks = _todas_as_linhas(
            lambda: db.table("feedbacks").select(_COLS)
                      .not_.is_("predicao_id", "null")
                      .order("created_at", desc=True))[:5000]

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
            "registrado_por":    fb.get("registrado_por") or "",
            "registrado_em":     (fb.get("created_at") or "")[:16],
        })
    _cache_set(cache_key, result)
    return result


@app.get("/feedbacks/status")
def feedbacks_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    carteira_id: Optional[str] = None,
):
    """Retorna mapa cpf → {pagou, valor_recuperado, data_pagamento} com o feedback mais recente por CPF da empresa."""
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    role       = payload.get("role", "")

    if not empresa_id and role != "comando":
        return {}

    cache_key = f"fb_status:{carteira_id or empresa_id}"
    cached = _cache_get(cache_key, ttl=30)
    if cached is not None:
        return cached

    db = get_db()

    if carteira_id:
        _exige_carteira_da_empresa(db, carteira_id, payload)

    empresa_pred_ids: set | None = None
    if carteira_id:
        try:
            empresa_pred_ids = {p["id"] for p in _todas_as_linhas(
                lambda: db.table("predicoes").select("id").eq("carteira_id", carteira_id))}
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")
    elif empresa_id:
        try:
            cart_ids = _ids_carteiras(db, empresa_id)
            # Mesmo sem carteiras o escopo tem de ficar vazio, não nulo: nulo
            # cairia na consulta global e devolveria feedbacks de todo mundo.
            pred_res_all: list = []
            for i in range(0, len(cart_ids), 100):
                # Cem carteiras por vez cabem na URL, mas as predições delas
                # passam de mil com folga — daí o lote interno também paginar.
                pr = type("R", (), {"data": _todas_as_linhas(
                    lambda lote=cart_ids[i:i+100]:
                        db.table("predicoes").select("id").in_("carteira_id", lote))})()
                pred_res_all.extend(pr.data or [])
            empresa_pred_ids = {p["id"] for p in pred_res_all}
        except Exception:
            # Não conseguir montar o escopo da empresa não pode virar consulta
            # global: isso vazaria feedbacks de outras empresas.
            raise HTTPException(status_code=503, detail="Não foi possível montar o escopo da empresa.")

    _COLS2 = "cpf, pagou, valor_recuperado, data_pagamento, predicao_id, empresa, created_at, registrado_por"
    if empresa_pred_ids is not None:
        feedbacks = _feedbacks_das_predicoes(db, _COLS2, empresa_pred_ids)
        if empresa_id and not carteira_id:
            r2 = db.table("feedbacks").select(_COLS2).eq("empresa", empresa_id).is_("predicao_id", "null").order("created_at", desc=True).limit(500).execute()
            feedbacks.extend(r2.data or [])
        feedbacks = feedbacks[:5000]
    else:
        feedbacks = _todas_as_linhas(
            lambda: db.table("feedbacks").select(_COLS2).order("created_at", desc=True))[:5000]

    status_map: dict = {}
    for fb in feedbacks:
        cpf = str(fb.get("cpf") or "").strip()
        if not cpf or cpf in status_map:
            continue
        status_map[cpf] = {
            "pagou":            fb.get("pagou"),
            "valor_recuperado": fb.get("valor_recuperado"),
            "data_pagamento":   fb.get("data_pagamento") or (fb.get("created_at") or "")[:10],
            "registrado_por":   fb.get("registrado_por") or "",
            "registrado_em":    (fb.get("created_at") or "")[:16],
        }

    _cache_set(cache_key, status_map)
    return status_map


@app.get("/admin/modelo/qualidade")
def admin_modelo_qualidade(empresa_id: Optional[str] = None,
                           credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """
    Qualidade do modelo EM USO por uma empresa, medida nos devedores dela com
    pagamento registrado: separação (KS/Gini/AUC), calibração, matriz de
    confusão e comparação com o teste feito no treino. Ver model/diagnostico.py.
    """
    _exigir_comando(credentials)
    empresa = (empresa_id or "").strip().lower()
    if not empresa:
        resultado = {"ok": False, "motivo": "Escolha uma empresa: o diagnóstico mede o modelo que pontua aquela empresa, nos pagamentos dela."}
    else:
        from model.diagnostico import avaliar_modelo_ativo
        try:
            resultado = avaliar_modelo_ativo(get_db(), empresa)
        except Exception as e:
            codigo = _erros.registrar({"path": "/admin/modelo/qualidade"}, e, 500)
            raise HTTPException(status_code=500, detail=f"Erro ao avaliar o modelo. Código: {codigo}.")

    # Procedência do modelo ativo. A interface precisa disso para dizer em que
    # dado o score se apoia: um banco desconfia mais de quem não mostra a régua
    # do que de quem admite estar em calibração inicial.
    resultado["procedencia"] = _procedencia_modelo_ativo(empresa or None)
    return resultado


def _procedencia_modelo_ativo(empresa_id: "str | None" = None) -> dict:
    """Origem e confiabilidade declarada do modelo que está decidendo hoje."""
    from model.retrain import MIN_FEEDBACKS_DEFAULT
    try:
        from model.retrain import _carregar_versoes
        versoes = _carregar_versoes()
        if empresa_id:
            from model import modelos_empresa as _me
            if _me.tem_modelo_proprio(empresa_id):
                versoes = _me.carregar_versoes(empresa_id)
        ativa = versoes.get("versao_ativa", "v1_inicial")
        meta = next((v for v in versoes.get("versoes", []) if v.get("versao") == ativa), {})
    except Exception:
        ativa, meta = "v1_inicial", {}

    n = meta.get("n_feedbacks_reais")
    if n is None:
        n = meta.get("n_amostras")
    tipo_alvo = meta.get("tipo_alvo") or "simulado"
    sintetico = tipo_alvo != "real"

    if sintetico:
        nivel = "sintetico"
        aviso = ("Modelo em calibração inicial: treinado em dados simulados, sem "
                 "nenhum resultado real registrado. Os scores ordenam a carteira "
                 "segundo premissas declaradas, não segundo histórico desta base.")
    elif n is not None and n < MIN_FEEDBACKS_DEFAULT:
        nivel = "insuficiente"
        aviso = (f"Modelo treinado com apenas {n} resultado(s) real(is), abaixo do "
                 f"mínimo de {MIN_FEEDBACKS_DEFAULT}. As métricas têm alta variância "
                 f"e não devem ser apresentadas como desempenho do modelo.")
    else:
        nivel = "ok"
        aviso = ""

    return {
        "versao_ativa": ativa,
        "tipo_alvo": tipo_alvo,
        "n_feedbacks_reais": n,
        "minimo_recomendado": MIN_FEEDBACKS_DEFAULT,
        "nivel": nivel,       # sintetico | insuficiente | ok
        "aviso": aviso,
    }


# ── Modelo por empresa ───────────────────────────────────────────────────────
# Enviar a carteira histórica de um cliente, treinar o modelo DELE e descartar os
# dados. O treino roda em segundo plano (leva minutos), um por vez; o resultado
# fica no versions.json da empresa. Ver docs/PLANO_TREINO_POR_EMPRESA.md.

_JOBS_TREINO: dict = {}
_JOBS_TREINO_MAX = 50
_JOBS_TREINO_LOCK = threading.Lock()
_TRAVA_TREINO = "treino_modelo_empresa"


def _resumo_job(j: dict) -> dict:
    return {k: v for k, v in j.items() if not k.startswith("_")}


def _correr_treino(job_id: str, conteudo: "bytes | None", nome: str, empresa: str, email: str,
                   uid: str, trava: bool) -> None:
    """Treina em segundo plano. Sem `conteudo`, treina com os pagamentos registrados no Mizan."""
    from model import treino_empresa as _te
    job = _JOBS_TREINO[job_id]
    job["estado"] = "treinando"
    try:
        if conteudo is None:
            from model import treino_feedbacks as _tf
            reg = _tf.treinar_empresa(get_db(), empresa, email)
        else:
            reg = _te.treinar(conteudo, nome, empresa, email)
        job.update(estado="concluido", versao=reg["versao"], registro=reg)
        _registrar_auditoria(
            acao="modelo_treinado", entidade="modelo", entidade_id=reg["versao"],
            usuario_email=email, empresa_id=empresa, usuario_id=uid,
            detalhes={"sha256": reg["arquivo"]["sha256"], "n_amostras": reg["n_amostras"],
                      "validacao": reg["validacao"], "origem": reg.get("origem", "arquivo"),
                      "dados_descartados": True})
    except _te.DadosInvalidos as e:
        job.update(estado="recusado", erro=str(e))
    except Exception as e:
        # Mensagem genérica ao cliente; o detalhe vai para o log mascarado.
        codigo = _erros.registrar({"path": "/comando/treino"}, e, 500)
        job.update(estado="falhou", erro=f"O treino falhou por um erro interno. Código: {codigo}.")
    finally:
        job["terminou_em"] = datetime.utcnow().isoformat()
        if trava:
            try:
                _travas.liberar(_TRAVA_TREINO)
            except Exception:
                pass


@app.post("/comando/treino", status_code=202)
async def comando_treinar_modelo(
    file: UploadFile = File(...),
    empresa_id: str = Form(...),
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Inicia o treino do modelo de uma empresa. Devolve o id da tarefa."""
    payload = _exigir_comando(credentials)
    empresa = (empresa_id or "").strip().lower()
    if not empresa:
        raise HTTPException(status_code=422, detail="Informe a empresa.")
    nome = (file.filename or "").lower()
    if not nome.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Arquivo deve ser CSV ou Excel (.csv / .xlsx / .xls).")
    conteudo = await file.read()

    # Um treino por vez, entre instâncias também: ele ocupa memória demais para dois.
    if not _travas.adquirir(_TRAVA_TREINO, duracao_min=30):
        raise HTTPException(status_code=409, detail="Já há um treino em andamento. Aguarde terminar.")
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_TREINO_LOCK:
        while len(_JOBS_TREINO) >= _JOBS_TREINO_MAX:
            _JOBS_TREINO.pop(next(iter(_JOBS_TREINO)))
        _JOBS_TREINO[job_id] = {"id": job_id, "empresa_id": empresa, "estado": "na_fila",
                                "arquivo": file.filename, "iniciou_em": datetime.utcnow().isoformat()}
    threading.Thread(
        target=_correr_treino,
        args=(job_id, conteudo, file.filename or "", empresa, payload.get("email", ""),
              payload.get("sub", ""), True),
        daemon=True).start()
    del conteudo
    return {"id": job_id, "estado": "na_fila"}


class TreinoFeedbacksIn(BaseModel):
    empresa_id: str = Field(..., min_length=1, max_length=100)


@app.post("/comando/treino/feedbacks", status_code=202)
def comando_treinar_com_feedbacks(body: TreinoFeedbacksIn,
                                  credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Treina o modelo de uma empresa com os pagamentos registrados no Mizan para ELA.

    Mesmo fluxo do treino por arquivo: em segundo plano, um por vez, e a versão
    nasce inativa. Os pagamentos de outras empresas não entram.
    """
    payload = _exigir_comando(credentials)
    empresa = body.empresa_id.strip().lower()
    from model import modelos_empresa as _me
    try:
        _me.slug(empresa)
    except ValueError:
        raise HTTPException(status_code=422, detail="Empresa inválida.")
    if not _travas.adquirir(_TRAVA_TREINO, duracao_min=30):
        raise HTTPException(status_code=409, detail="Já há um treino em andamento. Aguarde terminar.")
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_TREINO_LOCK:
        while len(_JOBS_TREINO) >= _JOBS_TREINO_MAX:
            _JOBS_TREINO.pop(next(iter(_JOBS_TREINO)))
        _JOBS_TREINO[job_id] = {"id": job_id, "empresa_id": empresa, "estado": "na_fila",
                                "arquivo": None, "origem": "feedbacks",
                                "iniciou_em": datetime.utcnow().isoformat()}
    threading.Thread(
        target=_correr_treino,
        args=(job_id, None, "", empresa, payload.get("email", ""), payload.get("sub", ""), True),
        daemon=True).start()
    return {"id": job_id, "estado": "na_fila"}


@app.get("/comando/treino/{job_id}")
def comando_estado_treino(job_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    j = _JOBS_TREINO.get(job_id)
    if j is None:
        # Reinício do servidor apaga as tarefas em memória; o resultado de um
        # treino concluído continua em /comando/modelos.
        raise HTTPException(status_code=404, detail="Tarefa não encontrada (o servidor pode ter reiniciado). Veja a lista de versões.")
    return _resumo_job(j)


@app.get("/comando/modelos")
def comando_listar_modelos(empresa_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    from model import modelos_empresa as _me
    empresa = (empresa_id or "").strip().lower()
    try:
        v = _me.carregar_versoes(empresa)
    except ValueError:
        raise HTTPException(status_code=422, detail="Empresa inválida.")
    return {"empresa_id": empresa, "versao_ativa": v.get("versao_ativa"),
            "usando": "proprio" if v.get("versao_ativa") else "global",
            "versoes": list(reversed(v.get("versoes", [])))}


class AtivarModeloIn(BaseModel):
    empresa_id: str
    versao: Optional[str] = None
    forcar: bool = False


@app.post("/comando/modelos/ativar")
def comando_ativar_modelo(body: AtivarModeloIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    from model import modelos_empresa as _me
    empresa = (body.empresa_id or "").strip().lower()
    try:
        dados = _me.carregar_versoes(empresa)
    except ValueError:
        raise HTTPException(status_code=422, detail="Empresa inválida.")
    reg = next((v for v in dados["versoes"] if v.get("versao") == body.versao), None)
    if reg is None:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")
    m = reg.get("metricas") or {}
    auc_novo = (m.get("novo") or {}).get("auc")
    auc_atual = (m.get("atual") or {}).get("auc")
    if not body.forcar and auc_novo is not None and auc_atual is not None and auc_novo < auc_atual:
        raise HTTPException(
            status_code=409,
            detail=f"O modelo novo (AUC {auc_novo}) não supera o que a empresa usa hoje (AUC {auc_atual}) "
                   "na mesma fatia de teste. Confirme para ativar mesmo assim.")
    try:
        _me.ativar(empresa, body.versao)
    except (KeyError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=f"Não foi possível ativar: {e}")
    try:
        from storage_ml import upload_empresa
        upload_empresa(_me.slug(empresa), _me.pasta(empresa))
    except Exception as e:
        print(f"[Storage] Aviso: upload pós-ativação falhou: {e}")
    _registrar_auditoria(acao="modelo_ativado", entidade="modelo", entidade_id=body.versao,
                         usuario_email=payload.get("email", ""), empresa_id=empresa,
                         usuario_id=payload.get("sub", ""), detalhes={"forcado": body.forcar})
    return {"ok": True, "empresa_id": empresa, "versao_ativa": body.versao}


@app.post("/comando/modelos/desativar")
def comando_desativar_modelo(body: AtivarModeloIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Volta a empresa ao modelo global. As versões treinadas ficam guardadas."""
    payload = _exigir_comando(credentials)
    from model import modelos_empresa as _me
    empresa = (body.empresa_id or "").strip().lower()
    try:
        _me.desativar(empresa)
    except ValueError:
        raise HTTPException(status_code=422, detail="Empresa inválida.")
    try:
        from storage_ml import upload_empresa
        upload_empresa(_me.slug(empresa), _me.pasta(empresa))
    except Exception as e:
        print(f"[Storage] Aviso: upload pós-desativação falhou: {e}")
    _registrar_auditoria(acao="modelo_desativado", entidade="modelo", entidade_id=empresa,
                         usuario_email=payload.get("email", ""), empresa_id=empresa,
                         usuario_id=payload.get("sub", ""), detalhes={})
    return {"ok": True, "empresa_id": empresa, "usando": "global"}


# ── Chaves de API (integração: webhook de pagamento) ─────────────────────────
# Antes só dava para criar uma chave inserindo a linha à mão no Supabase. A
# chave é mostrada UMA vez, na criação; o banco guarda só o SHA-256.

class ChaveApiIn(BaseModel):
    empresa_id: str = Field(..., min_length=1, max_length=100)
    rotulo: str = Field(..., min_length=2, max_length=80)


@app.get("/comando/api-keys")
def comando_listar_chaves(empresa_id: Optional[str] = None,
                          credentials: HTTPAuthorizationCredentials = Security(bearer)):
    _exigir_comando(credentials)
    q = get_db().table("api_keys").select(_COLS_API_KEY)
    if empresa_id:
        q = q.eq("empresa_id", empresa_id.strip().lower())
    return q.order("created_at", desc=True).limit(200).execute().data or []


@app.post("/comando/api-keys")
def comando_criar_chave(body: ChaveApiIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    import secrets as _secrets
    empresa = body.empresa_id.strip().lower()
    chave = "mzk_" + _secrets.token_urlsafe(32)
    linha = {"empresa_id": empresa, "empresa_nome": empresa, "rotulo": body.rotulo.strip(),
             "api_key_hash": _hash_api_key(chave), "ativa": True}
    res = get_db().table("api_keys").insert(linha).execute()
    criada = (res.data or [{}])[0]
    _registrar_auditoria(acao="chave_api_criada", entidade="api_key", entidade_id=str(criada.get("id", "")),
                         usuario_email=payload.get("email", ""), empresa_id=empresa, usuario_id=payload.get("sub", ""),
                         detalhes={"rotulo": linha["rotulo"]})
    return {"id": criada.get("id"), "empresa_id": empresa, "rotulo": linha["rotulo"], "chave": chave,
            "aviso": "Copie agora: a chave não é mostrada de novo. O Mizan guarda só uma impressão dela."}


@app.post("/comando/api-keys/{chave_id}/revogar")
def comando_revogar_chave(chave_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    chave_id = _uuid_ou_404(chave_id)
    db = get_db()
    atual = db.table("api_keys").select(_COLS_API_KEY).eq("id", chave_id).limit(1).execute().data
    if not atual:
        raise HTTPException(status_code=404, detail="Chave não encontrada.")
    db.table("api_keys").update({"ativa": False}).eq("id", chave_id).execute()
    _registrar_auditoria(acao="chave_api_revogada", entidade="api_key", entidade_id=chave_id,
                         usuario_email=payload.get("email", ""), empresa_id=atual[0].get("empresa_id") or "",
                         usuario_id=payload.get("sub", ""), detalhes={"rotulo": atual[0].get("rotulo")})
    return {"ok": True}


# ── Central de Ajuda ─────────────────────────────────────────────────────────
# Catálogo estático em backend/ajuda/*.md; busca local em ajuda_busca.py. A
# pergunta não sai do servidor e não vai para o log. Cada perfil enxerga só as
# respostas das telas que tem.

class AjudaBuscaIn(BaseModel):
    pergunta: str = Field(..., min_length=2, max_length=300)


_LACUNAS_VISTAS: dict = {}


def _registrar_lacuna(tipo: str, pergunta: str, entrada_id: "str | None", perfil: str, sub: str) -> None:
    """Guarda, sem identificar ninguém, uma busca que a Central não resolveu.

    Só entra o texto já mascarado, o perfil e (em "não resolveu") qual resposta
    foi mostrada. Quem buscou não é gravado. Para não contar a mesma pessoa
    várias vezes, a memória do processo lembra por uma hora um resumo
    irreversível de (pessoa, tipo, pergunta): isso nunca vai para o banco.
    Qualquer falha é engolida e não loga o texto: é telemetria, não pode
    atrapalhar a busca nem vazar a pergunta para o log.
    """
    import hashlib
    from ajuda_duvidas import mascarar_pii
    from ajuda_lacunas import chave_de
    try:
        texto, _ = mascarar_pii((pergunta or "").strip()[:300])
        chave = chave_de(texto)
        if len(texto) < 2 or not chave:
            return
        marca = hashlib.sha256(f"{sub}|{tipo}|{chave}".encode()).hexdigest()
        agora = _time.time()
        if len(_LACUNAS_VISTAS) > 5000:
            _LACUNAS_VISTAS.clear()
        if agora - _LACUNAS_VISTAS.get(marca, 0) < 3600:
            return
        _LACUNAS_VISTAS[marca] = agora
        get_db().table("ajuda_lacunas").insert({
            "tipo": tipo, "pergunta": texto, "chave": chave,
            "entrada_id": entrada_id, "perfil": perfil}).execute()
    except Exception:
        print("[Ajuda] não consegui registrar uma busca sem resposta")


@app.post("/ajuda/buscar")
def ajuda_buscar(body: AjudaBuscaIn, tarefas: BackgroundTasks,
                 credentials: HTTPAuthorizationCredentials = Security(bearer)):
    import ajuda as _aj
    import ajuda_busca as _ab
    payload = _usuario_autenticado(credentials)
    perfil = payload.get("role", "operador")
    achados = _ab.buscador_para(perfil).buscar(body.pergunta, k=3)
    if not achados["certeza"]:
        tarefas.add_task(_registrar_lacuna, "sem_resposta", body.pergunta, None, perfil, payload["sub"])
    por_id = {e.id: e for e in _aj.para_perfil(perfil)}
    return {
        "certeza": achados["certeza"],
        "resultados": [{**_aj.para_json(por_id[r["id"]], perfil), "score": r["score"]}
                       for r in achados["resultados"] if r["id"] in por_id],
    }


class NaoResolveuIn(BaseModel):
    pergunta: str = Field(..., min_length=2, max_length=300)
    entrada_id: Optional[str] = Field(None, max_length=100)


@app.post("/ajuda/nao-resolveu")
def ajuda_nao_resolveu(body: NaoResolveuIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """"Isto não resolveu": a resposta mostrada não bastou. Anônimo, com o perfil."""
    import ajuda as _aj
    payload = _usuario_autenticado(credentials)
    perfil = payload.get("role", "operador")
    # só vale como "qual resposta" uma que este perfil pode ver
    visiveis = {e.id for e in _aj.para_perfil(perfil)}
    entrada = body.entrada_id if body.entrada_id in visiveis else None
    _registrar_lacuna("nao_resolveu", body.pergunta, entrada, perfil, payload["sub"])
    return {"ok": True}


@app.get("/ajuda/indice")
def ajuda_indice(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    import ajuda as _aj
    perfil = _usuario_autenticado(credentials).get("role", "operador")
    return _aj.indice(perfil)


@app.get("/ajuda/entradas/{entrada_id}")
def ajuda_entrada(entrada_id: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    import ajuda as _aj
    perfil = _usuario_autenticado(credentials).get("role", "operador")
    for e in _aj.para_perfil(perfil):
        if e.id == entrada_id:
            return _aj.para_json(e, perfil)
    # Entrada de tela que o perfil não tem responde como inexistente.
    raise HTTPException(status_code=404, detail="Resposta não encontrada.")


@app.get("/ajuda/estado-do-modelo")
def ajuda_estado_do_modelo(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Em que dados o score desta empresa se apoia: simulados ou reais."""
    payload = _usuario_autenticado(credentials)
    proc = _procedencia_modelo_ativo(payload.get("empresa_id") or None)
    return {"nivel": proc["nivel"], "aviso": proc["aviso"], "tipo_alvo": proc["tipo_alvo"]}


# ── Dúvidas ao COMANDO ───────────────────────────────────────────────────────
# Quem não achou a resposta na Central pergunta ao COMANDO. Quem pergunta vê as
# próprias; o administrador vê as da equipe (mesma empresa); o COMANDO vê todas e
# responde. O texto é mascarado antes de gravar (ver ajuda_duvidas.py).

def _uuid_ou_404(valor: str) -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except ValueError:
        raise HTTPException(status_code=404, detail="Dúvida não encontrada.")


class DuvidaIn(BaseModel):
    pergunta: str = Field(..., min_length=3, max_length=2000)
    tela: Optional[str] = Field(None, max_length=120)
    buscou: Optional[str] = Field(None, max_length=300)


@app.post("/ajuda/duvidas", status_code=201)
def ajuda_enviar_duvida(body: DuvidaIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    from ajuda_duvidas import mascarar_pii
    payload = _usuario_autenticado(credentials)
    pergunta, n1 = mascarar_pii(body.pergunta.strip())
    buscou, n2 = mascarar_pii((body.buscou or "").strip())
    if len(pergunta) < 3:
        raise HTTPException(status_code=422, detail="Escreva a sua dúvida.")
    linha = {
        "empresa_id": payload.get("empresa_id", "") or "",
        "autor_id": payload["sub"], "autor_email": payload.get("email", ""),
        "autor_nome": payload.get("nome", ""),
        "pergunta": pergunta, "tela": (body.tela or "")[:120] or None, "buscou": buscou or None,
    }
    res = get_db().table("duvidas").insert(linha).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Não foi possível registrar a dúvida.")
    return {"id": res.data[0]["id"], "mascarado": (n1 + n2) > 0}


_COLUNAS_MINHA_DUVIDA = "id, created_at, pergunta, estado, resposta, respondida_em, visto_em"


@app.get("/ajuda/duvidas/minhas")
def ajuda_minhas_duvidas(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _usuario_autenticado(credentials)
    res = (get_db().table("duvidas").select(_COLUNAS_MINHA_DUVIDA)
           .eq("autor_id", payload["sub"]).order("created_at", desc=True).limit(100).execute())
    return res.data or []


@app.get("/ajuda/duvidas/novidades")
def ajuda_duvidas_novidades(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Quantas respostas novas esperam por quem perguntou. Acende o aviso do menu."""
    payload = _usuario_autenticado(credentials)
    res = (get_db().table("duvidas").select("id", count="exact")
           .eq("autor_id", payload["sub"]).eq("estado", "respondida").is_("visto_em", "null")
           .limit(1).execute())
    return {"respondidas_nao_vistas": res.count or 0}


@app.post("/ajuda/duvidas/vistas")
def ajuda_duvidas_vistas(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Quem perguntou abriu as respostas: apaga o aviso."""
    payload = _usuario_autenticado(credentials)
    (get_db().table("duvidas").update({"visto_em": datetime.utcnow().isoformat()})
     .eq("autor_id", payload["sub"]).eq("estado", "respondida").is_("visto_em", "null").execute())
    return {"ok": True}


@app.get("/ajuda/duvidas/equipe")
def ajuda_duvidas_da_equipe(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """O administrador acompanha o que a equipe dele perguntou. Só leitura."""
    payload = _exigir_admin_ou_comando(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="O COMANDO vê todas as dúvidas em /comando/duvidas.")
    res = (get_db().table("duvidas")
           .select("id, created_at, autor_nome, autor_email, pergunta, estado, resposta, respondida_em")
           .eq("empresa_id", payload.get("empresa_id", "")).order("created_at", desc=True)
           .limit(200).execute())
    return res.data or []


class RespostaIn(BaseModel):
    resposta: str = Field(..., min_length=2, max_length=4000)


class SugerirIn(BaseModel):
    sugerir: bool = True
    titulo: Optional[str] = Field(None, max_length=200)


class RevisaoIn(BaseModel):
    estado: str


@app.get("/comando/duvidas")
def comando_listar_duvidas(estado: str = "aberta", empresa_id: Optional[str] = None,
                           limite: int = 50, offset: int = 0,
                           credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """`estado`: aberta | respondida | sugestao (respostas marcadas para virar ajuda) | todas."""
    _exigir_comando(credentials)
    if estado not in ("aberta", "respondida", "sugestao", "todas"):
        raise HTTPException(status_code=422, detail="estado inválido.")
    db = get_db()
    limite, offset = min(max(limite, 1), 100), max(offset, 0)
    q = db.table("duvidas").select("*", count="exact")
    if estado in ("aberta", "respondida"):
        q = q.eq("estado", estado)
    elif estado == "sugestao":
        q = q.eq("sugestao_estado", "pendente")
    if empresa_id:
        q = q.eq("empresa_id", empresa_id.strip().lower())
    res = q.order("created_at", desc=(estado != "aberta")).range(offset, offset + limite - 1).execute()
    abertas = db.table("duvidas").select("id", count="exact").eq("estado", "aberta").limit(1).execute()
    sug = db.table("duvidas").select("id", count="exact").eq("sugestao_estado", "pendente").limit(1).execute()
    return {"itens": res.data or [], "total": res.count or 0,
            "abertas": abertas.count or 0, "sugestoes_pendentes": sug.count or 0}


def _duvida_do_comando(db, duvida_id: str) -> dict:
    r = db.table("duvidas").select("*").eq("id", _uuid_ou_404(duvida_id)).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Dúvida não encontrada.")
    return r.data[0]


@app.post("/comando/duvidas/{duvida_id}/responder")
def comando_responder_duvida(duvida_id: str, body: RespostaIn,
                             credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = _exigir_comando(credentials)
    db = get_db()
    d = _duvida_do_comando(db, duvida_id)
    agora = datetime.utcnow().isoformat()
    # Responder de novo é permitido (corrigir a resposta): volta a avisar quem perguntou.
    db.table("duvidas").update({
        "estado": "respondida", "resposta": body.resposta.strip(),
        "respondida_por": payload.get("email", ""), "respondida_em": agora, "visto_em": None,
    }).eq("id", d["id"]).execute()
    _registrar_auditoria(acao="duvida_respondida", entidade="duvida", entidade_id=d["id"],
                         usuario_email=payload.get("email", ""), empresa_id=d.get("empresa_id", ""),
                         usuario_id=payload.get("sub", ""), detalhes={"reresposta": d["estado"] == "respondida"})
    return {"ok": True}


@app.post("/comando/duvidas/{duvida_id}/sugerir")
def comando_sugerir_para_ajuda(duvida_id: str, body: SugerirIn,
                               credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Marca a resposta como candidata a virar uma entrada da Central (ou desmarca).
    Não publica nada: a entrada só nasce depois da revisão e de passar nos testes."""
    payload = _exigir_comando(credentials)
    db = get_db()
    d = _duvida_do_comando(db, duvida_id)
    if d["estado"] != "respondida":
        raise HTTPException(status_code=409, detail="Responda a dúvida antes de sugerir uma entrada.")
    if body.sugerir:
        patch = {"sugestao_estado": "pendente", "sugestao_titulo": (body.titulo or "").strip() or None,
                 "sugestao_revisada_por": None, "sugestao_revisada_em": None}
    else:
        patch = {"sugestao_estado": None, "sugestao_titulo": None,
                 "sugestao_revisada_por": None, "sugestao_revisada_em": None}
    db.table("duvidas").update(patch).eq("id", d["id"]).execute()
    _registrar_auditoria(acao="duvida_sugerida_para_ajuda" if body.sugerir else "duvida_sugestao_retirada",
                         entidade="duvida", entidade_id=d["id"], usuario_email=payload.get("email", ""),
                         empresa_id=d.get("empresa_id", ""), usuario_id=payload.get("sub", ""), detalhes={})
    return {"ok": True}


@app.post("/comando/duvidas/{duvida_id}/sugestao")
def comando_revisar_sugestao(duvida_id: str, body: RevisaoIn,
                             credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Revisão: aprovada = vale escrever a entrada; descartada = não."""
    payload = _exigir_comando(credentials)
    if body.estado not in ("aprovada", "descartada"):
        raise HTTPException(status_code=422, detail="estado deve ser 'aprovada' ou 'descartada'.")
    db = get_db()
    d = _duvida_do_comando(db, duvida_id)
    if d.get("sugestao_estado") != "pendente":
        raise HTTPException(status_code=409, detail="Não há sugestão pendente nesta dúvida.")
    db.table("duvidas").update({
        "sugestao_estado": body.estado, "sugestao_revisada_por": payload.get("email", ""),
        "sugestao_revisada_em": datetime.utcnow().isoformat(),
    }).eq("id", d["id"]).execute()
    _registrar_auditoria(acao=f"duvida_sugestao_{body.estado}", entidade="duvida", entidade_id=d["id"],
                         usuario_email=payload.get("email", ""), empresa_id=d.get("empresa_id", ""),
                         usuario_id=payload.get("sub", ""), detalhes={})
    return {"ok": True}


@app.get("/comando/ajuda/lacunas")
def comando_lacunas_da_ajuda(dias: int = 90, estado: str = "pendentes", limite: int = 50,
                             credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """O que a Central não soube responder, agrupado, da pergunta mais repetida para a menos."""
    from datetime import timedelta
    import ajuda_busca as _ab
    from ajuda_lacunas import agrupar
    _exigir_comando(credentials)
    if estado not in ("pendentes", "tratadas", "todas"):
        raise HTTPException(status_code=422, detail="estado inválido.")
    dias, limite = min(max(dias, 1), 365), min(max(limite, 1), 200)
    db = get_db()
    corte = (datetime.utcnow() - timedelta(days=dias)).isoformat()
    linhas = _todas_as_linhas(lambda: db.table("ajuda_lacunas").select("*").gte("created_at", corte))
    grupos = agrupar(linhas)
    if estado == "pendentes":
        grupos = [g for g in grupos if not g["tratada"]]
    elif estado == "tratadas":
        grupos = [g for g in grupos if g["tratada"]]
    buscador = _ab.buscador_para("comando")
    por_id = {e.id: e for e in buscador.entradas}
    for g in grupos[:limite]:
        # a resposta que a busca achou mais perto: o ponto de partida de quem vai escrever
        perto = buscador.buscar(g["exemplo"], k=1)["resultados"]
        g["mais_perto"] = ({"id": perto[0]["id"], "titulo": por_id[perto[0]["id"]].titulo, "score": perto[0]["score"]}
                           if perto else None)
    return {"grupos": grupos[:limite], "total_de_grupos": len(grupos), "total_de_registros": len(linhas), "dias": dias}


class TratarLacunaIn(BaseModel):
    chave: str = Field(..., min_length=1, max_length=300)
    tratada: bool = True


@app.post("/comando/ajuda/lacunas/tratar")
def comando_tratar_lacuna(body: TratarLacunaIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Marca como tratada (a resposta foi escrita) ou desfaz. Se a pergunta voltar a
    aparecer depois, ela volta para a lista como 'reapareceu'."""
    payload = _exigir_comando(credentials)
    patch = ({"tratada_em": datetime.utcnow().isoformat(), "tratada_por": payload.get("email", "")}
             if body.tratada else {"tratada_em": None, "tratada_por": None})
    q = get_db().table("ajuda_lacunas").update(patch).eq("chave", body.chave)
    if body.tratada:
        q = q.is_("tratada_em", "null")          # não sobrescreve quem já tratou antes
    q.execute()
    _registrar_auditoria(acao="lacuna_tratada" if body.tratada else "lacuna_reaberta", entidade="ajuda",
                         entidade_id=body.chave[:80], usuario_email=payload.get("email", ""),
                         usuario_id=payload.get("sub", ""), detalhes={})
    return {"ok": True}


class LimparLacunasIn(BaseModel):
    dias: int = Field(..., ge=30, le=3650)


@app.post("/comando/ajuda/lacunas/limpar")
def comando_limpar_lacunas(body: LimparLacunasIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Apaga o registro de buscas mais antigo que `dias` (mínimo 30)."""
    from datetime import timedelta
    payload = _exigir_comando(credentials)
    corte = (datetime.utcnow() - timedelta(days=body.dias)).isoformat()
    get_db().table("ajuda_lacunas").delete().lt("created_at", corte).execute()
    _registrar_auditoria(acao="lacunas_limpas", entidade="ajuda", entidade_id="lacunas",
                         usuario_email=payload.get("email", ""), usuario_id=payload.get("sub", ""),
                         detalhes={"mais_antigas_que_dias": body.dias})
    return {"ok": True}


@app.get("/admin/price-model")
def admin_price_model_stats(empresa_id: Optional[str] = None,
                            credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Metadados e métricas do modelo de preço ATIVO de uma empresa."""
    _exigir_comando(credentials)
    from model.price_model import stats as _price_stats
    empresa = (empresa_id or "").strip().lower()
    s = _price_stats(empresa) if empresa else None
    if s is None:
        return {
            "disponivel": False,
            "empresa_id": empresa or None,
            "mensagem": (
                "O modelo de preço é por empresa: é treinado com os pagamentos dela junto com a versão do "
                "modelo (Treinar por empresa) e passa a valer quando a versão é ativada. Precisa de pelo menos "
                "15 pagamentos registrados e 5 com valor recuperado. Sem ele, vale a premissa da empresa."
                if empresa else
                "O modelo de preço agora é por empresa. Escolha uma empresa para ver o dela."
            ),
        }
    return {**s, "empresa_id": empresa}


@app.get("/admin/drift")
def detectar_drift(empresa_id: Optional[str] = None, dias: int = 30,
                   credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Deriva da população de UMA empresa: PSI dos scores das análises dela nos
    últimos `dias` contra a distribuição congelada no treino do modelo em uso.

    Antes havia uma segunda "deriva", diferente do PSI da análise: a média de
    score dos últimos 30 dias contra a do histórico inteiro (que incluía os
    próprios 30 dias), todas as empresas juntas, com um limite fixo de 10
    pontos, e um e-mail a cada vez que a tela abria (achado D4). Agora é o mesmo
    PSI, com a mesma régua (model/psi.py), por empresa e sem efeito colateral.
    """
    _exigir_comando(credentials)
    empresa = (empresa_id or "").strip().lower()
    if not empresa:
        return {"status": "escolha_empresa", "drift_detectado": False,
                "mensagem": "Escolha uma empresa para medir a deriva da população dela."}
    from datetime import timedelta
    from model.psi import calcular
    from model.score import _carregar_modelos

    dias = min(max(int(dias or 30), 1), 365)
    db = get_db()
    corte = (datetime.utcnow() - timedelta(days=dias)).isoformat()
    cart_ids = [c["id"] for c in _todas_as_linhas(
        lambda: db.table("carteiras").select("id").eq("empresa_id", empresa))]
    scores: list = []
    for i in range(0, len(cart_ids), ITENS_POR_IN):
        parte = cart_ids[i:i + ITENS_POR_IN]
        scores += [float(p["score_recuperabilidade"]) for p in _todas_as_linhas(
            lambda: db.table("predicoes").select("id, score_recuperabilidade")
                      .in_("carteira_id", parte).gte("created_at", corte))
                   if p.get("score_recuperabilidade") is not None]

    _, _, meta = _carregar_modelos(empresa)
    r = calcular(scores, meta.get("psi_referencia"))
    if not r.get("ok"):
        return {"status": "indisponivel", "drift_detectado": False, "empresa_id": empresa, "dias": dias,
                "n": len(scores), "psi": r, "mensagem": r.get("motivo")}
    return {
        "status": r["nivel"],
        "drift_detectado": r["nivel"] != "estavel",
        "empresa_id": empresa,
        "dias": dias,
        "n": len(scores),
        "psi": r,
        "mensagem": f"PSI {r['psi']} nos devedores analisados nos últimos {dias} dias: {r['leitura']}",
    }


@app.get("/recomendacao/{cpf}")
def recomendacao_devedor(cpf: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """
    Retorna a melhor abordagem de cobrança para o CPF via LinUCB.
    Salva a recomendação no Supabase para fechar o loop de aprendizado via POST /feedback.
    """
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    db = get_db()

    role = payload.get("role", "")
    if not empresa_id and role != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")

    # Em lotes de carteiras: passar todas num único in_ estourava o tamanho da
    # URL de quem tem centenas delas.
    pred = _predicao_do_cpf(
        db, cpf, empresa_id,
        colunas="cpf, nome, produto, uf, valor_divida, renda_estimada, dias_em_atraso, "
                "score_recuperabilidade, perfil_cluster, cluster_id, carteira_id")
    if not pred:
        raise HTTPException(status_code=404, detail=f"Nenhuma predição encontrada para CPF: {cpf}")
    valor_divida = float(pred.get("valor_divida") or 0)
    renda = float(pred.get("renda_estimada") or 0)
    comprometimento = valor_divida / renda if renda > 0 else 1.0

    devedor = {**pred, "comprometimento_renda": comprometimento}

    from model.bandit import recomendar as _bandit_recomendar
    rec = _bandit_recomendar(devedor, empresa_id)

    try:
        db.table("recomendacoes").insert({
            "cpf":      cpf,
            "empresa_id": empresa_id,
            "acao_id":  rec["acao_id"],
            "canal":    rec["canal"],
            "oferta":   rec["oferta"],
            "score_ucb": rec["score_ucb"],
            "contexto": rec["contexto"],
        }).execute()
    except Exception as _e:
        print(f"[Bandit] Erro ao salvar recomendacao: {_e}")

    return {**rec, "cpf": cpf, "nome": pred.get("nome")}


@app.get("/predicoes/{cpf}/propostas")
def propostas_devedor(
    cpf: str,
    despesas_mensais: Optional[float] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Monta as propostas de renegociação para o CPF, com margem livre e valor esperado.

    Filtra pelo que cabe no bolso do devedor e ordena por valor esperado —
    a decisão descrita na referência técnica. As propostas que não cabem
    continuam na resposta, marcadas, para o operador ver por que foram
    descartadas em vez de receber uma lista sem explicação.
    """
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    db = get_db()

    role = payload.get("role", "")
    if not empresa_id and role != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")

    pred = _predicao_do_cpf(
        db, cpf, empresa_id,
        # despesas_mensais: sem pedir esta coluna, a margem livre só existia se o
        # operador digitasse as despesas, mesmo com a carteira trazendo-as.
        colunas="cpf, nome, valor_divida, renda_estimada, despesas_mensais, dias_em_atraso, "
                "score_recuperabilidade, probabilidade_pagamento, carteira_id")
    if not pred:
        raise HTTPException(status_code=404, detail=f"Nenhuma predição encontrada para CPF: {cpf}")
    from model.proposta import avaliar, calcular_margem, montar_propostas

    politica = _politica_proposta(empresa_id)
    # A carteira pode trazer as despesas; a query string permite ao operador
    # informar na hora, quando o devedor declara na ligação.
    despesas = despesas_mensais
    if despesas is None:
        despesas = pred.get("despesas_mensais")
    margem = calcular_margem(pred.get("renda_estimada"), despesas, politica)

    divida = float(pred.get("valor_divida") or 0)
    propostas = montar_propostas(divida)

    # A probabilidade do modelo é uma por devedor, igual para toda oferta.
    # Ela serve de ponto de partida; o que distingue uma proposta da outra por
    # probabilidade é o feedback real de renegociação, que o bandit acumula
    # por tipo de oferta. Onde já existe histórico, ele manda; onde não
    # existe, a estimativa é exatamente a do modelo.
    pop = pred.get("probabilidade_pagamento")
    if pop is None:
        score = float(pred.get("score_recuperabilidade") or 0)
        pop = max(0.0, min(1.0, score / 100))
        origem_pop = "score"
    else:
        pop = float(pop)
        origem_pop = "modelo"

    try:
        from model.bandit import pop_por_oferta as _pop_oferta
        pops_oferta = _pop_oferta(empresa_id, pop)
    except Exception as _e:
        # Bandit indisponível não pode derrubar a proposta: cai na do modelo.
        print(f"[Propostas] PoP por oferta indisponível: {_e}")
        pops_oferta = None

    aval = avaliar(propostas, margem, [pop] * len(propostas), origem_pop,
                   politica, pop_por_oferta=pops_oferta)
    return {
        "cpf": cpf,
        "nome": pred.get("nome"),
        "valor_divida": divida,
        **aval.para_json(),
    }


def _empresa_da_carteira(db, carteira_id) -> str:
    if not carteira_id:
        return ""
    try:
        r = db.table("carteiras").select("empresa_id").eq("id", carteira_id).limit(1).execute()
        return (r.data or [{}])[0].get("empresa_id") or ""
    except Exception:
        return ""


@app.get("/predicoes/{cpf}/explicacao")
def explicar_score_devedor(cpf: str, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """
    Explica por que ESSE CPF específico recebeu o score que recebeu: para cada variável,
    mostra o quanto ela empurrou o score para cima ou para baixo em relação ao devedor
    médio da base de treino. Atende ao direito à explicação de decisão automatizada (LGPD art. 20).
    """
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    db = get_db()

    role = payload.get("role", "")
    if not empresa_id and role != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")

    pred = _predicao_do_cpf(
        db, cpf, empresa_id,
        colunas="cpf, nome, produto, uf, status, valor_divida, renda_estimada, "
                "dias_em_atraso, score_recuperabilidade, carteira_id")
    if not pred:
        raise HTTPException(status_code=404, detail=f"Nenhuma predição encontrada para CPF: {cpf}")
    from model.score import explicar_predicao
    try:
        # Explica com o modelo que de fato pontuou: o da empresa dona da carteira.
        explicacao = explicar_predicao(pred, empresa_id or _empresa_da_carteira(db, pred.get("carteira_id")))
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Modelo não encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar explicação: {e}")

    return {**explicacao, "cpf": cpf, "nome": pred.get("nome"),
            "score_registrado": pred.get("score_recuperabilidade")}


@app.get("/admin/bandit/stats")
def bandit_stats(
    empresa_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estatísticas do bandit por ação: tentativas, recompensa média, convergência."""
    payload = _exigir_comando(credentials)
    _emp = _empresa_do_bandit(payload, empresa_id)
    from model.bandit import carregar_bandit
    bandit = carregar_bandit(_emp)
    total = sum(bandit.n_tentativas)
    return {
        "empresa_id": _emp,
        "total_interacoes": total,
        "alpha": bandit.alpha,
        "fase": "exploração_inicial" if total == 0 else "aprendendo" if total < 50 else "calibrado",
        "acoes": bandit.stats(),
    }


@app.get("/admin/feature-importance")
def feature_importance(
    empresa_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """O que mais pesa no score do modelo que pontua UMA empresa, medido nos
    devedores da análise mais recente dela (até 500, amostra pela ordem do id).

    Antes lia `feature_importances_` do modelo geral, que o modelo calibrado não
    tem: a rota respondia 400 e a tela mostrava sempre "indisponível". Agora usa
    o mesmo método da explicação de cada devedor (model/score.peso_das_variaveis).
    """
    _exigir_comando(credentials)
    empresa = (empresa_id or "").strip().lower()
    if not empresa:
        return {"ok": False, "features": [],
                "mensagem": "Escolha uma empresa: o peso é medido no modelo que pontua aquela empresa, nos devedores dela."}
    from model.diagnostico import _modelo_em_uso
    from model.score import _carregar_modelos, peso_das_variaveis
    db = get_db()
    carts = (db.table("carteiras").select("id, created_at").eq("empresa_id", empresa)
             .order("created_at", desc=True).limit(1).execute().data or [])
    if not carts:
        return {"ok": False, "features": [], "empresa_id": empresa,
                "mensagem": "Esta empresa ainda não tem análise para medir."}
    linhas = (db.table("predicoes")
              .select("id, produto, uf, status, valor_divida, renda_estimada, dias_em_atraso")
              .eq("carteira_id", carts[0]["id"]).order("id").limit(500).execute().data or [])
    if len(linhas) < 20:
        return {"ok": False, "features": [], "empresa_id": empresa,
                "mensagem": f"A análise mais recente tem {len(linhas)} devedores; poucos para medir."}
    try:
        r = peso_das_variaveis(pd.DataFrame(linhas).drop(columns=["id"]), empresa)
        _, _, meta = _carregar_modelos(empresa)
    except Exception as e:
        codigo = _erros.registrar({"path": "/admin/feature-importance"}, e, 500)
        raise HTTPException(status_code=500, detail=f"Não foi possível medir o peso das variáveis. Código: {codigo}.")
    from model.score import NOMES_VARIAVEIS
    return {
        "ok": True,
        "empresa_id": empresa,
        "carteira_id": carts[0]["id"],
        "modelo": _modelo_em_uso(empresa),
        "n_devedores": r["n_devedores"],
        "score_medio": r["score_medio"],
        "total_features": len(meta.get("feature_names") or []),
        "features": [{"nome": v["nome"], "variavel": v["variavel"], "percentual": v["percentual"],
                      "impacto_medio_pontos": v["impacto_medio_pontos"],
                      "efeito_medio_pontos": v["efeito_medio_pontos"]} for v in r["variaveis"]],
        "nao_medidas": [NOMES_VARIAVEIS.get(c, c) for c in r["nao_medidas"]],
    }


@app.get("/admin/bandit/convergencia")
def bandit_convergencia(
    empresa_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Incerteza e convergência por ação do bandit. Incerteza < 0.01 com ≥10 tentativas = convergido."""
    payload = _exigir_comando(credentials)
    from model.bandit import convergencia_stats, carregar_bandit
    _emp   = _empresa_do_bandit(payload, empresa_id)
    bandit = carregar_bandit(_emp)
    total  = sum(bandit.n_tentativas)
    acoes  = convergencia_stats(_emp)
    n_conv = sum(1 for a in acoes if a["convergido"])
    return {
        "empresa_id": _emp,
        "total_interacoes": total,
        "alpha":            bandit.alpha,
        "acoes_convergidas": n_conv,
        "acoes_total":       len(acoes),
        "acoes":             acoes,
    }


@app.patch("/admin/bandit/alpha")
def ajustar_alpha_bandit(
    body: dict,
    empresa_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Ajusta o parâmetro de exploração do bandit (0.1 – 5.0). Valor alto = mais exploração."""
    payload = _exigir_comando(credentials)
    novo_alpha = body.get("alpha")
    if novo_alpha is None:
        raise HTTPException(status_code=422, detail="Campo 'alpha' obrigatório.")
    _emp = _empresa_do_bandit(payload, empresa_id)
    from model.bandit import ajustar_alpha
    alpha_efetivo = ajustar_alpha(float(novo_alpha), _emp)
    return {"ok": True, "alpha": alpha_efetivo, "empresa_id": _emp}


class ZerarBanditIn(BaseModel):
    empresa_id: str = Field(..., min_length=1, max_length=100)
    confirmacao: str


@app.post("/admin/bandit/zerar")
def zerar_bandit(body: ZerarBanditIn, credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Apaga o aprendizado das ofertas de UMA empresa (sem volta). Exige digitar ZERAR."""
    payload = _exigir_comando(credentials)
    if body.confirmacao.strip().upper() != "ZERAR":
        raise HTTPException(status_code=422, detail="Digite ZERAR para confirmar.")
    empresa = body.empresa_id.strip().lower()
    from model.bandit import carregar_bandit, zerar
    antes = int(sum(carregar_bandit(empresa).n_tentativas))
    zerar(empresa)
    _registrar_auditoria(acao="bandit_zerado", entidade="bandit", entidade_id=empresa,
                         usuario_email=payload.get("email", ""), empresa_id=empresa,
                         usuario_id=payload.get("sub", ""), detalhes={"interacoes_descartadas": antes})
    return {"ok": True, "empresa_id": empresa, "interacoes_descartadas": antes}


@app.get("/predicoes/historico/{cpf}")
def historico_score_devedor(
    cpf: str,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Evolução do score de recuperabilidade de um devedor ao longo do tempo."""
    # Esta rota recebia a credencial e nunca a usava. O HTTPBearer só confere
    # que o cabeçalho EXISTE, não que o token valha: com "Authorization: Bearer
    # lixo" ela devolvia o histórico de score de qualquer CPF, de qualquer
    # empresa. Reproduzido antes de corrigir.
    payload = _usuario_autenticado(credentials)
    empresa_id = payload.get("empresa_id", "")
    if not empresa_id and payload.get("role") != "comando":
        raise HTTPException(status_code=403, detail="Acesso negado: usuário sem empresa definida.")

    db = get_db()
    colunas = ("id, score_recuperabilidade, perfil_cluster, cluster_id, "
               "valor_divida, dias_em_atraso, created_at")
    if empresa_id:
        # Só as carteiras da empresa de quem chamou. Em lotes de cem, porque
        # uma empresa com centenas estouraria a URL num único in_.
        historico = []
        carteiras = _ids_carteiras(db, empresa_id)
        for i in range(0, len(carteiras), ITENS_POR_IN):
            lote = carteiras[i:i + ITENS_POR_IN]
            historico += _todas_as_linhas(
                lambda lote=lote: db.table("predicoes").select(colunas)
                .eq("cpf", cpf).in_("carteira_id", lote).order("created_at"))
        historico.sort(key=lambda p: p.get("created_at") or "")
    else:
        historico = _todas_as_linhas(
            lambda: db.table("predicoes").select(colunas).eq("cpf", cpf).order("created_at"))
    if not historico:
        raise HTTPException(status_code=404, detail=f"Nenhuma predição encontrada para CPF: {cpf}")

    tendencia = None
    if len(historico) >= 2:
        primeiro = float(historico[0].get("score_recuperabilidade") or 0)
        ultimo   = float(historico[-1].get("score_recuperabilidade") or 0)
        delta    = ultimo - primeiro
        tendencia = "melhora" if delta > 5 else "piora" if delta < -5 else "estável"

    return {
        "cpf":      cpf,
        "n_analises": len(historico),
        "tendencia":  tendencia,
        "historico":  historico,
    }


@app.get("/admin/modelos")
def listar_modelos(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """
    Lista todas as versões do modelo com:
    - Métricas de treino (acurácia e AUC-ROC por cross-validation)
    - Performance real (acurácia calculada com feedbacks reais recebidos enquanto essa versão era ativa)
    """
    _exigir_comando(credentials)

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
    for i in range(0, len(pred_ids), ITENS_POR_IN):
        res = (
            db.table("predicoes")
            .select("id, carteira_id, score_recuperabilidade")
            .in_("id", pred_ids[i: i + ITENS_POR_IN])
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
    # Promover versão abaixo do mínimo de amostras exige confirmação explícita.
    forcar: bool = False


@app.post("/admin/retreinar")
def admin_retreinar(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Desativado: retreinava o modelo geral com os pagamentos de TODAS as empresas
    juntos e podia ativá-lo sozinho (achado D1). O treino com pagamentos agora é
    por empresa, em POST /comando/treino/feedbacks, e nasce inativo."""
    _exigir_comando(credentials)
    raise HTTPException(
        status_code=410,
        detail="O retreino geral foi desativado: ele misturava os pagamentos de todas as empresas. "
               "Treine o modelo de cada empresa com os pagamentos dela em COMANDO → Treinar modelo de uma empresa.")


@app.post("/admin/retreinar/promover")
def admin_promover(
    payload: PromoverIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Promove uma versão específica como modelo ativo."""
    _exigir_comando(credentials)

    try:
        from model.retrain import promover_versao, VersaoInsuficiente
        promover_versao(payload.versao, forcar=payload.forcar)
        _score_cache.clear()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except VersaoInsuficiente as e:
        # 409: o pedido é válido, mas conflita com o estado dos dados.
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao promover: {e}")

    _registrar_auditoria(
        acao="modelo_promovido",
        entidade="modelo",
        entidade_id=payload.versao,
        usuario_email=_usuario_autenticado(credentials).get("email", ""),
        detalhes={"versao": payload.versao, "forcado": payload.forcar},
    )
    return {"ok": True, "versao_promovida": payload.versao, "forcado": payload.forcar}


@app.get("/admin/retreinar/status")
def admin_status_retreinamento(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Lista versões de modelo disponíveis e a versão ativa."""
    _exigir_comando(credentials)

    from pathlib import Path
    versions_file = Path(__file__).parent / "model" / "versions.json"
    if not versions_file.exists():
        return {"versao_ativa": "v1_inicial", "versoes": [], "mensagem": "Nenhum retreinamento realizado ainda."}

    with open(versions_file, encoding="utf-8") as f:
        return json.load(f)


@app.get("/admin/scheduler/status")
def scheduler_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estado atual do scheduler: última verificação, próxima, quantos retreinamentos automáticos."""
    _exigir_comando(credentials)
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
    _exigir_comando(credentials)
    from scheduler import verificar_e_retreinar, MIN_NOVOS_PADRAO
    min_fb = int(os.getenv("SCHEDULER_MIN_FEEDBACKS", MIN_NOVOS_PADRAO))
    resultado = await asyncio.to_thread(verificar_e_retreinar, min_fb)
    return resultado


@app.get("/admin/auto-sync/status")
def auto_sync_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Estado do auto-sync de conexões: última execução, conexões sincronizadas, erros."""
    _exigir_comando(credentials)
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
    _exigir_comando(credentials)
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
def db_sync_get_config(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Retorna config atual da sincronização automática (senha omitida)."""
    _exigir_comando(credentials)
    from db_sync import carregar_config
    cfg = carregar_config()
    return {**cfg, "senha": "***" if cfg.get("senha") else ""}


@app.post("/admin/db-sync/config")
def db_sync_set_config(
    payload: DBSyncConfigIn,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Salva ou atualiza a configuração de sincronização automática."""
    _exigir_comando(credentials)
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
    _exigir_comando(credentials)
    from db_sync import sincronizar
    resultado = await asyncio.to_thread(sincronizar)
    return resultado


@app.get("/admin/db-sync/status")
def db_sync_status(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """Retorna status da última sincronização."""
    _exigir_comando(credentials)
    from db_sync import carregar_config
    cfg = carregar_config()
    return {
        "ativo": cfg["ativo"],
        "ultimo_sync": cfg["ultimo_sync"],
        "n_sincronizacoes": cfg["n_sincronizacoes"],
        "ultimo_resultado": cfg["ultimo_resultado"],
    }


@app.get("/auditoria")
def listar_auditoria(
    entidade: Optional[str] = None,
    entidade_id: Optional[str] = None,
    usuario_email: Optional[str] = None,
    acao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Security(bearer),
):
    """
    Histórico de ações auditadas — filtrado pela empresa do token (ou tudo para COMANDO).
    Suporta filtro por período/usuário/ação e paginação, para telas de auditoria/compliance.
    """
    # A tela de auditoria é de admin e comando; a rota aceitava qualquer usuário
    # autenticado, então um operador lia o histórico da empresa chamando a API.
    payload = _exigir_admin_ou_comando(credentials)
    empresa_id = payload.get("empresa_id", "")
    role       = payload.get("role", "operador")
    db = get_db()
    q  = db.table("auditoria").select("*")
    if role != "comando":
        q = q.eq("empresa_id", empresa_id)
    if entidade:
        q = q.eq("entidade", entidade)
    if entidade_id:
        q = q.eq("entidade_id", str(entidade_id))
    if usuario_email:
        q = q.eq("usuario_email", usuario_email.strip().lower())
    if acao:
        q = q.eq("acao", acao)
    if data_inicio:
        q = q.gte("created_at", data_inicio)
    if data_fim:
        q = q.lte("created_at", data_fim)
    limit = min(max(limit, 1), 1000)
    offset = max(offset, 0)
    res = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data or []



# ── Retenção de dados de devedores ───────────────────────────────────────
# O usuário do Mizan pode apagar a própria conta. O devedor não: ele está na
# base porque o banco cliente mandou a carteira, nunca consentiu nada e não
# tem onde clicar. Estas rotas são o caminho que faltava — um prazo por
# empresa, e um pedido de eliminação por titular (LGPD art. 18).
#
# O que elas fazem é anonimizar, não apagar: o modelo aprende de
# (variáveis → resultado) e nunca precisou do CPF, então tirar o
# identificador encerra a identificação sem destruir o treino. Ver
# model/retencao.py para o porquê e para os limites do termo "anonimizado".

_TABELAS_RETENCAO = ("predicoes", "feedbacks", "contatos", "recomendacoes")





def _linhas_da_empresa(db, tabela: str, empresa_id: str, carteiras: list, refinar) -> list:
    """TODAS as linhas da empresa numa tabela, já refinadas por `refinar`.

    Cada tabela guarda o dono de um jeito diferente, e errar aqui significaria
    anonimizar a base de outro cliente — daí o escopo ser explícito por tabela
    em vez de um filtro genérico.

    Lê página por página, e as carteiras em lotes. Antes isto devolvia UMA
    consulta lida com `.limit(50000)`, que parece pedir cinquenta mil e entrega
    mil: a prévia dizia "1.000 registros" para uma base de 41.000, e "Executar
    agora" anonimizava no máximo mil por clique enquanto a tela dizia
    "concluído". Predições, além disso, iam todas as carteiras num único in_.

    Empresa sem carteira não tem predição, e devolve vazio — não "sem filtro".
    """
    colunas = "id, created_at, anonimizado_em"

    def base():
        return db.table(tabela).select(colunas)

    if tabela == "predicoes":
        linhas: list = []
        for i in range(0, len(carteiras), ITENS_POR_IN):
            lote = carteiras[i:i + ITENS_POR_IN]
            linhas += _todas_as_linhas(
                lambda lote=lote: refinar(base().in_("carteira_id", lote)))
        return linhas
    if tabela == "feedbacks":
        # O campo `empresa` do feedback guarda, em registros antigos, o NOME de
        # exibição em vez do id. Filtrar só por ele deixava esses pagamentos
        # fora da retenção e do pedido do titular, com o CPF lá dentro. Entram
        # também os ligados a uma predição das carteiras da empresa.
        linhas = {l["id"]: l for l in _todas_as_linhas(lambda: refinar(base().eq("empresa", empresa_id)))}
        pred_ids = []
        for i in range(0, len(carteiras), ITENS_POR_IN):
            lote = carteiras[i:i + ITENS_POR_IN]
            pred_ids += [p["id"] for p in _todas_as_linhas(
                lambda lote=lote: db.table("predicoes").select("id").in_("carteira_id", lote))]
        for i in range(0, len(pred_ids), ITENS_POR_IN):
            lote = pred_ids[i:i + ITENS_POR_IN]
            for l in _todas_as_linhas(lambda lote=lote: refinar(base().in_("predicao_id", lote))):
                linhas[l["id"]] = l
        return list(linhas.values())
    return _todas_as_linhas(lambda: refinar(base().eq("empresa_id", empresa_id)))


def _anonimizar_ids(db, tabela: str, ids: list, patch: dict) -> None:
    """Aplica o patch em lotes: o filtro vai na URL e não cabe com dezenas de milhares de ids."""
    for i in range(0, len(ids), ITENS_POR_IN):
        db.table(tabela).update(patch).in_("id", ids[i:i + ITENS_POR_IN]).execute()


def _empresa_retencao(payload: dict, empresa_id_alvo: "str | None") -> str:
    """Empresa sobre a qual agir: a escolhida pelo COMANDO (a tela é só dele)."""
    if payload.get("role") == "comando":
        if not (empresa_id_alvo or "").strip():
            raise HTTPException(status_code=400, detail="Informe a empresa.")
        return empresa_id_alvo.strip().lower()
    empresa_id = payload.get("empresa_id", "")
    if not empresa_id:
        raise HTTPException(status_code=400, detail="Usuário sem empresa definida.")
    return empresa_id


@app.get("/retencao")
def ver_retencao(empresa_id_alvo: Optional[str] = None,
                 credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Política atual e quantas linhas ela alcançaria — sem tocar em nada.

    A prévia funciona mesmo com a política desligada: para escolher um prazo
    é preciso ver antes o que ele levaria.
    """
    from model import retencao as R
    payload = _exigir_comando(credentials)       # retenção é do COMANDO
    empresa_id = _empresa_retencao(payload, empresa_id_alvo)

    politica = R.de_config(_extra_empresa(empresa_id))
    db = get_db()
    carteiras = _ids_carteiras(db, empresa_id)

    # Prévia com o prazo configurado ou, se não houver, com o que o sistema
    # sugere — senão a tela mostraria zero e não diria nada.
    simulada = politica if politica.ativa else R.PoliticaRetencao(ativa=True, dias=365)

    previa, total_identificado = {}, 0
    for tabela in _TABELAS_RETENCAO:
        # Sem try/except de propósito. Engolir a falha de leitura e seguir com
        # lista vazia mostrava "0 registros com CPF" quando a consulta tinha
        # quebrado, e o admin leria "nada a anonimizar". Erro aqui tem de ser
        # erro (500 com código), não um zero que parece resposta.
        linhas = _linhas_da_empresa(db, tabela, empresa_id, carteiras,
                                    lambda q: q.is_("anonimizado_em", "null"))
        vencidas = R.selecionar(linhas, simulada)
        previa[tabela] = {"com_identificacao": len(linhas), "vencidas": len(vencidas)}
        total_identificado += len(linhas)

    return {
        "empresa_id": empresa_id,
        "politica": {"ativa": politica.ativa, "dias": politica.dias},
        "prazo_simulado": simulada.dias,
        "minimo_dias": R.MINIMO_DIAS,
        "maximo_dias": R.MAXIMO_DIAS,
        "total_com_identificacao": total_identificado,
        "previa": previa,
        "leitura": (
            f"Sem prazo configurado. Com {simulada.dias} dias, "
            f"{sum(p['vencidas'] for p in previa.values())} linhas perderiam o CPF hoje."
            if not politica.ativa else
            f"Prazo de {politica.dias} dias. "
            f"{sum(p['vencidas'] for p in previa.values())} linhas vencidas aguardando execução."
        ),
    }


@app.post("/retencao/executar")
def executar_retencao(empresa_id_alvo: Optional[str] = None,
                      credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Anonimiza o que passou do prazo. Exige política configurada."""
    from model import retencao as R
    payload = _exigir_comando(credentials)       # retenção é do COMANDO
    empresa_id = _empresa_retencao(payload, empresa_id_alvo)

    politica = R.de_config(_extra_empresa(empresa_id))
    if not politica.ativa:
        raise HTTPException(status_code=400,
                            detail="Nenhum prazo de retenção configurado para esta empresa.")
    erro = politica.valida()
    if erro:
        raise HTTPException(status_code=400, detail=erro)

    db = get_db()
    carteiras = _ids_carteiras(db, empresa_id)
    resultado = {}
    for tabela in _TABELAS_RETENCAO:
        linhas = _linhas_da_empresa(db, tabela, empresa_id, carteiras,
                                    lambda q: q.is_("anonimizado_em", "null"))
        alvos = R.selecionar(linhas, politica)
        _anonimizar_ids(db, tabela, alvos, R.patch_anonimo(tabela))
        resultado[tabela] = len(alvos)

    _registrar_auditoria("retencao_executada", "empresa", empresa_id,
                         payload.get("email"), empresa_id,
                         {"dias": politica.dias, "anonimizadas": resultado},
                         payload.get("sub"))
    return {"ok": True, "dias": politica.dias, "anonimizadas": resultado,
            "total": sum(resultado.values())}


class TitularIn(BaseModel):
    cpf: str


@app.post("/retencao/titular")
def eliminar_titular(body: TitularIn, empresa_id_alvo: Optional[str] = None,
                     credentials: HTTPAuthorizationCredentials = Security(bearer)):
    """Pedido de eliminação de um titular (LGPD art. 18, V).

    Independe de prazo: o titular pediu, o identificador sai hoje. O que fica
    é a linha sem nome — o histórico de recuperação da empresa não é apagado
    junto, e o modelo segue aprendendo com um registro que não aponta para
    ninguém.
    """
    from model import retencao as R
    payload = _exigir_comando(credentials)       # retenção é do COMANDO
    empresa_id = _empresa_retencao(payload, empresa_id_alvo)

    bruto = (body.cpf or "").strip()
    digitos = "".join(c for c in bruto if c.isdigit())
    if not digitos:
        raise HTTPException(status_code=400, detail="Informe o CPF do titular.")
    # O CPF é gravado como veio do arquivo do cliente: uns mandam
    # "123.456.789-00", outros só os dígitos, e o Excel come o zero à
    # esquerda no caminho. Procurar só uma das formas deixaria o titular
    # sem resposta enquanto o dado dele continua lá.
    formas = {bruto, digitos, digitos.zfill(11), digitos.lstrip("0")}
    formas = [f for f in formas if f]

    db = get_db()
    carteiras = _ids_carteiras(db, empresa_id)
    resultado = {}
    for tabela in _TABELAS_RETENCAO:
        linhas = _linhas_da_empresa(db, tabela, empresa_id, carteiras,
                                    lambda q: q.in_("cpf", formas))
        ids = [l["id"] for l in linhas if not l.get("anonimizado_em")]
        _anonimizar_ids(db, tabela, ids, R.patch_anonimo(tabela))
        resultado[tabela] = len(ids)

    # A auditoria registra o pedido sem repetir o CPF: guardar o identificador
    # na trilha desfaria o que a rota acabou de fazer.
    _registrar_auditoria("titular_eliminado", "empresa", empresa_id,
                         payload.get("email"), empresa_id,
                         {"cpf_final": digitos[-4:], "anonimizadas": resultado},
                         payload.get("sub"))
    return {"ok": True, "anonimizadas": resultado, "total": sum(resultado.values())}



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
