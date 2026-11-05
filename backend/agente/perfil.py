"""Perfil de comportamento do cliente, para orientar a conversa.

Lê o que o sistema já guarda do caso (leituras da Triagem, mensagens do
cliente, propostas e acordo) e devolve cinco traços numa régua de 0 a 100,
com o "antes" e o "agora", mais o que costuma funcionar com essa pessoa.

Regras de cuidado (LGPD, art. 11 e 20):
- é orientação de conversa, não diagnóstico nem decisão automática;
- não usa nem mostra dado sensível (saúde, religião, política, origem);
  o sinal de "sofrimento_grave" da Triagem fica de fora de propósito;
- não guarda texto do cliente: o texto só é lido aqui, na hora, para contar
  tamanho e algumas palavras de aperto financeiro;
- cada traço diz de onde veio, para a pessoa da equipe poder discordar.

Função pura: recebe o caso e as mensagens, não toca no banco.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

AVISO = ("Orientação de conversa feita a partir das mensagens e do histórico. "
         "Não é diagnóstico e não decide nada sozinha.")

# Quanto cada emoção lida pela Triagem pesa na régua calmo → tenso.
_TENSAO = {"calmo": 15, "triste": 55, "ansioso": 65, "irritado": 85, "desesperado": 90}
# Quanto cada intenção mostra de vontade de resolver.
_VONTADE = {"pagar_negociar": 82, "ja_paguei": 70, "duvida": 55, "pedir_pessoa": 50,
            "outro": 45, "contestar": 32, "parar_contato": 10}
_APERTO = ("desempreg", "sem dinheiro", "nao tenho como", "nao consigo pagar", "apertad",
           "parcel", "dividir", "recebo dia", "salario", "so tenho", "pouco dinheiro", "mais barato")

MIN_MENSAGENS = 2          # abaixo disso, ainda não dá para dizer nada honesto


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _data(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m")
    except (TypeError, ValueError):
        return ""


def _limitar(v: float) -> int:
    return int(round(max(0, min(100, v))))


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _tamanho(msgs: list) -> int | None:
    if not msgs:
        return None
    media = sum(len((m.get("texto") or "").strip()) for m in msgs) / len(msgs)
    # 20 caracteres ≈ bem direto; 300 ≈ explica bastante.
    return _limitar((media - 20) / 280 * 100)


def calcular(caso: dict | None, mensagens: list | None) -> dict:
    d = (caso or {}).get("dados") or {}
    entrada = [m for m in (mensagens or []) if m.get("direcao") == "entrada" and (m.get("texto") or "").strip()]
    leituras = list(d.get("leituras") or [])
    if not leituras and d.get("leitura"):
        leituras = [d["leitura"]]
    neg = d.get("negociacao") or {}
    eventos = neg.get("eventos") or []
    propostas = sum(e.get("tipo") == "oferta_apresentada" for e in eventos)
    aceitos = sum(e.get("tipo") == "acordo_aceito" for e in eventos)

    base = {"mensagens_do_cliente": len(entrada), "leituras": len(leituras), "propostas": propostas,
            "desde": (entrada[0].get("criado_em") if entrada else None)}
    if len(entrada) < MIN_MENSAGENS and not leituras:
        faltam = MIN_MENSAGENS - len(entrada)
        return {"pronto": False, "aviso": AVISO, "base": base,
                "falta": f"O perfil aparece depois de {_plural(faltam, 'resposta', 'respostas')} do cliente."}

    primeira, ultima = (leituras[0], leituras[-1]) if leituras else ({}, {})
    fonte_leitura = (f"leitura da Triagem de {_data(ultima.get('quando'))}" if ultima.get("quando")
                     else "leitura da Triagem")
    tracos = []

    # 1. Como está agora: calmo → tenso
    agora_h = _TENSAO.get(ultima.get("emocao"))
    antes_h = _TENSAO.get(primeira.get("emocao")) if len(leituras) > 1 else None
    if agora_h is not None:
        tracos.append({"id": "humor", "nome": "Como está agora", "esquerda": "calmo", "direita": "tenso",
                       "agora": agora_h, "antes": antes_h,
                       "fontes": [fonte_leitura] + ([f"comparado com {_plural(len(leituras), 'leitura', 'leituras')}"]
                                                    if antes_h is not None else [])})

    # 2. Jeito de falar: direto → explica bastante
    if entrada:
        meio = len(entrada) // 2
        agora_t = _tamanho(entrada[meio:] if len(entrada) >= 4 else entrada)
        antes_t = _tamanho(entrada[:meio]) if len(entrada) >= 4 else None
        tracos.append({"id": "fala", "nome": "Jeito de falar", "esquerda": "curto e direto", "direita": "explica bastante",
                       "agora": agora_t, "antes": antes_t,
                       "fontes": [f"tamanho de {_plural(len(entrada), 'mensagem', 'mensagens')} do cliente"]})

    # 3. Confiança: desconfiado → confia
    conf, fontes_c = 50, []
    if d.get("identidade_ok"):
        conf += 20; fontes_c.append("confirmou quem é")
    contestou = [l for l in leituras if l.get("intencao") == "contestar"]
    if contestou:
        conf -= 25; fontes_c.append(f"contestou a dívida em {_plural(len(contestou), 'mensagem', 'mensagens')}")
    if aceitos:
        conf += 15; fontes_c.append("aceitou um acordo")
    antes_c = 50 if fontes_c else None
    tracos.append({"id": "confianca", "nome": "Confiança", "esquerda": "desconfiado", "direita": "confia",
                   "agora": _limitar(conf), "antes": antes_c,
                   "fontes": fontes_c or ["ainda sem sinal claro: começa no meio"]})

    # 4. Vontade de resolver: evita → quer resolver
    agora_v = _VONTADE.get(ultima.get("intencao"))
    if aceitos:
        agora_v = max(agora_v or 0, 90)
    antes_v = _VONTADE.get(primeira.get("intencao")) if len(leituras) > 1 else None
    if agora_v is not None:
        tracos.append({"id": "vontade", "nome": "Vontade de resolver", "esquerda": "evita", "direita": "quer resolver",
                       "agora": agora_v, "antes": antes_v,
                       "fontes": [fonte_leitura] + (["acordo aceito"] if aceitos else [])})

    # 5. Aperto financeiro: com folga → apertado
    textos = [_sem_acento(m.get("texto") or "") for m in entrada]
    citou = sum(any(p in t for p in _APERTO) for t in textos)
    aperto, fontes_a = 40, []
    if citou:
        aperto += min(40, 18 * citou); fontes_a.append(f"falou de dinheiro curto em {_plural(citou, 'mensagem', 'mensagens')}")
    if propostas >= 2 and not aceitos:
        aperto += 15; fontes_a.append(f"{propostas} propostas sem aceite")
    parcelas = int((((d.get("acordo") or {}).get("condicoes") or {}).get("n_parcelas") or 0))
    if parcelas >= 6:
        aperto += 15; fontes_a.append(f"acordo em {parcelas}x")
    if fontes_a:
        tracos.append({"id": "aperto", "nome": "Aperto financeiro", "esquerda": "com folga", "direita": "apertado",
                       "agora": _limitar(aperto), "antes": None, "fontes": fontes_a})

    por_id = {t["id"]: t["agora"] for t in tracos}
    funciona, evitar, move = [], [], []
    if por_id.get("humor", 0) >= 60:
        funciona.append("Frases curtas e calmas, uma coisa por vez.")
        evitar.append("Cobrar resposta imediata ou repetir o valor em tom de pressão.")
    if "fala" in por_id:
        if por_id["fala"] <= 35:
            funciona.append("Ir direto ao valor, à data e ao próximo passo.")
            evitar.append("Mensagens longas com muita explicação.")
        elif por_id["fala"] >= 65:
            funciona.append("Responder ponto a ponto o que ele trouxe.")
    if por_id.get("confianca", 50) <= 40:
        funciona.append("Explicar de onde vem a dívida e quem está falando antes de propor.")
        evitar.append("Pedir pagamento antes de tirar a dúvida.")
    if por_id.get("vontade", 0) >= 70:
        funciona.append("Propor uma opção concreta já, com data.")
        move.append("Resolver logo e tirar isso da frente.")
    if por_id.get("aperto", 0) >= 60:
        funciona.append("Entrada baixa e parcelas que caibam no mês.")
        evitar.append("Começar pela oferta à vista.")
        move.append("Caber no orçamento do mês.")
    if ultima.get("urgencia") == "alta":
        move.append("Resolver antes de um prazo que preocupa (negativação, vencimento).")
    if ultima.get("intencao") == "pedir_pessoa":
        funciona.append("Oferecer falar com alguém da equipe.")
    if not move:
        move.append("Ainda não está claro. Pergunte o que é mais importante para ele agora.")

    return {"pronto": True, "aviso": AVISO, "base": base, "frase": _frase(por_id),
            "tracos": tracos, "funciona": funciona[:4], "evitar": evitar[:3], "move": move[:3]}


def _frase(t: dict) -> str:
    partes = []
    if t.get("humor", 0) >= 60:
        partes.append("está tenso")
    elif "humor" in t:
        partes.append("está calmo")
    if t.get("vontade", 0) >= 70:
        partes.append("quer resolver")
    elif "vontade" in t and t["vontade"] <= 35:
        partes.append("está evitando o assunto")
    if t.get("aperto", 0) >= 60:
        partes.append("o dinheiro está curto")
    if t.get("confianca", 50) <= 40:
        partes.append("ainda desconfia")
    if not partes:
        return "Ainda há pouco para dizer. Siga a conversa e o perfil se completa."
    texto = ", ".join(partes[:-1]) + (" e " if len(partes) > 1 else "") + partes[-1]
    return texto[0].upper() + texto[1:] + "."
