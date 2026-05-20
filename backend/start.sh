#!/bin/bash
set -e

DATA_DIR="${MIZAN_DATA_DIR:-}"

if [ -n "$DATA_DIR" ]; then
    mkdir -p "$DATA_DIR/model"

    # Copiar modelos iniciais para o volume se ainda não existirem
    for f in mizan_model.pkl kmeans.pkl scaler.pkl versions.json; do
        if [ ! -f "$DATA_DIR/model/$f" ] && [ -f "/app/model/$f" ]; then
            cp "/app/model/$f" "$DATA_DIR/model/$f"
            echo "[Init] $f copiado para $DATA_DIR/model/"
        fi
    done

    echo "[Init] Volume de dados pronto em $DATA_DIR"
fi

exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
