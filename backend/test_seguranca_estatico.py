"""Prova estática do plano de segurança (docs: PLANO_SEGURANCA.md). Não executa o app.

    python test_seguranca_estatico.py

Confere requirements, package-lock, SQL, vercel.json, index.html e o texto do
main.py. Cada item imprime "ok" ou "FALHA" com o motivo. Não altere as
asserções para um item passar: se uma estiver errada, explique no PR.
"""
import ast
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
FRONT = RAIZ / "frontend"

falhas = 0


def checar(cond, item, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  [{item}] {titulo}" + (f"  — {detalhe}" if detalhe and not cond else ""))
    if not cond:
        falhas += 1


def ler(p: Path) -> str:
    return p.read_text(encoding="utf-8")


MAIN = ler(AQUI / "main.py")
ARVORE = ast.parse(MAIN)


def funcao(nome: str) -> "ast.FunctionDef | None":
    for n in ast.walk(ARVORE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nome:
            return n
    return None


def _versao(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


# ── S3: chave de API só pelo hash ─────────────────────────────────────────────
mig = AQUI / "sql" / "migracao_api_keys_sem_texto.sql"
checar(mig.exists() and re.search(r"drop\s+column\s+if\s+exists\s+api_key\b", ler(mig), re.I),
       "S3", "migração que apaga a coluna api_key existe")
f = funcao("_buscar_api_key")
fonte = ast.get_source_segment(MAIN, f) if f else ""
checar(f is not None and '"api_key"' not in fonte and "'api_key'" not in fonte,
       "S3", "_buscar_api_key não consulta a coluna em texto")
schema = ler(AQUI / "sql" / "schema.sql")
checar(not re.search(r"^\s*api_key\s+TEXT", schema, re.M | re.I), "S3", "schema.sql sem a coluna api_key")

# ── S4: exceção crua na resposta ──────────────────────────────────────────────
# Em handler amplo (Exception, bare, OSError e família, KeyError, RuntimeError),
# o detail não pode citar a exceção. type(e).__name__ é permitido.
AMPLAS = {"Exception", "BaseException", "OSError", "IOError", "FileNotFoundError", "KeyError", "RuntimeError",
          "<bare>"}


def _vaza(valor, nome) -> bool:
    for n in ast.walk(valor):
        if isinstance(n, ast.Name) and n.id == nome:
            pai = getattr(n, "_pai", None)
            if isinstance(pai, ast.Call) and ast.unparse(pai.func) == "type":
                continue
            return True
    return False


ocorrencias = []
for caminho in [AQUI / "main.py", *sorted((AQUI / "agente").glob("*.py"))]:
    arv = ast.parse(ler(caminho))
    for no in ast.walk(arv):
        for filho in ast.iter_child_nodes(no):
            filho._pai = no
    for h in ast.walk(arv):
        if not (isinstance(h, ast.ExceptHandler) and h.name):
            continue
        if h.type is None:
            tipos = {"<bare>"}
        elif isinstance(h.type, ast.Tuple):
            tipos = {ast.unparse(x) for x in h.type.elts}
        else:
            tipos = {ast.unparse(h.type)}
        if not tipos & AMPLAS:
            continue
        for n in ast.walk(h):
            if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("HTTPException"):
                for k in n.keywords:
                    if k.arg == "detail" and _vaza(k.value, h.name):
                        ocorrencias.append(f"{caminho.name}:{n.lineno}")
checar(not ocorrencias, "S4", "nenhuma exceção inesperada na resposta",
       f"{len(ocorrencias)} lugares: {', '.join(ocorrencias)}")

# ── S5: dependências ──────────────────────────────────────────────────────────
req = {}
soltas = []
for linha in ler(AQUI / "requirements.txt").splitlines():
    linha = linha.split("#")[0].strip()
    if not linha:
        continue
    m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([\w.]+)$", linha)
    if not m:
        soltas.append(linha)
        continue
    req[m.group(1).lower()] = m.group(3)
checar(not soltas, "S5", "requirements.txt só com versões exatas (==)", f"soltas: {soltas}")
MINIMOS_PY = {"fastapi": "0.162.0", "starlette": "1.10.0", "python-multipart": "0.0.32",
              "python-dotenv": "1.2.4", "cryptography": "43.0.0"}
for pacote, minimo in MINIMOS_PY.items():
    checar(pacote in req and _versao(req[pacote]) >= _versao(minimo), "S5",
           f"{pacote} >= {minimo}", f"encontrado: {req.get(pacote)}")
lock = json.loads(ler(FRONT / "package-lock.json"))
pacotes = lock.get("packages", {})
MINIMOS_JS = {"react-router": "7.18.5", "react-router-dom": "7.18.5", "jspdf": "4.2.1", "xlsx": "0.20.3"}
for pacote, minimo in MINIMOS_JS.items():
    v = (pacotes.get(f"node_modules/{pacote}") or {}).get("version", "0")
    checar(_versao(v) >= _versao(minimo), "S5", f"{pacote} >= {minimo} no package-lock", f"encontrado: {v}")
dompurify = (pacotes.get("node_modules/dompurify") or {}).get("version")
checar(dompurify is None or _versao(dompurify) >= (3, 2, 4), "S5", "dompurify sem a versão vulnerável",
       f"encontrado: {dompurify}")

# ── S10: segredos de produção ─────────────────────────────────────────────────
lf = funcao("lifespan")
lf_src = ast.get_source_segment(MAIN, lf) if lf else ""
checar("_conferir_segredos_de_producao(" in lf_src, "S10", "lifespan chama _conferir_segredos_de_producao")
if lf_src:
    i_conf = lf_src.find("_conferir_segredos_de_producao(")
    checar(0 <= i_conf < lf_src.find("_scheduler.start()") and i_conf < lf_src.find("garantir_admin()"),
           "S10", "conferência antes do agendador e do primeiro admin")

# ── S11: planilha ─────────────────────────────────────────────────────────────
checar("defusedxml" in req, "S11", "defusedxml no requirements.txt")
sem_trava = []
for f in (n for n in ast.walk(ARVORE) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
    src = ast.get_source_segment(MAIN, f) or ""
    if "pd.read_excel(" in src and f.name != "_processar":
        if "_conferir_planilha_segura(" not in src or src.find("_conferir_planilha_segura(") > src.find("pd.read_excel("):
            sem_trava.append(f.name)
checar(not sem_trava, "S11", "toda leitura de Excel em main.py passa antes pela trava", f"sem trava: {sem_trava}")
te = ler(AQUI / "model" / "treino_empresa.py")
checar("planilha.conferir(" in te, "S11", "treino por empresa também confere a planilha")

# ── S12: RLS em toda tabela dos scripts ───────────────────────────────────────
sql_tudo = "\n".join(ler(p) for p in (AQUI / "sql").glob("*.sql"))
criadas = set(re.findall(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)", sql_tudo, re.I))
com_rls = set(re.findall(r"alter\s+table\s+(?:if\s+exists\s+)?(?:public\.)?(\w+)\s+enable\s+row\s+level\s+security",
                         sql_tudo, re.I))
faltam = sorted(t.lower() for t in criadas if t.lower() not in {x.lower() for x in com_rls})
checar(not faltam, "S12", f"todas as {len(criadas)} tabelas dos scripts têm RLS", f"sem RLS: {faltam}")

# ── S13: cabeçalhos ───────────────────────────────────────────────────────────
vercel = json.loads(ler(FRONT / "vercel.json"))
cab = {h["key"].lower(): h["value"] for bloco in vercel.get("headers", []) for h in bloco.get("headers", [])}
for nome in ("content-security-policy", "x-content-type-options", "x-frame-options",
             "referrer-policy", "strict-transport-security"):
    checar(nome in cab, "S13", f"vercel.json define {nome}")
csp = cab.get("content-security-policy", "")
script_src = re.search(r"script-src([^;]*)", csp)
checar("frame-ancestors 'none'" in csp, "S13", "CSP com frame-ancestors 'none'")
checar(bool(script_src) and "unsafe-inline" not in script_src.group(1) and "unsafe-eval" not in script_src.group(1),
       "S13", "script-src sem unsafe-inline/unsafe-eval")
html = ler(FRONT / "index.html")
embutidos = [m for m in re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S) if m[1].strip()]
checar(not embutidos, "S13", "index.html sem script embutido")

# ── Itens que já estavam ok: não podem regredir ──────────────────────────────
origens = re.search(r"_ALLOWED_ORIGINS\s*=\s*\[(.*?)\]", MAIN, re.S)
checar(bool(origens) and '"*"' not in origens.group(1), "OK-CORS", "CORS sem origem coringa")
src_front = "\n".join(ler(p) for p in (FRONT / "src").rglob("*") if p.suffix in (".js", ".jsx"))
checar(not re.search(r"dangerouslySetInnerHTML|\.innerHTML\s*=|\beval\(|new Function\(", src_front),
       "OK-XSS", "frontend sem innerHTML/eval")
checar(not re.search(r"localStorage\.setItem\([^)]*token", src_front, re.I), "OK-TOKEN", "token fora do localStorage")
plano = AQUI / "test_seguranca_plano.py"
PROTEGIDAS = ("_usuario_autenticado", "_buscar_api_key", "_checar_rate_limit", "_registrar_tentativa",
              "validar_token", "conferir_login", "_credencial_google_segura", "_conferir_planilha_segura")
trocas = re.findall(rf"\bmain\.({'|'.join(PROTEGIDAS)})\s*=", ler(plano)) if plano.exists() else ["(arquivo ausente)"]
checar(not trocas, "OK-PROVA", "a prova dinâmica não substitui as funções de segurança", f"trocadas: {trocas}")

print()
print("APROVADO" if not falhas else f"{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
