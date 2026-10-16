"""Agentes — Auditor: política com versão, regra aplicada, segurança sempre livre.

    python test_agente_auditor.py
"""
import copy, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agente import auditor, orquestrador as orq    # noqa: E402
from agente.llm import ClienteFalso                # noqa: E402
from agente.repositorio import RepoMemoria         # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

POL = auditor.validar_politica(auditor.POLITICA_DEMONSTRACAO)
# Sexta 16/10/2026, 14h em Brasília = 17h UTC.
SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
CASO = {"id": "c1", "situacao": "negociando", "dados": {"divida": 3000.0, "identidade_ok": True}}

def aud(tipo, params=None, caso=CASO, agora=SEXTA_14H, **kw):
    return auditor.auditar({"tipo": tipo, "params": params or {}}, caso, POL, 1, agora, **kw)

print("— política —")
checar(POL["desconto_max_pct"] == 30 and POL["parcelas_max"] == 12 and POL["dias_semana"] == [0, 1, 2, 3, 4, 5],
       "política de demonstração é válida")
for campo, valor, nome in (("desconto_max_pct", 120, "desconto acima de 95%"), ("hora_inicio", 21, "início depois do fim"),
                           ("dias_semana", [7], "dia inexistente"), ("parcelas_max", True, "verdadeiro/falso não é número")):
    ruim = {**auditor.POLITICA_DEMONSTRACAO, campo: valor}
    try:
        auditor.validar_politica(ruim); ok = False
    except ValueError:
        ok = True
    checar(ok, f"recusa {nome}")
try:
    auditor.validar_politica({k: v for k, v in auditor.POLITICA_DEMONSTRACAO.items() if k != "parcela_min"}); ok = False
except ValueError:
    ok = True
checar(ok, "recusa política incompleta")

print("— lista do que pode —")
d = aud("apagar_divida")
checar(not d["permitida"] and d["regra"] == "R0_ACAO_DESCONHECIDA", "ação desconhecida é bloqueada")
d = auditor.auditar({"tipo": "propor_acordo", "params": {}}, CASO, None, None, SEXTA_14H)
checar(not d["permitida"] and d["regra"] == "R0_SEM_POLITICA", "sem política ativa, nada além de segurança")
for t in ("suspender_contato", "registrar_contestacao", "transferir_para_pessoa"):
    d = auditor.auditar({"tipo": t}, {**CASO, "situacao": "suspenso"}, None, None, SEXTA_14H - timedelta(hours=14))
    checar(d["permitida"] and d["regra"] == "R9_SEGURANCA", f"{t}: sempre permitido, mesmo sem política e de madrugada")
checar(aud("simular_acordo")["permitida"], "consulta e simulação passam")

print("— situação —")
for s in ("suspenso", "contestado", "com_pessoa", "quitado", "novo"):
    d = aud("enviar_mensagem", caso={**CASO, "situacao": s})
    checar(not d["permitida"] and d["regra"] == "R1_SITUACAO", f"não fala com caso '{s}'")

print("— horário e frequência (Brasília) —")
checar(aud("enviar_mensagem")["permitida"], "sexta 14h: pode")
checar(aud("enviar_mensagem", agora=datetime(2026, 10, 16, 10, 59, tzinfo=timezone.utc))["regra"] == "R2_HORARIO",
       "7h59 em Brasília: fora")
checar(aud("enviar_mensagem", agora=datetime(2026, 10, 16, 11, 0, tzinfo=timezone.utc))["permitida"], "8h00: pode")
checar(aud("enviar_mensagem", agora=datetime(2026, 10, 16, 23, 0, tzinfo=timezone.utc))["regra"] == "R2_HORARIO",
       "20h00: fora")
checar(aud("enviar_mensagem", agora=datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc))["regra"] == "R2_HORARIO",
       "domingo: fora")
checar(aud("enviar_mensagem", agora=datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc))["regra"] == "R2_HORARIO",
       "sexta 23h em Brasília (já sábado em UTC): fora")
d = aud("enviar_mensagem", contatos_7d=3)
checar(not d["permitida"] and d["regra"] == "R3_FREQUENCIA", "4º contato na semana: bloqueado")
checar(aud("enviar_mensagem", contatos_7d=2)["permitida"], "3º contato: pode")

print("— condições do acordo —")
checar(aud("propor_acordo", {"desconto_pct": 30, "n_parcelas": 1})["permitida"], "30% à vista: no limite, pode")
d = aud("propor_acordo", {"desconto_pct": 31, "n_parcelas": 1})
checar(d["regra"] == "R4_DESCONTO" and d["versao_politica"] == 1, "31%: bloqueado, com a versão da política")
checar(aud("propor_acordo", {"n_parcelas": 13, "entrada_pct": 10})["regra"] == "R5_PARCELAS", "13 parcelas: bloqueado")
checar(aud("propor_acordo", {"n_parcelas": 12, "entrada_pct": 10})["permitida"], "12x com 10% de entrada: pode")
checar(aud("propor_acordo", {"n_parcelas": 12, "entrada_pct": 5})["regra"] == "R7_ENTRADA_MIN", "entrada de 5%: bloqueado")
pouco = {**CASO, "dados": {"divida": 500.0, "identidade_ok": True}}
checar(aud("propor_acordo", {"n_parcelas": 12, "entrada_pct": 10}, caso=pouco)["regra"] == "R6_PARCELA_MIN",
       "parcela de R$ 37,50 abaixo de R$ 50: bloqueado")
checar(aud("propor_acordo", {"n_parcelas": 0})["regra"] == "R4_CONDICOES", "condição impossível: bloqueado")
checar(aud("propor_acordo", {"n_parcelas": 1}, caso={**CASO, "dados": {"identidade_ok": True}})["regra"] == "R4_CONDICOES",
       "caso sem valor de dívida: bloqueado")

print("— aceite só de simulação do sistema —")
cond = {"desconto_pct": 10, "n_parcelas": 6, "entrada_pct": 10}
sim = {"id": "s1", "caso_id": "c1", "condicoes": cond, "valida_ate": SEXTA_14H + timedelta(minutes=30)}
checar(aud("registrar_aceite", {**cond, "simulacao_id": "s1", "data": "2026-10-20"}, simulacao=sim)["permitida"], "aceite da simulação válida")
checar(aud("registrar_aceite", {**cond, "simulacao_id": "s1", "data": "2026-10-20"})["regra"] == "R8_SIMULACAO", "sem simulação: bloqueado")
checar(aud("registrar_aceite", {**cond, "simulacao_id": "s2", "data": "2026-10-20"}, simulacao=sim)["regra"] == "R8_SIMULACAO",
       "simulação com outro id: bloqueado")
checar(aud("registrar_aceite", {**cond, "desconto_pct": 20, "simulacao_id": "s1", "data": "2026-10-20"}, simulacao=sim)["regra"] == "R8_SIMULACAO",
       "IA mudou o desconto depois de simular: bloqueado")
checar(aud("registrar_aceite", {**cond, "simulacao_id": "s1", "data": "2026-10-20"}, simulacao=sim,
           agora=SEXTA_14H + timedelta(minutes=31))["regra"] == "R8_SIMULACAO", "simulação vencida: bloqueado")
checar(aud("registrar_aceite", {**cond, "simulacao_id": "s1", "data": "2026-10-20"}, simulacao={**sim, "caso_id": "c9"})["regra"] == "R8_SIMULACAO",
       "simulação de outro devedor: bloqueado")

print("— no orquestrador: regra e versão no rastreio —")
repo = RepoMemoria()
caso = repo.obter_ou_criar_caso("emp", "p1")
repo.salvar_caso(caso["id"], {"situacao": "negociando", "dados": {"divida": 3000.0, "identidade_ok": True}})
repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
pol2 = {**copy.deepcopy(auditor.POLITICA_DEMONSTRACAO), "desconto_max_pct": 40.0}
repo.gravar_politica("emp", 2, pol2)
decisoes = []
def propor(ctx):
    decisoes.append(ctx.auditar({"tipo": "propor_acordo", "params": {"desconto_pct": 35, "n_parcelas": 1}}))
    decisoes.append(ctx.auditar({"tipo": "propor_acordo", "params": {"desconto_pct": 45, "n_parcelas": 1}}))
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
orq.processar_proximo(repo, {"mensagem_devedor": orq.Grafo("g", "a").no("a", propor, agente="negociador")},
                      ClienteFalso(), SEXTA_14H)
checar(decisoes[0]["permitida"] and decisoes[0]["versao_politica"] == 2, "vale a versão ativa mais recente (40%)")
checar(not decisoes[1]["permitida"] and decisoes[1]["regra"] == "R4_DESCONTO", "45% bloqueado pela versão 2")
aud_passos = [p for p in repo.passos if p["no"] == "auditor"]
checar([p["resultado"] for p in aud_passos] == ["ok", "bloqueado"] and all(p["versao_politica"] == 2 for p in aud_passos)
       and aud_passos[1]["regra"] == "R4_DESCONTO", "cada decisão vira passo com regra, versão e resultado")
checar(repo.obter_caso(caso["id"])["versao_politica"] == 2, "o caso guarda a versão da política vigente")

repo = RepoMemoria()
caso = repo.obter_ou_criar_caso("emp", "p1")
repo.salvar_caso(caso["id"], {"situacao": "negociando", "dados": {"divida": 3000.0, "identidade_ok": True}})
repo.politicas.append({"empresa_id": "emp", "versao": 1, "regras": {"desconto_max_pct": 999}, "ativa": True})
decisoes.clear()
orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
orq.processar_proximo(repo, {"mensagem_devedor": orq.Grafo("g", "a").no("a", propor)}, ClienteFalso(), SEXTA_14H)
checar(decisoes[0]["regra"] == "R0_SEM_POLITICA", "política gravada inválida: tratada como sem política (bloqueia)")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
