# Revisão do fluxo dos agentes — 22/10/2026

Revisão motivada por demora do Negociador e respostas que encerravam o atendimento automático. Sem identificador de um caso de produção, o diagnóstico abaixo é de código e de cenários reproduzidos com repositório e provedor simulados. Não é uma medição da latência real da IA.

## Causas encontradas e correções

| Problema | Correção |
|---|---|
| Cada sinal do escritório aguardava uma gravação no banco durante a resposta. | Publicador observacional com uma thread por processo e fila limitada a 128 entradas. Substitui snapshots pendentes do mesmo evento pelo mais recente. A conversa não espera a gravação; sinais podem ser descartados sob carga. Não altera decisões nem situação do evento. |
| O envio pela tela podia processar cinco eventos da empresa, inclusive de outros clientes. | Processa um evento pronto do caso selecionado. Preserva prioridades, reservas e ordem da fila existente. Se houver trabalho anterior do mesmo caso, a mensagem enviada permanece na fila. |
| Repetições internas do transporte/SDK multiplicavam o tempo de espera na mesma requisição. | Uma tentativa HTTP por chamada. Indisponibilidade, timeout e cota retornam ao mecanismo existente de espera e checkpoint. Erro permanente Gemini não repete o mesmo nó imediatamente. |
| A passagem humana dependia de um resumo opcional por IA. | Ficha estruturada e resumo montados imediatamente pelo código. A geração opcional continua disponível; a revisão de tom do Supervisor permanece. |
| Uma falha técnica podia colocar o caso com uma pessoa sem registrar demanda na Agenda. | Todos os grafos usados pela API registram a passagem antes de confirmar a transferência. Se a gravação falhar, o evento segue o tratamento de repetição/falha da fila, sem prometer atendimento não registrado. |
| A consulta real da Agenda omitia a observação usada para identificar avisos existentes. | Inclui o campo e reutiliza a demanda de transferência pendente encontrada na consulta. Evita duplicação em repetição do mesmo pedido; não adiciona uma restrição única no banco. |
| A conversa não buscava a resposta após uma espera técnica e podia mostrar erro definitivo enquanto o evento estava pendente. | Consulta o evento mais recente diretamente por empresa e caso; a tela atualiza a cada cinco segundos enquanto há evento pendente/processando, sem reenviar a mensagem. Mostra estados distintos de espera e atendimento humano. |

O publicador grava apenas o campo `dados` do evento, preservando o payload de entrada capturado pelo observador. A escrita é condicionada à empresa, evento, trace e timestamp para não substituir um snapshot mais novo. Esse filtro foi conferido por teste de construção da consulta, sem executar UPDATE em dados reais.

## Regras preservadas

- Confirmação de identidade, política financeira, Auditor e registro de aceite.
- Pedido explícito de uma pessoa, contestação, suspensão e sinais de risco.
- Aprovação administrativa das reuniões e controle manual para devolver o caso ao agente.
- Limites existentes de chamadas, esperas de IA e falhas da fila. Após esgotar as esperas, a equipe recebe a demanda.
- Nenhuma alteração de modelo, credencial, política financeira ou esquema do banco.

## Regressões persistentes e validação

`backend/test_agente_latencia.py`: 16 testes, cobrindo observabilidade lenta/fila cheia, escrita isolada, uma tentativa de transporte, SDK sem repetição oculta, consulta por caso, mensagem na fila, isolamento de clientes, falha com demanda humana, falha de gravação sem falsa confirmação, passagem sem IA opcional, falha em vencimento e deduplicação.

`frontend/tests/conversa.ui.mjs` (`npm run test:conversa:ui`): navegador com API simulada. Confere mensagem pendente, recuperação automática da resposta, somente um envio, ausência de erro definitivo durante espera e manutenção do controle humano. Passou sem erros JavaScript.

`python -m agente.bateria --sem-gravar`: **87/87 cenários e 249 verificações aprovados**, provedor falso, sem custo de IA. O cenário do Supervisor foi atualizado para exigir a ficha/resumo imediatos sem chamada opcional durante a passagem. Os testes unitários do Supervisor continuam verificando separadamente a geração opcional e suas validações.

Também passaram os testes de orquestrador, transferência indevida, Supervisor, estação, escritório, conversa, Acompanhador, Agenda humana, LLM, Gemini, manipulação, fluxo do devedor, disponibilidade, ferramentas, triagem, Estrategista, Acompanhador com IA e base de conhecimento. Build de produção do frontend aprovado.

Para reproduzir os novos testes, na pasta `backend`:

```powershell
python test_agente_latencia.py
python test_agente_supervisor.py
python -m agente.bateria --sem-gravar
```

A regressão de navegador usa Playwright disponível no ambiente (`MIZAN_PLAYWRIGHT_MODULE`) e opcionalmente um canal instalado (`MIZAN_BROWSER_CHANNEL=msedge`), seguindo o padrão dos testes do escritório.

## Limites da validação

A bateria usa IA e banco simulados. A suíte HTTP completa e a parte HTTP do teste de passagem não foram concluídas neste ambiente porque faltam dependências de servidor, começando por `uvicorn`; as dependências de produção não foram alteradas. Dependências de busca foram instaladas apenas em diretório temporário de QA para executar os cenários de conhecimento.

Não houve chamada paga à IA nem alteração de atendimento real. Tempos do provedor, banco, inicialização do servidor e periodicidade do worker ainda influenciam a espera. O polling da tela consulta o resultado; quem processa eventos adiados continua sendo o worker/agendador existente. Não há promessa de resposta em um número fixo de segundos.
