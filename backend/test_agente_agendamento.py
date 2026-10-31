"""Agendamento pelo agente: marcar, remarcar e desmarcar sem duplicar compromissos.

Reproduz o caso relatado: marcou dia 3, a pessoa disse que não podia mais e pediu
outro dia, e o agente manteve o dia 3 e criou dois compromissos no dia novo.
IA simulada com roteiro; sem banco.

    python test_agente_agendamento.py
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

SEXTA_14H = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)          # sexta, 14h em Brasília
DIA_3, DIA_13 = "2026-11-03", "2026-11-13"                               # terça e sexta
DEV = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Luciana Prado",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao"}
tri = lambda i="outro": json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [],
                                    "sinais_de_risco": []})
F = lambda nome, **a: Resposta(ferramentas=[{"nome": nome, "args": a}])


class Mundo:
    def __init__(self, identidade=True):
        self.repo, self.fonte = RepoMemoria(), FonteMemoria([DEV])
        self.caso = self.repo.obter_ou_criar_caso("emp", "p1")
        dados = {"identidade_ok": True, "divida": 3000.0} if identidade else {}
        self.repo.salvar_caso(self.caso["id"], {"situacao": "em_contato", "dados": dados})
        self.repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
        self.grafos = {"mensagem_devedor": grafo_mensagem(self.fonte)}
        self.n, self.briefings = 0, []

    def escreve(self, texto, roteiro):
        def guardar(item):
            def f(_s, mensagens):
                self.briefings.append(json.dumps(mensagens, ensure_ascii=False).replace('\\"', '"'))
                return item
            return f
        self.cliente = ClienteFalso([tri()] + [guardar(r) for r in roteiro])
        self.n += 1
        orq.registrar_evento(self.repo, "emp", self.caso["id"], "mensagem_devedor", f"m{self.n}", {"texto": texto})
        return orq.processar_proximo(self.repo, self.grafos, self.cliente, SEXTA_14H)

    def pendentes(self, tipo=None):
        return [a for a in self.fonte.agenda if a["situacao"] == "pendente" and (tipo is None or a["tipo"] == tipo)]

    def saida(self):
        return [m["texto"] for m in self.repo.mensagens if m["direcao"] == "saida"][-1]


print("— o caso relatado: marcou, não pode mais, pede outro dia —")
m = Mundo()
m.escreve("Pode marcar dia 3 às 10h?", [F("agendar_retorno", data=DIA_3, hora="10:00", motivo="combinado com a pessoa"),
                                         Resposta(texto="Combinado: falo com você dia 03/11 às 10h.")])
checar([(a["data"], a["hora"]) for a in m.pendentes()] == [(DIA_3, "10:00")], "marcou o dia 3")
m.escreve("Não posso mais no dia 3", [Resposta(texto="Sem problema. Qual dia fica melhor para você?")])
checar('"compromissos_marcados"' in m.briefings[-1] and DIA_3 in m.briefings[-1],
       "o agente vê o compromisso marcado (com o id) antes de responder")
# A IA marca de novo em vez de remarcar, e ainda repete a chamada: o sistema não pode duplicar.
m.escreve("Remarca pro dia 13, mesmo horário", [
    F("agendar_retorno", data=DIA_13, hora="10:00", motivo="remarcado a pedido"),
    F("agendar_retorno", data=DIA_13, hora="10:00", motivo="remarcado a pedido"),
    Resposta(texto="Pronto, remarquei para 13/11 às 10h.")])
p = m.pendentes()
checar([(a["data"], a["hora"]) for a in p] == [(DIA_13, "10:00")],
       "fica UM compromisso, no dia novo; o dia 3 não fica pendurado", str([(a["data"], a["hora"]) for a in p]))
checar(m.saida() == "Pronto, remarquei para 13/11 às 10h.", "e a resposta sai normalmente")

print("— remarcar pelo id, sem id e com outra hora —")
m = Mundo()
m.escreve("marca dia 3 às 10h", [F("agendar_retorno", data=DIA_3, hora="10:00", motivo="combinado"), Resposta(texto="Ok.")])
cid = m.pendentes()[0]["id"]
m.escreve("muda pra dia 13 às 15h", [F("remarcar_compromisso", compromisso_id=cid, data=DIA_13, hora="15:00",
                                        motivo="pediu outro dia"), Resposta(texto="Remarcado.")])
checar([(a["id"], a["data"], a["hora"]) for a in m.pendentes()] == [(cid, DIA_13, "15:00")],
       "remarcar muda data e hora do mesmo compromisso")
m.escreve("na verdade dia 3 de novo", [F("remarcar_compromisso", data=DIA_3, motivo="voltou atrás"), Resposta(texto="Ok.")])
checar([(a["data"], a["hora"]) for a in m.pendentes()] == [(DIA_3, "15:00")],
       "sem o id, remarca o único compromisso marcado pelo agente (a hora fica)")
checar(m.repo.obter_caso(m.caso["id"])["dados"].get("remarcacoes") in (None, 0),
       "remarcar conversa não gasta o limite de remarcação de promessa (R12)")

print("— desmarcar —")
m.escreve("não quero mais, pode cancelar", [F("desmarcar_compromisso", motivo="a pessoa desistiu"), Resposta(texto="Desmarquei.")])
checar(m.pendentes() == [] and any(a["situacao"] == "cancelada" for a in m.fonte.agenda),
       "desmarcar cancela o compromisso (fica no histórico como cancelado)")
r = m.escreve("e agora?", [F("desmarcar_compromisso", motivo="de novo"), Resposta(texto="Não há nada marcado.")])
checar(r["ok"], "desmarcar sem nada marcado não quebra")

print("— marcar de novo o mesmo dia e hora não duplica —")
m = Mundo()
m.escreve("marca dia 3 às 10h", [F("agendar_retorno", data=DIA_3, hora="10:00", motivo="x"),
                                 F("agendar_retorno", data=DIA_3, hora="10:00", motivo="x"), Resposta(texto="Ok.")])
checar(len(m.pendentes()) == 1, "a mesma marcação duas vezes vira uma só")

print("— remarcar sem a identidade confirmada —")
m = Mundo(identidade=False)
m.escreve("marca dia 3 às 10h", [F("agendar_retorno", data=DIA_3, hora="10:00", motivo="x"), Resposta(texto="Ok.")])
m.escreve("muda pra dia 13", [F("remarcar_compromisso", data=DIA_13, motivo="pediu"), Resposta(texto="Ok.")])
checar([a["data"] for a in m.pendentes()] == [DIA_13], "quem marcou sem confirmar identidade também consegue remarcar")
m.fonte.agenda.append({"id": "prom1", "empresa_id": "emp", "cpf": DEV["cpf"], "nome": DEV["nome"], "predicao_id": "p1",
                       "operador_id": "x", "operador_nome": "x", "tipo": "promessa", "data": DIA_3, "hora": None,
                       "valor": 270.0, "observacao": "Acordo", "situacao": "pendente"})
m.escreve("muda o pagamento pro dia 13", [F("remarcar_compromisso", compromisso_id="prom1", data=DIA_13, motivo="x"),
                                           Resposta(texto="Ok.")])
checar(next(a for a in m.fonte.agenda if a["id"] == "prom1")["data"] == DIA_3,
       "promessa de pagamento continua exigindo identidade para remarcar")

print("— limite de remarcação (R12) vale para promessa de pagamento —")
m = Mundo()
m.fonte.agenda.append({"id": "prom1", "empresa_id": "emp", "cpf": DEV["cpf"], "nome": DEV["nome"], "predicao_id": "p1",
                       "operador_id": "x", "operador_nome": "x", "tipo": "promessa", "data": DIA_3, "hora": None,
                       "valor": 270.0, "observacao": "Acordo", "situacao": "pendente"})
for i, d in enumerate(["2026-11-04", "2026-11-05", "2026-11-06"]):
    m.escreve(f"muda o pagamento pro dia {d[-2:]}", [F("remarcar_compromisso", compromisso_id="prom1", data=d, motivo="x"),
                                                    Resposta(texto="Ok.")])
checar(next(a for a in m.fonte.agenda if a["id"] == "prom1")["data"] == "2026-11-05",
       "a terceira remarcação da promessa é barrada (máximo 2)")

print("— atendimento com pessoa: pedir de novo atualiza o pedido, não cria outro —")
m = Mundo()
m.escreve("quero falar com alguém dia 3 às 10h", [
    F("marcar_atendimento_humano", data=DIA_3, hora="10:00", motivo="reuniao", resumo="quer conversar"),
    Resposta(texto="Registrei o pedido.")])
caso = m.repo.obter_caso(m.caso["id"])
m.repo.salvar_caso(caso["id"], {"situacao": "em_contato"})       # a equipe devolveu ao agente
m.escreve("prefiro dia 13 às 11h", [
    F("marcar_atendimento_humano", data=DIA_13, hora="11:00", motivo="reuniao", resumo="pediu outro dia"),
    Resposta(texto="Atualizei o pedido.")])
at = [a for a in m.pendentes() if (a.get("observacao") or "").startswith("Atendimento com pessoa")]
checar([(a["data"], a["hora"]) for a in at] == [(DIA_13, "11:00")], "um pedido só, com o dia novo",
       str([(a["data"], a["hora"]) for a in at]))
checar(m.repo.obter_caso(m.caso["id"])["dados"]["atendimento"]["data"] == DIA_13, "o caso aponta o dia novo")

print("— duplicatas antigas viram uma só —")
m = Mundo()
for d in (DIA_3, DIA_13, DIA_13):
    m.fonte.criar_agenda("emp", DEV, "retorno", d, hora="10:00", observacao="Retorno combinado pelo assistente: antigo")
m.fonte.criar_agenda("emp", DEV, "retorno", DIA_3, observacao="Nova mensagem do devedor (caso com_pessoa): responder pela equipe.")
m.escreve("pode ser dia 13 às 10h", [F("agendar_retorno", data=DIA_13, hora="10:00", motivo="x"), Resposta(texto="Ok.")])
meus = [a for a in m.pendentes() if (a["observacao"] or "").startswith("Retorno combinado")]
checar(len(meus) == 1 and meus[0]["data"] == DIA_13, "sobra um retorno do assistente, no dia 13",
       str([(a["data"], a["situacao"]) for a in m.fonte.agenda]))
checar(any((a["observacao"] or "").startswith("Nova mensagem") for a in m.pendentes()),
       "tarefas da equipe (não combinadas com a pessoa) ficam como estão")
from agente import ferramentas                                          # noqa: E402
vistos = ferramentas.compromissos_combinados(m.fonte.agenda_pendente("emp", "p1"), True)
checar([v["o_que"] for v in vistos] == ["retorno do assistente"], "o agente só vê o que foi combinado com a pessoa", str(vistos))

print("— atendimento já aprovado e remarcado volta para aprovação —")
m = Mundo()
m.escreve("quero falar com alguém dia 3 às 10h", [
    F("marcar_atendimento_humano", data=DIA_3, hora="10:00", motivo="reuniao", resumo="quer conversar"), Resposta(texto="Ok.")])
item = m.pendentes()[0]
m.fonte.atualizar_agenda("emp", "p1", item["id"], {"operador_id": "op-luciana", "operador_nome": "Luciana"})
m.repo.salvar_caso(m.caso["id"], {"situacao": "em_contato"})
m.escreve("dá pra ser dia 13?", [F("remarcar_compromisso", compromisso_id=item["id"], data=DIA_13, motivo="pediu"),
                                 Resposta(texto="Pedi a mudança para dia 13 às 10h; a equipe confirma.")])
novo = next(a for a in m.fonte.agenda if a["id"] == item["id"])
checar(novo["data"] == DIA_13 and novo["hora"] == "10:00" and novo["operador_id"] != "op-luciana",
       "o horário novo volta para a equipe aprovar e escolher quem atende", str((novo["data"], novo["operador_id"])))

print("— remarcar sem id quando só há a promessa —")
m = Mundo()
m.fonte.agenda.append({"id": "prom9", "empresa_id": "emp", "cpf": DEV["cpf"], "nome": DEV["nome"], "predicao_id": "p1",
                       "operador_id": "x", "operador_nome": "x", "tipo": "promessa", "data": DIA_3, "hora": None,
                       "valor": 270.0, "observacao": "Acordo", "situacao": "pendente"})
m.escreve("posso pagar dia 13?", [F("remarcar_compromisso", data=DIA_13, motivo="pediu"), Resposta(texto="Ok.")])
checar(next(a for a in m.fonte.agenda if a["id"] == "prom9")["data"] == DIA_13, "sem id, remarca a única promessa")

print("— a hora que fica precisa valer no dia novo —")
m = Mundo()
m.escreve("marca dia 3 às 10h", [F("agendar_retorno", data=DIA_3, hora="10:00", motivo="x"), Resposta(texto="Ok.")])
m.escreve("pode ser domingo dia 15?", [F("remarcar_compromisso", data="2026-11-15", motivo="pediu"), Resposta(texto="Ok.")])
checar([a["data"] for a in m.pendentes()] == [DIA_3], "domingo às 10h está fora dos dias de contato: não remarca")

print("— dizer que desmarcou sem desmarcar é barrado —")
from agente import guardrails                                           # noqa: E402
checar(guardrails.conferir("Pronto, desmarquei o seu retorno.", {"dinheiro": [], "percentuais": set()}, feitas=set()) != [],
       "\"desmarquei\" sem a ferramenta não sai")
checar(guardrails.conferir("Pronto, desmarquei o seu retorno.", {"dinheiro": [], "percentuais": set()},
                           feitas={"desmarcar_compromisso"}) == [], "com a ferramenta, sai")

print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
