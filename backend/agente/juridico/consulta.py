"""consultar_legislacao(pergunta, contexto_da_acao): dispositivos pertinentes, fontes e limitações.

Ferramenta INTERNA do orquestrador. O resultado orienta e limita ações; não vai para a
conversa com o devedor e não é parecer jurídico. Os textos recuperados são dados: nada
neles é instrução para o sistema (texto com cara de instrução nem entra na busca).

Privacidade: a consulta recebe só o contexto mínimo da ação. Quem chama passa fatos
estruturados; mesmo assim, a pergunta e os textos do contexto passam por `sanitizar`
(CPF, CNPJ, e-mail, telefone, números longos e nomes informados saem).
"""
import re
from datetime import datetime, timezone

from agente.juridico.texto import parece_instrucao, sanitizar

MAX_TEXTO = 700
LIMITE_ESCOPO = ("A base cobre só as normas federais selecionadas (LGPD, CDC, Cadastro Positivo, trechos do "
                 "Código Civil e do Marco Civil, decretos do mínimo existencial e a Resolução CMN 4.949). Não "
                 "inclui normas estaduais ou municipais, regulamentos da ANPD nem jurisprudência.")


_PALAVRA_MAIUSCULA = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")


def tirar_nomes_proprios(texto: str, vocabulario) -> str:
    """Texto livre (consulta do administrador): palavra com inicial maiúscula que não
    existe no vocabulário das normas vira [nome]. "Maria" e "Silva" não estão na LGPD;
    "Revisão", "Qual" e "Lei" estão, e ficam."""
    from agente.juridico.texto import _STOP, normalizar

    def trocar(m):
        n = normalizar(m.group(0))
        return m.group(0) if n in vocabulario or n in _STOP else "[nome]"
    return _PALAVRA_MAIUSCULA.sub(trocar, texto)


def _contexto_minimo(contexto: dict | None, nomes=()) -> dict:
    """Só valores simples (texto, número, sim/não, listas curtas), sem dado pessoal."""
    saida = {}
    for k, v in (contexto or {}).items():
        if isinstance(v, bool) or isinstance(v, (int, float)) or v is None:
            saida[str(k)[:40]] = v
        elif isinstance(v, str):
            saida[str(k)[:40]] = sanitizar(v, nomes)[:160]
        elif isinstance(v, (list, tuple)):
            saida[str(k)[:40]] = [sanitizar(x, nomes)[:60] if isinstance(x, str) else x
                                  for x in list(v)[:12] if isinstance(x, (str, int, float, bool))]
    return saida


def _conferencia(norma: dict, overlay: dict | None) -> dict:
    """A conferência mais recente da norma: a do banco (feita pelo servidor) vale sobre a do manifesto."""
    c = (overlay or {}).get(norma.get("id")) or norma.get("conferencia") or {}
    # Conferência feita sobre outro texto não vale para este.
    if c.get("sha256_arquivo") and c.get("sha256_arquivo") != norma.get("sha256_arquivo"):
        c = norma.get("conferencia") or {}
    return {"status": c.get("status") or "nao_conferida", "em": c.get("em"), "detalhe": c.get("detalhe"),
            "divergentes": list(c.get("divergentes") or [])}


def _dispositivo(r: dict, origem: str, conf: dict, pontos=None) -> dict:
    return {"id": r["id"], "rotulo": r["rotulo"], "norma_id": r["norma_id"], "artigo": r["artigo"],
            "texto": r["texto"][:MAX_TEXTO], "contexto": (r.get("contexto") or "")[:400],
            "situacao": r["situacao"], "notas": list(r.get("notas") or [])[:4],
            "conflito": bool(r.get("conflito")),
            "conferencia": "divergente" if r["id"] in conf["divergentes"] else conf["status"],
            "origem": origem, **({"pontuacao": pontos} if pontos is not None else {})}


def consultar_legislacao(pergunta: str, contexto_da_acao: dict | None = None, *, fundamentos=(),
                         normas=None, k: int = 6, indice=None, conferencias=None, nomes=(),
                         texto_livre: bool = False, agora: datetime | None = None) -> dict:
    """Dispositivos pertinentes à ação, com fonte, versão e limitações.

    - `fundamentos`: [(norma_id, artigo)] que a regra da ação exige; vêm por busca exata
      no índice. Se um não estiver no índice, a consulta diz que faltou (nunca inventa).
    - `conferencias`: resultado das conferências oficiais gravadas no banco (opcional).
    """
    from agente.juridico.indice import carregar_indice
    agora = agora or datetime.now(timezone.utc)
    ind = indice or carregar_indice()
    normas_m = (ind.manifesto or {}).get("normas", {})
    contexto = _contexto_minimo(contexto_da_acao, nomes)
    p = sanitizar(pergunta, nomes)
    if texto_livre:                         # pergunta escrita por uma pessoa: nomes próprios também saem
        p = tirar_nomes_proprios(p, ind.idf)
        contexto = {k_: tirar_nomes_proprios(v, ind.idf) if isinstance(v, str) else v for k_, v in contexto.items()}
    limitacoes = []
    if parece_instrucao(p) or any(isinstance(v, str) and parece_instrucao(v) for v in contexto.values()):
        limitacoes.append("A pergunta trazia texto com cara de instrução; foi tratada só como termo de busca.")
    consulta = " ".join([p] + [str(v) for v in contexto.values() if isinstance(v, str)])

    confs = {nid: _conferencia(m, conferencias) for nid, m in normas_m.items()}
    vazio = {"status": "nao_conferida", "divergentes": []}
    dispositivos, vistos, faltando = [], set(), []
    for norma_id, artigo in fundamentos:
        regs = ind.artigo(norma_id, artigo)
        if not regs:
            faltando.append(f"{norma_id} art. {artigo}")
            continue
        for r in regs:
            if r["id"] not in vistos and (r["caminho"] == "caput" or r["situacao"] in ("vigente", "desatualizado")):
                vistos.add(r["id"])
                dispositivos.append(_dispositivo(r, "fundamento", confs.get(norma_id, vazio)))
    for r, pontos, _ in ind.buscar(consulta, k=k, normas=normas):
        if r["id"] not in vistos:
            vistos.add(r["id"])
            dispositivos.append(_dispositivo(r, "busca", confs.get(r["norma_id"], vazio), pontos))

    if not ind.docs:
        limitacoes.append("O índice jurídico está vazio: nada foi consultado.")
    elif not dispositivos:
        limitacoes.append("Nenhum dispositivo pertinente encontrado. Isso não quer dizer que a ação é permitida.")
    if faltando:
        limitacoes.append("Fundamentos esperados que não estão no índice: " + ", ".join(faltando) + ".")
    usadas = sorted({d["norma_id"] for d in dispositivos})
    fontes = []
    for nid in usadas:
        m = normas_m.get(nid, {})
        c = confs.get(nid, vazio)
        fontes.append({"norma_id": nid, "norma": m.get("titulo") or nid, "sigla": m.get("sigla"),
                       "versao_texto": m.get("versao_texto"), "arquivo": m.get("arquivo"),
                       "commit": m.get("commit"), "url_repositorio": m.get("url_repositorio"),
                       "url_oficial": m.get("url_oficial"), "fonte_original": m.get("fonte_original"),
                       "conferencia": c["status"], "conferido_em": c.get("em"),
                       "aplica_se": m.get("aplica_se") or None})
        if c["status"] == "nao_conferida":
            limitacoes.append(f"{m.get('sigla') or nid}: redação e vigência não conferidas na fonte oficial "
                              f"({c.get('detalhe') or 'sem conferência'}).")
        elif c["status"] == "divergente":
            limitacoes.append(f"{m.get('sigla') or nid}: há dispositivos com redação diferente da fonte oficial.")
        if str(m.get("versao_texto") or "").startswith(("original", "publicação original")):
            limitacoes.append(f"{m.get('sigla') or nid}: o acervo traz o texto original; pode haver alterações "
                              "posteriores não incorporadas.")
        if m.get("aplica_se"):
            limitacoes.append(f"{m.get('sigla') or nid}: aplica-se a {m['aplica_se']}.")
    for d in dispositivos:
        if d["situacao"] == "desatualizado":
            limitacoes.append(f"{d['rotulo']}: texto do acervo desatualizado. {d['notas'][-1] if d['notas'] else ''}".strip())
        if d["conflito"]:
            limitacoes.append(f"{d['rotulo']}: há versões conflitantes deste dispositivo no acervo.")
    limitacoes.append(LIMITE_ESCOPO)
    limitacoes.append("Resultado de busca e regra interna, não parecer jurídico.")
    return {"pergunta": p, "contexto_da_acao": contexto, "dispositivos": dispositivos, "fontes": fontes,
            "limitacoes": list(dict.fromkeys(limitacoes)), "fundamentos_ausentes": faltando,
            "indice": {"versao": ind.versao, "commit": (ind.manifesto or {}).get("commit"),
                       "gerado_em": (ind.manifesto or {}).get("gerado_em")},
            "consultado_em": agora.isoformat()}
