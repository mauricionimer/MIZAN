"""Cada "?" do front leva a uma resposta que existe e que quem vê a tela pode ler.

    python test_ajuda_cobertura.py

O "?" ao lado de uma métrica só se esconde quando o perfil não pode ver a
resposta. Por isso a conferência é estática: se um "?" apontasse para uma
resposta que o perfil da tela não tem, ele nunca apareceria, e ninguém notaria.
"""
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ajuda                                       # noqa: E402
from model.premissas import PREMISSAS              # noqa: E402

falhas = 0


def checar(cond, titulo, detalhe=""):
    global falhas
    print(f"{'ok  ' if cond else 'FALHA'}  {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not cond:
        falhas += 1


entradas = {e.id: e for e in ajuda.carregar()}
SRC = ajuda.REPO / "frontend/src"
ARQ = {f.relative_to(SRC): f.read_text(encoding="utf-8") for f in SRC.rglob("*.jsx")}

# quem enxerga cada arquivo
TODOS = {"operador", "admin", "comando"}
PAGINAS = {
    "pages/Dashboard.jsx": TODOS, "pages/DebtorDetail.jsx": TODOS, "pages/Upload.jsx": TODOS,
    "pages/Feedback.jsx": TODOS, "pages/AlterarSenha.jsx": TODOS,
    "pages/Retencao.jsx": {"comando"}, "pages/Auditoria.jsx": {"admin", "comando"},
    "pages/AdminUsuarios.jsx": {"admin", "comando"}, "pages/Backtest.jsx": {"admin", "comando"},
    "pages/Premissas.jsx": {"admin", "comando"}, "pages/Ajuda.jsx": TODOS,
    "pages/DuvidasComando.jsx": {"comando"},
    "pages/AprendizadoDashboard.jsx": {"comando"}, "pages/BanditDashboard.jsx": {"comando"},
    "pages/ComandoDashboard.jsx": {"comando"}, "pages/TreinoModelo.jsx": {"comando"},
    "pages/ChavesApi.jsx": {"comando"}, "pages/PerformanceIA.jsx": TODOS,
    "components/DistribuirFila.jsx": {"admin", "comando"}, "pages/Agenda.jsx": TODOS, "pages/PainelOperador.jsx": TODOS,
}

# ids citados em cada arquivo (qualquer texto entre aspas, na linha de um "?")
ligacoes = {}
desconhecidos = []
for arq, texto in ARQ.items():
    for n, linha in enumerate(texto.split("\n"), 1):
        if not re.search(r"DicaAjuda|ajuda\s*[=:]|ajuda_id", linha):
            continue
        for m in re.findall(r"""['"]([a-z0-9]+(?:-[a-z0-9]+)*)['"]""", linha):
            if m in entradas:
                ligacoes.setdefault(m, set()).add(str(arq))
        # DicaAjuda/ajuda estático com id que não existe
        for m in re.findall(r"""(?:DicaAjuda id|ajuda)\s*[=:]\s*["']([^"']+)["']""", linha):
            if m not in entradas:
                desconhecidos.append(f"{arq}:{n} → {m}")
for p in PREMISSAS.values():                          # a tela de premissas liga por dado
    ligacoes.setdefault(p.ajuda_id, set()).add("pages/Premissas.jsx")

checar(not desconhecidos, "todo \"?\" estático aponta para uma resposta que existe", "; ".join(desconhecidos[:3]))
checar(all(p.ajuda_id in entradas for p in PREMISSAS.values()), "e os campos da tela de premissas também")

# a resposta é legível por quem vê a página
ruins = []
for id_, arqs in ligacoes.items():
    e = entradas[id_]
    for a in arqs:
        publico = PAGINAS.get(a)
        if publico is None:
            ruins.append(f"{a}: página sem público declarado")
            continue
        if publico == TODOS:
            if not e.perfis:
                ruins.append(f"{id_} em {a}: ninguém lê")
        elif not publico <= set(e.perfis):
            ruins.append(f"{id_} em {a}: a página é de {sorted(publico)}, a resposta só de {e.perfis}")
checar(not ruins, "todo \"?\" leva a uma resposta que o público da página consegue ler", "; ".join(ruins[:3]))

# cobertura: toda resposta está ligada a um "?" ou é declarada só da Central
sem_ligacao = sorted(set(entradas) - set(ligacoes) - set(ajuda.SO_NA_CENTRAL))
checar(not sem_ligacao, f"todas as respostas têm um \"?\" ({len(ligacoes)} ligadas, {len(ajuda.SO_NA_CENTRAL)} só na Central)", str(sem_ligacao))
sobra = sorted(set(ajuda.SO_NA_CENTRAL) & set(ligacoes))
checar(not sobra, "nada declarado 'só na Central' tem um \"?\" (a lista não envelhece)", str(sobra))
checar(set(ajuda.SO_NA_CENTRAL) <= set(entradas), "e tudo que está na lista existe")

print("\nRESULTADO:", "tudo certo" if falhas == 0 else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
