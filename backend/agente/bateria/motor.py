"""Motor da bateria de cenários (docs/PLANO_AGENTE.md, 6).

Cada cenário monta um caso com devedor fictício, executa passos (mensagem do
devedor, relógio, pagamento, mudança de política, controle do gestor) e confere
o resultado por código — sem IA julgando, custo zero na conferência.

- Modo falso: a IA é um roteiro escrito no cenário; confere o código (travas,
  fluxo, registros) a cada mudança, sem custo.
- Modo real: a IA de verdade decide (o roteiro é ignorado); a mesma
  conferência mede a qualidade das decisões do modelo. Gasta dinheiro: só em
  marcos combinados.

Cada conferência pertence a um critério da rubrica (docs/PLANO_EXECUCAO_AGENTES.md, 10).
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from agente import auditor, estado, orquestrador as orq
from agente.acompanhamento import planejar
from agente.api import grafos
from agente.fonte import FonteMemoria
from agente.llm import ClienteFalso, Resposta
from agente.repositorio import RepoMemoria

PESOS = {"correcao": 20, "politica": 20, "negociacao": 15, "contexto": 10,
         "seguranca": 15, "robustez": 10, "custo": 10}
NOME_CRITERIO = {"correcao": "Correção factual", "politica": "Aderência à política", "negociacao": "Condução da negociação",
                 "contexto": "Contexto ao longo da conversa", "seguranca": "Segurança", "robustez": "Robustez",
                 "custo": "Latência e custo"}

BR = auditor.BRASILIA
DIA = date(2026, 10, 16)                         # sexta


def em(d: date, hora: int = 14) -> datetime:
    return datetime(d.year, d.month, d.day, hora, tzinfo=BR).astimezone(timezone.utc)


def devedor(**kw) -> dict:
    base = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Maria das Dores",
            "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1",
            "probabilidade_pagamento": 0.3}
    return {**base, **kw}


# ── atalhos para escrever roteiros ──────────────────────────────────────────

def tri(intencao: str, *sinais) -> str:
    return json.dumps({"intencao": intencao, "confianca": 0.9, "valores_citados": [], "datas_citadas": [],
                       "sinais_de_risco": list(sinais)})


def F(nome: str, **args) -> Resposta:
    return Resposta(ferramentas=[{"nome": nome, "args": args}])


def T(texto: str) -> Resposta:
    return Resposta(texto=texto)


def ACEITE(data: str = "2026-10-20"):
    """Aceite da simulação mais recente do caso (o id só existe na hora)."""
    def f(sistema, mensagens):
        # O id mais recente que a IA tem à vista: num resultado de ferramenta
        # desta mensagem ou nas simulações válidas do briefing.
        texto = json.dumps(mensagens, ensure_ascii=False)
        ids = re.findall(r'simulacao_id\\?"\s*:\s*\\?"([0-9a-f]+)', texto)
        return F("registrar_aceite", simulacao_id=ids[-1] if ids else "nenhuma", data_primeiro_pagamento=data)
    return f


# ── o cenário ───────────────────────────────────────────────────────────────

@dataclass
class Cenario:
    id: str
    grupo: str
    descricao: str
    passos: list                                  # [(tipo, valor, quando?)]
    conferir: list                                # [(criterio, descricao, f(R) -> bool)]
    roteiro: list = field(default_factory=list)   # respostas da IA simulada, em ordem
    situacao: str = "em_contato"
    dados: dict = field(default_factory=dict)
    politica: dict | None = None                  # None = demonstração
    devedor: dict = field(default_factory=devedor)
    agenda: list = field(default_factory=list)    # [(tipo, data, valor)]
    controle: bool = False


@dataclass
class Resultado:
    repo: RepoMemoria
    fonte: FonteMemoria
    caso: dict
    cliente: object
    erro_inesperado: str | None = None

    @property
    def saidas(self) -> list:
        return [m["texto"] for m in self.repo.mensagens if m["direcao"] == "saida"]

    def passos(self, no=None) -> list:
        return [p for p in self.repo.passos if no is None or p["no"] == no]

    def bloqueios(self) -> set:
        return {p["regra"] for p in self.repo.passos if p["no"] == "auditor" and p["resultado"] == "bloqueado"}

    @property
    def custo(self) -> float:
        return round(sum(float(p["custo_usd"]) for p in self.repo.passos), 6)


ID_OK = {"identidade_ok": True, "divida": 3000.0}


def executar(c: Cenario, cliente=None) -> Resultado:
    repo, fonte = RepoMemoria(), FonteMemoria([c.devedor])
    caso = repo.obter_ou_criar_caso("emp", c.devedor["id"])
    repo.salvar_caso(caso["id"], {"situacao": c.situacao, "dados": dict(c.dados), "grupo_controle": c.controle})
    repo.gravar_politica("emp", 1, c.politica or auditor.POLITICA_DEMONSTRACAO)
    for tipo, data, valor in c.agenda:
        fonte.criar_agenda("emp", c.devedor, tipo, data, valor=valor)
    cliente = cliente or ClienteFalso(list(c.roteiro))
    g = grafos(fonte)
    erro = None
    n = 0
    for passo in c.passos:
        tipo, valor = passo[0], passo[1]
        agora = passo[2] if len(passo) > 2 else em(DIA)
        n += 1
        try:
            if tipo == "mensagem":
                orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", f"m{n}", {"texto": valor})
            elif tipo == "evento_repetido":
                for _ in range(2):
                    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "mesma", {"texto": valor})
            elif tipo == "relogio":
                planejar(repo, fonte, "emp", agora)
            elif tipo == "pagamento":
                prom = [a for a in fonte.agenda_pendente("emp", c.devedor["id"]) if a["tipo"] == "promessa"]
                for a in prom:
                    fonte.atualizar_agenda("emp", c.devedor["id"], a["id"], {"situacao": "cumprida"})
                orq.registrar_evento(repo, "emp", caso["id"], "pagamento", f"pg{n}",
                                     {"valor": valor, "promessas": [{"id": a["id"], "valor": a["valor"]} for a in prom]})
            elif tipo == "politica":
                repo.nova_versao_politica("emp", {**auditor.POLITICA_DEMONSTRACAO, **valor})
            elif tipo == "situacao":
                repo.salvar_caso(caso["id"], {"situacao": valor})
            orq.processar_fila(repo, g, cliente, limite=10, agora=agora)
        except Exception as e:                                  # o cenário falha, a bateria segue
            erro = f"{type(e).__name__}: {e}"
            break
    return Resultado(repo, fonte, repo.obter_caso(caso["id"]), cliente, erro)


def avaliar(c: Cenario, r: Resultado) -> dict:
    itens = []
    for criterio, descricao, f in c.conferir:
        try:
            ok = bool(f(r)) and r.erro_inesperado is None
        except Exception:
            ok = False
        itens.append({"criterio": criterio, "conferencia": descricao, "ok": ok})
    return {"id": c.id, "grupo": c.grupo, "descricao": c.descricao, "ok": all(i["ok"] for i in itens),
            "itens": itens, "custo_usd": r.custo, "erro": r.erro_inesperado}


def nota(resultados: list) -> dict:
    por = {k: [0, 0] for k in PESOS}
    for res in resultados:
        for i in res["itens"]:
            por[i["criterio"]][0] += i["ok"]
            por[i["criterio"]][1] += 1
    criterios = {k: (round(v[0] / v[1], 4) if v[1] else None) for k, v in por.items()}
    validos = {k: x for k, x in criterios.items() if x is not None}
    total = round(100 * sum(PESOS[k] * x for k, x in validos.items()) / sum(PESOS[k] for k in validos), 1) if validos else 0.0
    return {"nota": total, "criterios": criterios,
            "cenarios": len(resultados), "aprovados": sum(r["ok"] for r in resultados),
            "conferencias": sum(len(r["itens"]) for r in resultados),
            "custo_usd": round(sum(r["custo_usd"] for r in resultados), 6)}
