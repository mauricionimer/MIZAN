import io
import os

import pandas as pd
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from model.score import score_carteira

load_dotenv()

COLUNAS_OBRIGATORIAS = [
    "cpf", "nome", "produto", "status", "uf",
    "valor_divida", "renda_estimada", "dias_em_atraso",
]

app = FastAPI(
    title="Mizan API",
    description="Plataforma de análise de carteira de crédito com IA",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    resultado_sorted = resultado.sort_values("score_recuperabilidade", ascending=False)

    # Lista de devedores ranqueados
    devedores = []
    for rank, (_, row) in enumerate(resultado_sorted.iterrows(), start=1):
        devedor = {
            "rank": rank,
            "score_recuperabilidade": float(row["score_recuperabilidade"]),
            "perfil_cluster": row["perfil_cluster"],
        }
        for col in df.columns:
            val = row[col]
            devedor[col] = None if pd.isna(val) else val
        devedores.append(devedor)

    # Resumo geral
    total_em_risco = float(resultado["valor_divida"].sum())
    media_score = float(resultado["score_recuperabilidade"].mean().round(1))

    # Distribuição por aging
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

    # Distribuição por perfil de cluster
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

    # Top 10 prioritários
    top10 = devedores[:10]

    return {
        "resumo": {
            "total_devedores": len(resultado),
            "total_em_risco": round(total_em_risco, 2),
            "score_medio": media_score,
        },
        "distribuicao_aging": aging_dist,
        "distribuicao_cluster": cluster_dist,
        "top10_prioritarios": top10,
        "ranking_completo": devedores,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
