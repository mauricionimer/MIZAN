# Fluxo dos agentes do Mizan

Este documento descreve os fluxos implementados, incluindo entradas, lógica, saídas, motivos da divisão de responsabilidades e salvaguardas.

## Princípios de operação

- **Um caso por vez:** o Orquestrador reserva o evento e trava o caso para impedir ações concorrentes.
- **IA não autoriza dinheiro:** a IA interpreta e redige; o Auditor decide em código se a ação pode acontecer.
- **Falha não vira improviso:** uma etapa recebe nova tentativa segura; persistindo a falha, a equipe recebe o caso com contexto.
- **Dados mínimos:** dados sensíveis não chegam completos à IA e os logs técnicos não guardam texto de conversa.
- **Pessoa tem a palavra final:** a equipe pode assumir, devolver e aprovar recomendações de alcance operacional.

## Visão geral

```text
Evento -> Orquestrador -> grafo adequado -> agentes especializados
                                      |            |
                                      |            +-> Auditor e Travas
                                      v
                              checkpoint/trace -> resultado ou Agenda da equipe
```

Os eventos são mensagens do devedor, vencimentos, pagamentos, abordagens, contestações e pedidos para parar contato. Parar contato e contestação têm prioridade sobre mensagens, que têm prioridade sobre eventos de relógio.

## Orquestrador

| Item | Detalhe |
|---|---|
| Entradas | Evento, caso, data/hora, política ativa, disponibilidade da IA e checkpoint. |
| Lógica | Reserva fila, trava caso, seleciona o grafo, executa um nó por vez e grava checkpoint. |
| Saídas | Evento feito, adiado/pendente ou caso encaminhado; toda rodada recebe `trace_id`. |
| Por que | Evita duplicidade e conflito em uma operação que dura dias ou semanas. |

Cada etapa recebe até duas tentativas. Falhas finais transferem o caso. IA ocupada adia o evento, teto diário espera a virada em Brasília e reservas vencidas retornam à fila.

## Triagem

| Item | Detalhe |
|---|---|
| Entradas | Mensagem mascarada, data atual e última fala do agente quando necessária para contexto. |
| Lógica | Aplica regras determinísticas primeiro; nos demais casos usa IA com JSON validado. |
| Saídas | Intenção, confiança, valores/datas citados, emoção, urgência, ironia, risco e semáforo. |
| Por que | Roteamento e segurança precisam ser rápidos e regras críticas não podem depender apenas de IA. |

As intenções incluem negociar, informar pagamento, contestar, parar contato, pessoa errada, pedir pessoa, dúvida e outro. Sinais críticos vão para uma rota segura antes de qualquer negociação; a leitura relevante alimenta o caderno do caso.

## Negociador

| Item | Detalhe |
|---|---|
| Entradas | Triagem, estado, histórico compacto, estratégia, ofertas permitidas, agenda e base de conhecimento. |
| Lógica | Usa IA e ferramentas de esquema fixo para simular acordo, confirmar identidade, registrar compromisso, consultar conhecimento e pedir pessoa. |
| Saídas | Resposta pronta, ações executadas/propostas e notas objetivas no caderno. |
| Por que | Linguagem e contexto são necessários para conversar; efeitos reais precisam de ferramenta verificável. |

Ele não inventa valores, leis ou ações. A resposta passa por Travas e Auditor. Se a resposta é barrada, há reescrita; se o problema se repete, o caso é encaminhado.

A primeira abordagem não fala de dívida, pendência, valor ou proposta. Ela se apresenta como assistente virtual, confirma se está falando com a pessoa certa e explica que a pergunta protege a privacidade. Depois da confirmação, o Negociador conduz para o pagamento de forma respeitosa: pergunta se a pessoa prefere entender o que está em aberto ou ver uma opção que caiba no momento dela. Só então simula e apresenta condições.

## Auditor

| Item | Detalhe |
|---|---|
| Entradas | Ação proposta, parâmetros, situação, política versionada, frequência, simulação e data/hora. |
| Lógica | Verifica situação, horário, frequência, identidade, desconto, parcelas, entrada, datas, remarcações e simulação. |
| Saídas | `permitida`, regra aplicada, versão da política e motivo. |
| Por que | Autorização financeira precisa ser reproduzível, auditável e independente da IA. |

Sem política ativa, somente ações de segurança passam. Aceite exige identidade confirmada e simulação válida do mesmo caso com as mesmas condições.

## Travas e ferramentas

As **Travas** verificam valores, percentuais, parcelas, tom, CPF, instruções de sistema, fontes legais e afirmações de ações. As **Ferramentas** realizam efeitos reais: simular/registrar acordo, suspender cobrança, abrir contestação, agendar retorno, registrar pagamento informado, transferir para humano, consultar base e registrar contato. Essa divisão impede que texto gerado pela IA seja tratado como fato.

## Estrategista

| Item | Detalhe |
|---|---|
| Entradas | Carteira, atraso, valor, histórico, política, recomendações aprovadas e desempenho do bandit. |
| Lógica | Classifica casos, mantém grupo sorteado e pode orientar tom, canal, oferta inicial ou adiamento. Seleção e sorteio seguem em código. |
| Saídas | Grupo, prioridade, canal, oferta inicial, motivo e evento de abordagem quando necessário. |
| Por que | Separa plano da conversa e permite medir se a estratégia melhora a recuperação. |

A IA é opcional e possui reserva em código. O Estrategista só usa recomendações do Cientista após aprovação humana.

## Acompanhamento

| Item | Detalhe |
|---|---|
| Entradas | Agenda, acordo/promessa, pagamentos, estado, política, histórico e leitura da Triagem. |
| Lógica | Confere o que vence, respeita janela de contato e decide lembrar, esperar, procurar, remarcar ou chamar pessoa. |
| Saídas | Lembrete, novo evento, registro de pagamento, situação atualizada ou demanda humana. |
| Por que | Promessa, atraso e pagamento definem o próximo passo melhor do que uma mensagem isolada. |

Após o primeiro pagamento confirmado, o fluxo indica pagamento em andamento. Sem resposta após as esperas permitidas, o caso vai para a equipe com motivo e contexto.

## Supervisor

| Item | Detalhe |
|---|---|
| Entradas | Caderno, histórico recente, leitura da Triagem, ofertas feitas e sugestão calculada. |
| Lógica | Monta ficha de passagem; pode usar IA para resumo, mas valida campos, limites e números. Revisa tom em conversa delicada. |
| Saídas | Resumo para Agenda/equipe com situação, pedido, emoção, prioridade e próximo passo; ou orientação de reescrita. |
| Por que | A equipe recebe contexto acionável sem reler toda a conversa nem herdar números inventados. |

Sem IA, a ficha calculada permanece disponível. O sistema não trata ausência de revisão como aprovação automática.

## Cientista

| Item | Detalhe |
|---|---|
| Entradas | Observações consolidadas, métricas do bandit, resultados de acordos e sinais de passagens humanas. |
| Lógica | Calcula comparações em código; IA apenas redige hipóteses e recomendações baseadas nesses resultados. |
| Saídas | Relatório, hipóteses, selo de evidência e recomendação pendente de aprovação. |
| Por que | Aprende com resultado real sem autorizar sozinho mudanças de política. |

## Passagem para atendimento humano

O caso vai para a equipe quando há pedido de pessoa, sofrimento grave, contestação, reprovação repetida nas Travas, esgotamento de tentativas ou necessidade identificada pelo Acompanhamento. A transferência cria demanda na Agenda com prioridade, motivo e próximo passo. Operadores podem assumir ou devolver o caso.

## Observabilidade e falhas

Cada evento possui trace; cada etapa guarda agente, nó, resultado, duração, modelo, tokens, custo, regra e versão de política. O monitoramento operacional registra, sem conteúdo da conversa: falha de etapa, nova tentativa, reserva em código quando a IA falha, espera de IA, teto de custo, falha final, encaminhamento humano e evento definitivamente falho.

A persistência desses logs requer `backend/sql/migracao_logs_agentes.sql`.

## Mapa de responsabilidade

| Necessidade | Responsável | Salvaguarda |
|---|---|---|
| Entender mensagem | Triagem | Regras de segurança e formato validado |
| Conversar/propor | Negociador | Ferramentas, Travas e Auditor |
| Autorizar ação | Auditor | Política versionada em código |
| Planejar abordagem | Estrategista | Grupo sorteado e aprovação humana |
| Cuidar de datas/pagamentos | Acompanhamento | Agenda, política e estado |
| Resumir/revisar | Supervisor | Ficha calculada e números validados |
| Aprender | Cientista | Evidência e aprovação humana |
| Coordenar | Orquestrador | Trava, idempotência, checkpoint e logs |
