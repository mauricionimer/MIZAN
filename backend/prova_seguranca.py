"""Roda a prova do plano de segurança e grava docs/PROVA_SEGURANCA_RESULTADO.md.

    python prova_seguranca.py          # provas novas + testes de segurança antigos + auditorias
    python prova_seguranca.py --tudo   # e também todos os test_*.py do backend

Etapas: test_seguranca_estatico.py, test_seguranca_plano.py, os testes de
segurança que já existiam, pip-audit e npm audit --omit=dev. Termina com
APROVADO só se todas passarem. O relatório leva a saída de cada etapa: "pronto"
é o relatório, não a afirmação de quem executou.
"""
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
SAIDA = RAIZ / "docs" / "PROVA_SEGURANCA_RESULTADO.md"

PROVAS = ["test_seguranca_estatico.py", "test_seguranca_plano.py"]
ANTIGOS = ["test_api_key.py", "test_autorizacao.py", "test_segredos.py", "test_destino_conexao.py",
           "test_conexoes_escopo.py", "test_conexao_sheets.py", "test_erros_internos.py", "test_limite.py",
           "test_escopo_carteira.py", "test_auditoria_acesso.py", "test_varredura_contas.py",
           "test_agente_manipulacao.py", "test_agente_telegram.py", "test_revisao_api.py"]


def rodar(cmd, cwd, timeout=900):
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        codigo, saida = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        codigo, saida = 124, f"tempo esgotado ({timeout} s)"
    except FileNotFoundError as e:
        codigo, saida = 127, f"comando não encontrado: {e}"
    return codigo, saida, time.monotonic() - t0


def resumo(saida: str) -> str:
    """Linhas ok/FALHA (sem os eventos de log em JSON), para o relatório."""
    linhas = [l for l in saida.splitlines() if l.strip() and not l.lstrip().startswith(("{", "agente_operacional="))]
    return "\n".join(linhas[-400:])


def main():
    tudo = "--tudo" in sys.argv
    py = [sys.executable, "-X", "utf8"]
    etapas = [(f, py + [f], AQUI) for f in PROVAS]
    extras = sorted(p.name for p in AQUI.glob("test_*.py")) if tudo else ANTIGOS
    etapas += [(f, py + [f], AQUI) for f in extras if f not in PROVAS and (AQUI / f).exists()]
    etapas.append(("pip-audit", py + ["-m", "pip_audit", "-r", "requirements.txt"], AQUI))
    npm = shutil.which("npm")
    etapas.append(("npm audit --omit=dev", [npm or "npm", "audit", "--omit=dev"], RAIZ / "frontend"))

    resultados = []
    for nome, cmd, cwd in etapas:
        codigo, saida, dur = rodar(cmd, cwd)
        resultados.append((nome, codigo, saida, dur))
        print(f"{'ok  ' if codigo == 0 else 'FALHA'}  {nome}  ({dur:.0f} s)")

    falhas = [r for r in resultados if r[1] != 0]
    veredito = "APROVADO" if not falhas else "REPROVADO"
    commit = rodar(["git", "rev-parse", "--short", "HEAD"], RAIZ)[1].strip()
    sujo = bool(rodar(["git", "status", "--porcelain"], RAIZ)[1].strip())

    md = [f"# Prova de segurança: {veredito}", "",
          f"- Data: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
          f"- Commit: `{commit}`" + (" (com alterações não commitadas)" if sujo else ""),
          f"- Modo: {'--tudo (todos os test_*.py)' if tudo else 'provas + testes de segurança'}",
          f"- Python {platform.python_version()} em {platform.system()}", "",
          "| Etapa | Resultado | Tempo |", "|---|---|---|"]
    md += [f"| `{n}` | {'ok' if c == 0 else f'**FALHA** (código {c})'} | {d:.0f} s |" for n, c, _, d in resultados]
    if falhas:
        md += ["", "## Falhas", ""] + [f"- `{n}`" for n, *_ in falhas]
    md += ["", "## Saída de cada etapa", ""]
    for n, c, s, _ in resultados:
        md += [f"<details><summary><code>{n}</code>: {'ok' if c == 0 else 'FALHA'}</summary>", "", "```",
               resumo(s), "```", "", "</details>", ""]
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text("\n".join(md), encoding="utf-8")
    print(f"\n{veredito}  ({len(falhas)} etapa(s) com falha)  → {SAIDA.relative_to(RAIZ)}")
    sys.exit(0 if not falhas else 1)


if __name__ == "__main__":
    main()
