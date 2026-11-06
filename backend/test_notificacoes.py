"""Notificações para administradores e operadores (docs/NOTIFICACOES.md). Sem rede e sem banco.

    python test_notificacoes.py

Cobre o núcleo (destino, agrupamento, repetição, privacidade, disjuntor), os gatilhos do
agente e das rotas, o relógio (lembretes, 8h, 9h, prazos, escalonamento, limpeza, e-mail)
e as rotas /notificacoes (autorização, preferências, sem tabela).
"""
import os, sys, uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
os.environ.update(SUPABASE_URL="http://127.0.0.1:1", SUPABASE_KEY="x", JWT_SECRET="teste",
                  MIZAN_NOTIFICACOES_ASSINCRONO="0", MIZAN_NOTIFICACOES="1")
for v in ("MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
import notificacoes as N                                             # noqa: E402
from agente import auditor, ferramentas as fer, mudancas, orquestrador as orq   # noqa: E402
from agente.fonte import FonteMemoria                               # noqa: E402
from agente.llm import ClienteFalso                                 # noqa: E402
from agente.repositorio import RepoMemoria                          # noqa: E402

N.ASSINCRONO = False
falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

UTC = timezone.utc
SEXTA_14H = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)          # 14h de Brasília, sexta-feira
PESSOAS = [
    {"id": "op1", "nome": "Ana Lima", "email": "ana@x", "role": "operador", "ativo": True, "empresa_id": "emp"},
    {"id": "op2", "nome": "Beto Souza", "email": "beto@x", "role": "operador", "ativo": True, "empresa_id": "emp"},
    {"id": "op3", "nome": "Caio Saiu", "email": "caio@x", "role": "operador", "ativo": False, "empresa_id": "emp"},
    {"id": "adm1", "nome": "Carla Gestora", "email": "carla@x", "role": "admin", "ativo": True, "empresa_id": "emp"},
    {"id": "adm2", "nome": "Davi Gestor", "email": "davi@x", "role": "admin", "ativo": True, "empresa_id": "emp"},
    {"id": "cmd", "nome": "Comando", "email": "cmd@x", "role": "comando", "ativo": True, "empresa_id": "emp"},
    {"id": "op9", "nome": "Outra Empresa", "email": "o@x", "role": "operador", "ativo": True, "empresa_id": "outra"},
    {"id": "adm9", "nome": "Admin Outra", "email": "a9@x", "role": "admin", "ativo": True, "empresa_id": "outra"},
]
DEV = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "MARIA DAS DORES",
       "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1"}


def novo(agenda=None):
    a = N.ArmazemMemoria(usuarios=PESSOAS, agenda=agenda)
    N.usar_armazem(a)
    N._DISJUNTOR.update(seguidas=0, ate=0.0, log_em=0.0)
    N._RODOU.clear(); N._ULTIMO.clear()
    return a

def de(a, usuario=None, tipo=None):
    return [l for l in a.linhas if (usuario is None or l["usuario_id"] == usuario) and (tipo is None or l["tipo"] == tipo)]


print("— texto —")
m = N.montar("N01", {"nome": "MARIA DAS DORES", "predicao_id": "p1", "situacao": "com a equipe"}, "operador")
checar(m["titulo"] == "Maria escreveu de novo" and m["link"] == "/pasta/p1?aba=conversa", "só o primeiro nome, com o link da conversa", m["titulo"])
checar(N.montar("N10", {"nome": "123.456.789-00", "predicao_id": "p1", "hora": "14:30", "minutos": 5})["titulo"]
       == "Reunião com Cliente em 5 minutos", "nome com número (um CPF por engano) não aparece")
checar(N.montar("N01", {"nome": "Ana", "predicao_id": "p1"}, n=3)["titulo"] == "Ana mandou 3 mensagens", "vários juntos: versão em grupo")
checar(N.montar("N06", {"nome": "João", "predicao_id": "p2", "quando": "amanhã às 14:30"}, "operador")["link"] == "/agenda"
       and N.montar("N06", {"nome": "João", "predicao_id": "p2", "quando": "x"}, "admin")["link"] == "/agente?aba=agenda",
       "operador e administrador recebem a versão do seu papel (o operador não abre a tela dos agentes)")
checar(N._link("https://golpe.example", {}) == "/inicio" and N._link("//golpe.example", {}) == "/inicio"
       and N._link("/pasta/{predicao_id}", {"predicao_id": "a b"}) == "/inicio", "link só para tela interna do Mizan")
checar(N.montar("N14", {"nome": "Ana", "hora": "10:00"})["link"] == "/agenda", "sem o id do devedor, o link cai na agenda")
modelos = " ".join(" ".join(str(v) for v in (t.titulo, t.texto, t.externo, t.titulo_grupo, t.texto_grupo,
                                              *[str(x) for x in t.por_papel.values()], *[str(x) for x in t.variantes.values()]))
                   for t in N.CATALOGO.values())
checar(not any(p in modelos.lower() for p in ("{cpf", "{valor", "r$", "{divida")),
       "nenhum modelo de texto leva CPF ou valor")
checar(all("{" not in t.externo for t in N.CATALOGO.values()) and all("{nome" not in t.externo for t in N.CATALOGO.values()),
       "o título de fora do Mizan (navegador, e-mail) é fixo, sem nome")
checar(len(N.CATALOGO) == 34 and {f"N{i:02d}" for i in range(1, 34)} | {"ESC"} == set(N.CATALOGO),
       "catálogo com os 33 eventos do mapa e o escalonamento")
checar(N.quando("2026-11-07", "14:30:00", SEXTA_14H) == "amanhã às 14:30" and N.quando("2026-11-06", None, SEXTA_14H) == "hoje"
       and N.quando("2026-11-20", "9:00", SEXTA_14H) == "20/11 às 9:00", "quando: hoje, amanhã e data")

lidas_pela_tela = {"id", "tipo", "categoria", "prioridade", "titulo", "texto", "link", "acao", "agrupadas",
                   "criado_em", "atualizado_em", "lida_em", "resolvida_em"}
colunas = {c.strip() for c in N.ArmazemSupabase._COLUNAS.split(",")}
checar(lidas_pela_tela <= colunas, "a consulta de produção traz tudo o que a tela mostra (o botão também)",
       str(lidas_pela_tela - colunas))

print("— preferências e horário silencioso —")
p = N.preferencias_validas({"navegador": "sim", "silencio_inicio": 30, "silencio_fim": 7, "desligadas": ["equipe", "xyz"],
                            "email_resumo": True})
checar(p["navegador"] is False and p["silencio_inicio"] == 20 and p["silencio_fim"] == 7 and p["desligadas"] == ["equipe"]
       and p["email_resumo"] is True, "valores errados viram o padrão; categoria desconhecida some", str(p))
noite, tarde, madrugada = (datetime(2026, 11, 6, h, 30, tzinfo=UTC) for h in (23, 17, 9))    # 20:30, 14:30 e 6:30 de Brasília
checar(N.em_silencio({}, noite) and N.em_silencio({}, madrugada) and not N.em_silencio({}, tarde), "das 20h às 8h é silêncio")
checar(not N.em_silencio({"silencio_ligado": False}, noite), "silêncio desligado: nunca")
checar(N.toca_agora("urgente", {}, noite) and not N.toca_agora("alta", {}, noite) and N.toca_agora("alta", {}, tarde)
       and not N.toca_agora("normal", {}, tarde), "no silêncio só o urgente toca; o normal nunca toca")

print("— destino —")
a = novo()
nomes = lambda l: sorted(p["id"] for p in l)
checar(nomes(N.destinatarios("emp", devedor=DEV)) == ["op1"], "o responsável pelo devedor")
checar(nomes(N.destinatarios("emp", devedor={**DEV, "responsavel_id": None})) == ["adm1", "adm2"], "sem responsável: os administradores")
checar(nomes(N.destinatarios("emp", devedor={**DEV, "responsavel_id": "agente-mizan"})) == ["adm1", "adm2"], "com o agente: os administradores")
checar(nomes(N.destinatarios("emp", devedor={**DEV, "responsavel_id": "op3"})) == ["adm1", "adm2"], "responsável desligado: os administradores")
checar(nomes(N.destinatarios("emp", devedor=DEV, admins=True)) == ["adm1", "adm2", "op1"], "responsável e administradores juntos, sem repetir")
checar(nomes(N.destinatarios("emp", devedor={**DEV, "responsavel_id": "op9"})) == ["adm1", "adm2"], "pessoa de outra empresa nunca recebe")
checar(nomes(N.destinatarios("emp", usuarios=["cmd"])) == ["adm1", "adm2"], "o COMANDO não tem sino")
checar(nomes(N.destinatarios("emp", admins=True, exceto="adm1")) == ["adm2"], "quem fez a ação não recebe")
checar(N.destinatarios("emp", usuarios=["op3"], ou_admins=False) == [], "sem ninguém válido e sem cair para os administradores: ninguém")

print("— gravar: único, agrupar e categoria desligada —")
a = novo()
N.notificar("N22", "emp", devedor=DEV, admins=True, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N22:c1",
            entidade=("devedor", "p1"))
N.notificar("N22", "emp", devedor=DEV, admins=True, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N22:c1")
checar(sorted(l["usuario_id"] for l in a.linhas) == ["adm1", "adm2", "op1"], "único: a mesma chave não sai duas vezes")
a.marcar_lidas("op1", "emp")
N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "Maria"}, chave="N22:c1")
checar(len(de(a, "op1")) == 1, "único: nem depois de lida")
for _ in range(3):
    N.notificar("N01", "emp", devedor=DEV, contexto={"nome": "Maria", "predicao_id": "p1", "situacao": "com a equipe"},
                chave="N01:c1")
n01 = de(a, "op1", "N01")
checar(len(n01) == 1 and n01[0]["agrupadas"] == 3 and n01[0]["titulo"] == "Maria mandou 3 mensagens",
       "agrupar: três mensagens seguidas viram um aviso", str([(l["agrupadas"], l["titulo"]) for l in n01]))
a.marcar_lidas("op1", "emp")
N.notificar("N01", "emp", devedor=DEV, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N01:c1")
checar(len(de(a, "op1", "N01")) == 2 and de(a, "op1", "N01")[-1]["agrupadas"] == 1, "agrupar: depois de lido, a próxima mensagem abre outro")
a.salvar_preferencias("op1", "emp", {"desligadas": ["conversas"]}); N._CACHE.clear()
N.notificar("N01", "emp", devedor=DEV, contexto={"nome": "Maria"}, chave="N01:c2")
N.notificar("N03", "emp", devedor=DEV, contexto={"nome": "Maria"}, chave="N03:c2")
checar(not de(a, "op1") or (not [l for l in de(a, "op1") if l["chave"] == "N01:c2"] and [l for l in de(a, "op1") if l["chave"] == "N03:c2"]),
       "categoria desligada não chega, mas o urgente chega sempre")
checar(all("cpf" not in l and "123.456" not in str(l) for l in a.linhas), "nenhuma linha guarda o CPF do devedor")
v0 = mudancas.versoes("emp", usuario_id="adm1")["notificacoes"]
N.notificar("N31", "emp", admins=True, chave="N31:c9:2026-11-06")
checar(mudancas.versoes("emp", usuario_id="adm1")["notificacoes"] != v0, "a versão da pessoa em /mudancas sobe: o sino atualiza")
checar(mudancas.versoes("emp")["agenda"] == mudancas.versoes("emp")["agenda"] and "notificacoes" not in mudancas.versoes("emp"),
       "sem a pessoa, /mudancas segue como antes")

print("— resolução —")
a = novo()
N.notificar("N06", "emp", devedor=DEV, admins=True, contexto={"nome": "Maria", "quando": "hoje às 15:00"}, chave="N06:i1",
            entidade=("agenda", "i1"))
N.compromisso_resolvido("emp", {"id": "i1", "predicao_id": "p1", "observacao": "Atendimento com pessoa pedido pelo devedor (x)"})
checar(all(l["resolvida_em"] for l in de(a, tipo="N06")), "compromisso resolvido: os avisos dele saem das pendências")
N.notificar("N02", "emp", devedor=DEV, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N02:c1:i2", entidade=("devedor", "p1"))
N.compromisso_resolvido("emp", {"id": "i2", "predicao_id": "p1", "observacao": "Transferido pelo assistente (pedido_do_devedor): x"})
checar(all(l["resolvida_em"] for l in de(a, tipo="N02")), "transferência cumprida na agenda resolve o aviso da transferência")
N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "Maria"}, chave="N22:c7", entidade=("devedor", "p1"))
N.compromisso_resolvido("emp", {"id": "i3", "predicao_id": "p1", "observacao": "Transferido pelo assistente (x)"})
checar(not de(a, tipo="N22")[0]["resolvida_em"], "mas não resolve o que é de outro assunto (contestação)")
N.notificar("N22", "outra", usuarios=["op9"], contexto={"nome": "X"}, chave="N22:z", entidade=("devedor", "p1"))
N.resolver("emp", "devedor", "p1")
checar(not [l for l in a.linhas if l["empresa_id"] == "outra" and l["resolvida_em"]], "resolver nunca mexe em outra empresa")

print("— disjuntor —")
class Quebrado(N.ArmazemMemoria):
    def __init__(s, erro): super().__init__(usuarios=PESSOAS); s.erro = erro; s.chamadas = 0
    def existe(s, *a): s.chamadas += 1; raise RuntimeError(s.erro)
q = Quebrado("timeout"); N.usar_armazem(q); N._DISJUNTOR.update(seguidas=0, ate=0.0)
for i in range(5):
    N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "M"}, chave=f"k{i}")
checar(q.chamadas == 3 and N.disjuntor_aberto(), "3 falhas seguidas abrem o disjuntor; as próximas nem tentam", str(q.chamadas))
q2 = Quebrado('relation "public.notificacoes" does not exist'); N.usar_armazem(q2); N._DISJUNTOR.update(seguidas=0, ate=0.0)
N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "M"}, chave="k")
checar(N.disjuntor_aberto() and N._DISJUNTOR["ate"] - __import__("time").monotonic() > 500, "sem a tabela: para por 10 minutos de uma vez")
checar(N.relogio(SEXTA_14H) == {}, "com o disjuntor aberto, o relógio nem lê a agenda")
os.environ["MIZAN_NOTIFICACOES"] = "0"; a = novo()
N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "M"}, chave="k")
checar(not a.linhas, "MIZAN_NOTIFICACOES=0 desliga tudo")
os.environ["MIZAN_NOTIFICACOES"] = "1"


print("— gatilhos do agente (fluxo real das ferramentas, IA simulada) —")
def rodar(chamadas, dev=DEV, situacao="em_contato", triagem=None, dados=None, agenda=None):
    a = novo()
    repo, fonte = RepoMemoria(), FonteMemoria([dev])
    fonte.agenda = [dict(x) for x in (agenda or [])]
    caso = repo.obter_ou_criar_caso("emp", dev["id"])
    repo.salvar_caso(caso["id"], {"situacao": situacao, "dados": dados or {"identidade_ok": True, "divida": 3000.0}})
    repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    res = []
    def no(ctx):
        if triagem:
            ctx.saida["triagem"] = triagem
        for nome, args in chamadas:
            res.append(fer.executar(ctx, fonte, nome, args))
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", f"m{uuid.uuid4().hex[:6]}")
    orq.processar_proximo(repo, {"mensagem_devedor": orq.Grafo("g", "a").no("a", no, agente="negociador")},
                          ClienteFalso(), SEXTA_14H)
    return res, a, fonte, repo.obter_caso(caso["id"])

r, a, fonte, caso = rodar([("transferir_para_humano", {"motivo": "dificuldade_grave", "resumo": "Disse que não aguenta mais."})],
                          triagem={"intencao": "outro", "sinais_de_risco": ["sofrimento_grave"]})
n03 = de(a, tipo="N03")
checar(r[0]["ok"] and sorted(l["usuario_id"] for l in n03) == ["adm1", "adm2", "op1"] and all(l["prioridade"] == "urgente" for l in n03),
       "risco grave: urgente para o responsável e para os administradores", str([(l["usuario_id"], l["prioridade"]) for l in n03]))
checar(not de(a, tipo="N02") and "não aguenta" not in str(a.linhas), "sem aviso duplicado de transferência e sem o texto da conversa")
r, a, *_ = rodar([("transferir_para_humano", {"motivo": "pedido_do_devedor", "resumo": "Quer falar com alguém."})])
n02 = de(a, tipo="N02")
checar([l["usuario_id"] for l in n02] == ["op1"] and "pediu para falar" in n02[0]["texto"] and n02[0]["prioridade"] == "alta",
       "transferência comum: alta, para o responsável, com o motivo em palavras simples", n02[0]["texto"] if n02 else "")
r, a, fonte, caso = rodar([("marcar_atendimento_humano", {"data": "2026-11-07", "hora": "14:30", "motivo": "reuniao",
                                                         "resumo": "Quer revisar as parcelas."})])
n06 = {l["usuario_id"]: l for l in de(a, tipo="N06")}
item = r[0]["compromisso_id"]
checar(set(n06) == {"adm1", "adm2", "op1"} and n06["adm1"]["prioridade"] == "alta" and n06["op1"]["prioridade"] == "normal"
       and n06["adm1"]["link"] == "/agente?aba=agenda" and "amanhã às 14:30" in n06["adm1"]["texto"],
       "reunião pedida: o administrador aprova (alta); o responsável fica sabendo (normal)", str({k: v["prioridade"] for k, v in n06.items()}))
# o administrador aprova e escolhe o Beto
fonte.agenda[-1]["operador_id"] = "op2"
N.reuniao_atribuida("emp", {**fonte.agenda[-1]}, "op2", agora=SEXTA_14H)
checar([l["usuario_id"] for l in de(a, tipo="N07")] == ["op2"] and all(l["resolvida_em"] for l in de(a, tipo="N06")),
       "aprovada: o Beto recebe a reunião e a pendência de aprovação some de todos")
checar("Amanhã às 14:30" in de(a, tipo="N07")[0]["texto"], "com o dia e a hora", de(a, tipo="N07")[0]["texto"])
# a pessoa muda o horário: volta para aprovação, e o Beto fica sabendo
repo = RepoMemoria()
ctx = SimpleNamespace(caso={"id": caso["id"], "empresa_id": "emp", "predicao_id": "p1", "situacao": "com_pessoa", "dados": {}},
                      saida={}, agora=SEXTA_14H)
N.apos_ferramenta(ctx, DEV, "remarcar_compromisso", {"data": "2026-11-09", "hora": "10:00", "motivo": "x"},
                  {"ok": True, "compromisso_id": item, "o_que": "atendimento com uma pessoa da equipe", "data": "2026-11-09",
                   "hora": "10:00"})
n08 = {l["usuario_id"]: l for l in de(a, tipo="N08")}
checar(set(n08) == {"op2", "adm1", "adm2"} and n08["op2"]["link"] == "/agenda" and n08["adm1"]["link"] == "/agente?aba=agenda"
       and all(l["resolvida_em"] for l in de(a, tipo="N07")), "remarcada: quem ia atender e os administradores; a atribuição antiga sai",
       str(sorted(n08)))
N.apos_ferramenta(ctx, DEV, "desmarcar_compromisso", {"motivo": "x"},
                  {"ok": True, "compromisso_id": item, "o_que": "atendimento com uma pessoa da equipe",
                   "era": {"data": "2026-11-09", "hora": "10:00"}})
n09 = {l["usuario_id"]: l for l in de(a, tipo="N09")}
checar(set(n09) == {"op2", "adm1", "adm2"} and n09["op2"]["prioridade"] == "alta" and n09["adm1"]["prioridade"] == "normal"
       and all(l["resolvida_em"] for l in de(a, tipo="N08")), "desmarcada: avisa quem ia atender (alta) e os administradores (normal)")
r, a, *_ = rodar([("registrar_pagamento_informado", {"data": "2026-11-05", "valor": 350.0})])
n18 = de(a, tipo="N18")
checar([l["usuario_id"] for l in n18] == ["op1"] and "350" not in str(n18), "pagamento informado: conferir, sem o valor no aviso")
r, a, *_ = rodar([("abrir_contestacao", {"motivo": "Não reconhece."}), ("suspender_cobranca", {"motivo": "pediu_para_parar"})])
checar(sorted(l["usuario_id"] for l in de(a, tipo="N22")) == ["adm1", "adm2", "op1"], "contestação: responsável e administradores")
checar([l["usuario_id"] for l in de(a, tipo="N23")] == ["op1"] and "não ser mais contatado" in de(a, tipo="N23")[0]["titulo"],
       "pedido para parar: o responsável", de(a, tipo="N23")[0]["titulo"] if de(a, tipo="N23") else "")
r, a, *_ = rodar([("registrar_pedido_titular", {"tipo": "acesso"})])
n24 = {l["usuario_id"]: l for l in de(a, tipo="N24")}
checar(set(n24) == {"adm1", "adm2", "op1"} and n24["adm1"]["prioridade"] == "alta" and n24["op1"]["prioridade"] == "normal"
       and "15 dias" in n24["adm1"]["texto"], "pedido sobre os dados: administradores (alta), com o prazo de 15 dias")
sem_dono = {**DEV, "responsavel_id": None}
r, a, *_ = rodar([("registrar_pagamento_informado", {"data": "2026-11-05"})], dev=sem_dono)
checar(sorted(l["usuario_id"] for l in de(a, tipo="N18")) == ["adm1", "adm2"], "devedor sem responsável: vai para os administradores")
ctx_g = SimpleNamespace(caso={"id": "c5", "empresa_id": "emp", "predicao_id": "p1", "situacao": "com_pessoa",
                              "dados": {"assumido_por": "adm2"}}, saida={}, agora=SEXTA_14H)
a = novo()
N.mensagem_em_caso_da_equipe(ctx_g, DEV)
checar([l["usuario_id"] for l in a.linhas] == ["adm2"], "mensagem num caso assumido: vai para quem assumiu")
ctx_g.caso["dados"] = {"assumido_por": "op3"}
N.mensagem_em_caso_da_equipe(ctx_g, DEV)
checar([l["usuario_id"] for l in a.linhas] == ["adm2", "op1"], "quem assumiu saiu da empresa: vai para o responsável")

print("— gatilhos do agente pela rodada completa (grafo de mensagem) —")
from agente import api as agente_api                                # noqa: E402
a = novo()
repo, fonte = RepoMemoria(), FonteMemoria([DEV])
caso = repo.obter_ou_criar_caso("emp", "p1")
repo.salvar_caso(caso["id"], {"situacao": "com_pessoa", "dados": {}})
repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
for i in range(2):
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", f"msg{i}", dados={"texto": "Alguém pode me ajudar?"})
    orq.processar_proximo(repo, agente_api.grafos(fonte), ClienteFalso(), SEXTA_14H + timedelta(minutes=i))
n01 = de(a, tipo="N01")
checar(len(n01) == 1 and n01[0]["usuario_id"] == "op1" and n01[0]["agrupadas"] == 2,
       "duas mensagens num caso com a equipe: um aviso só, para o responsável", str([(l["usuario_id"], l["agrupadas"]) for l in n01]))

print("— ganchos de equipe e sistema —")
a = novo()
N.pagamento_confirmado("emp", [{"id": "pr1", "predicao_id": "p1", "nome": "Maria", "operador_id": "op1", "observacao": "x"},
                               {"id": "pr2", "predicao_id": "p1", "nome": "Maria", "operador_id": "op1", "observacao": "x"},
                               {"id": "pr3", "predicao_id": "p2", "nome": "João", "operador_id": "agente-mizan", "observacao": "x"}],
                       ator_id="adm1")
n19 = {l["usuario_id"]: l for l in de(a, tipo="N19")}
checar(set(n19) == {"op1", "adm2"} and n19["op1"]["agrupadas"] == 1,
       "pagamento confirmado: o dono da promessa (uma vez por devedor); sem dono pessoa, os administradores menos quem confirmou",
       str({k: v["agrupadas"] for k, v in n19.items()}))
N.devedores_recebidos("emp", "op2", 25, ator_id="adm1")
N.devedores_recebidos("emp", "op2", 5, ator_id="adm1")
n26 = de(a, "op2", "N26")
checar(len(n26) == 1 and n26[0]["agrupadas"] == 30 and n26[0]["titulo"] == "Devedores novos na sua fila: 30",
       "fila distribuída duas vezes no dia: um aviso que soma", n26[0]["titulo"] if n26 else "")
N.devedores_recebidos("emp", "adm1", 3, ator_id="adm1")
checar(not de(a, "adm1", "N26"), "quem distribuiu para si mesmo não é avisado")
N.duvida_respondida("emp", "op1", "d1", "2026-11-06T10:00")
N.duvida_respondida("emp", "op1", "d1", "2026-11-06T10:00")
checar(len(de(a, "op1", "N29")) == 1, "dúvida respondida: um aviso por resposta")
N.resolver("emp", "duvida", "d1", ("N29",))
checar(de(a, "op1", "N29")[0]["resolvida_em"], "quem perguntou abriu a resposta: o aviso sai")
t0 = SEXTA_14H
for i in range(0, 20, 2):
    N.agente_parado("emp", "ia_aguardando", t0 + timedelta(minutes=i))
checar(len(de(a, "adm1", "N30")) == 1 and "IA não responde" in de(a, "adm1", "N30")[0]["titulo"],
       "IA ocupada por mais de 15 minutos seguidos: um aviso urgente aos administradores")
a = novo()
N.agente_parado("emp", "ia_aguardando", t0)
N.agente_parado("emp", "ia_aguardando", t0 + timedelta(minutes=10))     # a IA tinha voltado no meio
N.agente_parado("emp", "ia_aguardando", t0 + timedelta(minutes=17))
checar(not de(a, tipo="N30"), "IA ocupada só de vez em quando: nada")
N.agente_parado("emp", "teto_ia", t0); N.agente_parado("emp", "teto_ia", t0 + timedelta(minutes=30))
N.agente_parado("sistema", "teto_ia", t0); N.agente_parado("emp", "no_falhou", t0)
checar(len(de(a, "adm1", "N30")) == 1 and de(a, "adm1", "N30")[0]["prioridade"] == "urgente",
       "teto do dia: um aviso por dia; categoria comum e 'sistema' não avisam")
N.agente_parado("emp", "evento_falhou", t0); N.agente_parado("emp", "evento_falhou", t0 + timedelta(minutes=3))
f = [l for l in de(a, "adm1", "N30") if "falh" in l["titulo"].lower()]
checar(len(f) == 1 and f[0]["agrupadas"] == 2 and f[0]["prioridade"] == "alta", "eventos que falharam: alta, somados na hora")
N.seguranca("emp", "bloqueio", "op1", "Ana Lima", agora=t0); N.seguranca("emp", "bloqueio", "op1", "Ana Lima", agora=t0)
checar(sorted(l["usuario_id"] for l in de(a, tipo="N33")) == ["adm1", "adm2"], "acesso bloqueado: os administradores, uma vez por hora")
N.seguranca("emp", "senha_2fa", "adm1", "Carla Gestora", agora=t0)
checar(not [l for l in de(a, "adm1", "N33") if "trocou a senha" in l["titulo"]], "a própria pessoa não recebe o aviso da própria senha")
N.seguranca("emp", "2fa_pessoa", "op2", agora=t0)
checar(de(a, "op2", "N33") and de(a, "op2", "N33")[0]["link"] == "/seguranca", "2FA redefinido: a pessoa recebe e vai configurar")
N.sincronizacao_falhou("emp", "cx1"); N.sincronizacao_falhou("emp", "cx1")
checar(len(de(a, "adm1", "N31")) == 1, "conexão que falha: um aviso por dia")
N.recomendacao_do_cientista("emp", "rec1", exceto="adm1"); N.experimento_parado("emp", "exp1")
checar([l["usuario_id"] for l in de(a, tipo="N32") if "recomendação" in l["titulo"]] == ["adm2"]
       and len([l for l in de(a, tipo="N32") if l["prioridade"] == "alta"]) == 2, "Cientista: os outros administradores; parada por dano é alta")


print("— relógio: lembretes de horário —")
def compromisso(id_, hora, dono, obs="Atendimento com pessoa pedido pelo devedor (reuniao): resumo", data="2026-11-06", **k):
    return {"id": id_, "empresa_id": "emp", "predicao_id": "p1", "nome": "Maria", "operador_id": dono, "tipo": "retorno",
            "data": data, "hora": hora, "observacao": obs, "situacao": "pendente", **k}
br = lambda h, m=0, d=6: datetime(2026, 11, d, h, m, tzinfo=N.BRASILIA).astimezone(UTC)   # horário de Brasília
a = novo([compromisso("r1", "14:30", "op2")])
N.lembretes(br(13, 50)); checar(not a.linhas, "40 minutos antes: nada ainda")
N.lembretes(br(14, 0)); N.lembretes(br(14, 1))
l30 = de(a, "op2", "N10")
checar(len(l30) == 1 and l30[0]["prioridade"] == "alta" and l30[0]["titulo"] == "Reunião com Maria em 30 minutos",
       "30 minutos antes: alta, uma vez só", str([l["titulo"] for l in l30]))
N.lembretes(br(14, 25)); N.lembretes(br(14, 26))
l5 = [l for l in de(a, "op2", "N10") if "5 minutos" in l["titulo"]]
checar(len(l5) == 1 and l5[0]["prioridade"] == "urgente", "5 minutos antes: urgente, uma vez só")
N.lembretes(br(15, 1))
checar(len(de(a, "op2", "N12")) == 1, "30 minutos depois, sem registro: avisa o operador")
a = novo([compromisso("r1", "14:30", "op2")])
N.lembretes(br(14, 27))
checar([l["titulo"] for l in de(a, "op2", "N10")] == ["Reunião com Maria em 5 minutos"],
       "servidor que volta tarde: sai só o lembrete de 5 minutos")
a = novo([compromisso("r2", "14:30", "a-definir")])
N.lembretes(br(12, 29)); checar(not a.linhas, "reunião sem atendente a mais de 2 horas: nada ainda")
N.lembretes(br(12, 31)); N.lembretes(br(13, 0))
n11 = de(a, tipo="N11")
checar(sorted(l["usuario_id"] for l in n11) == ["adm1", "adm2"] and all(l["prioridade"] == "urgente" for l in n11),
       "reunião sem atendente a 2 horas: urgente para os administradores, uma vez")
a = novo([compromisso("r3", "10:00", "op1", obs="Ligar de volta para combinar"),
          compromisso("r4", "10:00", "op1", obs="Retorno combinado pelo assistente: x"),
          compromisso("r5", "10:00", "agente-mizan", obs="Ligar de volta")])
N.lembretes(br(9, 46))
checar([l["chave"].split(":")[1] for l in de(a, tipo="N14")] == ["r3"],
       "retorno com hora: 15 min antes, só o da pessoa (o do assistente e o sem dono não)")
a = novo([compromisso("r6", "00:20", "op2", data="2026-11-07")])
N.lembretes(br(23, 55))
checar(len(de(a, "op2", "N10")) == 1, "reunião depois da meia-noite: o lembrete sai no dia anterior")

class Contando(N.ArmazemMemoria):
    def __init__(s, *a, **k): super().__init__(*a, **k); s.consultas = 0
    def existe(s, *a): s.consultas += 1; return super().existe(*a)
c0 = Contando(usuarios=PESSOAS, agenda=[compromisso("r9", "14:30", "op2")]); N.usar_armazem(c0)
for minuto in range(0, 10):
    N.lembretes(br(14, minuto))
checar(len(de(c0, "op2", "N10")) == 1 and c0.consultas == 1,
       "lembrete já gravado: o relógio não pergunta ao banco de novo a cada minuto", str(c0.consultas))

class CaiUmaVez(N.ArmazemMemoria):
    def __init__(s, *a, **k): super().__init__(*a, **k); s.vezes = 0
    def agenda_ate(s, dia):
        s.vezes += 1
        if s.vezes == 1:
            raise TimeoutError("banco fora às 8h")
        return super().agenda_ate(dia)
cai = CaiUmaVez(usuarios=PESSOAS, agenda=[compromisso("h1", None, "op1", obs="Ligar")]); N.usar_armazem(cai)
N._RODOU.clear(); N._ULTIMO.clear(); N._DISJUNTOR.update(seguidas=0, ate=0.0)
N.relogio(br(8, 0)); N.relogio(br(8, 1))
checar(len(de(cai, "op1", "N15")) == 1 and cai.vezes == 2, "banco fora às 8h: a agenda do dia sai no minuto seguinte")
N.relogio(br(8, 2))
checar(cai.vezes == 2, "depois de dar certo, não roda de novo no mesmo dia")
N._DISJUNTOR.update(seguidas=0, ate=0.0)

print("— o que já passou sai da lista —")
a = novo([compromisso("p1r", "14:30", "op2"), compromisso("p2r", "10:00", "op1", obs="Ligar de volta")])
N.lembretes(br(9, 50)); N.lembretes(br(14, 25))          # o tempo só anda para a frente
checar(len(de(a, "op2", "N10")) == 1 and len(de(a, "op1", "N14")) == 1, "(lembretes criados)")
N.lembretes(br(14, 50))
checar(not de(a, "op2", "N10")[0]["resolvida_em"], "20 minutos depois do horário o lembrete ainda vale")
N.lembretes(br(15, 1))
checar(de(a, "op2", "N10")[0]["resolvida_em"] and de(a, "op1", "N14")[0]["resolvida_em"],
       "meia hora depois do horário, o lembrete da reunião e o do retorno saem da lista")
checar(de(a, "op2", "N12") and not de(a, "op2", "N12")[0]["resolvida_em"],
       "mas o 'reunião não registrada' fica, porque ainda pede ação")
a = novo()
ontem_10h = br(10, 0, d=5).isoformat()
N.notificar("N15", "emp", usuarios=["op1"], ou_admins=False, contexto={"resumo": "Hoje: 2 compromissos."},
            chave="N15:ontem:op1", agora=br(10, 0, d=5))
N.notificar("N10", "emp", usuarios=["op1"], contexto={"nome": "Maria", "hora": "00:20", "minutos": 30},
            chave="N10:meianoite", entidade=("agenda", "mn"), agora=br(23, 55, d=5))
N.notificar("N15", "emp", usuarios=["op2"], ou_admins=False, contexto={"resumo": "Hoje: 1 compromisso."},
            chave="N15:hoje:op2", agora=br(8, 0))
N.virada_do_dia(br(0, 5))
checar(de(a, "op1", "N15")[0]["resolvida_em"] and not de(a, "op2", "N15")[0]["resolvida_em"],
       "na virada do dia, a agenda de ontem sai da lista e a de hoje fica")
checar(not de(a, "op1", "N10")[0]["resolvida_em"], "lembrete criado ontem para uma reunião depois da meia-noite não sai na virada")
N._RODOU.clear()
N.relogio(br(0, 6)); N.relogio(br(0, 7))
checar(("virada", "2026-11-06") in N._RODOU, "a virada roda no primeiro minuto do dia, uma vez")

print("— relógio: 8h, 9h, mensagens sem resposta e escalonamento —")
ag = [compromisso("h1", None, "op1", obs="Ligar"), compromisso("h2", "15:00", "op1", obs="Ligar"),
      compromisso("h3", None, "op1", obs="Ligar", data="2026-11-02"),
      compromisso("h4", "16:00", "a-definir"),
      compromisso("h5", None, "agente-mizan", obs="Retorno combinado pelo assistente: x"),
      {"id": "t1", "empresa_id": "emp", "predicao_id": None, "nome": "Fechar o mês", "operador_id": "adm1", "tipo": "retorno",
       "data": "2026-11-06", "hora": None, "observacao": "", "situacao": "pendente"},
      compromisso("x1", None, "op9", obs="Ligar", empresa_id="outra")]
a = novo(ag)
N.manha(br(8, 5))
op1 = de(a, "op1", "N15")
checar(len(op1) == 1 and op1[0]["texto"] == "Hoje: 2 compromissos (1 com hora marcada). Atrasados: 1.",
       "agenda do dia do operador", op1[0]["texto"] if op1 else "")
equipe = de(a, "adm1", "N15")
checar(len(equipe) == 1 and equipe[0]["titulo"] == "Resumo da equipe hoje" and "1 reunião espera atendente" in equipe[0]["texto"],
       "resumo da equipe para o administrador", equipe[0]["texto"] if equipe else "")
checar(not de(a, "op2", "N15"), "quem não tem nada hoje não recebe")
checar([l["titulo"] for l in de(a, "adm1", "N27")] == ["Tarefa para hoje: Fechar o mês"], "tarefa administrativa de hoje")
checar(len(de(a, "op9", "N15")) == 1 and "Hoje: 1 compromisso." == de(a, "op9", "N15")[0]["texto"], "cada empresa com a sua agenda")
N.manha(br(9, 0))
checar(len(de(a, "op1", "N15")) == 1, "rodar de novo no mesmo dia não repete")
seg = lambda h, m=0: datetime(2026, 11, 9, h, m, tzinfo=N.BRASILIA).astimezone(UTC)     # segunda-feira, 09/11
criado = lambda dias: (seg(9) - timedelta(days=dias)).isoformat()
ag = [compromisso("v1", None, "op1", obs="Acordo pelo assistente: 1x", data="2026-11-08", tipo="promessa"),
      compromisso("v2", None, "op1", obs="x", data="2026-11-08", tipo="promessa"),
      compromisso("a1", None, "op2", obs="Ligar", data="2026-11-05"),
      compromisso("a2", None, "op2", obs="Ligar", data="2026-11-06"),
      compromisso("l1", None, "agente-mizan", obs="Pedido sobre os dados pessoais (acesso): registrado pelo assistente. "
                  "A pessoa responsável pelos dados analisa e responde em até 15 dias.", data="2026-10-28", created_at=criado(12)),
      compromisso("l2", None, "agente-mizan", obs="Pedido sobre os dados pessoais (acesso): ... em até 15 dias.",
                  data="2026-10-25", created_at=criado(15))]
a = novo(ag)
N.nove_horas(seg(9, 10))
n16 = de(a, "op1", "N16")
checar(len(n16) == 1 and n16[0]["titulo"] == "2 promessas venceram ontem sem pagamento confirmado" and n16[0]["link"] == "/agenda",
       "promessas vencidas ontem: um aviso com a contagem", n16[0]["titulo"] if n16 else "")
n17 = de(a, "adm1", "N17")
checar(len(n17) == 1 and n17[0]["titulo"].endswith(": 1") and "Beto: 1" in (n17[0]["texto"] or ""),
       "atrasados há mais de 1 dia útil (segunda: só o que é de antes de sexta)", n17[0]["texto"] if n17 else "")
n25 = {l["chave"]: l for l in de(a, "adm1", "N25")}
checar(n25.get("N25:l1:3d", {}).get("titulo", "").endswith("vence em 3 dias") and n25.get("N25:l2:dia", {}).get("prioridade") == "urgente"
       and n25["N25:l2:dia"]["titulo"].endswith("vence hoje"), "prazo LGPD: 3 dias antes (alta) e no dia (urgente)", str(list(n25)))
a = novo([{"id": "m1", "empresa_id": "emp", "predicao_id": "p1", "nome": "Maria", "operador_id": "op1", "tipo": "retorno",
           "data": "2026-11-06", "hora": None, "situacao": "pendente",
           "observacao": "Nova mensagem do devedor (caso com_pessoa): responder pela equipe.",
           "created_at": (SEXTA_14H - timedelta(hours=3)).isoformat()},
          {"id": "m2", "empresa_id": "emp", "predicao_id": "p2", "nome": "João", "operador_id": "op1", "tipo": "retorno",
           "data": "2026-11-06", "hora": None, "situacao": "pendente",
           "observacao": "Nova mensagem do devedor (caso com_pessoa): responder pela equipe.",
           "created_at": (SEXTA_14H - timedelta(minutes=50)).isoformat()}])
N.sem_resposta(SEXTA_14H)
n28 = de(a, "op1", "N28")
checar(len(n28) == 1 and n28[0]["titulo"] == "Maria espera resposta há mais de 2 horas" and "11:00" in n28[0]["texto"],
       "mensagem sem resposta há mais de 2 horas (e não a de 50 minutos)", n28[0]["texto"] if n28 else "")
a = novo()
N.notificar("N10", "emp", usuarios=["op2"], contexto={"nome": "Maria", "predicao_id": "p1", "hora": "14:30", "minutos": 5},
            chave="N10:r1:5", entidade=("agenda", "r1"), prioridade="urgente", agora=SEXTA_14H)
N.notificar("N03", "emp", devedor=DEV, admins=True, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N03:x",
            entidade=("devedor", "p1"), agora=SEXTA_14H)
N.escalar(SEXTA_14H + timedelta(minutes=10)); checar(not de(a, tipo="ESC"), "urgente lido há menos de 15 minutos: não escala")
N.escalar(SEXTA_14H + timedelta(minutes=16)); N.escalar(SEXTA_14H + timedelta(minutes=17))
esc = de(a, tipo="ESC")
checar(sorted(l["usuario_id"] for l in esc) == ["adm1", "adm2"] and esc[0]["titulo"].startswith("Sem resposta há 15 min: Reunião com Maria")
       and esc[0]["link"] == "/pasta/p1?aba=conversa", "reunião em 5 min sem leitura: escala para os administradores, uma vez")
checar(len([l for l in esc if "Maria mostrou" in l["titulo"]]) == 0, "o risco grave não escala: os administradores já receberam")

print("— relógio: limpeza, e-mail e o passo do agendador —")
a = novo()
dias = lambda n: (SEXTA_14H - timedelta(days=n)).isoformat()
def linha(id_, criado, lida=None, resolvida=None):
    return {"id": id_, "empresa_id": "emp", "usuario_id": "op1", "tipo": "N01", "prioridade": "alta", "chave": id_,
            "criado_em": criado, "atualizado_em": criado, "lida_em": lida, "resolvida_em": resolvida}
a.linhas += [linha("resolvida-ha-10", dias(12), resolvida=dias(10)), linha("resolvida-ha-3", dias(4), resolvida=dias(3)),
             linha("lida-ha-40", dias(40), lida=dias(40)), linha("lida-ha-10", dias(10), lida=dias(10)),
             linha("aberta-ha-100", dias(100)), linha("aberta-ha-60", dias(60))]
N.limpar(SEXTA_14H)
checar(sorted(l["id"] for l in a.linhas) == ["aberta-ha-60", "lida-ha-10", "resolvida-ha-3"],
       "limpeza: resolvidas saem em 7 dias, lidas em 30, qualquer uma em 90", str(sorted(l["id"] for l in a.linhas)))
a = novo()
a.salvar_preferencias("op1", "emp", {"email_resumo": True})
N.notificar("N18", "emp", devedor=DEV, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N18:x")
N.notificar("N06", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria", "quando": "hoje"}, chave="N06:x")
enviados = []
N.resumos_por_email(br(8, 2), enviar=lambda para, assunto, corpo: enviados.append((para, assunto, corpo)) or True)
N.resumos_por_email(br(8, 3), enviar=lambda para, assunto, corpo: enviados.append((para, assunto, corpo)) or True)
checar(len(enviados) == 1 and enviados[0][0] == "ana@x" and "2 avisos abertos" in enviados[0][2]
       and "Maria" not in enviados[0][2] and "Reuniões: 1" in enviados[0][2], "resumo por e-mail: um por dia, só contagens, sem o devedor")
a = novo([compromisso("r1", "14:30", "op2")])
N._RODOU.clear(); N._ULTIMO.clear()
feito = N.relogio(br(14, 0))
checar(feito.get("lembretes") == 1 and "manha" not in feito and "nove" in feito, "o passo do agendador às 14h: lembretes e a rodada das 9h", str(feito))
checar("nove" not in N.relogio(br(14, 1)), "a rodada das 9h roda uma vez por dia")


print("— rotas /notificacoes —")
import main                                                         # noqa: E402
from auth import criar_token                                        # noqa: E402
from fastapi.testclient import TestClient                           # noqa: E402
main._usuario_autenticado = lambda cred: main.validar_token(cred.credentials)
main._usuario_recente = lambda cred: main.validar_token(cred.credentials)
c = TestClient(main.app, raise_server_exceptions=False)
def jwt(sub, role="operador", emp="emp"):
    return {"Authorization": "Bearer " + criar_token({"sub": sub, "email": f"{sub}@x", "nome": sub, "role": role, "empresa_id": emp})}
ANA, BETO, CARLA, CMD, OUTRA = jwt("op1"), jwt("op2"), jwt("adm1", "admin"), jwt("cmd", "comando", ""), jwt("op1", emp="outra")
a = novo()
N.notificar("N03", "emp", devedor=DEV, admins=True, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N03:z")
N.notificar("N22", "emp", devedor=DEV, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="N22:z")
N.notificar("N26", "emp", usuarios=["op2"], ou_admins=False, quantidade=4, chave="N26:z")
r = c.get("/notificacoes", headers=ANA)
j = r.json()
checar(r.status_code == 200 and j["ativo"] and j["nao_lidas"] == 2 and j["urgentes"] == 1
       and {i["tipo"] for i in j["itens"]} == {"N03", "N22"}, "a pessoa vê só as dela, com as contagens", r.text[:160])
checar(all(set(i) >= {"titulo", "link", "acao", "externo", "toca", "prioridade"} for i in j["itens"])
       and next(i for i in j["itens"] if i["tipo"] == "N03")["toca"], "cada item traz o botão, o título de fora e se toca agora")
checar(c.get("/notificacoes", headers=OUTRA).json()["nao_lidas"] == 0, "o mesmo id em outra empresa não vê nada")
checar(c.get("/notificacoes", headers=CMD).json()["ativo"] is False, "o COMANDO não tem sino")
checar(c.get("/notificacoes", params={"filtro": "x"}, headers=ANA).status_code == 422
       and c.get("/notificacoes", params={"antes": "ontem"}, headers=ANA).status_code == 422, "filtro e data inválidos: 422")
da_beto = de(a, "op2")[0]["id"]
r = c.post(f"/notificacoes/{da_beto}/lida", headers=ANA)
checar(r.status_code == 200 and not de(a, "op2")[0]["lida_em"], "marcar a notificação de outra pessoa não muda nada")
checar(c.post("/notificacoes/nao-e-id/lida", headers=ANA).status_code == 404, "id inválido: 404")
ag0 = mudancas.versoes("emp")["agenda"]
uma = next(i["id"] for i in j["itens"] if i["tipo"] == "N22")
checar(c.post(f"/notificacoes/{uma}/lida", headers=ANA).status_code == 200
       and c.get("/notificacoes", headers=ANA).json()["nao_lidas"] == 1, "marcar uma como lida")
checar(mudancas.versoes("emp")["agenda"] == ag0, "marcar como lida não recarrega a agenda de ninguém")
v = c.get("/mudancas", headers=ANA).json()
checar("notificacoes" in v, "/mudancas traz a versão das notificações da pessoa")
r = c.post("/notificacoes/lidas", json={}, headers=ANA)
checar(r.status_code == 200 and r.json()["lidas"] == 1 and c.get("/notificacoes", headers=ANA).json()["nao_lidas"] == 0,
       "marcar todas como lidas")
checar(c.get("/notificacoes", params={"filtro": "todas"}, headers=ANA).json()["itens"][0]["lida"] is True,
       "em 'todas', as lidas continuam aparecendo")
checar(c.put("/notificacoes/preferencias", json={"silencio_inicio": 25}, headers=ANA).status_code == 422
       and c.put("/notificacoes/preferencias", json={"desligadas": ["xyz"]}, headers=ANA).status_code == 422,
       "preferências inválidas: 422")
r = c.put("/notificacoes/preferencias", json={"navegador": True, "silencio_inicio": 21, "silencio_fim": 7,
                                              "desligadas": ["equipe"]}, headers=BETO)
checar(r.status_code == 200 and r.json()["navegador"] and c.get("/notificacoes/preferencias", headers=BETO).json()["silencio_inicio"] == 21,
       "salvar e ler as preferências")
checar(c.get("/notificacoes/preferencias", headers=ANA).json()["silencio_inicio"] == 20, "cada pessoa tem as suas")
checar(c.put("/notificacoes/preferencias", json={}, headers=CMD).status_code == 403, "o COMANDO não salva preferências de sino")
print("— lixeira e resolvidas fora da lista —")
a = novo()
N.notificar("N22", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx1", entidade=("devedor", "p1"))
N.notificar("N18", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx2")
N.notificar("N19", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx3")
N.notificar("N26", "emp", usuarios=["op2"], ou_admins=False, quantidade=3, chave="lx4")
N.resolver("emp", "devedor", "p1", ("N22",))
r = c.get("/notificacoes", params={"filtro": "todas"}, headers=ANA).json()
checar(sorted(i["tipo"] for i in r["itens"]) == ["N18", "N19"], "o que já se resolveu não aparece nem em 'Todas'",
       str([i["tipo"] for i in r["itens"]]))
id18 = next(i["id"] for i in r["itens"] if i["tipo"] == "N18")
id_beto = de(a, "op2")[0]["id"]
r = c.delete(f"/notificacoes/{id18}", headers=ANA)
checar(r.status_code == 200 and r.json()["excluidas"] == 1 and not de(a, "op1", "N18"), "a lixeira apaga a notificação")
r = c.delete(f"/notificacoes/{id_beto}", headers=ANA)
checar(r.status_code == 200 and r.json()["excluidas"] == 0 and de(a, "op2"), "a de outra pessoa não é apagada")
checar(c.delete("/notificacoes/nao-e-id", headers=ANA).status_code == 404, "id inválido: 404")
checar(c.delete(f"/notificacoes/{id_beto}", headers=CMD).status_code == 403, "o COMANDO não apaga nada")
a.marcar_lidas("op1", "emp")
N.notificar("N20", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx5")
checar(c.post("/notificacoes/excluir", json={}, headers=ANA).status_code == 422, "excluir sem dizer quais: 422")
r = c.post("/notificacoes/excluir", json={"lidas": True}, headers=ANA)
restam = sorted(l["tipo"] for l in a.linhas if l["usuario_id"] == "op1")
checar(r.status_code == 200 and restam == ["N20"] and de(a, "op2"),
       "'Excluir as lidas' apaga só as lidas da pessoa", str(restam))
r = c.post("/notificacoes/excluir", json={"ids": [de(a, "op1", "N20")[0]["id"]]}, headers=ANA)
checar(r.status_code == 200 and r.json()["excluidas"] == 1 and not de(a, "op1"), "excluir por ids")
N.notificar("N06", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "João", "quando": "hoje às 15:00"}, chave="lx6")
N.notificar("N18", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx7")
N.notificar("N19", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria"}, chave="lx8")
a.marcar_lidas("op1", "emp", [de(a, "op1", "N06")[0]["id"], de(a, "op1", "N18")[0]["id"]])
cat18 = de(a, "op1", "N18")[0]["categoria"]
r = c.post("/notificacoes/excluir", json={"lidas": True, "categoria": cat18}, headers=ANA)
restam = sorted(l["tipo"] for l in a.linhas if l["usuario_id"] == "op1")
checar(r.status_code == 200 and r.json()["excluidas"] == 1 and restam == ["N06", "N19"],
       "'Excluir as lidas' com a página filtrada: só as lidas daquele assunto", str(restam))
checar(c.post("/notificacoes/excluir", json={"lidas": True, "categoria": "xyz"}, headers=ANA).status_code == 422
       and c.post("/notificacoes/excluir", json={"lidas": True, "prioridade": "baixa"}, headers=ANA).status_code == 422,
       "excluir com assunto ou prioridade desconhecidos: 422")
r = c.post("/notificacoes/excluir", json={"ids": []}, headers=ANA)
checar(r.status_code == 200 and r.json()["excluidas"] == 0 and len(de(a, "op1")) == 2, "lista vazia de ids não apaga nada")

print("— página de notificações: filtros e contagem por assunto —")
a = novo()
N.notificar("N03", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="pg1")
N.notificar("N22", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Maria", "predicao_id": "p1"}, chave="pg2")
N.notificar("N06", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "João", "quando": "hoje às 15:00"}, chave="pg3")
N.notificar("N07", "emp", usuarios=["op1"], ou_admins=False, contexto={"nome": "Ana", "quando": "hoje às 16:00"}, chave="pg4")
a.marcar_lidas("op1", "emp", [de(a, "op1", "N07")[0]["id"]])
r = c.get("/notificacoes", params={"categoria": "reunioes"}, headers=ANA).json()
checar([i["tipo"] for i in r["itens"]] == ["N06"] and r["nao_lidas"] == 3,
       "filtro por assunto (as contagens seguem sendo de tudo o que está aberto)", str([i["tipo"] for i in r["itens"]]))
checar(r["por_categoria"] == {"conversas": 1, "reunioes": 1, "retornos": 0, "pedidos": 1, "equipe": 0, "sistema": 0},
       "não lidas por assunto, para os filtros da página", str(r.get("por_categoria")))
r = c.get("/notificacoes", params={"categoria": "reunioes", "filtro": "todas"}, headers=ANA).json()
checar(sorted(i["tipo"] for i in r["itens"]) == ["N06", "N07"], "assunto com o histórico: também as já lidas")
r = c.get("/notificacoes", params={"prioridade": "urgente"}, headers=ANA).json()
checar([i["tipo"] for i in r["itens"]] == ["N03"], "só urgentes")
checar(c.get("/notificacoes", params={"categoria": "xyz"}, headers=ANA).status_code == 422
       and c.get("/notificacoes", params={"prioridade": "baixa"}, headers=ANA).status_code == 422,
       "assunto ou prioridade desconhecidos: 422")
checar(c.get("/notificacoes", params={"categoria": "reunioes"}, headers=CMD).json() == {**main._NOTIFICACOES_VAZIO},
       "o COMANDO recebe a resposta vazia, também com filtro")

class SemTabela(N.ArmazemMemoria):
    def listar(s, *a): raise RuntimeError('relation "public.notificacoes" does not exist')
N.usar_armazem(SemTabela(usuarios=PESSOAS))
r = c.get("/notificacoes", headers=ANA)
checar(r.status_code == 200 and r.json()["ativo"] is False and "migracao_notificacoes" in r.json().get("mensagem", ""),
       "sem a tabela: a resposta diz que não está ligado (o sino some), sem erro")
class Lento(N.ArmazemMemoria):
    def listar(s, *a): raise TimeoutError("banco lento")
N.usar_armazem(Lento(usuarios=PESSOAS))
r = c.get("/notificacoes", headers=ANA)
checar(r.status_code == 503 and "Código" in r.text, "banco fora: 503 com código, sem detalhe técnico", r.text[:120])

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
