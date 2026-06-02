"""
Sincronização automática de pagamentos com banco de dados externo.
Config salva em backend/db_sync_config.json (não versionado).

Fluxo:
  1. Usuário configura via POST /admin/db-sync/config
  2. Scheduler chama sincronizar() a cada SCHEDULER_INTERVALO_HORAS
  3. Sincronizar lê pagamentos novos desde ultimo_sync e registra feedbacks
"""
import json
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR_STR = __import__("os").getenv("MIZAN_DATA_DIR", "")
_CONFIG_FILE  = Path(_DATA_DIR_STR) / "db_sync_config.json" if _DATA_DIR_STR else Path(__file__).parent / "db_sync_config.json"

_PADRAO = {
    "ativo": False,
    "tipo": "postgres",
    "host": "localhost",
    "porta": None,
    "banco": "",
    "usuario": "",
    "senha": "",
    "query": "SELECT cpf, pagou, valor_recuperado FROM pagamentos WHERE updated_at > :ultimo_sync",
    "coluna_cpf": "cpf",
    "coluna_pagou": "pagou",
    "coluna_valor": "valor_recuperado",
    "ultimo_sync": None,
    "ultimo_resultado": None,
    "n_sincronizacoes": 0,
}


def carregar_config() -> dict:
    if not _CONFIG_FILE.exists():
        return dict(_PADRAO)
    with open(_CONFIG_FILE, encoding="utf-8") as f:
        return {**_PADRAO, **json.load(f)}


def salvar_config(cfg: dict):
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False, default=str)


def _build_url(cfg: dict) -> str:
    from urllib.parse import quote_plus
    tipo  = cfg.get("tipo", "postgres")
    host  = cfg.get("host") or ""
    banco = cfg.get("banco") or ""
    user  = quote_plus(cfg.get("usuario") or "")
    senha = quote_plus(cfg.get("senha") or "")

    if tipo == "sqlite":
        if not banco:
            raise ValueError("Caminho do arquivo SQLite não configurado.")
        return f"sqlite:///{banco}"

    if not host:
        raise ValueError("Host não configurado.")
    if not banco:
        raise ValueError("Nome do banco de dados não configurado.")

    if tipo == "postgres":
        porta = cfg.get("porta") or 5432
        return f"postgresql+psycopg://{user}:{senha}@{host}:{porta}/{banco}"
    if tipo == "mysql":
        porta = cfg.get("porta") or 3306
        return f"mysql+pymysql://{user}:{senha}@{host}:{porta}/{banco}"
    raise ValueError(f"Tipo não suportado: {tipo}")


def _parsear_pagou(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "sim", "s", "yes", "verdadeiro")
    return bool(val)


def sincronizar() -> dict:
    """Busca pagamentos novos no banco externo e registra como feedbacks. Chamado pelo scheduler."""
    cfg = carregar_config()
    agora = datetime.now(timezone.utc)

    if not cfg["ativo"]:
        return {"acao": "inativo", "sincronizou": False}

    # Conecta e executa query com parâmetro :ultimo_sync
    try:
        from sqlalchemy import create_engine, text
        url = _build_url(cfg)
        params = {"ultimo_sync": cfg["ultimo_sync"] or "1970-01-01T00:00:00+00:00"}
        engine = create_engine(url)
        with engine.connect() as conn:
            df = pd.read_sql(text(cfg["query"]), conn, params=params)
        engine.dispose()
    except Exception as e:
        resultado = {"acao": "erro", "sincronizou": False, "erro": str(e),
                     "sincronizado_em": agora.isoformat()}
        cfg["ultimo_resultado"] = resultado
        salvar_config(cfg)
        print(f"[DB Sync] Erro ao conectar: {e}")
        return resultado

    if df.empty:
        resultado = {"acao": "sem_novos", "sincronizou": False, "n_registros": 0,
                     "sincronizado_em": agora.isoformat()}
        cfg["ultimo_sync"] = agora.isoformat()
        cfg["ultimo_resultado"] = resultado
        salvar_config(cfg)
        return resultado

    # Mapeia colunas configuradas
    col_cpf   = cfg.get("coluna_cpf", "cpf")
    col_pagou = cfg.get("coluna_pagou", "pagou")
    col_valor = cfg.get("coluna_valor", "valor_recuperado")

    empresa_id = cfg.get("empresa_id") or cfg.get("empresa_nome") or ""

    from db import get_db
    db = get_db()

    # Pré-busca predicao_ids para linkar feedbacks ao devedor correto
    cpfs = [str(row[col_cpf]) for _, row in df.iterrows() if row.get(col_cpf)]
    pred_map: dict[str, str] = {}
    for i in range(0, len(cpfs), 100):
        res = (
            db.table("predicoes")
            .select("cpf, id")
            .in_("cpf", cpfs[i:i+100])
            .order("created_at", desc=True)
            .execute()
        )
        for p in (res.data or []):
            if p["cpf"] not in pred_map:
                pred_map[p["cpf"]] = p["id"]

    fb_rows = []
    for _, row in df.iterrows():
        p = row.get(col_pagou)
        if p is None or (isinstance(p, float) and pd.isna(p)):
            continue
        cpf = str(row[col_cpf])
        vr = row.get(col_valor)
        fb_row = {
            "cpf": cpf,
            "pagou": _parsear_pagou(p),
            "valor_recuperado": float(vr) if vr is not None and not pd.isna(vr) else 0.0,
        }
        if empresa_id:
            fb_row["empresa"] = empresa_id
        if cpf in pred_map:
            fb_row["predicao_id"] = pred_map[cpf]
        fb_rows.append(fb_row)

    if fb_rows:
        for i in range(0, len(fb_rows), 100):
            db.table("feedbacks").insert(fb_rows[i:i+100]).execute()

    cfg["ultimo_sync"] = agora.isoformat()
    cfg["n_sincronizacoes"] = cfg.get("n_sincronizacoes", 0) + 1
    resultado = {"acao": "sincronizou", "sincronizou": True, "n_registros": len(fb_rows),
                 "sincronizado_em": agora.isoformat()}
    cfg["ultimo_resultado"] = resultado
    salvar_config(cfg)
    print(f"[DB Sync] {len(fb_rows)} pagamentos sincronizados")
    return resultado
