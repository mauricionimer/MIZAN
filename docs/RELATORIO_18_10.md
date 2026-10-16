# Relatório quinzenal — 18/10/2026 (rascunho)

Texto pronto para colar no formulário do AKCIT Camp. Os quatro campos pedidos
pelo edital: metas, se foram cumpridas, o que impediu e link de evidência.

---

## Metas da quinzena

1. Definir a arquitetura dos agentes do Mizan com base no curso (tipos de
   agente, orquestração, memória, LGPD, guardrails e LLMOps).
2. Construir a base: estado de cada caso, fila de eventos, orquestrador,
   rastreio de cada passo e controle de custo de IA.
3. Construir o Auditor (política do banco com versão), as ferramentas do
   negociador, a Triagem e o Negociador, testados sem custo de IA.
4. Ter uma tela de demonstração com a conversa e o porquê de cada decisão.

## As metas foram cumpridas?

Sim, as quatro, com testes automáticos. O que existe hoje:

- **Orquestrador em código**, modelado como grafo de estados (conceitos do
  LangGraph): fila com prioridade, o mesmo evento nunca é processado duas vezes,
  um atendimento por caso de cada vez, retomada do ponto em que parou e caminho
  de erro que passa o caso para uma pessoa.
- **Auditor em código, com a palavra final**: toda ação do agente é conferida
  contra a política do banco (desconto, parcelas, entrada, horário, frequência,
  datas e remarcações) e fica registrada a regra que decidiu e a versão da
  política.
- **Triagem**: o que não pode errar (pedido para parar, pessoa errada, "não
  reconheço a dívida", pedido de atendente, tentativa de manipulação, sinais de
  sofrimento) é decidido por regras, sem IA; o resto vai para um modelo barato.
- **Negociador** com 14 ferramentas: confirma a identidade antes de falar de
  valores, simula antes de propor, pergunta quanto cabe no bolso e só registra
  um acordo a partir de uma simulação feita pelo sistema.
- **Travas no texto de saída**: nenhum valor que não tenha vindo de uma
  simulação, nada de ameaça ou constrangimento (Código de Defesa do Consumidor,
  art. 42), nada de CPF ou dado interno.
- **LGPD**: a IA recebe só o primeiro nome e os valores depois da confirmação
  de identidade; a primeira mensagem diz que é um assistente virtual; o devedor
  pode pedir uma pessoa a qualquer momento.
- **Tela do Agente e Central de orquestração** no Mizan: a conversa de um lado
  e, do outro, cada passo com a regra aplicada, o tempo e o custo.

## O que impediu ou atrasou

- Ainda não conversamos com uma IA real: até aqui tudo foi testado com um
  cliente simulado, de propósito, para não gastar o orçamento de IA (US$ 10)
  durante o desenvolvimento. A primeira conversa real está marcada para 19/10.
- Falta a validação com quem trabalha com cobrança: as conversas ainda não
  aconteceram.

## Próxima quinzena

Acompanhamento (datas e pagamentos), Estrategista com grupo de controle
sorteado, bateria de cenários com nota, primeira rodada com IA real, demo de
ponta a ponta e entregáveis do regional (fluxo, BMC, pitch).

## Link de evidência

https://github.com/mauricionimer/AGENTESMIZAN
