"""Mede a busca da Central de Ajuda com as perguntas de `ajuda_avaliacao.py`.

    python avaliar_busca.py            # dev e teste
    python avaliar_busca.py --dev      # só o conjunto de ajuste

Reporta: acerto em 1º lugar, entre os 3 primeiros, e com certeza; recusa de
perguntas fora do assunto; e quantas respostas certas a busca marcou como
"sem certeza" (custo da cautela).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ajuda                                   # noqa: E402
import ajuda_avaliacao as av                   # noqa: E402
from ajuda_busca import Buscador               # noqa: E402


def medir(conjunto: str, imprimir_erros=False, buscador=None):
    entradas = ajuda.carregar()
    b = buscador or Buscador(entradas)          # índice do COMANDO: vê tudo
    idx = {"dev": (0, 1), "teste": (2,)}[conjunto]
    n = top1 = top3 = certos = certos_e_sem_certeza = 0
    erros = []
    for id_, qs in av.AVALIACAO.items():
        for i in idx:
            r = b.buscar(qs[i], k=3)
            ids = [x["id"] for x in r["resultados"]]
            n += 1
            if ids[:1] == [id_]:
                top1 += 1
                certos += 1
                if not r["certeza"]:
                    certos_e_sem_certeza += 1
            elif id_ in ids:
                pass
            if id_ in ids:
                top3 += 1
            if ids[:1] != [id_]:
                erros.append((qs[i], id_, ids[:3], r["resultados"][0]["score"] if ids else 0, r["certeza"]))
    fora = av.FORA_DE_ESCOPO[conjunto]
    recusadas = sum(1 for q in fora if not b.buscar(q)["certeza"])
    # entre as que a busca respondeu COM certeza, quantas estavam certas
    com_certeza = sum(1 for id_, qs in av.AVALIACAO.items() for i in idx if b.buscar(qs[i])["certeza"])
    certeza_certa = sum(1 for id_, qs in av.AVALIACAO.items() for i in idx
                        if b.buscar(qs[i])["certeza"] and b.buscar(qs[i])["resultados"][0]["id"] == id_)
    res = dict(n=n, top1=top1 / n, top3=top3 / n, certezas=com_certeza / n,
               precisao_com_certeza=(certeza_certa / com_certeza if com_certeza else None),
               fora=len(fora), recusa=recusadas / len(fora))
    if imprimir_erros:
        for e in erros:
            print("  erro:", e)
    return res


if __name__ == "__main__":
    conj = ["dev"] if "--dev" in sys.argv else ["dev", "teste"]
    for c in conj:
        r = medir(c, imprimir_erros="--erros" in sys.argv)
        print(f"{c:6} n={r['n']:3}  1º lugar={r['top1']:.1%}  entre os 3={r['top3']:.1%}  "
              f"com certeza={r['certezas']:.1%} (precisão {r['precisao_com_certeza']:.1%})  "
              f"fora do assunto recusadas={r['recusa']:.1%} de {r['fora']}")
