"""Negociador: consultas adiantadas em código (CPF pedido, dados do caso, política).
Cada uma poupa uma ida e volta à IA. IA simulada; sem banco.

    python test_agente_adiantar.py
"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import auditor, orquestrador as orq                      # noqa: E402
from agente.fonte import FonteMemoria                                 # noqa: E402
from agente.grafos import grafo_mensagem                              # noqa: E402
from agente.llm import ClienteFalso, Resposta                         # noqa: E402
from agente.repositorio import RepoMemoria                            # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
DEVEDOR = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Maria das Dores",
           "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1"}
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})


class Mundo:
    def __init__(self, dados=None):
        self.repo, self.fonte = RepoMemoria(), FonteMemoria([DEVEDOR])
        self.caso = self.repo.obter_ou_criar_caso("emp", "p1")
        self.repo.salvar_caso(self.caso["id"], {"situacao": "em_contato", "dados": dados or {}})
        self.repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
        self.grafos = {"mensagem_devedor": grafo_mensagem(self.fonte)}
        self.n, self.vistas = 0, []

    def agente_disse(self, texto):
        self.repo.gravar_mensagem("emp", self.caso["id"], "saida", texto, "t0", criado_em=SEXTA_14H)

    def escreve(self, texto, resposta):
        """A IA do negociador responde de primeira com `resposta` e guarda o briefing que recebeu."""
        def negociador(_sistema, mensagens):
            self.vistas.append(json.dumps(mensagens, ensure_ascii=False).replace("\\\"", "\""))
            return Resposta(texto=resposta)
        self.cliente = ClienteFalso([tri("outro"), negociador])
        self.n += 1
        orq.registrar_evento(self.repo, "emp", self.caso["id"], "mensagem_devedor", f"m{self.n}", {"texto": texto})
        return orq.processar_proximo(self.repo, self.grafos, self.cliente, SEXTA_14H)

    @property
    def dados(self):
        return self.repo.obter_caso(self.caso["id"])["dados"]


print("— CPF pedido e certo: confirmado em código, a IA responde de primeira —")
m = Mundo()
m.agente_disse("Para sua segurança, me diga os 3 primeiros dígitos do seu CPF.")
m.escreve("123", "Obrigado, Maria! Você prefere entender o que está em aberto ou ver uma opção de pagamento?")
checar(m.dados.get("identidade_ok") is True, "identidade confirmada sem a IA pedir a ferramenta")
checar(len(m.cliente.chamadas) == 2, "uma chamada de triagem e UMA do negociador", str(len(m.cliente.chamadas)))
checar('"verificar_identidade"' in m.vistas[0] and '"identidade_confirmada": true' in m.vistas[0],
       "o briefing diz que a identidade foi confirmada nesta mensagem")
checar('"consultar_caso"' in m.vistas[0] and '"consultar_politica"' in m.vistas[0] and "3000" in m.vistas[0],
       "e já traz os dados do caso e as regras (a IA não precisa pedir)")
checar(any("identidade confirmada" in (n.get("decisao") or "") + (n.get("motivo") or "") for n in m.dados.get("caderno") or []),
       "o caderno registra a confirmação, como quando a IA pede a ferramenta")

print("— CPF inteiro também vale —")
m = Mundo()
m.escreve("sou eu, cpf 123.456.789-00", "Obrigado, Maria!")
checar(m.dados.get("identidade_ok") is True, "CPF completo com o assunto CPF: confirmado")

print("— o que NÃO é adiantado (fica com a IA, como antes) —")
m = Mundo()
m.agente_disse("Para sua segurança, me diga os 3 primeiros dígitos do seu CPF.")
m.escreve("999", "Esses números não conferem. Pode verificar?")
checar(not m.dados.get("identidade_ok") and not m.dados.get("falhas_identidade"),
       "dígitos errados: não confirma e não conta tentativa (a IA decide pela ferramenta)")
checar('"consultas_desta_mensagem"' not in m.vistas[0], "e nada é adiantado no briefing")
m = Mundo()
m.agente_disse("Quanto você consegue pagar por mês?")
m.escreve("posso pagar 123", "Entendi.")
checar(not m.dados.get("identidade_ok"), "número sem falar de CPF: não é tratado como CPF")

print("— identidade já confirmada: dados e regras adiantados em toda mensagem —")
m = Mundo(dados={"identidade_ok": True, "divida": 3000.0})
m.escreve("quero ver uma opção", "Vou simular para você.")
checar('"consultar_caso"' in m.vistas[0] and '"consultar_politica"' in m.vistas[0],
       "o briefing traz consultar_caso e consultar_politica")
checar(len(m.cliente.chamadas) == 2, "sem chamadas a mais à IA")

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
