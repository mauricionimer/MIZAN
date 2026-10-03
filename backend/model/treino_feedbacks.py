"""
Treino do modelo de UMA empresa com os pagamentos registrados no próprio Mizan.

Substitui o retreino global (model/retrain.py) no agendador e no painel. Aquele
juntava os feedbacks de todas as empresas num modelo só, que passava a pontuar
todos os clientes, e o ativava sozinho (achado D1 do mapa do sistema). Aqui:

  - entram só as predições das carteiras da empresa e o pagamento ligado a
    elas. A empresa vem da carteira da predição, não do campo `empresa` do
    feedback, que em registros antigos guarda o nome de exibição;
  - o treino é o mesmo do arquivo histórico (treino_empresa.treinar), com as
    mesmas travas: mínimo de linhas e de cada resultado, validação no tempo,
    comparação com o modelo em uso na mesma fatia;
  - nada é ativado. A versão fica guardada para o COMANDO conferir e ativar.

As variáveis são as que a análise gravou na predição. O histórico de contatos,
que o retreino antigo usava, fica de fora: um contato com resultado
"pagamento confirmado" é a própria resposta e faria o modelo parecer melhor do
que é.
"""

import pandas as pd

ORIGEM = "feedbacks"
NOME = "pagamentos registrados no Mizan"
LOTE = 1000          # o PostgREST corta a resposta em mil linhas
ITENS_IN = 100       # 800 ids num in_ já estouraram a URL no Supabase real


def _paginar(construir) -> list:
    linhas, i = [], 0
    while True:
        parte = construir().order("id").range(i, i + LOTE - 1).execute().data or []
        linhas += parte
        if len(parte) < LOTE:
            return linhas
        i += LOTE


def _norm(empresa_id) -> str:
    return str(empresa_id or "").strip().lower()


def datasets(db, empresas=None) -> dict:
    """{empresa: (df, datas_dos_feedbacks)} das empresas pedidas (todas, se None).

    `df` vai direto para treino_empresa.treinar; `datas_dos_feedbacks` (uma por
    linha) servem para contar o que chegou desde o último treino.
    """
    alvo = {_norm(e) for e in empresas} if empresas is not None else None
    carteira_empresa = {}
    for c in _paginar(lambda: db.table("carteiras").select("id, empresa_id")):
        emp = _norm(c.get("empresa_id"))
        if emp and (alvo is None or emp in alvo):
            carteira_empresa[c["id"]] = emp
    if not carteira_empresa:
        return {}

    # Um pagamento por predição. Se em algum momento foi marcado como pago, conta
    # como pago (quem não pagou e pagou depois); entre iguais, vale o mais novo.
    por_predicao: dict = {}
    for f in _paginar(lambda: db.table("feedbacks").select("id, predicao_id, pagou, created_at")
                      .not_.is_("predicao_id", "null")):
        pid, atual = f.get("predicao_id"), por_predicao.get(f.get("predicao_id"))
        if not pid:
            continue
        if (atual is None
                or (f.get("pagou") and not atual.get("pagou"))
                or (bool(f.get("pagou")) == bool(atual.get("pagou"))
                    and (f.get("created_at") or "") > (atual.get("created_at") or ""))):
            por_predicao[pid] = f

    linhas: dict = {}
    ids = list(por_predicao)
    for i in range(0, len(ids), ITENS_IN):
        res = (db.table("predicoes")
               .select("id, carteira_id, produto, uf, status, valor_divida, dias_em_atraso, "
                       "renda_estimada, created_at")
               .in_("id", ids[i:i + ITENS_IN]).execute())
        for p in res.data or []:
            emp = carteira_empresa.get(p.get("carteira_id"))
            if not emp:
                continue                      # predição de outra empresa (ou de carteira apagada)
            f = por_predicao[p["id"]]
            linhas.setdefault(emp, []).append((
                {
                    "produto": p.get("produto"),
                    "uf": p.get("uf"),
                    "status": p.get("status"),
                    "valor_divida": p.get("valor_divida"),
                    "dias_em_atraso": p.get("dias_em_atraso"),
                    "renda_estimada": p.get("renda_estimada"),
                    "pagou": 1 if f.get("pagou") else 0,
                    # a data da análise: treina no que foi analisado antes, mede no depois
                    "data_referencia": str(p.get("created_at") or "")[:10] or None,
                },
                str(f.get("created_at") or ""),
            ))
    return {emp: (pd.DataFrame([r for r, _ in ls]), [d for _, d in ls]) for emp, ls in linhas.items()}


def ultimo_treino(empresa_id) -> "str | None":
    """Quando foi o último treino desta empresa com os pagamentos do Mizan."""
    from model import modelos_empresa as me
    datas = [v.get("criado_em") or "" for v in me.carregar_versoes(_norm(empresa_id)).get("versoes", [])
             if v.get("origem") == ORIGEM]
    return max(datas) if datas else None


def novos_desde(datas: list, desde: "str | None") -> int:
    return len(datas) if not desde else sum(1 for d in datas if d > desde)


def treinar(df: pd.DataFrame, empresa_id: str, usuario_email: str = "") -> dict:
    """Treina e guarda, inativo, o modelo da empresa com estes pagamentos."""
    from model import treino_empresa as te
    if df is None or df.empty:
        raise te.DadosInvalidos("Esta empresa ainda não tem pagamentos registrados ligados às suas análises.")
    conteudo = df.to_csv(index=False).encode()        # só para a impressão digital (SHA-256)
    return te.treinar(conteudo, NOME, _norm(empresa_id), usuario_email, df=df, origem=ORIGEM)


def treinar_empresa(db, empresa_id: str, usuario_email: str = "") -> dict:
    df, _ = datasets(db, [empresa_id]).get(_norm(empresa_id), (None, []))
    return treinar(df, empresa_id, usuario_email)
