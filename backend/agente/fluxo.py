"""Leitura do andamento do devedor, sem alterar decisões ou situações dos agentes.

Pagamento em andamento exige um pagamento confirmado pelo Acompanhamento.
Uma informação do devedor em conferência não vale como confirmação.
"""
from math import isfinite
from datetime import datetime, timezone

FASES = (
    ("nao_iniciado", "Não iniciado"),
    ("contactado", "Contactado"),
    ("negociando", "Negociando"),
    ("acordo", "Acordo"),
    ("pagamento", "Pagamento em andamento"),
)
AVISOS = {
    "quitado": ("sucesso", "Quitado"),
    "atrasado": ("atencao", "Pagamento em atraso"),
    "quebrado": ("atencao", "Acordo quebrado"),
    "pagamento_em_conferencia": ("informacao", "Pagamento aguardando conferência"),
    "contestado": ("atencao", "Dívida contestada"),
    "suspenso": ("informacao", "Contato suspenso"),
    "com_pessoa": ("informacao", "Atendimento com a equipe"),
}
DESCRICOES = {
    "nao_iniciado": "Nenhum contato iniciado foi registrado pelos agentes.",
    "contactado": "O caso está em contato com o devedor.",
    "negociando": "O caso está em negociação.",
    "acordo": "Há um acordo registrado. O primeiro pagamento ainda não foi confirmado pelo Acompanhamento.",
    "pagamento": "O Acompanhamento registrou pelo menos um pagamento confirmado.",
}


def _positivo(valor):
    if isinstance(valor, bool):
        return False
    try:
        numero = float(valor)
        return isfinite(numero) and numero > 0
    except (TypeError, ValueError):
        return False


def para_tela(caso, houve_contato=False):
    dados = (caso or {}).get("dados") or {}
    situacao = (caso or {}).get("situacao")
    pagamentos = [p for p in dados.get("pagamentos") or []
                  if isinstance(p, dict) and _positivo(p.get("valor"))]
    acordo = bool(dados.get("acordo"))
    # A situação atual prevalece numa nova rodada de contato/negociação.
    fase = {"novo": "nao_iniciado", "em_contato": "contactado", "negociando": "negociando"}.get(situacao)
    if caso is None:
        fase = "nao_iniciado"
    elif fase is None:
        if pagamentos:
            fase = "pagamento"
        elif acordo or situacao == "acordo_ativo":
            fase = "acordo"
        elif houve_contato:
            fase = "contactado"
        elif situacao == "so_lembrete":
            fase = "nao_iniciado"  # planejamento de lembrete não prova contato
    aviso = AVISOS.get(situacao)
    return {
        "fase_atual": fase,
        "fases": [{"id": id_, "nome": nome} for id_, nome in FASES],
        "descricao": DESCRICOES.get(fase, "Os registros disponíveis ainda não identificam a fase deste caso."),
        "aviso": {"tipo": aviso[0], "texto": aviso[1]} if aviso else None,
        "situacao": situacao,
        "atualizado_em": (caso or {}).get("atualizado_em"),
        "pagamentos_confirmados": len(pagamentos),
    }


def carregar_registros(db, empresa, pred, falta_tabela=None):
    """Histórico da operação; nenhuma consulta usa CPF sem empresa."""
    indisponiveis = []
    def ler(query, tabela):
        try:
            return query.execute().data or []
        except Exception as e:
            if falta_tabela and falta_tabela(e, tabela):
                indisponiveis.append(tabela)
                return []
            raise
    contatos = ler(db.table('contatos').select('resultado, created_at, usuario_id')
                .eq('empresa_id', empresa).eq('cpf', pred['cpf'])
                .in_('resultado', ['contactado', 'prometeu_pagar', 'nao_quis', 'pagou'])
                .order('created_at', desc=True).limit(100), 'contatos')
    ofertas = ler(db.table('ofertas_feitas').select('resposta, created_at, operador_id')
               .eq('empresa_id', empresa).eq('predicao_id', pred['id'])
               .order('created_at', desc=True).limit(100), 'ofertas_feitas')
    feedbacks = ler(db.table('feedbacks').select('*').eq('empresa', empresa)
                 .eq('predicao_id', pred['id']).order('created_at', desc=True).limit(1), 'feedbacks')
    parcelas = ler(db.table('acordo_parcelas').select('*').eq('empresa_id', empresa)
                .eq('predicao_id', pred['id']).order('created_at', desc=True).limit(1000), 'acordo_parcelas')
    humanos = lambda linhas, campo: [l for l in linhas if l.get(campo) not in ('agente-mizan', 'a-definir')]
    return {'contatos': humanos(contatos, 'usuario_id'), 'ofertas': humanos(ofertas, 'operador_id'),
            'feedbacks': feedbacks, 'parcelas': parcelas, 'indisponiveis': indisponiveis}


def _quando(v):
    try:
        d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace('Z', '+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    except (TypeError, ValueError):
        return None


def operacao_para_tela(registros, hoje=None):
    """Fatos manuais: promessa não é acordo; pagamento exige baixa confirmada."""
    from agenda import hoje as dia_atual
    from acordos import situacao as situacao_acordo
    hoje = hoje or dia_atual()
    candidatos, avisos = [], []
    pagos = 0
    for c in registros.get('contatos') or []:
        if c.get('resultado') in ('contactado', 'nao_quis', 'pagou', 'prometeu_pagar'):
            candidatos.append(('negociando' if c['resultado'] == 'prometeu_pagar' else 'contactado', c.get('created_at')))
    ofertas = registros.get('ofertas') or []
    if ofertas:
        o = max(ofertas, key=lambda o: _quando(o.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc))
        candidatos.append(('acordo' if o.get('resposta') == 'aceitou' else 'negociando', o.get('created_at')))
    parcelas = registros.get('parcelas') or []
    if parcelas:
        recente = max(parcelas, key=lambda p: _quando(p.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc))
        grupo = [p for p in parcelas if p.get('feedback_id') == recente.get('feedback_id')]
        pagas = [p for p in grupo if p.get('situacao') == 'paga' and _positivo(p.get('valor'))]
        pagos = len(pagas)
        candidatos.append(('pagamento' if pagas else 'acordo',
                           max((p.get('pago_em') or p.get('created_at') or '' for p in grupo), key=lambda v: _quando(v) or datetime.min.replace(tzinfo=timezone.utc))))
        # Uma página incompleta não pode declarar um acordo quitado.
        if len(grupo) == int(recente.get('total') or 0):
            sit = situacao_acordo(grupo, hoje)['situacao']
            if sit in AVISOS:
                tipo, texto = AVISOS[sit]
                avisos.append({'tipo': tipo, 'texto': texto})
    feedbacks = registros.get('feedbacks') or []
    if feedbacks:
        fb = max(feedbacks, key=lambda f: _quando(f.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc))
        if fb.get('pagou') is True and _positivo(fb.get('valor_recuperado')):
            pagos = max(pagos, 1)
            candidatos.append(('pagamento', fb.get('created_at')))
            if fb.get('forma_pagamento') == 'a_vista' or fb.get('parcelas') == 1:
                avisos.append({'tipo': 'sucesso', 'texto': 'Quitado'})
    ordem = {id_: i for i, (id_, _) in enumerate(FASES)}
    fase, em = max(candidatos, key=lambda c: (ordem[c[0]], _quando(c[1]) or datetime.min.replace(tzinfo=timezone.utc))) if candidatos else (None, None)
    return {'fase_atual': fase, 'atualizado_em': em, 'pagamentos_confirmados': pagos, 'avisos': avisos}


def unificar(caso, houve_contato=False, registros=None, hoje=None):
    agente = para_tela(caso, houve_contato)
    manual = operacao_para_tela(registros or {}, hoje)
    a, m = agente['fase_atual'], manual['fase_atual']
    fase, conflito = a, False
    if m:
        if not a or a == 'nao_iniciado':
            fase = m
        elif a != m:
            ordem = {id_: i for i, (id_, _) in enumerate(FASES)}
            da, dm = _quando(agente['atualizado_em']), _quando(manual['atualizado_em'])
            if da and dm and ordem[m] >= ordem[a] and dm >= da:
                fase = m
            elif not (da and dm and ordem[a] >= ordem[m] and da >= dm):
                fase, conflito = None, True
    pode_pagamento = max(agente['pagamentos_confirmados'], manual['pagamentos_confirmados']) > 0
    decisao = ((caso or {}).get('dados') or {}).get('fluxo_manual')
    if decisao and decisao.get('fase') in dict(FASES):
        if decisao['fase'] != 'pagamento' or pode_pagamento:
            fase = decisao['fase']
        else:
            decisao = None  # baixa corrigida: não conserva uma confirmação sem lastro
    avisos = ([agente['aviso']] if agente['aviso'] else []) + manual['avisos']
    if conflito and not decisao:
        avisos.append({'tipo': 'atencao', 'texto': 'Os registros indicam fases diferentes. O operador deve definir a fase atual.'})
    if (registros or {}).get('indisponiveis'):
        avisos.append({'tipo': 'atencao', 'texto': 'Histórico da operação incompleto: alguns registros ainda não estão disponíveis.'})
        if fase == 'nao_iniciado' and not decisao:
            fase = None
    avisos = list({(v['tipo'], v['texto']): v for v in avisos}.values())
    if decisao:
        descricao = 'Fase definida pelo operador. Os avisos e os pagamentos continuam vinculados aos registros reais.'
    elif m and fase == m:
        descricao = {'contactado': 'Há contato com resposta registrado pela operação.',
                     'negociando': 'Há negociação ou promessa registrada, sem uma oferta aceita que confirme o acordo.',
                     'acordo': 'Há oferta aceita ou acordo registrado. O primeiro pagamento ainda não foi confirmado.',
                     'pagamento': 'Há pagamento confirmado nos registros da operação.'}[m]
    else:
        descricao = agente['descricao'] if fase else 'Confira os registros das duas fontes e defina a fase do devedor.'
    datas = [d for d in (_quando(agente['atualizado_em']), _quando(manual['atualizado_em'])) if d]
    return {**agente, 'fase_atual': fase, 'descricao': descricao, 'avisos': avisos,
            'aviso': avisos[0] if avisos else None, 'manual': decisao, 'conflito': conflito,
            'pode_marcar_pagamento': pode_pagamento, 'fontes': {'agentes': a, 'operacao': m},
            'atualizado_em': max(datas).isoformat() if datas else None}
