"""Orquestrador dos agentes (docs/PLANO_EXECUCAO_AGENTES.md, 3.0, 4 e 5).

Código, não IA. É dono do estado do caso e decide quem age e quando:

- Fila de eventos com prioridade: pedido para parar e contestação passam na
  frente de mensagem, que passa na frente de pagamento, datas e relógio.
- Idempotência: cada evento tem uma chave; o mesmo evento duas vezes vira um só.
- Um por vez por caso: trava com prazo no próprio caso, no relógio real, com um
  dono por execução e renovada a cada checkpoint.
- Grafo: nós (funções) ligados por arestas fixas ou condicionais, como no
  LangGraph, sem a dependência.
- Checkpoint por evento: depois de cada nó o estado é gravado, com o que os nós
  seguintes precisam do rascunho (texto, triagem, resposta); se o processo cair
  ou a IA pedir espera, o mesmo evento recomeça do nó seguinte ao último
  concluído, com o rascunho de volta. Outro evento do caso não apaga esse.
- Espera sem tirar o caso do agente: IA ocupada (cota, rede) adia o evento;
  teto de gasto do dia adia até a meia-noite de Brasília.
- Nó de erro: nó que falha tenta mais uma vez; falhou de novo, o caso vai para
  uma pessoa com o motivo registrado.
- Evento que quebra fora do grafo (banco fora do ar, por exemplo) volta para a
  fila; na segunda falha vira "falhou" e aparece na Central. Evento preso em
  "processando" (o processo morreu) volta sozinho quando a reserva vence.

Os nós precisam ser seguros para rodar de novo: uma ação com efeito fora do
Mizan (enviar mensagem) usa a sua própria chave de idempotência.
"""
import json
import os
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from agente import auditor, estado, llm
from agente.rastreio import Rastreio, novo_trace_id
from agente.repositorio import PRONTO_JA, EventoDuplicado

FIM = "FIM"

PRIORIDADE = {
    "pedido_parar": 100,
    "contestacao": 90,
    "mensagem_devedor": 80,
    "pagamento": 60,
    "vencimento": 40,
    "relogio": 20,
}

MAX_FALHAS_EVENTO = 2               # na segunda falha o evento vira "falhou"
TENTATIVAS_POR_NO = 2               # a primeira e mais uma
MAX_PASSOS = 30                     # um grafo que passa disso está em laço
DURACAO_TRAVA = timedelta(minutes=5)
ESPERA_NOVA_TENTATIVA = timedelta(minutes=1)

# Máquina e processo. Cada execução ganha um sufixo próprio (novo_dono): a thread
# do agendador e a da rota rodam no mesmo processo e não podem dividir a trava.
DONO = f"{socket.gethostname()}:{os.getpid()}"

# Erros em que tentar de novo não muda nada: vão direto para uma pessoa.
_SEM_NOVA_TENTATIVA = (llm.PrecoDesconhecido, estado.TransicaoProibida)
MAX_ESPERAS_IA = 5                   # cota estourada: até 5 esperas por evento; depois, uma pessoa
MAX_CHECKPOINTS = 10                 # eventos do caso com checkpoint guardado ao mesmo tempo


def novo_dono() -> str:
    return f"{DONO}:{uuid.uuid4().hex[:12]}"


def agora_real() -> datetime:
    """Relógio de verdade, para a trava. O `agora` do evento pode ser o da demo
    ou o de um teste; a trava protege processos reais e usa o relógio real."""
    return datetime.now(timezone.utc)


def proxima_meia_noite(agora: datetime) -> datetime:
    """Meia-noite de Brasília seguinte a `agora` (quando o teto do dia zera)."""
    amanha = agora.astimezone(auditor.BRASILIA).date() + timedelta(days=1)
    return datetime(amanha.year, amanha.month, amanha.day, tzinfo=auditor.BRASILIA)


class LacoNoGrafo(RuntimeError):
    pass


@dataclass
class No:
    nome: str
    funcao: object                   # (ctx) -> None
    agente: str = "codigo"
    seguinte: object = FIM           # nome do próximo nó ou (ctx) -> nome


class Grafo:
    def __init__(self, nome: str, inicio: str):
        self.nome = nome
        self.inicio = inicio
        self.nos: dict = {}
        # Chamado depois do nó de erro (ex.: avisar o devedor que uma pessoa assume).
        self.ao_falhar = None

    def no(self, nome: str, funcao, agente: str = "codigo", seguinte=FIM) -> "Grafo":
        if nome == FIM or nome in self.nos:
            raise ValueError(f"nó inválido ou repetido: {nome}")
        self.nos[nome] = No(nome, funcao, agente, seguinte)
        return self

    def proximo(self, no: No, ctx) -> str:
        nome = no.seguinte(ctx) if callable(no.seguinte) else no.seguinte
        if nome != FIM and nome not in self.nos:
            raise ValueError(f"{no.nome} apontou para nó inexistente: {nome}")
        return nome

    def validar(self) -> None:
        if self.inicio not in self.nos:
            raise ValueError(f"grafo {self.nome}: nó inicial {self.inicio} não existe")
        for no in self.nos.values():
            if not callable(no.seguinte) and no.seguinte != FIM and no.seguinte not in self.nos:
                raise ValueError(f"grafo {self.nome}: {no.nome} aponta para {no.seguinte}")


@dataclass
class Contexto:
    caso: dict
    evento: dict
    repo: object
    rastreio: Rastreio
    cliente: object
    hoje: object
    agora: object = None
    saida: dict = field(default_factory=dict)       # rascunho entre nós deste evento

    def mudar_situacao(self, nova: str, por: str = "agente") -> None:
        self.caso["situacao"] = estado.mudar(self.caso["situacao"], nova, por)

    @property
    def pode_falar(self) -> bool:
        return estado.pode_falar(self.caso["situacao"])

    def politica(self) -> tuple:
        """(regras, versão) da política ativa da empresa; (None, None) se não houver
        ou se a gravada for inválida — aí o Auditor só deixa passar segurança."""
        if "_politica" not in self.saida:
            achada = self.repo.politica_ativa(self.caso["empresa_id"])
            try:
                self.saida["_politica"] = ((auditor.validar_politica(achada["regras"]), achada["versao"])
                                           if achada else (None, None))
            except ValueError:
                self.saida["_politica"] = (None, None)
        return self.saida["_politica"]

    def auditar(self, acao: dict, contatos_7d: int = 0, simulacao: dict | None = None, ironia: bool = False) -> dict:
        """Passa a ação pelo Auditor e registra a decisão como um passo do rastreio."""
        regras, versao = self.politica()
        with self.rastreio.span("auditor", "auditor") as p:
            d = auditor.auditar(acao, self.caso, regras, versao, self.agora,
                                contatos_7d=contatos_7d, simulacao=simulacao, ironia=ironia)
            p["regra"], p["versao_politica"] = d["regra"], d["versao_politica"]
            p["detalhe"] = {"acao": (acao or {}).get("tipo"), "permitida": d["permitida"], "motivo": d.get("motivo")}
            if not d["permitida"]:
                p["resultado"] = "bloqueado"
        self.caso["versao_politica"] = versao
        return d

    def ia(self, papel: str, sistema: str, mensagens: list, ferramentas=None, max_tokens: int = 1024):
        """Chama a IA com teto de custo do dia e soma tokens e custo ao passo atual."""
        em_andamento = self.rastreio.atual["custo_usd"] if self.rastreio.atual else 0.0
        llm.conferir_teto(self.repo.custo_do_dia(self.caso["empresa_id"], self.hoje) + em_andamento)
        r = self.cliente.gerar(sistema=sistema, mensagens=mensagens, modelo=llm.modelo_para(papel),
                               ferramentas=ferramentas, max_tokens=max_tokens, papel=papel)
        self.rastreio.somar_ia(r)
        return r

    def anotar(self, agente: str, decisao: str, motivo: str = "") -> None:
        estado.anotar(self.caso, agente, decisao, motivo, trace_id=self.rastreio.trace_id, quando=self.agora)

    def ia_ou_codigo(self, papel: str, gerar, reserva):
        """Decisão de um agente com IA e caminho em código.

        `gerar()` usa a IA; `reserva()` é o que o sistema faz sem ela. A reserva
        vale quando o agente está desligado (MIZAN_IA_PAPEIS), a IA falha, o teto
        do dia acaba ou a resposta não serve (gerar levanta ValueError). O passo
        atual registra a origem e o motivo.
        """
        motivo = None
        if not llm.ia_ligada(papel):
            motivo = "desligado"
        else:
            try:
                resultado = gerar()
                self._marcar_origem("ia", None)
                return resultado
            except llm.TetoExcedido:
                motivo = "teto do dia"
            except (llm.SemRoteiro, llm.PrecoDesconhecido, ValueError, KeyError, TypeError) as e:
                motivo = type(e).__name__
            except Exception as e:                       # falha da IA (rede, cota): o código segue
                motivo = type(e).__name__
        self._marcar_origem("codigo", motivo)
        return reserva()

    def _marcar_origem(self, origem: str, motivo):
        if self.rastreio.atual is not None:
            extra = {"origem": origem}
            if motivo:
                extra["sem_ia"] = motivo
            self.rastreio.atual["detalhe"] = {**self.rastreio.atual.get("detalhe", {}), **extra}


def registrar_evento(repo, empresa_id: str, caso_id: str, tipo: str, chave: str,
                     dados: dict | None = None, origem: str = "sistema",
                     disponivel_em: datetime | None = None, agora: datetime | None = None) -> tuple:
    """Põe um evento na fila. Devolve (evento, novo); repetido devolve o que já existe.

    A data em que fica pronto vai sempre explícita, do app: `disponivel_em`, ou o
    `agora` de quem registra, ou "pronto já". Nunca o DEFAULT NOW() do banco, que
    fica depois do `agora` que o chamador calculou e passa para processar_fila.
    """
    evento = {"empresa_id": empresa_id, "caso_id": caso_id, "tipo": tipo, "chave": chave,
              "origem": origem, "prioridade": PRIORIDADE.get(tipo, 50), "dados": dados or {},
              "disponivel_em": disponivel_em or agora or PRONTO_JA}
    try:
        return repo.inserir_evento(evento), True
    except EventoDuplicado:
        return repo.evento_por_chave(empresa_id, chave), False


def _transferir(ctx: Contexto, motivo: str) -> None:
    """Nó de erro: o caso vai para uma pessoa, com o motivo."""
    with ctx.rastreio.span("erro", "orquestrador") as p:
        p["detalhe"] = {"motivo": motivo}
        if ctx.caso["situacao"] not in estado.SO_PESSOA_TIRA | estado.FINAIS:
            ctx.mudar_situacao("com_pessoa")


def _ler_checkpoint(caso: dict, evento_id) -> dict | None:
    """Checkpoint deste evento: {"proximo": nó, "saida": rascunho}, ou None."""
    dados = caso.get("dados") or {}
    ck = (dados.get("_checkpoints") or {}).get(str(evento_id))
    if ck:
        return ck
    antigo = dados.get("_checkpoint") or {}          # formato antigo: um só por caso
    if antigo.get("evento_id") == evento_id:
        return {"proximo": antigo.get("proximo"), "saida": {}}
    return None


def _rascunho_para_guardar(saida: dict) -> dict:
    """O que os nós seguintes precisam de ctx.saida (texto, triagem, resposta...).

    Fica de fora o que começa com "_" (cache que se refaz, como a política e o
    devedor, que tem dado pessoal), o pedido de adiamento e o que não vira JSON.
    """
    guardar = {}
    for k, v in saida.items():
        if k.startswith("_") or k == "adiar_para":
            continue
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            continue
        guardar[k] = v
    return guardar


def _marcar_checkpoint(ctx: "Contexto", proximo: str) -> None:
    eid = str(ctx.evento["id"])
    dados = dict(ctx.caso.get("dados") or {})
    cks = {k: v for k, v in (dados.get("_checkpoints") or {}).items() if k != eid}
    while len(cks) >= MAX_CHECKPOINTS:              # sobra de evento que nunca voltou
        cks.pop(min(cks, key=lambda k: str(cks[k].get("em") or "")))
    cks[eid] = {"proximo": proximo, "saida": _rascunho_para_guardar(ctx.saida),
                "em": (ctx.agora or agora_real()).isoformat()}
    dados["_checkpoints"] = cks
    if (dados.get("_checkpoint") or {}).get("evento_id") == ctx.evento["id"]:
        dados.pop("_checkpoint")
    ctx.caso["dados"] = dados


def _limpar_checkpoint(ctx: "Contexto") -> None:
    """Evento terminou: some o checkpoint e a contagem de esperas dele (só dele)."""
    eid = str(ctx.evento["id"])
    dados = dict(ctx.caso.get("dados") or {})
    for chave in ("_checkpoints", "_esperas_ia"):
        resto = {k: v for k, v in (dados.get(chave) or {}).items() if k != eid}
        if resto:
            dados[chave] = resto
        else:
            dados.pop(chave, None)
    if (dados.get("_checkpoint") or {}).get("evento_id") == ctx.evento["id"]:
        dados.pop("_checkpoint")
    ctx.caso["dados"] = dados


def executar(grafo: Grafo, ctx: Contexto, dono: str = DONO) -> dict:
    """Roda o grafo para o evento do contexto, com checkpoint a cada nó."""
    ck = _ler_checkpoint(ctx.caso, ctx.evento["id"])
    if ck and (ck.get("proximo") == FIM or ck.get("proximo") in grafo.nos):
        atual = ck["proximo"]
        # O rascunho volta: sem ele o negociador da retomada receberia mensagem vazia.
        ctx.saida.update({k: v for k, v in (ck.get("saida") or {}).items() if k not in ctx.saida})
    else:
        atual = grafo.inicio
    passos = 0
    erro = None
    esperar_ia = None
    teto = False
    while atual != FIM:
        passos += 1
        if passos > MAX_PASSOS:
            erro = LacoNoGrafo.__name__
            break
        no = grafo.nos[atual]
        for tentativa in range(1, TENTATIVAS_POR_NO + 1):
            try:
                with ctx.rastreio.span(no.nome, no.agente) as p:
                    p["detalhe"] = {"tentativa": tentativa}
                    no.funcao(ctx)
                erro = None
                break
            except _SEM_NOVA_TENTATIVA as e:
                erro = type(e).__name__
                break
            except llm.TetoExcedido:
                teto = True
                break
            except llm.IaOcupada as e:
                esperar_ia = e.esperar_s
                break
            except Exception as e:
                erro = type(e).__name__
        if esperar_ia is not None or teto:
            break
        if erro:
            break
        try:
            atual = grafo.proximo(no, ctx)
        except Exception as e:                       # aresta para nó que não existe
            erro = type(e).__name__
            break
        _marcar_checkpoint(ctx, atual)
        _checkpoint(ctx, no.nome, dono)

    agora = ctx.agora or agora_real()
    if teto:
        # Gasto do dia no teto: espera o dia virar em Brasília, sem passar o caso
        # para uma pessoa (não é culpa do devedor nem do caso).
        _marcar_checkpoint(ctx, atual)
        ctx.saida["adiar_para"] = proxima_meia_noite(agora)
        with ctx.rastreio.span("aguardar_teto", "orquestrador") as p:
            p["detalhe"] = {"ate": ctx.saida["adiar_para"].isoformat()}
        _checkpoint(ctx, "aguardando teto do dia", dono)
        return {"ok": True, "erro": None, "situacao": ctx.caso["situacao"]}
    if esperar_ia is not None:
        # Cota da IA estourada: o evento volta para a fila e recomeça deste nó
        # depois da espera, sem contar como falha e sem tirar o caso do agente.
        dados = dict(ctx.caso.get("dados") or {})
        esperas = dict(dados.get("_esperas_ia") or {})
        eid = str(ctx.evento["id"])
        n = int(esperas.get(eid) or 0) + 1
        if n <= MAX_ESPERAS_IA:
            esperas[eid] = n                         # por evento: um não zera a conta do outro
            dados["_esperas_ia"] = esperas
            ctx.caso["dados"] = dados
            _marcar_checkpoint(ctx, atual)
            ctx.saida["adiar_para"] = agora + timedelta(seconds=max(30.0, esperar_ia))
            with ctx.rastreio.span("aguardar_ia", "orquestrador") as p:
                p["detalhe"] = {"esperar_s": round(esperar_ia), "vez": n}
            _checkpoint(ctx, "aguardando IA", dono)
            return {"ok": True, "erro": None, "situacao": ctx.caso["situacao"]}
        erro = "IaOcupada"
    if erro:
        _transferir(ctx, erro)
        if grafo.ao_falhar:
            try:
                grafo.ao_falhar(ctx)
            except Exception as e:                   # o aviso não pode derrubar a transferência
                print(f"[Agente] aviso de falha não enviado: {type(e).__name__}")
    _limpar_checkpoint(ctx)
    try:
        from agente import semaforo
        semaforo.atualizar(ctx.caso, agora)             # a cor da pasta acompanha cada rodada do caso
    except Exception as e:                              # a cor nunca derruba o atendimento
        print(f"[Agente] semáforo não atualizado: {type(e).__name__}")
    try:
        from agente import canal_telegram
        canal_telegram.entregar(ctx)                    # o que o agente escreveu vai ao Telegram, se o chat estiver ligado
    except Exception as e:                              # o canal nunca derruba o atendimento
        print(f"[Agente] entrega no Telegram falhou: {type(e).__name__}")
    _checkpoint(ctx, "erro" if erro else ctx.caso.get("ultimo_passo"), dono)
    return {"ok": erro is None, "erro": erro, "situacao": ctx.caso["situacao"]}


def _checkpoint(ctx: Contexto, ultimo: str | None, dono: str) -> None:
    ctx.caso["ultimo_passo"] = ultimo
    campos = {k: ctx.caso.get(k) for k in ("situacao", "ultimo_passo", "dados", "grupo",
                                           "grupo_controle", "proxima_data", "tentativas",
                                           "versao_politica", "resumo")}
    # Renova a trava: um turno longo (várias chamadas à IA) não a deixa vencer no meio.
    campos["trava_ate"] = agora_real() + DURACAO_TRAVA
    if not ctx.repo.salvar_caso(ctx.caso["id"], campos, dono=dono):
        raise RuntimeError("trava do caso perdida durante o processamento")


def processar_proximo(repo, grafos: dict, cliente=None, agora: datetime | None = None,
                      dono: str | None = None, empresa_id: str | None = None) -> dict | None:
    """Pega o evento pronto de maior prioridade cujo caso está livre e processa.

    Com `empresa_id`, só eventos dessa empresa (a rota de uma empresa não processa
    a fila das outras). Devolve um resumo, ou None se não havia nada a fazer.
    """
    agora = agora or agora_real()
    dono = dono or novo_dono()
    for ev in repo.candidatos(agora, empresa_id=empresa_id):
        if not repo.reservar_evento(ev["id"]):
            continue                                    # outro processo pegou
        real = agora_real()
        if not repo.travar_caso(ev["caso_id"], dono, real + DURACAO_TRAVA, real):
            # Caso ocupado com outro evento: devolve como estava e tenta o próximo.
            repo.devolver_evento(ev["id"], ev.get("disponivel_em"))
            continue
        try:
            return _processar(repo, grafos, ev, cliente or llm.cliente(), agora, dono)
        finally:
            repo.soltar_caso(ev["caso_id"], dono)
    return None


def _processar(repo, grafos, ev, cliente, agora, dono) -> dict:
    trace_id = ev.get("trace_id") or novo_trace_id()
    try:
        # Dentro do try: banco fora do ar aqui também devolve o evento à fila.
        repo.atualizar_evento(ev["id"], {"trace_id": trace_id})
        grafo = grafos.get(ev["tipo"])
        if grafo is None:
            raise LookupError(f"sem grafo para o evento {ev['tipo']}")
        caso = repo.obter_caso(ev["caso_id"])
        if caso is None:
            raise LookupError("caso não encontrado")
        rastreio = Rastreio(ev["empresa_id"], repo.gravar_passo, caso_id=caso["id"],
                            evento_id=ev["id"], trace_id=trace_id)
        # "Hoje" do negócio é o de Brasília: às 21h o dia ainda não virou.
        ctx = Contexto(caso=caso, evento=ev, repo=repo, rastreio=rastreio,
                       cliente=cliente, hoje=agora.astimezone(auditor.BRASILIA).date(), agora=agora)
        resultado = executar(grafo, ctx, dono)
    except Exception as e:
        # Falha fora do grafo: volta para a fila; na segunda vira "falhou".
        falhas = int(ev.get("tentativas") or 0) + 1
        final = falhas >= MAX_FALHAS_EVENTO
        repo.atualizar_evento(ev["id"], {
            "situacao": "falhou" if final else "pendente",
            "tentativas": falhas, "erro": type(e).__name__,
            "disponivel_em": agora + ESPERA_NOVA_TENTATIVA,
            "concluido_em": agora if final else None,
        })
        return {"evento_id": ev["id"], "trace_id": trace_id, "ok": False,
                "erro": type(e).__name__, "situacao_evento": "falhou" if final else "pendente"}
    adiar = ctx.saida.get("adiar_para")
    if adiar and resultado["ok"]:
        # O grafo pediu para esperar (ex.: fora do horário de contato): volta
        # para a fila sem contar como falha. A chave do evento continua a mesma.
        repo.atualizar_evento(ev["id"], {"situacao": "pendente", "disponivel_em": adiar})
        return {"evento_id": ev["id"], "trace_id": trace_id, "situacao_evento": "adiado", **resultado}
    repo.atualizar_evento(ev["id"], {"situacao": "feito", "erro": resultado["erro"],
                                     "concluido_em": agora})
    return {"evento_id": ev["id"], "trace_id": trace_id, "situacao_evento": "feito", **resultado}


def processar_fila(repo, grafos: dict, cliente=None, limite: int = 20,
                   agora: datetime | None = None, dono: str | None = None,
                   empresa_id: str | None = None) -> list:
    """Processa até `limite` eventos prontos. Para o agendador chamar.

    Antes, devolve à fila o que ficou preso em "processando" com a reserva vencida.
    """
    try:
        repo.devolver_presos(agora_real(), MAX_FALHAS_EVENTO, empresa_id=empresa_id)
    except Exception as e:                               # não pode travar a fila
        print(f"[Agente] não devolveu eventos presos: {type(e).__name__}")
    feitos = []
    for _ in range(limite):
        r = processar_proximo(repo, grafos, cliente, agora, dono, empresa_id=empresa_id)
        if r is None:
            break
        feitos.append(r)
    return feitos
