"""Perguntas de avaliação da base do devedor, escritas à parte das `perguntas` da base.

Mede a busca como o devedor escreve de verdade: sem acento, curto, com gíria.
Uma pergunta aqui que também está na base não mede nada: o teste confere isso.
"""

# (pergunta, id esperado)
NO_ASSUNTO = [
    ("meu nome vai ficar sujo pra sempre?", "nome-negativado-prazo"),
    ("quantos anos fico com o nome no spc", "nome-negativado-prazo"),
    ("divida prescreve em 5 anos e some do serasa?", "nome-negativado-prazo"),
    ("negativação dura quanto tempo", "nome-negativado-prazo"),
    ("se eu quitar hoje meu nome limpa quando", "nome-sai-depois-de-pagar"),
    ("ja paguei tudo e continuo negativado no serasa", "nome-sai-depois-de-pagar"),
    ("em quantos dias tiram meu nome depois de pagar", "nome-sai-depois-de-pagar"),
    ("depois de pagar quem tira meu nome do spc", "nome-sai-depois-de-pagar"),
    ("vou ter algum comprovante que quitei?", "comprovante-de-pagamento"),
    ("quero recibo de quitação da divida", "comprovante-de-pagamento"),
    ("vcs vao ligar pro meu trabalho cobrando?", "cobranca-sem-constrangimento"),
    ("minha familia vai ficar sabendo da divida?", "cobranca-sem-constrangimento"),
    ("isso é ameaça? a cobrança pode me humilhar?", "cobranca-sem-constrangimento"),
    ("cobraram valor errado de mim", "cobranca-indevida"),
    ("me cobraram duas vezes, tenho direito ao dobro?", "cobranca-indevida"),
    ("a multa de atraso pode ser de quanto no maximo", "multa-por-atraso"),
    ("multa por atrasar a parcela tem limite?", "multa-por-atraso"),
    ("se eu adiantar parcela tem desconto nos juros", "pagamento-antecipado"),
    ("posso quitar antecipado?", "pagamento-antecipado"),
    ("que dados meus vocês têm guardado", "meus-dados-pessoais"),
    ("quero corrigir meu endereço no cadastro", "meus-dados-pessoais"),
    ("foi um robo que decidiu minha oferta?", "revisao-de-decisao-automatica"),
    ("quero que um humano revise a decisão do sistema", "revisao-de-decisao-automatica"),
    ("devo pra varios bancos e nao consigo pagar nenhum", "superendividamento"),
    ("tenho dividas demais, maiores que meu salario", "superendividamento"),
]

# Fora da base: a busca precisa responder "não sei".
FORA = [
    "posso pagar com bitcoin?",
    "qual a previsão do tempo amanhã",
    "vocês abrem no feriado?",
    "qual o telefone da agência",
    "me empresta mais dinheiro?",
    "quanto é minha dívida?",
    "aceito pagar dia 20",
    "oi tudo bem",
    "quero falar sobre futebol",
    "qual o seu nome?",
]
