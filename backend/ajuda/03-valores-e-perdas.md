# Valores, fases e perdas

## valor-de-face
titulo: Valor de face
perfis: operador, admin, comando
telas: Visão da carteira
perguntas:
- o que é valor de face
- como o valor de face é calculado
- valor de face é o que vou recuperar
- total em risco
- quanto devem no total os devedores
- valor total da carteira
curta: É a soma das dívidas da carteira, como vieram no arquivo. Não é o que se espera recuperar.
calculo: valor de face = soma de valor_divida de todos os devedores.
fazer: Use como o teto do que existe em aberto. O que se espera recuperar é o "valor esperado".
cuidado: É um dado do cliente; o sistema não corrige nem atualiza juros.
fontes:
- backend/main.py::_analisar_df
- frontend/src/pages/Dashboard.jsx::texto "Valor de Face"

## valor-esperado
titulo: Valor esperado de recuperação
perfis: operador, admin, comando
telas: Recuperabilidade; Visão da carteira
perguntas:
- o que é valor esperado
- como o valor esperado de recuperação é calculado
- quanto vou recuperar
- o valor esperado é garantido
- diferença entre valor esperado e valor de face
curta: É a média do que se espera recuperar de cada dívida: o valor da dívida vezes a taxa de recuperação prevista.
calculo: valor esperado = dívida × taxa de recuperação prevista. O total da carteira é a soma dos valores de cada devedor.
fazer: Use para comparar devedores e carteiras, não como promessa de caixa.
cuidado: É um valor esperado, ou seja, uma média. E depende da taxa, que hoje é uma premissa ou um modelo (veja "Taxa de recuperação").
fontes:
- backend/main.py::_analisar_df

## taxa-de-recuperacao
titulo: Taxa de recuperação prevista
perfis: admin, comando
telas: Precificação
perguntas:
- o que é taxa de recuperação
- de onde vem a taxa de recuperação
- o que é origem da taxa
- o que significa ML ativo
- o que significa premissa no selo
- por que aparece aviso de premissa
curta: É a fração da dívida que se espera recuperar. Vem de um modelo de preço, se já houver dados reais para treiná-lo; senão, de uma premissa declarada.
calculo: Com o modelo de preço treinado: a taxa é a que ele prevê (já inclui a chance de pagar, então não se multiplica de novo). Sem ele: taxa = probabilidade de pagamento × "recuperação se pagar". A origem aparece no selo da Precificação: "ML ativo" ou "Premissa".
fazer: Enquanto estiver em "Premissa", trate o valor esperado como estimativa de planejamento e registre os pagamentos para o modelo de preço poder ser treinado.
cuidado: O modelo de preço exige um mínimo de 15 pagamentos com predição ligada e 5 pagamentos reais com valor.
fontes:
- backend/main.py::_analisar_df
- backend/model/price_model.py::prever
constantes:
- backend/model/price_model.py::MIN_AMOSTRAS = 15
- backend/model/price_model.py::MIN_PAGAMENTOS = 5

## recuperacao-se-pagar
titulo: Recuperação se pagar (premissa)
perfis: admin, comando
telas: Precificação
perguntas:
- o que é recuperação se pagar
- quanto do saldo entra quando o devedor paga
- como mudar a premissa de recuperação
- por que a premissa é 100 por cento
- premissa de recuperação
- o devedor paga tudo ou só parte
curta: Quanto da dívida entra quando o devedor efetivamente paga. O padrão é 100%: pagou, pagou tudo.
calculo: Usada só quando o modelo de preço ainda não existe: taxa = probabilidade de pagamento × recuperação se pagar. Aceita valores entre 0 (exclusive) e 1.
fazer: Se a empresa costuma fechar acordos com desconto, informe um valor menor para o valor esperado refletir isso.
cuidado: O padrão 1,0 é uma premissa declarada, não uma medida. Hoje a configuração é gravada pela API; ainda não há tela para ela.
revisar: achado E1: as premissas da empresa (recuperação se pagar, comissão, cessão, critério da fila, buffer e teto de parcela) não têm tela.
fontes:
- backend/main.py::_premissa_recuperacao_se_pagar
constantes:
- backend/main.py::PREMISSA_RECUPERACAO_SE_PAGAR_PADRAO = 1.0

## valor-esperado-liquido
titulo: Valor esperado líquido (após comissão)
perfis: admin, comando
telas: Ciclo de cobrança
perguntas:
- o que é valor esperado líquido
- por que a fila usa o líquido
- como a comissão afeta a fila
- diferença entre bruto e líquido
- o líquido do ciclo e o líquido da precificação são a mesma coisa
curta: É o valor esperado depois de descontar a comissão que o banco paga na fase especializada. É o que ordena a fila.
calculo: Na fase especializada (31 a 360 dias): líquido = esperado × (1 − comissão%). Nas outras fases, e sem comissão informada, o líquido é igual ao bruto, e o sistema avisa.
fazer: Informe a comissão do contrato com o escritório de cobrança para a fila refletir o que sobra para o banco.
cuidado: Não é o "Valor Líquido" do simulador de precificação, que usa um custo de cobrança escolhido no controle deslizante. São dois conceitos com nomes parecidos.
revisar: achado D3: dois "líquidos" com nomes parecidos.
fontes:
- backend/model/ciclo.py::liquido
- backend/model/ciclo.py::custos_de_config

## fases-do-ciclo
titulo: Fases do ciclo de cobrança
perfis: admin, comando
telas: Ciclo de cobrança
perguntas:
- o que são as fases do ciclo de cobrança
- o que é fase administrativa
- o que é fase especializada
- o que é write-off
- em que fase está a dívida
- o que é fase preventiva
curta: Cada dívida está numa de quatro fases conforme os dias de atraso, e cada fase tem uma economia diferente.
calculo: Preventiva: antes do vencimento. Administrativa: de 0 a 30 dias, régua interna do banco. Especializada: de 31 a 360 dias, escritório terceirizado com comissão. Write-off: acima de 360 dias, perda reconhecida; a alternativa é vender a carteira. Os limites 30 e 360 pertencem à fase anterior.
fazer: Use a distribuição por fase para dimensionar equipe interna e terceirizada, e para identificar o que já deveria ser vendido.
cuidado: As fases e os limites vêm do material técnico de referência, não de um contrato específico do banco. O aging (faixas de 30 dias) é outra segmentação por tempo e não coincide exatamente com as fases.
fontes:
- backend/model/ciclo.py::fase_de
- backend/model/ciclo.py::FASES
constantes:
- backend/model/ciclo.py::FIM_ADMINISTRATIVA = 30
- backend/model/ciclo.py::FIM_ESPECIALIZADA = 360

## comissao-de-cobranca
titulo: Comissão de cobrança
perfis: admin, comando
telas: Ciclo de cobrança
perguntas:
- como informar a comissão
- qual a comissão do escritório
- por que aparece aviso de comissão não informada
- o valor esperado está bruto
- qual a comissão de mercado
curta: É o percentual que o banco paga ao escritório sobre o que é recuperado na fase especializada. Sem ele informado, o valor esperado dessa fase fica bruto.
calculo: Aceita qualquer valor de 0 a 100, conforme o contrato. A referência cita que o mercado pratica de 10% a 25%, mas esse intervalo não é aplicado por padrão.
fazer: Informe o percentual do seu contrato para a fila deixar de superestimar essas dívidas.
cuidado: O sistema não escolhe um número dentro da faixa por conta própria: aplicar uma taxa que ninguém informou erraria na direção que favorece o produto. Hoje a configuração é gravada pela API; ainda não há tela.
revisar: achado E1 (premissas sem tela).
fontes:
- backend/model/ciclo.py::aviso
constantes:
- backend/model/ciclo.py::COMISSAO_MERCADO = (10.0, 25.0)

## cessao-e-write-off
titulo: Cessão e "vale mais vender"
perfis: admin, comando
telas: Ciclo de cobrança
perguntas:
- o que é cessão
- o que significa vale mais vender
- quando vender a carteira
- o que é write-off e cessão
- quanto vale a carteira vendida
curta: Acima de 360 dias a alternativa a cobrar é vender a dívida a um fundo. A tela compara as duas opções e diz qual rende mais.
calculo: valor se vendida = valor de face × percentual de cessão (informado pela empresa). "Vale mais vender" quando esse valor é maior que o valor esperado líquido de continuar cobrando.
fazer: Considere ceder as faixas em que a comparação aponta "vale mais vender".
cuidado: Só aparece se o percentual de cessão estiver informado. A referência cita 2% a 5% do valor de face como faixa de mercado; não é aplicada por padrão.
fontes:
- backend/model/ciclo.py::valor_cessao
constantes:
- backend/model/ciclo.py::CESSAO_MERCADO = (2.0, 5.0)

## aging
titulo: Aging da carteira
perfis: operador, admin, comando
telas: Visão da carteira
perguntas:
- o que é aging
- quais são as faixas de aging
- por que o aging é diferente das fases
- como o aging é calculado
- envelhecimento da carteira
- faixa de dias de atraso
curta: É a quantidade de devedores em cada faixa de dias em atraso.
calculo: Faixas: 0 a 29, 30 a 59, 60 a 89, 90 a 179 e 180 ou mais dias. Cada devedor entra na faixa dos seus dias em atraso.
fazer: Use para ver o envelhecimento da carteira. Para decisões de custo, use as fases do ciclo.
cuidado: As faixas são escolha de projeto e não coincidem com as fases (por exemplo, o dia 30 cai em "30–59" no aging, mas na fase administrativa).
revisar: achado D7: fronteira do dia 30.
fontes:
- backend/main.py::_aging_label

## precificacao-simulador
titulo: Precificação: custo, retorno, preço sugerido e lucro
perfis: admin, comando
telas: Precificação
perguntas:
- como o preço sugerido de compra é calculado
- o que é preço sugerido
- como funciona o simulador de precificação
- o que é custo de cobrança no simulador
- o que é retorno alvo
- como o lucro final é calculado
- de onde vêm 25 por cento e 30 por cento
curta: Simula quanto pagar por uma carteira para atingir um retorno desejado, dado o que se espera recuperar e o custo de cobrar.
calculo: Líquido = valor esperado × (1 − custo%). Preço sugerido = líquido ÷ (1 + retorno%). Lucro = líquido − preço. Retorno = lucro ÷ preço. Taxa de recuperação estimada = valor esperado ÷ valor de face. O custo (5–50%, padrão 25) e o retorno (10–80%, padrão 30) são controles deslizantes.
fazer: Ajuste os dois controles para os números da sua operação e compare cenários. Os padrões servem só de ponto de partida.
cuidado: Os padrões 25% e 30% são escolha de projeto: não são do cliente nem do mercado. O cálculo usa o valor esperado bruto e é feito na tela, sem gravar nada.
revisar: achado D3 (dois "líquidos").
fontes:
- frontend/src/pages/Dashboard.jsx::texto "Preço Sugerido de Compra"
- frontend/src/pages/Dashboard.jsx::texto "Retorno Alvo"

## perda-esperada
titulo: Perda esperada, EAD e LGD
perfis: admin, comando
telas: Precificação
perguntas:
- o que é perda esperada
- o que é EAD
- o que é LGD
- o que é EL
- como a perda esperada é calculada
- qual número vai para a provisão
curta: É quanto da dívida não deve voltar. Em linguagem de risco: EAD é a exposição, LGD é a perda proporcional e EL é a perda esperada.
calculo: EAD = saldo devedor (é dado: a inadimplência já ocorreu). LGD = 1 − taxa de recuperação prevista, entre 0 e 1. Perda esperada (EL) = EAD − valor esperado de recuperação, que é igual a EAD × LGD. O LGD da carteira é ponderado pela dívida.
fazer: Leve a perda esperada para a conversa de provisão com a área de risco.
cuidado: Como o valor esperado depende da taxa (modelo ou premissa), a perda esperada herda essa limitação. Não é uma provisão contábil pronta.
fontes:
- backend/main.py::_analisar_df
