"""Atividade dos agentes por hora (últimas 24 h), para o painel de cada agente."""
import os
import sys
from datetime import datetime, timedelta, timezone

os.environ.setdefault("AGENTE_REPO", "memoria")
from agente import api  # noqa: E402

AGORA = datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)


def em(h):
    return (AGORA - timedelta(hours=h)).isoformat()


def test_baldes_de_uma_hora_e_ultima_e_a_corrente():
    passos = [{"criado_em": em(0.1), "resultado": "ok"}, {"criado_em": em(0.9), "resultado": "erro"},
              {"criado_em": em(5.5), "resultado": "bloqueado"}, {"criado_em": em(23.9), "resultado": "ok"},
              {"criado_em": em(30), "resultado": "ok"}, {"criado_em": None}, {"criado_em": "x"}]
    r = api.por_hora(passos, AGORA)
    assert len(r["acoes"]) == 24 and sum(r["acoes"]) == 4
    assert r["acoes"][23] == 2 and r["atencao"][23] == 1
    assert r["acoes"][18] == 1 and r["atencao"][18] == 1
    assert r["acoes"][0] == 1


def test_resumo_traz_por_hora_so_com_agora():
    passos = [{"no": "triagem", "criado_em": em(1), "resultado": "ok"}]
    assert "por_hora" not in api._resumo_agente("Triagem", passos)
    assert sum(api._resumo_agente("Triagem", passos, AGORA)["por_hora"]["acoes"]) == 1


if __name__ == "__main__":
    falhas = 0
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            try:
                f(); print("ok", nome)
            except Exception as e:  # noqa: BLE001
                falhas += 1; print("FALHOU", nome, repr(e))
    sys.exit(1 if falhas else 0)
