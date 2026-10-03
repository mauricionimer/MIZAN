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
- qual a regra de ordenação da lista de devedores
- por que o primeiro da lista é esse
- a lista é ordenada pela nota ou pelo valor
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
- posso mudar a forma como a lista é ordenada
- como distribuir o esforço entre as regiões
- existe outra regra de ordenação da fila
curta: O padrão maximiza a recuperação. A alternativa reparte o esforço entre as regiões na proporção do tamanho de cada uma, e recupera um pouco menos.
calculo: valor_esperado: ordena por dívida × taxa, sem olhar região. proporcional_por_grupo: dentro de cada UF vale o valor esperado, e a fila alterna as UFs de modo que, em qualquer ponto de corte, cada região apareça na proporção do seu tamanho.
fazer: É decisão de política da empresa, não do sistema. Antes de mudar, rode a análise de equidade e o backtest para ver o custo de cada critério. Troque em Premissas > Critério da fila; vale para as próximas análises.
cuidado: Ordenar por valor esperado tende a deixar para trás regiões de dívidas menores, mesmo quando pagam igual. Nenhum dos dois critérios é "o certo".
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
- o que quer dizer a etiqueta alta ao lado do devedor
- como a etiqueta de prioridade é definida
- qual a proporção de devedores em cada prioridade
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
- por que o número de prioritários é sempre um quinto
- prioritários é uma medida
- o que conta o card de prioritários
- por que o card de prioritários mostra um quinto
- o número de prioritários significa o quê
curta: É quantos devedores cabem na faixa Alta: um quinto da carteira.
calculo: devedores prioritários = piso de (total de devedores × 20%).
fazer: Use como tamanho de uma "meta de ciclo" inicial. Para saber até onde a sua equipe chega de verdade, use o Alcance da operação.
cuidado: Não é uma medida da carteira: é só o tamanho da faixa Alta, que é sempre 20% do total.
fontes:
- frontend/src/pages/Dashboard.jsx::texto "Devedores Prioritários"

## urgencia-do-devedor
titulo: Chance de pagar (onde antes ficava a "Urgência")
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é urgência
- diferença entre urgência e prioridade
- por que a urgência é baixa e a prioridade é alta
- onde foi parar a urgência
- o que é a chance de pagar na recomendação
- urgência vem da nota ou da fila
- por que urgência e prioridade mostravam coisas diferentes
- o que significa a porcentagem ao lado do canal e da oferta
curta: Na recomendação de abordagem, ao lado do canal e da oferta, aparece a chance de pagar deste devedor: o próprio score, em porcentagem. Não há mais o selo "Urgência".
calculo: Chance de pagar = score de recuperabilidade (0 a 100) lido como porcentagem. Até outubro de 2026 esse lugar mostrava "Urgência" Alta (score 70 ou mais), Média (40 a 69) ou Baixa, um terceiro critério que podia contradizer a Prioridade.
fazer: Para decidir quem contatar primeiro, use a Prioridade e a posição na fila: elas consideram também o valor da dívida e a comissão. A chance de pagar ajuda a calibrar a conversa, não a ordem.
cuidado: Um devedor com chance de 35% e dívida grande pode estar no topo da fila: é a fila que pesa chance × valor.
fontes:
- frontend/src/pages/DebtorDetail.jsx::texto "Chance de pagar"

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
- quanto vale o topo da fila que a equipe consegue trabalhar
- onde informo a capacidade da equipe
- o que mostra o alcance da operação
curta: Mostra até onde a fila chega com o número de contatos que a sua equipe consegue fazer no ciclo, e quanto esse topo vale.
calculo: Você informa a capacidade N: operadores × contatos por dia × dias úteis. O alcance soma o valor esperado líquido (depois da comissão da fase especializada, o mesmo que ordena a fila) dos N primeiros. "Do recuperável" é essa soma ÷ o líquido de toda a carteira, e "Vai até a posição" é o rank do N-ésimo. As linhas dentro do alcance aparecem marcadas na tabela.
fazer: Informe a capacidade real da equipe e leve o número para a reunião de planejamento. O valor fica guardado no seu navegador para a próxima vez.
cuidado: Sem comissão configurada, líquido e bruto são iguais. Carteiras analisadas antes de o líquido ser gravado somam o bruto; a tela só escreve "(líquido)" quando é líquido.
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
- como procuro um devedor específico na tabela
- como filtro por estado ou produto
- como vejo só quem já pagou
curta: Dá para buscar por nome ou CPF e filtrar por produto, UF, prioridade e situação do pagamento (pago, não pago, pendente).
calculo: A busca e os filtros são aplicados no servidor e a tabela mostra uma página de 50 por vez. "Pago" e "não pago" usam o feedback mais recente de cada CPF; "pendente" é quem ainda não tem feedback.
fazer: Use "pendente" para ver quem ainda não foi trabalhado.
cuidado: A prioridade é calculada sobre a carteira inteira, não sobre o que sobrou do filtro.
revisar: achado C6, resolvido: o filtro de status agora é aplicado no servidor, sem lista de CPFs na consulta.
fontes:
- backend/main.py::pagina_do_ranking
