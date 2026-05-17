import io
import os
from datetime import date
from typing import Optional

import pandas as pd
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from db import get_db
from model.score import score_carteira

load_dotenv()

COLUNAS_OBRIGATORIAS = [
    "cpf", "nome", "produto", "status", "uf",
    "valor_divida", "renda_estimada", "dias_em_atraso",
]

app = FastAPI(
    title="Mizan API",
    description="Plataforma de análise de carteira de crédito com IA",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer()


class FeedbackIn(BaseModel):
    cpf: str
    pagou: bool
    valor_recuperado: Optional[float] = 0.0
    data_pagamento: Optional[date] = None
    empresa: Optional[str] = None


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
    db = get_db()
    res = (
        db.table("api_keys")
        .select("*")
        .eq("api_key", credentials.credentials)
        .eq("ativa", True)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=401, detail="API key inválida ou inativa.")
    return res.data[0]


@app.get("/health")
def health():
    return {"status": "ok"}


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
async def analisar(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um CSV.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Erro ao ler CSV: {e}")

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltantes:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSV inválido. Colunas obrigatórias ausentes: {faltantes}. "
                f"Colunas encontradas: {df.columns.tolist()}"
            ),
        )

    try:
        resultado = score_carteira(df)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Modelos não encontrados ({e.filename}). Execute model/train.py primeiro.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na análise: {e}")

    resultado["valor_esperado_recuperacao"] = (
        resultado["score_recuperabilidade"] / 100 * resultado["valor_divida"]
    ).round(2)

    resultado_sorted = resultado.sort_values("score_recuperabilidade", ascending=False)

    devedores = []
    for rank, (_, row) in enumerate(resultado_sorted.iterrows(), start=1):
        devedor = {
            "rank": rank,
            "score_recuperabilidade": float(row["score_recuperabilidade"]),
            "perfil_cluster": row["perfil_cluster"],
            "valor_esperado_recuperacao": float(row["valor_esperado_recuperacao"]),
        }
        for col in df.columns:
            val = row[col]
            devedor[col] = None if pd.isna(val) else val
        devedores.append(devedor)

    total_em_risco = float(resultado["valor_divida"].sum())
    ver_total = float(resultado["valor_esperado_recuperacao"].sum())
    media_score = float(resultado["score_recuperabilidade"].mean().round(1))

    resultado["aging"] = resultado["dias_em_atraso"].apply(_aging_label)
    aging_dist = (
        resultado.groupby("aging")
        .agg(
            total_devedores=("valor_divida", "count"),
            valor_total=("valor_divida", "sum"),
            score_medio=("score_recuperabilidade", "mean"),
        )
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )

    cluster_dist = (
        resultado.groupby("perfil_cluster")
        .agg(
            total_devedores=("valor_divida", "count"),
            valor_total=("valor_divida", "sum"),
            score_medio=("score_recuperabilidade", "mean"),
        )
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )

    top10 = devedores[:10]

    resumo = {
        "total_devedores": len(resultado),
        "total_em_risco": round(total_em_risco, 2),
        "score_medio": media_score,
        "valor_esperado_recuperacao_total": round(ver_total, 2),
        "taxa_recuperacao_esperada": round(ver_total / total_em_risco * 100, 1) if total_em_risco else 0,
    }

    # Persistir no Supabase — falha silenciosa para não bloquear a análise
    try:
        db = get_db()
        cart_res = db.table("carteiras").insert({
            "nome_arquivo": file.filename,
            "total_devedores": resumo["total_devedores"],
            "valor_face": resumo["total_em_risco"],
            "valor_esperado": resumo["valor_esperado_recuperacao_total"],
            "score_medio": resumo["score_medio"],
            "modelo_versao": "v1",
        }).execute()

        carteira_id = cart_res.data[0]["id"]

        predicoes_rows = [
            {
                "carteira_id": carteira_id,
                "cpf": str(d.get("cpf", "")),
                "nome": d.get("nome"),
                "produto": d.get("produto"),
                "uf": d.get("uf"),
                "valor_divida": d.get("valor_divida"),
                "dias_em_atraso": d.get("dias_em_atraso"),
                "score_recuperabilidade": d.get("score_recuperabilidade"),
                "valor_esperado_recuperacao": d.get("valor_esperado_recuperacao"),
                "perfil_cluster": d.get("perfil_cluster"),
                "cluster_id": d.get("cluster_id"),
            }
            for d in devedores
        ]

        # Batch em lotes de 500 para respeitar limites do Supabase
        for i in range(0, len(predicoes_rows), 500):
            db.table("predicoes").insert(predicoes_rows[i : i + 500]).execute()

    except Exception:
        pass

    return {
        "resumo": resumo,
        "distribuicao_aging": aging_dist,
        "distribuicao_cluster": cluster_dist,
        "top10_prioritarios": top10,
        "ranking_completo": devedores,
    }


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

    return {"ok": True, "feedback_id": res.data[0]["id"], "predicao_id": predicao_id}


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
