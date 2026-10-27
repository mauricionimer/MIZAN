# Arquitetura do Mizan

## Resposta direta: qual é o framework dos agentes?

Os agentes do Mizan usam um **motor próprio em Python**, implementado em `backend/agente/orquestrador.py`. Ele modela a execução com grafos de nós, arestas condicionais e contexto compartilhado. A abordagem se inspira nos conceitos do LangGraph, mas o projeto **não instala nem depende de LangChain ou LangGraph**.

O motor próprio cuida de fila de eventos por prioridade, bloqueio por caso, idempotência, checkpoints, novas tentativas controladas, espera por capacidade de IA e encaminhamento para atendimento humano quando necessário.

## Camadas do sistema

| Camada | Estrutura usada | Responsabilidade |
| --- | --- | --- |
| Interface | React 18, Vite, React Router, Tailwind CSS | Painéis de carteira, agenda, pastas, agentes, autenticação e relatórios. |
| API | Python 3.12, FastAPI, Pydantic, Uvicorn | Endpoints, autorização, validações, tarefas de fundo e regras de negócio. |
| Agentes | Grafos e orquestrador próprios | Coordena triagem, negociação, auditoria, estratégia, acompanhamento e supervisão. |
| IA | Adaptadores para Gemini e Anthropic; cliente falso nos testes | Geração, classificação e uso de ferramentas dentro das regras do produto. |
| Dados | Supabase/Postgres e conectores externos | Carteiras, conversas, acordos, agenda, logs e integrações de bancos/planilhas. |
| Inteligência de dados | Pandas, scikit-learn, joblib | Predição, recuperabilidade, recomendações e avaliação de estratégias. |
| Segurança | JWT, criptografia Fernet, guardrails e auditor | Controle de acesso, sigilo, autorização de ações e proteção contra instruções indevidas. |
| Operação | Logs estruturados, trace ID, métricas por etapa | Diagnóstico, custo/tokens, tempo de resposta, erros e repasse à equipe. |
| Entrega | Vercel, Render e GitHub Actions | Frontend, API, verificação de disponibilidade e publicação contínua. |

## Estrutura dos agentes

1. **Orquestrador** recebe eventos e decide a próxima etapa no grafo.
2. **Triagem** classifica intenção e risco antes de qualquer ação.
3. **Negociador** conversa com o devedor e conduz a negociação com propostas permitidas.
4. **Auditor** aplica políticas e autoriza ferramentas; a IA não movimenta valores nem cria acordos sem esse controle.
5. **Estrategista** prioriza casos e define a abordagem de cada contato.
6. **Acompanhamento** monitora promessa, vencimento, pagamento e situação do acordo.
7. **Supervisor** prepara o contexto para revisão e atendimento humano quando o caso exige uma pessoa.
8. **Cientista** calcula e explica cenários com dados e evidências, sempre sujeito à aprovação adequada.

## Ciclo de uma conversa

`evento → prioridade → bloqueio do caso → triagem → regras de segurança → negociação ou atendimento humano → ferramentas autorizadas → auditoria → checkpoint e log`

O fluxo preserva `trace_id`, contexto do caso, resultado, versão de política, tempo, consumo e ocorrências de falha. Assim, uma conversa pode ser entendida, reprocessada com segurança e entregue à equipe com o contexto necessário.

## Limites importantes

- A IA pode sugerir texto, classificar uma intenção e solicitar ferramentas; não substitui as regras de autorização.
- Dados pessoais são mascarados antes de seguirem para modelos de IA.
- Valores e condições vêm das simulações e regras do sistema, não de uma resposta livre do modelo.
- Falhas persistentes, pedidos de pessoa ou situações sensíveis são encaminhados para atendimento humano com resumo do caso.

Consulte também [`FLUXO_AGENTES.md`](FLUXO_AGENTES.md) para a documentação operacional detalhada de entradas, lógica e saídas de cada agente.

