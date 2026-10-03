# Pagamentos e resultados

## registrar-pagamento
titulo: Como registrar um pagamento (e quem pode)
perfis: operador, admin, comando
telas: Pagamentos
perguntas:
- como registrar um pagamento
- por que não consigo registrar pagamento
- quem pode confirmar um pagamento
- como marcar que o devedor pagou
- pagamento manual
- por que o operador não registra pagamento
- como importar pagamentos em lote
- como registro que o devedor pagou
- quem tem permissão para confirmar pagamentos
- como importo vários pagamentos por arquivo
curta: Só o administrador (e o COMANDO) registra pagamentos. O operador acompanha, e registra contatos na página do devedor.
calculo: O administrador registra de quatro jeitos: o botão "Confirmar pagamento" na linha da fila, o formulário da página Pagamentos, o arquivo em lote (colunas cpf e pagou, e opcionalmente valor_recuperado e data_pagamento) ou uma coluna pagou na própria carteira ou consulta de banco. Todo pagamento é ligado à predição do devedor na carteira da empresa.
fazer: Se você é operador e o devedor pagou, avise o administrador. Registre o contato na página do devedor para o histórico.
cuidado: Registrar contato como "Pagou" não confirma o pagamento da carteira: só o administrador confirma. Sem pagamentos registrados, o sistema não consegue aprender nem medir o próprio acerto.
fontes:
- backend/main.py::rota /feedback
- backend/main.py::rota /feedback/lote
- backend/main.py::rota /devedores/{cpf}/confirmar-pagamento

## escrita-de-volta
titulo: Escrita de volta no banco do cliente
perfis: admin, comando
telas: Análise
perguntas:
- o sistema escreve no meu banco de dados
- o que é write back
- escrita de volta
- o mizan altera minha base
- como ativar a atualização do status no banco
- o sistema altera dados no banco do cliente
- como atualizar a situação na minha base quando alguém paga
- o que é a opção de write back da conexão
curta: Por padrão a conexão é somente leitura. Se o administrador ativar, o Mizan atualiza uma coluna do banco do cliente quando um pagamento é registrado.
calculo: Com a opção ligada e uma coluna indicada, ao registrar um pagamento o Mizan grava nessa coluna o valor configurado para "pago" (padrão: pago), na tabela da consulta salva, para aquele CPF. O valor de "não pago" só é gravado se tiver sido configurado; sem ele, nada é alterado para quem não pagou. Vale a conexão mais recente da empresa que tenha a opção ligada.
fazer: Ative só se o banco do cliente autorizar escrita para o usuário da conexão e se a equipe de dados concordar.
cuidado: É uma ação que altera dados fora do Mizan. Fica desligada até alguém ligar.
fontes:
- backend/main.py::_writeback_pagamento

## como-o-sistema-aprende
titulo: Como o sistema aprende com os pagamentos
perfis: admin, comando
telas: Quem pagou
perguntas:
- como o sistema aprende
- para que serve registrar pagamento
- o que acontece com os pagamentos registrados
- o modelo é retreinado sozinho
- quando o modelo é atualizado
- por que preciso registrar os resultados
- o que acontece com os pagamentos que eu registro
- o modelo se atualiza sozinho com o tempo
- por que preciso registrar também quem não pagou
curta: Cada pagamento (ou não pagamento) registrado ensina três coisas: qual abordagem funciona, quanto se recupera de verdade e, com volume, um modelo novo.
calculo: (1) O aprendizado de abordagem (canal e oferta) é atualizado a cada resultado, por empresa. (2) Com pelo menos 15 pagamentos ligados à predição e 5 pagamentos reais com valor, treina-se o modelo de preço (taxa de recuperação). (3) Periodicamente, para cada empresa com pelo menos 30 pagamentos novos desde o último treino dela (padrão), o sistema treina uma versão nova do modelo DELA, só com os pagamentos dela. O treino exige 300 devedores com resultado e 30 de cada tipo, e a versão nasce inativa: só passa a pontuar quando o COMANDO confere as métricas e ativa.
fazer: Registre também quem NÃO pagou: sem os dois lados o modelo não aprende a separar. Uma carteira só com pagamentos positivos não ensina nada.
cuidado: Nada muda nas análises até o COMANDO ativar a versão nova. Os pagamentos de uma empresa nunca entram no modelo de outra.
fontes:
- backend/scheduler.py::verificar_e_retreinar
- backend/model/treino_feedbacks.py::treinar
- backend/model/price_model.py::treinar
constantes:
- backend/scheduler.py::MIN_NOVOS_PADRAO = 30
- backend/model/treino_empresa.py::MIN_LINHAS = 300
- backend/model/treino_empresa.py::MIN_POR_CLASSE = 30
- backend/model/price_model.py::MIN_AMOSTRAS = 15
- backend/model/price_model.py::MIN_PAGAMENTOS = 5

## quem-pagou
titulo: Quem pagou: taxa de pagamento por faixa de score
perfis: admin, comando
telas: Quem pagou
perguntas:
- o que é a tabela quem pagou
- o que são as faixas de score alta média baixa
- como o sistema mede se está acertando
- taxa de pagamento por faixa
- o score alto paga mais
- tabela de taxa de pagamento por faixa de score
- como vejo se as notas altas realmente pagam mais
- o que é a seção quem pagou
curta: Agrupa os pagamentos registrados por faixa de score e mostra qual fração de cada faixa pagou. Se o score funciona, a faixa Alta paga mais que a Baixa.
calculo: Faixas pelo score do devedor: Alta = 70 ou mais, Média = 40 a 69, Baixa = menos de 40. Taxa de pagamento = pagaram ÷ total de feedbacks da faixa.
fazer: Compare as faixas: a taxa deve cair de Alta para Baixa. Se não cai, o score não está ordenando bem para a sua base.
cuidado: Poucos pagamentos registrados dão taxas instáveis. Os cortes 70 e 40 são escolha de projeto. Esta tabela só considera quem teve feedback registrado.
fontes:
- backend/main.py::rota /performance

## acuracia-geral
titulo: Acurácia geral
perfis: admin, comando
telas: Quem pagou
perguntas:
- o que é a acurácia geral
- como a acurácia é calculada
- acurácia alta quer dizer que o modelo é bom
- por que a acurácia pode enganar
- qual o percentual de acerto do score
- como o sistema mede o acerto
- qual o percentual de acerto do score
- como a acurácia geral é calculada
- acurácia alta significa modelo bom
curta: É a fração dos pagamentos registrados em que o score "acertou": score de 40 ou mais para quem pagou, ou abaixo de 40 para quem não pagou.
calculo: acurácia = (score ≥ 40 e pagou, ou score < 40 e não pagou) ÷ total com score. O corte é 40.
fazer: Prefira o KS e o Gini do painel do COMANDO, que medem a separação sem depender de um corte.
cuidado: A acurácia depende do corte (40, escolha de projeto) e engana quando quase todos pagam ou quase ninguém paga: um modelo que sempre diz "paga" teria acurácia alta numa base em que 90% pagam.
fontes:
- backend/main.py::rota /performance

## pagamentos-registrados
titulo: Pagamentos registrados (lista)
perfis: operador, admin, comando
telas: Pagamentos registrados
perguntas:
- o que é a lista de pagamentos registrados
- onde vejo quem pagou
- quanto foi recuperado
- por que a lista mostra só alguns pagamentos
- onde vejo os pagamentos registrados
- histórico de pagamentos
- lista de quem já pagou com valores e datas
- onde acompanho o que foi registrado
- por que a lista mostra só os últimos pagamentos
curta: Lista os pagamentos e não pagamentos já registrados na carteira, com o valor recuperado, a data e quem registrou.
calculo: Lê os feedbacks ligados às predições da empresa, do mais recente para o mais antigo, e mostra até os 5.000 mais recentes.
fazer: Use para conferir o que a equipe já registrou antes de registrar de novo.
cuidado: Se houver mais de 5.000 registros, só os mais recentes aparecem.
fontes:
- backend/main.py::rota /performance/pagamentos
