"""Orquestrador dos agentes (docs/PLANO_EXECUCAO_AGENTES.md, 3.0, 4 e 5).

Código, não IA. É dono do estado do caso e decide quem age e quando:

- Fila de eventos com prioridade: pedido para parar e contestação passam na
  frente de mensagem, que passa na frente de pagamento, datas e relógio.
- Idempotência: cada evento tem uma chave; o mesmo evento duas vezes vira um só.
- Um por vez por caso: trava com prazo no próprio caso.
- Grafo: nós (funções) ligados por arestas fixas ou condicionais, como no
  LangGraph, sem a dependência.
- Checkpoint: depois de cada nó o estado é gravado; se o processo cair, o mesmo
  evento recomeça do nó seguinte ao último concluído.
- Nó de erro: nó que falha tenta mais uma vez; falhou de novo, o caso vai para
  uma pessoa com o motivo registrado.
- Evento que quebra fora do grafo (banco fora do ar, por exemplo) volta para a
  fila; na segunda falha vira "falhou" e aparece na Central.

Os nós precisam ser seguros para rodar de novo: uma ação com efeito fora do
Mizan (enviar mensagem) usa a sua própria chave de idempotência.
"""
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from agente import auditor, estado, llm
from agente.rastreio import Rastreio, novo_trace_id
from agente.repositorio import EventoDuplicado

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

DONO = f"{socket.gethostname()}:{os.getpid()}"

# Erros em que tentar de novo não muda nada: vão direto para uma pessoa.
_SEM_NOVA_TENTATIVA = (llm.TetoExcedido, llm.PrecoDesconhecido, estado.TransicaoProibida)


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

    def auditar(self, acao: dict, contatos_7d: int = 0, simulacao: dict | None = None) -> dict:
        """Passa a ação pelo Auditor e registra a decisão como um passo do rastreio."""
        regras, versao = self.politica()
        with self.rastreio.span("auditor", "auditor") as p:
            d = auditor.auditar(acao, self.caso, regras, versao, self.agora,
                                contatos_7d=contatos_7d, simulacao=simulacao)
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
                     disponivel_em: datetime | None = None) -> tuple:
    """Põe um evento na fila. Devolve (evento, novo); repetido devolve o que já existe."""
    evento = {"empresa_id": empresa_id, "caso_id": caso_id, "tipo": tipo, "chave": chave,
              "origem": origem, "prioridade": PRIORIDADE.get(tipo, 50), "dados": dados or {}}
    if disponivel_em is not None:
        evento["disponivel_em"] = disponivel_em
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


def executar(grafo: Grafo, ctx: Contexto, dono: str = DONO) -> dict:
    """Roda o grafo para o evento do contexto, com checkpoint a cada nó."""
    ckpt = (ctx.caso.get("dados") or {}).get("_checkpoint") or {}
    atual = ckpt["proximo"] if ckpt.get("evento_id") == ctx.evento["id"] else grafo.inicio
    passos = 0
    erro = None
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
            except Exception as e:
                erro = type(e).__name__
        if erro:
            break
        try:
            atual = grafo.proximo(no, ctx)
        except Exception as e:                       # aresta para nó que não existe
            erro = type(e).__name__
            break
        dados = dict(ctx.caso.get("dados") or {})
        dados["_checkpoint"] = {"evento_id": ctx.evento["id"], "proximo": atual}
        ctx.caso["dados"] = dados
        _checkpoint(ctx, no.nome, dono)

    if erro:
        _transferir(ctx, erro)
        if grafo.ao_falhar:
            try:
                grafo.ao_falhar(ctx)
            except Exception as e:                   # o aviso não pode derrubar a transferência
                print(f"[Agente] aviso de falha não enviado: {type(e).__name__}")
    dados = dict(ctx.caso.get("dados") or {})
    dados.pop("_checkpoint", None)
    ctx.caso["dados"] = dados
    _checkpoint(ctx, "erro" if erro else ctx.caso.get("ultimo_passo"), dono)
    return {"ok": erro is None, "erro": erro, "situacao": ctx.caso["situacao"]}


def _checkpoint(ctx: Contexto, ultimo: str | None, dono: str) -> None:
    ctx.caso["ultimo_passo"] = ultimo
    campos = {k: ctx.caso.get(k) for k in ("situacao", "ultimo_passo", "dados", "grupo",
                                           "grupo_controle", "proxima_data", "tentativas",
                                           "versao_politica", "resumo")}
    if not ctx.repo.salvar_caso(ctx.caso["id"], campos, dono=dono):
        raise RuntimeError("trava do caso perdida durante o processamento")


def processar_proximo(repo, grafos: dict, cliente=None, agora: datetime | None = None,
                      dono: str = DONO) -> dict | None:
    """Pega o evento pronto de maior prioridade cujo caso está livre e processa.

    Devolve um resumo, ou None se não havia nada a fazer.
    """
    agora = agora or datetime.now(timezone.utc)
    for ev in repo.candidatos(agora):
        if not repo.reservar_evento(ev["id"]):
            continue                                    # outro processo pegou
        if not repo.travar_caso(ev["caso_id"], dono, agora + DURACAO_TRAVA, agora):
            # Caso ocupado com outro evento: devolve e tenta o próximo.
            repo.atualizar_evento(ev["id"], {"situacao": "pendente"})
            continue
        try:
            return _processar(repo, grafos, ev, cliente or llm.cliente(), agora, dono)
        finally:
            repo.soltar_caso(ev["caso_id"], dono)
    return None


def _processar(repo, grafos, ev, cliente, agora, dono) -> dict:
    trace_id = ev.get("trace_id") or novo_trace_id()
    repo.atualizar_evento(ev["id"], {"trace_id": trace_id})
    try:
        grafo = grafos.get(ev["tipo"])
        if grafo is None:
            raise LookupError(f"sem grafo para o evento {ev['tipo']}")
        caso = repo.obter_caso(ev["caso_id"])
        if caso is None:
            raise LookupError("caso não encontrado")
        rastreio = Rastreio(ev["empresa_id"], repo.gravar_passo, caso_id=caso["id"],
                            evento_id=ev["id"], trace_id=trace_id)
        ctx = Contexto(caso=caso, evento=ev, repo=repo, rastreio=rastreio,
                       cliente=cliente, hoje=agora.date(), agora=agora)
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
                   agora: datetime | None = None, dono: str = DONO) -> list:
    """Processa até `limite` eventos prontos. Para o agendador chamar."""
    feitos = []
    for _ in range(limite):
        r = processar_proximo(repo, grafos, cliente, agora, dono)
        if r is None:
            break
        feitos.append(r)
    return feitos
