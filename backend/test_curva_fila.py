"""Curva "até onde vale cobrar": soma acumulada da fila, em poucos pontos."""
import os
import sys

os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste")
import main  # noqa: E402


def test_curva_soma_e_proximo():
    r = main.pontos_da_curva([50, 30, 10, 5, 5], pontos=5)
    assert r["total_devedores"] == 5 and r["total_valor"] == 100
    assert [p["n"] for p in r["pontos"]] == [1, 2, 3, 4, 5]
    assert [p["pct"] for p in r["pontos"]] == [50, 80, 90, 95, 100]
    assert r["pontos"][0]["proximo"] == 30          # o próximo da fila depois do 1º
    assert r["pontos"][-1]["proximo"] == 0.0        # depois do último não há ninguém


def test_curva_amostra_poucos_pontos_e_termina_na_fila_toda():
    r = main.pontos_da_curva([1.0] * 1000, pontos=40)
    assert len(r["pontos"]) == 40
    assert r["pontos"][-1]["n"] == 1000 and r["pontos"][-1]["pct"] == 100


def test_curva_vazia_e_sem_valor():
    assert main.pontos_da_curva([], 40)["pontos"] == []
    r = main.pontos_da_curva([0, 0, 0], 5)
    assert all(p["pct"] == 0.0 for p in r["pontos"])  # sem divisão por zero


if __name__ == "__main__":
    falhas = 0
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            try:
                f(); print("ok", nome)
            except Exception as e:  # noqa: BLE001
                falhas += 1; print("FALHOU", nome, repr(e))
    sys.exit(1 if falhas else 0)
