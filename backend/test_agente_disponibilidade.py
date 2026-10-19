"""Disponibilidade de operador: próximo horário real no handoff, cadastro em
memória e a correção do bug R3_FREQUENCIA x mensagem de segurança
(docs/PLANO_DISPONIBILIDADE_OPERADOR.md).

    python test_agente_disponibilidade.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agente import auditor, disponibilidade, orquestrador as orq        # noqa: E402
from agente.fonte import FonteMemoria                                   # noqa: E402
from agente.grafos import grafo_mensagem                                # noqa: E402
from agente.llm import ClienteFalso                                     # noqa: E402
from agente.repositorio import RepoMemoria                              # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)          # sexta, 14h em Brasília
DEVEDOR = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "Maria das Dores",
           "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao"}


def mundo(operadores=None, disponibilidades=None, situacao="em_contato"):
    repo, fonte = RepoMemoria(), FonteMemoria([DEVEDOR])
    if operadores is not None:
        fonte._operadores = operadores
    for d in disponibilidades or []:
        fonte.disponibilidades.append(d)
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": situacao, "dados": {}})
    repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    return repo, fonte, caso


print("— função determinística: próximo atendimento —")
_, fonte_vazia, _ = mundo()
checar(disponibilidade.proximo_atendimento(fonte_vazia, "emp", SEXTA_14H) is None,
       "sem nenhum operador com disponibilidade: None (cai no texto genérico)")

OP = {"id": "op1", "nome": "Carla"}
# sexta = dia_semana 4. Faixa de hoje já começou (8h-12h): não serve para hoje.
# Sábado (dia_semana 5) tem faixa 9h-13h: é o próximo horário real a partir de sexta 14h.
_, fonte1, _ = mundo(operadores=[OP], disponibilidades=[
    {"id": "d1", "empresa_id": "emp", "usuario_id": "op1", "dia_semana": 4,
     "hora_inicio": 8, "hora_fim": 12, "ativo": True},
    {"id": "d2", "empresa_id": "emp", "usuario_id": "op1", "dia_semana": 5,
     "hora_inicio": 9, "hora_fim": 13, "ativo": True},
])
prox = disponibilidade.proximo_atendimento(fonte1, "emp", SEXTA_14H)
checar(prox is not None and prox["nome"] == "Carla" and prox["hora_inicio"] == 9 and prox["dia_semana"] == 5,
       "pula a faixa de hoje que já começou e acha o sábado às 9h", str(prox))

# Faixa de hoje ainda não começou (16h-18h, agora são 14h): vale para hoje mesmo.
_, fonte2, _ = mundo(operadores=[OP], disponibilidades=[
    {"id": "d1", "empresa_id": "emp", "usuario_id": "op1", "dia_semana": 4,
     "hora_inicio": 16, "hora_fim": 18, "ativo": True},
])
prox2 = disponibilidade.proximo_atendimento(fonte2, "emp", SEXTA_14H)
checar(prox2 is not None and prox2["dia"] == "2026-10-16" and prox2["hora_inicio"] == 16,
       "faixa de hoje que ainda não começou conta como próximo horário", str(prox2))

# Operador inativo (não está mais na lista de operadores) não entra na escolha.
_, fonte3, _ = mundo(operadores=[], disponibilidades=[
    {"id": "d1", "empresa_id": "emp", "usuario_id": "op_saiu", "dia_semana": 4,
     "hora_inicio": 16, "hora_fim": 18, "ativo": True},
])
checar(disponibilidade.proximo_atendimento(fonte3, "emp", SEXTA_14H) is None,
       "disponibilidade de operador que não está mais ativo não conta")


print("— handoff com nome e horário reais —")
repo, fonte, caso = mundo(operadores=[OP], disponibilidades=[
    {"id": "d1", "empresa_id": "emp", "usuario_id": "op1", "dia_semana": 4,
     "hora_inicio": 16, "hora_fim": 18, "ativo": True},
])
grafos = {"mensagem_devedor": grafo_mensagem(fonte)}
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1", {"texto": "Quero falar com um atendente"})
r = orq.processar_proximo(repo, grafos, ClienteFalso(["NÃO DEVIA SER CHAMADO"]), SEXTA_14H)
saidas = [m["texto"] for m in repo.mensagens if m["direcao"] == "saida"]
checar(r["ok"] and repo.obter_caso(caso["id"])["situacao"] == "com_pessoa", "caso passa para com_pessoa")
checar(len(saidas) == 1 and "Carla" in saidas[0] and "16h" in saidas[0],
       "a mensagem de handoff tem o nome e o horário reais do operador", str(saidas))
checar("qualquer coisa que a IA não disse" not in saidas[0], "nada do texto vem de IA (ClienteFalso nunca foi chamado)")


print("— sem operador disponível: cai no texto genérico, sem quebrar —")
repo, fonte, caso = mundo()
grafos = {"mensagem_devedor": grafo_mensagem(fonte)}
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1", {"texto": "Quero falar com um atendente"})
r = orq.processar_proximo(repo, grafos, ClienteFalso(["NÃO DEVIA SER CHAMADO"]), SEXTA_14H)
saidas = [m["texto"] for m in repo.mensagens if m["direcao"] == "saida"]
checar(r["ok"] and repo.obter_caso(caso["id"])["situacao"] == "com_pessoa", "mesmo sem disponibilidade, transfere")
checar(len(saidas) == 1 and "pessoa da equipe" in saidas[0] and "Carla" not in saidas[0],
       "mensagem genérica (sem nome nem horário inventados)", str(saidas))


print("— bug corrigido: R3_FREQUENCIA não bloqueia o handoff —")
d = auditor.auditar({"tipo": "enviar_mensagem", "params": {}},
                    {"id": "c1", "situacao": "em_contato"}, auditor.POLITICA_DEMONSTRACAO, 1, SEXTA_14H,
                    contatos_7d=99)
checar(not d["permitida"] and d["regra"] == "R3_FREQUENCIA",
       "mensagem comum (enviar_mensagem) continua bloqueada no limite: confirma que o teste é real")
d2 = auditor.auditar({"tipo": "enviar_mensagem_seguranca", "params": {}},
                     {"id": "c1", "situacao": "com_pessoa"}, auditor.POLITICA_DEMONSTRACAO, 1, SEXTA_14H,
                     contatos_7d=99)
checar(d2["permitida"] and d2["regra"] == "R9_SEGURANCA",
       "mensagem de handoff/segurança passa mesmo no limite semanal e com o caso fora da janela de contato")

# Cenário de ponta a ponta: devedor já recebeu o máximo de contatos permitido
# na semana e, mesmo assim, o handoff (que é o único jeito de passar o caso
# para uma pessoa) tem que sair — sem isso, a conversa parece simplesmente
# morta para quem pediu ajuda.
repo, fonte, caso = mundo()
for i in range(auditor.POLITICA_DEMONSTRACAO["contatos_semana_max"]):
    repo.gravar_mensagem("emp", caso["id"], "saida", f"contato anterior {i}", "trace",
                        criado_em=SEXTA_14H - timedelta(hours=1))
grafos = {"mensagem_devedor": grafo_mensagem(fonte)}
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1", {"texto": "Quero falar com um atendente"})
r = orq.processar_proximo(repo, grafos, ClienteFalso(["NÃO DEVIA SER CHAMADO"]), SEXTA_14H)
saidas = [m["texto"] for m in repo.mensagens if m["direcao"] == "saida"]
checar(r["ok"] and repo.obter_caso(caso["id"])["situacao"] == "com_pessoa",
       "devedor no limite semanal de contatos: mesmo assim o caso vai para a equipe")
checar(saidas and "pessoa da equipe" in saidas[-1],
       "e a confirmação do handoff é enviada, não fica em silêncio", str(saidas))
passo_seguranca = [p for p in repo.passos if p["no"] == "auditor" and (p.get("regra") == "R9_SEGURANCA")]
checar(any(True for _ in passo_seguranca), "o rastreio mostra a decisão de segurança, não um bloqueio silencioso")


print("— CRUD em memória (FonteMemoria) ──────────────────────────────────")
_, fonte, _ = mundo(operadores=[OP])
item = fonte.criar_disponibilidade("emp", "op1", 1, 9, 12)
checar(item["id"] and item["dia_semana"] == 1, "cria faixa")
checar(len(fonte.disponibilidade_operador("emp")) == 1, "lista só a da empresa")
checar(fonte.disponibilidade_operador("outra_empresa") == [], "não vaza entre empresas")
ok = fonte.editar_disponibilidade("emp", item["id"], {"hora_fim": 13})
checar(ok and ok["hora_fim"] == 13, "edita a faixa")
checar(fonte.remover_disponibilidade("emp", item["id"]), "remove (desativa) a faixa")
checar(fonte.disponibilidade_operador("emp") == [], "some da listagem depois de removida")
checar(not fonte.remover_disponibilidade("emp", "nao-existe"), "remover item inexistente: False, não quebra")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
