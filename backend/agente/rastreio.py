"""Rastreio dos agentes (docs/PLANO_EXECUCAO_AGENTES.md, 9).

Cada evento ganha um trace_id. Cada nó executado vira um passo (span) com nó,
agente, resultado, duração, regra, versões, tokens e custo. É isso que a
Central de orquestração mostra e o que responde "por que o agente fez isso?".

Nunca grave dado pessoal em `detalhe`: só ids, nomes de regra e tipos de erro.
"""
import time
import uuid
from contextlib import contextmanager


def novo_trace_id() -> str:
    return uuid.uuid4().hex


class Rastreio:
    def __init__(self, empresa_id: str, gravar, caso_id=None, evento_id=None, trace_id=None):
        self.empresa_id = empresa_id
        self.caso_id = caso_id
        self.evento_id = evento_id
        self.trace_id = trace_id or novo_trace_id()
        self._gravar = gravar
        self.passos: list = []
        self.atual: dict | None = None

    @contextmanager
    def span(self, no: str, agente: str = "codigo"):
        passo = {
            "empresa_id": self.empresa_id, "trace_id": self.trace_id,
            "caso_id": self.caso_id, "evento_id": self.evento_id,
            "no": no, "agente": agente, "resultado": "ok", "duracao_ms": 0,
            "regra": None, "versao_politica": None, "modelo": None, "versao_prompt": None,
            "tokens_entrada": 0, "tokens_saida": 0, "custo_usd": 0.0, "detalhe": {},
        }
        anterior, self.atual = self.atual, passo
        inicio = time.perf_counter()
        try:
            yield passo
        except Exception as e:
            passo["resultado"] = "erro"
            passo["detalhe"] = {**passo["detalhe"], "erro": type(e).__name__}
            raise
        finally:
            passo["duracao_ms"] = int((time.perf_counter() - inicio) * 1000)
            passo["custo_usd"] = round(passo["custo_usd"], 6)
            self.atual = anterior
            self.passos.append(passo)
            try:
                self._gravar(passo)
            except Exception as e:
                # Rastreio que falha não pode derrubar o atendimento.
                print(f"[Agente] não gravou o passo {no}: {type(e).__name__}")

    def somar_ia(self, resposta) -> None:
        """Soma tokens e custo de uma chamada de IA ao passo em andamento."""
        if self.atual is None:
            return
        self.atual["tokens_entrada"] += int(resposta.tokens_entrada or 0)
        self.atual["tokens_saida"] += int(resposta.tokens_saida or 0)
        self.atual["custo_usd"] += float(resposta.custo_usd or 0)
        self.atual["modelo"] = resposta.modelo or self.atual["modelo"]

    @property
    def custo_total(self) -> float:
        return round(sum(p["custo_usd"] for p in self.passos), 6)
