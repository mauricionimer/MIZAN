"""Roda a bateria de cenários.

    cd backend
    python -m agente.bateria                 # IA simulada, custo zero
    python -m agente.bateria --real          # IA de verdade (gasta; ver docs/PLANO_AGENTE.md, 7)
    python -m agente.bateria --grupo Ataques # só um grupo

Grava o resultado em agente/bateria/resultados/<versão>-<modo>.json.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agente import llm, negociador, triagem
from agente.bateria.cenarios import todos
from agente.bateria.motor import NOME_CRITERIO, avaliar, executar, nota


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bateria de cenários do agente")
    ap.add_argument("--real", action="store_true", help="usa a IA configurada (MIZAN_AGENTE_CLIENTE etc.)")
    ap.add_argument("--grupo")
    ap.add_argument("--sem-gravar", action="store_true")
    ap.add_argument("--limite-usd", type=float, default=2.0, help="para a rodada real ao passar deste gasto")
    a = ap.parse_args(argv)

    cenarios = [c for c in todos() if not a.grupo or c.grupo == a.grupo]
    resultados = []
    for c in cenarios:
        cliente = llm.cliente() if a.real else None
        res = avaliar(c, executar(c, cliente))
        resultados.append(res)
        print(f"{'ok  ' if res['ok'] else 'FALHA'}  [{c.grupo}] {c.id}: {c.descricao}")
        for i in res["itens"]:
            if not i["ok"]:
                print(f"         ✗ {i['conferencia']}")
        if res["erro"]:
            print(f"         ! {res['erro']}")
        gasto = sum(r["custo_usd"] for r in resultados)
        if a.real and gasto >= a.limite_usd:
            print(f"\nParou: gasto de US$ {gasto:.4f} chegou ao limite de US$ {a.limite_usd} desta rodada.")
            break
    n = nota(resultados)
    versao = f"{negociador.VERSAO_PROMPT}+{triagem.VERSAO_PROMPT}"
    modo = "real" if a.real else "falso"
    print()
    print(f"Versão {versao} · modo {modo}")
    print(f"Nota {n['nota']} / 100 · {n['aprovados']}/{n['cenarios']} cenários · {n['conferencias']} conferências · US$ {n['custo_usd']}")
    for k, v in n["criterios"].items():
        if v is not None:
            print(f"  {NOME_CRITERIO[k]:<32} {v:.0%}")
    if not a.sem_gravar and not a.grupo:
        pasta = Path(__file__).parent / "resultados"
        pasta.mkdir(exist_ok=True)
        (pasta / f"{versao}-{modo}.json").write_text(json.dumps(
            {"versao": versao, "modo": modo, "em": datetime.now(timezone.utc).isoformat(), **n, "resultados": resultados},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if n["aprovados"] == n["cenarios"] else 1


if __name__ == "__main__":
    sys.exit(main())
