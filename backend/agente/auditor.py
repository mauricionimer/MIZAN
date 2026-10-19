"""Auditor (docs/PLANO_AGENTE.md, 3.3; docs/PLANO_EXECUCAO_AGENTES.md, 8).

Código, não IA, e com a palavra final. Toda ação que um agente quer fazer passa
por aqui antes de executar. A resposta diz se pode, qual regra decidiu e qual
versão da política estava valendo — é isso que vai para o rastreio.

Regras de projeto:
- Ação desconhecida é bloqueada (lista do que pode, não do que não pode).
- Sem política ativa, só as ações de segurança passam.
- Ações de segurança (parar contato, contestação, chamar uma pessoa) nunca são
  bloqueadas: quem pede para parar não pode esbarrar em regra nenhuma.
- As contas de acordo são as mesmas do simulador (model/oferta.py).
"""
from datetime import date, datetime, timedelta, timezone

from agente import estado
from model import oferta

# Valores FICTÍCIOS, só para a demonstração do AKCIT Camp. Não são recomendação;
# cada banco define os seus.
POLITICA_DEMONSTRACAO = {
    "desconto_max_pct": 30.0,
    "parcelas_max": 12,
    "parcela_min": 50.0,
    "entrada_min_pct": 10.0,          # só em acordo parcelado
    "hora_inicio": 8,
    "hora_fim": 20,                   # até 19:59
    "dias_semana": [0, 1, 2, 3, 4, 5],  # segunda a sábado (0 = segunda)
    "contatos_semana_max": 3,
    "prazo_max_dias": 30,             # data de promessa ou retorno até 30 dias à frente
    "remarcacoes_max": 2,             # vezes que o agente pode remarcar um compromisso
    "prazo_confirmacao_dias": 2,      # dias úteis que o banco leva para confirmar um pagamento
    "dias_sem_resposta": 3,           # dias úteis de espera da resposta depois de cobrar o atraso
    "percentual_controle": 10,        # parte da carteira sorteada que segue sem o agente
}

# Horário de Brasília. Sem horário de verão desde 2019; fuso fixo evita
# depender da base de fusos do servidor.
BRASILIA = timezone(timedelta(hours=-3))

_LIMITES = {                          # campo: (mínimo, máximo)
    "desconto_max_pct": (0.0, 95.0),
    "parcelas_max": (1, 120),
    "parcela_min": (0.0, 1_000_000.0),
    "entrada_min_pct": (0.0, 90.0),
    "hora_inicio": (0, 23),
    "hora_fim": (1, 24),
    "contatos_semana_max": (0, 50),
    "prazo_max_dias": (1, 180),
    "remarcacoes_max": (0, 10),
    "prazo_confirmacao_dias": (0, 15),
    "dias_sem_resposta": (1, 30),
    "percentual_controle": (0, 50),
}

# "Já paguei" também é segurança: suspende a cobrança enquanto o banco confere.
# "enviar_mensagem_seguranca" é a mensagem fixa de handoff/segurança (com_pessoa,
# parar, pessoa_errada, contestado, apoio): quem pediu ajuda ou já teve a
# cobrança suspensa/contestada/transferida precisa ouvir essa confirmação
# mesmo que o devedor já tenha batido o limite semanal de contatos ou esteja
# fora do horário comercial (R2_HORARIO e R3_FREQUENCIA existem para a
# cobrança ativa, não para avisar que uma pessoa assumiu).
SEGURANCA = frozenset({"suspender_contato", "registrar_contestacao", "transferir_para_pessoa",
                       "registrar_pagamento_informado", "enviar_mensagem_seguranca"})
FALA = frozenset({"enviar_mensagem"})          # o agente procura o devedor
RESPOSTA = frozenset({"responder_mensagem"})   # o devedor escreveu e o agente responde
ACORDO = frozenset({"propor_acordo", "registrar_aceite"})
COMPROMISSO = frozenset({"agendar_retorno", "remarcar_compromisso", "marcar_atendimento"})
REGISTRO = frozenset({"registrar_contato", "marcar_promessa_quebrada"})
LEITURA = frozenset({"consultar_caso", "verificar_identidade", "listar_ofertas", "simular_acordo",
                     "consultar_politica", "consultar_base"})


def validar_politica(bruto: dict) -> dict:
    """Política limpa e dentro dos limites; levanta ValueError com o motivo."""
    if not isinstance(bruto, dict):
        raise ValueError("política em formato inválido")
    saida = {}
    for campo, (lo, hi) in _LIMITES.items():
        if campo not in bruto:
            raise ValueError(f"falta {campo}")
        v = bruto[campo]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{campo}: informe um número")
        if not lo <= v <= hi:
            raise ValueError(f"{campo}: de {lo:g} a {hi:g}")
        saida[campo] = int(v) if isinstance(lo, int) else float(v)
    if saida["hora_inicio"] >= saida["hora_fim"]:
        raise ValueError("o horário de início precisa ser antes do fim")
    dias = bruto.get("dias_semana")
    if not isinstance(dias, list) or not dias or any(d not in range(7) for d in dias):
        raise ValueError("dias_semana: lista com números de 0 (segunda) a 6 (domingo)")
    saida["dias_semana"] = sorted(set(dias))
    return saida


def _decisao(permitida: bool, regra: str, motivo: str, versao) -> dict:
    return {"permitida": permitida, "regra": regra, "motivo": motivo, "versao_politica": versao}


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _conferir_data(valor, politica: dict, agora: datetime, versao, aceita_hoje: bool = False) -> dict | None:
    """Data de promessa ou retorno: depois de hoje e dentro do prazo máximo.
    No aceite do acordo, hoje também vale ("pago hoje no pix")."""
    try:
        data = date.fromisoformat(str(valor))
    except ValueError:
        return _decisao(False, "R11_DATA", "data inválida", versao)
    hoje = agora.astimezone(BRASILIA).date()
    if data < hoje or (data == hoje and not aceita_hoje):
        return _decisao(False, "R11_DATA", "a data precisa ser a partir de hoje" if aceita_hoje
                        else "a data precisa ser depois de hoje", versao)
    if data > hoje + timedelta(days=politica["prazo_max_dias"]):
        return _decisao(False, "R11_DATA", f"data além de {politica['prazo_max_dias']} dias", versao)
    return None


def _conferir_hora(data_txt, hora, politica: dict, versao) -> dict | None:
    """Hora combinada: dentro da janela de contato, em dia de contato."""
    if not hora:
        return None
    try:
        h, m = (int(x) for x in str(hora).split(":"))
        dia = date.fromisoformat(str(data_txt))
    except ValueError:
        return _decisao(False, "R2_HORARIO", "hora inválida", versao)
    if dia.weekday() not in politica["dias_semana"]:
        return _decisao(False, "R2_HORARIO", "dia da semana fora da política", versao)
    if not (politica["hora_inicio"] <= h < politica["hora_fim"]) or not 0 <= m < 60:
        return _decisao(False, "R2_HORARIO",
                        f"fora do horário ({politica['hora_inicio']}h às {politica['hora_fim']}h)", versao)
    return None


def auditar(acao: dict, caso: dict, politica: dict | None, versao: int | None,
            agora: datetime, contatos_7d: int = 0, simulacao: dict | None = None, ironia: bool = False) -> dict:
    """Decide se a ação pode ser executada.

    acao        : {"tipo": str, "params": dict}
    caso        : o caso (usa "situacao" e "dados.divida")
    politica    : regras validadas ou None se a empresa não tem política ativa
    contatos_7d : mensagens enviadas a este devedor nos últimos 7 dias
    simulacao   : a simulação a que o aceite se refere, como o sistema a gravou
    """
    tipo = (acao or {}).get("tipo")
    params = (acao or {}).get("params") or {}

    if tipo in SEGURANCA:
        return _decisao(True, "R9_SEGURANCA", "ação de segurança sempre permitida", versao)
    if tipo in LEITURA:
        return _decisao(True, "R0_LEITURA", "só consulta, não muda nada", versao)
    if tipo not in FALA | RESPOSTA | ACORDO | COMPROMISSO | REGISTRO:
        return _decisao(False, "R0_ACAO_DESCONHECIDA", f"ação não prevista: {tipo}", versao)
    if politica is None:
        return _decisao(False, "R0_SEM_POLITICA", "a empresa não tem política ativa", versao)

    if not estado.pode_falar(caso.get("situacao", "")):
        return _decisao(False, "R1_SITUACAO",
                        f"o caso está em '{caso.get('situacao')}': o agente não fala com o devedor", versao)

    if tipo in RESPOSTA:
        # Responder a quem escreveu não é contato novo: vale a qualquer hora e
        # não conta na frequência. Só a situação do caso importa.
        return _decisao(True, "OK", "resposta a mensagem do devedor", versao)

    if tipo in REGISTRO:
        return _decisao(True, "OK", "registro do que aconteceu", versao)

    if tipo in COMPROMISSO:
        ruim = (_conferir_data(params.get("data"), politica, agora, versao)
                or _conferir_hora(params.get("data"), params.get("hora"), politica, versao))
        if ruim:
            return ruim
        if tipo == "remarcar_compromisso":
            feitas = int((caso.get("dados") or {}).get("remarcacoes") or 0)
            if feitas >= politica["remarcacoes_max"]:
                return _decisao(False, "R12_REMARCACOES",
                                f"já foram {feitas} remarcações (máximo {politica['remarcacoes_max']})", versao)
        return _decisao(True, "OK", "data dentro da política", versao)

    if tipo in FALA:
        local = agora.astimezone(BRASILIA)
        if local.weekday() not in politica["dias_semana"]:
            return _decisao(False, "R2_HORARIO", "dia da semana fora da política", versao)
        if not politica["hora_inicio"] <= local.hour < politica["hora_fim"]:
            return _decisao(False, "R2_HORARIO",
                            f"fora do horário ({politica['hora_inicio']}h às {politica['hora_fim']}h)", versao)
        if contatos_7d >= politica["contatos_semana_max"]:
            return _decisao(False, "R3_FREQUENCIA",
                            f"já foram {contatos_7d} contatos em 7 dias (máximo {politica['contatos_semana_max']})", versao)
        return _decisao(True, "OK", "dentro do horário e da frequência", versao)

    # Acordo: só depois de confirmar que é o titular, e com as contas do simulador.
    if not (caso.get("dados") or {}).get("identidade_ok"):
        return _decisao(False, "R10_IDENTIDADE", "identidade do devedor não confirmada", versao)
    if tipo == "registrar_aceite" and ironia:
        # "Ah claro, aceito, com o dinheiro que eu não tenho": a Triagem viu ironia
        # nesta mensagem. Aceite só com confirmação clara numa mensagem seguinte.
        return _decisao(False, "R13_IRONIA", "a mensagem parece irônica: confirme o aceite antes de registrar", versao)
    try:
        cond = oferta.condicoes(params)
    except ValueError as e:
        return _decisao(False, "R4_CONDICOES", str(e), versao)
    divida = float((caso.get("dados") or {}).get("divida") or 0)
    if divida <= 0:
        return _decisao(False, "R4_CONDICOES", "caso sem valor de dívida", versao)
    conta = oferta.calcular(divida, **cond)
    if cond["desconto_pct"] > politica["desconto_max_pct"]:
        return _decisao(False, "R4_DESCONTO", f"desconto acima do máximo de {politica['desconto_max_pct']:g}%", versao)
    if cond["n_parcelas"] > politica["parcelas_max"]:
        return _decisao(False, "R5_PARCELAS", f"mais parcelas que o máximo de {politica['parcelas_max']}", versao)
    if cond["n_parcelas"] > 1 and conta["parcela"] < politica["parcela_min"]:
        return _decisao(False, "R6_PARCELA_MIN", f"parcela abaixo do mínimo de {_brl(politica['parcela_min'])}", versao)
    if cond["n_parcelas"] > 1 and cond["entrada_pct"] < politica["entrada_min_pct"]:
        return _decisao(False, "R7_ENTRADA_MIN", f"entrada abaixo do mínimo de {politica['entrada_min_pct']:g}%", versao)

    if tipo == "registrar_aceite":
        # O aceite só vale para uma simulação que o próprio sistema fez, ainda
        # válida e com as mesmas condições: nenhum valor vem do texto da IA.
        if not simulacao or simulacao.get("id") != params.get("simulacao_id"):
            return _decisao(False, "R8_SIMULACAO", "aceite sem simulação do sistema", versao)
        if simulacao.get("caso_id") != caso.get("id"):
            return _decisao(False, "R8_SIMULACAO", "simulação de outro caso", versao)
        if agora >= simulacao["valida_ate"]:
            return _decisao(False, "R8_SIMULACAO", "simulação vencida", versao)
        if oferta.condicoes(simulacao.get("condicoes") or {}) != cond:
            return _decisao(False, "R8_SIMULACAO", "condições diferentes das simuladas", versao)
        ruim = _conferir_data(params.get("data"), politica, agora, versao, aceita_hoje=True)
        if ruim:
            return ruim
    return _decisao(True, "OK", "dentro da política", versao)
