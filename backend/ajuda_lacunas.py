"""
O que a Central de Ajuda não soube responder: agrupar para o COMANDO saber o que escrever.

Duas fontes entram aqui, sem identificar ninguém (só o perfil de quem buscou):
  - 'sem_resposta': a busca não teve certeza do que respondeu;
  - 'nao_resolveu': a pessoa viu uma resposta e disse que não resolveu.

"Como vejo quem pagou?" e "como vejo os pagamentos" são a mesma lacuna escrita
de dois jeitos. A chave (texto normalizado, ver ajuda_busca.preparar) junta as
variações que só diferem em acento, caixa, plural ou palavras de ligação; o que
fica separado o COMANDO enxerga lado a lado.
"""

from collections import Counter

import ajuda_busca


def chave_de(texto: str) -> str:
    """Texto normalizado e ordenado por palavra: a ordem das palavras não separa duas lacunas."""
    palavras = sorted(set(ajuda_busca.preparar(texto).split()))
    return " ".join(palavras)[:300]


def agrupar(linhas: list) -> list:
    """Uma entrada por pergunta (chave), da mais repetida para a menos."""
    grupos: dict = {}
    for r in linhas:
        g = grupos.setdefault(r["chave"], {"linhas": []})
        g["linhas"].append(r)
    saida = []
    for chave, g in grupos.items():
        ls = sorted(g["linhas"], key=lambda r: r.get("created_at") or "", reverse=True)
        tratadas = [r for r in ls if r.get("tratada_em")]
        saida.append({
            "chave": chave,
            "exemplo": ls[0]["pergunta"],
            "total": len(ls),
            "sem_resposta": sum(1 for r in ls if r["tipo"] == "sem_resposta"),
            "nao_resolveu": sum(1 for r in ls if r["tipo"] == "nao_resolveu"),
            "ultima": ls[0].get("created_at"),
            "perfis": dict(Counter(r["perfil"] for r in ls)),
            # as respostas que foram mostradas e não resolveram, as mais citadas primeiro
            "entradas_que_nao_resolveram": [
                {"id": i, "vezes": n} for i, n in
                Counter(r["entrada_id"] for r in ls if r.get("entrada_id")).most_common(3)],
            "tratada": len(tratadas) == len(ls),
            # tratada antes e voltou a aparecer: a resposta escrita não bastou
            "reapareceu": 0 < len(tratadas) < len(ls),
        })
    # mais repetida primeiro; entre iguais, a mais recente (duas ordenações estáveis)
    saida.sort(key=lambda g: g["ultima"] or "", reverse=True)
    saida.sort(key=lambda g: g["total"], reverse=True)
    return saida
