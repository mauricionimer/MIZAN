# Fila e prioridade

## fila-ordem
titulo: Como a fila é ordenada
perfis: operador, admin, comando
telas: Recuperabilidade
perguntas:
- como a fila é ordenada
- por que esse devedor está no topo
- por que o devedor com score baixo está primeiro
- a fila é ordenada pelo score
- o que é o rank
- qual a lógica do ranking
- por que o primeiro da fila não é quem tem a maior dívida
curta: A fila vai de quem rende mais para quem rende menos: valor esperado de recuperação, não score e não tamanho da dívida.
calculo: valor esperado = dívida × taxa de recuperação prevista. Na fase especializada (31 a 360 dias) desconta-se a comissão, se a empresa configurou uma. A fila ordena o valor esperado líquido, do maior para o menor, e o rank 1 é o topo.
fazer: Trabalhe de cima para baixo. O que está no topo é onde um contato rende mais, e a capacidade da equipe diz até onde vale ir (veja "Alcance da operação").
cuidado: Quem deve muito e paga pouco pode render mais que quem paga sempre e deve pouco; é por isso que o topo não coincide com o maior score. Com o modelo em dados simulados, a probabilidade é uma premissa (veja "O modelo está em dados simulados ou reais?").
fontes:
- backend/main.py::_analisar_df
- backend/model/priorizacao.py::ordenar
- backend/model/ciclo.py::liquido

## criterio-de-priorizacao
titulo: Critério da fila: valor esperado ou proporcional por região
perfis: admin, comando
telas: Recuperabilidade
perguntas:
- posso mudar o critério da fila
- o que é proporcional por grupo
- a fila trata as regiões de forma justa
- ordenar por valor esperado prejudica alguma região
- o que é equidade na fila
curta: O padrão maximiza a recuperação. A alternativa reparte o esforço entre as regiões na proporção do tamanho de cada uma, e recupera um pouco menos.
calculo: valor_esperado: ordena por dívida × taxa, sem olhar região. proporcional_por_grupo: dentro de cada UF vale o valor esperado, e a fila alterna as UFs de modo que, em qualquer ponto de corte, cada região apareça na proporção do seu tamanho.
fazer: É decisão de política da empresa, não do sistema. Antes de mudar, rode a análise de equidade e o backtest para ver o custo de cada critério.
cuidado: Ordenar por valor esperado tende a deixar para trás regiões de dívidas menores, mesmo quando pagam igual. Nenhum dos dois critérios é "o certo".
revisar: a configuração do critério (criterio_priorizacao) ainda não tem tela; hoje é gravada na configuração da empresa pela API.
fontes:
- backend/model/priorizacao.py::de_config
- backend/model/priorizacao.py::ordenar
constantes:
- backend/model/priorizacao.py::CRITERIO_PADRAO = "valor_esperado"

## prioridade-alta-media-baixa
titulo: Prioridade Alta, Média e Baixa
perfis: operador, admin, comando
telas: Recuperabilidade; Devedor
perguntas:
- o que significa prioridade alta
- como a prioridade é definida
- por que a prioridade é média
- o que é prioridade baixa
- prioridade é igual ao score
- quantos devedores são prioridade alta
curta: É a posição do devedor na fila: o quinto de cima é Alta, até a metade é Média, o resto é Baixa.
calculo: posição = rank ÷ total de devedores da carteira. Até 20% = Alta. Até 50% = Média. Acima disso = Baixa.
fazer: Foque nos Alta no ciclo. Os Média entram se sobrar capacidade.
cuidado: A prioridade vem da posição na fila, não do score. Os cortes 20% e 50% são escolha de projeto, pensados para a capacidade típica de uma operação, não uma regra de crédito. Filtrar a tabela não muda a prioridade de ninguém.
fontes:
- frontend/src/utils/prioridade.js::prioridadePorRank
constantes:
- frontend/src/utils/prioridade.js::CORTE_ALTA = 0.20
- frontend/src/utils/prioridade.js::CORTE_MEDIA = 0.50

## devedores-prioritarios
titulo: Devedores prioritários (card da visão da carteira)
perfis: operador, admin, comando
telas: Visão da carteira
perguntas:
- o que é devedores prioritários
- de onde vem o número de prioritários
- quantos devedores são prioritários
- como o card de prioritários é calculado
curta: É quantos devedores cabem na faixa Alta: um quinto da carteira.
calculo: devedores prioritários = piso de (total de devedores × 20%).
fazer: Use como tamanho de uma "meta de ciclo" inicial. Para saber até onde a sua equipe chega de verdade, use o Alcance da operação.
cuidado: Não é uma medida da carteira: é só o tamanho da faixa Alta, que é sempre 20% do total.
fontes:
- frontend/src/pages/Dashboard.jsx::texto "Devedores Prioritários"

## urgencia-do-devedor
titulo: Urgência (na página do devedor)
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é urgência
- diferença entre urgência e prioridade
- por que a urgência é baixa e a prioridade é alta
- como a urgência é calculada
curta: A urgência da página do devedor vem só do score: 70 ou mais é Alta, 40 a 69 é Média, abaixo de 40 é Baixa.
calculo: urgência = Alta se score ≥ 70; Média se score ≥ 40; senão Baixa.
fazer: Para decidir quem contatar primeiro, olhe a Prioridade e a posição na fila: elas consideram também o valor da dívida.
cuidado: Urgência e Prioridade são conceitos diferentes e podem discordar: um devedor com score 35 e dívida grande pode ser Prioridade Alta e Urgência Baixa.
revisar: achado D8: a urgência por score contradiz a lógica da fila; decisão pendente sobre unificar ou remover.
fontes:
- frontend/src/pages/DebtorDetail.jsx::texto "Urgência"

## alcance-da-operacao
titulo: Alcance da operação
perfis: operador, admin, comando
telas: Alcance da operação
perguntas:
- o que é o alcance da operação
- até onde a minha equipe chega na fila
- quanto vale o topo da fila que dá para trabalhar
- como informar a capacidade
- o que é capacidade de contatos
- quanto vou recuperar com a minha equipe
curta: Mostra até onde a fila chega com o número de contatos que a sua equipe consegue fazer no ciclo, e quanto esse topo vale.
calculo: Você informa a capacidade N: operadores × contatos por dia × dias úteis. O alcance soma o valor esperado de recuperação dos N primeiros da fila. "Do recuperável" é essa soma ÷ o valor esperado de toda a carteira, e "Vai até a posição" é o rank do N-ésimo. As linhas dentro do alcance aparecem marcadas na tabela.
fazer: Informe a capacidade real da equipe e leve o número para a reunião de planejamento. O valor fica guardado no seu navegador para a próxima vez.
cuidado: A soma usa o valor esperado bruto (sem a comissão da fase especializada), enquanto a fila é ordenada pelo líquido; com comissão configurada, as duas medidas podem divergir um pouco.
revisar: achado D5 do mapa do sistema.
fontes:
- frontend/src/utils/alcance.js::calcularAlcance
- backend/main.py::rota /carteiras/{carteira_id}/alcance

## filtros-da-fila
titulo: Busca e filtros da fila
perfis: operador, admin, comando
telas: Recuperabilidade
perguntas:
- como buscar um devedor
- como filtrar por produto
- como filtrar por estado
- como filtrar quem já pagou
- o que é o filtro de status
- por que filtrar não muda a prioridade
curta: Dá para buscar por nome ou CPF e filtrar por produto, UF, prioridade e situação do pagamento (pago, não pago, pendente).
calculo: A busca e os filtros são aplicados no servidor e a tabela mostra uma página de 50 por vez. "Pago" e "não pago" usam o feedback mais recente de cada CPF; "pendente" é quem ainda não tem feedback.
fazer: Use "pendente" para ver quem ainda não foi trabalhado.
cuidado: A prioridade é calculada sobre a carteira inteira, não sobre o que sobrou do filtro. Em carteiras com milhares de feedbacks, o filtro por situação do pagamento pode falhar por tamanho da consulta.
revisar: achado C6: o filtro de status envia uma lista de CPFs na consulta, que não aguenta milhares de itens.
fontes:
- backend/main.py::pagina_do_ranking
