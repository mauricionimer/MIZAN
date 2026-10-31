# Base de conhecimento do devedor

Fatos que o devedor pergunta e que não estão no caso dele. Lido por
`agente/conhecimento.py`; a ferramenta `consultar_base` do Negociador busca aqui.

Regras desta base:
- Só lei ou súmula, com o texto literal em `trecho` e o endereço oficial em `url`.
  Conferido no Planalto e no STJ em 16/10/2026.
- `resposta` é o que o agente pode dizer: frase simples, sem prometer o que a lei
  não promete, terminando com a fonte do jeito que o agente deve citar.
- Nada de regra própria de um banco aqui (prazo de baixa do acordo parcelado,
  formas de pagamento): isso muda por empresa e não é lei.
- Mudou um texto? Rode `python test_agente_conhecimento.py` (formato e qualidade
  da busca).

Formato de cada entrada (estrito: chave errada vira falha de teste):

    ## id-em-kebab-case
    titulo: Como a pergunta aparece na Central
    fonte: Lei e artigo, do jeito que o agente cita
    url: https://endereço oficial
    perguntas:
    - jeito de perguntar
    resposta: O que o agente pode dizer.
    trecho: Texto literal da lei ou súmula.
      Linhas recuadas em dois espaços continuam o campo.

## nome-negativado-prazo
titulo: Quanto tempo o nome fica negativado
fonte: CDC (Lei 8.078/1990), art. 43, § 1º; STJ, Súmula 323
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- quanto tempo meu nome fica sujo
- por quanto tempo fico negativado
- meu nome fica no serasa para sempre
- quando meu nome sai do spc sozinho
- a dívida caduca depois de cinco anos
- depois de quanto tempo a negativação acaba
- meu cpf fica restrito por quantos anos
- o nome fica negativado por anos
- a dívida prescreve e sai do cadastro
- depois de cinco anos meu nome limpa sozinho
resposta: O registro de uma dívida no cadastro de inadimplentes pode ficar no máximo cinco anos. Depois disso ele sai do cadastro, mas a dívida não deixa de existir por isso (CDC, art. 43, § 1º, e Súmula 323 do STJ).
trecho: CDC, art. 43, § 1º: "Os cadastros e dados de consumidores devem ser objetivos, claros,
  verdadeiros e em linguagem de fácil compreensão, não podendo conter informações negativas
  referentes a período superior a cinco anos." STJ, Súmula 323: "A inscrição do nome do devedor
  pode ser mantida nos serviços de proteção ao crédito até o prazo máximo de cinco anos,
  independentemente da prescrição da execução."

## nome-sai-depois-de-pagar
titulo: Quando o nome sai do cadastro depois de pagar
fonte: STJ, Súmula 548
url: https://arquivocidadao.stj.jus.br/index.php/sumula-548
perguntas:
- se eu pagar quando meu nome sai do serasa
- depois que eu quitar em quantos dias limpa meu nome
- paguei a dívida e meu nome continua sujo
- quanto tempo para tirar meu nome do spc depois do pagamento
- quem tira meu nome da lista de inadimplentes
- quitei e ainda estou negativado
- prazo para baixar a negativação depois de pagar tudo
- já quitei tudo e continuo com o nome sujo no serasa
- paguei tudo e o nome não limpou
- depois de pagar quanto tempo demora para sair do spc
resposta: Depois que a dívida é paga por inteiro, quem cobra tem até cinco dias úteis para pedir a retirada do seu nome do cadastro de inadimplentes (Súmula 548 do STJ). Em acordo parcelado, confirme com a equipe quando o pedido de retirada é feito.
trecho: STJ, Súmula 548: "Incumbe ao credor a exclusão do registro da dívida em nome do devedor no
  cadastro de inadimplentes no prazo de cinco dias úteis, a partir do integral e efetivo
  pagamento do débito."

## comprovante-de-pagamento
titulo: Direito ao comprovante de quitação
fonte: Código Civil (Lei 10.406/2002), art. 319
url: https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm
perguntas:
- vou receber um comprovante de que paguei
- tenho direito a recibo de quitação
- como provo que quitei a dívida
- quero um documento dizendo que não devo mais nada
- vocês mandam carta de quitação
- preciso de um papel provando o pagamento
- vou receber algum comprovante
- comprovante de quitação da dívida
resposta: Quem paga tem direito a receber a quitação, que é o comprovante de que a dívida foi paga (Código Civil, art. 319). Guarde também o comprovante de cada pagamento que fizer.
trecho: Código Civil, art. 319: "O devedor que paga tem direito a quitação regular, e pode reter o
  pagamento, enquanto não lhe seja dada."

## cobranca-sem-constrangimento
titulo: Como a cobrança pode ser feita
fonte: CDC (Lei 8.078/1990), art. 42
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- vocês vão ligar no meu trabalho
- vão contar para minha família que eu devo
- podem me cobrar na frente dos outros
- estão me ameaçando na cobrança isso pode
- a cobrança pode me expor
- tenho medo de passar humilhação por causa da dívida
- meus parentes vão saber da dívida
- vocês vão avisar meus familiares
- vão espalhar que estou devendo
resposta: Na cobrança, você não pode ser exposto ao ridículo nem passar por constrangimento ou ameaça (CDC, art. 42). Se isso acontecer, você pode registrar uma reclamação.
trecho: CDC, art. 42: "Na cobrança de débitos, o consumidor inadimplente não será exposto a ridículo,
  nem será submetido a qualquer tipo de constrangimento ou ameaça."

## cobranca-indevida
titulo: Cobrança de valor que não é devido
fonte: CDC (Lei 8.078/1990), art. 42, parágrafo único
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- me cobraram um valor errado
- paguei a mais o que eu faço
- estão cobrando uma coisa que eu não devo
- tenho direito a receber em dobro
- cobraram duas vezes a mesma parcela
- cobrança indevida devolve o dinheiro
resposta: Quem paga uma cobrança indevida tem direito a receber de volta o dobro do que pagou a mais, com correção e juros, a não ser que tenha sido um engano justificável (CDC, art. 42, parágrafo único). Se você acha que a cobrança está errada, eu registro para a equipe conferir.
trecho: CDC, art. 42, parágrafo único: "O consumidor cobrado em quantia indevida tem direito à
  repetição do indébito, por valor igual ao dobro do que pagou em excesso, acrescido de correção
  monetária e juros legais, salvo hipótese de engano justificável."

## multa-por-atraso
titulo: Limite da multa por atraso
fonte: CDC (Lei 8.078/1990), art. 52, § 1º
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- qual o valor máximo da multa por atraso
- quanto pode ser a multa de atraso
- a multa da parcela atrasada tem limite
- por que a multa está tão alta
- cobraram multa muito alta pelo atraso
resposta: Em compra a crédito ou financiamento, a multa por atraso de uma prestação não pode passar de 2% do valor da prestação (CDC, art. 52, § 1º). Juros pelo atraso são outra coisa e não entram nesse limite.
trecho: CDC, art. 52, § 1º: "As multas de mora decorrentes do inadimplemento de obrigações no seu
  termo não poderão ser superiores a dois por cento do valor da prestação."

## pagamento-antecipado
titulo: Pagar antes do vencimento
fonte: CDC (Lei 8.078/1990), art. 52, § 2º
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- posso adiantar as parcelas
- se eu pagar antes diminui o valor
- quero quitar antes do prazo tenho desconto
- adiantar o pagamento reduz os juros
- posso pagar tudo de uma vez antes de terminar
- antecipar a quitação da dívida
- pagamento antecipado tem redução
resposta: Você pode adiantar o pagamento, no todo ou em parte. Quando há juros embutidos, eles diminuem na proporção do que foi adiantado (CDC, art. 52, § 2º).
trecho: CDC, art. 52, § 2º: "É assegurado ao consumidor a liquidação antecipada do débito, total ou
  parcialmente, mediante redução proporcional dos juros e demais acréscimos."

## meus-dados-pessoais
titulo: Acesso e correção dos seus dados
fonte: LGPD (Lei 13.709/2018), art. 18
url: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
perguntas:
- quais dados vocês têm sobre mim
- quero ver as informações que vocês guardam de mim
- meu endereço cadastrado está errado quero corrigir
- como peço para corrigir meus dados
- onde vocês conseguiram meus dados
- quero saber o que vocês fazem com meus dados pessoais
resposta: Pela LGPD, você pode pedir a confirmação de que seus dados são tratados, o acesso a eles e a correção do que estiver incompleto, errado ou desatualizado, sem custo (LGPD, art. 18). Eu passo o pedido para a equipe responsável.
trecho: LGPD, art. 18: "O titular dos dados pessoais tem direito a obter do controlador, em relação aos
  dados do titular por ele tratados, a qualquer momento e mediante requisição: I - confirmação da
  existência de tratamento; II - acesso aos dados; III - correção de dados incompletos, inexatos ou
  desatualizados; [...]" § 5º: "O requerimento referido no § 3º deste artigo será atendido sem
  custos para o titular, nos prazos e nos termos previstos em regulamento."

## revisao-de-decisao-automatica
titulo: Revisão de decisão feita por sistema
fonte: LGPD (Lei 13.709/2018), art. 20
url: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
perguntas:
- quem decidiu minha proposta foi um robô
- quero que uma pessoa revise essa decisão
- a oferta foi calculada por computador
- não concordo com a decisão automática
- como foi decidido o desconto que vocês me ofereceram
- vocês usam inteligência artificial para decidir
resposta: Você tem direito a pedir a revisão de uma decisão tomada só por sistema e a receber informação clara sobre os critérios usados (LGPD, art. 20). Aqui, quem faz essa revisão é uma pessoa da equipe: posso passar o seu caso para ela agora mesmo.
trecho: LGPD, art. 20: "O titular dos dados tem direito a solicitar a revisão de decisões tomadas
  unicamente com base em tratamento automatizado de dados pessoais que afetem seus interesses,
  incluídas as decisões destinadas a definir o seu perfil pessoal, profissional, de consumo e de
  crédito ou os aspectos de sua personalidade." § 1º: "O controlador deverá fornecer, sempre que
  solicitadas, informações claras e adequadas a respeito dos critérios e dos procedimentos
  utilizados para a decisão automatizada, observados os segredos comercial e industrial."

## superendividamento
titulo: Muitas dívidas ao mesmo tempo
fonte: CDC (Lei 8.078/1990), art. 104-A
url: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm
perguntas:
- tenho muitas dívidas e não consigo pagar nenhuma
- estou superendividado o que eu faço
- devo para vários bancos ao mesmo tempo
- minhas dívidas somadas são maiores que meu salário
- existe algum jeito de juntar todas as dívidas num plano só
resposta: Se você é pessoa física e está superendividado, a lei permite pedir uma repactuação das dívidas: o juiz pode marcar uma audiência de conciliação com todos os credores para montar um plano de pagamento de até 5 anos, preservando o mínimo para viver (CDC, art. 104-A). Aqui eu posso ver condições para esta dívida que caibam no seu orçamento.
trecho: CDC, art. 104-A: "A requerimento do consumidor superendividado pessoa natural, o juiz poderá
  instaurar processo de repactuação de dívidas, com vistas à realização de audiência
  conciliatória, presidida por ele ou por conciliador credenciado no juízo, com a presença de
  todos os credores de dívidas previstas no art. 54-A deste Código, na qual o consumidor
  apresentará proposta de plano de pagamento com prazo máximo de 5 (cinco) anos, preservados o
  mínimo existencial, nos termos da regulamentação, e as garantias e as formas de pagamento
  originalmente pactuadas."
