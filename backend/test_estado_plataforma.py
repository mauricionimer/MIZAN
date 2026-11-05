"""Estado da plataforma: só afirma o que mediu."""
import sys
from datetime import datetime, timedelta, timezone

import plataforma as pl

AGORA = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def test_sem_dado_vira_sem_medicao_e_nao_ok():
    for s in (pl.agentes([]), pl.email([], AGORA), pl.pagamentos([])):
        assert s["estado"] == "sem_medicao" and s["nivel"] is None
    r = pl.resumo([pl.servidor(), pl.agentes([])])
    assert r["estado"] == "ok" and r["sem_medicao"] == 1


def test_agentes_conta_erros_e_lentos():
    passos = ([{"no": "negociar", "resultado": "ok", "duracao_ms": 1200}] * 8
              + [{"no": "triagem", "resultado": "erro", "duracao_ms": 900},
                 {"no": "negociar", "resultado": "ok", "duracao_ms": 20000},
                 {"no": "enviar", "resultado": "erro", "duracao_ms": 5}])   # não é resposta: fora
    s = pl.agentes(passos)
    assert s["amostra"] == 10 and s["erros"] == 1
    assert s["nivel"] == 80.0 and s["estado"] == "atencao"
    assert "9 de 10" in s["frase"]


def test_email_so_ultimas_24h():
    envios = [{"em": AGORA - timedelta(hours=1), "ok": True},
              {"em": AGORA - timedelta(hours=2), "ok": False},
              {"em": AGORA - timedelta(days=3), "ok": False}]
    s = pl.email(envios, AGORA)
    assert s["amostra"] == 2 and s["nivel"] == 50.0 and s["estado"] == "problema"


def test_pagamentos_atraso_de_registro():
    fb = [{"data_pagamento": "2026-11-01", "created_at": "2026-11-01T10:00:00Z"},
          {"data_pagamento": "2026-11-01", "created_at": "2026-11-02T10:00:00Z"},
          {"data_pagamento": "2026-10-20", "created_at": "2026-11-02T10:00:00Z"},
          {"data_pagamento": None, "created_at": "2026-11-02T10:00:00Z"}]
    s = pl.pagamentos(fb)
    assert s["amostra"] == 3 and round(s["nivel"]) == 67 and "2 de 3" in s["frase"]


def test_email_utils_anota_resultado_sem_dados_pessoais():
    import email_utils
    email_utils.ENVIOS.clear()
    email_utils._anotar(True)
    assert set(email_utils.ENVIOS[0]) == {"em", "ok"}


if __name__ == "__main__":
    falhas = 0
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            try:
                f(); print("ok", nome)
            except Exception as e:  # noqa: BLE001
                falhas += 1; print("FALHOU", nome, repr(e))
    sys.exit(1 if falhas else 0)
