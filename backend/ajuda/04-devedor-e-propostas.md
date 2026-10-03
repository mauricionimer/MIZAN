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
curta: É a dívida total dividida pela renda mensal estimada, mostrada em porcentagem.
calculo: comprometimento = valor da dívida ÷ renda estimada, limitado a 10 vezes (1.000%) no modelo. Sem renda, vale 0 no modelo.
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
curta: É quanto do mês sobra para o devedor pagar uma parcela, depois das despesas e de uma folga de segurança.
calculo: margem livre = (renda − despesas mensais) × (1 − buffer%). O buffer padrão é 30%. Se as despesas ou a renda não forem informadas, a margem fica indisponível: o sistema não estima despesas.
fazer: Informe as despesas na hora da conversa (campo na seção de propostas) ou inclua a coluna despesas_mensais na carteira.
cuidado: Sem margem, nenhuma parcela é marcada como "cabe no bolso" e nenhuma proposta é sugerida, de propósito: sugerir sem saber se cabe é pior que não sugerir. O buffer de 30% vem do material de referência, mas é regra do banco; ele pode ser ajustado por empresa (hoje só pela API).
revisar: achado E1 (premissas sem tela).
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
curta: Sugere por qual canal (WhatsApp, telefone, carta/e-mail) e com qual oferta abordar este devedor, e vai melhorando com os resultados registrados.
calculo: São 12 combinações (3 canais × 4 ofertas). Um algoritmo de aprendizado por reforço (LinUCB) pontua cada uma com a estimativa de retorno para o perfil do devedor mais um bônus de exploração (peso 1,0) para as combinações pouco testadas. O contexto tem 14 números: score, dias de atraso, comprometimento, produto, região e renda. O estado de aprendizado é separado por empresa. Modos: "exploração inicial" (sem nenhum feedback), "aprendendo" (menos de 3 interações com a combinação) e "calibrado" (3 ou mais).
fazer: Registre o contato e o resultado, informando canal e oferta: é o que ensina o sistema.
cuidado: "Calibrado" significa apenas 3 ou mais interações com aquela combinação: é um número pequeno. A justificativa mostra a taxa média daquela combinação em todos os perfis, não só nos parecidos.
revisar: achado T2 e D2 (texto "perfis similares" e aprendizado offline).
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
- para que serve o registro de contato
curta: Registra canal, resultado e (opcionalmente) a oferta apresentada. Alimenta o histórico do devedor e o aprendizado do sistema.
calculo: Resultados e o que valem para o aprendizado: sem resposta e não quis negociar = 0; contactado = 0,05; prometeu pagar = 0,2; pagou = valor recuperado ÷ dívida (máximo 1). Esses pesos são escolha de projeto.
fazer: Informe sempre a oferta apresentada: é ela que é creditada no aprendizado.
cuidado: Marcar "Pagou" no contato não confirma o pagamento da carteira: a confirmação é feita pelo administrador. E os pesos 0,05 e 0,2 não vêm de nenhuma fonte externa.
revisar: achado D11 (um operador pode marcar "Pagou" no contato sem confirmar o pagamento).
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
curta: É a oferta de maior valor esperado entre as quatro padrão, escolhida para a carteira inteira. A análise individual está na página do devedor.
calculo: Para cada devedor: valor esperado de cada oferta = dívida × (1 − desconto) × chance de pagamento da oferta; vence a maior. A verificação de margem não entra aqui, porque a carteira quase nunca traz as despesas.
fazer: Para a análise completa, com margem e o motivo de cada proposta, abra o devedor.
cuidado: Sem feedback por oferta, a de maior valor esperado é sempre a sem desconto, e o sistema avisa na tela. Isso vale para a carteira, não para a pessoa.
fontes:
- backend/main.py::_analisar_df
