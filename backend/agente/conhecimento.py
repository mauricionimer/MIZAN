"""Base de conhecimento do devedor: o RAG do Negociador (docs/PLANO_EXECUCAO_AGENTES.md, 6).

O caso diz quanto a pessoa deve; esta base responde o que ela pergunta e que
não está no caso: quanto tempo o nome fica negativado, quando sai depois de
pagar, comprovante, cobrança indevida, dados pessoais. Cada trecho traz a
fonte oficial (lei ou súmula), o endereço e o texto literal, para a resposta
poder ser conferida por quem estiver olhando o rastreio.

- Busca local, sem IA e sem mandar a pergunta para fora: o mesmo buscador da
  Central de Ajuda (ajuda_busca.Buscador), com a mesma regra de certeza.
- Sem certeza, devolve que não achou: o agente diz que não tem a informação e
  oferece uma pessoa. Responder errado com confiança é pior que não responder.
- Os guardrails só deixam o texto citar lei, artigo ou súmula que veio daqui
  nesta conversa (guardrails.referencias_do_texto).

O conteúdo vive em agente/base/*.md. Mudou um texto: rode
test_agente_conhecimento.py, que confere o formato e mede a busca.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "base"

_CHAVES_TEXTO = ("titulo", "fonte", "url", "resposta", "trecho")
_CHAVES_LISTA = ("perguntas",)


class ErroNaBase(ValueError):
    pass


@dataclass
class Trecho:
    id: str
    arquivo: str
    titulo: str = ""
    fonte: str = ""
    url: str = ""
    resposta: str = ""
    trecho: str = ""
    perguntas: list = field(default_factory=list)

    # O buscador da Central de Ajuda indexa estes campos: a resposta faz o papel
    # da "curta"; os outros não existem aqui.
    @property
    def curta(self) -> str:
        return self.resposta

    calculo = fazer = cuidado = ""


def _interpretar(arquivo: Path) -> list:
    trechos, atual, chave = [], None, None
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        onde = f"{arquivo.name}:{n}"
        if linha.startswith("## "):
            atual = Trecho(id=linha[3:].strip(), arquivo=arquivo.name)
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", atual.id):
                raise ErroNaBase(f"{onde}: id fora do formato: {atual.id!r}")
            trechos.append(atual)
            chave = None
            continue
        if atual is None or not linha.strip():
            continue                                   # cabeçalho do arquivo
        if linha.startswith("- ") and chave in _CHAVES_LISTA:
            getattr(atual, chave).append(linha[2:].strip())
            continue
        if linha.startswith("  ") and chave in _CHAVES_TEXTO:
            setattr(atual, chave, (getattr(atual, chave) + " " + linha.strip()).strip())
            continue
        m = re.match(r"([a-z_]+):\s*(.*)$", linha)
        if not m or m.group(1) not in _CHAVES_TEXTO + _CHAVES_LISTA:
            raise ErroNaBase(f"{onde}: linha não reconhecida: {linha!r}")
        chave, valor = m.group(1), m.group(2).strip()
        if chave in _CHAVES_LISTA:
            if valor:
                raise ErroNaBase(f"{onde}: {chave} é uma lista; use linhas com '- '")
        else:
            setattr(atual, chave, valor)
    for t in trechos:
        faltam = [c for c in _CHAVES_TEXTO if not getattr(t, c)]
        if faltam or not t.perguntas:
            raise ErroNaBase(f"{arquivo.name}: {t.id} sem {', '.join(faltam) or 'perguntas'}")
    return trechos


def carregar(pasta: Path = PASTA) -> list:
    trechos = []
    for arq in sorted(pasta.glob("*.md")):
        trechos.extend(_interpretar(arq))
    ids = [t.id for t in trechos]
    repetidos = {i for i in ids if ids.count(i) > 1}
    if repetidos:
        raise ErroNaBase(f"ids repetidos: {', '.join(sorted(repetidos))}")
    return trechos


@lru_cache(maxsize=1)
def _indice():
    from ajuda_busca import Buscador                   # numpy/sklearn só quando precisa
    trechos = carregar()
    return trechos, Buscador(trechos)


def por_id(trecho_id: str) -> "Trecho | None":
    trechos, _ = _indice()
    return next((t for t in trechos if t.id == trecho_id), None)


def consultar(pergunta: str) -> dict:
    """{"certeza": bool, "trecho": Trecho | None, "score": float}."""
    trechos, busca = _indice()
    r = busca.buscar(pergunta or "", k=2)
    if not r["certeza"]:
        return {"certeza": False, "trecho": None, "score": r["resultados"][0]["score"] if r["resultados"] else 0.0}
    melhor = r["resultados"][0]
    return {"certeza": True, "trecho": por_id(melhor["id"]), "score": melhor["score"]}
