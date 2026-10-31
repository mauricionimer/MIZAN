"""Ponte entre o orquestrador e a base jurídica interna (agente/juridico).

- Import tardio: a base carrega o índice (e o scikit-learn) só na primeira consulta, ou
  no aquecimento ao subir o servidor (`aquecer`).
- Falha da base nunca libera nada: a decisão vira revisão humana.
- Decisões que dependem só da política da empresa (estratégia de contato, decisão
  automatizada) valem para todos os casos com a mesma política: são avaliadas e
  registradas uma vez (sem caso) e reaproveitadas por algumas horas.
- Nada daqui vai para a conversa com o devedor.
"""
import json
import threading
from datetime import datetime, timedelta, timezone

VALIDADE_EMPRESA = timedelta(hours=6)
BLOQUEIA = ("nao_prosseguir", "revisao_humana")
_CACHE = {}
_LOCK = threading.Lock()


def _agora(agora):
    return agora or datetime.now(timezone.utc)


def _falha(acao: str, erro: Exception) -> dict:
    # Sem dado pessoal: só o tipo do erro.
    print(f"[Jurídico] consulta falhou: {type(erro).__name__}")
    return {"acao": acao, "decisao": "revisao_humana", "condicoes": [], "dispositivos": [], "fontes": [],
            "justificativa": f"a consulta à base jurídica falhou ({type(erro).__name__}): revisão humana",
            "incertezas": ["consulta jurídica indisponível"], "fatos": {}, "consultado_em": None,
            "registro_id": None}


def avaliar_e_registrar(repo, empresa_id, caso_id, acao, fatos, trace_id=None, agora=None) -> dict:
    try:
        from agente.juridico.decisao import avaliar_e_registrar as _avaliar
        return _avaliar(repo, empresa_id, caso_id, acao, fatos, trace_id=trace_id, agora=agora)
    except Exception as e:
        return _falha(acao, e)


def _versao_indice() -> str | None:
    try:
        from agente.juridico.indice import carregar_indice
        return carregar_indice().versao
    except Exception:
        return None


def da_empresa(repo, empresa_id, acao, fatos, trace_id=None, agora=None) -> dict:
    """Decisão que vale para a empresa toda (mesma política, mesma versão do índice)."""
    agora = _agora(agora)
    chave = (empresa_id, acao, json.dumps(fatos, sort_keys=True, default=str), _versao_indice())
    with _LOCK:
        achado = _CACHE.get(chave)
        if achado and achado[0] > agora:
            return {**achado[1], "reaproveitada": True}
    d = avaliar_e_registrar(repo, empresa_id, None, acao, fatos, trace_id=trace_id, agora=agora)
    if d.get("consultado_em"):                     # falha técnica não fica guardada
        with _LOCK:
            _CACHE[chave] = (agora + VALIDADE_EMPRESA, d)
    return d


def limpar_cache() -> None:
    with _LOCK:
        _CACHE.clear()


# ── fatos mínimos, montados em código (nunca do texto da conversa) ──────────

def fatos_estrategia(regras: dict | None) -> dict:
    """Como o agente procura as pessoas, pela política da empresa."""
    r = regras or {}
    return {"contata_terceiros": False,              # o agente só escreve para o próprio devedor
            "conteudo_com_ameaca": False,            # as travas de saída barram ameaça e constrangimento
            "identifica_credor": True,               # a abertura diz o nome da empresa
            "horario_inicio": r.get("hora_inicio"), "horario_fim": r.get("hora_fim"),
            "dias_semana": list(r.get("dias_semana") or []) if regras else None,
            "frequencia_semanal_max": r.get("contatos_semana_max"),
            "canais": ["telegram", "chat"]}


def fatos_decisao_automatizada(regras: dict | None) -> dict:
    """O Estrategista escolhe tom e oferta inicial sozinho, dentro da política."""
    return {"revisao_humana_disponivel": True,       # a pessoa pode pedir uma pessoa a qualquer momento
            "criterios_explicaveis": regras is not None,   # critérios = política versionada + grupos do plano
            "usa_dado_sensivel": False,              # a decisão usa dívida, atraso e histórico de contato
            "uso": "tom_e_oferta_inicial"}


def revisar_politica(repo, empresa_id: str, regras: dict | None, agora=None) -> list:
    """As duas decisões de nível empresa, para o plano do dia."""
    return [da_empresa(repo, empresa_id, "estrategia_cobranca", fatos_estrategia(regras), agora=agora),
            da_empresa(repo, empresa_id, "decisao_automatizada_credito", fatos_decisao_automatizada(regras),
                       agora=agora)]


def resumo(d: dict) -> dict:
    """O que a tela da operação mostra de uma decisão (sem os fatos)."""
    return {k: d.get(k) for k in ("acao", "acao_descricao", "decisao", "condicoes", "justificativa",
                                  "consultado_em", "registro_id")}


def aquecer() -> None:
    """Carrega o índice e prepara a busca semântica em segundo plano (a primeira consulta fica rápida)."""
    def _rodar():
        try:
            from agente.juridico.indice import carregar_indice
            ind = carregar_indice()
            ind.buscar("tratamento de dados pessoais", k=1)
        except Exception as e:
            print(f"[Jurídico] aquecimento falhou: {type(e).__name__}")
    threading.Thread(target=_rodar, name="juridico-aquecer", daemon=True).start()


# ── para as rotas de administrador (main.py: /agente/juridico/...) ───────────

def fontes(repo) -> dict:
    """Normas do índice com origem, versão do texto, commit e a conferência mais recente."""
    from agente.juridico import catalogo, registro
    from agente.juridico.consulta import LIMITE_ESCOPO, _conferencia
    from agente.juridico.indice import carregar_indice
    ind = carregar_indice()
    m = ind.manifesto or {}
    overlay = registro.conferencias(repo)
    normas = []
    for nid, n in (m.get("normas") or {}).items():
        c = _conferencia(n, overlay)
        normas.append({"norma_id": nid, "norma": n.get("titulo"), "sigla": n.get("sigla"),
                       "versao_texto": n.get("versao_texto"), "arquivo": n.get("arquivo"),
                       "url_repositorio": n.get("url_repositorio"), "url_oficial": n.get("url_oficial"),
                       "commit": n.get("commit"), "dispositivos": n.get("dispositivos"),
                       "aplica_se": n.get("aplica_se") or None, "conferencia": c["status"],
                       "conferido_em": c.get("em"), "detalhe_conferencia": c.get("detalhe"),
                       "divergentes": len(c.get("divergentes") or [])})
    return {"indice": {"versao": ind.versao, "commit": m.get("commit"), "gerado_em": m.get("gerado_em"),
                       "acervo": m.get("acervo"), "registros": len(ind.registros), "buscaveis": len(ind.docs)},
            "normas": normas, "descartadas": [{"norma": d[0], "motivo": d[1]} for d in catalogo.DESCARTADAS],
            "limite": LIMITE_ESCOPO}


def consultar(repo, pergunta: str, contexto: dict | None = None) -> dict:
    """consultar_legislacao para o administrador (a pergunta passa pela mesma limpeza)."""
    from agente.juridico import registro
    from agente.juridico.consulta import consultar_legislacao
    return consultar_legislacao(pergunta, contexto, conferencias=registro.conferencias(repo), texto_livre=True)


def conferir_fontes(repo, buscar=None, agora=None) -> dict:
    """Confere cada norma na fonte oficial e grava o resultado (vale para as próximas decisões)."""
    from agente.juridico import conferencia, registro
    from agente.juridico.indice import carregar_indice
    ind = carregar_indice()
    saida = {}
    for nid, m in ((ind.manifesto or {}).get("normas") or {}).items():
        regs = [r for r in ind.registros if r["norma_id"] == nid]
        res = conferencia.conferir(m, regs, buscar=buscar, agora=agora)
        res["sha256_arquivo"] = m.get("sha256_arquivo")        # vale só para esta versão do texto
        res["indice_versao"] = ind.versao
        try:
            repo.gravar_conferencia_juridica(nid, res)
        except Exception as e:
            print(f"[Jurídico] conferência de {nid} não gravada: {type(e).__name__}")
        saida[nid] = {"status": res["status"], "em": res.get("em"), "detalhe": res.get("detalhe"),
                      "verificados": res.get("verificados"), "divergentes": len(res.get("divergentes") or [])}
    registro.esquecer_conferencias()
    limpar_cache()                       # decisões de empresa refeitas com a conferência nova
    return saida


_CONFERINDO = {"rodando": False, "ultimo": None}


def conferir_em_segundo_plano(repo) -> dict:
    """A conferência baixa as páginas oficiais (pode levar alguns minutos): roda à parte."""
    with _LOCK:
        if _CONFERINDO["rodando"]:
            return {"iniciada": False, "motivo": "uma conferência já está em andamento"}
        _CONFERINDO["rodando"] = True

    def _rodar():
        try:
            _CONFERINDO["ultimo"] = {"resultado": conferir_fontes(repo), "em": _agora(None).isoformat()}
        except Exception as e:
            _CONFERINDO["ultimo"] = {"erro": type(e).__name__, "em": _agora(None).isoformat()}
        finally:
            _CONFERINDO["rodando"] = False
    threading.Thread(target=_rodar, name="juridico-conferir", daemon=True).start()
    return {"iniciada": True}


def estado_conferencia() -> dict:
    return {"rodando": _CONFERINDO["rodando"], "ultimo": _CONFERINDO["ultimo"]}
