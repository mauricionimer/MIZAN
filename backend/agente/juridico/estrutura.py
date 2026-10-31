"""Texto da norma → dispositivos: artigo (caput), parágrafo, inciso e alínea.

Cada dispositivo vira um trecho com:
- rótulo canônico ("LGPD, art. 18, § 4º, inciso II");
- o próprio texto, sem as notas editoriais;
- o contexto para interpretá-lo: capítulo e seção, o caput do artigo e o
  dispositivo-pai (o parágrafo de um inciso, o inciso de uma alínea);
- as notas ("redação dada pela Lei nº …") e a situação: vigente, revogado ou vetado.

Formato de entrada: o Markdown do acervo ctresb/leis (cabeçalho YAML; "**Art. 1º**",
"**§ 1º**", "**Parágrafo único.**", "I - …", "a) …"; notas em itálico entre parênteses).
"""
import hashlib
import re

from agente.juridico.texto import normalizar, parece_instrucao

VERSAO_PARSER = "2"

_ART = re.compile(r"^\*\*Art\.\s*(\d+)\s*[ºo°]?\s*(-[A-Z])?\s*\.?\*\*\s*(.*)$")
_PAR = re.compile(r"^\*\*§\s*(\d+)\s*[ºo°]?\s*(-[A-Z])?\s*\.?\*\*\s*(.*)$")
_PAR_UNICO = re.compile(r"^\*\*Par[aá]grafo [uú]nico\.?\*\*\s*(.*)$", re.I)
_INCISO = re.compile(r"^([IVXLC]+(?:-[A-Z])?)\s*[-–—]\s+(.*)$")
_ALINEA = re.compile(r"^([a-z])\)\s+(.*)$")
_TITULO = re.compile(r"^#{2,4}\s+((T[ÍI]TULO|LIVRO)\b.*)$", re.I)
_CAPITULO = re.compile(r"^#{3,5}\s+(CAP[ÍI]TULO\b.*)$", re.I)
_SECAO = re.compile(r"^#{4,6}\s+((Se[çc][ãa]o|Subse[çc][ãa]o)\b.*)$", re.I)
_NOTA = re.compile(r"\*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\*")
_FIM = re.compile(r"^(Bras[ií]lia,|Este texto n[ãa]o substitui|_{3,})", re.I)


def ler_cabecalho(texto: str) -> tuple:
    """(metadados do YAML, corpo)."""
    meta, corpo = {}, texto
    if texto.startswith("---"):
        fim = texto.find("\n---", 3)
        if fim > 0:
            for linha in texto[3:fim].splitlines():
                m = re.match(r"^([a-z_0-9]+):\s*(.*)$", linha.strip())
                if m:
                    v = m.group(2).strip()
                    if len(v) >= 2 and v[0] == v[-1] == '"':
                        v = v[1:-1]
                    meta[m.group(1)] = {"true": True, "false": False, "null": None}.get(v, v)
            corpo = texto[fim + 4:]
    return meta, corpo


def _ordinal(n: str) -> str:
    return f"{n}º" if n.isdigit() and int(n) < 10 else n


def _limpar(texto: str) -> tuple:
    """(texto sem notas e sem marcação, notas)."""
    notas = [n.strip() for n in _NOTA.findall(texto)]
    t = _NOTA.sub("", texto)
    t = re.sub(r"\*\*|__|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", t)
    return re.sub(r"\s+", " ", t).strip(), notas


def _situacao(texto: str, notas: list) -> str:
    alvo = normalizar(" ".join(notas) + " " + texto)
    if not texto.strip() or re.fullmatch(r"\(?\s*(vetado|revogad[oa].*)\)?\.?", normalizar(texto)):
        if "vetad" in alvo:
            return "vetado"
        if "revogad" in alvo:
            return "revogado"
    if re.search(r"\b(revogad[oa])\b", normalizar(" ".join(notas))) and not re.search(r"redacao dada", alvo):
        return "revogado"
    if re.fullmatch(r"\(?vetad[oa].*", normalizar(texto)):
        return "vetado"
    return "vigente"


def dispositivos(texto_md: str, norma_id: str, sigla: str, recorte=()) -> list:
    """Dispositivos da norma, na ordem do texto. `recorte` limita a faixas de artigos."""
    _, corpo = ler_cabecalho(texto_md)
    saida = []
    ctx = {"titulo": "", "capitulo": "", "secao": ""}
    art = None           # {"num", "rotulo", "caput", "base"}
    pai_par = None       # parágrafo atual (para incisos)
    pai_inc = None       # inciso atual (para alíneas)
    atual = None         # último dispositivo (recebe linhas de continuação)
    dentro = True

    def no_recorte(num: str) -> bool:
        if not recorte:
            return True
        n = int(re.match(r"\d+", num).group())
        return any(a <= n <= b for a, b in recorte)

    def novo(caminho, rotulo, texto_bruto, pai=None):
        nonlocal atual
        texto, notas = _limpar(texto_bruto)
        d = {"norma_id": norma_id, "artigo": art["num"], "caminho": caminho, "rotulo": rotulo,
             "texto": texto, "notas": notas, "capitulo": ctx["capitulo"], "secao": ctx["secao"],
             "titulo": ctx["titulo"], "pai": pai}
        saida.append(d)
        atual = d
        return d

    for bruta in corpo.splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("# "):
            continue
        if _FIM.match(linha):
            dentro = False
            atual = None
            continue
        m = _TITULO.match(linha)
        if m:
            ctx.update(titulo=_limpar(m.group(1))[0], capitulo="", secao="")
            atual = None
            continue
        m = _CAPITULO.match(linha)
        if m:
            ctx.update(capitulo=_limpar(m.group(1))[0], secao="")
            atual = None
            continue
        m = _SECAO.match(linha)
        if m:
            ctx["secao"] = _limpar(m.group(1))[0]
            atual = None
            continue
        m = _ART.match(linha)
        if m:
            num = m.group(1) + (m.group(2) or "")
            dentro = True
            if not no_recorte(num):
                art, atual, pai_par, pai_inc = None, None, None, None
                continue
            rot = f"{sigla}, art. {_ordinal(m.group(1))}{m.group(2) or ''}"
            art = {"num": num, "rotulo": rot}
            pai_par = pai_inc = None
            d = novo("caput", rot, m.group(3))
            art["caput"] = d
            continue
        if art is None or not dentro:
            continue
        m = _PAR.match(linha)
        if m:
            n = m.group(1) + (m.group(2) or "")
            pai_par = novo(f"p{n}", f"{art['rotulo']}, § {_ordinal(m.group(1))}{m.group(2) or ''}", m.group(3),
                           pai="caput")
            pai_inc = None
            continue
        m = _PAR_UNICO.match(linha)
        if m:
            pai_par = novo("pu", f"{art['rotulo']}, parágrafo único", m.group(1), pai="caput")
            pai_inc = None
            continue
        m = _INCISO.match(linha)
        if m:
            base = pai_par or art["caput"]
            pai_inc = novo(f"{base['caminho']}.i{m.group(1)}", f"{base['rotulo']}, inciso {m.group(1)}",
                           m.group(2), pai=base["caminho"])
            continue
        m = _ALINEA.match(linha)
        if m and pai_inc is not None:
            novo(f"{pai_inc['caminho']}.a{m.group(1)}", f"{pai_inc['rotulo']}, alínea {m.group(1)}",
                 m.group(2), pai=pai_inc["caminho"])
            continue
        if atual is not None:                       # continuação (texto citado, quebra de linha)
            texto, notas = _limpar(linha)
            atual["texto"] = (atual["texto"] + " " + texto).strip()
            atual["notas"] = atual["notas"] + notas

    return _finalizar(saida)


def _finalizar(itens: list) -> list:
    """Situação, contexto para interpretação, ids e hashes; marca rótulos repetidos (conflito)."""
    por_art = {}
    for d in itens:
        por_art.setdefault(d["artigo"], {})[d["caminho"]] = d
    vistos = {}
    for d in itens:
        d["situacao"] = _situacao(d["texto"], d["notas"])
        familia = por_art[d["artigo"]]
        partes = [p for p in (d["titulo"], d["capitulo"], d["secao"]) if p]
        cadeia, pai = [], d.get("pai")
        while pai:
            p = familia.get(pai)
            if p is None:
                break
            cadeia.insert(0, f"{p['rotulo']}: {p['texto']}")
            pai = p.get("pai")
        d["contexto"] = " | ".join(partes + cadeia)
        d["hash"] = hashlib.sha1(normalizar(d["texto"]).encode("utf-8")).hexdigest()[:16]
        d["alerta_instrucao"] = parece_instrucao(d["texto"])
        base_id = f"{d['norma_id']}:{d['artigo']}:{d['caminho']}"
        n = vistos.get(base_id, 0)
        vistos[base_id] = n + 1
        d["id"] = base_id if n == 0 else f"{base_id}#{n + 1}"
    # O mesmo dispositivo aparecendo duas vezes no texto: as versões ficam marcadas
    # como conflitantes, e a decisão não se apoia em nenhuma delas sozinha.
    repetidos = {k for k, n in vistos.items() if n > 1}
    for d in itens:
        if d["id"].split("#")[0] in repetidos:
            d["conflito"] = True
    return itens
