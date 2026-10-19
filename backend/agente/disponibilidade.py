"""Próximo horário real de um operador, para a mensagem de handoff
(docs/PLANO_DISPONIBILIDADE_OPERADOR.md).

Código, não IA: o nome e o horário que vão para o devedor sempre saem daqui,
nunca de texto gerado. Sem nenhum operador com disponibilidade cadastrada,
`proximo_atendimento` devolve None e quem chamou usa a mensagem genérica —
não falta disponibilidade cadastrada não pode quebrar o handoff.
"""
from datetime import timedelta

from agente.auditor import BRASILIA

DIAS_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

MAX_DIAS_A_FRENTE = 14          # não passa disso procurando faixa livre


def proximo_atendimento(fonte, empresa_id: str, agora) -> dict | None:
    """{"usuario_id", "nome", "dia" (ISO), "dia_semana", "hora_inicio"} do primeiro
    operador ativo da empresa com disponibilidade cadastrada a partir de `agora`,
    ou None se ninguém tem disponibilidade (ou a empresa não tem operador)."""
    try:
        operadores = {o["id"]: o.get("nome") or "" for o in fonte.operadores(empresa_id)}
        faixas = [f for f in fonte.disponibilidade_operador(empresa_id) if f.get("ativo", True)]
    except Exception:
        return None
    faixas = [f for f in faixas if f.get("usuario_id") in operadores]
    if not faixas or not operadores:
        return None

    local = agora.astimezone(BRASILIA)
    for i in range(MAX_DIAS_A_FRENTE + 1):
        dia = (local + timedelta(days=i)).date()
        dia_semana = dia.weekday()
        candidatas = [f for f in faixas if int(f["dia_semana"]) == dia_semana]
        if i == 0:
            # Hoje: só conta o que ainda não começou (faixa que já passou não serve).
            candidatas = [f for f in candidatas if int(f["hora_inicio"]) > local.hour]
        if not candidatas:
            continue
        escolhida = min(candidatas, key=lambda f: int(f["hora_inicio"]))
        return {"usuario_id": escolhida["usuario_id"], "nome": operadores.get(escolhida["usuario_id"], ""),
                "dia": dia.isoformat(), "dia_semana": dia_semana, "hora_inicio": int(escolhida["hora_inicio"])}
    return None
