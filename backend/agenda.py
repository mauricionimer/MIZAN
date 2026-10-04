"""F2 — agenda de retornos e promessas (docs/PLANO_OPERADOR.md).

Regras puras, sem banco: o nível de aviso de cada compromisso e o "hoje" da
operação. O "hoje" é o de Brasília, não o do servidor (o Render roda em UTC:
às 22h de Goiânia já seria amanhã e uma promessa de hoje viraria "vencida").
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")

TIPOS = ("promessa", "retorno")
SITUACOES = ("pendente", "cumprida", "quebrada", "cancelada")
NIVEIS = ("alto", "medio", "safe")

# Quanto à frente se pode agendar. Um ano cobre acordo de fim de safra; mais
# que isso é quase sempre data digitada errado (2062 em vez de 2026).
DIAS_MAXIMOS_A_FRENTE = 365


def hoje() -> date:
    return datetime.now(FUSO).date()


def nivel(data_compromisso: date, referencia: date | None = None) -> str:
    """Alto: já passou e segue pendente. Médio: hoje ou amanhã. Safe: 2 dias ou mais."""
    ref = referencia or hoje()
    if data_compromisso < ref:
        return "alto"
    if data_compromisso <= ref + timedelta(days=1):
        return "medio"
    return "safe"


def contar_niveis(datas: list, referencia: date | None = None) -> dict:
    ref = referencia or hoje()
    saida = {n: 0 for n in NIVEIS}
    for d in datas:
        saida[nivel(d, ref)] += 1
    return saida


def validar_data_nova(d: date, referencia: date | None = None) -> None:
    """Compromisso novo (ou remarcado) não nasce no passado nem longe demais."""
    ref = referencia or hoje()
    if d < ref:
        raise ValueError("A data não pode estar no passado.")
    if d > ref + timedelta(days=DIAS_MAXIMOS_A_FRENTE):
        raise ValueError(f"A data passa de {DIAS_MAXIMOS_A_FRENTE} dias: confira o ano.")
