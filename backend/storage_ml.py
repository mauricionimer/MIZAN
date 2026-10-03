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


# ── modelos por empresa ──────────────────────────────────────────────────────
# Mesmo bucket, prefixo `empresas/<slug>/`. Só vão os artefatos do modelo e o
# versions.json (métricas e impressão digital do arquivo de treino) — nunca os
# dados com que o modelo foi treinado, que não existem em disco.

def _enviar(b, caminho_remoto: str, dados: bytes) -> None:
    opts = {"content-type": "application/octet-stream"}
    try:
        b.upload(path=caminho_remoto, file=dados, file_options=opts)
    except Exception:
        try:
            b.remove([caminho_remoto])
        except Exception:
            pass
        b.upload(path=caminho_remoto, file=dados, file_options=opts)


def upload_empresa(slug: str, pasta: Path) -> bool:
    """Sobe a pasta de modelos da empresa para o Storage."""
    try:
        _garantir_bucket()
        b = _bucket()
        enviados = []
        for arq in sorted(pasta.iterdir()):
            if arq.is_file() and arq.suffix in (".pkl", ".json"):
                _enviar(b, f"empresas/{slug}/{arq.name}", arq.read_bytes())
                enviados.append(arq.name)
        print(f"[Storage] Empresa {slug}: enviados {len(enviados)} arquivos.")
        return True
    except Exception as e:
        print(f"[Storage] Erro no upload da empresa {slug}: {e}")
        return False


def sincronizar_empresa(slug: str, pasta: Path) -> None:
    """Traz do Storage a versão ativa da empresa se ela mudou desde a última vez.

    É assim que uma ativação (ou desativação) feita em outra instância chega
    aqui. Sem Storage ou sem nada publicado, não faz nada.
    """
    import json
    b = _bucket()
    try:
        remoto = json.loads(b.download(f"empresas/{slug}/versions.json"))
    except Exception:
        return                                   # nada publicado para esta empresa
    arq = pasta / "versions.json"
    try:
        local = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    except (OSError, ValueError):
        local = {}
    ativa = remoto.get("versao_ativa")
    if ativa == local.get("versao_ativa") and (arq.exists() or not ativa):
        return
    pasta.mkdir(parents=True, exist_ok=True)
    if ativa is None:                            # desativada lá: volta ao global aqui também
        for nome in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl", "price_model.pkl"):
            (pasta / nome).unlink(missing_ok=True)
    else:
        for nome in ("mizan_model.pkl", "kmeans.pkl", "scaler.pkl"):
            (pasta / nome).write_bytes(b.download(f"empresas/{slug}/{nome}"))
        # o modelo de preço só existe nas versões treinadas com os pagamentos
        try:
            (pasta / "price_model.pkl").write_bytes(b.download(f"empresas/{slug}/price_model_{ativa}.pkl"))
        except Exception:
            (pasta / "price_model.pkl").unlink(missing_ok=True)
    arq.write_text(json.dumps(remoto, indent=2, ensure_ascii=False), encoding="utf-8")
