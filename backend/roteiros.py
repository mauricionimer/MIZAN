"""F4 — roteiros de abordagem (docs/PLANO_OPERADOR.md).

Um roteiro é um texto com variáveis entre chaves, de um canal e, se quiser, de
uma oferta do catálogo. O servidor só valida; quem preenche é a tela, com os
dados do devedor e da proposta que ela já tem (frontend/src/utils/roteiros.js).
"""
import re

from model.bandit import OFERTAS

CANAIS = ("whatsapp", "sms", "email", "telefone")

# Nome da variável → o que ela vira. A mesma lista existe na tela.
VARIAVEIS = {
    "primeiro_nome": "primeiro nome do devedor",
    "nome": "nome completo do devedor",
    "valor_divida": "valor da dívida",
    "dias_atraso": "dias em atraso",
    "valor_proposta": "valor à vista da proposta (já com desconto)",
    "parcelas": "número de parcelas",
    "valor_parcela": "valor de cada parcela",
    "desconto": "desconto da proposta, em %",
    "empresa": "nome da empresa",
    "operador": "primeiro nome de quem envia",
}

TITULO_MIN, TITULO_MAX = 2, 80
TEXTO_MIN, TEXTO_MAX = 5, 2000

_VAR = re.compile(r"\{([^{}]*)\}")


def variaveis_do_texto(texto: str) -> list:
    return [m.strip() for m in _VAR.findall(texto or "")]


def validar(titulo: str, canal: str, oferta, texto: str) -> dict:
    """Campos limpos, ou ValueError com a mensagem para a tela."""
    titulo = (titulo or "").strip()
    texto = (texto or "").strip()
    if not TITULO_MIN <= len(titulo) <= TITULO_MAX:
        raise ValueError(f"O título precisa ter de {TITULO_MIN} a {TITULO_MAX} caracteres.")
    if canal not in CANAIS:
        raise ValueError("Canal inválido. Use: WhatsApp, SMS, e-mail ou ligação.")
    if oferta in ("", None):
        oferta = None
    elif oferta not in OFERTAS:
        raise ValueError("Oferta inválida.")
    if not TEXTO_MIN <= len(texto) <= TEXTO_MAX:
        raise ValueError(f"O texto precisa ter de {TEXTO_MIN} a {TEXTO_MAX} caracteres.")
    desconhecidas = sorted({v for v in variaveis_do_texto(texto) if v not in VARIAVEIS})
    if desconhecidas:
        raise ValueError("Variável desconhecida: " + ", ".join("{" + v + "}" for v in desconhecidas)
                         + ". Use os botões de variável.")
    return {"titulo": titulo, "canal": canal, "oferta": oferta, "texto": texto}


# Modelos do Mizan: valem enquanto a empresa não cadastra os dela. Só texto e
# variáveis — nenhum número fixo: valor, desconto e parcelas vêm da proposta.
_ESCRITO = {
    "avista_10pct": ("À vista com desconto",
                     "Olá, {primeiro_nome}! Aqui é {operador}, da {empresa}. Temos uma condição para você "
                     "quitar sua dívida de {valor_divida}: {valor_proposta} à vista, com {desconto} de desconto. "
                     "Posso te enviar o boleto?"),
    "desconto_30pct": ("Desconto especial à vista",
                       "Olá, {primeiro_nome}! Aqui é {operador}, da {empresa}. Liberamos uma condição especial "
                       "para encerrar sua dívida: de {valor_divida} por {valor_proposta} à vista ({desconto} de "
                       "desconto). Quer aproveitar?"),
    "parcelado_4x": ("Parcelado sem juros",
                     "Olá, {primeiro_nome}! Aqui é {operador}, da {empresa}. Você pode regularizar sua dívida em "
                     "{parcelas}x de {valor_parcela}, sem juros. Quer que eu gere a primeira parcela?"),
    "parcelado_12x": ("Parcelas que cabem no mês",
                      "Olá, {primeiro_nome}! Aqui é {operador}, da {empresa}. Para facilitar, sua dívida pode ser "
                      "paga em {parcelas}x de {valor_parcela}. Posso fechar esse acordo para você?"),
}
_FALA = {
    "avista_10pct": "Bom dia! Falo com {nome}? Aqui é {operador}, da {empresa}. Estou ligando sobre o débito de "
                    "{valor_divida}, em atraso há {dias_atraso} dias. Hoje consigo {valor_proposta} à vista, com "
                    "{desconto} de desconto. Podemos fechar?",
    "desconto_30pct": "Bom dia! Falo com {nome}? Aqui é {operador}, da {empresa}. Sobre o débito de {valor_divida}: "
                      "tenho uma condição especial, {valor_proposta} à vista, {desconto} de desconto. Fica bom para "
                      "o senhor ou a senhora?",
    "parcelado_4x": "Bom dia! Falo com {nome}? Aqui é {operador}, da {empresa}. Sobre o débito de {valor_divida}: "
                    "dá para parcelar em {parcelas}x de {valor_parcela}, sem juros. Qual dia do mês fica melhor?",
    "parcelado_12x": "Bom dia! Falo com {nome}? Aqui é {operador}, da {empresa}. Sobre o débito de {valor_divida}: "
                     "consigo {parcelas}x de {valor_parcela}. Esse valor cabe no seu orçamento?",
}


def padroes(canal: "str | None" = None) -> list:
    """Modelos do Mizan, um por oferta e canal."""
    saida = []
    for c in (CANAIS if canal is None else (canal,)):
        for oferta in OFERTAS:
            titulo, texto = _ESCRITO[oferta]
            if c == "telefone":
                texto = _FALA[oferta]
            saida.append({"id": f"padrao-{c}-{oferta}", "titulo": titulo, "canal": c, "oferta": oferta,
                          "texto": texto, "dono_id": None, "padrao": True})
    return saida
