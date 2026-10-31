"""Base jurídica nos fluxos reais do agente, com dados fictícios e IA simulada (sem rede):
pedido do titular, tratamento de dados (Telegram), decisão automatizada e estratégia de
cobrança (plano), oferta com sinais de superendividamento, contestação, rotas de
administrador e privacidade dos registros. A fundamentação fica no registro interno;
as mensagens ao devedor não citam lei nem falam da análise.

    python test_juridico_fluxos.py
"""
import json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryptography.fernet import Fernet                                  # noqa: E402
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_ENCRYPTION_KEY=Fernet.generate_key().decode(), MIZAN_AGENTE_ATIVO="1")
for v in ("MIZAN_AGENTE_CLIENTE", "MIZAN_AGENTE_TETO_DIA_USD"):
    os.environ.pop(v, None)
import main                                                             # noqa: E402
from auth import criar_token                                            # noqa: E402
from fastapi.testclient import TestClient                               # noqa: E402
from agente import api, auditor, canal_telegram, guardrails, juridico_orq, negociador, orquestrador as orq  # noqa: E402
from agente.fonte import FonteMemoria                                   # noqa: E402
from agente.grafos import grafo_mensagem                                # noqa: E402
from agente.juridico import conferencia                                 # noqa: E402
from agente.llm import ClienteFalso, Resposta                           # noqa: E402
from agente.repositorio import RepoMemoria                              # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
DEV = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Maria das Dores", "telefone": "(62) 98888-7777",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1"}
ID_OK = {"identidade_ok": True, "divida": 3000.0}
tri = lambda i: json.dumps({"intencao": i, "confianca": 0.9, "valores_citados": [], "datas_citadas": [], "sinais_de_risco": []})
CAMPOS_PASSO = {"acao", "decisao", "registro_id", "reaproveitada", "fundamentos"}
_LEI = re.compile(r"\b(lei|lgpd|cdc|art\.|artigo|súmula|jurídic|parecer|análise interna)", re.I)


def sem_lei(textos):
    return not any(_LEI.search(t or "") for t in textos)


class Mundo:
    def __init__(self, situacao="em_contato", dados=None):
        self.repo, self.fonte = RepoMemoria(), FonteMemoria([DEV])
        self.caso = self.repo.obter_ou_criar_caso("emp", "p1")
        self.repo.salvar_caso(self.caso["id"], {"situacao": situacao, "dados": dados or {}})
        self.repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
        self.grafos = {"mensagem_devedor": grafo_mensagem(self.fonte)}
        self.n, self.cliente = 0, None

    def escreve(self, texto, triagem=None, negociador_=()):
        self.cliente = ClienteFalso({"triagem": [triagem] if triagem else [], "negociador": list(negociador_)})
        self.n += 1
        orq.registrar_evento(self.repo, "emp", self.caso["id"], "mensagem_devedor", f"m{self.n}", {"texto": texto})
        return orq.processar_proximo(self.repo, self.grafos, self.cliente, SEXTA_14H)

    @property
    def c(self):
        return self.repo.obter_caso(self.caso["id"])

    def saidas(self):
        return [m["texto"] for m in self.repo.mensagens if m["direcao"] == "saida"]

    def juridico(self):
        return self.repo.consultas_juridicas("emp")

    def passos_juridicos(self):
        return [p for p in self.repo.passos if p["no"] == "consulta_juridica"]

    def chamou_negociador(self):
        return any(c.get("papel") == "negociador" for c in self.cliente.chamadas)


print("— pedido do titular: acesso aos dados —")
m = Mundo()
vistos = []
def resp(_s, msgs):
    vistos.append(json.dumps(msgs, ensure_ascii=False))
    return Resposta(texto="Pode, sim: você tem direito a saber quais dados temos sobre você. Registrei seu pedido, "
                          "e a resposta completa sai em até 15 dias.")
m.escreve("Oi, quero saber quais dados vocês têm sobre mim", tri("duvida"), [resp])
obs = [a.get("observacao") or "" for a in m.fonte.agenda]
checar(any("Pedido sobre os dados pessoais (acesso aos dados)" in o and "15 dias" in o for o in obs),
       "pedido registrado na agenda da equipe, com o prazo", str(obs))
j = m.juridico()
checar(len(j) == 1 and j[0]["acao"] == "pedido_titular" and j[0]["decisao"] == "revisao_humana" and j[0]["caso_id"] == m.caso["id"],
       "decisão interna: pedido do titular → revisão humana, no caso", str([(x["acao"], x["decisao"]) for x in j]))
checar(any(d["id"].startswith("lgpd:18") for d in j[0]["dispositivos"]) and any(f["norma_id"] == "lgpd" for f in j[0]["fontes"]),
       "o registro traz os dispositivos e as fontes consultados")
checar((m.c["dados"].get("pedidos_titular") or [{}])[0].get("tipo") == "acesso", "o caso guarda o tipo do pedido (sem o texto)")
checar(vistos and "pedido_sobre_dados_registrado" in vistos[0], "o briefing avisa o atendente que o pedido foi registrado")
checar(m.c["situacao"] == "em_contato" and m.saidas() and "15 dias" in m.saidas()[-1] and sem_lei(m.saidas()),
       "a conversa segue; a resposta diz o direito e o prazo, sem citar lei", str(m.saidas()))
checar(all(set(p.get("detalhe") or {}) <= CAMPOS_PASSO for p in m.passos_juridicos()) and m.passos_juridicos(),
       "o rastreio da operação só leva ação e conclusão da consulta", str([p.get("detalhe") for p in m.passos_juridicos()]))

print("— pedido do titular: eliminação passa para uma pessoa —")
m = Mundo(dados=ID_OK)
m.escreve("Quero que apaguem meus dados", tri("duvida"))
s = m.saidas()
checar(m.c["situacao"] == "com_pessoa" and not m.chamou_negociador(), "uma pessoa assume, sem a IA de conversa")
checar(s and "Registrei seu pedido sobre os seus dados (eliminação de dados)" in s[-1] and "manti" in s[-1] and sem_lei(s),
       "a mensagem confirma o pedido, diz quem responde e que dado mantido terá motivo, sem lei", str(s))
checar(any(x["acao"] == "pedido_titular" for x in m.juridico()), "decisão interna registrada")

print("— pedido sobre os dados junto com o pedido de parar —")
m = Mundo()
m.escreve("Apaguem meus dados e não me mande mais mensagem")
s = m.saidas()
checar(m.c["situacao"] == "suspenso" and any("eliminação de dados" in (a.get("observacao") or "") for a in m.fonte.agenda),
       "cobrança suspensa e o pedido de eliminação registrado", m.c["situacao"])
checar(s and "não vamos mais entrar em contato" in s[-1] and "Também registrei seu pedido" in s[-1] and sem_lei(s),
       "a confirmação diz as duas coisas", str(s))

print("— caso com a equipe: o pedido sobre os dados também fica registrado —")
m = Mundo(situacao="com_pessoa", dados=ID_OK)
m.escreve("quero corrigir meu endereço no cadastro")
checar(any("correção de dados" in (a.get("observacao") or "") for a in m.fonte.agenda)
       and any(x["acao"] == "pedido_titular" for x in m.juridico()), "registrado mesmo com a conversa na equipe")

print("— contestação: registro consultivo, a cobrança suspende —")
m = Mundo()
m.escreve("Não reconheço essa dívida")
checar(m.c["situacao"] == "contestado" and any(x["acao"] == "contestacao" and x["decisao"] == "prosseguir_com_condicoes"
                                              for x in m.juridico()), "contestação registrada; decisão interna com condições")
checar(sem_lei(m.saidas()), "a mensagem não cita lei")

print("— oferta: aceite com sinais de superendividamento —")
m = Mundo(dados=ID_OK)
m.escreve("Quero pagar à vista", tri("pagar_negociar"), [
    Resposta(ferramentas=[{"id": "s1", "nome": "simular_acordo", "args": {"n_parcelas": 1, "desconto_pct": 10}}]),
    Resposta(texto="À vista com 10% de desconto fica R$ 2.700,00. Confirma?")])
sim = m.c["dados"]["simulacoes"][-1]["id"]
m.escreve("Aceito, pago dia 20. Mas tenho várias dívidas e não sobra nada pra comer", tri("pagar_negociar"), [
    Resposta(ferramentas=[{"id": "a1", "nome": "registrar_aceite",
                           "args": {"simulacao_id": sim, "data_primeiro_pagamento": "2026-10-20"}}])])
s = m.saidas()
checar(not m.fonte.ofertas and m.c["situacao"] == "com_pessoa", "acordo não registrado; uma pessoa confere antes")
checar(any(x["acao"] == "oferta_credito" and x["decisao"] == "revisao_humana" for x in m.juridico()),
       "decisão interna: revisão humana (mínimo existencial)")
checar(s and "equipe" in s[-1] and sem_lei(s), "a pessoa ouve que a equipe continua, sem lei nem análise", s[-1] if s else "")

print("— dúvida sobre direitos: palavras simples; a lei só quando pedida —")
m = Mundo()
m.escreve("Quanto tempo meu nome fica sujo?", tri("duvida"), [
    Resposta(ferramentas=[{"id": "b1", "nome": "consultar_base", "args": {"pergunta": "quanto tempo meu nome fica sujo"}}]),
    Resposta(texto="Pelo CDC, art. 43, § 1º, no máximo cinco anos."),
    Resposta(texto="No máximo cinco anos no cadastro de inadimplentes.")])
checar(m.saidas() == ["Olá, Maria! Aqui é o assistente virtual de Banco Demonstração. No máximo cinco anos no cadastro de inadimplentes."],
       "citação sem pedido é barrada e refeita", str(m.saidas()))
m.escreve("E qual é a lei que diz isso?", tri("duvida"), [
    Resposta(ferramentas=[{"id": "b2", "nome": "consultar_base", "args": {"pergunta": "quanto tempo meu nome fica sujo"}}]),
    Resposta(texto="É o Código de Defesa do Consumidor (CDC, art. 43, § 1º).")])
checar(m.saidas()[-1].startswith("É o Código de Defesa do Consumidor"), "pediu a lei: cita como veio da base", m.saidas()[-1])

print("— estratégia de cobrança e decisão automatizada: o plano —")
juridico_orq.limpar_cache()
devs = [{"id": f"p{i}", "empresa_id": "emp", "cpf": f"{i:011d}", "nome": f"Pessoa {i} Silva", "valor_divida": 1000.0 + i,
         "probabilidade_pagamento": 0.3} for i in range(6)]
repo, fonte = RepoMemoria(), FonteMemoria(devs)
repo.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "percentual_controle": 0})
api.fabrica_repo, api.fabrica_fonte, api.fabrica_cliente = (lambda: repo), (lambda: fonte), (lambda: ClienteFalso())
r = api.aplicar_plano("emp", agora=SEXTA_14H)
checar(r.get("contagem") and {d["acao"]: d["decisao"] for d in r["juridico"]} ==
       {"estrategia_cobranca": "prosseguir_com_condicoes", "decisao_automatizada_credito": "prosseguir_com_condicoes"},
       "política em horário comercial: o plano é aplicado, com as duas decisões internas", str(r.get("juridico"))[:200])
checar(any(m_["direcao"] == "saida" for m_ in repo.mensagens), "a primeira abordagem sai")
emp_regs = repo.consultas_juridicas("emp")
checar({x["acao"] for x in emp_regs} == {"estrategia_cobranca", "decisao_automatizada_credito"}
       and all(x["caso_id"] is None for x in emp_regs), "decisões de nível empresa: registradas uma vez, sem caso",
       str([(x["acao"], x["caso_id"]) for x in emp_regs]))
checar(any(p["no"] == "consulta_juridica" and (p.get("detalhe") or {}).get("reaproveitada") for p in repo.passos),
       "os casos seguintes reaproveitam a mesma decisão (sem consultar de novo)")

repo2, fonte2 = RepoMemoria(), FonteMemoria(devs)
repo2.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "percentual_controle": 0, "hora_fim": 22,
                                 "dias_semana": [0, 1, 2, 3, 4, 5, 6]})
api.fabrica_repo, api.fabrica_fonte = (lambda: repo2), (lambda: fonte2)
r = api.aplicar_plano("emp", agora=SEXTA_14H)
checar(r.get("aplicado") is False and r["revisao_juridica"] and r["revisao_juridica"][0]["acao"] == "estrategia_cobranca"
       and not repo2.casos and not repo2.mensagens, "contato até 22h e aos domingos: nada aplicado, revisão humana",
       str(r)[:200])

print("— trava no contato iniciado pelo agente (fora do plano) —")
repo3, fonte3 = RepoMemoria(), FonteMemoria(devs[:1])
repo3.gravar_politica("emp", 1, {**auditor.POLITICA_DEMONSTRACAO, "dias_semana": [0, 1, 2, 3, 4, 5, 6]})
caso3 = repo3.obter_ou_criar_caso("emp", "p0")
from agente.estrategista import grafo_abordagem                         # noqa: E402
orq.registrar_evento(repo3, "emp", caso3["id"], "abordagem", "ab1", {"com_ia": False})
orq.processar_proximo(repo3, {"abordagem": grafo_abordagem(fonte3)}, ClienteFalso(), SEXTA_14H)
checar(repo3.obter_caso(caso3["id"])["situacao"] == "novo" and not repo3.mensagens
       and any(p["no"] == "consulta_juridica" and p["resultado"] == "bloqueado" for p in repo3.passos),
       "política com contato aos domingos: a abordagem não sai e fica para revisão")

print("— Telegram: canal e uso do identificador do chat —")
REPO, FONTE = RepoMemoria(), FonteMemoria([{**DEV, "empresa_id": "goias"}, {**DEV, "id": "p2", "empresa_id": "goias"}])
REPO.gravar_politica("goias", 1, auditor.POLITICA_DEMONSTRACAO)
api.fabrica_repo, api.fabrica_fonte, api.fabrica_cliente = (lambda: REPO), (lambda: FONTE), (lambda: ClienteFalso())
ENVIADOS = []
canal_telegram.enviar_texto = lambda chat, texto: (ENVIADOS.append((str(chat), texto)) or True)
canal_telegram.apagar_mensagem = lambda chat, mid: True
canal_telegram.enviar_acao = lambda chat, acao="typing": True
os.environ.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="segredo-forte", TELEGRAM_BOT_USERNAME="mizan_bot")
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
cli = TestClient(main.app, raise_server_exceptions=False)
def jwt(empresa, role="admin", sub="adm"):
    return {"Authorization": "Bearer " + criar_token({"sub": sub, "email": f"{sub}@x", "nome": "Adm", "role": role,
                                                      "empresa_id": empresa})}
ADM, OP = jwt("goias"), jwt("goias", "operador", "op")
H = {"X-Telegram-Bot-Api-Secret-Token": "segredo-forte"}
def start(codigo, uid, chat):
    return cli.post("/canal/telegram/webhook", headers=H, json={"update_id": uid, "message": {
        "message_id": uid, "chat": {"id": chat, "type": "private"}, "from": {"is_bot": False}, "text": f"/start {codigo}"}})

cod = cli.post("/agente/casos/p1/telegram-convite", headers=ADM).json()["codigo"]
start(cod, 10, 777)
caso1 = REPO.caso_de("goias", "p1")
regs = REPO.consultas_juridicas("goias", caso_id=caso1["id"])
checar({x["acao"] for x in regs} == {"comunicacao_devedor", "uso_dados_pessoais"}
       and all(x["decisao"] == "prosseguir_com_condicoes" for x in regs), "canal e dados: prosseguir com condições",
       str([(x["acao"], x["decisao"]) for x in regs]))
checar((caso1["dados"].get("telegram") or {}).get("chat_id") == "777", "o chat fica ligado")
checar(sem_lei([t for _, t in ENVIADOS]), "nenhuma mensagem do Telegram cita lei ou a análise")

original = juridico_orq.avaliar_e_registrar
def barra(repo, emp, caso_id, acao, fatos, trace_id=None, agora=None):
    d = original(repo, emp, caso_id, acao, fatos, trace_id=trace_id, agora=agora)
    return {**d, "decisao": "revisao_humana"} if acao == "comunicacao_devedor" else d
juridico_orq.avaliar_e_registrar = barra
ENVIADOS.clear()
cod2 = cli.post("/agente/casos/p2/telegram-convite", headers=ADM).json()["codigo"]
r = start(cod2, 11, 888).json()
caso2 = REPO.caso_de("goias", "p2")
juridico_orq.avaliar_e_registrar = original
checar(r.get("ok") and not (caso2["dados"].get("telegram") or {}).get("chat_id"),
       "canal em revisão: o chat não fica ligado", str(caso2["dados"].get("telegram")))
checar(ENVIADOS and ENVIADOS[-1][1] == canal_telegram.MSG_CANAL_EM_REVISAO and sem_lei([ENVIADOS[-1][1]]),
       "a pessoa recebe uma mensagem neutra, sem lei")
checar(caso2["situacao"] == "novo" and not [m_ for m_ in REPO.mensagens if m_["caso_id"] == caso2["id"]],
       "nenhuma abordagem sai pelo canal em revisão")

print("— rotas de administrador e controle de acesso —")
REPO.gravar_consulta_juridica({"empresa_id": "beta", "caso_id": "x", "acao": "uso_dados_pessoais", "decisao": "prosseguir",
                               "contexto_cifrado": None})
checar(cli.get("/agente/juridico/decisoes", headers=OP).status_code == 403, "operador não lê os registros jurídicos")
checar(cli.post("/agente/juridico/consultar", headers=OP, json={"pergunta": "revisão de decisão"}).status_code == 403,
       "operador não consulta a base")
checar(cli.get("/agente/juridico/decisoes").status_code in (401, 403), "sem login: recusado")
d = cli.get("/agente/juridico/decisoes", headers=ADM).json()["decisoes"]
checar(d and all(x["empresa_id"] == "goias" for x in d) and all("contexto_cifrado" not in x for x in d)
       and any(x.get("fatos") for x in d), "administrador lê só os da própria empresa, com os fatos decifrados")
d = cli.get(f"/agente/juridico/decisoes?caso_id={caso1['id']}", headers=ADM).json()["decisoes"]
checar(d and all(x["caso_id"] == caso1["id"] for x in d), "filtro por caso")
q = cli.post("/agente/juridico/consultar", headers=ADM,
             json={"pergunta": "Maria CPF 123.456.789-00 pediu revisão da decisão automatizada"}).json()
checar(q["dispositivos"] and any(x["id"].startswith("lgpd:20") for x in q["dispositivos"]) and "123.456" not in json.dumps(q)
       and "Maria" not in q["pergunta"], "consulta do administrador: dispositivos, sem dado pessoal", q["pergunta"])
f = cli.get("/agente/juridico/fontes", headers=ADM).json()
checar(len(f["normas"]) == 8 and f["indice"]["commit"] and all(n["url_oficial"] and n["commit"] for n in f["normas"])
       and f["descartadas"], "fontes: as 8 normas com commit, fonte oficial e as descartadas")

print("— conferência oficial pelo servidor —")
def sem_rede(url):
    raise OSError("sem rede no teste")
conferencia._buscar = sem_rede
checar(cli.post("/agente/juridico/conferir", headers=OP).status_code == 403, "operador não dispara a conferência")
r = cli.post("/agente/juridico/conferir", headers=ADM).json()
for _ in range(100):
    if not juridico_orq.estado_conferencia()["rodando"]:
        break
    time.sleep(0.05)
confs = REPO.conferencias_juridicas()
checar(r.get("iniciada") and len(confs) == 8 and all(c["status"] == "nao_conferida" and c.get("sha256_arquivo") for c in confs.values()),
       "roda em segundo plano e grava o resultado de cada norma (sem rede: não conferida)", str(r))

print("— privacidade dos registros —")
todos = json.dumps([REPO.consultas_juridicas_, m.repo.consultas_juridicas_, repo.consultas_juridicas_], ensure_ascii=False, default=str)
checar(not any(x in todos for x in ("Maria", "das Dores", "123.456", "98888", "várias dívidas", "apaguem")),
       "registros sem nome, CPF, telefone nem o texto do devedor")
cifrados = [x["contexto_cifrado"] for x in REPO.consultas_juridicas_ if x.get("contexto_cifrado")]
checar(cifrados and all(c.startswith("fernet:") for c in cifrados), "fatos cifrados com a chave Fernet da Mizan")
checar(not any("lgpd:" in json.dumps(p, default=str) for p in m.repo.passos), "a fundamentação não vai para o rastreio da operação")

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
