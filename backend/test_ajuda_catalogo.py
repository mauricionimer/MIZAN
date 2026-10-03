"""O catálogo da Central de Ajuda não pode ficar velho nem mostrar o que o perfil não vê.

    python test_ajuda_catalogo.py

A ajuda é texto escrito à mão sobre código que muda. Sem este teste, um número
trocado no código continuaria sendo explicado do jeito antigo. Aqui:

  - toda fonte citada existe (arquivo e símbolo/rota/rótulo);
  - toda constante citada tem o valor que o código tem hoje;
  - toda entrada tem o que a Central promete (pergunta, resposta curta, cálculo,
    o que fazer, cuidado);
  - uma entrada nunca é entregue a quem não tem a tela que ela explica, e a
    tabela de telas por perfil bate com o front.
"""
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ajuda                                       # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


REPO = ajuda.REPO
entradas = ajuda.carregar()
checar(len(entradas) >= 60, f"o catálogo tem {len(entradas)} entradas (mínimo 60)")

# ── estrutura ────────────────────────────────────────────────────────────
ids = [e.id for e in entradas]
checar(len(ids) == len(set(ids)), "ids únicos", str({i for i in ids if ids.count(i) > 1}))
checar(all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids), "ids em kebab-case",
       str([i for i in ids if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i)]))
faltando = []
for e in entradas:
    for campo in ("titulo", "curta", "calculo", "fazer", "cuidado"):
        if not getattr(e, campo).strip():
            faltando.append(f"{e.id}.{campo}")
    if len(e.perguntas) < 5:
        faltando.append(f"{e.id}: só {len(e.perguntas)} perguntas")
    if not e.fontes:
        faltando.append(f"{e.id}: sem fonte")
    if not e.telas:
        faltando.append(f"{e.id}: sem telas")
    if not e.perfis:
        faltando.append(f"{e.id}: sem perfis")
checar(not faltando, "toda entrada tem título, resposta curta, cálculo, o que fazer, cuidado, 5+ perguntas, fonte, tela e perfil",
       "; ".join(faltando[:5]))
longas = [e.id for e in entradas if len(e.curta) > 330]
checar(not longas, "a resposta curta cabe num balão (até 330 caracteres)", str(longas))

# perguntas repetidas entre entradas tornam a busca ambígua
vistas, repetidas = {}, []
norm = lambda t: re.sub(r"\s+", " ", t.lower().strip())
for e in entradas:
    for p in e.perguntas:
        k = norm(p)
        if k in vistas and vistas[k] != e.id:
            repetidas.append(f"{p!r} em {vistas[k]} e {e.id}")
        vistas[k] = e.id
checar(not repetidas, "nenhuma pergunta aparece em duas entradas", "; ".join(repetidas[:3]))

# ── contra o código ──────────────────────────────────────────────────────
erros_fonte = [f"{e.id}: {f} → {m}" for e in entradas for f in e.fontes if (m := ajuda.verificar_fonte(f))]
checar(not erros_fonte, f"todas as {sum(len(e.fontes) for e in entradas)} fontes existem no código", "; ".join(erros_fonte[:3]))
erros_const = [f"{e.id}: {c} → {m}" for e in entradas for c in e.constantes if (m := ajuda.verificar_constante(c))]
checar(not erros_const, f"todas as {sum(len(e.constantes) for e in entradas)} constantes citadas têm o valor do código", "; ".join(erros_const[:3]))

# ── perfis e telas ───────────────────────────────────────────────────────
desconhecidas = [f"{e.id}: {t}" for e in entradas for t in e.telas if t not in ajuda.TELAS]
checar(not desconhecidas, "toda tela citada existe na tabela de telas", "; ".join(desconhecidas[:3]))
perfis_ruins = [f"{e.id}: {p}" for e in entradas for p in e.perfis if p not in ajuda.PERFIS]
checar(not perfis_ruins, "todo perfil citado é válido", "; ".join(perfis_ruins[:3]))

vazamentos = []
for e in entradas:
    permitido = set(ajuda.PERFIS)
    for t in e.telas:
        permitido &= set(ajuda.TELAS.get(t, ()))
    sobra = set(e.perfis) - permitido
    if sobra:
        vazamentos.append(f"{e.id} entrega a {sorted(sobra)} a explicação de {e.telas}")
checar(not vazamentos, "nenhuma entrada explica ao perfil uma tela que ele não tem", "; ".join(vazamentos[:3]))

op = ajuda.para_perfil("operador", entradas)
checar(op and all("operador" in e.perfis for e in op), f"o operador recebe {len(op)} entradas, todas marcadas para ele")
admin_so = {"precificacao-simulador", "perda-esperada", "fases-do-ciclo", "psi", "treino-por-empresa", "ks"}
checar(not ({e.id for e in op} & admin_so),
       "e nenhuma de precificação, ciclo, PSI, treino ou KS", str({e.id for e in op} & admin_so))
cm = ajuda.para_perfil("comando", entradas)
checar(len(cm) == len(entradas), "o COMANDO recebe tudo")

# ── a tabela de telas bate com o front ───────────────────────────────────
app = (REPO / "frontend/src/App.jsx").read_text(encoding="utf-8")
def papeis(rota):
    m = re.search(r'<Route path="' + re.escape(rota) + r'"[^\n]*?roles=\{\[([^\]]*)\]\}', app)
    return tuple(sorted(x.strip().strip("'\"") for x in m.group(1).split(","))) if m else None
esperado = {
    "/admin/usuarios": "Usuários", "/retencao": "Retenção", "/premissas": "Premissas", "/backtest": "Backtest",
    "/auditoria": "Auditoria", "/comando": "Painel COMANDO", "/aprendizado": "Aprendizado",
    "/bandit": "Performance IA", "/comando/treino": "Treinar modelo",
}
divergentes = []
for rota, tela in esperado.items():
    no_front = papeis(rota)
    na_tabela = tuple(sorted(ajuda.TELAS[tela]))
    if no_front != na_tabela:
        divergentes.append(f"{rota}: front {no_front}, tabela {na_tabela}")
checar(not divergentes, "as telas restritas da tabela batem com os papéis das rotas do front", "; ".join(divergentes))

dash = (REPO / "frontend/src/pages/Dashboard.jsx").read_text(encoding="utf-8").split("\n")
def sob_filtro_de_operador(marcador, janela=6):
    for i, l in enumerate(dash):
        if marcador in l:
            return any("!isOperador" in x for x in dash[i:i + janela])
    return None
for tela, marcador in (("Precificação", "── Precificação ──"), ("Ciclo de cobrança", "── Ciclo de cobrança ──"),
                       ("Quem pagou", "── Resultados Reais ──")):
    achado = sob_filtro_de_operador(marcador)
    checar(achado is True and "operador" not in ajuda.TELAS[tela],
           f"'{tela}' está escondida do operador no front e na tabela", f"front={achado}")
alc = sob_filtro_de_operador("── Alcance da operação ──", janela=8)
checar(alc is False and "operador" in ajuda.TELAS["Alcance da operação"], "'Alcance da operação' é visível ao operador, no front e na tabela")

# ── achados citados existem no mapa ──────────────────────────────────────
mapa = (REPO / "docs/MAPA_DO_SISTEMA.md").read_text(encoding="utf-8")
codigos_do_mapa = set(re.findall(r"\*\*([A-Z]\d{1,2})\*\*", mapa))
citados = {c for e in entradas for c in re.findall(r"\b([A-Z]\d{1,2})\b", e.revisar)}
orfaos = citados - codigos_do_mapa
checar(not orfaos, "todo achado citado em 'revisar' existe no mapa do sistema", str(sorted(orfaos)))

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
