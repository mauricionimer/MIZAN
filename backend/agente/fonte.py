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

OPERADOR_AGENTE = "agente-mizan"
NOME_AGENTE = "Assistente virtual"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FonteMemoria:
    def __init__(self, devedores=None, catalogo=None, nome_empresa="Banco Demonstração"):
        self._nome_empresa = nome_empresa
        self.devedores = {d["id"]: d for d in (devedores or [])}   # predicao_id -> devedor
        self._catalogo = catalogo
        self.agenda: list = []
        self.ofertas: list = []
        self.contatos: list = []
        self.contestacoes: list = []

    def devedor(self, empresa_id: str, predicao_id: str) -> dict | None:
        d = self.devedores.get(predicao_id)
        return copy.deepcopy(d) if d and d.get("empresa_id") == empresa_id else None

    def nome_empresa(self, empresa_id: str) -> str:
        return self._nome_empresa

    def catalogo(self, empresa_id: str) -> list:
        from model.oferta import catalogo_padrao
        return copy.deepcopy(self._catalogo) if self._catalogo else catalogo_padrao()

    def agenda_pendente(self, empresa_id: str, predicao_id: str) -> list:
        return [copy.deepcopy(a) for a in self.agenda if a["empresa_id"] == empresa_id
                and a["predicao_id"] == predicao_id and a["situacao"] == "pendente"]

    def criar_agenda(self, empresa_id: str, devedor: dict, tipo: str, data: str,
                     valor=None, observacao: str = "") -> dict:
        item = {"id": str(uuid.uuid4()), "empresa_id": empresa_id, "cpf": devedor["cpf"],
                "predicao_id": devedor["id"], "operador_id": devedor.get("responsavel_id") or OPERADOR_AGENTE,
                "tipo": tipo, "data": data, "valor": valor, "observacao": observacao, "situacao": "pendente"}
        self.agenda.append(item)
        return copy.deepcopy(item)

    def atualizar_agenda(self, empresa_id: str, predicao_id: str, item_id: str, campos: dict) -> bool:
        for a in self.agenda:
            if a["id"] == item_id and a["empresa_id"] == empresa_id and a["predicao_id"] == predicao_id \
                    and a["situacao"] == "pendente":
                a.update(campos)
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
        res = (self.db.table("agenda").select("id, tipo, data, valor, situacao")
               .eq("empresa_id", empresa_id).eq("predicao_id", predicao_id)
               .eq("situacao", "pendente").order("data").limit(20).execute())
        return res.data or []

    def criar_agenda(self, empresa_id: str, devedor: dict, tipo: str, data: str,
                     valor=None, observacao: str = "") -> dict:
        linha = {"empresa_id": empresa_id, "cpf": devedor["cpf"], "nome": devedor.get("nome"),
                 "carteira_id": devedor.get("carteira_id"), "predicao_id": devedor["id"],
                 # O compromisso fica na agenda de quem cuida do devedor; sem
                 # responsável, na do agente (aparece para a equipe).
                 "operador_id": devedor.get("responsavel_id") or OPERADOR_AGENTE,
                 "operador_nome": devedor.get("responsavel_nome") or NOME_AGENTE,
                 "tipo": tipo, "data": data, "valor": valor, "observacao": observacao or None,
                 "situacao": "pendente"}
        res = self.db.table("agenda").insert({k: v for k, v in linha.items() if v is not None}).execute()
        return res.data[0]

    def atualizar_agenda(self, empresa_id: str, predicao_id: str, item_id: str, campos: dict) -> bool:
        res = (self.db.table("agenda").update(campos).eq("id", item_id).eq("empresa_id", empresa_id)
               .eq("predicao_id", predicao_id).eq("situacao", "pendente").execute())
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
