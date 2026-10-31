"""Busca híbrida nos dispositivos: termos exatos (BM25) + semântica local (LSA), fundidas
por posição (Reciprocal Rank Fusion).

- BM25 acha o dispositivo pelos termos da pergunta ("revisão", "decisão automatizada",
  "art. 42-A") e pelos radicais ("cobrança" ~ "cobrar").
- LSA (TF-IDF + SVD, scikit-learn) aproxima textos que falam da mesma coisa com palavras
  diferentes. É semântica estatística, treinada só no acervo; nada sai do servidor.
- Os sinônimos de texto.py traduzem o vocabulário da operação para o da lei.

Ficam fora da busca: revogados, vetados, duplicados de outra norma e trechos com cara de
instrução. Revogados e vetados continuam acessíveis por artigo, para registro.
"""
import math
import threading
from collections import Counter

from agente.juridico.texto import expandir, termos

RRF_K = 60
_CACHE = {"versao": None, "indice": None}
_LOCK = threading.Lock()


def buscavel(r: dict) -> bool:
    return (r.get("situacao") in ("vigente", "desatualizado") and not r.get("duplicado_de")
            and not r.get("alerta_instrucao"))


class Indice:
    def __init__(self, registros: list, manifesto: dict):
        self.registros = registros
        self.manifesto = manifesto or {}
        self.versao = self.manifesto.get("versao_indice") or "sem-versao"
        self.por_id = {r["id"]: r for r in registros}
        self.por_artigo = {}
        for r in registros:
            self.por_artigo.setdefault((r["norma_id"], r["artigo"]), []).append(r)
        self.docs = [r for r in registros if buscavel(r)]
        self._toks = [termos(f"{r['rotulo']} {r.get('contexto', '')} {r['texto']} {r['texto']}")
                      for r in self.docs]
        self._bm25_preparar()
        self._lsa = None

    # ── BM25 ──
    def _bm25_preparar(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(t) for t in self._toks]
        self.dl = [len(t) for t in self._toks]
        self.avgdl = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        df = Counter(w for t in self._toks for w in set(t))
        n = len(self._toks)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def _bm25(self, q: list) -> list:
        notas = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl))
            notas.append(s)
        return notas

    # ── LSA ──
    def _lsa_preparar(self):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize
        self._vet = TfidfVectorizer(analyzer=lambda x: x, sublinear_tf=True, min_df=1)
        m = self._vet.fit_transform(self._toks)
        comps = max(2, min(150, m.shape[0] - 1, m.shape[1] - 1))
        self._svd = TruncatedSVD(n_components=comps, random_state=7)
        self._docs_lsa = normalize(self._svd.fit_transform(m))
        self._normalize = normalize
        self._lsa = True

    def _semantica(self, q: list) -> list:
        if not self.docs:
            return []
        if self._lsa is None:
            self._lsa_preparar()
        v = self._normalize(self._svd.transform(self._vet.transform([q])))
        return list((self._docs_lsa @ v.T).ravel())

    def buscar(self, consulta: str, k: int = 8, normas=None) -> list:
        """[(registro, pontuação, {"bm25": pos, "semantica": pos})], do mais pertinente ao menos."""
        if not self.docs:
            return []
        q = termos(expandir(consulta))
        if not q:
            return []
        lex, sem = self._bm25(q), self._semantica(q)
        idx = [i for i in range(len(self.docs)) if not normas or self.docs[i]["norma_id"] in normas]
        ord_lex = [i for i in sorted(idx, key=lambda i: -lex[i]) if lex[i] > 0]
        ord_sem = [i for i in sorted(idx, key=lambda i: -sem[i]) if sem[i] > 0.05]
        rrf = Counter()
        pos = {}
        for nome, ordem in (("bm25", ord_lex[:200]), ("semantica", ord_sem[:200])):
            for p, i in enumerate(ordem):
                rrf[i] += 1.0 / (RRF_K + p + 1)
                pos.setdefault(i, {})[nome] = p + 1
        melhores = rrf.most_common(k)
        return [(self.docs[i], round(s, 5), pos[i]) for i, s in melhores]

    def artigo(self, norma_id: str, artigo: str) -> list:
        """Todos os dispositivos do artigo, na ordem do texto (inclui revogados e vetados)."""
        return list(self.por_artigo.get((norma_id, str(artigo)), []))


def carregar_indice(dados=None) -> Indice:
    """Índice gravado no pacote (agente/juridico/dados), carregado uma vez por processo."""
    from agente.juridico import ingestao
    registros, manifesto = ingestao.carregar(dados or ingestao.DADOS)
    versao = (manifesto or {}).get("versao_indice")
    with _LOCK:
        if dados is None and _CACHE["indice"] is not None and _CACHE["versao"] == versao:
            return _CACHE["indice"]
        ind = Indice(registros, manifesto)
        if dados is None:
            _CACHE.update(versao=versao, indice=ind)
        return ind
