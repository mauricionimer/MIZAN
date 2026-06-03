"""
Sincronização dos arquivos de modelo ML com o Supabase Storage.

Por que existe:
  O Render free tier usa filesystem efêmero — qualquer deploy apaga os .pkl.
  Este módulo sobe os arquivos ativos após cada promoção e os baixa no startup,
  garantindo que o modelo retreinado sobreviva indefinidamente a deploys.

Arquivos gerenciados:
  mizan_model.pkl, kmeans.pkl, scaler.pkl, versions.json
"""

import os
from pathlib import Path

_BUCKET = "mizan-models"
_MODEL_FILES = ["mizan_model.pkl", "kmeans.pkl", "scaler.pkl", "versions.json", "price_model.pkl"]

_DATA_DIR_STR = os.getenv("MIZAN_DATA_DIR", "")
_MODEL_DIR = (
    Path(_DATA_DIR_STR) / "model" if _DATA_DIR_STR else Path(__file__).parent / "model"
)


def _bucket():
    from db import get_db
    return get_db().storage.from_(_BUCKET)


def _garantir_bucket() -> None:
    try:
        from db import get_db
        get_db().storage.create_bucket(_BUCKET, options={"public": False})
        print(f"[Storage] Bucket '{_BUCKET}' criado.")
    except Exception:
        pass  # já existe — ignorar


def upload_modelos() -> bool:
    """Sobe os arquivos de modelo ativos para o Supabase Storage após cada promoção."""
    try:
        _garantir_bucket()
        b = _bucket()
        enviados = []
        for nome in _MODEL_FILES:
            caminho = _MODEL_DIR / nome
            if not caminho.exists():
                continue
            dados = caminho.read_bytes()
            try:
                b.upload(
                    path=nome,
                    file=dados,
                    file_options={"content-type": "application/octet-stream"},
                )
            except Exception:
                # Arquivo já existe no bucket — remove e reenvia
                try:
                    b.remove([nome])
                except Exception:
                    pass
                b.upload(
                    path=nome,
                    file=dados,
                    file_options={"content-type": "application/octet-stream"},
                )
            enviados.append(nome)
        print(f"[Storage] Upload concluído: {enviados}")
        return True
    except Exception as e:
        print(f"[Storage] Erro no upload dos modelos: {e}")
        return False


def download_modelos() -> bool:
    """
    Baixa os arquivos de modelo do Supabase Storage para MODEL_DIR no startup.
    Retorna True se pelo menos o modelo principal foi restaurado.
    """
    try:
        _garantir_bucket()
        b = _bucket()
        baixados = []
        for nome in _MODEL_FILES:
            try:
                dados: bytes = b.download(nome)
                if dados:
                    (_MODEL_DIR / nome).write_bytes(dados)
                    baixados.append(nome)
            except Exception:
                pass  # arquivo ainda não existe no bucket — usa o local do git
        if baixados:
            print(f"[Storage] Modelos restaurados do Supabase: {baixados}")
            return "mizan_model.pkl" in baixados
        print("[Storage] Bucket vazio — usando modelo local do repositório.")
        return False
    except Exception as e:
        print(f"[Storage] Erro no download dos modelos: {e}")
        return False
