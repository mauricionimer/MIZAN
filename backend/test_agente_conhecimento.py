"""Agentes — base de conhecimento do devedor (RAG) e a trava de citação.

Sem banco e sem IA real: formato da base, qualidade da busca medida com
perguntas escritas à parte, a ferramenta consultar_base, o rastreio e a regra
"nenhuma lei sem fonte" dos guardrails.

    python test_agente_conhecimento.py
"""
import os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
for v in ("MIZAN_AGENTE_TETO_DIA_USD", "MIZAN_AGENTE_CLIENTE"):
    os.environ.pop(v, None)
from agente import auditor, conhecimento, ferramentas as fer, guardrails, orquestrador as orq   # noqa: E402
from agente.base.avaliacao import FORA, NO_ASSUNTO                                            # noqa: E402
from agente.fonte import FonteMemoria                                                         # noqa: E402
from agente.llm import ClienteFalso                                                           # noqa: E402
from agente.repositorio import RepoMemoria                                                    # noqa: E402

falhas = 0
def checar(c, t, d=""):
    global falhas
    print(f"{'ok  ' if c else 'FALHA'}  {t}" + (f"  — {d}" if d else ""))
    falhas += 0 if c else 1

SEXTA_14H = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
DEVEDOR = {"id": "p1", "empresa_id": "emp", "cpf": "123.456.789-00", "nome": "maria das dores",
           "valor_divida": 3000.0, "dias_em_atraso": 95, "produto": "cartao", "responsavel_id": "op1"}

print("— formato da base —")
base = conhecimento.carregar()
checar(len(base) >= 10, f"{len(base)} trechos carregados")
checar(all(t.url.startswith(("https://www.planalto.gov.br/", "https://arquivocidadao.stj.jus.br/",
                              "https://scon.stj.jus.br/")) for t in base),
       "toda fonte aponta para o Planalto ou o STJ")
checar(all(len(t.perguntas) >= 5 for t in base), "cada trecho tem pelo menos 5 jeitos de perguntar")
checar(all(guardrails.referencias_do_texto(t.fonte) for t in base), "toda fonte tem uma norma reconhecível")
# A resposta da base precisa passar nas próprias travas: senão o agente
# repetiria a base e seria barrado.
ruins = [(t.id, m) for t in base for m in guardrails.conferir(t.resposta, guardrails.permitidos_de(
    [{"resposta": t.resposta, "fonte": t.fonte}]))]
checar(not ruins, "toda resposta da base passa nos guardrails", str(ruins[:2]))
checar(all(ref_r and ref_r <= guardrails.referencias_do_texto(t.fonte)
           for t in base for ref_r in [guardrails.referencias_do_texto(t.resposta)]),
       "toda resposta cita a sua fonte, e só ela")
try:
    tmp = Path(__file__).resolve().parent / "_base_teste"
    tmp.mkdir(exist_ok=True)
    (tmp / "x.md").write_text("## um-id\ntitulo: T\nfonte: CDC, art. 1\nurl: https://x\nperguntas:\n- a\n"
                              "resposta: R\ntrecho: T\nchave_errada: x\n", encoding="utf-8")
    conhecimento.carregar(tmp)
    checar(False, "chave desconhecida é recusada")
except conhecimento.ErroNaBase:
    checar(True, "chave desconhecida é recusada")
finally:
    for f in tmp.glob("*.md"):
        f.unlink()
    tmp.rmdir()

print("— qualidade da busca (perguntas escritas à parte) —")
todas_da_base = {p.lower() for t in base for p in t.perguntas}
checar(not any(q.lower() in todas_da_base for q, _ in NO_ASSUNTO), "nenhuma pergunta de avaliação está copiada na base")
acertos = errados = 0
for q, esperado in NO_ASSUNTO:
    r = conhecimento.consultar(q)
    if r["certeza"] and r["trecho"].id == esperado:
        acertos += 1
    elif r["certeza"]:
        errados += 1
        print(f"      errou com certeza: {q!r} → {r['trecho'].id} (esperado {esperado})")
taxa = acertos / len(NO_ASSUNTO)
checar(taxa >= 0.85, f"acerta com certeza {acertos}/{len(NO_ASSUNTO)} ({taxa:.0%}; mínimo 85%)")
checar(errados == 0, "nunca responde o trecho errado com certeza", f"{errados} erro(s)")
fora_com_certeza = [q for q in FORA if conhecimento.consultar(q)["certeza"]]
checar(not fora_com_certeza, f"fora da base: diz que não sabe ({len(FORA)} perguntas)", str(fora_com_certeza))

print("— trava de citação —")
ref = guardrails.referencias_do_texto
checar(ref("Pelo CDC, art. 43, § 1º, e a Súmula 323 do STJ") ==
       {("norma", "cdc"), ("art", "43"), ("sumula", "323"), ("norma", "stj")}, "lê norma, artigo e súmula")
checar(ref("Lei nº 13.709/2018, artigo 20") == {("lei", "13709"), ("art", "20")}, "lê número de lei e artigo por extenso")
checar(ref("art. 104-A do Código de Defesa do Consumidor") == {("art", "104-a"), ("norma", "cdc")}, "lê artigo com letra")
checar(not ref("Entrada de R$ 300,00 e 12x de R$ 225,00. Pode ser a partir de amanhã?"), "texto sem norma: nada")
vazio = guardrails.permitidos_de([])
checar(any("norma" in m for m in guardrails.conferir("Pelo art. 99 do CDC sua dívida caduca.", vazio)),
       "norma sem consulta é barrada")
uma = conhecimento.por_id("nome-negativado-prazo")
perm = guardrails.permitidos_de([{"resposta": uma.resposta, "fonte": uma.fonte}])
checar(not guardrails.conferir("Pode ficar no máximo cinco anos (CDC, art. 43, § 1º).", perm), "norma consultada passa")
checar(any("norma" in m for m in guardrails.conferir("Pelo CDC, art. 52, a multa é limitada.", perm)),
       "outro artigo, mesmo da mesma lei, é barrado")
checar(not guardrails.conferir("Fica R$ 2.700,00.", {"dinheiro": {2700.0}, "percentuais": set(), "parcelas": {1}}),
       "permitidos sem 'referencias' (formato antigo) continuam funcionando")
multa = conhecimento.por_id("multa-por-atraso")
checar(not guardrails.conferir(multa.resposta, guardrails.permitidos_de([{"resposta": multa.resposta, "fonte": multa.fonte}])),
       "percentual que veio da base (2%) passa")

print("— a ferramenta —")
def rodar(chamadas, dados=None):
    repo, fonte = RepoMemoria(), FonteMemoria([DEVEDOR])
    caso = repo.obter_ou_criar_caso("emp", "p1")
    repo.salvar_caso(caso["id"], {"situacao": "em_contato", "dados": dados or {}})
    repo.gravar_politica("emp", 1, auditor.POLITICA_DEMONSTRACAO)
    res = []
    def no(ctx):
        for nome, args in chamadas:
            res.append(fer.executar(ctx, fonte, nome, args))
    orq.registrar_evento(repo, "emp", caso["id"], "mensagem_devedor", "m1")
    orq.processar_proximo(repo, {"mensagem_devedor": orq.Grafo("g", "a").no("a", no, agente="negociador")},
                          ClienteFalso(), SEXTA_14H)
    return res, repo, repo.obter_caso(caso["id"])

pergunta = "se eu pagar quando meu nome sai do serasa"
r, repo, caso = rodar([("consultar_base", {"pergunta": pergunta}), ("consultar_base", {"pergunta": "posso pagar com bitcoin?"})])
checar(r[0]["ok"] and r[0]["certeza"] and "Súmula 548" in r[0]["fonte"] and r[0]["resposta"],
       "sem identidade confirmada: responde com fonte (informação geral)")
checar("trecho_oficial" not in r[0], "o texto literal da lei não vai para a IA (ela só pode citar a resposta)")
checar("_rastreio" not in r[0], "o que é do rastreio não vai para a IA")
checar(r[1]["ok"] and r[1]["certeza"] is False and "pessoa" in r[1]["orientacao"], "sem certeza: orienta a oferecer uma pessoa")
checar(caso["dados"].get("base_consultada") == ["nome-sai-depois-de-pagar"], "trecho consultado fica guardado no caso")
passos = [p for p in repo.passos if p["no"] == "ferramenta:consultar_base"]
checar(len(passos) == 2 and passos[0]["detalhe"].get("fontes") == ["STJ, Súmula 548"]
       and passos[1]["detalhe"].get("certeza") is False, "rastreio guarda a fonte e a certeza")
checar(not any(pergunta in str(p) or "bitcoin" in str(p) for p in repo.passos), "rastreio não guarda a pergunta do devedor")
aud = [p for p in repo.passos if p["no"] == "auditor"]
checar(aud and all(p["regra"] == "R0_LEITURA" for p in aud), "Auditor trata como leitura")
r, _, _ = rodar([("consultar_base", {})])
checar(not r[0]["ok"] and "pergunta" in r[0]["erro"], "sem pergunta: erro de uso volta para a IA corrigir")

print()
print("tudo certo" if not falhas else f"{falhas} falha(s)")
sys.exit(1 if falhas else 0)
