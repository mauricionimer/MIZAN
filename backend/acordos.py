"""A4 — acordos em andamento (docs/PLANO_ADMIN.md).

Pagamento confirmado com N > 1 parcelas abre um acordo: a 1ª parcela é o que
acabou de entrar; as demais vencem todo mês no mesmo dia, com o mesmo valor.
Aqui ficam só as regras (datas e situação); o banco fica em main.py.
"""
import calendar
from datetime import date

# Escolha de projeto, escrita na ajuda: parcela em aberto há mais de 30 dias
# quebra o acordo (é o atraso em que a cobrança volta à estaca zero).
DIAS_QUEBRA = 30
SITUACOES = ("em_dia", "atrasado", "quebrado", "quitado")


def somar_meses(d: date, meses: int) -> date:
    """Mesmo dia `meses` depois; dia 31 vira o último dia do mês curto."""
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def vencimentos(primeira: date, total: int) -> list:
    return [somar_meses(primeira, i) for i in range(total)]


def situacao(parcelas: list, hoje: date) -> dict:
    """Situação de UM acordo a partir das parcelas dele.

    Cada parcela: {"vencimento": date|str, "situacao": "pendente"|"paga", "valor": n}.
    """
    def dia(v):
        return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])
    abertas = [p for p in parcelas if p.get("situacao") != "paga"]
    vencidas = [p for p in abertas if dia(p["vencimento"]) < hoje]
    atraso = max(((hoje - dia(p["vencimento"])).days for p in vencidas), default=0)
    if not abertas:
        estado = "quitado"
    elif atraso > DIAS_QUEBRA:
        estado = "quebrado"
    elif vencidas:
        estado = "atrasado"
    else:
        estado = "em_dia"
    proxima = min((dia(p["vencimento"]) for p in abertas), default=None)
    return {
        "situacao": estado,
        "dias_atraso": atraso,
        "pagas": len(parcelas) - len(abertas),
        "total": len(parcelas),
        "valor_pago": round(sum(float(p.get("valor") or 0) for p in parcelas if p.get("situacao") == "paga"), 2),
        "valor_aberto": round(sum(float(p.get("valor") or 0) for p in abertas), 2),
        "valor_vencido": round(sum(float(p.get("valor") or 0) for p in vencidas), 2),
        "proximo_vencimento": proxima.isoformat() if proxima else None,
    }
