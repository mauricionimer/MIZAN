"""Agentes — as 15 ferramentas do Negociador, com devedor fictício e sem banco.

    python test_agente_ferramentas.py
"""
import copy, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import auditor, ferramentas as fer, orquestrador as orq   # noqa: E402
from agente.fonte import FonteMemoria, FonteSupabase                  # noqa: E402
from agente.llm import ClienteFalso                                   # noqa: E402
from agente.repositorio import RepoMemoria                            # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)   # 14h em Brasília
DEVEDOR = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "maria das dores",
           "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1"}

def cenario(chamadas, situacao="em_contato", politica=True, agora=SEXTA_14H, dados=None, devedores=None):
    """Roda uma sequência de chamadas de ferramenta num evento. Devolve (resultados, repo, fonte, caso)."""
    repo, fonte = RepoMemoria(), FonteMemoria(devedores or [DEVEDOR])
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": situacao, "dados": dados or {}})
    if politica:
        repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    res = []
    def no(ctx):
        for item in chamadas:
            nome, args = item(res) if callable(item) else item
            res.append(fer.executar(ctx, fonte, nome, args))
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
    orq.processar_proximo(repo, {"mensagem_devedor": orq.Grafo("g", "a").no("a", no, agente="negociador")},
                          ClienteFalso(), agora)
    return res, repo, fonte, repo.obter_caso(caso["id"])

print("— definições —")
defs = fer.definicoes()
checar(len(defs) == 15 and all({"name", "description", "input_schema"} <= set(d) for d in defs),
       "15 ferramentas no formato da API")
acoes = {f.acao for f in fer.FERRAMENTAS.values()}
conhecidas = auditor.SEGURANCA | auditor.FALA | auditor.ACORDO | auditor.COMPROMISSO | auditor.REGISTRO | auditor.LEITURA
checar(acoes <= conhecidas, "toda ferramenta corresponde a uma ação que o Auditor conhece", str(acoes - conhecidas))

print("— identidade primeiro —")
r, repo, fonte, c = cenario([("consultar_caso", {}), ("simular_acordo", {"n_parcelas": 1}),
                              ("verificar_identidade", {"tres_primeiros_digitos_cpf": "999"}),
                              ("verificar_identidade", {"tres_primeiros_digitos_cpf": "123"}),
                              ("consultar_caso", {})])
checar(r[0]["primeiro_nome"] == "Maria" and "valor_divida" not in r[0], "antes: só primeiro nome, sem valores")
checar(not r[1]["ok"] and "identidade" in r[1]["erro"], "simular antes de confirmar: recusado")
checar(r[2]["confirmada"] is False and r[2]["tentativas_restantes"] == 2, "dígitos errados: não confirma")
checar(r[3]["confirmada"] and r[4]["valor_divida"] == 3000.0, "dígitos certos: libera os valores")
todos = str(r)
checar("123.456" not in todos and "dores" not in todos.lower(), "CPF e nome completo nunca vão para a IA")
r, *_ = cenario([("verificar_identidade", {"tres_primeiros_digitos_cpf": "000"})] * 4)
checar(r[3]["ok"] is False and "transfira" in r[3]["erro"], "3 erros: para de tentar e manda transferir")

ID_OK = {"identidade_ok": True, "divida": 3000.0}

print("— simular e aceitar —")
r, repo, fonte, c = cenario([
    ("simular_acordo", {"desconto_pct": 10, "n_parcelas": 6, "entrada_pct": 10, "cabe_por_mes": 500}),
    lambda res: ("registrar_aceite", {"simulacao_id": res[0]["simulacao_id"], "data_primeiro_pagamento": "2026-10-20"}),
    lambda res: ("registrar_aceite", {"simulacao_id": res[0]["simulacao_id"], "data_primeiro_pagamento": "2026-10-20"}),
], dados=ID_OK)
s = r[0]
checar(s["dentro_da_politica"] and s["valor_negociado"] == 2700 and s["entrada"] == 270 and s["parcela"] == 405
       and s["cabe_no_bolso"], "valores exatos do simulador (2.700; entrada 270; 6x 405) e cabe em R$ 500")
checar(r[1]["registrado"] and c["situacao"] == "acordo_ativo" and str(c["proxima_data"]) == "2026-10-20",
       "aceite: acordo ativo, próxima data marcada")
checar(len(fonte.agenda) == 1 and fonte.agenda[0]["tipo"] == "promessa" and fonte.agenda[0]["valor"] == 270
       and fonte.agenda[0]["operador_id"] == "op1", "promessa na agenda do responsável, valor = entrada")
checar(len(fonte.ofertas) == 1 and fonte.ofertas[0]["resposta"] == "aceitou" and fonte.ofertas[0]["parcela"] == 405,
       "oferta aceita no histórico de ofertas")
checar(r[2]["bloqueado"] and r[2]["regra"] == "R8_SIMULACAO" and len(fonte.agenda) == 1,
       "mesma simulação de novo: bloqueada, nada duplicado")
checar(fonte.contatos == [], "o agente não registra 'prometeu pagar' (bandit só aprende com dinheiro)")

r, *_ = cenario([("simular_acordo", {"desconto_pct": 50, "n_parcelas": 1})], dados=ID_OK)
checar(not r[0]["dentro_da_politica"] and "simulacao_id" not in r[0] and "desconto" in r[0]["motivo"],
       "fora da política: mostra o motivo e não gera simulação aceitável")
r, *_ = cenario([("simular_acordo", {"n_parcelas": 12, "entrada_pct": 10, "cabe_por_mes": 200})], dados=ID_OK)
checar(r[0]["dentro_da_politica"] and r[0]["cabe_no_bolso"] is False, "12x de 225 não cabe em R$ 200")
r, *_ = cenario([("simular_acordo", {"desconto_pct": 10, "n_parcelas": 1}),
                 lambda res: ("registrar_aceite", {"simulacao_id": res[0]["simulacao_id"],
                                                   "data_primeiro_pagamento": "2026-12-31"})], dados=ID_OK)
checar(r[1]["bloqueado"] and r[1]["regra"] == "R11_DATA", "data do pagamento além de 30 dias: bloqueado")
r, *_ = cenario([("simular_acordo", {"desconto_pct": 10, "n_parcelas": 1}),
                 lambda res: ("registrar_aceite", {"simulacao_id": res[0]["simulacao_id"],
                                                   "data_primeiro_pagamento": "2026-10-20"})],
                dados=ID_OK, agora=SEXTA_14H)
checar(r[1]["registrado"], "à vista com 10%: aceito")

print("— ofertas do catálogo —")
r, *_ = cenario([("listar_ofertas", {})], dados=ID_OK)
nomes = [o["desconto_pct"] for o in r[0]["ofertas"]]
checar(r[0]["ok"] and r[0]["ofertas"] and all(d <= 30 for d in nomes), "só as ofertas dentro da política", str(nomes))
parc = [o for o in r[0]["ofertas"] if o["n_parcelas"] > 1]
checar(parc and all(o["entrada_pct"] == 10 and o["entrada_ajustada"] for o in parc),
       "parcelado sem entrada no catálogo: entrada sobe ao mínimo da política e vem marcado", str(parc))
r, *_ = cenario([("listar_ofertas", {})], dados=ID_OK, politica=False)
checar(r[0]["ofertas"] == [], "sem política: nenhuma oferta")

print("— segurança —")
r, repo, fonte, c = cenario([("suspender_cobranca", {"motivo": "pediu_para_parar"}),
                              ("simular_acordo", {"n_parcelas": 1}),
                              ("agendar_retorno", {"data": "2026-10-20", "motivo": "x"})], dados=ID_OK)
checar(r[0]["cobranca_suspensa"] and c["situacao"] == "suspenso", "pediu para parar: suspenso")
checar(r[2]["bloqueado"] and r[2]["regra"] == "R1_SITUACAO", "depois de suspenso, não agenda mais nada")
r, repo, fonte, c = cenario([("abrir_contestacao", {"motivo": "não reconheço"}),
                              ("abrir_contestacao", {"motivo": "não reconheço"})], politica=False)
checar(c["situacao"] == "contestado" and len(fonte.contestacoes) == 1, "contestação sem política e sem identidade; uma só")
r, repo, fonte, c = cenario([("transferir_para_humano", {"motivo": "pedido_do_devedor", "resumo": "quer falar com gente"})],
                            politica=False, agora=SEXTA_14H - timedelta(hours=14))
checar(c["situacao"] == "com_pessoa" and fonte.agenda[0]["data"] == "2026-10-16" and "quer falar" in c["resumo"],
       "transferência de madrugada, sem política: vai para a agenda do responsável hoje")
r, repo, fonte, c = cenario([("registrar_pagamento_informado", {"data": "2026-10-15", "valor": 270})])
checar(c["situacao"] == "pagamento_em_conferencia" and "conferir" in fonte.agenda[0]["observacao"],
       "'já paguei': cobrança suspensa e conferência para a equipe")

print("— compromissos —")
def com_promessa():
    f = FonteMemoria([DEVEDOR])
    f.criar_agenda("emp", DEVEDOR, "promessa", "2026-10-18", valor=270)
    return f
fonte0 = com_promessa(); item = fonte0.agenda[0]["id"]
r, repo, fonte, c = cenario([("remarcar_compromisso", {"compromisso_id": item, "data": "2026-10-25", "motivo": "salário"})],
                            dados=ID_OK, devedores=[DEVEDOR])
checar(not r[0]["ok"] and "não encontrado" in r[0]["erro"], "compromisso inexistente nesta fonte: recusado")

# Mesma fonte com a promessa já gravada.
repo = RepoMemoria(); fonte = fonte0
caso = repo.obter_ou_criar_caso("emp", "p1")
repo.salvar_caso(caso["id"], {"situacao": "acordo_ativo", "dados": dict(ID_OK)})
repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
res = []
def remarca(ctx):
    for d in ("2026-10-25", "2026-10-28", "2026-10-30"):
        res.append(fer.executar(ctx, fonte, "remarcar_compromisso", {"compromisso_id": item, "data": d, "motivo": "salário"}))
    res.append(fer.executar(ctx, fonte, "marcar_promessa_quebrada", {"compromisso_id": item, "motivo": "sem resposta"}))
orq.registrar_evento(repo, "emp", caso["id"], "vencimento", "v1")
orq.processar_proximo(repo, {"vencimento": orq.Grafo("g", "a").no("a", remarca)}, ClienteFalso(), SEXTA_14H)
checar(res[0]["ok"] and res[1]["ok"] and res[2]["regra"] == "R12_REMARCACOES", "2 remarcações; a 3ª é bloqueada")
checar(fonte.agenda[0]["data"] == "2026-10-28", "data remarcada na agenda")
checar(res[3]["ok"] and fonte.agenda[0]["situacao"] == "quebrada", "promessa marcada como quebrada")

r, *_ = cenario([("agendar_retorno", {"data": "2026-10-16", "motivo": "x"})], dados=ID_OK)
checar(r[0]["regra"] == "R11_DATA", "retorno para hoje: bloqueado (precisa ser depois)")
r, repo, fonte, c = cenario([("agendar_retorno", {"data": "2026-10-19", "motivo": "vai ver com a esposa"})], dados=ID_OK)
checar(r[0]["ok"] and fonte.agenda[0]["tipo"] == "retorno", "retorno marcado")
r, repo, fonte, c = cenario([("registrar_contato", {"resultado": "nao_quis", "observacao": "sem interesse"})])
checar(r[0]["ok"] and fonte.contatos[0]["resultado"] == "nao_quis", "contato sem acordo registrado")

print("— uso errado vira resposta, não quebra —")
r, repo, *_ = cenario([("apagar_tudo", {}), ("simular_acordo", {"n_parcelas": "doze"}),
                       ("simular_acordo", {"n_parcelas": 2, "extra": 1}), ("agendar_retorno", {"data": "amanhã", "motivo": "x"}),
                       ("registrar_contato", {"resultado": "prometeu_pagar"})], dados=ID_OK)
checar(all(not x["ok"] for x in r), "ferramenta desconhecida, tipo errado, argumento a mais, data ruim, valor fora da lista")
checar(any(p["regra"] == "R0_ACAO_DESCONHECIDA" for p in repo.passos), "ferramenta desconhecida fica no rastreio")
r, *_ = cenario([("consultar_caso", {})], devedores=[{**DEVEDOR, "empresa_id": "outra"}])
checar(not r[0]["ok"] and "não encontrado" in r[0]["erro"], "devedor de outra empresa: não encontrado")
r, *_ = cenario([("consultar_politica", {})])
checar(r[0]["regras"]["desconto_max_pct"] == 30 and r[0]["versao"] == 1, "consulta a política vigente")

print("— rastreio —")
r, repo, *_ = cenario([("simular_acordo", {"n_parcelas": 1}),
                       lambda res: ("registrar_aceite", {"simulacao_id": res[0]["simulacao_id"],
                                                         "data_primeiro_pagamento": "2026-10-20"})], dados=ID_OK)
nos = [p["no"] for p in repo.passos]
checar(nos == ["auditor", "ferramenta:simular_acordo", "auditor", "ferramenta:registrar_aceite", "a"],
       "cada ferramenta: decisão do Auditor e depois a execução", str(nos))

print("— Supabase: escopo da empresa (sem banco de verdade) —")
class Q:
    def __init__(s, db, t): s.db, s.t, s.ops = db, t, []
    def __getattr__(s, nome):
        def f(*a, **k):
            s.ops.append((nome, a)); return s
        return f
    def execute(s):
        s.db.log.append((s.t, s.ops))
        class R: pass
        r = R(); r.data = s.db.resposta.pop(0) if s.db.resposta else []
        return r
class DB:
    def __init__(s): s.log, s.resposta = [], []
    def table(s, t): return Q(s, t)
db = DB(); fs = FonteSupabase(db)
db.resposta = [[{"id": "p1", "carteira_id": "cart-de-outra", "cpf": "1"}], []]
checar(fs.devedor("emp", "p1") is None, "predição de carteira de outra empresa: não encontrado")
checar(("eq", ("empresa_id", "emp")) in db.log[-1][1] and db.log[-1][0] == "carteiras", "confere a carteira na empresa")
db.resposta = [[{"id": "x"}]]
fs.atualizar_agenda("emp", "p1", "x", {"data": "2026-10-20"})
ops = db.log[-1][1]
checar(all(o in ops for o in (("eq", ("empresa_id", "emp")), ("eq", ("predicao_id", "p1")), ("eq", ("situacao", "pendente")))),
       "atualiza agenda só do devedor, da empresa e pendente")
db.resposta = [[{"id": "c"}]]
fs.registrar_contato("emp", {"id": "p1", "cpf": "1"}, "nao_quis", "x")
checar(db.log[-1][0] == "contatos" and not any(t == "recomendacoes" or t == "bandit_estado" for t, _ in db.log),
       "contato do agente não mexe no bandit")

print()
print(f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
