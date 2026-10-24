"""Registro operacional seguro dos agentes.

Este módulo registra somente o contexto técnico necessário para operar o
sistema. Mensagens, nomes, documentos e qualquer outro dado do devedor não
entram no log. A gravação no banco é deliberadamente "best effort": se a
observabilidade estiver indisponível, o atendimento continua e o evento ainda
fica no log estruturado do servidor.
"""
import json
import logging
from datetime import datetime, timezone


LOGGER = logging.getLogger("mizan.agentes")

NIVEIS = {"aviso", "erro", "critico"}
_CATEGORIAS = {
    "no_falhou": "Uma etapa do agente falhou",
    "ia_reserva": "A IA falhou e o caminho seguro em código foi usado",
    "ia_aguardando": "A IA está ocupada; o evento foi adiado",
    "teto_ia": "O teto diário da IA foi atingido; o evento foi adiado",
    "falha_final": "O agente não concluiu a etapa e o caso precisa de equipe",
    "encaminhado_equipe": "O caso foi encaminhado para atendimento humano",
    "evento_retentativa": "O evento falhou fora do fluxo e será tentado novamente",
    "evento_falhou": "O evento falhou definitivamente",
    "reservas_vencidas": "Eventos presos foram devolvidos à fila",
    "observabilidade_indisponivel": "Não foi possível gravar um log operacional",
}
_CHAVES_SEGURAS = {"no", "erro", "evento_tipo", "tentativa", "esperar_s", "vez", "quantidade"}


def _seguro(detalhe: dict | None) -> dict:
    """Permite apenas chaves técnicas e valores curtos, sem texto do atendimento."""
    saida = {}
    for chave, valor in (detalhe or {}).items():
        if chave not in _CHAVES_SEGURAS or valor is None:
            continue
        if isinstance(valor, (int, float, bool)):
            saida[chave] = valor
        elif isinstance(valor, str):
            # Os valores permitidos são nomes de nó/classe/tipo de evento.
            saida[chave] = valor[:120]
    return saida


def registrar(repo, *, empresa_id: str, nivel: str, categoria: str, agente: str = "orquestrador",
              evento_id=None, caso_id=None, trace_id=None, tentativa=None, detalhe: dict | None = None) -> dict:
    """Emite log estruturado e tenta persistir sem afetar o atendimento."""
    linha = {
        "empresa_id": empresa_id,
        "nivel": nivel if nivel in NIVEIS else "erro",
        "categoria": categoria,
        "mensagem": _CATEGORIAS.get(categoria, "Ocorrência operacional do agente"),
        "agente": agente or "orquestrador",
        "evento_id": evento_id,
        "caso_id": caso_id,
        "trace_id": trace_id,
        "tentativa": tentativa,
        "detalhe": _seguro(detalhe),
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }
    # JSON permite alertas e busca no provedor sem depender do banco.
    LOGGER.warning("agente_operacional=%s", json.dumps(linha, ensure_ascii=False, default=str))
    try:
        repo.gravar_log_agente(linha)
    except Exception as erro:
        # Não registre o erro remoto em detalhe: respostas de provedores podem conter texto externo.
        LOGGER.error("agente_log_persistencia_falhou tipo=%s", type(erro).__name__)
    return linha
