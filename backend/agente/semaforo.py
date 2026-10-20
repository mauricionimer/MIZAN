"""Semáforo do devedor: branco, amarelo ou vermelho (a cor da pasta na tela).

- branco:   sem pendência (ainda não foi acionado, ou está tranquilo)
- amarelo:  em andamento (contato, negociação, acordo, lembrete) ou atenção moderada
- vermelho: precisa de atenção agora (urgência, contestação, acordo atrasado ou quebrado,
            pessoa irritada ou desesperada, risco, pedido de uma pessoa)

Duas fontes, como no resto dos agentes:
- o piso vem de REGRAS em código, a partir da situação do caso e do que a Triagem
  leu da última mensagem. A IA nunca baixa a cor abaixo dele;
- a Triagem (IA) também classifica a cor a cada mensagem e pode subir a cor acima
  do piso (ex.: o devedor ameaça acionar o Procon).
A cor final é a mais alta das duas, e o motivo é o da fonte que decidiu. A leitura
da IA vale por `VALIDADE_IA_DIAS`; depois disso só as regras mandam. O caso quitado
é sempre branco.
"""
from datetime import datetime, timedelta, timezone

from agente import guardrails

CORES = ("branco", "amarelo", "vermelho")
ORDEM = {c: i for i, c in enumerate(CORES)}
VALIDADE_IA_DIAS = 14
VALIDADE_LEITURA_DIAS = 7

ROTULO = {"branco": "Sem pendência", "amarelo": "Em andamento", "vermelho": "Urgente"}

# situação do caso → (cor mínima, motivo)
_PISO_SITUACAO = {
    "novo": ("branco", "ainda não foi acionado"),
    "quitado": ("branco", "dívida quitada"),
    "so_lembrete": ("amarelo", "recebendo lembretes"),
    "em_contato": ("amarelo", "em contato com o agente"),
    "negociando": ("amarelo", "negociação em andamento"),
    "acordo_ativo": ("amarelo", "acordo em andamento"),
    "pagamento_em_conferencia": ("amarelo", "pagamento em conferência"),
    "suspenso": ("amarelo", "pediu para parar o contato"),
    "atrasado": ("vermelho", "acordo atrasado"),
    "quebrado": ("vermelho", "acordo quebrado"),
    "contestado": ("vermelho", "contestação aberta"),
    "com_pessoa": ("amarelo", "com a equipe"),
}


def cor_valida(valor) -> str | None:
    v = str(valor or "").strip().lower()
    return v if v in CORES else None


def _quando(valor):
    try:
        d = datetime.fromisoformat(str(valor))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _recente(valor, dias: int, agora: datetime) -> bool:
    q = _quando(valor)
    return q is not None and agora - q <= timedelta(days=dias)


def piso(caso: dict, agora: datetime) -> tuple:
    """(cor, motivo) que só o código decide, sem IA."""
    d = caso.get("dados") or {}
    cor, motivo = _PISO_SITUACAO.get(caso.get("situacao"), ("branco", "sem pendência"))
    if caso.get("situacao") == "quitado":
        return cor, motivo
    achados = [(cor, motivo)]
    if caso.get("situacao") == "com_pessoa":
        from agente import passagem
        f = passagem.para_tela(d.get("passagem"), agora)
        if f and f.get("nivel") == "urgente":
            achados.append(("vermelho", "caso urgente com a equipe"))
    lei = d.get("leitura") or {}
    if lei and _recente(lei.get("quando"), VALIDADE_LEITURA_DIAS, agora):
        sinais = set(lei.get("sinais") or [])
        if "sofrimento_grave" in sinais:
            achados.append(("vermelho", "sinal de sofrimento grave"))
        if lei.get("emocao") == "desesperado":
            achados.append(("vermelho", "devedor desesperado"))
        if lei.get("emocao") == "irritado" or "agressividade" in sinais:
            achados.append(("vermelho", "devedor irritado"))
        if lei.get("urgencia") == "alta":
            achados.append(("vermelho", "urgência alta"))
        if lei.get("intencao") in ("contestar", "pedir_pessoa"):
            achados.append(("vermelho", "contestou a dívida" if lei["intencao"] == "contestar" else "pediu uma pessoa"))
        if lei.get("emocao") in ("ansioso", "triste") or lei.get("urgencia") == "media":
            achados.append(("amarelo", "devedor " + (lei.get("emocao") if lei.get("emocao") in ("ansioso", "triste") else "com urgência média")))
    return max(achados, key=lambda a: ORDEM[a[0]])


def calcular(caso: dict, agora: datetime | None = None) -> dict:
    """A cor do caso agora: o maior entre o piso das regras e a leitura da IA."""
    agora = agora or datetime.now(timezone.utc)
    cor_r, motivo_r = piso(caso, agora)
    if caso.get("situacao") == "quitado":
        return {"cor": "branco", "motivo": motivo_r, "origem": "regra", "em": agora.isoformat()}
    lei = (caso.get("dados") or {}).get("leitura") or {}
    cor_ia = cor_valida(lei.get("semaforo")) if _recente(lei.get("quando"), VALIDADE_IA_DIAS, agora) else None
    if cor_ia and ORDEM[cor_ia] > ORDEM[cor_r]:
        motivo = guardrails.limpar_nota(lei.get("semaforo_motivo") or "avaliação do agente", 80)
        return {"cor": cor_ia, "motivo": motivo, "origem": "agente", "em": agora.isoformat()}
    return {"cor": cor_r, "motivo": motivo_r, "origem": "regra", "em": agora.isoformat()}


def atualizar(caso: dict, agora: datetime | None = None) -> dict:
    """Recalcula e grava em caso["dados"]["semaforo"]. Devolve o semáforo."""
    s = calcular(caso, agora)
    dados = dict(caso.get("dados") or {})
    dados["semaforo"] = s
    caso["dados"] = dados
    return s


def guardar_leitura(caso: dict, triagem: dict, agora: datetime | None = None) -> None:
    """Guarda o que a Triagem leu da última mensagem (sem texto do devedor)."""
    dados = dict(caso.get("dados") or {})
    dados["leitura"] = {
        "intencao": triagem.get("intencao"), "emocao": triagem.get("emocao"), "urgencia": triagem.get("urgencia"),
        "sinais": list(triagem.get("sinais_de_risco") or []),
        "semaforo": cor_valida(triagem.get("semaforo")),
        "semaforo_motivo": guardrails.limpar_nota(triagem.get("semaforo_motivo") or "", 80),
        "quando": (agora or datetime.now(timezone.utc)).isoformat(),
    }
    caso["dados"] = dados


def para_tela(caso: dict | None, agora: datetime | None = None) -> dict:
    """O semáforo atual do caso (recalculado, para a cor acompanhar o tempo). Sem caso: branco."""
    if not caso:
        return {"cor": "branco", "rotulo": ROTULO["branco"], "motivo": "ainda não foi acionado", "origem": "regra"}
    s = calcular(caso, agora)
    return {"cor": s["cor"], "rotulo": ROTULO[s["cor"]], "motivo": s["motivo"], "origem": s["origem"]}


def arquivos(caso: dict | None) -> list:
    """O que vai dentro da pasta: um papel por informação que o agente juntou."""
    if not caso:
        return [{"name": "Sem atendimento", "meta": "o agente ainda não atuou"}]
    d = caso.get("dados") or {}
    out = [{"name": "Situação", "meta": str(caso.get("situacao") or "").replace("_", " ")}]
    lei = d.get("leitura") or {}
    if lei:
        partes = [p for p in (lei.get("emocao"), f"urgência {lei['urgencia']}" if lei.get("urgencia") else None) if p]
        out.append({"name": "Última leitura", "meta": ", ".join(partes) or "triagem"})
    n = len(d.get("caderno") or [])
    if n:
        out.append({"name": "Caderno do caso", "meta": f"{n} anotaç{'ão' if n == 1 else 'ões'}"})
    if d.get("acordo"):
        out.append({"name": "Acordo", "meta": "em andamento" if caso.get("situacao") != "quitado" else "quitado"})
    if d.get("passagem"):
        out.append({"name": "Passagem p/ equipe", "meta": str((d["passagem"] or {}).get("motivo") or "").replace("_", " ")})
    return out[:4]
