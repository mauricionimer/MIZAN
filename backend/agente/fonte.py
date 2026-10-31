"""De onde as ferramentas leem e onde gravam o que acontece com o devedor.

- FonteMemoria: testes e demonstração local.
- FonteSupabase: produção, nas tabelas que o Mizan já usa (predicoes, agenda,
  ofertas_feitas, contatos) e nas do agente (agente_contestacoes).

Sempre escopado à empresa, com falha fechada: devedor de outra empresa é
"não encontrado".

O contato registrado pelo agente NÃO passa pelo aprendizado do bandit de hoje,
que dá 0,2 a uma promessa antes de entrar dinheiro (docs/PLANO_AGENTE.md, 3.5).
O agente só ensina o bandit pelo dinheiro que entra, quando a regra nova for
ligada com o seu OK.
"""
import copy
import uuid
from datetime import datetime, timezone

from agente import mudancas

OPERADOR_AGENTE = "agente-mizan"
NOME_AGENTE = "Assistente virtual"
# Atendimento com uma pessoa pedido pelo devedor sem responsável: fica na fila
# do administrador, que escolhe o operador (aba Agenda do Agente).
OPERADOR_A_DEFINIR = "a-definir"
NOME_A_DEFINIR = "A definir pelo administrador"
OPERADORES_DO_AGENTE = (OPERADOR_AGENTE, OPERADOR_A_DEFINIR)


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FonteMemoria:
    def __init__(self, devedores=None, catalogo=None, nome_empresa="Banco Demonstração"):
        self._nome_empresa = nome_empresa
        self._devedores = {d["id"]: d for d in (devedores or [])}   # predicao_id -> devedor
        self._catalogo = catalogo
        self.agenda: list = []
        self.ofertas: list = []
        self.contatos: list = []
        self.contestacoes: list = []
        self.disponibilidades: list = []

    def devedor(self, empresa_id: str, predicao_id: str) -> dict | None:
        d = self._devedores.get(predicao_id)
        return copy.deepcopy(d) if d and d.get("empresa_id") == empresa_id else None

    def nome_empresa(self, empresa_id: str) -> str:
        return self._nome_empresa

    def devedores(self, empresa_id: str, limite: int = 2000) -> list:
        return [copy.deepcopy(d) for d in self._devedores.values() if d.get("empresa_id") == empresa_id][:limite]

    def catalogo(self, empresa_id: str) -> list:
        from model.oferta import catalogo_padrao
        return copy.deepcopy(self._catalogo) if self._catalogo else catalogo_padrao()

    def agenda_pendente(self, empresa_id: str, predicao_id: str) -> list:
        return [copy.deepcopy(a) for a in self.agenda if a["empresa_id"] == empresa_id
                and a["predicao_id"] == predicao_id and a["situacao"] == "pendente"]

    def compromisso(self, empresa_id: str, predicao_id: str, item_id: str) -> dict | None:
        return next((copy.deepcopy(a) for a in self.agenda if a['empresa_id'] == empresa_id
                     and a['predicao_id'] == predicao_id and a['id'] == item_id), None)

    def criar_agenda(self, empresa_id: str, devedor: dict, tipo: str, data: str,
                     valor=None, observacao: str = "", hora: str | None = None, operador: tuple | None = None) -> dict:
        op_id, op_nome = operador or (devedor.get("responsavel_id") or OPERADOR_AGENTE,
                                      devedor.get("responsavel_nome") or NOME_AGENTE)
        item = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "cpf": devedor["cpf"], "nome": devedor.get("nome"),
                "predicao_id": devedor["id"], "operador_id": op_id, "operador_nome": op_nome,
                "tipo": tipo, "data": data, "hora": hora, "valor": valor, "observacao": observacao,
                "situacao": "pendente"}
        self.agenda.append(item)
        mudancas.marcar(empresa_id, "agenda")
        return copy.deepcopy(item)

    def recomendacao_bandit(self, empresa_id: str, devedor: dict) -> dict | None:
        return copy.deepcopy(getattr(self, "_bandit", None))

    def pagamentos(self, empresa_id: str, predicao_ids: list) -> dict:
        """{predicao_id: valor recebido} de quem pagou."""
        pagos = getattr(self, "pagos", {})
        return {p: pagos[p] for p in predicao_ids if p in pagos}

    def agenda_dos_casos(self, empresa_id: str, predicao_ids: list) -> list:
        ids = set(predicao_ids)
        return [copy.deepcopy(a) for a in self.agenda if a["empresa_id"] == empresa_id and a["predicao_id"] in ids
                and a["situacao"] == "pendente"]

    def operadores(self, empresa_id: str) -> list:
        return copy.deepcopy(getattr(self, "_operadores", []))

    def atribuir_agenda(self, empresa_id: str, item_id: str, operador_id: str, operador_nome: str) -> dict | None:
        for a in self.agenda:
            if a["id"] == item_id and a["empresa_id"] == empresa_id and a["situacao"] == "pendente" \
                    and a["operador_id"] in OPERADORES_DO_AGENTE:
                a.update({"operador_id": operador_id, "operador_nome": operador_nome})
                return copy.deepcopy(a)
        return None

    def atualizar_agenda(self, empresa_id: str, predicao_id: str, item_id: str, campos: dict) -> bool:
        for a in self.agenda:
            if a["id"] == item_id and a["empresa_id"] == empresa_id and a["predicao_id"] == predicao_id \
                    and a["situacao"] == "pendente":
                a.update(campos)
                mudancas.marcar(empresa_id, "agenda")
                return True
        return False

    def registrar_oferta(self, empresa_id: str, devedor: dict, linha: dict) -> dict:
        o = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "predicao_id": devedor["id"], **linha}
        self.ofertas.append(o)
        return copy.deepcopy(o)

    def registrar_contato(self, empresa_id: str, devedor: dict, resultado: str, observacao: str) -> dict:
        c = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "cpf": devedor["cpf"],
             "resultado": resultado, "observacao": observacao}
        self.contatos.append(c)
        return copy.deepcopy(c)

    def abrir_contestacao(self, empresa_id: str, caso_id: str, motivo: str) -> dict:
        c = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "caso_id": caso_id,
             "motivo": motivo, "situacao": "aberta"}
        self.contestacoes.append(c)
        return copy.deepcopy(c)

    # ── disponibilidade do operador (backend/sql/migracao_disponibilidade_operador.sql) ──
    def disponibilidade_operador(self, empresa_id: str, usuario_id: str | None = None) -> list:
        return [copy.deepcopy(d) for d in self.disponibilidades
                if d["empresa_id"] == empresa_id and d.get("ativo", True)
                and (usuario_id is None or d["usuario_id"] == usuario_id)]

    def criar_disponibilidade(self, empresa_id: str, usuario_id: str, dia_semana: int,
                              hora_inicio: int, hora_fim: int) -> dict:
        item = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "usuario_id": usuario_id,
                "dia_semana": dia_semana, "hora_inicio": hora_inicio, "hora_fim": hora_fim, "ativo": True}
        self.disponibilidades.append(item)
        return copy.deepcopy(item)

    def editar_disponibilidade(self, empresa_id: str, item_id: str, campos: dict) -> dict | None:
        for d in self.disponibilidades:
            if d["id"] == item_id and d["empresa_id"] == empresa_id:
                d.update(campos)
                return copy.deepcopy(d)
        return None

    def remover_disponibilidade(self, empresa_id: str, item_id: str) -> bool:
        for d in self.disponibilidades:
            if d["id"] == item_id and d["empresa_id"] == empresa_id:
                d["ativo"] = False
                return True
        return False


_COLUNAS_DEVEDOR = ("id, cpf, nome, carteira_id, valor_divida, dias_em_atraso, produto, "
                    "responsavel_id, responsavel_nome")


class FonteSupabase:
    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            from db import get_db
            return get_db()
        return self._db

    def devedor(self, empresa_id: str, predicao_id: str) -> dict | None:
        res = self.db.table("predicoes").select(_COLUNAS_DEVEDOR).eq("id", predicao_id).limit(1).execute()
        if not res.data:
            return None
        d = res.data[0]
        # A predição só vale se a carteira dela for da empresa (falha fechada).
        cart = (self.db.table("carteiras").select("id").eq("id", d.get("carteira_id"))
                .eq("empresa_id", empresa_id).limit(1).execute())
        return d if cart.data else None

    def devedores(self, empresa_id: str, limite: int = 2000) -> list:
        """Devedores da carteira mais recente da empresa, na ordem da fila."""
        cart = (self.db.table("carteiras").select("id").eq("empresa_id", empresa_id)
                .order("created_at", desc=True).limit(1).execute())
        if not cart.data:
            return []
        res = (self.db.table("predicoes")
               .select("id, nome, valor_divida, dias_em_atraso, score_recuperabilidade, probabilidade_pagamento, rank, produto")
               .eq("carteira_id", cart.data[0]["id"]).order("rank").limit(limite).execute())
        return res.data or []

    def nome_empresa(self, empresa_id: str) -> str:
        res = (self.db.table("empresa_config").select("nome_exibicao")
               .eq("empresa_id", empresa_id).limit(1).execute())
        return ((res.data or [{}])[0].get("nome_exibicao") or "").strip() or empresa_id

    def catalogo(self, empresa_id: str) -> list:
        from model.oferta import catalogo_da_empresa
        res = self.db.table("empresa_config").select("extra").eq("empresa_id", empresa_id).limit(1).execute()
        extra = (res.data or [{}])[0].get("extra") or {}
        return catalogo_da_empresa(extra)[0]

    def agenda_pendente(self, empresa_id: str, predicao_id: str) -> list:
        res = (self.db.table("agenda").select("id, tipo, data, hora, valor, situacao, operador_id, operador_nome, observacao")
               .eq("empresa_id", empresa_id).eq("predicao_id", predicao_id)
               .eq("situacao", "pendente").order("data").limit(20).execute())
        return res.data or []

    def criar_agenda(self, empresa_id: str, devedor: dict, tipo: str, data: str,
                     valor=None, observacao: str = "", hora: str | None = None, operador: tuple | None = None) -> dict:
        # O compromisso fica na agenda de quem cuida do devedor; sem responsável,
        # na do agente (aparece para o gestor). `operador` escolhe outro dono.
        op_id, op_nome = operador or (devedor.get("responsavel_id") or OPERADOR_AGENTE,
                                      devedor.get("responsavel_nome") or NOME_AGENTE)
        linha = {"empresa_id": empresa_id, "cpf": devedor["cpf"], "nome": devedor.get("nome"),
                 "carteira_id": devedor.get("carteira_id"), "predicao_id": devedor["id"],
                 "operador_id": op_id, "operador_nome": op_nome,
                 "tipo": tipo, "data": data, "hora": hora, "valor": valor, "observacao": observacao or None,
                 "situacao": "pendente"}
        res = self.db.table("agenda").insert({k: v for k, v in linha.items() if v is not None}).execute()
        mudancas.marcar(empresa_id, "agenda")                     # a Agenda aberta na tela se atualiza sozinha
        return res.data[0]

    def compromisso(self, empresa_id: str, predicao_id: str, item_id: str) -> dict | None:
        r = (self.db.table('agenda').select('id, situacao, operador_id, operador_nome, data, hora')
             .eq('empresa_id', empresa_id).eq('predicao_id', predicao_id).eq('id', item_id).limit(1).execute())
        return (r.data or [None])[0]

    def recomendacao_bandit(self, empresa_id: str, devedor: dict) -> dict | None:
        """O que o bandit da empresa recomenda para o devedor (contexto completo da
        predição, que nunca vai para a IA). Falhou: sem recomendação."""
        try:
            from model import bandit
            linha = (self.db.table("predicoes").select("*").eq("id", devedor["id"]).limit(1).execute().data or [None])[0]
            return bandit.recomendar(linha or devedor, empresa_id) if linha else None
        except Exception as e:
            print(f"[Agente] bandit indisponível: {type(e).__name__}")
            return None

    def pagamentos(self, empresa_id: str, predicao_ids: list) -> dict:
        """{predicao_id: valor recebido} de quem pagou (feedbacks com pagou = true)."""
        saida: dict = {}
        ids = list(dict.fromkeys(predicao_ids))
        for i in range(0, len(ids), 200):
            res = (self.db.table("feedbacks").select("predicao_id, valor_recuperado")
                   .in_("predicao_id", ids[i:i + 200]).eq("pagou", True).execute())
            for f in res.data or []:
                saida[f["predicao_id"]] = saida.get(f["predicao_id"], 0.0) + float(f.get("valor_recuperado") or 0)
        return saida

    def agenda_dos_casos(self, empresa_id: str, predicao_ids: list) -> list:
        """Compromissos pendentes dos devedores que estão com o agente."""
        saida = []
        for i in range(0, len(predicao_ids), 200):
            res = (self.db.table("agenda").select("id, predicao_id, nome, operador_id, operador_nome, tipo, data, hora, "
                                                  "valor, observacao, situacao")
                   .eq("empresa_id", empresa_id).eq("situacao", "pendente")
                   .in_("predicao_id", predicao_ids[i:i + 200]).order("data").limit(500).execute())
            saida += res.data or []
        return saida

    def operadores(self, empresa_id: str) -> list:
        res = (self.db.table("usuarios").select("id, nome, email, role, ativo")
               .eq("empresa_id", empresa_id).limit(1000).execute())
        return [{"id": u["id"], "nome": u.get("nome") or u.get("email") or ""} for u in res.data or []
                if u.get("role") == "operador" and u.get("ativo", True)]

    def atribuir_agenda(self, empresa_id: str, item_id: str, operador_id: str, operador_nome: str) -> dict | None:
        # Só troca quem ainda está com o agente: dois cliques não sobrescrevem um ao outro.
        res = (self.db.table("agenda").update({"operador_id": operador_id, "operador_nome": operador_nome})
               .eq("id", item_id).eq("empresa_id", empresa_id).eq("situacao", "pendente")
               .in_("operador_id", list(OPERADORES_DO_AGENTE)).execute())
        return (res.data or [None])[0]

    def atualizar_agenda(self, empresa_id: str, predicao_id: str, item_id: str, campos: dict) -> bool:
        res = (self.db.table("agenda").update(campos).eq("id", item_id).eq("empresa_id", empresa_id)
               .eq("predicao_id", predicao_id).eq("situacao", "pendente").execute())
        if res.data:
            mudancas.marcar(empresa_id, "agenda")
        return bool(res.data)

    def registrar_oferta(self, empresa_id: str, devedor: dict, linha: dict) -> dict:
        dados = {"empresa_id": empresa_id, "cpf": devedor["cpf"], "nome": devedor.get("nome"),
                 "carteira_id": devedor.get("carteira_id"), "predicao_id": devedor["id"],
                 "operador_id": OPERADOR_AGENTE, "operador_nome": NOME_AGENTE, **linha}
        res = self.db.table("ofertas_feitas").insert({k: v for k, v in dados.items() if v is not None}).execute()
        return res.data[0]

    def registrar_contato(self, empresa_id: str, devedor: dict, resultado: str, observacao: str) -> dict:
        linha = {"empresa_id": empresa_id, "cpf": devedor["cpf"], "canal": "whatsapp",
                 "resultado": resultado, "observacao": observacao[:500] or None,
                 "usuario_id": OPERADOR_AGENTE, "usuario_nome": NOME_AGENTE}
        res = self.db.table("contatos").insert({k: v for k, v in linha.items() if v is not None}).execute()
        return res.data[0]

    def abrir_contestacao(self, empresa_id: str, caso_id: str, motivo: str) -> dict:
        res = (self.db.table("agente_contestacoes")
               .insert({"empresa_id": empresa_id, "caso_id": caso_id, "motivo": motivo}).execute())
        return res.data[0]

    # ── disponibilidade do operador (backend/sql/migracao_disponibilidade_operador.sql) ──
    def disponibilidade_operador(self, empresa_id: str, usuario_id: str | None = None) -> list:
        q = (self.db.table("disponibilidade_operador").select("*")
             .eq("empresa_id", empresa_id).eq("ativo", True))
        if usuario_id is not None:
            q = q.eq("usuario_id", usuario_id)
        return q.order("dia_semana").order("hora_inicio").limit(500).execute().data or []

    def criar_disponibilidade(self, empresa_id: str, usuario_id: str, dia_semana: int,
                              hora_inicio: int, hora_fim: int) -> dict:
        res = (self.db.table("disponibilidade_operador").insert({
            "empresa_id": empresa_id, "usuario_id": usuario_id, "dia_semana": dia_semana,
            "hora_inicio": hora_inicio, "hora_fim": hora_fim, "ativo": True}).execute())
        return res.data[0]

    def editar_disponibilidade(self, empresa_id: str, item_id: str, campos: dict) -> dict | None:
        res = (self.db.table("disponibilidade_operador").update(campos)
               .eq("id", item_id).eq("empresa_id", empresa_id).execute())
        return res.data[0] if res.data else None

    def remover_disponibilidade(self, empresa_id: str, item_id: str) -> bool:
        res = (self.db.table("disponibilidade_operador").update({"ativo": False})
               .eq("id", item_id).eq("empresa_id", empresa_id).execute())
        return bool(res.data)
