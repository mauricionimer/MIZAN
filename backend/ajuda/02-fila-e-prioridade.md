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
fazer: Trabalhe de cima para baixo. O que está no topo é onde um contato rende mais, até onde a capacidade da equipe permitir.
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
fazer: Use como tamanho de uma "meta de ciclo" inicial. Para medir quanto a fila rende numa capacidade, use o Backtest.
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

## divisao-da-fila
titulo: Divisão da fila entre operadores
perfis: operador, admin, comando
telas: Recuperabilidade; Devedor
perguntas:
- como divido a fila entre os operadores
- como vejo só os meus devedores
- por que o colega não recebeu só os piores
- dois operadores podem ligar para o mesmo devedor
- como troco o responsável de um devedor
- o que acontece com a divisão quando a carteira é analisada de novo
- quem está sem responsável
curta: O admin reparte a fila entre os operadores escolhidos; cada devedor fica com no máximo um responsável e o operador abre direto em "Minha fila".
calculo: A fila já está na ordem do valor esperado. A divisão segue essa ordem em rodízio de ida e volta (1, 2, 3, 3, 2, 1, 1, 2, 3…), então cada operador recebe uma fatia com o mesmo perfil de valor e o mesmo número de devedores, com diferença de no máximo um. O valor por operador mostrado antes de confirmar é a média (total ÷ operadores), aproximado.
fazer: Em Recuperabilidade, use "Distribuir fila", marque os operadores e confirme. Para quem entrou depois, marque "Só quem está sem responsável": quem já tinha dono continua com ele. Na ficha do devedor o admin troca o responsável na hora.
cuidado: Só operadores ativos da empresa da carteira podem receber fila. Reanalisar ou sincronizar a carteira mantém o responsável de quem continua nela, pelo CPF; devedores novos entram sem responsável. Até rodar sql/migracao_operador.sql no Supabase a divisão aparece como "falta rodar o SQL".
fontes:
- backend/fila_operadores.py::serpentina
- backend/main.py::distribuir_fila
- backend/main.py::atribuir_responsavel

## agenda-de-retorno
titulo: Agenda de retornos e promessas
perfis: operador, admin, comando
telas: Agenda; Devedor
perguntas:
- onde vejo quem prometeu pagar
- como agendo um retorno para o devedor
- o que é o alerta vermelho da agenda
- o que significa alto médio e safe
- a promessa some sozinha quando o devedor paga
- como remarco um retorno
- o que faço quando o devedor não pagou o que prometeu
curta: A Agenda guarda os retornos ("me liga sexta") e as promessas de pagamento combinados nos contatos, separados por urgência: Alto, Médio e Safe.
calculo: Alto (vermelho) é o compromisso cuja data já passou e segue pendente. Médio (âmbar) vence hoje ou amanhã. Safe (verde) é daqui a 2 dias ou mais. O dia de referência é o de Brasília. O número no menu soma Alto e Médio e fica vermelho quando há algum Alto.
fazer: Ao registrar um contato com "Prometeu pagar", informe a data prometida e o valor: a promessa entra na Agenda. Para qualquer outro resultado, marque "Agendar retorno". Na Agenda, use Pagou, Não pagou, Feito ou Remarcar.
cuidado: Quando um pagamento confirmado do devedor entra (baixa em Pagamentos, confirmação na fila, lote ou integração), as promessas pendentes dele viram "pagas" sozinhas. Marcar "Pagou" na Agenda não registra o pagamento nos resultados: isso continua sendo feito em Pagamentos. O operador vê só os próprios compromissos; o admin vê os da equipe; o COMANDO consulta a agenda de uma empresa, sem alterar.
fontes:
- backend/agenda.py::nivel
- backend/main.py::_cumprir_promessas
- backend/main.py::listar_agenda

## painel-do-operador
titulo: Meu painel e painel da equipe
perfis: operador, admin, comando
telas: Painel do operador
perguntas:
- quantos contatos eu fiz hoje
- quanto entrou da minha fila
- como vejo os acordos que fechei
- o que é contato efetivo
- por que o recebido não bate com as promessas
- como vejo o desempenho de cada operador
- de onde vem a meta do dia
curta: Mostra, por período (hoje, 7 dias, 30 dias), os contatos feitos, os acordos fechados e quanto entrou. O operador vê os próprios números; o admin vê a equipe, um operador por linha.
calculo: Contatos são os contatos registrados pelo operador no período; contato efetivo é todo resultado diferente de "sem resposta". Acordos são as promessas de pagamento que ele registrou, com o valor prometido. Recebido soma os pagamentos confirmados (marcados como pagos em Pagamentos, na fila, em lote ou pela integração) de devedores sob a responsabilidade dele na divisão da fila. A meta compara os contatos de hoje com a meta de Premissas. O dia é o de Brasília.
fazer: Use "Hoje" para acompanhar a meta e "30 dias" para comparar operadores. Para a barra da meta aparecer, o admin informa "Meta de contatos por operador por dia" em Premissas.
cuidado: Promessa não é dinheiro: só pagamento confirmado entra em "Recebido". Pagamento de devedor sem responsável aparece à parte no painel da equipe. Sem a divisão da fila, o recebido não é atribuído a ninguém.
fontes:
- backend/painel.py::resumir
- backend/main.py::painel_operador
- backend/main.py::painel_equipe

## meta-de-contatos
titulo: Meta de contatos por operador por dia
perfis: admin, comando
telas: Premissas
perguntas:
- como defino a meta diária dos operadores
- qual meta de contatos colocar
- a meta muda a fila
- onde aparece a meta de contatos
- posso tirar a meta
curta: Quantos contatos cada operador deve registrar por dia. Aparece como barra em "Meu painel" e na tabela da equipe.
calculo: Número inteiro de 1 a 1000, igual para todos os operadores da empresa. A barra compara os contatos registrados hoje (dia de Brasília) com esse número. Não tem padrão: sem ela, o painel mostra os números sem a barra.
fazer: Defina com base no que a equipe faz hoje: abra o painel da equipe em "30 dias", veja os contatos por operador e divida por dias úteis.
cuidado: A meta não muda a ordem da fila nem nenhum cálculo do modelo; é só acompanhamento.
fontes:
- backend/model/premissas.py::PREMISSAS
