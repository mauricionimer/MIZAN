"""
Dúvidas enviadas ao COMANDO: o que o servidor faz com o texto antes de gravar.

Quem pergunta cola o que tem na tela: "o devedor 123.456.789-09 está com nota 12,
por quê?". A tela pede para não colocar dado de cliente, mas pedir não basta, e
essa tabela é lida por outras pessoas. O servidor mascara o que tem cara de
dado pessoal ANTES de gravar, mesmo que a pessoa tenha ignorado o aviso.

O que é mascarado: CNPJ, CPF, e-mail, telefone e sequências longas de dígitos
(contrato, conta, cartão). O que NÃO dá para mascarar por regra é nome de
pessoa: a tela avisa, e a revisão da dúvida pelo COMANDO é a segunda barreira.
Números comuns da conversa ("30 dias", "score 85", "R$ 1.234,56") não são
tocados: o teste cobre isso.
"""

import re

# Ordem importa: o padrão mais específico primeiro, senão um CNPJ viraria um
# CPF e um pedaço de número.
_PADROES = (
    ("CNPJ", re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")),
    ("CPF", re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # telefone brasileiro: +55, DDD opcional, 8 ou 9 dígitos com hífen ou espaço opcional
    ("telefone", re.compile(r"(?<!\d)(?:\+?55[\s-]?)?(?:\(?\d{2}\)?[\s-]?)?9?\d{4}[\s-]?\d{4}(?!\d)")),
    ("número", re.compile(r"(?<!\d)\d{9,}(?!\d)")),
)


def mascarar_pii(texto: str) -> tuple:
    """(texto mascarado, quantas trocas). Idempotente: mascarar duas vezes não muda nada."""
    total = 0
    for rotulo, padrao in _PADROES:
        texto, n = padrao.subn(f"[{rotulo}]", texto)
        total += n
    return texto, total
