"""Agentes — Acompanhamento: relógio de datas, lembretes, atraso, sem resposta e
pagamentos. Sem IA (mensagens prontas), sem banco.

    python test_agente_acompanhamento.py
"""
import os, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_ATIVO", "MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
from agente import acompanhamento as acp, api, auditor, orquestrador as orq   # noqa: E402
from agente.fonte import FonteMemoria                                        # noqa: E402
from agente.llm import ClienteFalso                                          # noqa: E402
from agente.repositorio import RepoMemoria                                   # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

BR = auditor.BRASILIA
def em(dia, hora=14):                       # hora de Brasília → UTC
    return datetime(dia.year, dia.month, dia.day, hora, tzinfo=BR).astimezone(timezone.utc)
SEX = date(2026, 10, 16)
DEV = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Maria das Dores", "valor_divida": 3000.0}

class Mundo:
    def __init__(self, situacao="acordo_ativo", venc=SEX + timedelta(days=4), valor=270.0, n_parcelas=6, controle=False):
        self.repo, self.fonte = RepoMemoria(), FonteMemoria([DEV])
        self.caso = self.repo.obter_ou_criar_caso("emp", "p1")
        acordo = {"condicoes": {"n_parcelas": n_parcelas, "desconto_pct": 10, "entrada_pct": 10}, "primeiro_pagamento": valor,
                  "data": venc.isoformat()}
        self.repo.salvar_caso(self.caso["id"], {"situacao": situacao, "grupo_controle": controle,
                                                "dados": {"identidade_ok": True, "divida": 3000.0, "acordo": acordo}})
        self.repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
        self.item = self.fonte.criar_agenda("emp", DEV, "promessa", venc.isoformat(), valor=valor)
        self.grafos = api.grafos(self.fonte)
    def relogio(self, agora):
        criados = acp.planejar(self.repo, self.fonte, "emp", agora)
        orq.processar_fila(self.repo, self.grafos, ClienteFalso(), agora=agora)
        return criados
    @property
    def c(self): return self.repo.obter_caso(self.caso["id"])
    def saidas(self): return [m["texto"] for m in self.repo.mensagens if m["direcao"] == "saida"]

print("— dias úteis —")
checar(acp.dia_util(date(2026, 10, 17)) == date(2026, 10, 19), "sábado conta na segunda")
checar(acp.somar_dias_uteis(date(2026, 10, 16), 2) == date(2026, 10, 20), "sexta + 2 dias úteis = terça")

print("— lembrete —")
m = Mundo(venc=SEX + timedelta(days=1))                     # vence sábado → conta segunda (19/10)
checar(m.relogio(em(SEX)) == [], "sábado não é véspera: segunda é o vencimento efetivo")
m = Mundo(venc=SEX + timedelta(days=4))                     # terça 20/10
m.relogio(em(SEX + timedelta(days=3)))                      # segunda 14h
s = m.saidas()
checar(len(s) == 1 and "R$ 270,00" in s[0] and "amanhã (20/10)" in s[0] and s[0].startswith("Olá, Maria!"),
       "véspera: lembrete pronto com valor e data, sem IA", str(s))
m.relogio(em(SEX + timedelta(days=3), 16))
checar(len(m.saidas()) == 1, "o relógio rodando de novo no mesmo dia não repete o lembrete")
m.relogio(em(SEX + timedelta(days=4)))
checar(len(m.saidas()) == 1, "no dia: não repete (um lembrete por compromisso e vencimento)", str(m.saidas()))

m = Mundo(venc=SEX + timedelta(days=4))
m.relogio(em(SEX + timedelta(days=3), 6))                   # segunda 6h: fora do horário
ev = [e for e in m.repo.eventos.values() if e["tipo"] == "vencimento"][0]
checar(m.saidas() == [] and ev["situacao"] == "pendente" and ev["disponivel_em"] == em(SEX + timedelta(days=3), 8),
       "fora do horário: espera até as 8h, sem contar como falha")
orq.processar_fila(m.repo, m.grafos, ClienteFalso(), agora=em(SEX + timedelta(days=3), 8))
checar(len(m.saidas()) == 1, "às 8h o lembrete sai")

print("— quem não é procurado —")
for sit in ("suspenso", "contestado", "com_pessoa", "pagamento_em_conferencia"):
    m = Mundo(situacao=sit)
    if sit in ("pagamento_em_conferencia",):
        m.relogio(em(SEX + timedelta(days=3)))
    else:
        orq.registrar_evento(m.repo, "emp", m.caso["id"], "vencimento", "x",
                             {"compromisso_id": m.item["id"], "valor": 270, "data": "2026-10-20", "fase": "lembrete"})
        orq.processar_fila(m.repo, m.grafos, ClienteFalso(), agora=em(SEX + timedelta(days=3)))
    checar(m.saidas() == [], f"caso {sit}: nenhum lembrete")
m = Mundo(controle=True)
checar(m.relogio(em(SEX + timedelta(days=3))) == [] and m.saidas() == [], "grupo sorteado: o agente não toca")
m = Mundo()
m.fonte.atualizar_agenda("emp", "p1", m.item["id"], {"situacao": "cumprida"})
orq.registrar_evento(m.repo, "emp", m.caso["id"], "vencimento", "x",
                     {"compromisso_id": m.item["id"], "valor": 270, "data": "2026-10-20", "fase": "lembrete"})
orq.processar_fila(m.repo, m.grafos, ClienteFalso(), agora=em(SEX + timedelta(days=3)))
checar(m.saidas() == [], "pagou antes do lembrete sair: lembrete cancelado")

print("— atraso —")
m = Mundo(venc=SEX + timedelta(days=4))                    # terça 20/10; confirmação até quinta 22/10
m.relogio(em(date(2026, 10, 22)))
checar(not any("Ainda não identificamos" in t for t in m.saidas()), "dentro do prazo de confirmação do banco: ninguém é cobrado")
m.relogio(em(date(2026, 10, 23)))
s = m.saidas()
checar(any("Ainda não identificamos o pagamento de R$ 270,00 previsto para 20/10" in t for t in s) and m.c["situacao"] == "atrasado",
       "passado o prazo: procura o devedor, sem acusar; acordo vira atrasado")
checar("remarcar" in m.c["dados"]["objetivo"], "o Negociador recebe o objetivo de entender e remarcar")
m.relogio(em(date(2026, 10, 27)))
checar(m.c["situacao"] == "atrasado", "ainda dentro dos 3 dias úteis de espera da resposta")
m.relogio(em(date(2026, 10, 28)))
c = m.c
checar(c["situacao"] == "com_pessoa" and m.fonte.agenda[0]["situacao"] == "quebrada"
       and any("não respondeu" in (a.get("observacao") or "") for a in m.fonte.agenda),
       "sem resposta: promessa quebrada e uma pessoa assume, com resumo")

m = Mundo(venc=SEX + timedelta(days=4))
m.relogio(em(date(2026, 10, 23)))
m.repo.gravar_mensagem("emp", m.caso["id"], "entrada", "recebo dia 30, posso pagar depois?", criado_em=em(date(2026, 10, 24)))
m.relogio(em(date(2026, 10, 28)))
checar(m.c["situacao"] == "atrasado" and m.fonte.agenda[0]["situacao"] == "pendente", "respondeu: a conversa segue, nada é quebrado")

print("— pagamento —")
m = Mundo(n_parcelas=1, valor=2700.0)
api.fabrica_repo, api.fabrica_fonte, api.fabrica_cliente = (lambda: m.repo), (lambda: m.fonte), (lambda: ClienteFalso())
os.environ["MIZAN_AGENTE_ATIVO"] = "1"
api.simular_pagamento("emp", "p1", 2700.0, agora=em(SEX))
checar(m.c["situacao"] == "quitado" and m.fonte.agenda[0]["situacao"] == "cumprida", "à vista pago: promessa cumprida, quitado")
checar(m.saidas() == ["Olá, Maria. Recebemos o seu pagamento de R$ 2.700,00. Obrigado!"], "agradece com o valor certo")

m = Mundo(valor=270.0)
api.fabrica_repo, api.fabrica_fonte = (lambda: m.repo), (lambda: m.fonte)
api.simular_pagamento("emp", "p1", 200.0, agora=em(SEX))
checar(m.c["situacao"] == "acordo_ativo" and "faltam R$ 70,00" in m.saidas()[0]
       and any("Conferir a baixa" in (a.get("observacao") or "") for a in m.fonte.agenda),
       "pagou menos: mostra o que falta; a baixa parcial fica com a equipe")

m = Mundo(situacao="pagamento_em_conferencia", valor=270.0)
api.fabrica_repo, api.fabrica_fonte = (lambda: m.repo), (lambda: m.fonte)
api.simular_pagamento("emp", "p1", 270.0, agora=em(SEX))
checar(m.c["situacao"] == "acordo_ativo" and "pagamento_informado" not in m.c["dados"], "'já paguei' confirmado: volta ao acordo")

m = Mundo(situacao="suspenso")
api.fabrica_repo, api.fabrica_fonte = (lambda: m.repo), (lambda: m.fonte)
api.simular_pagamento("emp", "p1", 270.0, agora=em(SEX))
checar(m.saidas() == [] and m.c["situacao"] == "suspenso", "pediu para não ser contatado: pagamento registrado, sem mensagem")

m = Mundo(n_parcelas=1, valor=2700.0)
api.fabrica_repo, api.fabrica_fonte = (lambda: m.repo), (lambda: m.fonte)
api.simular_pagamento("emp", "p1", 2700.0, agora=em(SEX, 22))
checar(m.c["situacao"] == "quitado" and m.saidas() == [], "pagamento às 22h: registra; não escreve fora do horário")

print("— ciclo do servidor —")
m = Mundo(venc=SEX + timedelta(days=4))
api.fabrica_repo, api.fabrica_fonte = (lambda: m.repo), (lambda: m.fonte)
r = api.ciclo_agendado(agora=em(SEX + timedelta(days=3)))
checar(r["eventos_criados"] == 1 and r["processados"] == 1 and len(m.saidas()) == 1, "o agendador roda o relógio e a fila", str(r))
os.environ.pop("MIZAN_AGENTE_ATIVO")
checar(api.ciclo_agendado() == {"ligado": False}, "desligado: o agendador não faz nada")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
