"""F3 — painel do operador (docs/PLANO_OPERADOR.md).

Só contagens do que foi registrado: nada estimado, nada projetado.
- contatos: linhas de `contatos` do operador no período;
- contato efetivo: resultado diferente de "sem resposta";
- acordos: promessas de pagamento que ele registrou (tabela `agenda`);
- recebido: pagamentos CONFIRMADOS (feedbacks pagou=true) de devedores sob a
  responsabilidade dele. Promessa não é dinheiro e não entra aqui.
"""
from datetime import date, datetime, time, timedelta, timezone

from agenda import FUSO

PERIODOS = {"hoje": 1, "7d": 7, "30d": 30}


def inicio_do_periodo(periodo: str, hoje: date) -> date:
    if periodo not in PERIODOS:
        raise ValueError("Período inválido. Use: hoje, 7d ou 30d.")
    return hoje - timedelta(days=PERIODOS[periodo] - 1)


def meia_noite_utc(d: date) -> str:
    """00:00 de Brasília do dia `d`, em UTC ISO — o que o banco guarda em created_at."""
    return datetime.combine(d, time(0, 0), tzinfo=FUSO).astimezone(timezone.utc).isoformat()


def _dia_local(created_at) -> "date | None":
    if not created_at:
        return None
    try:
        t = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(FUSO).date()


def resumir(contatos: list, promessas: list, pagamentos: list, hoje: date, meta_dia: "int | None") -> dict:
    """Números de UM operador. As listas já vêm recortadas no período."""
    n = len(contatos)
    efetivos = sum(1 for c in contatos if c.get("resultado") and c.get("resultado") != "sem_resposta")
    hoje_n = sum(1 for c in contatos if _dia_local(c.get("created_at")) == hoje)
    sit = [p.get("situacao") for p in promessas]
    return {
        "contatos": n,
        "contatos_efetivos": efetivos,
        "taxa_contato_efetivo": round(efetivos / n, 4) if n else None,
        "contatos_hoje": hoje_n,
        "acordos": len(promessas),
        "acordos_valor": round(sum(float(p.get("valor") or 0) for p in promessas), 2),
        "promessas_cumpridas": sit.count("cumprida"),
        "promessas_quebradas": sit.count("quebrada"),
        "promessas_pendentes": sit.count("pendente"),
        "pagamentos": len(pagamentos),
        "recebido": round(sum(float(p.get("valor_recuperado") or 0) for p in pagamentos), 2),
        "meta_dia": meta_dia,
        "meta_pct": round(hoje_n / meta_dia, 4) if meta_dia else None,
    }
