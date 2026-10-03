# Modelo e score

## estado-do-modelo
titulo: O modelo está em dados simulados ou reais?
perfis: operador, admin, comando
telas: Visão da carteira
perguntas:
- o score é confiável
- o modelo foi treinado com dados reais
- por que aparece aviso de modelo em calibração inicial
- o score reflete o histórico da minha carteira
- de onde vem o score
- posso confiar na nota
curta: Enquanto não houver uma carteira real com resultado de pagamento, o score vem de um modelo treinado em dados simulados: ele ordena segundo premissas declaradas, não segundo o histórico da sua base.
calculo: O modelo ativo é treinado com um alvo simulado (uma nota ponderada de dias de atraso, comprometimento de renda, produto e tentativas de contato). Quando uma empresa envia a carteira histórica com o resultado real, o COMANDO treina um modelo só dela, compara com o atual e, se aprovar, ativa.
fazer: Use a fila como ordenação inicial, não como previsão calibrada. À medida que os pagamentos forem registrados, o sistema passa a aprender com eles.
cuidado: Em dados simulados a probabilidade não é uma probabilidade medida: foi calibrada contra o alvo simulado. Não apresente os números como desempenho do modelo.
fontes:
- backend/model/train.py::_criar_alvo_simulado
- backend/main.py::_procedencia_modelo_ativo
- backend/model/treino_empresa.py::treinar
constantes:
- backend/model/retrain.py::MIN_FEEDBACKS_DEFAULT = 30

## score-recuperabilidade
titulo: Score de recuperabilidade
perfis: operador, admin, comando
telas: Recuperabilidade; Devedor
perguntas:
- o que é o score
- como o score é calculado
- o que significa score 80
- o que é recuperabilidade
- score alto quer dizer que vai pagar
- qual a escala do score
- de que escala é a nota
curta: Nota de 0 a 100 que resume a chance estimada de o devedor pagar alguma coisa. Quanto maior, mais provável.
calculo: score = probabilidade de pagamento × 100, com uma casa decimal. A probabilidade vem de um classificador de árvores (HistGradientBoosting) calibrado por Platt, que lê as variáveis da carteira e o perfil (cluster) do devedor.
fazer: Use o score junto com o valor da dívida: a fila já combina os dois (veja "Como a fila é ordenada").
cuidado: Score alto não significa dívida alta nem prioridade máxima. E, enquanto o modelo estiver em dados simulados, é uma nota de ordenação, não uma chance medida.
fontes:
- backend/model/score.py::score_carteira
- backend/model/train.py::_treinar_com_df

## probabilidade-de-pagamento
titulo: Probabilidade de pagamento
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é probabilidade de pagamento
- qual a chance de o devedor pagar
- diferença entre score e probabilidade
- probabilidade é igual ao score
curta: É o score dividido por 100, limitado entre 0 e 1. Está no devedor e alimenta as propostas.
calculo: probabilidade_pagamento = score ÷ 100, entre 0 e 1.
fazer: Use para comparar devedores entre si. Nas propostas, ela é substituída pela chance de pagamento por tipo de oferta quando já existe feedback real.
cuidado: Com o modelo em dados simulados não é uma probabilidade medida.
fontes:
- backend/main.py::_analisar_df

## variaveis-do-modelo
titulo: Quais informações o modelo usa
perfis: operador, admin, comando
telas: Devedor
perguntas:
- quais colunas o modelo usa
- o modelo usa o cpf
- o modelo usa o nome
- o modelo usa a idade ou a cor
- que dados entram no score
- o que o modelo considera
curta: Valor da dívida, renda, dias em atraso, produto, estado e o que se pode derivar disso. CPF e nome não entram.
calculo: Usa as colunas numéricas e as colunas de texto com até 30 valores diferentes. Calcula ainda: dívida ÷ renda (limitada a 0–10), logaritmo da dívida, logaritmo da renda e valor por dia de atraso. CPF, nome e identificadores ficam de fora.
fazer: Quanto mais completas as colunas obrigatórias e a renda, mais fiel é o score. Veja "Dados incompletos".
cuidado: Coluna de texto com muitos valores diferentes (mais de 30) é ignorada.
fontes:
- backend/model/train.py::_detectar_features
- backend/model/train.py::_adicionar_derivadas
constantes:
- backend/model/train.py::_CAT_MAX_UNIQUE = 30

## perfil-cluster
titulo: Perfil do devedor (grupo)
perfis: operador, admin, comando
telas: Visão da carteira; Devedor
perguntas:
- o que é o perfil do devedor
- o que significa crônico alto comprometimento cartão
- como os grupos são formados
- o que é cluster
- o que é segmentação
curta: O sistema agrupa devedores parecidos automaticamente e dá a cada grupo um nome pelo que ele tem em comum.
calculo: Agrupamento KMeans sobre as variáveis. O nome é montado por regras: dias de atraso médios abaixo de 60 = Recente, abaixo de 180 = Intermediário, senão Crônico; dívida ÷ renda média abaixo de 0,3 = Baixo, abaixo de 0,7 = Moderado, senão Alto; e o produto predominante.
fazer: Use os grupos para planejar a abordagem em massa, por exemplo uma régua diferente para cada perfil.
cuidado: Os grupos são estatísticos, não categorias do banco. Os cortes que dão nome (60, 180, 0,3, 0,7) são escolha de projeto, não regra de crédito.
fontes:
- backend/model/train.py::_gerar_labels_clusters

## por-que-esse-score
titulo: Por que esse score? (motivos)
perfis: operador, admin, comando
telas: Devedor
perguntas:
- por que esse devedor tem esse score
- como o sistema explica a nota
- o que são os principais motivos
- o que puxou o score para baixo
- o que puxou o score para cima
- direito à explicação
curta: Mostra até três motivos que mais subiram e até três que mais baixaram o score deste devedor, em pontos.
calculo: Para cada variável, o sistema troca só ela pela referência da população de treino (mediana ou moda), mantém as outras e o perfil, e mede quantos pontos o score mudaria. Mostra os três maiores efeitos de cada lado, ignorando os menores que 1 ponto.
fazer: Use para conversar com o devedor e para justificar a ordem da fila (atende ao direito à explicação da LGPD, art. 20).
cuidado: Com a nota no extremo (0 ou 100) nenhuma variável isolada move o score e a lista vem vazia, com um aviso. E os textos dos motivos usam a palavra "historicamente" para produto e região, o que só vale quando o modelo foi treinado com resultado real.
revisar: o texto "historicamente" em produto e região precisa ser ajustado (achado T1 do mapa do sistema).
fontes:
- backend/model/score.py::explicar_predicao
- backend/model/score.py::_reason_codes
- backend/main.py::explicar_score_devedor
constantes:
- backend/model/score.py::MAX_REASON_CODES = 3
- backend/model/score.py::IMPACTO_MINIMO_REASON_CODE = 1.0

## dados-incompletos
titulo: Dados incompletos
perfis: operador, admin, comando
telas: Recuperabilidade; Devedor
perguntas:
- o que significa dados incompletos
- por que o devedor aparece com aviso de dados
- valor zerado ou nulo
- renda não informada
- o que fazer quando faltam dados
curta: Marca o devedor que veio sem valor da dívida, sem dias de atraso ou sem renda (ausente, vazio ou zero).
calculo: Antes de qualquer preenchimento, o sistema confere valor_divida e dias_em_atraso (críticos) e renda_estimada (importante). O aviso lista quais campos estavam zerados, nulos ou ausentes.
fazer: Corrija na origem e reenvie a carteira. Sem renda, a verificação de capacidade de pagamento (margem livre) fica indisponível.
cuidado: Quando a coluna de renda nem existe no arquivo, o sistema grava renda 0; nesse caso a razão dívida ÷ renda também vira 0, porque sem renda não há como medir. O score desse devedor é uma estimativa feita com esse dado faltando.
fontes:
- backend/model/score.py::_avaliar_qualidade_dados

## modelo-proprio-ou-geral
titulo: Minha empresa usa um modelo próprio?
perfis: admin, comando
telas: Treinar modelo
perguntas:
- minha empresa tem modelo próprio
- o modelo é só da minha empresa
- meus dados treinam o modelo dos outros
- o modelo geral e o modelo da empresa
- como saber qual modelo está pontuando
curta: Cada empresa usa o modelo geral até que o COMANDO treine e ative um modelo só dela. O modelo próprio nunca pontua outra empresa.
calculo: Ao pontuar, o sistema procura o modelo ativo da empresa; se não houver, usa o geral. A versão usada fica gravada na carteira.
fazer: Peça ao COMANDO para treinar o modelo com a carteira histórica, se quiser pontuar com base no seu histórico.
cuidado: Hoje o retreino automático do modelo geral ainda usa os pagamentos de todas as empresas juntos; essa política está em revisão.
revisar: decisão D1 do mapa do sistema (retreino automático misturando empresas).
fontes:
- backend/model/modelos_empresa.py::carregar_ativo
- backend/model/score.py::_carregar_modelos
- backend/model/retrain.py::_buscar_feedbacks
