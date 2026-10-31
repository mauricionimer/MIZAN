"""Guarda dos dados do agente: casos, eventos e passos.

Duas implementações com a mesma interface:
- RepoMemoria: testes e demonstração local, sem banco.
- RepoSupabase: produção, nas tabelas de sql/migracao_agente.sql.

As reservas (evento e trava do caso) são atualizações condicionais: o filtro vai
na própria cláusula do UPDATE, então de dois processos disputando a mesma linha
só um recebe a linha de volta. Mesmo padrão de travas.py.
"""
import copy
import threading
import uuid
from datetime import date, datetime, timedelta, timezone

# "Hoje" do negócio é o de Brasília (o servidor roda em UTC). Igual a auditor.BRASILIA.
BRASILIA = timezone(timedelta(hours=-3))

# Evento sem data marcada fica pronto já. O valor vai explícito no insert: com o
# DEFAULT NOW() do banco, quem calculou `agora` antes de registrar não via o evento.
PRONTO_JA = datetime(2000, 1, 1, tzinfo=timezone.utc)

# Evento "processando" guarda em disponivel_em até quando a reserva vale. Passou
# disso (o processo morreu no meio), volta para a fila. Prazo folgado: um turno com
# IA real pode passar de 5 minutos; a trava do caso impede dois ao mesmo tempo.
RESERVA_EVENTO = timedelta(minutes=15)

PAGINA = 1000                     # o PostgREST corta em max-rows (1000 no Supabase)


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def inicio_do_dia_brasilia(dia: date) -> datetime:
    """Meia-noite de Brasília do dia, em UTC."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=BRASILIA).astimezone(timezone.utc)


def _dt(v):
    if v is None or isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


class EventoDuplicado(Exception):
    pass


class RepoMemoria:
    def __init__(self):
        self.casos: dict = {}
        self.eventos: dict = {}
        self.passos: list = []
        self.logs_agentes: list = []
        self.politicas: list = []
        self.mensagens: list = []
        self.consultas_juridicas_: list = []
        self.conferencias_juridicas_: dict = {}
        self._lock = threading.Lock()

    # ── casos ──
    def obter_ou_criar_caso(self, empresa_id: str, predicao_id: str) -> dict:
        with self._lock:
            for c in self.casos.values():
                if c["empresa_id"] == empresa_id and c["predicao_id"] == predicao_id:
                    return copy.deepcopy(c)
            caso = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "predicao_id": predicao_id,
                    "situacao": "novo", "grupo": None, "grupo_controle": False, "proxima_data": None,
                    "tentativas": 0, "versao_politica": None, "resumo": None, "ultimo_passo": None,
                    "dados": {}, "trava_dono": None, "trava_ate": None, "atualizado_em": agora_utc()}
            self.casos[caso["id"]] = caso
            return copy.deepcopy(caso)

    def obter_caso(self, caso_id: str) -> dict | None:
        c = self.casos.get(caso_id)
        return copy.deepcopy(c) if c else None

    def caso_por_telegram(self, chat_id) -> dict | None:
        """O caso ligado a este chat do Telegram, se houver."""
        for c in self.casos.values():
            if str(((c.get("dados") or {}).get("telegram") or {}).get("chat_id") or "") == str(chat_id):
                return copy.deepcopy(c)
        return None

    def salvar_caso(self, caso_id: str, campos: dict, dono: str | None = None) -> bool:
        """Grava o checkpoint. Com `dono`, só grava se a trava ainda for dele."""
        with self._lock:
            c = self.casos.get(caso_id)
            if not c or (dono is not None and c["trava_dono"] != dono):
                return False
            c.update(copy.deepcopy(campos))
            c["atualizado_em"] = agora_utc()
            return True

    def travar_caso(self, caso_id: str, dono: str, ate: datetime, agora: datetime) -> bool:
        with self._lock:
            c = self.casos.get(caso_id)
            if not c:
                return False
            if c["trava_ate"] is not None and c["trava_ate"] >= agora:
                return False
            c["trava_dono"], c["trava_ate"] = dono, ate
            return True

    def soltar_caso(self, caso_id: str, dono: str) -> None:
        with self._lock:
            c = self.casos.get(caso_id)
            if c and c["trava_dono"] == dono:
                c["trava_dono"], c["trava_ate"] = None, None

    # ── eventos ──
    def inserir_evento(self, evento: dict) -> dict:
        with self._lock:
            for e in self.eventos.values():
                if e["empresa_id"] == evento["empresa_id"] and e["chave"] == evento["chave"]:
                    raise EventoDuplicado(evento["chave"])
            e = {"id": str(uuid.uuid4()), "situacao": "pendente", "tentativas": 0, "erro": None,
                 "trace_id": None, "concluido_em": None, "criado_em": agora_utc(),
                 # Sem data, pronto já (o mesmo que registrar_evento manda ao banco).
                 "disponivel_em": PRONTO_JA, **copy.deepcopy(evento)}
            self.eventos[e["id"]] = e
            return copy.deepcopy(e)

    def evento_por_chave(self, empresa_id: str, chave: str) -> dict | None:
        for e in self.eventos.values():
            if e["empresa_id"] == empresa_id and e["chave"] == chave:
                return copy.deepcopy(e)
        return None

    def candidatos(self, agora: datetime, limite: int = 10, empresa_id: str | None = None, caso_id=None) -> list:
        prontos = [e for e in self.eventos.values()
                   if e["situacao"] == "pendente" and e["disponivel_em"] <= agora
                   and (empresa_id is None or e["empresa_id"] == empresa_id)
                   and (caso_id is None or e["caso_id"] == caso_id)]
        prontos.sort(key=lambda e: (-e["prioridade"], e["criado_em"]))
        return [copy.deepcopy(e) for e in prontos[:limite]]

    def reservar_evento(self, evento_id: str, trace_id: str | None = None) -> bool:
        with self._lock:
            e = self.eventos.get(evento_id)
            if not e or e["situacao"] != "pendente":
                return False
            if trace_id:
                e["trace_id"] = trace_id
            e["situacao"] = "processando"
            e["disponivel_em"] = agora_utc() + RESERVA_EVENTO      # até quando a reserva vale
            return copy.deepcopy(e)                                 # o evento como ficou reservado

    def devolver_evento(self, evento_id: str, disponivel_em) -> None:
        """Devolve à fila um evento reservado que não deu para processar agora."""
        with self._lock:
            e = self.eventos.get(evento_id)
            if e and e["situacao"] == "processando":
                e["situacao"], e["disponivel_em"] = "pendente", _dt(disponivel_em) or PRONTO_JA

    def devolver_presos(self, agora: datetime, max_falhas: int, empresa_id: str | None = None) -> int:
        """Eventos "processando" com a reserva vencida (o processo caiu): voltam
        para a fila contando uma falha; na última, viram "falhou"."""
        n = 0
        with self._lock:
            for e in self.eventos.values():
                if (e["situacao"] == "processando" and e["disponivel_em"] < agora
                        and (empresa_id is None or e["empresa_id"] == empresa_id)):
                    falhas = int(e.get("tentativas") or 0) + 1
                    final = falhas >= max_falhas
                    e.update(situacao="falhou" if final else "pendente", tentativas=falhas,
                             erro="ReservaVencida", disponivel_em=agora,
                             concluido_em=agora if final else None)
                    n += 1
        return n

    def atualizar_evento(self, evento_id: str, campos: dict) -> None:
        with self._lock:
            if evento_id in self.eventos:
                self.eventos[evento_id].update(copy.deepcopy(campos))

    def pendente_do_caso(self, empresa_id: str, caso_id: str, tipo: str) -> dict | None:
        """O evento mais antigo deste tipo ainda na fila do caso (pronto ou adiado)."""
        evs = sorted((e for e in self.eventos.values() if e["empresa_id"] == empresa_id and e["caso_id"] == caso_id
                      and e["tipo"] == tipo and e["situacao"] == "pendente"), key=lambda e: e["criado_em"])
        return copy.deepcopy(evs[0]) if evs else None

    def atualizar_evento_pendente(self, evento_id: str, campos: dict) -> bool:
        """Atualiza só se o evento ainda está na fila (ninguém começou a processar)."""
        with self._lock:
            e = self.eventos.get(evento_id)
            if not e or e["situacao"] != "pendente":
                return False
            e.update(copy.deepcopy(campos))
            return True

    # ── mensagens ──
    def gravar_mensagem(self, empresa_id: str, caso_id: str, direcao: str, texto: str,
                        trace_id: str | None = None, criado_em: datetime | None = None) -> None:
        with self._lock:
            if direcao == "entrada" and trace_id and any(
                    m["caso_id"] == caso_id and m["direcao"] == "entrada" and m["trace_id"] == trace_id
                    for m in self.mensagens):
                return                       # o mesmo evento rodou de novo: a mensagem já está lá
            self.mensagens.append({"empresa_id": empresa_id, "caso_id": caso_id, "direcao": direcao,
                                   "texto": texto, "trace_id": trace_id, "criado_em": criado_em or agora_utc()})

    def ultimas_mensagens(self, empresa_id: str, caso_id: str, n: int = 20) -> list:
        ms = [copy.deepcopy(m) for m in self.mensagens if m["empresa_id"] == empresa_id and m["caso_id"] == caso_id]
        return ms[-n:]

    # ── leitura para as telas ──
    def caso_de(self, empresa_id: str, predicao_id: str) -> dict | None:
        for c in self.casos.values():
            if c["empresa_id"] == empresa_id and c["predicao_id"] == predicao_id:
                return copy.deepcopy(c)
        return None

    def passos_do_trace(self, empresa_id: str, trace_id: str) -> list:
        return [copy.deepcopy(p) for p in self.passos if p["empresa_id"] == empresa_id and p["trace_id"] == trace_id]

    def passos_recentes(self, empresa_id: str, desde: datetime, n: int = 300) -> list:
        ps = [p for p in self.passos if p["empresa_id"] == empresa_id and p["criado_em"] >= desde]
        return [copy.deepcopy(p) for p in sorted(ps, key=lambda p: p["criado_em"])[-n:]]

    def eventos_recentes(self, empresa_id: str, n: int = 500) -> list:
        evs = [e for e in self.eventos.values() if e["empresa_id"] == empresa_id]
        evs.sort(key=lambda e: e["criado_em"], reverse=True)
        return [copy.deepcopy(e) for e in evs[:n]]

    def ultimo_evento_caso(self, empresa_id, caso_id):
        evs = [e for e in self.eventos.values() if e["empresa_id"] == empresa_id and e["caso_id"] == caso_id]
        return copy.deepcopy(max(evs, key=lambda e: e["criado_em"])) if evs else None

    def situacoes_dos_casos(self, empresa_id: str) -> list:
        return [c["situacao"] for c in self.casos.values() if c["empresa_id"] == empresa_id]

    def eventos_escritorio(self, empresa_id: str) -> list:
        return [{**{k: e.get(k) for k in ("id", "caso_id", "trace_id", "tipo", "situacao", "tentativas")},
                 "escritorio": copy.deepcopy((e.get("dados") or {}).get("_escritorio"))}
                for e in sorted(self.eventos.values(), key=lambda e: (e["situacao"] == "processando", e["criado_em"]), reverse=True)
                if e["empresa_id"] == empresa_id][:500]

    def casos_da_empresa(self, empresa_id: str, situacoes=None) -> list:
        return [copy.deepcopy(c) for c in self.casos.values() if c["empresa_id"] == empresa_id
                and (situacoes is None or c["situacao"] in situacoes)]

    def casos_semaforo(self, empresa_id: str) -> list:
        return [{"predicao_id": c["predicao_id"], "situacao": c["situacao"],
                 "dados": {k: copy.deepcopy((c.get("dados") or {}).get(k))
                           for k in ("leitura", "passagem")}}
                for c in self.casos.values() if c["empresa_id"] == empresa_id]

    def passos_metricas(self, empresa_id: str, desde: datetime, n: int = 5000) -> list:
        return self.passos_recentes(empresa_id, desde, n)

    def empresas_com_politica(self) -> list:
        return sorted({p["empresa_id"] for p in self.politicas if p["ativa"]})

    # ── política ──
    def gravar_politica(self, empresa_id: str, versao: int, regras: dict, ativa: bool = True) -> None:
        with self._lock:
            if ativa:
                for p in self.politicas:
                    if p["empresa_id"] == empresa_id:
                        p["ativa"] = False
            self.politicas.append({"empresa_id": empresa_id, "versao": versao,
                                   "regras": copy.deepcopy(regras), "ativa": ativa})

    def politica_ativa(self, empresa_id: str) -> dict | None:
        ativas = [p for p in self.politicas if p["empresa_id"] == empresa_id and p["ativa"]]
        return copy.deepcopy(max(ativas, key=lambda p: p["versao"])) if ativas else None

    def politicas_da_empresa(self, empresa_id: str) -> list:
        ps = [copy.deepcopy(p) for p in self.politicas if p["empresa_id"] == empresa_id]
        return sorted(ps, key=lambda p: -p["versao"])

    def nova_versao_politica(self, empresa_id: str, regras: dict, criado_por: str | None = None) -> int:
        with self._lock:
            versao = max([p["versao"] for p in self.politicas if p["empresa_id"] == empresa_id], default=0) + 1
            for p in self.politicas:
                if p["empresa_id"] == empresa_id:
                    p["ativa"] = False
            self.politicas.append({"empresa_id": empresa_id, "versao": versao, "regras": copy.deepcopy(regras),
                                   "ativa": True, "criado_por": criado_por, "criado_em": agora_utc()})
            return versao

    # ── passos ──
    def gravar_passo(self, passo: dict) -> None:
        with self._lock:
            self.passos.append({**copy.deepcopy(passo), "criado_em": agora_utc()})

    def gravar_log_agente(self, log: dict) -> None:
        with self._lock:
            self.logs_agentes.append({"id": str(uuid.uuid4()), **copy.deepcopy(log), "criado_em": log.get("criado_em") or agora_utc()})

    def logs_operacionais(self, empresa_id: str, n: int = 100) -> list:
        logs = [copy.deepcopy(l) for l in self.logs_agentes if l["empresa_id"] == empresa_id]
        logs.sort(key=lambda l: str(l.get("criado_em") or ""), reverse=True)
        return logs[:n]

    # ── base jurídica: decisões internas e conferências oficiais ──
    def gravar_consulta_juridica(self, linha: dict) -> str:
        with self._lock:
            r = {"id": str(uuid.uuid4()), **copy.deepcopy(linha), "criado_em": agora_utc()}
            self.consultas_juridicas_.append(r)
            return r["id"]

    def consultas_juridicas(self, empresa_id: str, caso_id=None, n: int = 50) -> list:
        rs = [copy.deepcopy(r) for r in self.consultas_juridicas_ if r["empresa_id"] == empresa_id
              and (caso_id is None or r.get("caso_id") == str(caso_id))]
        return sorted(rs, key=lambda r: r["criado_em"], reverse=True)[:n]

    def gravar_conferencia_juridica(self, norma_id: str, resultado: dict) -> None:
        with self._lock:
            self.conferencias_juridicas_[norma_id] = copy.deepcopy(resultado)

    def conferencias_juridicas(self) -> dict:
        return copy.deepcopy(self.conferencias_juridicas_)

    # ── recomendações do Cientista ──
    def gravar_recomendacao(self, empresa_id: str, rec: dict) -> dict:
        with self._lock:
            lista = getattr(self, "recomendacoes_", None)
            if lista is None:
                lista = self.recomendacoes_ = []
            versao = max([r["versao"] for r in lista if r["empresa_id"] == empresa_id], default=0) + 1
            linha = {**copy.deepcopy(rec), "id": str(uuid.uuid4()), "empresa_id": empresa_id, "versao": versao,
                     "status": "proposta", "criado_em": agora_utc(), "decidido_por": None, "decidido_em": None}
            lista.append(linha)
            return copy.deepcopy(linha)

    def recomendacoes(self, empresa_id: str, n: int = 10) -> list:
        lista = [copy.deepcopy(r) for r in getattr(self, "recomendacoes_", []) if r["empresa_id"] == empresa_id]
        return sorted(lista, key=lambda r: -r["versao"])[:n]

    def decidir_recomendacao(self, empresa_id: str, rec_id: str, status: str, quem: str | None) -> dict | None:
        """Só decide o que ainda está "proposta" (dois cliques não decidem duas vezes)."""
        with self._lock:
            for r in getattr(self, "recomendacoes_", []):
                if r["empresa_id"] == empresa_id and r["id"] == rec_id and r["status"] == "proposta":
                    r.update(status=status, decidido_por=quem, decidido_em=agora_utc())
                    return copy.deepcopy(r)
        return None

    def recomendacao_aprovada(self, empresa_id: str) -> dict | None:
        ok = [r for r in self.recomendacoes(empresa_id, 1000) if r["status"] == "aprovada"]
        return ok[0] if ok else None

    def custo_do_dia(self, empresa_id: str, dia: date) -> float:
        """Gasto do dia de Brasília (o teto vira à meia-noite daqui, não às 21h)."""
        return round(sum(float(p["custo_usd"]) for p in self.passos
                         if p["empresa_id"] == empresa_id
                         and p["criado_em"].astimezone(BRASILIA).date() == dia), 6)

    # ── leitura em lote (telas e plano do dia) ──
    def casos_por_predicoes(self, empresa_id: str, predicao_ids) -> list:
        """Casos da empresa só destes devedores (uma consulta por lote, não uma por devedor)."""
        ids = {str(p) for p in predicao_ids or [] if p}
        return [copy.deepcopy(c) for c in self.casos.values()
                if c["empresa_id"] == empresa_id and str(c["predicao_id"]) in ids]

    def predicoes_dos_casos(self, empresa_id: str) -> list:
        """Só os ids dos devedores que têm caso com o agente."""
        return [c["predicao_id"] for c in self.casos.values() if c["empresa_id"] == empresa_id]


class _Gravador:
    """Grava em segundo plano, na ordem, sem descartar. Uma tentativa a mais se falhar."""

    def __init__(self):
        import queue
        self._fila = queue.Queue()
        self._thread = None
        self._lock = threading.Lock()

    def enfileirar(self, gravar) -> None:
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._rodar, name="mizan-passos", daemon=True)
                self._thread.start()
        self._fila.put(gravar)

    def _rodar(self):
        import time
        while True:
            gravar = self._fila.get()
            try:
                for tentativa in (1, 2):
                    try:
                        gravar()
                        break
                    except Exception as e:
                        if tentativa == 2:
                            print(f"[Agente] passo não gravado: {type(e).__name__}")
                        else:
                            time.sleep(0.5)
            finally:
                self._fila.task_done()

    def esperar(self, timeout: float) -> None:
        import time
        fim = time.monotonic() + timeout
        while self._fila.unfinished_tasks and time.monotonic() < fim:
            time.sleep(0.02)


gravador_de_passos = _Gravador()


class RepoSupabase:
    """Mesma interface, nas tabelas agente_*. Só o backend acessa (RLS ligado)."""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            from db import get_db
            return get_db()
        return self._db

    @staticmethod
    def _iso(v):
        return v.isoformat() if isinstance(v, (datetime, date)) else v

    def _caso(self, linha: dict | None) -> dict | None:
        if not linha:
            return None
        linha = dict(linha)
        linha["trava_ate"] = _dt(linha.get("trava_ate"))
        linha["dados"] = linha.get("dados") or {}
        return linha

    # ── casos ──
    def obter_ou_criar_caso(self, empresa_id: str, predicao_id: str) -> dict:
        t = self.db.table("agente_casos")
        res = t.select("*").eq("empresa_id", empresa_id).eq("predicao_id", predicao_id).limit(1).execute()
        if res.data:
            return self._caso(res.data[0])
        try:
            res = t.insert({"empresa_id": empresa_id, "predicao_id": predicao_id}).execute()
            return self._caso(res.data[0])
        except Exception:
            # Outro processo criou ao mesmo tempo (UNIQUE): usa o dele.
            res = t.select("*").eq("empresa_id", empresa_id).eq("predicao_id", predicao_id).limit(1).execute()
            if not res.data:
                raise
            return self._caso(res.data[0])

    def obter_caso(self, caso_id: str) -> dict | None:
        res = self.db.table("agente_casos").select("*").eq("id", caso_id).limit(1).execute()
        return self._caso(res.data[0]) if res.data else None

    def caso_por_telegram(self, chat_id) -> dict | None:
        """O caso ligado a este chat do Telegram (dados->telegram->chat_id), se houver."""
        res = (self.db.table("agente_casos").select("*")
               .eq("dados->telegram->>chat_id", str(chat_id)).limit(1).execute())
        return self._caso(res.data[0]) if res.data else None

    def salvar_caso(self, caso_id: str, campos: dict, dono: str | None = None) -> bool:
        dados = {k: self._iso(v) for k, v in campos.items()}
        dados["atualizado_em"] = agora_utc().isoformat()
        q = self.db.table("agente_casos").update(dados).eq("id", caso_id)
        if dono is not None:
            q = q.eq("trava_dono", dono)
        return bool(q.execute().data)

    def travar_caso(self, caso_id: str, dono: str, ate: datetime, agora: datetime) -> bool:
        res = (self.db.table("agente_casos")
               .update({"trava_dono": dono, "trava_ate": ate.isoformat()})
               .eq("id", caso_id)
               # Sem "+00:00" dentro do filtro: "+" em URL pode virar espaço.
               .or_(f"trava_ate.is.null,trava_ate.lt.{agora.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}")
               .execute())
        return bool(res.data)

    def soltar_caso(self, caso_id: str, dono: str) -> None:
        (self.db.table("agente_casos").update({"trava_dono": None, "trava_ate": None})
         .eq("id", caso_id).eq("trava_dono", dono).execute())

    # ── eventos ──
    def inserir_evento(self, evento: dict) -> dict:
        dados = {k: self._iso(v) for k, v in evento.items()}
        try:
            return self.db.table("agente_eventos").insert(dados).execute().data[0]
        except Exception as e:
            if self.evento_por_chave(evento["empresa_id"], evento["chave"]):
                raise EventoDuplicado(evento["chave"]) from e
            raise

    def evento_por_chave(self, empresa_id: str, chave: str) -> dict | None:
        res = (self.db.table("agente_eventos").select("*")
               .eq("empresa_id", empresa_id).eq("chave", chave).limit(1).execute())
        return res.data[0] if res.data else None

    def candidatos(self, agora: datetime, limite: int = 10, empresa_id: str | None = None, caso_id=None) -> list:
        q = (self.db.table("agente_eventos").select("*")
             .eq("situacao", "pendente").lte("disponivel_em", agora.isoformat()))
        if empresa_id is not None:
            q = q.eq("empresa_id", empresa_id)
        if caso_id is not None:
            q = q.eq("caso_id", caso_id)
        res = q.order("prioridade", desc=True).order("criado_em").limit(limite).execute()
        return res.data or []

    def reservar_evento(self, evento_id: str, trace_id: str | None = None) -> bool:
        ate = (agora_utc() + RESERVA_EVENTO).isoformat()
        campos = {"situacao": "processando", "disponivel_em": ate}
        if trace_id:
            campos["trace_id"] = trace_id                          # na mesma ida ao banco da reserva
        res = (self.db.table("agente_eventos").update(campos)
               .eq("id", evento_id).eq("situacao", "pendente").execute())
        if not res.data:
            return False
        linha = res.data[0]
        return linha if isinstance(linha, dict) and linha else True   # o evento como ficou reservado

    def devolver_evento(self, evento_id: str, disponivel_em) -> None:
        (self.db.table("agente_eventos")
         .update({"situacao": "pendente", "disponivel_em": self._iso(disponivel_em or PRONTO_JA)})
         .eq("id", evento_id).eq("situacao", "processando").execute())

    def devolver_presos(self, agora: datetime, max_falhas: int, empresa_id: str | None = None) -> int:
        q = (self.db.table("agente_eventos").select("id, tentativas, disponivel_em")
             .eq("situacao", "processando").lt("disponivel_em", agora.isoformat()))
        if empresa_id is not None:
            q = q.eq("empresa_id", empresa_id)
        n = 0
        for e in q.limit(50).execute().data or []:
            falhas = int(e.get("tentativas") or 0) + 1
            final = falhas >= max_falhas
            # Condicional: se outro processo já devolveu (ou terminou), não mexe.
            res = (self.db.table("agente_eventos").update({
                "situacao": "falhou" if final else "pendente", "tentativas": falhas, "erro": "ReservaVencida",
                "disponivel_em": agora.isoformat(), "concluido_em": agora.isoformat() if final else None})
                .eq("id", e["id"]).eq("situacao", "processando").lt("disponivel_em", agora.isoformat())
                .execute())
            n += 1 if res.data else 0
        return n

    def atualizar_evento(self, evento_id: str, campos: dict) -> None:
        dados = {k: self._iso(v) for k, v in campos.items()}
        self.db.table("agente_eventos").update(dados).eq("id", evento_id).execute()

    def pendente_do_caso(self, empresa_id: str, caso_id: str, tipo: str) -> dict | None:
        res = (self.db.table("agente_eventos").select("*").eq("empresa_id", empresa_id).eq("caso_id", caso_id)
               .eq("tipo", tipo).eq("situacao", "pendente").order("criado_em").limit(1).execute())
        return (res.data or [None])[0]

    def atualizar_evento_pendente(self, evento_id: str, campos: dict) -> bool:
        dados = {k: self._iso(v) for k, v in campos.items()}
        res = (self.db.table("agente_eventos").update(dados)
               .eq("id", evento_id).eq("situacao", "pendente").execute())
        return bool(res.data)

    def publicar_escritorio(self, empresa_id, evento_id, trace_id, dados):
        from agente.publicador import publicador
        def gravar(snapshot):
            t = snapshot["_escritorio"]["atualizado_em"]
            (self.db.table("agente_eventos").update({"dados": snapshot})
             .eq("id", evento_id).eq("empresa_id", empresa_id).eq("trace_id", trace_id)
             .or_(f"dados->_escritorio->>atualizado_em.is.null,dados->_escritorio->>atualizado_em.lte.{t}")
             .execute())
        return publicador.publicar((empresa_id, evento_id), gravar, dados)

    # ── mensagens ──
    # Retenção: apagar_em fica nulo por enquanto; a regra entra com o
    # model/retencao.py quando houver piloto (docs/PLANO_EXECUCAO_AGENTES.md, 7).
    def gravar_mensagem(self, empresa_id: str, caso_id: str, direcao: str, texto: str,
                        trace_id: str | None = None, criado_em: datetime | None = None) -> None:
        if direcao == "entrada" and trace_id:
            ja = (self.db.table("agente_mensagens").select("id").eq("caso_id", caso_id)
                  .eq("direcao", "entrada").eq("trace_id", trace_id).limit(1).execute())
            if ja.data:
                return                       # o mesmo evento rodou de novo: a mensagem já está lá
        linha = {"empresa_id": empresa_id, "caso_id": caso_id, "direcao": direcao, "texto": texto,
                 "trace_id": trace_id}
        if criado_em is not None:
            linha["criado_em"] = criado_em.isoformat()
        self.db.table("agente_mensagens").insert(linha).execute()

    def ultimas_mensagens(self, empresa_id: str, caso_id: str, n: int = 20) -> list:
        res = (self.db.table("agente_mensagens").select("direcao, texto, trace_id, criado_em")
               .eq("empresa_id", empresa_id).eq("caso_id", caso_id)
               .order("criado_em", desc=True).limit(n).execute())
        return list(reversed(res.data or []))

    # ── leitura para as telas ──
    def caso_de(self, empresa_id: str, predicao_id: str) -> dict | None:
        res = (self.db.table("agente_casos").select("*").eq("empresa_id", empresa_id)
               .eq("predicao_id", predicao_id).limit(1).execute())
        return self._caso(res.data[0]) if res.data else None

    def passos_do_trace(self, empresa_id: str, trace_id: str) -> list:
        res = (self.db.table("agente_passos").select("*").eq("empresa_id", empresa_id)
               .eq("trace_id", trace_id).order("criado_em").limit(200).execute())
        return res.data or []

    def passos_recentes(self, empresa_id: str, desde: datetime, n: int = 300) -> list:
        """Passos da empresa desde `desde` (índice empresa_id, criado_em)."""
        res = (self.db.table("agente_passos").select("*").eq("empresa_id", empresa_id)
               .gte("criado_em", desde.isoformat()).order("criado_em", desc=True).limit(n).execute())
        return list(reversed(res.data or []))

    def passos_metricas(self, empresa_id: str, desde: datetime, n: int = 5000) -> list:
        """Resumo sem transportar o detalhe de cada decisão. Respeita o teto por resposta."""
        campos = ("id,no,agente,caso_id,resultado,duracao_ms,modelo,versao_prompt,"
                  "tokens_entrada,tokens_saida,custo_usd,criado_em,"
                  "origem:detalhe->origem,ok:detalhe->ok")
        linhas = []
        while len(linhas) < n:
            pagina = (self.db.table("agente_passos").select(campos).eq("empresa_id", empresa_id)
                      .gte("criado_em", desde.isoformat()).order("criado_em", desc=True).order("id")
                      .range(len(linhas), min(n, len(linhas) + self.PAGINA) - 1).execute()).data or []
            if not pagina:
                break
            linhas.extend({**p, "detalhe": {"origem": p.get("origem"), "ok": p.get("ok")}}
                          for p in pagina)
        return list(reversed(linhas))

    def eventos_recentes(self, empresa_id: str, n: int = 500) -> list:
        res = (self.db.table("agente_eventos")
               .select("id, caso_id, tipo, origem, situacao, tentativas, erro, trace_id, criado_em, concluido_em")
               .eq("empresa_id", empresa_id).order("criado_em", desc=True).limit(n).execute())
        return res.data or []

    def ultimo_evento_caso(self, empresa_id, caso_id):
        res = (self.db.table("agente_eventos")
               .select("id,caso_id,tipo,situacao,erro,trace_id,disponivel_em,criado_em")
               .eq("empresa_id", empresa_id).eq("caso_id", caso_id)
               .order("criado_em", desc=True).limit(1).execute())
        return (res.data or [None])[0]

    def situacoes_dos_casos(self, empresa_id: str) -> list:
        res = (self.db.table("agente_casos").select("situacao").eq("empresa_id", empresa_id)
               .limit(5000).execute())
        return [c["situacao"] for c in res.data or []]

    def eventos_escritorio(self, empresa_id: str) -> list:
        campos = "id,caso_id,trace_id,tipo,situacao,tentativas,escritorio:dados->_escritorio"
        # Ativos primeiro, inclusive um evento antigo retomado pelo checkpoint.
        ativos = (self.db.table("agente_eventos").select(campos).eq("empresa_id", empresa_id)
                  .eq("situacao", "processando").order("criado_em", desc=True).limit(500).execute()).data or []
        recentes = (self.db.table("agente_eventos").select(campos).eq("empresa_id", empresa_id)
                    .neq("situacao", "processando").order("criado_em", desc=True).limit(max(1, 500-len(ativos))).execute()).data or []
        return (ativos + recentes)[:500]

    def casos_da_empresa(self, empresa_id: str, situacoes=None) -> list:
        q = self.db.table("agente_casos").select("*").eq("empresa_id", empresa_id)
        if situacoes is not None:
            q = q.in_("situacao", list(situacoes))
        return [self._caso(c) for c in (q.limit(5000).execute().data or [])]

    def casos_semaforo(self, empresa_id: str) -> list:
        """Só as entradas das regras de cor; cadernos/acordos vêm com a página exibida."""
        saida = []
        while True:
            linhas = (self.db.table("agente_casos")
                      .select("predicao_id,situacao,leitura:dados->leitura,passagem:dados->passagem")
                      .eq("empresa_id", empresa_id).order("predicao_id")
                      .range(len(saida), len(saida) + self.PAGINA - 1).execute()).data or []
            if not linhas:
                return saida
            saida.extend({"predicao_id": c["predicao_id"], "situacao": c["situacao"],
                          "dados": {"leitura": c.get("leitura"), "passagem": c.get("passagem")}}
                         for c in linhas)

    def empresas_com_politica(self) -> list:
        res = self.db.table("agente_politicas").select("empresa_id").eq("ativa", True).limit(1000).execute()
        return sorted({p["empresa_id"] for p in res.data or []})

    # ── política ──
    def politica_ativa(self, empresa_id: str) -> dict | None:
        res = (self.db.table("agente_politicas").select("versao, regras")
               .eq("empresa_id", empresa_id).eq("ativa", True)
               .order("versao", desc=True).limit(1).execute())
        return res.data[0] if res.data else None

    def politicas_da_empresa(self, empresa_id: str) -> list:
        res = (self.db.table("agente_politicas").select("versao, regras, ativa, criado_por, criado_em")
               .eq("empresa_id", empresa_id).order("versao", desc=True).limit(50).execute())
        return res.data or []

    def nova_versao_politica(self, empresa_id: str, regras: dict, criado_por: str | None = None) -> int:
        """Versão nova ativa; as anteriores ficam guardadas, inativas. O UNIQUE
        (empresa, versão) impede duas versões com o mesmo número."""
        atual = self.politicas_da_empresa(empresa_id)
        versao = (atual[0]["versao"] if atual else 0) + 1
        self.db.table("agente_politicas").insert({"empresa_id": empresa_id, "versao": versao, "regras": regras,
                                                  "ativa": True, "criado_por": criado_por}).execute()
        (self.db.table("agente_politicas").update({"ativa": False}).eq("empresa_id", empresa_id)
         .neq("versao", versao).execute())
        return versao

    # ── recomendações do Cientista (backend/sql/migracao_recomendacoes.sql) ──
    def gravar_recomendacao(self, empresa_id: str, rec: dict) -> dict:
        atual = self.recomendacoes(empresa_id, 1)
        versao = (atual[0]["versao"] if atual else 0) + 1
        res = self.db.table("agente_recomendacoes").insert({
            "empresa_id": empresa_id, "versao": versao, "texto": rec["texto"], "selo": rec["selo"],
            "origem": rec.get("origem") or "codigo", "relatorio": rec.get("relatorio") or {},
            "resultados": rec.get("resultados") or {}, "status": "proposta"}).execute()
        return res.data[0]

    def recomendacoes(self, empresa_id: str, n: int = 10) -> list:
        res = (self.db.table("agente_recomendacoes").select("*").eq("empresa_id", empresa_id)
               .order("versao", desc=True).limit(n).execute())
        return res.data or []

    def decidir_recomendacao(self, empresa_id: str, rec_id: str, status: str, quem: str | None) -> dict | None:
        res = (self.db.table("agente_recomendacoes")
               .update({"status": status, "decidido_por": quem, "decidido_em": agora_utc().isoformat()})
               .eq("empresa_id", empresa_id).eq("id", rec_id).eq("status", "proposta").execute())
        return res.data[0] if res.data else None

    def recomendacao_aprovada(self, empresa_id: str) -> dict | None:
        res = (self.db.table("agente_recomendacoes").select("*").eq("empresa_id", empresa_id)
               .eq("status", "aprovada").order("versao", desc=True).limit(1).execute())
        return res.data[0] if res.data else None

    # ── passos ──
    def gravar_passo(self, passo: dict) -> None:
        # Fora do caminho da resposta: cada passo era uma ida ao banco antes de a
        # mensagem sair. Em ordem, sem descartar (o teto de gasto do dia soma estes passos).
        db = self.db
        gravador_de_passos.enfileirar(lambda: db.table("agente_passos").insert(passo).execute())

    def esperar_passos(self, timeout: float = 2.0) -> None:
        """A tela vai ler os passos: espera os que ainda estão a caminho (até `timeout`)."""
        gravador_de_passos.esperar(timeout)

    def gravar_log_agente(self, log: dict) -> None:
        linha = {k: self._iso(v) for k, v in log.items() if k != "criado_em"}
        self.db.table("agente_logs").insert(linha).execute()

    # ── base jurídica (sql/migracao_agente_juridico.sql) ──
    def gravar_consulta_juridica(self, linha: dict) -> str | None:
        res = self.db.table("agente_consultas_juridicas").insert(
            {k: v for k, v in linha.items() if v is not None}).execute()
        return (res.data or [{}])[0].get("id")

    def consultas_juridicas(self, empresa_id: str, caso_id=None, n: int = 50) -> list:
        q = self.db.table("agente_consultas_juridicas").select("*").eq("empresa_id", empresa_id)
        if caso_id is not None:
            q = q.eq("caso_id", str(caso_id))
        return q.order("criado_em", desc=True).limit(n).execute().data or []

    def gravar_conferencia_juridica(self, norma_id: str, resultado: dict) -> None:
        self.db.table("agente_conferencias_juridicas").upsert(
            {"norma_id": norma_id, "status": resultado.get("status"), "conferido_em": resultado.get("em"),
             "resultado": resultado}, on_conflict="norma_id").execute()

    def conferencias_juridicas(self) -> dict:
        res = self.db.table("agente_conferencias_juridicas").select("norma_id, resultado").execute()
        return {r["norma_id"]: r["resultado"] for r in res.data or []}

    def logs_operacionais(self, empresa_id: str, n: int = 100) -> list:
        campos = "id,criado_em,nivel,categoria,mensagem,agente,evento_id,caso_id,trace_id,tentativa,detalhe"
        res = (self.db.table("agente_logs").select(campos).eq("empresa_id", empresa_id)
               .order("criado_em", desc=True).limit(n).execute())
        return res.data or []

    def custo_do_dia(self, empresa_id: str, dia: date) -> float:
        """Gasto do dia de Brasília, somado em páginas (sem .range o PostgREST para
        em 1000 linhas e o teto nunca dispararia)."""
        inicio = inicio_do_dia_brasilia(dia)
        total, de = 0.0, 0
        while True:
            res = (self.db.table("agente_passos").select("custo_usd")
                   .eq("empresa_id", empresa_id)
                   .gte("criado_em", inicio.isoformat())
                   .lt("criado_em", (inicio + timedelta(days=1)).isoformat())
                   .gt("custo_usd", 0)
                   .order("criado_em").range(de, de + PAGINA - 1)
                   .execute())
            linhas = res.data or []
            total += sum(float(l.get("custo_usd") or 0) for l in linhas)
            if len(linhas) < PAGINA:
                return round(total, 6)
            de += PAGINA

    # ── leitura em lote (telas e plano do dia) ──
    LOTE_IDS = 100                  # ids por consulta: a URL do in_() tem limite de tamanho
    PAGINA = 1000                   # o PostgREST corta em ~1000 linhas sem .range

    def casos_por_predicoes(self, empresa_id: str, predicao_ids) -> list:
        """Casos da empresa só destes devedores, com in_() em lotes de 100."""
        ids = list(dict.fromkeys(str(p) for p in predicao_ids or [] if p))
        saida = []
        for i in range(0, len(ids), self.LOTE_IDS):
            res = (self.db.table("agente_casos").select("*").eq("empresa_id", empresa_id)
                   .in_("predicao_id", ids[i:i + self.LOTE_IDS]).execute())
            saida += [self._caso(c) for c in res.data or []]
        return saida

    def predicoes_dos_casos(self, empresa_id: str) -> list:
        """Só os ids dos devedores que têm caso com o agente (paginado)."""
        saida, inicio = [], 0
        while True:
            res = (self.db.table("agente_casos").select("predicao_id").eq("empresa_id", empresa_id)
                   .order("predicao_id").range(inicio, inicio + self.PAGINA - 1).execute())
            linhas = res.data or []
            saida += [l["predicao_id"] for l in linhas]
            if len(linhas) < self.PAGINA:
                return saida
            inicio += self.PAGINA
