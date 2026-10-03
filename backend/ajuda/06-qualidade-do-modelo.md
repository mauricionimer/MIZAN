# Qualidade do modelo (COMANDO)

## ks
titulo: KS
perfis: comando
telas: Aprendizado
perguntas:
- o que é ks
- como interpretar o ks
- ks acima de 50 é bom
- o que é kolmogorov smirnov
- qual o ks bom
- o que é o indicador ks do modelo
- como interpretar o valor do ks
- ks muito alto é bom ou suspeito
curta: Mede o quanto o modelo separa quem paga de quem não paga, de 0 a 100. Acima de 50 é suspeito, não excelente.
calculo: Ordena os devedores pelo score e compara as curvas acumuladas de quem pagou e de quem não pagou; o KS é a maior distância entre elas, em escala 0–100. Leitura: abaixo de 20 fraco; 20 a 30 regular; 30 a 40 bom; 40 a 50 forte; acima de 50 suspeito.
fazer: Use o KS no recorte de teste (que o modelo não viu). Compare modelos diferentes sobre a mesma fatia.
cuidado: KS acima de 50 costuma indicar vazamento: alguma variável que carrega a resposta. Em dados simulados o KS não mede nada real.
fontes:
- backend/model/diagnostico.py::_ks_gini

## gini
titulo: Gini
perfis: comando
telas: Aprendizado
perguntas:
- o que é gini
- como interpretar o gini
- diferença entre gini e auc
- qual o gini bom
- gini de 40 é bom
- como o gini é calculado
- o que é o índice gini do modelo
- como interpretar o gini
- gini e auc são a mesma coisa
curta: É o AUC reescrito na escala 0–100 que a mesa de crédito usa: Gini = 2 × AUC − 1.
calculo: Gini = (2 × AUC − 1) × 100. Leitura: abaixo de 20 fraco; 20 a 40 regular; 40 a 60 bom; acima de 60 forte.
fazer: Leia junto com o KS: contam a mesma história por ângulos diferentes.
cuidado: Valem as mesmas ressalvas do KS: no recorte de teste e com dados reais.
fontes:
- backend/model/diagnostico.py::_ks_gini

## auc-e-brier
titulo: AUC e Brier
perfis: comando
telas: Aprendizado; Treinar modelo
perguntas:
- o que é auc
- o que é brier
- como interpretar o brier
- auc 0,5 significa o quê
- o que é erro quadrático das probabilidades
- o que significam auc e brier
- como saber se as probabilidades são confiáveis
- auc de 0,5 é bom
curta: AUC mede a ordenação (0,5 é sorte, 1 é perfeito). Brier mede o erro das probabilidades (menor é melhor).
calculo: AUC é a chance de um pagador ter score maior que um não pagador sorteado. Brier é a média de (probabilidade − resultado)², entre 0 e 1.
fazer: AUC para saber se ordena; Brier para saber se a probabilidade é confiável como número.
cuidado: Um AUC bom com Brier ruim quer dizer que ordena bem mas as probabilidades estão descalibradas.
fontes:
- backend/model/diagnostico.py::avaliar_modelo_ativo
- backend/model/treino_empresa.py::_metricas

## overfitting
titulo: Qualidade do modelo em uso (e se ele decorou o treino)
perfis: comando
telas: Aprendizado
perguntas:
- o que é overfitting
- o modelo está decorando
- o que é a qualidade do modelo em uso
- como saber se o modelo da empresa está funcionando
- o modelo está decorando os dados de treino
- o que mede o diagnóstico de qualidade
- o modelo caiu depois do treino
- o diagnóstico usa os dados de treino
curta: Pega o modelo que pontua a empresa hoje (o próprio ou o geral), pontua os devedores dela que têm pagamento registrado e compara com o que aconteceu.
calculo: Escolha a empresa e clique em Medir. Entram os devedores da empresa com pagamento registrado; se o modelo em uso foi treinado com os pagamentos do Mizan, só os registrados depois desse treino, porque os outros ele já viu. Mostra KS e Gini, AUC, Brier, a matriz de confusão (score 50 ou mais = "previu que paga") e a calibração por faixa. Quando o modelo próprio tem o teste feito no treino, mostra o AUC de lá ao lado do de agora: uma queda grande indica que ele decorou o treino ou que a carteira mudou. Precisa de pelo menos 30 devedores, com quem pagou e quem não pagou.
fazer: Meça cada empresa antes de apresentar os números, e de novo depois de ativar uma versão nova e juntar pagamentos.
cuidado: Não há corte oficial para "queda grande": compare com o histórico da própria empresa. Com o modelo geral treinado em dados simulados, a medida diz quanto ele acerta nesta carteira, não quanto um modelo treinado nela acertaria.
fontes:
- backend/model/diagnostico.py::avaliar_modelo_ativo
- backend/model/diagnostico.py::_modelo_em_uso
constantes:
- backend/model/diagnostico.py::MIN_AMOSTRAS_DIAGNOSTICO = 30

## dados-suficientes
titulo: Dados suficientes para a complexidade do modelo
perfis: comando
telas: Aprendizado
perguntas:
- tenho dados suficientes para o modelo
- o que é amostras por variável
- por que o modelo diz complexidade inadequada
- quantos pagamentos preciso
- tenho amostras suficientes
- quantos resultados preciso para avaliar o modelo
- tenho resultados suficientes para o modelo
- o que são amostras por variável
- por que o diagnóstico fala em complexidade adequada
curta: Regra prática: pelo menos 20 devedores com resultado para cada variável do modelo. Abaixo disso, desconfie de qualquer métrica.
calculo: amostras por variável = devedores com resultado no treino do modelo em uso ÷ número de variáveis dele. Adequado a partir de 20. Para medir o modelo, o diagnóstico exige no mínimo 30 devedores com pagamento registrado.
fazer: Se estiver abaixo, aguarde mais resultados ou use o treino por empresa com a carteira histórica.
cuidado: É regra prática, não teorema.
fontes:
- backend/model/diagnostico.py::avaliar_modelo_ativo
constantes:
- backend/model/diagnostico.py::AMOSTRAS_POR_FEATURE_MINIMO = 20
- backend/model/diagnostico.py::MIN_AMOSTRAS_DIAGNOSTICO = 30

## calibracao
titulo: Calibração por faixa
perfis: comando
telas: Aprendizado
perguntas:
- o que é calibração
- o modelo está calibrado
- probabilidade prevista contra taxa real
- como ler a calibração por faixa
- a probabilidade está otimista
- o que é o gráfico de confiabilidade
- as probabilidades do modelo batem com a realidade
- o que é a calibração por faixa
- previsto versus observado em cada faixa
curta: Compara, em cinco faixas de probabilidade, o que o modelo previu com o que de fato aconteceu. Calibrado é quando os dois se parecem.
calculo: Divide os devedores medidos em 5 grupos de mesmo tamanho por probabilidade e mostra a média prevista e a taxa real de pagamento de cada um.
fazer: Se a previsão for sistematicamente maior que a real, a probabilidade está otimista.
cuidado: Com poucos devedores por faixa a taxa real oscila muito.
fontes:
- backend/model/diagnostico.py::_calibracao_por_faixa

## peso-das-variaveis
titulo: O que mais pesa no score de uma empresa
perfis: comando
telas: Aprendizado
perguntas:
- o que mais pesa no score
- qual variável mais influencia o modelo
- importância das variáveis do modelo
- por que a importância das variáveis aparecia indisponível
- o que significa pontos na importância da variável
- quanto a renda pesa no score
- por que o score de bureau não aparece na importância
- como é medida a importância das variáveis
curta: Mostra quanto cada informação (dias em atraso, valor da dívida, renda, produto...) move, em média, o score dos devedores de uma empresa, no modelo que pontua essa empresa.
calculo: Em Aprendizado, escolha a empresa e clique em Medir. Pega até 500 devedores da análise mais recente da empresa. Para cada informação, troca só ela pelo valor típico do treino (mediana ou valor mais comum), mantém o resto e o grupo de perfil de cada devedor, e mede quanto o score muda. O peso é a média dessa mudança, em pontos; a porcentagem é a parte de cada informação na soma. É o mesmo método da explicação de cada devedor.
fazer: Use para conferir se o modelo da empresa se apoia no que faz sentido para a carteira dela, e compare antes de ativar uma versão nova.
cuidado: Mede associação dentro do modelo, não causa. Informações que não ficam gravadas na análise (como score de bureau e tentativas de contato) não podem ser medidas aqui e aparecem listadas à parte. Até outubro de 2026 esta seção ficava sempre "indisponível", porque o modelo calibrado não traz importância pronta.
fontes:
- backend/model/score.py::peso_das_variaveis
- backend/main.py::rota /admin/feature-importance

## psi
titulo: PSI (a carteira ainda parece com a do treino?)
perfis: admin, comando
telas: Precificação
perguntas:
- o que é psi
- como interpretar o psi
- por que aparece mudança crítica de população
- a carteira mudou em relação ao treino
- o que fazer com psi alto
- o que é o índice de estabilidade da população
- por que apareceu mudança crítica de população
- a carteira atual mudou em relação ao treino
curta: Mostra se a carteira analisada hoje tem uma distribuição de score parecida com a do treino. Alto significa que o modelo pode estar fora do terreno que conhece.
calculo: PSI = soma, nas 10 faixas de score, de (p_atual − p_treino) × ln(p_atual ÷ p_treino). Abaixo de 0,10: estável. De 0,10 a 0,25: atenção. Acima de 0,25: mudança crítica.
fazer: Acima de 0,25, retreine e, até lá, trate o score como ordenação grosseira, não como probabilidade.
cuidado: O PSI mede deslocamento da população, não perda de acerto: pode ser alto com o modelo ainda acertando, e baixo com o modelo já ruim por outro motivo. É alarme de "olhe isto".
fontes:
- backend/model/psi.py::calcular
constantes:
- backend/model/psi.py::PSI_ATENCAO = 0.10
- backend/model/psi.py::PSI_CRITICO = 0.25

## deriva-do-score
titulo: Deriva do score de uma empresa
perfis: comando
telas: Aprendizado
perguntas:
- o que é deriva do score
- como o drift é calculado
- diferença entre drift e psi
- por que o score médio mudou
- a população da empresa mudou
- como a deriva do score é calculada
- o que fazer quando a população mudou em relação ao treino
- o que é o aviso de deriva na tela de aprendizado
curta: É o PSI dos devedores que uma empresa analisou nos últimos 30 dias, contra a distribuição de score congelada no treino do modelo que pontua essa empresa.
calculo: Em Aprendizado, escolha a empresa e clique em Medir. Entram os scores das predições da empresa gravadas nos últimos 30 dias. O PSI usa as mesmas faixas e a mesma régua do PSI da análise: até 0,10 estável; acima de 0,10 atenção; acima de 0,25 crítico. Precisa de pelo menos 20 devedores no período.
fazer: Com "atenção" ou "crítico", meça a qualidade do modelo em uso (mesma tela) e considere treinar uma versão nova da empresa.
cuidado: Até outubro de 2026 havia outra "deriva", que comparava o score médio dos últimos 30 dias com o histórico inteiro, misturando todas as empresas, com limite fixo de 10 pontos e e-mail a cada abertura da tela. Ela deixou de existir: a deriva agora é só o PSI, por empresa, e não manda e-mail.
fontes:
- backend/main.py::rota /admin/drift
- backend/model/psi.py::calcular
constantes:
- backend/model/psi.py::PSI_ATENCAO = 0.10
- backend/model/psi.py::PSI_CRITICO = 0.25

## equidade
titulo: Equidade entre grupos
perfis: admin, comando
telas: Backtest
perguntas:
- o que é equidade
- o que é a regra dos 80 por cento
- a fila trata os grupos de forma justa
- razão de equidade
- a fila prejudica alguma região
- o que é impacto desproporcional
- a ordenação da fila trata as regiões de forma justa
- o que é a regra dos 80 por cento
- o que é a razão de equidade
curta: Compara que fatia de cada grupo (por exemplo, cada região) entra no topo da fila. A razão entre o menos e o mais favorecido deve ficar acima de 0,80.
calculo: razão = fatia selecionada do grupo menos favorecido ÷ fatia do mais favorecido. Alerta abaixo de 0,80. Grupos com menos de 30 devedores são ignorados na comparação, porque a taxa é ruído.
fazer: Se a razão ficar abaixo de 0,80, leve a decisão ao comitê: trocar o critério da fila para "proporcional por região" custa recuperação.
cuidado: A regra dos 80% é prática de origem norte-americana: não é lei brasileira nem exigência do material de referência do projeto. É ponto de partida.
fontes:
- backend/model/equidade.py::analisar
constantes:
- backend/model/equidade.py::RAZAO_ATENCAO = 0.80
- backend/model/equidade.py::MINIMO_POR_GRUPO = 30

## backtest
titulo: Backtest (carteira histórica)
perfis: admin, comando
telas: Backtest
perguntas:
- o que é o backtest
- como testar a fila com uma carteira antiga
- o que é capturado em 10 por cento da carteira
- como comparar a fila com maior dívida primeiro
- por que usar uma carteira histórica
- como medir a fila com uma carteira cujo resultado já se conhece
- o que o backtest compara
- como ler o valor capturado em cada capacidade
curta: Aplica a fila a uma carteira cujo resultado já se conhece e mede quanto cada critério teria recuperado trabalhando só uma parte dela.
calculo: Compara três filas (valor esperado, score puro e maior dívida primeiro) em capacidades de 10%, 20%, 30% e 50% da carteira, e mostra o valor capturado por cada uma, mais KS e Gini do score e a análise de equidade.
fazer: Use uma carteira com a coluna pagou. É a medida mais honesta de quanto a fila vale para a sua base.
cuidado: O backtest usa sempre o modelo geral, não o modelo próprio da empresa. Resultados citados em comentários do código vêm de dados sintéticos e não são desempenho real.
fontes:
- backend/backtest.py::rodar
constantes:
- backend/backtest.py::CAPACIDADE_EQUIDADE = 0.20

## versoes-e-promocao
titulo: Versões do modelo e promoção
perfis: comando
telas: Aprendizado
perguntas:
- o que é promover um modelo
- como voltar a uma versão anterior do modelo
- o que é versão ativa
- por que não consigo promover uma versão
- o que é tipo de alvo simulado ou real
- como ativar uma versão anterior do modelo
- o que significa promover uma versão do modelo
- quando uma versão não pode ser promovida
curta: Cada treino gera uma versão guardada. Só a promovida pontua. Dá para promover outra ou voltar atrás.
calculo: A promoção copia os arquivos da versão para os de produção. Uma versão com poucas amostras reais não pode ser promovida sem confirmação explícita. O "tipo de alvo" diz se a versão aprendeu com resultado real ou simulado.
fazer: Antes de promover, compare as métricas com a versão ativa na mesma fatia de teste.
cuidado: Versão de alvo simulado não mede desempenho: só mostra que o modelo roda. Estas são as versões do modelo geral, que não é mais retreinado com pagamentos de clientes; as versões treinadas com pagamentos são por empresa e ficam em Treinar modelo.
fontes:
- backend/model/retrain.py::promover_versao

## treino-por-empresa
titulo: Treinar o modelo de uma empresa
perfis: comando
telas: Treinar modelo
perguntas:
- como treinar o modelo de uma empresa
- quais colunas o arquivo de treino precisa
- o arquivo de treino fica guardado
- o treino usa cpf
- como ativar o modelo treinado
- como voltar ao modelo geral
- por que o treino foi recusado
- como treinar um modelo só de uma empresa com a carteira histórica
- o que acontece com o arquivo enviado para treino
- por que o arquivo de treino foi recusado
curta: O COMANDO envia a carteira histórica com o resultado real; o sistema treina um modelo só daquela empresa, mostra as métricas contra o modelo atual e descarta o arquivo.
calculo: Exige valor_divida, dias_em_atraso e uma coluna de resultado (pagou, pago, quitou etc.); data (data_referencia) é opcional e habilita a validação no tempo. Mínimo de 300 linhas e 30 de cada resultado; máximo (padrão) de 100.000 linhas usadas (acima disso, amostra aleatória). Treinar não ativa: a ativação é um passo seguinte, e se o modelo novo for pior que o atual (AUC) pede confirmação.
fazer: Confira as métricas e os avisos antes de ativar; se algo estiver estranho, volte ao modelo geral.
cuidado: CPF, nome e contatos são removidos antes do treino e o arquivo não é gravado; ficam registrados só a impressão digital do arquivo, as contagens e as métricas. O modelo derivado de dados pessoais não deve ser descrito como "anônimo".
fontes:
- backend/model/treino_empresa.py::treinar
- backend/main.py::rota /comando/treino
constantes:
- backend/model/treino_empresa.py::MIN_LINHAS = 300
- backend/model/treino_empresa.py::MIN_POR_CLASSE = 30
- backend/model/treino_empresa.py::FRACAO_TESTE = 0.20

## estatisticas-do-bandit
titulo: Performance IA (estatísticas do aprendizado de abordagem)
perfis: comando
telas: Performance IA; Aprendizado
perguntas:
- o que é a tela performance ia
- como zerar o aprendizado das ofertas de uma empresa
- o que é o alpha do bandit
- o que é incerteza média
- o bandit convergiu
- como ajustar a exploração
- o que mostra a tela de performance ia
- o que é incerteza e alpha na recomendação de abordagem
- como ajustar o quanto o sistema explora
curta: Mostra quantas vezes cada combinação de canal e oferta foi tentada e com que resultado, e quanto o sistema ainda "duvida" de cada uma.
calculo: Para cada uma das 12 combinações: tentativas, pagamentos, recompensa média e incerteza (média da diagonal da matriz de confiança). Incerteza alta significa que ainda explora. O alpha (padrão 1,0) dá o peso da exploração; o COMANDO pode ajustá-lo, entre 0,1 e 5,0, para uma empresa por vez.
fazer: Aumente o alpha para explorar mais, reduza para explorar menos, com cuidado: muda as recomendações de todos os operadores daquela empresa.
cuidado: Combinações com poucas tentativas têm médias instáveis. Até outubro de 2026, um pagamento sem recomendação prévia ensinava ao bandit a ação que ele "teria" recomendado, que não foi feita; isso parou, mas as contagens antigas continuam lá. Em Aprendizado, o COMANDO pode zerar o aprendizado de uma empresa (sem volta, fica na auditoria).
fontes:
- backend/model/bandit.py::zerar
- backend/model/bandit.py::convergencia_stats
- backend/main.py::rota /admin/bandit/stats

## empresa-suspeita
titulo: Empresa com comportamento suspeito
perfis: comando
telas: Painel COMANDO
perguntas:
- o que significa empresa com comportamento suspeito
- por que uma empresa aparece como suspeita
- taxa de feedback baixa
- o que fazer com empresa suspeita
- por que aparece alerta vermelho de empresa
- o que é menos de 5 por cento de feedback
- por que uma empresa aparece como suspeita no painel
- o que significa baixa taxa de feedback
- como agir com uma empresa que não registra pagamentos
curta: Marca a empresa que analisou muitos devedores mas registrou quase nenhum pagamento, o que sugere que o sistema está sendo usado sem fechar o ciclo de aprendizado.
calculo: Suspeita quando a empresa tem 50 ou mais devedores analisados e menos de 5% deles com feedback registrado.
fazer: Procure o responsável pela empresa: sem resultados registrados o modelo não aprende e as métricas ficam sem base.
cuidado: Os limites 50 e 5% são escolha de projeto. Uma empresa recém-chegada, ainda sem pagamentos para registrar, também aparece.
fontes:
- backend/main.py::comando_visao_geral

## limites-do-banco
titulo: Limites do banco (diagnóstico)
perfis: comando
telas: Painel COMANDO
perguntas:
- o que faz o botão medir agora
- por que medir os limites do banco
- o que é itens por in
- o que é teto de resposta
- como medir os limites do supabase
- o que o diagnóstico do banco mostra
- para que serve o botão medir agora no painel
- como saber quantos itens cabem numa consulta ao banco
- o que mostra o diagnóstico dos limites do banco
curta: Mede no Supabase real três limites de que a paginação depende: tamanho da lista num filtro, linhas por resposta e a ordenação com desempate.
calculo: Testa listas de 100 até 3.200 identificadores sorteados (que não casam com nenhuma linha), pede 3.000 linhas para ver quantas voltam e confere se a ordenação por posição e id é aceita. Só lê.
fazer: Rode depois de mudar de plano ou de configuração do Supabase e confira se o tamanho adotado cabe.
cuidado: Medidas até hoje: lista de 400 passa e 800 falha; resposta limitada a 1.000 linhas.
fontes:
- backend/main.py::comando_diagnostico_banco
constantes:
- backend/main.py::ITENS_POR_IN = 100
- backend/main.py::LOTE_LEITURA = 1000
