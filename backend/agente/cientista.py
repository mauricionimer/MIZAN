"""Agente Cientista: lê os resultados e propõe o próximo passo, sem inventar evidência.

(docs/PLANO_AGENTES_IA.md, etapa 6)

- As contas são de agente/ciencia.py (código): taxas, intervalos, composição dos
  grupos, segmentos, o que o bandit aprendeu e o selo de evidência.
- A IA formula até 3 hipóteses a partir desses resultados e escreve o
  relatório: resultado, condições de uso, próximo experimento e uma recomendação
  para o Estrategista.
- Travas em código: todo número do texto tem de existir nos resultados; sem selo
  "evidência", o texto não pode dizer "comprovado", "causou", "garante" etc.;
  o selo de cada hipótese vem do código, não da IA.
- Reprovou duas vezes, IA desligada ou falhou: relatório escrito em código.
- A recomendação nasce "proposta". Só uma pessoa aprova; aprovada, entra como
  orientação no Estrategista. Não muda a política nem o bandit.
"""
import json
import re

from agente import ciencia, guardrails

VERSAO_PROMPT = "cientista-v3"            # v3: direção do resultado (agente pior pede rever a abordagem)
MAX_HIPOTESES = 3
METRICAS = ("taxa_pagamento", "recuperado_por_real")
_CAUSAL = re.compile(r"\b(comprovad\w*|comprova\w*|prova(?:m|do|da)? que|caus(?:ou|a|aram|ando)|garant\w*|"
                     r"certeza|definitiv\w*|sem dúvida|demonstra\w*|evidência estatística|com evidência|"
                     r"há evidência|aument(?:ou|aram)|elev(?:ou|aram)|efeito d[oa])\b", re.IGNORECASE)
# "Não há dúvida", "não resta dúvida", "sem dúvida": a negação aqui afirma; não serve de ressalva.
_DUVIDA = re.compile(r"\b(?:não\s+(?:há|resta|existe|tem)|sem|nenhuma)\s+(?:qualquer\s+|nenhuma\s+|mais\s+)?dúvidas?\b",
                     re.IGNORECASE)
_NEGACAO = re.compile(r"\b(sem|não|nem|falta\w*|ainda não|insuficiente)\b[^.;]{0,40}$", re.IGNORECASE)
# Recomendação de oferta só pode se apoiar no bandit (que sugere, mas não prova). Só nomes de
# oferta ou de canal: "parcela dos devedores" ou "agente ligado" não são oferta.
_OFERTA = re.compile(r"\b(avista_10pct|parcelado_4x|desconto_30pct|parcelado_12x|\d+\s?x|\d+\s?% de desconto|"
                     r"desconto|à vista|parcelamento|parcelad[oa]s?|whatsapp|telefone|ligaç(?:ão|ões)|carta|e-mail)\b",
                     re.IGNORECASE)
_MILHAR = r"[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?(?![\d.])"        # 3.000 / 12.500,00
_NUMERO = re.compile(_MILHAR + r"|\d+(?:[.,]\d+)?")
_MANTER = re.compile(r"\b(mant(?:er|enha|enham|ém)|continuar com) (?:a |o )?(?:mesma |atual )?(?:abordagem|estratégia)\b",
                     re.IGNORECASE)


# ── dados ────────────────────────────────────────────────────────────────────

def observacoes(repo, fonte, empresa_id: str) -> list:
    """Casos que entraram no grupo "contato" (procurados pelo agente ou sorteados para comparação).

    Vale o grupo de entrada (`dados.grupo_entrada`): o plano diário muda o grupo
    de quem fechou acordo ou quebrou, e esses casos não podem sumir da conta."""
    casos = [c for c in repo.casos_da_empresa(empresa_id)
             if ((c.get("dados") or {}).get("grupo_entrada") or c.get("grupo")) == "contato"]
    if not casos:
        return []
    devs = {d["id"]: d for d in fonte.devedores(empresa_id)}
    pagos = fonte.pagamentos(empresa_id, [c["predicao_id"] for c in casos])
    obs = []
    for c in casos:
        dev = devs.get(c["predicao_id"]) or {}
        d = c.get("dados") or {}
        recebido = float(pagos.get(c["predicao_id"]) or 0)
        obs.append({"grupo": "sorteado" if c.get("grupo_controle") else "agente",
                    "pagou": c["predicao_id"] in pagos, "recuperado": recebido,
                    "divida": float(dev.get("valor_divida") or 0),
                    "chance": d.get("chance", dev.get("probabilidade_pagamento")),
                    "dias": int(dev.get("dias_em_atraso") or 0), "produto": dev.get("produto") or "não informado",
                    "teve_acordo": bool(d.get("acordo")) or c["situacao"] in ("acordo_ativo", "quitado", "quebrado"),
                    "quebrou": c["situacao"] == "quebrado"})
    return obs


# ── travas ───────────────────────────────────────────────────────────────────

def _numeros_permitidos(resultados: dict) -> set:
    vistos = set()

    def andar(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            for v in (x, x * 100):
                for casas in (0, 1, 2, 4):
                    vistos.add(round(float(v), casas))
                vistos.add(round(abs(float(v)), 1))
                vistos.add(round(abs(float(v)), 0))
        elif isinstance(x, dict):
            for v in x.values():
                andar(v)
        elif isinstance(x, list):
            for v in x:
                andar(v)
        elif isinstance(x, str):
            for m in _NUMERO.findall(x):
                vistos.add(_valor(m))
    andar(resultados)
    vistos.update({95.0, 0.95})          # intervalo de 95%
    vistos.update({4.0, 10.0, 12.0, 30.0})   # nomes das ofertas do catálogo (4x, 12x, 10%, 30%)
    return vistos


def _valor(txt: str) -> float:
    if re.fullmatch(_MILHAR, txt):
        txt = txt.replace(".", "")
    return round(float(txt.replace(",", ".")), 4)


def conferir(texto: str, permitidos: set, pode_causal: bool) -> list:
    motivos = []
    for m in _NUMERO.findall(texto):
        v = _valor(m)
        if not any(abs(v - p) < 1e-6 for p in permitidos):
            motivos.append(f"o número {m} não está nos resultados")
    if not pode_causal:
        if (duvida := _DUVIDA.search(texto)):
            motivos.append(f"'{duvida.group(0)}' sem selo de evidência")
        for m in _CAUSAL.finditer(texto):
            antes = _DUVIDA.sub(" ", texto[:m.start()])           # "não há dúvida de que..." não é ressalva
            if not _NEGACAO.search(antes):                       # "ainda não há evidência" pode
                motivos.append(f"'{m.group(0)}' sem selo de evidência")
                break
    return motivos


def _selo_da_metrica(resultados: dict, metrica: str) -> str:
    comp = resultados["comparacao"]
    if metrica in METRICAS:
        return comp[metrica]["selo"]
    if metrica.startswith("segmento:"):
        nome = metrica.removeprefix("segmento:").strip()
        for s in resultados["segmentos"]:
            if s["segmento"] == nome:
                return s["taxa_pagamento"]["selo"]
    if metrica in ("bandit", "passagens"):
        return ciencia.SEM_EVIDENCIA           # o bandit sugere; prova é a comparação com o sorteado
    raise ValueError(f"métrica desconhecida: {metrica}")


# ── IA ───────────────────────────────────────────────────────────────────────

SISTEMA = """Você é o Cientista de estratégia de uma operação de cobrança. Recebe resultados JÁ CALCULADOS
pelo sistema: a comparação entre os casos procurados pelo agente e um grupo sorteado que não foi procurado
(o sorteio torna a comparação justa), a composição dos grupos, segmentos e o que o bandit (modelo que aprende
qual oferta funciona) acumulou. Responda APENAS com um objeto JSON:
{"resumo": "2 frases", "hipoteses": [{"hipotese": ..., "metrica": ..., "resultado": ..., "condicoes": ...,
 "proximo_experimento": ...}], "recomendacao": "1 ou 2 frases para o Estrategista",
 "recomendacao_metrica": a métrica da hipótese em que a recomendação se apoia}

Regras:
- No máximo 3 hipóteses. A primeira é a que sustenta a recomendação.
- "metrica": "taxa_pagamento", "recuperado_por_real", "segmento:<nome exato do segmento>", "bandit" ou
  "passagens" (o que a equipe ouviu nas transferências da semana: motivos, valor que as pessoas dizem
  conseguir pagar, quantas não couberam em nenhuma condição). Use "passagens" para propor um teste de
  política (ex.: mais parcelas) quando muitas não couberam; é sinal, nunca prova.
  Se <resultados> tiver "passagens" com "nao_coube" maior que zero, inclua uma hipótese com essa métrica.
- Use SOMENTE números que aparecem nos resultados (pode escrever taxas como porcentagem: 0.123 → 12.3%).
  Não calcule números novos. Diferença entre duas taxas se escreve em pontos percentuais (ex.: 29.0 p.p.).
- Cada texto respeita o selo da SUA métrica. O bandit nunca tem selo "evidência": ele sugere, mas só a
  comparação com o grupo sorteado mede efeito. Recomendação apoiada no bandit = "testar", nunca "comprovado".
- O sistema já decidiu o selo de cada métrica ("sem evidência", "indício", "evidência"). Respeite-o:
  com "sem evidência", diga que ainda não dá para concluir e o que falta (ex.: mais casos por grupo);
  com "indício", diga que os grupos diferem em composição; só com "evidência" fale em efeito.
  Nunca escreva "comprovado", "causou", "garante" ou "certeza" sem selo "evidência".
- Se os grupos não forem comparáveis, diga que uma melhora pode vir da composição da carteira.
- Cada métrica tem "direcao", decidida pelo sistema: "melhor" (o agente está acima do sorteado), "pior"
  (o agente está abaixo: o intervalo inteiro fica abaixo de zero) ou "incerto". Com "pior", NUNCA
  recomende manter a abordagem: recomende revê-la (o que mudar e testar contra o sorteado).
- "condicoes": onde o resultado vale (população, período, produto).
- A recomendação é uma orientação de abordagem para o Estrategista; ela não muda a política nem os limites.
- Português do Brasil, frases curtas, para um gestor que não é estatístico."""


def _relatorio_ia(ctx, resultados: dict) -> dict:
    permitidos = _numeros_permitidos(resultados)
    mensagens = [{"role": "user", "content": "<resultados>" + json.dumps(resultados, ensure_ascii=False) + "</resultados>"}]
    for _ in range(2):
        r = ctx.ia("cientista", SISTEMA, mensagens, max_tokens=1500)
        if ctx.rastreio.atual is not None:
            ctx.rastreio.atual["versao_prompt"] = VERSAO_PROMPT
        texto = (r.texto or "").strip()
        if texto.startswith("```"):
            texto = texto.strip("`").removeprefix("json").strip()
        d = json.loads(texto)
        hips = d.get("hipoteses") if isinstance(d, dict) else None
        if not isinstance(hips, list) or not 1 <= len(hips) <= MAX_HIPOTESES:
            raise ValueError("hipóteses fora do formato")
        rel = {"resumo": str(d.get("resumo") or ""), "recomendacao": str(d.get("recomendacao") or ""), "hipoteses": []}
        for h in hips:
            if not isinstance(h, dict):
                raise ValueError("hipótese fora do formato")
            item = {k: str(h.get(k) or "") for k in ("hipotese", "metrica", "resultado", "condicoes", "proximo_experimento")}
            item["selo"] = _selo_da_metrica(resultados, item["metrica"])       # do código, nunca da IA
            rel["hipoteses"].append(item)
        metrica_rec = str(d.get("recomendacao_metrica") or rel["hipoteses"][0]["metrica"])
        if metrica_rec not in [h["metrica"] for h in rel["hipoteses"]]:
            raise ValueError("recomendação apoiada numa métrica que não está nas hipóteses")
        if metrica_rec not in ("bandit", "passagens") and _OFERTA.search(rel["recomendacao"]):
            metrica_rec = "bandit"            # fala de oferta ou canal: quem sustenta é o bandit
        rel["recomendacao_metrica"] = metrica_rec
        rel["selo"] = _selo_da_metrica(resultados, metrica_rec)              # selo da recomendação, do código
        rel["direcao"] = (resultados["comparacao"][metrica_rec].get("direcao") if metrica_rec in METRICAS
                          else ciencia.INCERTO)
        # Cada texto é conferido com o selo da sua métrica; o resumo, com o mais fraco.
        ev = ciencia.EVIDENCIA
        pares = [(rel["recomendacao"], rel["selo"] == ev),
                 (rel["resumo"], all(h["selo"] == ev for h in rel["hipoteses"]))]
        pares += [(h[k], h["selo"] == ev) for h in rel["hipoteses"]
                  for k in ("hipotese", "resultado", "condicoes", "proximo_experimento")]
        motivos = sorted({m for t, pode in pares for m in conferir(t, permitidos, pode)})
        if (resultados["comparacao"]["taxa_pagamento"].get("direcao") == ciencia.PIOR
                and _MANTER.search(rel["recomendacao"])):
            motivos.append("o agente está pior que o grupo sorteado: recomende rever a abordagem, não mantê-la")
        if not motivos and rel["recomendacao"]:
            return rel
        mensagens += [{"role": "assistant", "content": r.texto or ""},
                      {"role": "user", "content": "[verificação automática] O relatório não pode ser publicado: "
                       + "; ".join(motivos or ["recomendação vazia"]) + ". Responda o JSON de novo, corrigido."}]
    raise ValueError("relatório reprovado duas vezes nas travas")


def _pct(x):
    return "sem dado" if x is None else f"{x * 100:.1f}%".replace(".", ",")


def _pp(x):
    return "sem dado" if x is None else f"{x * 100:.1f} p.p.".replace(".", ",", 1)


def relatorio_codigo(resultados: dict) -> dict:
    """Relatório sem IA, só com os números e o selo."""
    c = resultados["comparacao"]
    t = c["taxa_pagamento"]
    n = c["n"]
    if t.get("direcao") == ciencia.PIOR:
        rec = ("O grupo procurado pelo agente está pagando menos do que o grupo sorteado nesta carteira; "
               "rever a abordagem (tom, momento e oferta inicial) e testar a mudança contra o sorteado.")
    elif t["selo"] == ciencia.SEM_EVIDENCIA:
        falta = (f"até ter pelo menos {ciencia.N_MINIMO} casos por grupo com resultado"
                 if min(n["agente"], n["sorteado"]) < ciencia.N_MINIMO else
                 "até a diferença sair do que o acaso explica")
        rec = f"Manter a abordagem atual e o grupo sorteado {falta}; ainda não há base para mudar."
    elif t["selo"] == ciencia.INDICIO:
        rec = "Há indício de efeito, mas os grupos diferem em composição; manter o sorteio e reavaliar."
    else:
        rec = "O agente tem efeito na taxa de pagamento nesta carteira; manter a abordagem e testar a próxima variação."
    return {"resumo": f"Agente: {n['agente']} casos, pagamento {_pct(t['agente'])}. Sorteado: {n['sorteado']} casos, "
                      f"pagamento {_pct(t['sorteado'])}.",
            "recomendacao": rec, "selo": t["selo"], "direcao": t.get("direcao"),
            "hipoteses": [{"hipotese": "Procurar pelo agente aumenta a taxa de pagamento",
                           "metrica": "taxa_pagamento", "selo": t["selo"],
                           "resultado": f"Diferença de {_pp(t['diferenca'])} (intervalo de 95%: {_pp(t['ic95'][0])} a "
                                        f"{_pp(t['ic95'][1])}).",
                           "condicoes": "Casos do grupo contato desta empresa.",
                           "proximo_experimento": "Continuar o sorteio do grupo de comparação."}]
            + _hipotese_passagens(resultados.get("passagens"))}


def _hipotese_passagens(s: dict | None) -> list:
    """O que a equipe ouviu nas transferências vira hipótese de política (em código)."""
    if not s or not s.get("passagens"):
        return []
    if s.get("nao_coube"):
        titulo = "A política atual deixa de fora quem quer pagar, mas não alcança a menor parcela"
        res = (f"{s['nao_coube']} de {s['passagens']} transferências: a pessoa disse quanto podia pagar e nenhuma "
               f"condição coube (valor típico pedido {_brl(s['valor_pedido_quando_nao_coube'])}; menor parcela "
               f"possível {_brl(s['menor_parcela_possivel'])}).")
        exp = "Testar com o grupo sorteado uma condição de mais parcelas para quem não coube, com aprovação do administrador."
    else:
        motivo = next(iter(s.get("por_motivo") or {}), "—")
        titulo = f"O motivo mais comum das transferências ({motivo}) mostra onde o agente mais precisa da equipe"
        res = f"{s['passagens']} transferências na semana; motivo mais comum: {motivo}."
        exp = "Acompanhar os motivos por mais uma semana antes de mudar a política."
    return [{"hipotese": titulo,
             "metrica": "passagens", "selo": ciencia.SEM_EVIDENCIA, "resultado": res,
             "condicoes": f"Passagens para a equipe dos últimos {s.get('dias', 7)} dias.", "proximo_experimento": exp}]


def _brl(v) -> str:
    return "sem dado" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def analisar(ctx, obs: list, stats_bandit: list | None, sinais: dict | None = None) -> dict:
    """Relatório completo: resultados de código + texto da IA (ou de código)."""
    resultados = ciencia.analisar(obs, stats_bandit)
    if sinais and sinais.get("passagens"):
        resultados["passagens"] = sinais
    with ctx.rastreio.span("analise", "cientista") as p:
        rel = ctx.ia_ou_codigo("cientista", lambda: _relatorio_ia(ctx, resultados), lambda: relatorio_codigo(resultados))
        if resultados.get("passagens") and not any(h.get("metrica") == "passagens" for h in rel["hipoteses"]):
            # O que a equipe ouviu sempre aparece, mesmo que a IA não tenha usado. Sem passar de
            # MAX_HIPOTESES: sai a última que não sustenta a recomendação.
            hips = list(rel["hipoteses"])
            while len(hips) >= MAX_HIPOTESES:
                fora = next((i for i in range(len(hips) - 1, 0, -1)
                             if hips[i].get("metrica") != rel.get("recomendacao_metrica")), len(hips) - 1)
                hips.pop(fora)
            rel["hipoteses"] = hips + _hipotese_passagens(resultados["passagens"])
        p["detalhe"] = {**p.get("detalhe", {}), "selo": rel["selo"], "n": resultados["comparacao"]["n"]}
        origem = p["detalhe"].get("origem", "codigo")
    rel["recomendacao"] = guardrails.limpar_nota(rel["recomendacao"], 400)
    return {"relatorio": rel, "resultados": resultados, "origem": origem}


def orientacao(rec: dict | None) -> str | None:
    """O que vai para o Estrategista: só recomendação aprovada, com o selo."""
    if not rec or rec.get("status") != "aprovada":
        return None
    return guardrails.limpar_nota(f"[{rec.get('selo')}] {rec.get('texto') or ''}", 400)

