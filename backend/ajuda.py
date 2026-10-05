"""
Catálogo da Central de Ajuda.

O conteúdo vive em `ajuda/*.md`, um arquivo por assunto, e é estático: a Central
não gera texto, não consulta IA, não manda a pergunta para fora do servidor.

Formato de cada entrada (parser abaixo, estrito de propósito — erro de digitação
numa chave vira falha de teste, não resposta faltando em produção):

    ## id-em-kebab-case
    titulo: Como a tela chama
    perfis: operador, admin, comando
    telas: Visão da carteira; Recuperabilidade
    perguntas:
    - jeito de perguntar 1
    - jeito de perguntar 2
    curta: Uma ou duas frases, o que aparece no "?".
    calculo: A fórmula, com as constantes reais.
      Linhas seguintes, recuadas em dois espaços, continuam o campo.
    fazer: O que fazer com isso.
    cuidado: Quando não confiar.
    revisar: (opcional) por que esta entrada pode ficar velha: decisão pendente.
    fontes:
    - backend/model/psi.py::calcular
    constantes:
    - backend/model/psi.py::PSI_CRITICO = 0.25

Cada fonte e cada constante é conferida contra o código por
`test_ajuda_catalogo.py`: se alguém renomear a função ou mudar o valor, o texto
da ajuda acusa que ficou velho em vez de continuar dizendo o que já não é verdade.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / "ajuda"
REPO = RAIZ.parent

PERFIS = ("operador", "admin", "comando")

# O que cada perfil enxerga na interface. É a fonte da regra "a ajuda não
# explica tela que o perfil não tem"; o teste confere esta tabela contra o
# front (App.jsx e os `isOperador` das telas).
TELAS = {
    "Análise":                 ("operador", "admin", "comando"),
    "Visão da carteira":       ("operador", "admin", "comando"),
    "Recuperabilidade":        ("operador", "admin", "comando"),   # a tabela da fila
    "Pagamentos registrados":  ("operador", "admin", "comando"),
    "Devedor":                 ("operador", "admin", "comando"),
    "Pagamentos":              ("operador", "admin", "comando"),   # a página /feedback
    "Conta":                   ("operador", "admin", "comando"),
    "Ciclo de cobrança":       ("admin", "comando"),
    "Precificação":            ("admin", "comando"),
    "Quem pagou":              ("admin", "comando"),
    "Usuários":                ("admin", "comando"),
    "Retenção":                ("comando",),
    "Premissas":               ("admin", "comando"),
    "Backtest":                ("admin", "comando"),
    "Auditoria":               ("admin", "comando"),
    "Performance da IA":       ("operador", "admin", "comando"),
    "Agenda":                  ("operador", "admin", "comando"),
    "Painel do operador":      ("operador", "admin", "comando"),
    "Roteiros":                ("operador", "admin", "comando"),
    "Resultados":              ("admin", "comando"),
    "Acordos":                 ("admin", "comando"),
    "Ofertas":                 ("admin", "comando"),
    "Ajuda":                   ("operador", "admin", "comando"),
    "Dúvidas":                 ("comando",),
    "Painel COMANDO":          ("comando",),
    "Aprendizado":             ("comando",),
    "Performance IA":          ("comando",),
    "Treinar modelo":          ("comando",),
    "Chaves de API":           ("comando",),
}

# Nome de cada arquivo na lista de assuntos da página de Ajuda.
ASSUNTOS = {
    "01-modelo-e-score.md": "Modelo e score",
    "02-fila-e-prioridade.md": "Fila e prioridade",
    "03-valores-e-perdas.md": "Valores, fases e perdas",
    "04-devedor-e-propostas.md": "Devedor, margem e propostas",
    "05-pagamentos-e-resultados.md": "Pagamentos e resultados",
    "06-qualidade-do-modelo.md": "Qualidade do modelo",
    "07-operacao.md": "Arquivos, conexões, pessoas e privacidade",
}

# Respostas que não têm um "?" numa tela: só se chega a elas pela busca e pelo
# índice da Central. O teste de cobertura exige que toda resposta tenha um "?"
# ou esteja aqui, com o motivo.
SO_NA_CENTRAL = {
    "perda-esperada":
        "Os cartões EAD, LGD e EL saíram do Dashboard (pedido do cliente: vocabulário de provisão, "
        "não de cobrança). A resposta continua para quem buscar esses termos.",
    "psi":
        "A linha do PSI saiu do Dashboard; o COMANDO vê a deriva em Aprendizado, onde o '?' "
        "aponta para 'deriva-do-score'. A resposta continua para quem buscar PSI.",
    "probabilidade-de-pagamento":
        "Não aparece como número em nenhuma tela: entra nas propostas como a chance de cada oferta "
        "(ligada a 'chance-de-pagamento-por-oferta'). Quem pergunta o que é encontra pela busca.",
}

_CHAVES_TEXTO = ("titulo", "curta", "calculo", "fazer", "cuidado", "revisar")
_CHAVES_LISTA = ("perguntas", "fontes", "constantes")
_CHAVES = _CHAVES_TEXTO + _CHAVES_LISTA + ("perfis", "telas")


class ErroDeCatalogo(ValueError):
    pass


@dataclass
class Entrada:
    id: str
    arquivo: str
    titulo: str = ""
    perfis: list = field(default_factory=list)
    telas: list = field(default_factory=list)
    perguntas: list = field(default_factory=list)
    curta: str = ""
    calculo: str = ""
    fazer: str = ""
    cuidado: str = ""
    revisar: str = ""
    fontes: list = field(default_factory=list)
    constantes: list = field(default_factory=list)

    def visivel_para(self, perfil: str) -> bool:
        return perfil in self.perfis


def _interpretar(arquivo: Path) -> list:
    entradas, atual, chave = [], None, None
    for n, bruto in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        onde = f"{arquivo.name}:{n}"
        if bruto.startswith("## "):
            atual = Entrada(id=bruto[3:].strip(), arquivo=arquivo.name)
            entradas.append(atual)
            chave = None
            continue
        if atual is None:
            continue                       # texto livre antes da primeira entrada
        if not bruto.strip():
            continue
        if bruto.startswith("  ") and chave:                      # continuação
            _anexar(atual, chave, bruto.strip(), continuacao=True)
            continue
        if bruto.startswith("- ") and chave in _CHAVES_LISTA:
            getattr(atual, chave).append(bruto[2:].strip())
            continue
        m = re.match(r"^([a-z]+):\s*(.*)$", bruto)
        if not m or m.group(1) not in _CHAVES:
            raise ErroDeCatalogo(f"{onde}: linha que não é chave, item nem continuação: {bruto[:60]!r}")
        chave, valor = m.group(1), m.group(2).strip()
        if chave in ("perfis", "telas"):
            sep = "," if chave == "perfis" else ";"
            setattr(atual, chave, [v.strip() for v in valor.split(sep) if v.strip()])
        elif chave in _CHAVES_TEXTO:
            setattr(atual, chave, valor)
    return entradas


def _anexar(entrada: Entrada, chave: str, texto: str, continuacao: bool) -> None:
    if chave in _CHAVES_TEXTO:
        sep = "\n" if chave == "calculo" else " "
        setattr(entrada, chave, (getattr(entrada, chave) + sep + texto).strip())
    elif chave in _CHAVES_LISTA:
        lista = getattr(entrada, chave)
        if lista:
            lista[-1] = lista[-1] + " " + texto
    # perfis/telas não têm continuação: ficam numa linha


def carregar(pasta: Path = PASTA) -> list:
    """Todas as entradas do catálogo, na ordem dos arquivos."""
    todas = []
    for arq in sorted(pasta.glob("*.md")):
        if arq.name.startswith("_"):
            continue
        todas.extend(_interpretar(arq))
    return todas


def para_perfil(perfil: str, entradas: "list | None" = None) -> list:
    """O que o perfil pode ver. Nunca devolve entrada de tela que ele não tem."""
    return [e for e in (entradas if entradas is not None else carregar()) if e.visivel_para(perfil)]


# ── conferência contra o código (usada pelo teste e por scripts de revisão) ───

def _simbolos_py(texto: str) -> dict:
    """Símbolos de módulo/classe em um arquivo Python: nome -> valor literal (ou None)."""
    arvore = ast.parse(texto)
    achados = {}
    def visitar(corpo):
        for no in corpo:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                achados[no.name] = None
                if isinstance(no, ast.ClassDef):
                    visitar(no.body)
            elif isinstance(no, ast.Assign):
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name):
                        achados[alvo.id] = _avaliar(no.value)
            elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name) and no.value is not None:
                achados[no.target.id] = _avaliar(no.value)
    visitar(arvore.body)
    return achados


def _avaliar(no):
    """Valor de uma constante simples, com aritmética (ex.: 7 * 24 * 3600)."""
    try:
        return ast.literal_eval(no)
    except Exception:
        pass
    if isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
        a, b = _avaliar(no.left), _avaliar(no.right)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b,
                    ast.Div: a / b if b else None, ast.Pow: a ** b}[type(no.op)]
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.USub):
        v = _avaliar(no.operand)
        return -v if isinstance(v, (int, float)) else None
    return None


def verificar_fonte(fonte: str) -> "str | None":
    """None se a fonte existe; senão o motivo. Formas aceitas:

        arquivo::simbolo              função, classe ou constante (Python) /
                                      export function|const (JS)
        arquivo::rota /caminho        rota declarada em @app.*("/caminho") 
        arquivo::texto "Rótulo"       rótulo literal que aparece no arquivo
    """
    if "::" not in fonte:
        return f"fonte sem '::': {fonte!r}"
    caminho, _, alvo = fonte.partition("::")
    arq = REPO / caminho
    if not arq.exists():
        return f"arquivo não existe: {caminho}"
    texto = arq.read_text(encoding="utf-8")
    alvo = alvo.strip()
    if alvo.startswith("rota "):
        rota = alvo[5:].strip()
        return None if re.search(r'@app\.\w+\(\s*"' + re.escape(rota) + r'"', texto) else f"rota não encontrada: {rota}"
    if alvo.startswith("texto "):
        rotulo = alvo[6:].strip().strip('"')
        return None if rotulo in texto else f"texto não encontrado: {rotulo!r}"
    if caminho.endswith(".py"):
        return None if alvo in _simbolos_py(texto) else f"símbolo não encontrado: {alvo}"
    if re.search(r"\b(?:export\s+)?(?:default\s+)?(?:function|const|class)\s+" + re.escape(alvo) + r"\b", texto):
        return None
    return f"símbolo não encontrado: {alvo}"


def verificar_constante(item: str) -> "str | None":
    """Confere `arquivo::NOME = valor` com o valor que o código tem hoje."""
    m = re.match(r"^(.+?)::([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", item)
    if not m:
        return f"constante mal escrita: {item!r}"
    caminho, nome, esperado = m.group(1), m.group(2), m.group(3).strip()
    arq = REPO / caminho
    if not arq.exists():
        return f"arquivo não existe: {caminho}"
    texto = arq.read_text(encoding="utf-8")
    if caminho.endswith(".py"):
        simbolos = _simbolos_py(texto)
        if nome not in simbolos:
            return f"constante não encontrada: {nome}"
        atual = simbolos[nome]
        try:
            alvo = ast.literal_eval(esperado)
        except Exception:
            return f"valor esperado ilegível: {esperado!r}"
        return None if atual == alvo else f"{nome}: o código tem {atual!r}, a ajuda diz {alvo!r}"
    m2 = re.search(r"\bexport\s+const\s+" + re.escape(nome) + r"\s*=\s*([-0-9.]+)", texto) or \
         re.search(r"\bconst\s+" + re.escape(nome) + r"\s*=\s*([-0-9.]+)", texto)
    if not m2:
        return f"constante não encontrada: {nome}"
    try:
        return None if float(m2.group(1)) == float(esperado) else f"{nome}: o código tem {m2.group(1)}, a ajuda diz {esperado}"
    except ValueError:
        return f"valor ilegível: {esperado!r}"


def para_json(e: Entrada, perfil: str) -> dict:
    """O que a tela recebe de uma entrada. Detalhe técnico só para o COMANDO."""
    d = {"id": e.id, "titulo": e.titulo, "curta": e.curta, "calculo": e.calculo,
         "fazer": e.fazer, "cuidado": e.cuidado, "telas": e.telas,
         "assunto": ASSUNTOS.get(e.arquivo, e.arquivo),
         # A resposta descreve o que o sistema faz hoje, mas há uma decisão
         # pendente sobre ele: a tela avisa que pode mudar.
         "em_revisao": bool(e.revisar)}
    if perfil == "comando":
        d["fontes"] = e.fontes
        d["revisar"] = e.revisar
    return d


def indice(perfil: str, entradas: "list | None" = None) -> list:
    """Assuntos e títulos que o perfil pode ver, na ordem do catálogo."""
    grupos: dict = {}
    for e in para_perfil(perfil, entradas):
        grupos.setdefault(ASSUNTOS.get(e.arquivo, e.arquivo), []).append({"id": e.id, "titulo": e.titulo})
    return [{"assunto": a, "entradas": es} for a, es in grupos.items()]
