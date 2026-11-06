"""Notificações para administradores e operadores (docs/NOTIFICACOES.md).

Uma linha por pessoa que recebe, na tabela `notificacoes`
(backend/sql/migracao_notificacoes.sql). Quem chama só diz o que aconteceu:

    notificacoes.notificar("N06", empresa_id, devedor=dev, admins=True,
                           contexto={"nome": dev["nome"], "quando": "07/11 às 14:30"},
                           chave=f"N06:{item_id}", entidade=("agenda", item_id))

O catálogo diz o texto, a prioridade e para onde o clique leva. O destino segue a
regra do plano: o responsável pelo devedor; sem responsável (ou com o agente), os
administradores da empresa. Quem fez a ação não recebe.

Notificar nunca atrapalha o atendimento:
- a gravação vai para uma fila com uma linha de execução só, fora da conversa (e,
  em ordem, nunca grava duas coisas ao mesmo tempo neste servidor);
- nunca levanta erro; um disjuntor para por 2 minutos depois de 3 falhas seguidas;
- MIZAN_NOTIFICACOES=0 desliga tudo.

Privacidade: no texto, só o primeiro nome do devedor; nunca CPF, valor ou texto da
conversa. Fora do Mizan (navegador, e-mail) vai só o título genérico do tipo.
"""
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone

from agente import mudancas

BRASILIA = timezone(timedelta(hours=-3))
AGENTE = "agente-mizan"
A_DEFINIR = "a-definir"
DONOS_QUE_NAO_SAO_PESSOAS = (AGENTE, A_DEFINIR)

CATEGORIAS = ("conversas", "reunioes", "retornos", "pedidos", "equipe", "sistema")
ROTULO_CATEGORIA = {"conversas": "Conversas", "reunioes": "Reuniões", "retornos": "Retornos e pagamentos",
                    "pedidos": "Pedidos e LGPD", "equipe": "Equipe", "sistema": "Sistema"}
PRIORIDADES = ("urgente", "alta", "normal")

# Observações que o agente escreve na agenda (agente/ferramentas.py, grafos.py).
PREFIXO_ATENDIMENTO = "Atendimento com pessoa pedido pelo devedor"
PREFIXO_TRANSFERENCIA = "Transferido pelo assistente"
PREFIXO_MENSAGEM = "Nova mensagem do devedor"
PREFIXO_PEDIDO = "Pedido sobre os dados pessoais"
PREFIXO_PAGAMENTO_INFORMADO = "Devedor informa pagamento"
PREFIXO_ACORDO = "Acordo pelo assistente"
PREFIXO_RETORNO_ASSISTENTE = ("Retorno combinado pelo assistente", "Remarcado pelo assistente")

PADRAO_PREFERENCIAS = {"navegador": False, "email_resumo": False, "silencio_ligado": True,
                       "silencio_inicio": 20, "silencio_fim": 8, "desligadas": []}

ESCALAR_APOS = timedelta(minutes=15)
LIMITE_TITULO, LIMITE_TEXTO = 120, 300


# ── catálogo ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Tipo:
    codigo: str
    categoria: str
    prioridade: str
    titulo: str
    texto: str = ""
    externo: str = "Aviso novo no Mizan"      # fora do Mizan: nunca nome, CPF ou valor
    acao: str = "Abrir"
    link: str = "/agenda"
    modo: str = "unico"                      # unico: a chave nunca sai duas vezes; agrupar: soma enquanto aberta
    titulo_grupo: str = ""                   # quando há mais de um ({n})
    texto_grupo: str = ""
    link_grupo: str = ""
    por_papel: dict = field(default_factory=dict)    # "operador"/"admin" -> campos que mudam
    variantes: dict = field(default_factory=dict)    # contexto["variante"] -> campos que mudam


_CONVERSA = "/pasta/{predicao_id}?aba=conversa"
_RESUMO = "/pasta/{predicao_id}?aba=resumo"
_ACORDO = "/pasta/{predicao_id}?aba=acordo"
_APROVAR = "/agente?aba=agenda"

CATALOGO = {t.codigo: t for t in (
    # ── conversas ──
    Tipo("N01", "conversas", "alta", "{nome} escreveu de novo",
         "O caso está {situacao}. Responda pela conversa.",
         externo="Mensagem nova de um cliente", acao="Abrir conversa", link=_CONVERSA, modo="agrupar",
         titulo_grupo="{nome} mandou {n} mensagens"),
    Tipo("N02", "conversas", "alta", "{nome} foi passado para a equipe",
         "Motivo: {motivo}. Leia o resumo antes de responder.",
         externo="Caso passado para a equipe", acao="Ler resumo", link=_RESUMO),
    Tipo("N03", "conversas", "urgente", "Atenção: {nome} mostrou sinais de sofrimento grave",
         "Atender com prioridade, para acolher, não para cobrar. A cobrança deste caso parou.",
         externo="Atendimento urgente", acao="Abrir conversa", link=_CONVERSA),
    Tipo("N04", "conversas", "alta", "O link do Telegram de {nome} foi aberto em outro aparelho",
         "O Mizan não ligou esse aparelho. Se não foi a própria pessoa, gere um link novo na pasta.",
         externo="Tentativa de uso de um link do Telegram", acao="Abrir pasta", link=_RESUMO,
         por_papel={"operador": {"prioridade": "normal"}}),
    Tipo("N05", "conversas", "normal", "O caso de {nome} {mudanca}",
         "Quem estava com o caso fica sabendo por aqui.",
         externo="Um caso mudou de mãos", acao="Abrir pasta", link=_RESUMO),
    Tipo("N28", "conversas", "alta", "{nome} espera resposta há mais de 2 horas",
         "A mensagem chegou às {hora} e o caso está com a equipe.",
         externo="Cliente esperando resposta", acao="Abrir conversa", link=_CONVERSA),
    # ── reuniões ──
    Tipo("N06", "reunioes", "alta", "Reunião pedida por {nome}: aprovar",
         "Para {quando}. Escolha quem atende.",
         externo="Reunião para aprovar", acao="Aprovar reunião", link=_APROVAR,
         por_papel={"operador": {"prioridade": "normal", "titulo": "Reunião pedida por {nome}",
                                 "texto": "Para {quando}. O administrador aprova e escolhe quem atende.",
                                 "acao": "Ver na agenda", "link": "/agenda"}}),
    Tipo("N07", "reunioes", "alta", "Reunião com {nome} atribuída a você",
         "{quando_maiusculo}. O lembrete chega 30 e 5 minutos antes.",
         externo="Reunião atribuída a você", acao="Ver na agenda", link="/agenda"),
    Tipo("N08", "reunioes", "alta", "{nome} mudou o horário da reunião",
         "Novo horário: {quando}. A reunião volta para aprovação.",
         externo="Reunião remarcada", acao="Aprovar de novo", link=_APROVAR,
         por_papel={"operador": {"texto": "Novo horário: {quando}. O administrador aprova de novo e escolhe quem atende.",
                                 "acao": "Ver na agenda", "link": "/agenda"}}),
    Tipo("N09", "reunioes", "alta", "{nome} desmarcou a reunião de {quando}",
         "O compromisso saiu da agenda.",
         externo="Reunião desmarcada", acao="Ver na agenda", link="/agenda",
         por_papel={"admin": {"prioridade": "normal"}}),
    Tipo("N10", "reunioes", "alta", "Reunião com {nome} em {minutos} minutos",
         "Às {hora}. Abra a conversa para se preparar.",
         externo="Lembrete de reunião", acao="Abrir conversa", link=_CONVERSA),
    Tipo("N11", "reunioes", "urgente", "Reunião de {nome} às {hora} ainda sem atendente",
         "Faltam menos de 2 horas. Escolha quem atende.",
         externo="Reunião sem atendente", acao="Escolher atendente", link=_APROVAR),
    Tipo("N12", "reunioes", "alta", "A reunião com {nome} das {hora} não foi registrada",
         "Se aconteceu, marque como realizada na agenda; se não, remarque.",
         externo="Reunião sem registro", acao="Ver na agenda", link="/agenda"),
    # ── retornos e pagamentos ──
    Tipo("N13", "retornos", "normal", "Conferir o pagamento parcial de {nome}",
         "O assistente deixou na sua agenda: falta parte do valor combinado.",
         externo="Pagamento para conferir", acao="Abrir pasta", link=_ACORDO),
    Tipo("N14", "retornos", "alta", "Retorno com {nome} às {hora}",
         "Faltam 15 minutos.", externo="Retorno em 15 minutos", acao="Abrir pasta", link=_RESUMO),
    Tipo("N15", "retornos", "normal", "Sua agenda de hoje", "{resumo}",
         externo="Agenda do dia", acao="Abrir agenda", link="/agenda",
         por_papel={"admin": {"titulo": "Resumo da equipe hoje"}}),
    Tipo("N16", "retornos", "alta", "A promessa de {nome} venceu ontem sem pagamento confirmado",
         "Fale com a pessoa ou registre o pagamento, se já entrou.",
         externo="Promessa vencida", acao="Abrir pasta", link=_ACORDO,
         titulo_grupo="{n} promessas venceram ontem sem pagamento confirmado", link_grupo="/agenda",
         texto_grupo="Fale com as pessoas ou registre os pagamentos que já entraram."),
    Tipo("N17", "retornos", "alta", "Compromissos da equipe atrasados há mais de 1 dia útil: {n}",
         "{detalhe}", externo="Compromissos atrasados na equipe", acao="Abrir agenda da equipe", link="/agenda"),
    Tipo("N18", "retornos", "alta", "{nome} diz que já pagou: conferir",
         "Confira no banco antes de dar baixa. A cobrança fica parada enquanto isso.",
         externo="Pagamento informado para conferir", acao="Abrir pasta", link=_ACORDO),
    Tipo("N19", "retornos", "normal", "Pagamento confirmado: {nome}",
         "A promessa dessa pessoa foi marcada como cumprida.",
         externo="Pagamento confirmado", acao="Abrir pasta", link=_ACORDO, modo="agrupar",
         titulo_grupo="Pagamentos confirmados hoje na sua fila: {n}",
         texto_grupo="As promessas dessas pessoas foram marcadas como cumpridas.", link_grupo="/acordos"),
    Tipo("N20", "retornos", "normal", "O assistente fechou um acordo com {nome}",
         "A primeira parcela já está na agenda.",
         externo="Acordo fechado pelo assistente", acao="Abrir pasta", link=_ACORDO, modo="agrupar",
         titulo_grupo="Acordos fechados pelo assistente hoje: {n}",
         texto_grupo="As primeiras parcelas já estão na agenda.", link_grupo="/acordos"),
    Tipo("N21", "retornos", "alta", "O acordo de {nome} foi quebrado",
         "A promessa venceu sem pagamento e sem nova data.",
         externo="Acordo quebrado", acao="Abrir pasta", link=_ACORDO),
    # ── pedidos e LGPD ──
    Tipo("N22", "pedidos", "alta", "{nome} não reconhece a dívida",
         "A cobrança parou e a contestação foi aberta. Confira os dados antes de qualquer contato.",
         externo="Contestação aberta", acao="Abrir pasta", link=_RESUMO),
    Tipo("N23", "pedidos", "normal", "{nome} {pedido}", "A cobrança parou neste caso.",
         externo="Pedido para parar o contato", acao="Abrir pasta", link=_RESUMO),
    Tipo("N24", "pedidos", "alta", "Pedido de {nome} sobre os dados pessoais: {pedido}",
         "{prazo}", externo="Pedido sobre dados pessoais", acao="Abrir pasta", link=_RESUMO,
         por_papel={"operador": {"prioridade": "normal"}}),
    Tipo("N25", "pedidos", "alta", "O prazo do pedido de dados de {nome} {vence}",
         "O prazo é de 15 dias. Responda antes que vença.",
         externo="Prazo de pedido de dados pessoais", acao="Abrir pasta", link=_RESUMO),
    # ── equipe ──
    Tipo("N26", "equipe", "normal", "Devedores novos na sua fila: {n}", "Eles já aparecem nas suas pastas.",
         externo="Devedores novos na sua fila", acao="Abrir pastas", link="/pastas", modo="agrupar",
         titulo_grupo="Devedores novos na sua fila: {n}"),
    Tipo("N27", "equipe", "normal", "Tarefa para hoje: {tarefa}", "Tarefa administrativa da empresa.",
         externo="Tarefa para hoje", acao="Abrir tarefas", link="/agenda?area=administracao",
         titulo_grupo="{n} tarefas administrativas vencem hoje"),
    Tipo("N29", "equipe", "normal", "Sua dúvida foi respondida",
         "A equipe Mizan respondeu na Central de Ajuda.",
         externo="Dúvida respondida", acao="Ver resposta", link="/ajuda"),
    # ── sistema ──
    Tipo("N30", "sistema", "urgente", "O agente está parado", "",
         externo="O agente está parado", acao="Ver agentes", link="/agente",
         variantes={
             "teto": {"titulo": "O agente parou: o teto de gasto do dia foi atingido",
                      "texto": "As conversas esperam na fila até amanhã ou até o teto subir."},
             "ia": {"titulo": "O agente está parado: a IA não responde há mais de 15 minutos",
                    "texto": "As mensagens esperam na fila e saem quando a IA voltar."},
             "falhas": {"prioridade": "alta", "titulo": "Um evento do agente falhou de vez",
                        "texto": "Confira o caso na tela dos agentes.", "modo": "agrupar",
                        "titulo_grupo": "Eventos do agente que falharam de vez na última hora: {n}"},
         }),
    Tipo("N31", "sistema", "alta", "A sincronização de uma conexão falhou",
         "Os dados do banco do cliente podem estar desatualizados. Confira a conexão.",
         externo="A sincronização de uma conexão falhou", acao="Ver conexões", link="/"),
    Tipo("N32", "sistema", "normal", "O Cientista tem uma recomendação para você decidir",
         "Abra o Laboratório para aprovar ou recusar.",
         externo="Recomendação do Cientista", acao="Abrir Laboratório", link="/laboratorio",
         variantes={"dano": {"prioridade": "alta", "titulo": "O Cientista encerrou um experimento",
                             "texto": "O grupo do agente pagou menos que o grupo de comparação. Revise antes de continuar."}}),
    Tipo("N33", "sistema", "normal", "Segurança da conta", "",
         externo="Aviso de segurança", acao="Ver usuários", link="/admin/usuarios",
         variantes={
             "2fa_pessoa": {"prioridade": "alta", "titulo": "Sua verificação em duas etapas foi redefinida",
                            "texto": "A equipe Mizan redefiniu a verificação. Configure de novo em Verificação em duas etapas.",
                            "acao": "Configurar", "link": "/seguranca"},
             "2fa_admin": {"titulo": "A verificação em duas etapas de {pessoa} foi redefinida",
                           "texto": "Feito pela equipe Mizan. A pessoa configura de novo no próximo acesso."},
             "senha_2fa": {"titulo": "{pessoa} trocou a senha pelo código do aplicativo",
                           "texto": "Se não foi a própria pessoa, desative a conta em Usuários."},
             "bloqueio": {"prioridade": "alta", "titulo": "Acesso bloqueado por senhas erradas: {pessoa}",
                          "texto": "Muitas tentativas erradas seguidas. O acesso volta sozinho em alguns minutos."},
         }),
    # ── escalonamento: urgente sem leitura em 15 minutos ──
    Tipo("ESC", "sistema", "urgente", "Sem resposta há 15 min: {titulo_original}", "{texto_original}",
         externo="Aviso urgente sem resposta", acao="{acao_original}", link="{link_original}"),
)}

MOTIVO_TRANSFERENCIA = {"pedido_do_devedor": "a pessoa pediu para falar com alguém da equipe",
                        "fora_da_politica": "o pedido sai da política da empresa",
                        "dificuldade_grave": "a pessoa relatou dificuldade grave",
                        "duvida": "uma dúvida que o assistente não resolve sozinho",
                        "falha": "falha técnica no atendimento automático"}
SITUACAO_DO_CASO = {"com_pessoa": "com a equipe", "contestado": "em contestação",
                    "suspenso": "com a cobrança parada", "quitado": "quitado",
                    "pagamento_em_conferencia": "com pagamento em conferência"}


# ── texto ────────────────────────────────────────────────────────────────────
def primeiro_nome(nome) -> str:
    """Só o primeiro nome, com maiúscula. Nome com número (um CPF por engano) não sai."""
    partes = str(nome or "").split()
    if not partes or re.search(r"\d", partes[0]):
        return "Cliente"
    p = partes[0]
    return p[:1].upper() + p[1:].lower()


def _hora(h) -> str:
    return str(h or "")[:5]


def quando(data, hora=None, agora: datetime | None = None) -> str:
    """'hoje às 14:30', 'amanhã às 9:00' ou '07/11 às 14:30' (horário de Brasília)."""
    try:
        d = date.fromisoformat(str(data)[:10])
    except ValueError:
        return str(data or "")
    hoje = (agora or datetime.now(timezone.utc)).astimezone(BRASILIA).date()
    dia = "hoje" if d == hoje else "amanhã" if d == hoje + timedelta(days=1) else \
        "ontem" if d == hoje - timedelta(days=1) else d.strftime("%d/%m")
    return f"{dia} às {_hora(hora)}" if hora else dia


class _Campos(dict):
    def __missing__(self, chave):
        return ""


_LINK_SEGURO = re.compile(r"^/[A-Za-z0-9/_\-?=&.%]*$")


def _formatar(modelo: str, campos: dict) -> str:
    try:
        texto = str(modelo or "").format_map(_Campos(campos))
    except (ValueError, IndexError):
        texto = str(modelo or "")
    return re.sub(r"\s{2,}", " ", texto).strip()


def _link(modelo: str, campos: dict) -> str | None:
    if campos.get("predicao_id") in (None, "") and "{predicao_id}" in (modelo or ""):
        modelo = "/agenda"
    link = _formatar(modelo, {k: str(v) for k, v in campos.items()})
    return link if link and _LINK_SEGURO.match(link) and not link.startswith("//") and len(link) <= 300 else "/inicio"


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _modelo(tipo: Tipo, papel: str | None, variante: str | None) -> dict:
    """Campos do tipo com a variante e o papel aplicados (o papel por último)."""
    m = {k: getattr(tipo, k) for k in ("categoria", "prioridade", "titulo", "texto", "externo", "acao", "link",
                                       "modo", "titulo_grupo", "texto_grupo", "link_grupo")}
    m.update(tipo.variantes.get(variante or "", {}))
    m.update(tipo.por_papel.get(papel or "", {}))
    return m


def montar(codigo: str, contexto: dict, papel: str | None = None, n: int = 1) -> dict:
    """Título, texto, link e prioridade de um aviso para uma pessoa (função pura)."""
    tipo = CATALOGO[codigo]
    m = _modelo(tipo, papel, (contexto or {}).get("variante"))
    campos = dict(contexto or {})
    campos["nome"] = primeiro_nome(campos.get("nome")) if "nome" in campos or "{nome}" in m["titulo"] else ""
    campos["n"] = n
    q = campos.get("quando") or ""
    campos["quando_maiusculo"] = q[:1].upper() + q[1:]
    grupo = n > 1 and m["titulo_grupo"]
    titulo = _formatar(m["titulo_grupo"] if grupo else m["titulo"], campos)
    texto = _formatar((m["texto_grupo"] or m["texto"]) if grupo else m["texto"], campos)
    link = _link((m["link_grupo"] or m["link"]) if grupo else m["link"], campos)
    return {"categoria": m["categoria"], "prioridade": m["prioridade"], "modo": m["modo"],
            "titulo": _cortar(titulo or "Aviso novo", LIMITE_TITULO),
            "texto": _cortar(texto, LIMITE_TEXTO) or None, "link": link,
            "acao": _cortar(_formatar(m["acao"], campos) or "Abrir", 40),
            "externo": _cortar(_formatar(m["externo"], campos), 80)}


# ── preferências ─────────────────────────────────────────────────────────────
def preferencias_validas(dados: dict | None) -> dict:
    """Preferências com os padrões, só com valores conhecidos (o que vier errado é ignorado)."""
    p = dict(PADRAO_PREFERENCIAS)
    d = dados if isinstance(dados, dict) else {}
    for k in ("navegador", "email_resumo", "silencio_ligado"):
        if isinstance(d.get(k), bool):
            p[k] = d[k]
    for k in ("silencio_inicio", "silencio_fim"):
        if isinstance(d.get(k), int) and not isinstance(d.get(k), bool) and 0 <= d[k] <= 23:
            p[k] = d[k]
    if isinstance(d.get("desligadas"), list):
        p["desligadas"] = [c for c in CATEGORIAS if c in d["desligadas"]]
    return p


def em_silencio(prefs: dict, agora: datetime) -> bool:
    p = preferencias_validas(prefs)
    if not p["silencio_ligado"] or p["silencio_inicio"] == p["silencio_fim"]:
        return False
    h, ini, fim = agora.astimezone(BRASILIA).hour, p["silencio_inicio"], p["silencio_fim"]
    return ini <= h < fim if ini < fim else (h >= ini or h < fim)


def toca_agora(prioridade: str, prefs: dict, agora: datetime) -> bool:
    """Se o aviso deve chamar a atenção agora (aviso na tela ou do navegador)."""
    if prioridade == "urgente":
        return True
    return prioridade == "alta" and not em_silencio(prefs, agora)


# ── armazém ──────────────────────────────────────────────────────────────────
def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArmazemMemoria:
    """Para testes e demonstração local. Mesmo contrato do ArmazemSupabase."""

    def __init__(self, usuarios=None, agenda=None):
        self.linhas: list = []
        self.prefs: dict = {}
        self.usuarios_lista: list = list(usuarios or [])
        self.agenda: list = list(agenda or [])
        self._n = 0

    # pessoas
    def usuarios(self, empresa_id: str) -> list:
        return [dict(u) for u in self.usuarios_lista if (u.get("empresa_id") or "") == empresa_id]

    def preferencias(self, ids: list) -> dict:
        return {i: dict(self.prefs[i]) for i in ids if i in self.prefs}

    def salvar_preferencias(self, usuario_id: str, empresa_id: str, dados: dict) -> dict:
        atual = self.prefs.get(usuario_id) or {}
        self.prefs[usuario_id] = {**atual, "usuario_id": usuario_id, "empresa_id": empresa_id, "dados": dict(dados)}
        return dict(self.prefs[usuario_id])

    def com_resumo_por_email(self) -> list:
        return [dict(p) for p in self.prefs.values() if (p.get("dados") or {}).get("email_resumo")]

    def marcar_resumo_enviado(self, usuario_id: str, dia: str) -> None:
        if usuario_id in self.prefs:
            self.prefs[usuario_id]["resumo_enviado_em"] = dia

    # notificações
    def existe(self, usuario_id: str, chave: str) -> bool:
        return any(l["usuario_id"] == usuario_id and l["chave"] == chave for l in self.linhas)

    def aberta(self, usuario_id: str, chave: str) -> dict | None:
        return next((dict(l) for l in self.linhas if l["usuario_id"] == usuario_id and l["chave"] == chave
                     and not l.get("lida_em") and not l.get("resolvida_em")), None)

    def inserir(self, linha: dict) -> dict:
        if self.aberta(linha["usuario_id"], linha["chave"]):
            raise ValueError("duplicate key value violates unique constraint uq_notificacoes_abertas")
        self._n += 1
        agora = linha.get("criado_em") or _agora_iso()
        nova = {"id": str(uuid.UUID(int=self._n)), "criado_em": agora, "atualizado_em": agora, "agrupadas": 1,
                "lida_em": None, "resolvida_em": None, "escalada_em": None, **linha}
        self.linhas.append(nova)
        return dict(nova)

    def atualizar(self, id_: str, campos: dict) -> None:
        for l in self.linhas:
            if l["id"] == id_:
                l.update(campos)

    def resolver(self, empresa_id: str, entidade: str, entidade_id: str, tipos=None, quando: str | None = None) -> list:
        saida = []
        for l in self.linhas:
            if (l["empresa_id"] == empresa_id and l.get("entidade") == entidade and l.get("entidade_id") == entidade_id
                    and not l.get("resolvida_em") and (not tipos or l["tipo"] in tipos)):
                l["resolvida_em"] = quando or _agora_iso()
                saida.append(dict(l))
        return saida

    def de_entidade(self, empresa_id: str, entidade: str, entidade_id: str, tipos=None) -> list:
        return [dict(l) for l in self.linhas if l["empresa_id"] == empresa_id and l.get("entidade") == entidade
                and l.get("entidade_id") == entidade_id and (not tipos or l["tipo"] in tipos)]

    def listar(self, usuario_id: str, empresa_id: str, pendentes: bool, limite: int, antes: str | None,
               categoria: str | None = None, prioridade: str | None = None) -> list:
        ls = [l for l in self.linhas if l["usuario_id"] == usuario_id and l["empresa_id"] == empresa_id
              and not l.get("resolvida_em") and (not pendentes or not l.get("lida_em"))
              and (not antes or str(l["atualizado_em"]) < antes)
              and (not categoria or l.get("categoria") == categoria)
              and (not prioridade or l.get("prioridade") == prioridade)]
        ls.sort(key=lambda l: str(l["atualizado_em"]), reverse=True)
        return [dict(l) for l in ls[:limite]]

    def abertas(self, usuario_id: str, empresa_id: str) -> list:
        return [dict(l) for l in self.linhas if l["usuario_id"] == usuario_id and l["empresa_id"] == empresa_id
                and not l.get("lida_em") and not l.get("resolvida_em")]

    def marcar_lidas(self, usuario_id: str, empresa_id: str, ids=None, quando: str | None = None) -> int:
        n = 0
        for l in self.linhas:
            if (l["usuario_id"] == usuario_id and l["empresa_id"] == empresa_id and not l.get("lida_em")
                    and (ids is None or l["id"] in ids)):
                l["lida_em"] = quando or _agora_iso()
                n += 1
        return n

    def urgentes_sem_leitura(self, desde: str, ate: str) -> list:
        return [dict(l) for l in self.linhas if l["prioridade"] == "urgente" and not l.get("lida_em")
                and not l.get("resolvida_em") and not l.get("escalada_em") and desde < str(l["criado_em"]) < ate]

    def excluir(self, usuario_id: str, empresa_id: str, ids=None, so_lidas: bool = False,
                categoria: str | None = None, prioridade: str | None = None) -> int:
        if ids is None and not so_lidas:
            raise ValueError("excluir sem dizer quais")
        antes = len(self.linhas)
        self.linhas = [l for l in self.linhas if not (
            l["usuario_id"] == usuario_id and l["empresa_id"] == empresa_id
            and (ids is None or l["id"] in ids) and (not so_lidas or l.get("lida_em"))
            and (not categoria or l.get("categoria") == categoria)
            and (not prioridade or l.get("prioridade") == prioridade))]
        return antes - len(self.linhas)

    def resolver_antigas(self, tipos, antes: str, quando: str | None = None) -> list:
        saida = []
        for l in self.linhas:
            if l["tipo"] in tipos and str(l["criado_em"]) < antes and not l.get("resolvida_em"):
                l["resolvida_em"] = quando or _agora_iso()
                saida.append(dict(l))
        return saida

    def limpar(self, resolvidas_antes: str, lidas_antes: str, todas_antes: str) -> int:
        antes = len(self.linhas)
        self.linhas = [l for l in self.linhas if not (
            str(l["criado_em"]) < todas_antes
            or (l.get("resolvida_em") and str(l["resolvida_em"]) < resolvidas_antes)
            or (l.get("lida_em") and str(l["atualizado_em"]) < lidas_antes))]
        return antes - len(self.linhas)

    # agenda (só leitura, para o relógio)
    def _agenda(self, filtro) -> list:
        return [dict(a) for a in self.agenda if (a.get("situacao") or "pendente") == "pendente" and filtro(a)]

    def agenda_com_hora(self, dias: list) -> list:
        return self._agenda(lambda a: str(a.get("data"))[:10] in dias and a.get("hora"))

    def agenda_ate(self, dia: str) -> list:
        return self._agenda(lambda a: str(a.get("data"))[:10] <= dia)

    def avisos_de_mensagem(self, desde: str, ate: str) -> list:
        return self._agenda(lambda a: (a.get("observacao") or "").startswith(PREFIXO_MENSAGEM)
                            and desde <= str(a.get("created_at")) <= ate)


class ArmazemSupabase:
    """Produção: tabelas notificacoes e notificacao_preferencias, e leitura da agenda."""

    _COLUNAS = ("id, criado_em, atualizado_em, empresa_id, usuario_id, tipo, categoria, prioridade, titulo, "
                "texto, link, acao, entidade, entidade_id, chave, agrupadas, lida_em, resolvida_em, escalada_em")
    _COLUNAS_AGENDA = "id, empresa_id, predicao_id, nome, operador_id, tipo, data, hora, observacao, created_at"

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is not None:
            return self._db
        from db import get_db
        return get_db()

    def _t(self, nome="notificacoes"):
        return self.db.table(nome)

    def usuarios(self, empresa_id: str) -> list:
        return (self._t("usuarios").select("id, nome, email, role, ativo, empresa_id")
                .eq("empresa_id", empresa_id).limit(1000).execute().data or [])

    def preferencias(self, ids: list) -> dict:
        if not ids:
            return {}
        r = (self._t("notificacao_preferencias").select("usuario_id, empresa_id, dados, resumo_enviado_em")
             .in_("usuario_id", list(ids)).execute().data or [])
        return {p["usuario_id"]: p for p in r}

    def salvar_preferencias(self, usuario_id: str, empresa_id: str, dados: dict) -> dict:
        r = (self._t("notificacao_preferencias").upsert(
            {"usuario_id": usuario_id, "empresa_id": empresa_id, "dados": dados, "atualizado_em": _agora_iso()},
            on_conflict="usuario_id").execute().data or [{}])
        return r[0]

    def com_resumo_por_email(self) -> list:
        return (self._t("notificacao_preferencias").select("usuario_id, empresa_id, dados, resumo_enviado_em")
                .eq("dados->>email_resumo", "true").limit(2000).execute().data or [])

    def marcar_resumo_enviado(self, usuario_id: str, dia: str) -> None:
        self._t("notificacao_preferencias").update({"resumo_enviado_em": dia}).eq("usuario_id", usuario_id).execute()

    def existe(self, usuario_id: str, chave: str) -> bool:
        return bool(self._t().select("id").eq("usuario_id", usuario_id).eq("chave", chave).limit(1).execute().data)

    def aberta(self, usuario_id: str, chave: str) -> dict | None:
        r = (self._t().select("id, agrupadas").eq("usuario_id", usuario_id).eq("chave", chave)
             .is_("lida_em", "null").is_("resolvida_em", "null").limit(1).execute().data)
        return (r or [None])[0]

    def inserir(self, linha: dict) -> dict:
        return (self._t().insert(linha).execute().data or [linha])[0]

    def atualizar(self, id_: str, campos: dict) -> None:
        self._t().update(campos).eq("id", id_).execute()

    def resolver(self, empresa_id: str, entidade: str, entidade_id: str, tipos=None, quando: str | None = None) -> list:
        q = (self._t().update({"resolvida_em": quando or _agora_iso()}).eq("empresa_id", empresa_id)
             .eq("entidade", entidade).eq("entidade_id", str(entidade_id)).is_("resolvida_em", "null"))
        if tipos:
            q = q.in_("tipo", list(tipos))
        return q.execute().data or []

    def de_entidade(self, empresa_id: str, entidade: str, entidade_id: str, tipos=None) -> list:
        q = (self._t().select("id, usuario_id, tipo, criado_em, lida_em, resolvida_em").eq("empresa_id", empresa_id)
             .eq("entidade", entidade).eq("entidade_id", str(entidade_id)))
        if tipos:
            q = q.in_("tipo", list(tipos))
        return q.order("criado_em", desc=True).limit(50).execute().data or []

    def listar(self, usuario_id: str, empresa_id: str, pendentes: bool, limite: int, antes: str | None,
               categoria: str | None = None, prioridade: str | None = None) -> list:
        q = (self._t().select(self._COLUNAS).eq("usuario_id", usuario_id).eq("empresa_id", empresa_id)
             .is_("resolvida_em", "null"))                  # o que já se resolveu não fica na lista
        if pendentes:
            q = q.is_("lida_em", "null")
        if antes:
            q = q.lt("atualizado_em", antes)
        if categoria:
            q = q.eq("categoria", categoria)
        if prioridade:
            q = q.eq("prioridade", prioridade)
        return q.order("atualizado_em", desc=True).limit(limite).execute().data or []

    def abertas(self, usuario_id: str, empresa_id: str) -> list:
        return (self._t().select("id, tipo, categoria, prioridade").eq("usuario_id", usuario_id)
                .eq("empresa_id", empresa_id).is_("lida_em", "null").is_("resolvida_em", "null")
                .limit(500).execute().data or [])

    def marcar_lidas(self, usuario_id: str, empresa_id: str, ids=None, quando: str | None = None) -> int:
        q = (self._t().update({"lida_em": quando or _agora_iso()}).eq("usuario_id", usuario_id)
             .eq("empresa_id", empresa_id).is_("lida_em", "null"))
        if ids is not None:
            q = q.in_("id", list(ids))
        return len(q.execute().data or [])

    def urgentes_sem_leitura(self, desde: str, ate: str) -> list:
        return (self._t().select(self._COLUNAS).eq("prioridade", "urgente").is_("lida_em", "null")
                .is_("resolvida_em", "null").is_("escalada_em", "null").gt("criado_em", desde).lt("criado_em", ate)
                .limit(200).execute().data or [])

    def excluir(self, usuario_id: str, empresa_id: str, ids=None, so_lidas: bool = False,
                categoria: str | None = None, prioridade: str | None = None) -> int:
        if ids is None and not so_lidas:
            raise ValueError("excluir sem dizer quais")
        q = self._t().delete().eq("usuario_id", usuario_id).eq("empresa_id", empresa_id)
        if ids is not None:
            q = q.in_("id", list(ids))
        if so_lidas:
            q = q.not_.is_("lida_em", "null")
        if categoria:
            q = q.eq("categoria", categoria)
        if prioridade:
            q = q.eq("prioridade", prioridade)
        return len(q.execute().data or [])

    def resolver_antigas(self, tipos, antes: str, quando: str | None = None) -> list:
        return (self._t().update({"resolvida_em": quando or _agora_iso()}).in_("tipo", list(tipos))
                .lt("criado_em", antes).is_("resolvida_em", "null").execute().data or [])

    def limpar(self, resolvidas_antes: str, lidas_antes: str, todas_antes: str) -> int:
        n = len(self._t().delete().lt("criado_em", todas_antes).execute().data or [])
        n += len(self._t().delete().lt("resolvida_em", resolvidas_antes).execute().data or [])
        n += len(self._t().delete().lt("atualizado_em", lidas_antes).not_.is_("lida_em", "null").execute().data or [])
        return n

    def _paginas(self, montar_consulta, maximo: int = 20000) -> list:
        saida, passo = [], 1000
        while len(saida) < maximo:
            parte = montar_consulta().range(len(saida), len(saida) + passo - 1).execute().data or []
            saida += parte
            if len(parte) < passo:
                break
        return saida

    def agenda_com_hora(self, dias: list) -> list:
        return (self._t("agenda").select(self._COLUNAS_AGENDA).eq("situacao", "pendente").in_("data", list(dias))
                .not_.is_("hora", "null").limit(3000).execute().data or [])

    def agenda_ate(self, dia: str) -> list:
        return self._paginas(lambda: self._t("agenda").select(self._COLUNAS_AGENDA)
                             .eq("situacao", "pendente").lte("data", dia).order("id"))

    def avisos_de_mensagem(self, desde: str, ate: str) -> list:
        return (self._t("agenda").select(self._COLUNAS_AGENDA).eq("situacao", "pendente")
                .like("observacao", PREFIXO_MENSAGEM + "%").gte("created_at", desde).lte("created_at", ate)
                .limit(2000).execute().data or [])


fabrica_armazem = lambda: ArmazemSupabase()   # noqa: E731 — os testes trocam por ArmazemMemoria
_ARMAZEM = {"atual": None}


def armazem():
    if _ARMAZEM["atual"] is None:
        _ARMAZEM["atual"] = fabrica_armazem()
    return _ARMAZEM["atual"]


def usar_armazem(a) -> None:
    """Troca o armazém (testes) e limpa os caches de pessoas, preferências e chaves já gravadas."""
    _ARMAZEM["atual"] = a
    _CACHE.clear()
    _GRAVADAS.clear()


# Chaves de aviso "único" já gravadas neste servidor: o relógio passa pelo mesmo lembrete
# a cada minuto da janela e não precisa perguntar ao banco de novo. Depois de um reinício,
# a conferência no banco (existe) cobre.
_GRAVADAS: set = set()


# ── liga/desliga, fila e disjuntor ───────────────────────────────────────────
def ligado() -> bool:
    return os.getenv("MIZAN_NOTIFICACOES", "1") != "0"


ASSINCRONO = os.getenv("MIZAN_NOTIFICACOES_ASSINCRONO", "1") != "0"
_FILA = {"exec": None}
_TRAVA_FILA = threading.Lock()
_DISJUNTOR = {"seguidas": 0, "ate": 0.0, "log_em": 0.0}
ESTADO = {"gravadas": 0, "falhas": 0, "ultima_falha": None}     # sem dado pessoal: alimenta o diagnóstico


def _sem_tabela(e: Exception) -> bool:
    m = str(e).lower()
    return "notificac" in m and any(k in m for k in ("does not exist", "could not find", "schema cache",
                                                     "42p01", "pgrst205"))


def disjuntor_aberto() -> bool:
    return time.monotonic() < _DISJUNTOR["ate"]


def _registrar_falha(e: Exception) -> None:
    ESTADO["falhas"] += 1
    ESTADO["ultima_falha"] = type(e).__name__
    _DISJUNTOR["seguidas"] += 1
    if _DISJUNTOR["seguidas"] >= 3 or _sem_tabela(e):
        _DISJUNTOR["ate"] = time.monotonic() + (600 if _sem_tabela(e) else 120)
        _DISJUNTOR["seguidas"] = 0
    if time.monotonic() - _DISJUNTOR["log_em"] > 60:
        _DISJUNTOR["log_em"] = time.monotonic()
        dica = " (rode backend/sql/migracao_notificacoes.sql)" if _sem_tabela(e) else ""
        print(f"[Notificações] aviso não gravado: {type(e).__name__}{dica}")


def _seguro(fn, *a, **k):
    if not ligado() or disjuntor_aberto():
        return None
    try:
        r = fn(*a, **k)
        _DISJUNTOR["seguidas"] = 0
        return r
    except Exception as e:                       # notificar nunca derruba quem chamou
        _registrar_falha(e)
        return None


def _enfileirar(fn, *a, **k) -> None:
    if not ligado() or disjuntor_aberto():
        return
    if not ASSINCRONO:
        _seguro(fn, *a, **k)
        return
    with _TRAVA_FILA:
        if _FILA["exec"] is None:
            _FILA["exec"] = ThreadPoolExecutor(max_workers=1, thread_name_prefix="notificacoes")
        exe = _FILA["exec"]
    try:
        exe.submit(_seguro, fn, *a, **k)
    except RuntimeError:                         # servidor encerrando
        pass


def esperar(prazo_s: float = 10.0) -> None:
    """Espera a fila esvaziar (testes e encerramento)."""
    exe = _FILA["exec"]
    if exe is not None:
        exe.submit(lambda: None).result(timeout=prazo_s)


# ── pessoas e preferências (cache curto) ─────────────────────────────────────
_CACHE: dict = {}
_CACHE_S = 60


def _cache(chave, buscar):
    agora = time.monotonic()
    achado = _CACHE.get(chave)
    if achado and achado[0] > agora:
        return achado[1]
    valor = buscar()
    if len(_CACHE) > 5000:
        _CACHE.clear()
    _CACHE[chave] = (agora + _CACHE_S, valor)
    return valor


def pessoas(empresa_id: str) -> dict:
    """{id: pessoa} das pessoas ativas (operador e administrador) da empresa."""
    def buscar():
        return {str(u["id"]): {"id": str(u["id"]), "nome": u.get("nome") or "", "email": u.get("email") or "",
                               "role": u.get("role")}
                for u in armazem().usuarios(empresa_id) if u.get("ativo", True) and u.get("role") in ("operador", "admin")}
    return _cache(("pessoas", empresa_id), buscar) if empresa_id else {}


def _prefs_de(ids: list) -> dict:
    faltam = [i for i in ids if ("prefs", i) not in _CACHE or _CACHE[("prefs", i)][0] <= time.monotonic()]
    if faltam:
        achadas = armazem().preferencias(faltam)
        for i in faltam:
            _CACHE[("prefs", i)] = (time.monotonic() + _CACHE_S, preferencias_validas((achadas.get(i) or {}).get("dados")))
    return {i: _CACHE[("prefs", i)][1] for i in ids}


def destinatarios(empresa_id: str, *, usuarios=(), devedor: dict | None = None, admins: bool = False,
                  ou_admins: bool = True, exceto=None) -> list:
    """Quem recebe, pela regra do plano (seção 3). Nunca alguém de outra empresa."""
    gente = pessoas(empresa_id)
    ids: list = [str(u) for u in usuarios if u and str(u) in gente]
    if devedor is not None:
        resp = str(devedor.get("responsavel_id") or "")
        if resp in gente:
            ids.append(resp)
    if admins or (ou_admins and not ids):
        ids += [i for i, p in gente.items() if p["role"] == "admin"]
    saida, vistos = [], set()
    for i in ids:
        if i not in vistos and i != str(exceto or ""):
            vistos.add(i)
            saida.append(gente[i])
    return saida


# ── gravar ───────────────────────────────────────────────────────────────────
def notificar(codigo: str, empresa_id: str, *, contexto: dict | None = None, chave: str,
              usuarios=(), devedor: dict | None = None, admins: bool = False, ou_admins: bool = True,
              exceto=None, entidade: tuple | None = None, quantidade: int = 1, prioridade: str | None = None,
              agora: datetime | None = None) -> None:
    """Registra o aviso para quem deve receber. Volta na hora; grava na fila própria."""
    if not ligado() or not empresa_id or codigo not in CATALOGO:
        return
    if (str(empresa_id), str(chave)[:200]) in _GRAVADAS:
        return
    # Do devedor só vai para a fila o que decide o destino e o texto (nunca o CPF).
    dev = ({"id": devedor.get("id"), "nome": devedor.get("nome"), "responsavel_id": devedor.get("responsavel_id")}
           if devedor else None)
    _enfileirar(_gravar, codigo, str(empresa_id), dict(contexto or {}), str(chave)[:200], tuple(usuarios),
                dev, admins, ou_admins, exceto, entidade, max(1, int(quantidade)), prioridade, agora)


def _gravar(codigo, empresa_id, contexto, chave, usuarios, devedor, admins, ou_admins, exceto, entidade,
            quantidade, prioridade, agora) -> list:
    quem = destinatarios(empresa_id, usuarios=usuarios, devedor=devedor, admins=admins, ou_admins=ou_admins,
                         exceto=exceto)
    if not quem:
        return []
    prefs = _prefs_de([p["id"] for p in quem])
    momento = (agora or datetime.now(timezone.utc)).isoformat()
    gravadas, arm = [], armazem()
    for p in quem:
        base = montar(codigo, contexto, p["role"], quantidade)
        pri = prioridade or base["prioridade"]
        if base["categoria"] in prefs[p["id"]]["desligadas"] and pri != "urgente":
            continue                                       # a pessoa desligou esta categoria
        aberta = arm.aberta(p["id"], chave) if base["modo"] == "agrupar" else None
        if base["modo"] == "agrupar" and aberta:
            n = int(aberta.get("agrupadas") or 1) + quantidade
            m = montar(codigo, contexto, p["role"], n)
            arm.atualizar(aberta["id"], {"agrupadas": n, "titulo": m["titulo"], "texto": m["texto"], "link": m["link"],
                                         "acao": m["acao"], "atualizado_em": momento,
                                         "prioridade": prioridade or m["prioridade"]})
        else:
            if base["modo"] == "unico" and arm.existe(p["id"], chave):
                continue
            linha = {"empresa_id": empresa_id, "usuario_id": p["id"], "tipo": codigo, "categoria": base["categoria"],
                     "prioridade": pri, "titulo": base["titulo"], "texto": base["texto"], "link": base["link"],
                     "acao": base["acao"], "chave": chave, "agrupadas": quantidade,
                     "criado_em": momento, "atualizado_em": momento}
            if entidade:
                linha["entidade"], linha["entidade_id"] = str(entidade[0]), str(entidade[1])[:80]
            try:
                arm.inserir(linha)
            except Exception as e:
                if "duplicate" in str(e).lower() or "23505" in str(e):
                    continue                               # outro servidor gravou o mesmo aviso
                raise
        gravadas.append(p["id"])
        mudancas.marcar_usuario(p["id"])
    ESTADO["gravadas"] += len(gravadas)
    if base["modo"] == "unico":
        if len(_GRAVADAS) > 20000:
            _GRAVADAS.clear()
        _GRAVADAS.add((empresa_id, chave))
    return gravadas


def resolver(empresa_id: str, entidade: str, entidade_id, tipos=None) -> None:
    """O assunto se resolveu: os avisos ligados a ele saem da lista de pendentes."""
    if entidade_id in (None, "") or not empresa_id:
        return
    _enfileirar(_resolver, str(empresa_id), entidade, str(entidade_id), tuple(tipos or ()))


def _resolver(empresa_id, entidade, entidade_id, tipos) -> list:
    linhas = armazem().resolver(empresa_id, entidade, entidade_id, list(tipos) or None)
    for uid in {l.get("usuario_id") for l in linhas if l.get("usuario_id")}:
        mudancas.marcar_usuario(uid)
    return linhas


def compromisso_resolvido(empresa_id: str, item: dict) -> None:
    """Um compromisso da agenda foi cumprido, cancelado ou quebrado (por pessoa ou pelo agente)."""
    if not item or not item.get("id"):
        return
    resolver(empresa_id, "agenda", item["id"])
    obs, pid = item.get("observacao") or "", item.get("predicao_id")
    for prefixo, tipos in ((PREFIXO_TRANSFERENCIA, ("N02", "N03")), (PREFIXO_MENSAGEM, ("N01", "N28")),
                           (PREFIXO_PEDIDO, ("N24",)), (PREFIXO_PAGAMENTO_INFORMADO, ("N18",))):
        if obs.startswith(prefixo):
            resolver(empresa_id, "devedor", pid, tipos)


# ── ler (rotas) ──────────────────────────────────────────────────────────────
def para_tela(linha: dict, prefs: dict, agora: datetime) -> dict:
    tipo = CATALOGO.get(linha.get("tipo"))
    link = linha.get("link") or "/inicio"
    return {"id": linha["id"], "tipo": linha.get("tipo"), "categoria": linha.get("categoria"),
            "prioridade": linha.get("prioridade"), "titulo": linha.get("titulo"), "texto": linha.get("texto"),
            "link": link if _LINK_SEGURO.match(link) and not link.startswith("//") else "/inicio",
            "acao": linha.get("acao") or (tipo.acao if tipo and "{" not in tipo.acao else "Abrir"),
            "externo": tipo.externo if tipo else "Aviso novo no Mizan",
            "agrupadas": int(linha.get("agrupadas") or 1), "criado_em": linha.get("criado_em"),
            "atualizado_em": linha.get("atualizado_em"), "lida": bool(linha.get("lida_em")),
            "resolvida": bool(linha.get("resolvida_em")),
            "toca": (not linha.get("lida_em") and not linha.get("resolvida_em")
                     and toca_agora(linha.get("prioridade"), prefs, agora))}


def listar(usuario_id: str, empresa_id: str, filtro: str = "pendentes", limite: int = 30,
           antes: str | None = None, agora: datetime | None = None, categoria: str | None = None,
           prioridade: str | None = None) -> dict:
    """O que o sino e a página de notificações mostram. Levanta erro do banco (a rota decide o que dizer).
    `categoria` e `prioridade` filtram a lista; as contagens são sempre de tudo o que está aberto."""
    agora = agora or datetime.now(timezone.utc)
    limite = max(1, min(int(limite or 30), 100))
    arm = armazem()
    linhas = arm.listar(usuario_id, empresa_id, filtro != "todas", limite + 1, antes,
                        categoria if categoria in CATEGORIAS else None,
                        prioridade if prioridade in PRIORIDADES else None)
    abertas = arm.abertas(usuario_id, empresa_id)
    prefs = _prefs_de([usuario_id])[usuario_id]
    itens = [para_tela(l, prefs, agora) for l in linhas[:limite]]
    por_categoria = {c: 0 for c in CATEGORIAS}
    for a in abertas:
        if a.get("categoria") in por_categoria:
            por_categoria[a["categoria"]] += 1
    return {"ativo": True, "itens": itens, "mais": len(linhas) > limite,
            "nao_lidas": len(abertas), "urgentes": sum(1 for a in abertas if a.get("prioridade") == "urgente"),
            "por_categoria": por_categoria, "agora": agora.isoformat(), "preferencias": prefs}


def excluir(usuario_id: str, empresa_id: str, ids=None, so_lidas: bool = False,
            categoria: str | None = None, prioridade: str | None = None) -> int:
    """A pessoa apagou avisos dela: os indicados, ou os já lidos (só do assunto e da prioridade que a
    tela filtrava, se filtrava). Nunca os de outra pessoa."""
    if ids is not None and not ids:
        return 0
    n = armazem().excluir(usuario_id, empresa_id, ids, so_lidas,
                          categoria if so_lidas and categoria in CATEGORIAS else None,
                          prioridade if so_lidas and prioridade in PRIORIDADES else None)
    mudancas.marcar_usuario(usuario_id)
    return n


def marcar_lidas(usuario_id: str, empresa_id: str, ids=None) -> int:
    n = armazem().marcar_lidas(usuario_id, empresa_id, ids)
    mudancas.marcar_usuario(usuario_id)
    return n


def preferencias(usuario_id: str) -> dict:
    return preferencias_validas((armazem().preferencias([usuario_id]).get(usuario_id) or {}).get("dados"))


def salvar_preferencias(usuario_id: str, empresa_id: str, dados: dict) -> dict:
    p = preferencias_validas(dados)
    armazem().salvar_preferencias(usuario_id, empresa_id, p)
    _CACHE.pop(("prefs", usuario_id), None)
    mudancas.marcar_usuario(usuario_id)
    return p


# ── gatilhos do agente ───────────────────────────────────────────────────────
def _base(dev: dict, ctx=None) -> dict:
    return {"nome": (dev or {}).get("nome"), "predicao_id": (dev or {}).get("id")}


def apos_ferramenta(ctx, dev: dict, nome: str, args: dict, r: dict) -> None:
    """Chamada por agente/ferramentas.executar quando uma ferramenta deu certo."""
    try:
        _apos_ferramenta(ctx, dev or {}, nome, args or {}, r or {})
    except Exception as e:                        # nunca atrapalha a rodada do agente
        _registrar_falha(e)


def _apos_ferramenta(ctx, dev, nome, args, r) -> None:
    emp, caso_id, pid = ctx.caso["empresa_id"], ctx.caso.get("id"), dev.get("id")
    base, agora = _base(dev), getattr(ctx, "agora", None)
    devedor = ("devedor", pid)
    if nome == "transferir_para_humano":
        sinais = ((ctx.saida.get("triagem") or {}).get("sinais_de_risco") or []) if hasattr(ctx, "saida") else []
        if args.get("motivo") == "dificuldade_grave" and "sofrimento_grave" in sinais:
            notificar("N03", emp, devedor=dev, admins=True, contexto=base, chave=f"N03:{caso_id}:{r.get('compromisso_id')}",
                      entidade=devedor, agora=agora)
        else:
            notificar("N02", emp, devedor=dev, contexto={**base, "motivo": MOTIVO_TRANSFERENCIA.get(args.get("motivo"),
                      "o caso precisa de uma pessoa da equipe")}, chave=f"N02:{caso_id}:{r.get('compromisso_id')}",
                      entidade=devedor, agora=agora)
    elif nome == "marcar_atendimento_humano" and not r.get("ja_estava_marcado"):
        item, q = r.get("compromisso_id"), quando(r.get("data"), r.get("hora"), agora)
        if r.get("remarcado_de"):
            reuniao_remarcada(emp, item, dev, q, agora)
        else:
            notificar("N06", emp, devedor=dev, admins=True, contexto={**base, "quando": q},
                      chave=f"N06:{item}", entidade=("agenda", item), agora=agora)
    elif nome == "remarcar_compromisso":
        item = r.get("compromisso_id")
        if r.get("o_que") == "atendimento com uma pessoa da equipe":
            reuniao_remarcada(emp, item, dev, quando(r.get("data"), r.get("hora"), agora), agora)
        else:
            resolver(emp, "agenda", item, ("N14", "N16"))       # lembretes do horário antigo
    elif nome == "desmarcar_compromisso" and r.get("o_que") == "atendimento com uma pessoa da equipe":
        era = r.get("era") or {}
        _enfileirar(_reuniao_desmarcada, emp, r.get("compromisso_id"), dict(dev),
                    quando(era.get("data"), era.get("hora"), agora), agora)
    elif nome == "registrar_pagamento_informado":
        notificar("N18", emp, devedor=dev, contexto=base, chave=f"N18:{caso_id}:{args.get('data')}",
                  entidade=devedor, agora=agora)
    elif nome == "registrar_aceite":
        dia = (agora or datetime.now(timezone.utc)).astimezone(BRASILIA).date().isoformat()
        notificar("N20", emp, devedor=dev, contexto=base, chave=f"N20:{dia}", agora=agora)
    elif nome == "marcar_promessa_quebrada":
        notificar("N21", emp, devedor=dev, contexto=base, chave=f"N21:{args.get('compromisso_id')}",
                  entidade=("agenda", args.get("compromisso_id")), agora=agora)
    elif nome == "abrir_contestacao":
        notificar("N22", emp, devedor=dev, admins=True, contexto=base, chave=f"N22:{caso_id}",
                  entidade=devedor, agora=agora)
    elif nome == "suspender_cobranca":
        pedido = ("diz que não é a pessoa procurada" if args.get("motivo") == "pessoa_errada"
                  else "pediu para não ser mais contatado")
        notificar("N23", emp, devedor=dev, contexto={**base, "pedido": pedido}, chave=f"N23:{caso_id}",
                  entidade=devedor, agora=agora)
    elif nome == "registrar_pedido_titular":
        from agente.juridico import sinais as _sinais
        tipo = args.get("tipo")
        prazo = ("Responda em até 15 dias." if tipo in ("acesso", "origem")
                 else "A pessoa responsável pelos dados analisa e responde.")
        dia = (agora or datetime.now(timezone.utc)).astimezone(BRASILIA).date().isoformat()
        notificar("N24", emp, devedor=dev, admins=True,
                  contexto={**base, "pedido": str(_sinais.ROTULO_PEDIDO.get(tipo, "pedido")).lower(), "prazo": prazo},
                  chave=f"N24:{caso_id}:{tipo}:{dia}", entidade=devedor, agora=agora)


def reuniao_remarcada(empresa_id: str, item_id, dev: dict, novo_quando: str, agora=None) -> None:
    _enfileirar(_reuniao_remarcada, str(empresa_id), str(item_id), dict(dev or {}), novo_quando, agora)


def _ultimo_atendente(empresa_id: str, item_id: str) -> list:
    """Quem recebeu a reunião por último (aviso N07 mais recente do compromisso)."""
    n07 = armazem().de_entidade(empresa_id, "agenda", item_id, ["N07"])
    n07.sort(key=lambda l: str(l.get("criado_em")), reverse=True)
    return [n07[0]["usuario_id"]] if n07 else []


def _reuniao_remarcada(empresa_id, item_id, dev, novo_quando, agora) -> None:
    atendente = _ultimo_atendente(empresa_id, item_id)
    armazem().resolver(empresa_id, "agenda", item_id, ["N06", "N07", "N08", "N10", "N11", "N12"])
    _gravar("N08", empresa_id, {**_base(dev), "quando": novo_quando}, f"N08:{item_id}:{novo_quando}",
            tuple(atendente), None, True, True, None, ("agenda", item_id), 1, None, agora)


def _reuniao_desmarcada(empresa_id, item_id, dev, era_quando, agora) -> None:
    atendente = _ultimo_atendente(empresa_id, item_id)
    armazem().resolver(empresa_id, "agenda", item_id)
    _gravar("N09", empresa_id, {**_base(dev), "quando": era_quando}, f"N09:{item_id}",
            tuple(atendente), None, True, True, None, ("agenda", item_id), 1, None, agora)


def reuniao_atribuida(empresa_id: str, item: dict, operador_id: str, agora=None) -> None:
    """O administrador aprovou a reunião e escolheu quem atende."""
    item = dict(item or {})
    resolver(empresa_id, "agenda", item.get("id"), ("N06", "N08", "N11"))
    notificar("N07", empresa_id, usuarios=[operador_id], ou_admins=False,
              contexto={"nome": item.get("nome"), "predicao_id": item.get("predicao_id"),
                        "quando": quando(item.get("data"), item.get("hora"), agora)},
              chave=f"N07:{item.get('id')}:{operador_id}:{item.get('data')}:{item.get('hora')}",
              entidade=("agenda", item.get("id")), agora=agora)


def mensagem_em_caso_da_equipe(ctx, dev: dict) -> None:
    """N01: o devedor escreveu num caso que está com a equipe (agrupa por caso).
    Vai para quem assumiu o caso; sem ninguém (ou se essa pessoa saiu), para o responsável."""
    try:
        caso = ctx.caso
        dev = {"id": dev.get("id"), "nome": dev.get("nome"), "responsavel_id": dev.get("responsavel_id")}
        _enfileirar(_mensagem_equipe, caso["empresa_id"], caso["id"], caso.get("situacao"),
                    str((caso.get("dados") or {}).get("assumido_por") or ""), dev, getattr(ctx, "agora", None))
    except Exception as e:
        _registrar_falha(e)


def _mensagem_equipe(empresa_id, caso_id, situacao, assumiu, dev, agora) -> list:
    contexto = {**_base(dev), "situacao": SITUACAO_DO_CASO.get(situacao, "com a equipe")}
    com_quem = assumiu if assumiu and assumiu in pessoas(empresa_id) else ""
    return _gravar("N01", empresa_id, contexto, f"N01:{caso_id}", (com_quem,) if com_quem else (),
                   None if com_quem else dev, False, True, None, ("devedor", dev.get("id")), 1, None, agora)


def _so_o_necessario(dev: dict | None) -> dict:
    d = dev or {}
    return {"id": d.get("id"), "nome": d.get("nome"), "responsavel_id": d.get("responsavel_id")}


def _hoje_s(agora=None) -> str:
    return _dia(agora or datetime.now(timezone.utc)).isoformat()


def caso_mudou_de_maos(empresa_id: str, predicao_id, acao: str, quem_id, anterior_id=None, agora=None) -> None:
    """N05: um administrador assumiu o caso ou o devolveu ao assistente. Avisa quem estava com ele
    e o responsável (nunca quem fez), e tira das pendências o que perdeu o sentido."""
    if not empresa_id or not predicao_id:
        return
    agora = agora or datetime.now(timezone.utc)
    _enfileirar(_caso_mudou, str(empresa_id), str(predicao_id), acao, str(quem_id or ""), anterior_id, agora)
    resolver(empresa_id, "devedor", predicao_id, ("N02", "N03") if acao == "assumir" else ("N01", "N28"))


def _caso_mudou(empresa_id, predicao_id, acao, quem_id, anterior_id, agora) -> list:
    from agente import api as agente_api
    dev = _so_o_necessario(agente_api.fabrica_fonte().devedor(empresa_id, predicao_id) or {"id": predicao_id})
    usuarios = tuple(u for u in (anterior_id, dev.get("responsavel_id")) if u)
    if not usuarios:
        return []
    nome = str((pessoas(empresa_id).get(quem_id) or {}).get("nome") or "").split(" ")[0]
    mudanca = (f"foi assumido por {nome}" if nome else "foi assumido por alguém da equipe") if acao == "assumir" \
        else "voltou para o assistente"
    return _gravar("N05", empresa_id, {**_base(dev), "mudanca": mudanca},
                   f"N05:{predicao_id}:{acao}:{agora.strftime('%Y%m%d%H%M')}", usuarios, None, False, False,
                   quem_id, ("devedor", predicao_id), 1, None, agora)


def link_telegram_em_outro_aparelho(empresa_id: str, predicao_id, agora=None) -> None:
    """N04: alguém abriu um link do Telegram já usado, de outro aparelho."""
    if empresa_id and predicao_id:
        _enfileirar(_telegram_outro, str(empresa_id), str(predicao_id), agora)


def _telegram_outro(empresa_id, predicao_id, agora) -> list:
    from agente import api as agente_api
    dev = _so_o_necessario(agente_api.fabrica_fonte().devedor(empresa_id, predicao_id) or {"id": predicao_id})
    return _gravar("N04", empresa_id, _base(dev), f"N04:{predicao_id}:{_hoje_s(agora)}", (), dev, True, True, None,
                   ("devedor", predicao_id), 1, None, agora)


def pagamento_parcial(ctx, dev: dict, item: dict) -> None:
    """N13: o assistente deixou na agenda um pagamento parcial para conferir a baixa."""
    try:
        notificar("N13", ctx.caso["empresa_id"], devedor=dev, contexto=_base(dev), chave=f"N13:{item['id']}",
                  entidade=("agenda", item["id"]), agora=getattr(ctx, "agora", None))
    except Exception as e:
        _registrar_falha(e)


def pagamento_confirmado(empresa_id: str, promessas: list, ator_id=None, agora=None) -> None:
    """N19: a baixa de um pagamento cumpriu promessas (as linhas que a baixa devolveu). Avisa o dono
    da promessa (sem dono pessoa: os administradores) e resolve os avisos dela."""
    vistos = set()
    for p in promessas or []:
        compromisso_resolvido(empresa_id, p)
        pid = p.get("predicao_id")
        if not pid or pid in vistos:
            continue
        vistos.add(pid)
        dono = p.get("operador_id")
        notificar("N19", empresa_id, usuarios=[dono] if dono and dono not in DONOS_QUE_NAO_SAO_PESSOAS else (),
                  exceto=ator_id, contexto={"nome": p.get("nome"), "predicao_id": pid},
                  chave=f"N19:{_hoje_s(agora)}", agora=agora)


def devedores_recebidos(empresa_id: str, operador_id, quantidade: int, ator_id=None, agora=None) -> None:
    """N26: a fila foi distribuída ou o responsável trocou (soma o dia todo num aviso só)."""
    if operador_id and int(quantidade or 0) > 0:
        notificar("N26", empresa_id, usuarios=[operador_id], ou_admins=False, exceto=ator_id,
                  quantidade=int(quantidade), chave=f"N26:{_hoje_s(agora)}", agora=agora)


def duvida_respondida(empresa_id: str, autor_id, duvida_id, respondida_em) -> None:
    """N29: a equipe Mizan respondeu a dúvida de alguém (responder de novo avisa de novo)."""
    if autor_id and duvida_id:
        notificar("N29", empresa_id, usuarios=[autor_id], ou_admins=False,
                  chave=f"N29:{duvida_id}:{respondida_em}", entidade=("duvida", duvida_id))


_IA_OCUPADA: dict = {}      # empresa -> (desde quando a IA está ocupada, último aviso de IA ocupada)


def agente_parado(empresa_id: str, categoria: str, agora=None) -> None:
    """N30, chamado por agente/logs.registrar: só o que para o agente da empresa inteira."""
    if not empresa_id or empresa_id == "sistema" or categoria not in ("teto_ia", "ia_aguardando", "evento_falhou"):
        return
    agora = agora or datetime.now(timezone.utc)
    local = agora.astimezone(BRASILIA)
    if categoria == "teto_ia":
        notificar("N30", empresa_id, admins=True, contexto={"variante": "teto"},
                  chave=f"N30:teto:{local.date().isoformat()}", agora=agora)
    elif categoria == "ia_aguardando":
        desde, ultimo = _IA_OCUPADA.get(empresa_id, (agora, agora))
        if agora - ultimo > timedelta(minutes=5):
            desde = agora                                   # a IA tinha voltado: conta de novo
        _IA_OCUPADA[empresa_id] = (desde, agora)
        if agora - desde >= timedelta(minutes=15):
            notificar("N30", empresa_id, admins=True, contexto={"variante": "ia"},
                      chave=f"N30:ia:{local.strftime('%Y-%m-%dT%H')}", agora=agora)
    else:
        notificar("N30", empresa_id, admins=True, contexto={"variante": "falhas"},
                  chave=f"N30:falhas:{local.strftime('%Y-%m-%dT%H')}", agora=agora)


def sincronizacao_falhou(empresa_id: str, conexao_id, agora=None) -> None:
    """N31: a sincronização automática de uma conexão falhou (um aviso por conexão por dia)."""
    if empresa_id and conexao_id:
        notificar("N31", empresa_id, admins=True, chave=f"N31:{conexao_id}:{_hoje_s(agora)}", agora=agora)


def recomendacao_do_cientista(empresa_id: str, rec_id, exceto=None) -> None:
    if rec_id:
        notificar("N32", empresa_id, admins=True, exceto=exceto, chave=f"N32:rec:{rec_id}")


def experimento_parado(empresa_id: str, experimento_id) -> None:
    if experimento_id:
        notificar("N32", empresa_id, admins=True, contexto={"variante": "dano"}, chave=f"N32:dano:{experimento_id}")


def seguranca(empresa_id: str, variante: str, usuario_id=None, pessoa_nome: str = "", agora=None) -> None:
    """N33. 2fa_pessoa vai para a própria pessoa; 2fa_admin, senha_2fa e bloqueio, para os
    administradores (menos a própria pessoa)."""
    if not empresa_id or variante not in CATALOGO["N33"].variantes:
        return
    agora = agora or datetime.now(timezone.utc)
    marca = agora.astimezone(BRASILIA).strftime("%Y-%m-%dT%H")
    if variante == "2fa_pessoa":
        notificar("N33", empresa_id, usuarios=[usuario_id], ou_admins=False, contexto={"variante": variante},
                  chave=f"N33:{variante}:{usuario_id}:{marca}", agora=agora)
    else:
        notificar("N33", empresa_id, admins=True, exceto=usuario_id,
                  contexto={"variante": variante, "pessoa": str(pessoa_nome or "uma pessoa da equipe").strip()},
                  chave=f"N33:{variante}:{usuario_id}:{marca}", agora=agora)


# ── relógio ──────────────────────────────────────────────────────────────────
_RODOU: dict = {}          # (tarefa, dia) já rodada hoje neste servidor (a chave do aviso cobre reinícios)
_ULTIMO: dict = {}         # tarefa -> última vez que rodou


def _dia(agora: datetime) -> date:
    return agora.astimezone(BRASILIA).date()


def _inicio(a: dict) -> datetime | None:
    try:
        h = _hora(a.get("hora"))
        return datetime.combine(date.fromisoformat(str(a.get("data"))[:10]),
                                dtime(int(h[:2]), int(h[3:5])), BRASILIA)
    except (ValueError, TypeError):
        return None


def _tipo_do_item(a: dict) -> str:
    obs = a.get("observacao") or ""
    if not a.get("predicao_id"):
        return "tarefa"
    if a.get("tipo") == "promessa":
        return "promessa"
    if obs.startswith(PREFIXO_ATENDIMENTO):
        return "atendimento"
    if obs.startswith(PREFIXO_RETORNO_ASSISTENTE):
        return "retorno_do_assistente"
    return "retorno"


def _pessoa(empresa_id: str, uid) -> bool:
    return str(uid or "") in pessoas(empresa_id)


LEMBRETE_VALE_ATE = timedelta(minutes=30)      # meia hora depois do horário, o lembrete sai da lista
TIPOS_DO_DIA = ("N15", "N16", "N17", "N27", "N30", "N31")   # resumos e alertas que valem só para o dia


def _lembretes_que_passaram(empresa_id: str, item_id: str, marca: str) -> None:
    """O horário passou: "reunião em 5 minutos", "sem atendente" e "retorno às 10:00" saem da lista.
    Uma vez por compromisso e horário neste servidor (o relógio passa por ele a cada minuto)."""
    chave = (empresa_id, f"passou:{item_id}:{marca}")
    if chave in _GRAVADAS:
        return
    _GRAVADAS.add(chave)
    resolver(empresa_id, "agenda", item_id, ("N10", "N11", "N14", "ESC"))


def virada_do_dia(agora: datetime) -> int:
    """Resumos e alertas de dias anteriores (agenda do dia, atrasados, agente parado...) saem da lista."""
    inicio = datetime.combine(_dia(agora), dtime(0, 0), BRASILIA).astimezone(timezone.utc).isoformat()
    linhas = armazem().resolver_antigas(TIPOS_DO_DIA, inicio)
    for uid in {l.get("usuario_id") for l in linhas if l.get("usuario_id")}:
        mudancas.marcar_usuario(uid)
    return len(linhas)


def lembretes(agora: datetime) -> int:
    """N10, N11, N12 e N14: compromissos com hora marcada de ontem a amanhã."""
    hoje = _dia(agora)
    dias = [(hoje + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]
    n = 0
    for a in armazem().agenda_com_hora(dias):
        inicio, emp = _inicio(a), a.get("empresa_id") or ""
        if inicio is None or not emp:
            continue
        falta, t, item = inicio - agora, _tipo_do_item(a), a["id"]
        marca = f"{str(a.get('data'))[:10]}:{_hora(a.get('hora'))}"
        ctx = {"nome": a.get("nome"), "predicao_id": a.get("predicao_id"), "hora": _hora(a.get("hora"))}
        ent = ("agenda", item)
        if falta <= -LEMBRETE_VALE_ATE:
            _lembretes_que_passaram(emp, item, marca)
        if t == "atendimento" and a.get("operador_id") == A_DEFINIR:
            if timedelta(0) < falta <= timedelta(hours=2):
                notificar("N11", emp, admins=True, contexto=ctx, chave=f"N11:{item}:{marca}", entidade=ent, agora=agora)
                n += 1
        elif t == "atendimento":
            if timedelta(minutes=-1) < falta <= timedelta(minutes=5):
                notificar("N10", emp, usuarios=[a.get("operador_id")], contexto={**ctx, "minutos": 5},
                          chave=f"N10:{item}:{marca}:5", entidade=ent, prioridade="urgente", agora=agora)
                n += 1
            elif timedelta(minutes=5) < falta <= timedelta(minutes=30):
                notificar("N10", emp, usuarios=[a.get("operador_id")], contexto={**ctx, "minutos": 30},
                          chave=f"N10:{item}:{marca}:30", entidade=ent, agora=agora)
                n += 1
            elif timedelta(hours=-12) <= falta <= timedelta(minutes=-30):
                notificar("N12", emp, usuarios=[a.get("operador_id")], contexto=ctx, chave=f"N12:{item}:{marca}",
                          entidade=ent, agora=agora)
                n += 1
        elif t == "retorno" and _pessoa(emp, a.get("operador_id")) and timedelta(0) < falta <= timedelta(minutes=15):
            notificar("N14", emp, usuarios=[a.get("operador_id")], ou_admins=False, contexto=ctx,
                      chave=f"N14:{item}:{marca}", entidade=ent, agora=agora)
            n += 1
    return n


def escalar(agora: datetime) -> int:
    """Urgente sem leitura em 15 min vai também para os administradores que ainda não o receberam."""
    arm, n = armazem(), 0
    for l in arm.urgentes_sem_leitura((agora - timedelta(hours=6)).isoformat(), (agora - ESCALAR_APOS).isoformat()):
        emp = l.get("empresa_id") or ""
        gente = pessoas(emp)
        quem = gente.get(str(l.get("usuario_id")))
        arm.atualizar(l["id"], {"escalada_em": agora.isoformat()})
        if l.get("tipo") == "ESC" or quem is None or quem["role"] == "admin":
            continue
        ja = set()
        if l.get("entidade"):
            ja = {x["usuario_id"] for x in arm.de_entidade(emp, l["entidade"], l.get("entidade_id"))
                  if not x.get("resolvida_em")}
        admins = [i for i, p in gente.items() if p["role"] == "admin" and i not in ja]
        if not admins:
            continue
        tipo = CATALOGO.get(l.get("tipo"))
        contexto = {"titulo_original": l.get("titulo"), "texto_original": l.get("texto") or "",
                    "link_original": l.get("link") or "/inicio",
                    "acao_original": (tipo.acao if tipo and "{" not in tipo.acao else "Abrir")}
        _enfileirar(_gravar, "ESC", emp, contexto, f"ESC:{l['id']}", tuple(admins), None, False, False, None,
                    (l.get("entidade"), l.get("entidade_id")) if l.get("entidade") else None, 1, None, agora)
        n += 1
    return n


def sem_resposta(agora: datetime) -> int:
    """N28: mensagem do devedor esperando a equipe há mais de 2 horas."""
    n = 0
    for a in armazem().avisos_de_mensagem((agora - timedelta(hours=26)).isoformat(),
                                          (agora - timedelta(hours=2)).isoformat()):
        emp = a.get("empresa_id") or ""
        try:
            chegou = datetime.fromisoformat(str(a.get("created_at")).replace("Z", "+00:00"))
            hora = chegou.astimezone(BRASILIA).strftime("%H:%M")
        except ValueError:
            hora = ""
        dono = a.get("operador_id")
        notificar("N28", emp, usuarios=[dono] if _pessoa(emp, dono) else (), contexto={
            "nome": a.get("nome"), "predicao_id": a.get("predicao_id"), "hora": hora},
            chave=f"N28:{a['id']}", entidade=("devedor", a.get("predicao_id")), agora=agora)
        n += 1
    return n


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _dia_util_anterior(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def manha(agora: datetime) -> int:
    """8h: N15 (agenda do dia de cada pessoa e resumo da equipe) e N27 (tarefas de hoje)."""
    hoje = _dia(agora)
    hoje_s = hoje.isoformat()
    por_empresa: dict = {}
    for a in armazem().agenda_ate(hoje_s):
        if a.get("empresa_id"):
            por_empresa.setdefault(a["empresa_id"], []).append(a)
    n = 0
    for emp, itens in por_empresa.items():
        gente = pessoas(emp)
        if not gente:
            continue
        conta: dict = {}
        sem_atendente = 0
        tarefas: dict = {}
        for a in itens:
            t, dono, dia = _tipo_do_item(a), str(a.get("operador_id") or ""), str(a.get("data"))[:10]
            if t == "tarefa":
                if dia == hoje_s and dono in gente:
                    tarefas.setdefault(dono, []).append(a)
                continue
            if t == "atendimento" and dono == A_DEFINIR and dia == hoje_s:
                sem_atendente += 1
            if dono not in gente or t == "retorno_do_assistente":
                continue
            c = conta.setdefault(dono, {"hoje": 0, "hora": 0, "atrasados": 0})
            if dia == hoje_s:
                c["hoje"] += 1
                c["hora"] += 1 if a.get("hora") else 0
            else:
                c["atrasados"] += 1
        for uid, c in conta.items():
            if gente[uid]["role"] != "operador" or not (c["hoje"] or c["atrasados"]):
                continue
            partes = [f"Hoje: {_plural(c['hoje'], 'compromisso', 'compromissos')}"
                      + (f" ({c['hora']} com hora marcada)" if c["hora"] else "") + "."]
            if c["atrasados"]:
                partes.append(f"Atrasados: {c['atrasados']}.")
            notificar("N15", emp, usuarios=[uid], ou_admins=False, contexto={"resumo": " ".join(partes)},
                      chave=f"N15:{hoje_s}:{uid}", agora=agora)
            n += 1
        total_hoje = sum(c["hoje"] for c in conta.values())
        total_atrasados = sum(c["atrasados"] for c in conta.values())
        if total_hoje or total_atrasados or sem_atendente:
            partes = [f"Equipe hoje: {_plural(total_hoje, 'compromisso', 'compromissos')}."]
            if total_atrasados:
                partes.append(f"Atrasados: {total_atrasados}.")
            if sem_atendente:
                partes.append(f"{_plural(sem_atendente, 'reunião espera', 'reuniões esperam')} atendente.")
            notificar("N15", emp, admins=True, contexto={"resumo": " ".join(partes)}, chave=f"N15:{hoje_s}:equipe",
                      agora=agora)
            n += 1
        for uid, lista in tarefas.items():
            notificar("N27", emp, usuarios=[uid], ou_admins=False, quantidade=len(lista),
                      contexto={"tarefa": lista[0].get("nome") or "tarefa da empresa"},
                      chave=f"N27:{hoje_s}:{uid}", agora=agora)
            n += 1
    return n


def nove_horas(agora: datetime) -> int:
    """9h: N16 (promessas vencidas ontem), N17 (atrasados da equipe) e N25 (prazos de pedidos de dados)."""
    hoje = _dia(agora)
    ontem, hoje_s = (hoje - timedelta(days=1)).isoformat(), hoje.isoformat()
    corte = _dia_util_anterior(hoje).isoformat()
    por_empresa: dict = {}
    for a in armazem().agenda_ate(hoje_s):
        if a.get("empresa_id"):
            por_empresa.setdefault(a["empresa_id"], []).append(a)
    n = 0
    for emp, itens in por_empresa.items():
        gente = pessoas(emp)
        if not gente:
            continue
        vencidas: dict = {}
        atrasados: dict = {}
        for a in itens:
            t, dono, dia = _tipo_do_item(a), str(a.get("operador_id") or ""), str(a.get("data"))[:10]
            if t == "promessa" and dia == ontem and dono in gente:
                vencidas.setdefault(dono, []).append(a)
            if t in ("retorno", "atendimento", "promessa") and dono in gente and dia < corte:
                atrasados[dono] = atrasados.get(dono, 0) + 1
            if (a.get("observacao") or "").startswith(PREFIXO_PEDIDO) and "15 dias" in (a.get("observacao") or ""):
                n += _prazo_lgpd(emp, a, hoje, agora)
        for uid, lista in vencidas.items():
            um = lista[0]
            notificar("N16", emp, usuarios=[uid], ou_admins=False, quantidade=len(lista),
                      contexto={"nome": um.get("nome"), "predicao_id": um.get("predicao_id")},
                      chave=f"N16:{hoje_s}:{uid}", entidade=("agenda", um["id"]) if len(lista) == 1 else None,
                      agora=agora)
            n += 1
        total = sum(atrasados.values())
        if total:
            maiores = sorted(atrasados.items(), key=lambda kv: -kv[1])[:4]
            detalhe = " · ".join(f"{gente[u]['nome'].split(' ')[0] or 'Sem nome'}: {q}" for u, q in maiores)
            notificar("N17", emp, admins=True, quantidade=total, contexto={"detalhe": detalhe},
                      chave=f"N17:{hoje_s}", agora=agora)
            n += 1
    return n


def _prazo_lgpd(emp: str, a: dict, hoje: date, agora: datetime) -> int:
    try:
        criado = datetime.fromisoformat(str(a.get("created_at")).replace("Z", "+00:00")).astimezone(BRASILIA).date()
    except ValueError:
        return 0
    prazo = criado + timedelta(days=15)
    ctx = {"nome": a.get("nome"), "predicao_id": a.get("predicao_id")}
    if hoje >= prazo:
        notificar("N25", emp, admins=True, contexto={**ctx, "vence": "vence hoje" if hoje == prazo else "venceu"},
                  chave=f"N25:{a['id']}:dia", entidade=("agenda", a["id"]), prioridade="urgente", agora=agora)
        return 1
    if hoje >= prazo - timedelta(days=3):
        faltam = (prazo - hoje).days
        notificar("N25", emp, admins=True, contexto={**ctx, "vence": f"vence em {faltam} dias" if faltam > 1 else "vence amanhã"},
                  chave=f"N25:{a['id']}:3d", entidade=("agenda", a["id"]), agora=agora)
        return 1
    return 0


def resumos_por_email(agora: datetime, enviar=None) -> int:
    """8h: resumo por e-mail para quem ligou a opção. Só contagens: nada do devedor."""
    if enviar is None:
        from email_utils import enviar_email as enviar
    hoje_s, arm, n = _dia(agora).isoformat(), armazem(), 0
    for p in arm.com_resumo_por_email():
        if str(p.get("resumo_enviado_em") or "")[:10] == hoje_s:
            continue
        uid, emp = str(p.get("usuario_id")), p.get("empresa_id") or ""
        pessoa = pessoas(emp).get(uid)
        if not pessoa or not pessoa.get("email"):
            continue
        abertas = arm.abertas(uid, emp)
        if abertas:
            por_cat: dict = {}
            for a in abertas:
                por_cat[a.get("categoria")] = por_cat.get(a.get("categoria"), 0) + 1
            linhas = "".join(f"<li>{ROTULO_CATEGORIA.get(c, c)}: {q}</li>" for c, q in sorted(por_cat.items()))
            if enviar(pessoa["email"], "Seu resumo do dia no Mizan", _email_resumo(pessoa["nome"], len(abertas), linhas)):
                n += 1
        arm.marcar_resumo_enviado(uid, hoje_s)
    return n


def _email_resumo(nome: str, total: int, linhas: str) -> str:
    from html import escape
    try:
        from email_utils import CABECALHO_MARCA
    except Exception:
        CABECALHO_MARCA = ""
    url = os.getenv("FRONTEND_URL", "https://mizan-sand.vercel.app")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">{CABECALHO_MARCA}</div>
      <h2 style="color:#1e293b">Bom dia, {escape(primeiro_nome(nome))}!</h2>
      <p style="color:#475569">Você tem {total} {'aviso aberto' if total == 1 else 'avisos abertos'} no Mizan:</p>
      <ul style="color:#475569">{linhas}</ul>
      <div style="text-align:center;margin:28px 0">
        <a href="{escape(url)}/inicio" style="background:#2563eb;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">Abrir o Mizan</a>
      </div>
      <p style="color:#94a3b8;font-size:13px">Você recebe este resumo porque ligou o resumo por e-mail nas
      preferências de notificação. Para parar, desligue lá.</p>
    </div>"""


GUARDAR_RESOLVIDAS = timedelta(days=7)
GUARDAR_LIDAS = timedelta(days=30)
GUARDAR_TODAS = timedelta(days=90)


def limpar(agora: datetime) -> int:
    """Apaga o que não serve mais: resolvidas há 7 dias, lidas há 30, qualquer uma com mais de 90."""
    return armazem().limpar((agora - GUARDAR_RESOLVIDAS).isoformat(), (agora - GUARDAR_LIDAS).isoformat(),
                            (agora - GUARDAR_TODAS).isoformat())


def _na_janela_e_pendente(nome: str, agora: datetime, de: int, ate: int) -> bool:
    local = agora.astimezone(BRASILIA)
    return de <= local.hour < ate and (nome, local.date().isoformat()) not in _RODOU


def _marcar_feita(nome: str, agora: datetime) -> None:
    _RODOU[(nome, agora.astimezone(BRASILIA).date().isoformat())] = True
    if len(_RODOU) > 100:
        for k in sorted(_RODOU)[:50]:
            _RODOU.pop(k, None)


def relogio(agora: datetime | None = None) -> dict:
    """Um passo por minuto, chamado pelo agendador. Nunca levanta erro."""
    if not ligado() or disjuntor_aberto():
        return {}
    agora = agora or datetime.now(timezone.utc)
    feito: dict = {}
    passos = [("lembretes", lembretes), ("escalados", escalar)]
    ultimo = _ULTIMO.get("sem_resposta")
    if ultimo is None or agora - ultimo >= timedelta(minutes=5) or agora < ultimo:
        _ULTIMO["sem_resposta"] = agora
        passos.append(("sem_resposta", sem_resposta))
    for nome, fn in passos:
        r = _seguro(fn, agora)
        if r is not None:
            feito[nome] = r
    # Uma vez por dia, dentro da janela. Só conta como feita quando deu certo: banco fora às
    # 8h tenta de novo no minuto seguinte (as chaves dos avisos não deixam repetir).
    for rodada, de, ate, fns in (("manha", 8, 12, (("manha", manha), ("emails", resumos_por_email))),
                                 ("nove", 9, 18, (("nove", nove_horas),)),
                                 ("virada", 0, 24, (("virada", virada_do_dia),)),
                                 ("limpeza", 3, 6, (("limpeza", limpar),))):
        if not _na_janela_e_pendente(rodada, agora, de, ate):
            continue
        certo = True
        for nome, fn in fns:
            r = _seguro(fn, agora)
            if r is None:
                certo = False
            else:
                feito[nome] = r
        if certo:
            _marcar_feita(rodada, agora)
    return feito
