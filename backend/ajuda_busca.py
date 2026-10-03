"""
Busca da Central de Ajuda: local, sem IA e sem mandar a pergunta para fora.

A pergunta é comparada com as perguntas de cada entrada do catálogo (e com o
título e a resposta curta) por semelhança de texto:

  - sem acento nem maiúscula, sem palavras de ligação;
  - sinônimos do domínio ("nota" = score, "ranking" = fila);
  - dois olhares combinados: palavras inteiras e pedaços de palavra (3 a 5
    letras), que tolera plural, conjugação e erro de digitação.

A busca NUNCA inventa. Quando a melhor entrada não é parecida o bastante, ou
quando duas disputam o primeiro lugar, devolve `certeza = False` e as mais
próximas como sugestão: responder errado com confiança é pior que dizer que não
achou. A qualidade é medida por `avaliar_busca.py` com perguntas escritas à
parte (`ajuda_avaliacao.py`), e o resultado entra no teste.

Cada perfil tem o seu índice, montado só com o que ele pode ver: perguntar sobre
uma tela que ele não tem não acha nada, em vez de achar uma resposta de admin.
"""

import re
import unicodedata
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

import ajuda

# Palavras de ligação. "não" fica: muda o sentido ("pago e não pago").
_LIGACAO = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "por", "para", "pra", "pro", "com", "sem", "e", "ou", "que", "se", "ao", "aos", "me",
    "meu", "minha", "meus", "minhas", "seu", "sua", "isso", "isto", "esse", "essa", "esses", "essas",
    "este", "esta", "e", "eh", "ele", "ela", "eles", "elas", "qual", "quais", "como", "onde", "quando",
    "porque", "por", "pq", "foi", "ser", "sao", "esta", "estao", "tem", "ter", "mais", "muito", "ja",
    "la", "ai", "so", "mas", "ha", "vai", "vou", "posso", "pode", "podem", "faco", "fazer", "dar", "da",
    "quero", "preciso", "sistema", "mizan",
}

# Termo do usuário -> termos do catálogo que ele costuma significar.
_SINONIMOS = {
    "nota": "score", "pontuacao": "score", "ranking": "fila", "rank": "fila", "lista": "fila",
    "posicao": "fila", "cara": "devedor", "pessoa": "devedor", "inadimplente": "devedor",
    "caloteiro": "devedor", "ligar": "contato", "liguei": "contato", "telefonar": "contato",
    "ligacao": "contato", "anotar": "registrar", "lancar": "registrar", "lanco": "registrar",
    "baixa": "pagamento", "pagar": "pagou", "paga": "pagou", "pago": "pagou", "quitou": "pagou",
    "quitar": "pagou", "recuperar": "recuperacao", "recebo": "recuperacao", "receber": "recuperacao",
    "escritorio": "comissao", "terceirizada": "comissao", "terceirizado": "comissao",
    "drift": "deriva", "mudou": "deriva", "carteira": "carteira", "planilha": "arquivo",
    "csv": "arquivo", "excel": "arquivo", "subir": "enviar", "upload": "enviar", "importar": "enviar",
    "apagar": "eliminar", "excluir": "eliminar", "deletar": "eliminar", "exclusao": "eliminacao",
    "ia": "abordagem recomendacao", "robo": "abordagem recomendacao", "usuario": "usuarios",
    "funcionario": "usuarios", "login": "senha sessao", "logo": "logo foto", "marca": "logo foto",
    "cor": "cor tema", "acerto": "acuracia", "acertando": "acuracia", "divisao": "faixa",
    "cinco": "5", "dez": "10", "vinte": "20", "trinta": "30", "quarenta": "40", "cinquenta": "50",
    "oitenta": "80", "cem": "100", "meio": "0.5", "zero": "0",
}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9.% ]+", " ", t)


def _radical(p: str) -> str:
    """Tira plural e terminações comuns, sem pretensão de ser um stemmer completo."""
    if len(p) > 5 and p.endswith("oes"):
        return p[:-3] + "ao"
    if len(p) > 5 and p.endswith("res"):
        return p[:-2]
    if len(p) > 4 and p.endswith("s") and not p.endswith("ss"):
        return p[:-1]
    return p


def _palavras(texto: str) -> list:
    saida = []
    for p in normalizar(texto).split():
        p = p.strip(".%")
        if not p or p in _LIGACAO:
            continue
        saida.append(_radical(p))
        extra = _SINONIMOS.get(p)
        if extra:
            saida.extend(_radical(x) for x in extra.split())
    return saida


def preparar(texto: str) -> str:
    return " ".join(_palavras(texto))


class Buscador:
    """Índice de um conjunto de entradas. Barato de montar (algumas centenas de textos)."""

    PESO_TITULO = 1.0
    PESO_CURTA = 0.55
    PESO_CORPO = 0.45
    COBERTURA = 0.60     # fração das palavras da pergunta que o catálogo conhece
    LIMIAR = 0.40        # abaixo disto, nenhuma entrada é parecida o bastante
    MARGEM = 0.06        # diferença mínima para o 1º não estar empatado com o 2º

    def __init__(self, entradas: list):
        self.entradas = entradas
        docs, dono, peso = [], [], []
        vocabulario = set()
        for i, e in enumerate(entradas):
            for p in e.perguntas:
                docs.append(preparar(p)); dono.append(i); peso.append(1.0)
            docs.append(preparar(e.titulo)); dono.append(i); peso.append(self.PESO_TITULO)
            docs.append(preparar(e.curta)); dono.append(i); peso.append(self.PESO_CURTA)
            # O corpo da resposta traz o vocabulário que o operador usa ao
            # descrever o problema ("controles deslizantes", "faixa de dias").
            for campo in (e.calculo, e.fazer, e.cuidado):
                for frase in re.split(r"(?<=[.;])\s+|\n", campo):
                    d = preparar(frase)
                    if len(d.split()) >= 3:
                        docs.append(d); dono.append(i); peso.append(self.PESO_CORPO)
            vocabulario.update(_palavras(" ".join([e.titulo, e.curta, e.calculo, e.fazer, e.cuidado] + e.perguntas)))
        self._vocabulario = vocabulario
        self._dono = np.array(dono)
        self._peso = np.array(peso)
        self._palavras = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self._pedacos = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self._mp = self._palavras.fit_transform(docs)
        self._mc = self._pedacos.fit_transform(docs)

    def pontuar(self, pergunta: str) -> np.ndarray:
        """Um número por entrada, entre 0 e 1."""
        q = preparar(pergunta)
        if not q:
            return np.zeros(len(self.entradas))
        sp = (self._mp @ self._palavras.transform([q]).T).toarray().ravel()
        sc = (self._mc @ self._pedacos.transform([q]).T).toarray().ravel()
        por_doc = (0.5 * sp + 0.5 * sc) * self._peso
        por_entrada = np.zeros(len(self.entradas))
        np.maximum.at(por_entrada, self._dono, por_doc)
        return por_entrada

    def cobertura(self, pergunta: str) -> float:
        """Fração das palavras da pergunta que aparecem em algum lugar do catálogo.

        Pergunta fora do assunto ("previsão do tempo") traz palavras que o
        catálogo nunca viu; pergunta do assunto, mesmo mal escrita, quase sempre
        reaproveita o vocabulário. É o que separa "não achei" de "achei algo
        parecido".
        """
        palavras = [p for p in _palavras(pergunta) if len(p) >= 3 and not p.isdigit()]
        if not palavras:
            return 0.0
        return sum(1 for p in palavras if p in self._vocabulario) / len(palavras)

    def buscar(self, pergunta: str, k: int = 3) -> dict:
        p = self.pontuar(pergunta)
        ordem = np.argsort(-p)[:k]
        melhores = [(self.entradas[i], float(p[i])) for i in ordem if p[i] > 0]
        certeza = False
        if melhores:
            topo = melhores[0][1]
            segundo = melhores[1][1] if len(melhores) > 1 else 0.0
            certeza = (topo >= self.LIMIAR and (topo - segundo) >= self.MARGEM
                       and self.cobertura(pergunta) >= self.COBERTURA)
        return {"certeza": certeza,
                "resultados": [{"id": e.id, "score": round(s, 4)} for e, s in melhores]}


@lru_cache(maxsize=8)
def buscador_para(perfil: str) -> Buscador:
    """Índice do perfil: só o que ele pode ver. Montado uma vez por processo."""
    return Buscador(ajuda.para_perfil(perfil))
