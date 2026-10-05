# Devedor, margem e propostas

## comprometimento-de-renda
titulo: Comprometimento de renda
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é comprometimento de renda
- como o comprometimento de renda é calculado
- por que o comprometimento passa de 100 por cento
- comprometimento é a parcela
- quanto da renda a dívida representa
- razão dívida sobre renda
- quanto da renda a dívida consome
- por que o comprometimento passa de cem por cento
- como o comprometimento de renda é calculado
curta: É a dívida total dividida pela renda mensal estimada, mostrada em porcentagem.
calculo: comprometimento = valor da dívida ÷ renda estimada, limitado a 10 vezes (1.000%) no modelo. Sem renda (ausente, vazia ou zero), fica desconhecido e o modelo usa a mediana do treino.
fazer: Use para medir o tamanho da dívida frente ao que o devedor ganha. Para saber se uma parcela cabe, veja a margem livre.
cuidado: É a dívida inteira sobre a renda de um mês, não a parcela. Por isso passa de 100% com facilidade. A renda é uma estimativa, não um dado confirmado.
fontes:
- backend/model/score.py::_adicionar_derivadas
- frontend/src/pages/DebtorDetail.jsx::texto "Comprometimento de Renda"

## margem-livre
titulo: Margem livre mensal
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é margem livre
- como a margem livre é calculada
- por que a margem livre está indisponível
- o que é buffer de 30 por cento
- onde informo as despesas do devedor
- por que as propostas não têm sugestão
- quanto sobra por mês para o devedor pagar
- por que aparece margem indisponível
- onde informo as despesas mensais do devedor
curta: É quanto do mês sobra para o devedor pagar uma parcela, depois das despesas e de uma folga de segurança.
calculo: margem livre = (renda − despesas mensais) × (1 − buffer%). O buffer padrão é 30%. Se as despesas ou a renda não forem informadas, a margem fica indisponível: o sistema não estima despesas.
fazer: Informe as despesas na hora da conversa (campo na seção de propostas) ou inclua a coluna despesas_mensais na carteira.
cuidado: Sem margem, nenhuma parcela é marcada como "cabe no bolso" e nenhuma proposta é sugerida, de propósito: sugerir sem saber se cabe é pior que não sugerir. O buffer de 30% vem do material de referência, mas é regra do banco: o administrador ajusta em Premissas > Folga de segurança na margem livre, e vale na hora nas propostas.
fontes:
- backend/model/proposta.py::calcular_margem
constantes:
- backend/model/proposta.py::BUFFER_MARGEM_PCT_PADRAO = 30.0

## parcela-maxima
titulo: Parcela máxima
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é parcela máxima
- qual o valor máximo da parcela
- como a parcela máxima é definida
- o que é teto de comprometimento
- qual a maior parcela que cabe
- como a parcela máxima muda
- qual a maior parcela que cabe no bolso dele
- como é definida a parcela máxima
- a parcela cabe na margem
curta: É a maior parcela que a política do banco admite para a margem livre deste devedor.
calculo: parcela máxima = margem livre × teto de comprometimento%. O teto padrão é 100%: a parcela pode ocupar toda a margem (que já tem a folga de 30%).
fazer: Compare com a parcela de cada proposta: a marcada "dentro da margem" cabe.
cuidado: O teto mais rígido (por exemplo 30% da margem) é regra de quem concede crédito novo e fica disponível por empresa, mas o padrão reproduz o motor de renegociação do material de referência.
fontes:
- backend/model/proposta.py::parcela_maxima
constantes:
- backend/model/proposta.py::COMPROMETIMENTO_MAX_PCT_PADRAO = 100.0

## propostas-de-renegociacao
titulo: Propostas de renegociação
perfis: operador, admin, comando
telas: Devedor
perguntas:
- como as propostas são montadas
- quais são as propostas de renegociação
- o que significa sugerida
- o que significa alternativa
- por que a proposta sugerida é essa
- por que nenhuma proposta é sugerida
- qual proposta oferecer ao devedor
- quais ofertas posso fazer ao devedor
- o que significa proposta sugerida e alternativa
- por que não aparece proposta sugerida
curta: São quatro ofertas padrão. A sugerida é a de maior valor esperado entre as parceladas que cabem no bolso; a quitação à vista aparece como alternativa.
calculo: As quatro ofertas: parcelado em 4x sem desconto, parcelado em 12x, 10% de desconto à vista e 30% de desconto à vista. valor cobrado = dívida × (1 − desconto). valor esperado = valor cobrado × chance de pagamento da oferta. Entre as parceladas cuja parcela cabe na margem, a de maior valor esperado é a sugerida. A melhor à vista é a alternativa, pois pagamento único não sai da renda mensal.
fazer: Use a sugerida como ponto de partida da conversa. Se a margem estiver indisponível, informe as despesas.
cuidado: Enquanto não houver feedback por tipo de oferta, todas têm a mesma chance de pagamento e o sistema avisa. As quatro ofertas e seus descontos são ponto de partida, não política do banco.
fontes:
- backend/model/proposta.py::avaliar
- backend/model/proposta.py::ARQUETIPOS_PADRAO
- backend/main.py::rota /predicoes/{cpf}/propostas

## chance-de-pagamento-por-oferta
titulo: Chance de pagamento por oferta
perfis: operador, admin, comando
telas: Devedor
perguntas:
- de onde vem a chance de pagamento de cada oferta
- por que todas as ofertas têm a mesma chance
- como o sistema aprende qual oferta funciona
- o que é PoP
- o que é suavização
- como o sistema aprende qual tipo de oferta funciona
- por que todas as propostas têm a mesma chance
- o que é a suavização da chance de pagamento
curta: Começa igual ao modelo e passa a refletir o que a sua equipe registra: quantas vezes cada tipo de oferta resultou em pagamento.
calculo: chance da oferta = (pagamentos + 10 × chance do modelo) ÷ (tentativas + 10). Os 10 "pontos de mentira" evitam que 1 pagamento em 1 tentativa vire 100%. Soma os três canais, porque a pergunta é qual oferta funciona, não qual canal.
fazer: Registre cada contato informando a oferta apresentada. É assim que a estimativa deixa de ser a do modelo.
cuidado: O número 10 é escolha de engenharia, sem fonte externa. Só pagamentos contam como pagamento; contato "contactado" e "prometeu pagar" são tentativas sem pagamento. Antes desta correção esses contatos eram contados como pagamento, então o histórico gravado até agora pode estar inflado.
fontes:
- backend/model/bandit.py::pop_por_oferta
constantes:
- backend/model/bandit.py::K_SUAVIZACAO_POP = 10.0

## recomendacao-de-abordagem
titulo: Recomendação de abordagem (canal e oferta)
perfis: operador, admin, comando
telas: Devedor
perguntas:
- o que é a recomendação de abordagem
- como o sistema escolhe o canal
- por que recomenda whatsapp
- o que é perfil IA
- o que significa exploração inicial
- o que significa aprendendo
- o que significa calibrado
- como a IA escolhe a oferta
- qual canal usar para falar com esse devedor
- o que significam exploração inicial aprendendo e calibrado
- como o sistema escolhe canal e oferta
curta: Sugere por qual canal (WhatsApp, telefone, carta/e-mail) e com qual oferta abordar este devedor, e vai melhorando com os resultados registrados.
calculo: São 12 combinações (3 canais × 4 ofertas). Um algoritmo de aprendizado por reforço (LinUCB) pontua cada uma com a estimativa de retorno para o perfil do devedor mais um bônus de exploração (peso 1,0) para as combinações pouco testadas. O contexto tem 14 números: score, dias de atraso, comprometimento, produto, região e renda. O estado de aprendizado é separado por empresa. Modos: "exploração inicial" (sem nenhum feedback), "aprendendo" (menos de 3 interações com a combinação) e "calibrado" (3 ou mais).
fazer: Registre o contato e o resultado, informando canal e oferta: é o que ensina o sistema.
cuidado: "Calibrado" significa apenas 3 ou mais interações com aquela combinação: é um número pequeno. A justificativa agora diz isso com todas as letras: a taxa é a média daquela combinação em todos os perfis, não só nos parecidos.
fontes:
- backend/model/bandit.py::recomendar
- backend/model/bandit.py::LinUCB
- backend/model/bandit.py::construir_contexto
constantes:
- backend/model/bandit.py::D = 14

## registrar-contato
titulo: Registrar contato com o devedor
perfis: operador, admin, comando
telas: Devedor
perguntas:
- como registrar um contato
- o que significa contactado
- o que significa prometeu pagar
- o que acontece quando registro um contato
- registrar contato como pagou confirma o pagamento
- o que é disse que pagou a confirmar
- para que serve o registro de contato
- onde registro que falei com o devedor
- o que cada resultado de contato significa
- registrar contato muda alguma coisa no sistema
curta: Registra canal, resultado e (opcionalmente) a oferta apresentada. Alimenta o histórico do devedor e o aprendizado do sistema.
calculo: Resultados e o que valem para o aprendizado: sem resposta e não quis negociar = 0; contactado = 0,05; prometeu pagar = 0,2. "Disse que pagou" não vale nada na hora: é o que o devedor contou, não um pagamento. Quando o pagamento é confirmado (baixa do administrador, webhook ou sincronização), ele vale valor recuperado ÷ dívida (máximo 1) e é creditado à oferta e ao canal do último contato registrado com oferta. Esses pesos são escolha de projeto.
fazer: Informe sempre a oferta apresentada: é ela que recebe o crédito quando o pagamento for confirmado.
cuidado: "Disse que pagou" não confirma o pagamento da carteira nem entra nos resultados: a confirmação é feita pelo administrador ou chega pela integração. Os pesos 0,05 e 0,2 não vêm de nenhuma fonte externa.
fontes:
- backend/main.py::rota /contatos
- backend/main.py::_CONTATO_RECOMPENSA

## oferta-na-planilha
titulo: Desconto sugerido, valor da proposta e estratégia (planilha e fila)
perfis: operador, admin, comando
telas: Recuperabilidade
perguntas:
- de onde vem o desconto sugerido da planilha
- por que a oferta é igual para toda a carteira
- o que é estratégia de oferta
- por que o desconto sugerido é zero
- diferença entre a oferta da planilha e a da página do devedor
- de onde vêm desconto sugerido e parcelas máximas da planilha
- por que a oferta é a mesma para todos na planilha
- o que é a estratégia de oferta
curta: É a oferta de maior valor esperado entre as quatro padrão, escolhida para a carteira inteira. A análise individual está na página do devedor.
calculo: Para cada devedor: valor esperado de cada oferta = dívida × (1 − desconto) × chance de pagamento da oferta; vence a maior. A verificação de margem não entra aqui, porque a carteira quase nunca traz as despesas.
fazer: Para a análise completa, com margem e o motivo de cada proposta, abra o devedor.
cuidado: Sem feedback por oferta, a de maior valor esperado é sempre a sem desconto, e o sistema avisa na tela. Isso vale para a carteira, não para a pessoa.
fontes:
- backend/main.py::_analisar_df

## catalogo-de-ofertas
titulo: Catálogo de ofertas da empresa
perfis: admin, comando
telas: Ofertas
perguntas:
- como crio uma oferta nova
- posso mudar o desconto das ofertas
- como coloco entrada e juros na oferta
- o que é a família da oferta
- como volto às ofertas padrão
- por que os juros não contam como recuperação
- como funciona a conta da parcela
curta: O admin define as ofertas que a equipe pode fazer (até 20): nome, desconto, entrada, parcelas e juros. As propostas da ficha do devedor e o simulador passam a usar este catálogo.
calculo: Valor negociado = dívida × (1 − desconto). Entrada = valor negociado × entrada%. A parcela segue a tabela Price sobre o saldo (valor negociado − entrada) com os juros do mês; sem juros, saldo ÷ parcelas. Total pago = entrada + parcelas. À vista não tem entrada nem juros. Cada oferta entra automaticamente numa família de aprendizado: à vista até 15% de desconto, à vista acima de 15%, parcelado até 6x e parcelado em 7x ou mais.
fazer: Crie ofertas com nomes que a equipe reconheça ("Feirão 40% à vista") e confira a prévia numa dívida de exemplo. Desative em vez de excluir quando a campanha acabar e quiser reaproveitar depois.
cuidado: Juros compensam o tempo: entram no total pago pelo devedor, mas o valor esperado do banco usa o valor negociado. A chance de pagar de uma oferta nova começa pelo histórico da família dela; o sistema ainda não estima como cada ponto de desconto muda a chance. Sem catálogo salvo, valem as 4 ofertas padrão.
fontes:
- backend/model/oferta.py::calcular
- backend/model/oferta.py::familia
- backend/main.py::put_ofertas
constantes:
- backend/model/oferta.py::MAX_OFERTAS = 20

## alcada-do-operador
titulo: Alçada do operador
perfis: admin, comando
telas: Ofertas
perguntas:
- como limito o desconto que o operador pode dar
- qual o máximo de parcelas que o operador pode oferecer
- o que acontece quando a oferta passa da alçada
- o que é parcela mínima
- como tiro o limite do operador
curta: Limites do operador no simulador "Fazer oferta": desconto máximo, parcelas máximas, parcela mínima e juros mínimos. Fora deles, a oferta aparece em vermelho e não pode ser confirmada.
calculo: Cada limite é comparado com a oferta montada: desconto acima do máximo, parcelas acima do máximo, parcela abaixo do mínimo (só parcelado) e juros abaixo do mínimo (só parcelado). Campo vazio é sem limite.
fazer: Defina a alçada antes de liberar o simulador para a equipe. Ofertas fora dela continuam possíveis pelo administrador ajustando o catálogo.
cuidado: A alçada vale para o simulador e para o registro da oferta (o servidor confere de novo ao gravar); não muda as propostas sugeridas da ficha, que seguem o catálogo.
fontes:
- backend/model/oferta.py::fora_da_alcada
- backend/model/oferta.py::validar_alcada

## simulador-de-oferta
titulo: Fazer oferta (simulador)
perfis: operador, admin, comando
telas: Devedor
perguntas:
- como sei se a oferta é boa
- a oferta é boa para o banco
- essa parcela cabe no bolso do devedor
- o que significa atenção na oferta
- por que não consigo confirmar a oferta
- de onde vem a chance de pagar da oferta
- como monto uma oferta diferente do catálogo
curta: Na ficha do devedor, monte a oferta (desconto, parcelas, entrada e juros), partindo de uma oferta da empresa ou do zero. O sistema analisa na hora se ela é boa para quem paga e para o banco.
calculo: Para quem paga: Boa se a parcela cabe na parcela máxima (margem livre × teto das Premissas); Ruim se passa; Atenção se não dá para verificar (sem despesas) ou se a entrada passa da sobra do mês. À vista é Boa quando cabe na sobra de um mês; senão Atenção (depende de reserva). Para o banco: valor esperado = valor negociado × chance de pagar da família da oferta, comparado com o da melhor oferta do catálogo (a melhor que cabe no bolso ou a melhor à vista; sem margem, a de maior valor esperado). Boa a partir de 95%, Atenção de 80% a 95%, Ruim abaixo de 80% ou abaixo do que a venda da dívida renderia (dívida × cessão das Premissas, quando informada). Juros não entram no valor esperado. A análise geral é a pior das duas; fora da alçada é Ruim.
fazer: Comece pela oferta sugerida, ajuste com o devedor na conversa e confira os dois lados antes de fechar. Se as despesas forem declaradas na ligação, informe em Propostas: a análise refaz a margem na hora. Depois de fazer a oferta, use "Confirmar que fiz esta oferta": escolha o canal e a resposta. Aceitou vira contato "Prometeu pagar" e promessa na Agenda (valor do primeiro pagamento); Vai pensar vira retorno na Agenda; Recusou fica no histórico. A oferta completa aparece em "Ofertas feitas a este devedor", e o contato ensina a IA com a família da oferta.
cuidado: Os limites de 95% e 80% são escolha de projeto. A chance de pagar é a da família da oferta e ainda não muda com cada ponto de desconto. Oferta fora da alçada não pode ser confirmada.
fontes:
- backend/model/oferta.py::analisar
- backend/main.py::simular_oferta
- backend/main.py::registrar_oferta
constantes:
- backend/model/oferta.py::LIMIAR_BOA = 0.95
- backend/model/oferta.py::LIMIAR_ATENCAO = 0.80
