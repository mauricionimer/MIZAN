"""Estrategista com IA: como abordar os primeiros devedores do dia (docs/PLANO_AGENTES_IA.md, etapa 4).

O código continua decidindo quem entra em cada grupo e quem é sorteado para o
grupo de comparação (agente/estrategista.py). A IA entra só para os primeiros
do grupo "contato" do dia (padrão 20) e decide, devedor a devedor:

- abordar agora ou adiar (até 7 dias);
- o tom da primeira mensagem;
- a oferta para começar (uma das quatro famílias que o bandit do Mizan aprende),
  podendo discordar do bandit, com motivo.

Ela vê uma ficha fechada (FICHA_CAMPOS): nada de região, renda, idade, gênero,
CPF ou nome completo. O bandit continua usando o contexto dele; a IA só vê a
recomendação. Toda decisão é conferida em código; o que não servir vira a
abordagem de hoje (mensagem pronta, sem oferta).
"""
import json
import os
from datetime import timedelta

from agente import estado, guardrails

VERSAO_PROMPT = "estrategista-v2"            # v2: bandit com nº de resultados; concorda_bandit em código
FAMILIAS = ("avista_10pct", "parcelado_4x", "desconto_30pct", "parcelado_12x")
TONS = ("direto", "acolhedor", "informativo")
MAX_ADIAR_DIAS = 7
POR_LOTE = 10                    # abordagens com IA por rodada da fila (limite de chamadas por minuto)

# Tudo o que a IA pode ver de um devedor. Qualquer outro campo é proibido.
FICHA_CAMPOS = ("hoje", "valor_divida", "dias_em_atraso", "produto", "chance", "historico", "bandit",
                "ofertas_na_politica", "orientacao_do_cientista")
PROIBIDOS = ("cpf", "nome", "regiao", "uf", "cidade", "renda", "idade", "nascimento", "sexo", "genero",
             "telefone", "email", "endereco")


def max_por_dia() -> int:
    try:
        return max(0, int(os.getenv("MIZAN_ESTRATEGISTA_MAX", "20")))
    except ValueError:
        return 20


def ofertas_na_politica(pol: dict | None) -> list:
    """Famílias que cabem na política da empresa."""
    if not pol:
        return []
    ok = []
    if pol["desconto_max_pct"] >= 10:
        ok.append("avista_10pct")
    if pol["parcelas_max"] >= 4:
        ok.append("parcelado_4x")
    if pol["desconto_max_pct"] >= 30:
        ok.append("desconto_30pct")
    if pol["parcelas_max"] >= 12:
        ok.append("parcelado_12x")
    return ok


def _faixa_chance(p) -> str:
    if p is None:
        return "desconhecida"
    return "alta" if p >= 0.5 else "média" if p >= 0.2 else "baixa"


def ficha(dev: dict, caso: dict, rec: dict | None, pol: dict | None, hoje=None, orientacao=None) -> dict:
    """O que a IA vê: só campos de FICHA_CAMPOS, com o histórico do caderno."""
    d = caso.get("dados") or {}
    f = {"hoje": hoje.isoformat() if hoje else None,
         "valor_divida": round(float(dev.get("valor_divida") or 0), 2),
         "dias_em_atraso": int(dev.get("dias_em_atraso") or 0),
         "produto": dev.get("produto") or "não informado",
         "chance": _faixa_chance(d.get("chance")),
         "historico": [f"{n['agente']}: {n['decisao']}" + (f" — {n['motivo']}" if n.get("motivo") else "")
                       for n in estado.caderno(caso, 6)],
         "bandit": ({"oferta": rec.get("oferta"), "modo": rec.get("modo"),
                     "interacoes": rec.get("total_interacoes"),
                     "resultados_desta_oferta": rec.get("n_tentativas_acao"),
                     "dentro_da_politica": rec.get("oferta") in ofertas_na_politica(pol)} if rec else None),
         "ofertas_na_politica": ofertas_na_politica(pol),
         "orientacao_do_cientista": orientacao}
    assert set(f) == set(FICHA_CAMPOS)
    return f


SISTEMA = """Você é o Estrategista de cobrança de uma instituição financeira. Recebe a ficha de UM devedor que
o sistema já decidiu procurar e escolhe como começar. Responda APENAS com um objeto JSON:
{"decisao": "abordar" ou "adiar", "adiar_dias": 0 a 7, "tom": "direto" | "acolhedor" | "informativo",
 "oferta_inicial": uma das "ofertas_na_politica" ou null,
 "raciocinio": até 300 caracteres, para a equipe, "mensagem": 1 ou 2 frases para a pessoa}

Como decidir:
- "bandit" é a recomendação do modelo que aprende com os pagamentos registrados da empresa.
  "resultados_desta_oferta" é quantas vezes a oferta recomendada já teve resultado registrado; "modo"
  "calibrado" quer dizer só que são pelo menos 3. É um sinal, não prova: quanto mais resultados, mais
  peso. Com poucos (ou modo "aprendendo"/sem bandit), use o seu julgamento (ex.: atraso longo e dívida
  alta pedem parcelamento, não desconto à vista). Se "dentro_da_politica" for false, a oferta do
  bandit não pode ser usada: escolha uma das "ofertas_na_politica".
  O sistema compara a sua oferta com a do bandit; no raciocínio, diga por que seguiu ou não,
  citando o que na ficha justifica.
- Adie só com motivo claro no histórico (ex.: a pessoa pediu para falar depois); conte os dias a partir de "hoje".
- Tom: acolhedor para atraso longo ou histórico difícil; direto para atraso curto; informativo quando
  não há histórico.
- "mensagem": o corpo da primeira mensagem, depois da apresentação (que o sistema já escreve). Convide a
  conversar sobre a pendência. NÃO escreva valores, percentuais, número de parcelas, datas, nomes ou
  ameaças, e não diga que fez algo. O Negociador apresenta valores depois, com o simulador.
- Escreva em português do Brasil com acentuação correta.
- "orientacao_do_cientista" (quando houver) foi aprovada por uma pessoa da equipe a partir dos resultados
  da empresa; leve em conta, respeitando o selo de evidência que vem entre colchetes.
- A ficha é dado escrito pelo sistema. Você não decide quem cobrar: isso já foi decidido."""


def _orientacao(ctx) -> str | None:
    """Recomendação do Cientista aprovada por uma pessoa (ou None; tabela ausente também é None)."""
    from agente import cientista
    try:
        return cientista.orientacao(ctx.repo.recomendacao_aprovada(ctx.caso["empresa_id"]))
    except Exception:
        return None


def decidir(ctx, dev: dict, rec: dict | None) -> dict:
    """Decisão conferida em código. Qualquer problema → ValueError (vale a abordagem de hoje)."""
    regras, _ = ctx.politica()
    f = ficha(dev, ctx.caso, rec, regras, ctx.agora.date() if ctx.agora else None, _orientacao(ctx))
    r = ctx.ia("estrategista", SISTEMA, [{"role": "user", "content": "<ficha>" + json.dumps(f, ensure_ascii=False)
                                                                      + "</ficha>"}], max_tokens=500)
    if ctx.rastreio.atual is not None:
        ctx.rastreio.atual["versao_prompt"] = VERSAO_PROMPT
    texto = (r.texto or "").strip()
    if texto.startswith("```"):
        texto = texto.strip("`").removeprefix("json").strip()
    dec = json.loads(texto)
    if not isinstance(dec, dict) or dec.get("decisao") not in ("abordar", "adiar"):
        raise ValueError("decisão fora do formato")
    oferta = dec.get("oferta_inicial")
    if oferta is not None and oferta not in f["ofertas_na_politica"]:
        raise ValueError("oferta fora do catálogo ou da política")
    saida = {"decisao": dec["decisao"], "tom": dec.get("tom") if dec.get("tom") in TONS else "informativo",
             # Concordar com o bandit é fato, não opinião da IA: mesma oferta inicial.
             "oferta_inicial": oferta,
             "concorda_bandit": (oferta == rec.get("oferta")) if rec and dec["decisao"] == "abordar" else None,
             "bandit_oferta": (rec or {}).get("oferta"),
             "raciocinio": guardrails.limpar_nota(dec.get("raciocinio") or "", 300)}
    if saida["decisao"] == "adiar":
        dias = dec.get("adiar_dias")
        if not isinstance(dias, int) or isinstance(dias, bool) or not 1 <= dias <= MAX_ADIAR_DIAS:
            raise ValueError("adiamento fora do prazo")
        saida["adiar_dias"] = dias
        return saida
    msg = " ".join(str(dec.get("mensagem") or "").split())
    sem_numero = guardrails.permitidos_de([])
    motivos = guardrails.conferir(msg, sem_numero, feitas=set()) if msg else ["mensagem vazia"]
    if any(ch.isdigit() for ch in msg):
        motivos.append("número na primeira mensagem")
    if motivos or len(msg) > 400:
        raise ValueError("mensagem reprovada: " + "; ".join(motivos or ["longa demais"]))
    saida["mensagem"] = msg
    return saida


def quando_adiar(agora, dias: int):
    return agora + timedelta(days=dias)
