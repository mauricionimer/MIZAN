"""Agentes — a bateria de cenários inteira com a IA simulada precisa passar.

    python test_agente_bateria.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
from agente.bateria.__main__ import main     # noqa: E402

sys.exit(main(["--sem-gravar"]))
