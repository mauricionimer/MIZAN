# Plano de execução — os agentes do Mizan

Escrito em 15/10/2026, depois da leitura completa do ebook do curso AKCIT
("Agentes de IA", 13 capítulos). Complementa o `PLANO_AGENTE.md`: aquele diz
**o quê e por quê**; este diz **como construir**, peça por peça. Cada decisão
cita o capítulo do curso em que se apoia — é o vocabulário que a banca usa.

**Regras que não mudam:** custo de IA até US$ 10; nenhuma escrita minha no
Supabase de produção (o SQL você roda); testes sem dado real; suíte inteira
passando antes de publicar.

**Partes:** [Parte 1 — preparar o terreno](PARTE1_TERRENO.md) (16/10).

---

## 1. O ambiente do agente (cap. 1.3)

O curso manda começar especificando o ambiente, porque ele decide a arquitetura.

| Dimensão | Cobrança de crédito | Consequência no projeto |
|---|---|---|
| Observabilidade | **Parcial**: não sabemos a renda real nem a intenção do devedor | Estado interno por caso (memória) e perguntas ao devedor |
| Determinismo | **Estocástico**: a mesma oferta dá resultados diferentes | Aprendizado com o resultado (bandit) e grupo sorteado para medir |
| Episódios | **Sequencial**: o que se combina hoje muda o mês seguinte | Acompanhamento de datas e parcelas |
| Dinâmica | **Dinâmico**: pagamentos e mensagens chegam a qualquer hora | Orquestração por eventos, com prioridade |
| Agentes | **Multiagente**: devedor, operador, banco e nossos agentes | Coordenação central e só um agente falando com o devedor |
| Ações | **Discretas**: ofertas do catálogo, datas, transferências | Ferramentas com esquema fixo, conferidas pelo Auditor |

## 2. Os agentes e o tipo de cada um (cap. 1.4 e 2)

| Agente | Tipo, nos termos do curso | Camada (cap. 2.3) | Usa IA de linguagem? |
|---|---|---|---|
| Orquestrador | Coordenador central — padrão *planner* / supervisor-trabalhador (cap. 2.5, 7.3.2) | Coordenação | Não (código) |
| Triagem | Classificador de entrada com saída estruturada; "modelo menor para pedidos simples" (cap. 11.4) | Reativa | Sim, modelo barato |
| Estrategista | **Baseado em utilidade**: escolhe pela função valor esperado − custo do contato (cap. 1.4) | Deliberativa | Só para resumir o plano |
| Negociador | **Baseado em objetivos**, com estado do caso e **ferramentas** (cap. 1.4, 2.5) | Deliberativa | Sim, modelo principal |
| Auditor | Guardrail de política; "checagens e balanços" (cap. 9.4, 7.3.3) | Coordenação | Não (código) |
| Acompanhamento | **Reflexo baseado em modelo**: regras condição-ação sobre datas, com estado (cap. 1.4, 2.2) | Reativa | Não; aciona o Negociador |
| Aprendizado | **Agente de aprendizagem** (cap. 1.4): elemento de aprendizado = atualização do bandit; elemento crítico = dinheiro que entrou − custo, e o grupo sorteado; elemento de desempenho = Estrategista e Negociador; gerador de problemas = exploração do bandit e sorteio | Deliberativa (lenta) | Não |
| Pessoa (operador) | *Human-in-the-loop* (cap. 7.4.2, 9.4) e revisão humana da LGPD (art. 20) | — | — |

Por que vários e não um: entrada, ritmo e risco diferentes (cap. 3.3 —
especialização melhora qualidade; cada um testado sozinho; IA só onde há
linguagem, o que controla custo).

## 3. Arquitetura híbrida em camadas (cap. 2.3)

```
CAMADA DE COORDENAÇÃO   Orquestrador (estado, prioridade, autonomia, rastreio)
                        Auditor (política da empresa, versão, regra aplicada)
          │
CAMADA DELIBERATIVA     Estrategista (plano do dia)  ·  Negociador (conversa)
                        Aprendizado (o que funciona para cada perfil)
          │
CAMADA REATIVA          Triagem (entende a mensagem na hora)
                        Acompanhamento (vence amanhã, pagou, não pagou, "já paguei")
```

A camada reativa age rápido e tem prioridade quando o caso pede (pedido para
parar, contestação, "já paguei"); a deliberativa planeja; a coordenação decide
quem age e resolve conflitos — exatamente a divisão do cap. 2.3.

## 4. Orquestração como grafo de estados (cap. 7.5 e 8.6)

### 4.1 Decisão: orquestrador próprio, modelado como grafo

O curso apresenta quatro caminhos (cap. 8.6): manual, CrewAI, LangGraph e
Mangaba. **Recomendação: orquestrador próprio dentro do FastAPI, desenhado com
os conceitos do LangGraph** — estado, nós, arestas, checkpoint e nó de erro.

- Um caso de cobrança dura semanas e espera eventos externos (pagamento, data,
  resposta). O estado já mora no Supabase, que vira o próprio *checkpoint*.
- O Auditor precisa ser código no servidor, com a palavra final.
- O servidor gratuito tem 512 MB (`limite.py` já documenta isso); nenhuma
  dependência pesada nova.
- O cap. 8.6.1 aceita a orquestração manual, e o edital avalia "a qualidade da
  aplicação, e não a ferramenta".
- Como os conceitos são os mesmos, migrar para LangGraph depois é direto. Se
  você preferir usar LangGraph já, a decisão é sua; o custo é mais dependências
  e uma conexão direta ao Postgres para o *checkpointer*.

### 4.2 O estado do caso (cap. 7.5.1)

Uma linha por devedor em atendimento: situação (novo, só lembrete, em contato,
negociando, acordo ativo, atrasado, pagamento em conferência, contestado,
suspenso, com pessoa, quitado, quebrado), grupo do Estrategista, grupo sorteado
(sim/não), próxima data, tentativas, versão da política vigente, resumo da
conversa e último passo concluído.

### 4.3 Grafo de uma mensagem do devedor

```
receber ─► triagem ─┬─ parar contato / pessoa errada ─► suspender ─────────► FIM
                    ├─ contestar ──────────────────────► contestação ─► pessoa
                    ├─ "já paguei" ────────────────────► pagamento informado ─► FIM
                    ├─ manipulação ─► (segue, com alerta; nada muda na política)
                    └─ pagar / negociar ─► briefing (memória + RAG)
                                              │
                                              ▼
                               negociador ⇄ ferramentas ── cada ação ─► auditor
                                              │
                                              ▼
                                   conferência da resposta ─┬─ ok ─► enviar ─► FIM
                                                            └─ falhou ─► 1 nova tentativa ─► pessoa
nó de erro (qualquer nó): tempo-limite → 1 nova tentativa → pessoa com resumo
```

### 4.4 Outros grafos

- **Dia** (relógio): Estrategista monta o plano → Acompanhamento gera lembretes
  e eventos de vencimento → o que precisa de conversa entra como objetivo para o
  Negociador.
- **Pagamento**: evento do banco → ligar à promessa ou parcela → Aprendizado
  registra o dinheiro que entrou → agradecer → agendar o próximo lembrete.

### 4.5 Contratos entre agentes (cap. 7.4.2 e 7.4.3)

O curso recomenda gastar 80% do esforço definindo as tarefas e os *handoffs*.
Cada passagem tem formato fixo (JSON validado):

| De → para | Formato |
|---|---|
| Triagem → Orquestrador | `intencao`, `confianca`, `valores_citados`, `datas_citadas`, `sinais_de_risco` |
| Estrategista → Orquestrador | por caso: `grupo`, `motivo`, `canal`, `oferta_sugerida`, `prioridade` |
| Orquestrador → Negociador | `briefing`: estado, histórico resumido, objetivo, ofertas permitidas, limites |
| Negociador → Auditor | `acao` proposta com parâmetros (ex.: `registrar_aceite` + `simulacao_id`) |
| Auditor → Orquestrador | `permitida`, `regra`, `versao_politica`, `motivo` |
| Acompanhamento → Negociador | `objetivo` (ex.: "entender por que não pagou e remarcar dentro da regra") |

## 5. Filas, cache e limites sem Redis nem RabbitMQ (cap. 7.1, 7.2, 8.3, 8.4)

O curso ensina os conceitos com Redis e RabbitMQ. No volume do protótipo, o
mesmo efeito sai de graça com o que o Mizan já tem:

| Conceito do curso | Como fica no Mizan (custo zero) |
|---|---|
| Fila de tarefas | Tabela de eventos com situação (pendente, processando, feito, falhou) |
| Worker / consumidor | Agendador que **já roda dentro do servidor** (`scheduler.py`, APScheduler) e os próprios endpoints |
| Confirmação manual (*ack*) | Evento só vira "feito" depois de registrado o resultado |
| Idempotência | Chave única por evento e por ação (restrição UNIQUE no banco) |
| *Dead letter queue* | Evento que falha duas vezes vira "falhou" e aparece na Central de orquestração |
| Um por vez (*prefetch*) | Trava por caso com atualização condicional (o padrão já usado na Agenda) |
| Cache com validade (TTL) | Simulação com identificador e prazo de validade; briefing em memória por poucos minutos |
| *Rate limiting* | `limite.py` (já existe) + frequência por devedor e teto de custo no orquestrador |
| Servidor acordado | O GitHub Actions já faz um ping a cada 8 minutos (`keepalive.yml`) |

Quando trocar: com mais de uma instância do servidor ou volume alto, entram
Redis (cache e limite compartilhados) e uma fila dedicada.

## 6. Memória e RAG (cap. 5 e 6)

| Tipo de memória (cap. 6.1) | No Mizan |
|---|---|
| Curta duração | Últimas mensagens da conversa + resumo das antigas (cap. 6.2.3) |
| Episódica | Linha do tempo do caso: eventos com data e origem |
| Semântica | Política da empresa (com versão), catálogo e alçada, roteiros aprovados, Central de Ajuda |
| Procedimental | As ferramentas e as regras do Auditor |
| Aprendizado | Parâmetros do bandit por empresa |

**RAG = recuperação estruturada + base de conhecimento.**

- Fatos do caso vêm por **filtro de metadados** (empresa e caso), não por
  semelhança — mais preciso e separa as empresas (cap. 5.5.2, multi-tenancy).
- Dúvidas sobre regras usam a **busca da Central de Ajuda que já existe**
  (`ajuda_busca.py`, local, com medida de certeza). O acervo é pequeno (sete
  arquivos); o cap. 5.4.2 aceita busca exata abaixo de dez mil itens.
- **Sem banco vetorial no protótipo.** Próximo passo, quando o acervo crescer:
  pgvector no próprio Supabase (cap. 5.3.3). Embeddings não rodam no servidor
  de 512 MB.
- **Janela de contexto**: o Negociador recebe um briefing compacto, não o
  histórico inteiro; as partes fixas (instruções, ferramentas) usam cache de
  prompt para reduzir custo.
- **Correção de memória** (cap. 6.3.3): fato novo desativa o antigo (versão),
  em vez de apagar sem rastro.

## 7. LGPD aplicada (cap. 6.5 e 10.4)

| Item do checklist | Como fazemos |
|---|---|
| Minimização | A IA recebe primeiro nome, valores, datas e situação. Nunca CPF completo, endereço ou renda; o simulador usa a renda no código |
| Pseudonimização | Identificador do caso no prompt; a ligação com a pessoa fica só no banco |
| Transparência | Primeira mensagem diz que é o assistente virtual do banco |
| Segurança | Escopo por empresa no servidor; segredos em variáveis do Render; logs sem dado pessoal (o padrão `_cpf_no_log` já existe) |
| Direitos do titular | Exportar, corrigir e apagar a memória do caso; retenção com o `model/retencao.py` que já existe |
| Decisão automatizada (art. 20) | O devedor pode pedir uma pessoa a qualquer momento; o motivo de cada decisão fica registrado |
| Transferência internacional | A API da Anthropic processa fora do Brasil: minimização, pseudonimização e cláusula no contrato; Bedrock é alternativa (verificar a região) |
| Documentação | Registro do tratamento e avaliação de impacto (RoPA/DPIA) curtos antes do piloto |
| Dados de teste | Demo e bateria só com dados fictícios (cap. 6.5.7) |

## 8. Guardrails em três pontos (cap. 9.4)

- **Entrada**: a Triagem marca tentativa de manipulação; a mensagem do devedor
  é dado, não instrução; limite de tamanho.
- **Ação**: o Auditor confere alçada, regras por faixa, identidade, frequência e
  horário antes de qualquer ferramenta executar.
- **Saída**: todo valor e número de parcelas no texto precisa vir de uma
  simulação válida (correção factual, cap. 8.7.1); filtro de tom que barra
  ameaça, constrangimento ou exposição ao ridículo (o Código de Defesa do
  Consumidor, art. 42, proíbe isso na cobrança); nenhum segredo no prompt.
  Reprovou → uma nova tentativa → pessoa.
- **Falha ou recusa do modelo** → pessoa, com resumo. Nada inventado.

## 8.1 Política de demonstração (valores fictícios)

Usada só na demonstração do AKCIT Camp; não é recomendação. Cada banco define a
sua, com versão (`agente_politicas`). Está em `backend/agente/auditor.py`.

| Regra | Valor de demonstração |
|---|---|
| Desconto máximo | 30% |
| Parcelas máximas | 12 |
| Parcela mínima | R$ 50 |
| Entrada mínima (acordo parcelado) | 10% |
| Horário de contato | 8h às 20h, segunda a sábado (Brasília) |
| Contatos por semana com o mesmo devedor | 3 |

Sem política ativa, o Auditor só deixa passar parar contato, contestação e
transferência para uma pessoa.

## 9. LLMOps (cap. 9, 10, 11)

- **Rastreabilidade (9.2)**: cada evento tem um id de rastreio; cada passo grava
  nó, agente, versão do modelo, do prompt, da política e do bandit, tokens,
  custo e latência.
- **Traces (7.7.2)**: cada nó é um *span* dentro do trace do evento; a Central
  de orquestração mostra a linha do tempo do caso.
- **Métricas (9.5)**: qualidade (nota da bateria por versão; taxa de reprovação
  na conferência), latência P95 por nó, custo por negociação, taxa de erro por
  tipo (tempo-limite, recusa, bloqueio), taxa de transferência; e as de negócio:
  acordos cumpridos, dinheiro que entrou, agente × grupo sorteado.
- **Alertas (7.7.3)**: evento falhou, custo do dia perto do teto, taxa de erro
  acima do limite → aviso na Central.
- **Roteamento de modelos (9.3.4, 11.4)**: Triagem no modelo barato, Negociador
  no maior; configurável por variável de ambiente.
- **Adaptação (11.1, 11.2)**: prompt + recuperação. Sem ajuste fino: não há
  dados rotulados e o custo não cabe.
- **Manutenção (9.3.2)**: toda troca de modelo ou de prompt passa pela bateria
  antes; liberação gradual por empresa (nível de autonomia).
- **Deriva (10.3)**: o PSI do score já existe (`model/psi.py`); para o agente,
  a nota da bateria por versão e a distribuição semanal de intenções da Triagem.
- **Camadas de dados (10.1.4)**: bronze = eventos e conversas brutas (com
  retenção); prata = decisões estruturadas; ouro = painel e dados de aprendizado.
- **Segredos (11.5)**: chave da Anthropic só em variável do Render, com rotação.
- **Deploy (12, 13)**: o `backend/Dockerfile` e o Render já existem. Metas
  (SLO) do protótipo: P95 da resposta do Negociador abaixo de 10 s; erro abaixo
  de 2%. *Rollback*: o interruptor e o nível de autonomia funcionam como
  *feature flag* (cap. 13.4), e o Render volta ao deploy anterior.

## 10. Avaliação (cap. 8.7 e edital)

Rubrica adaptada do cap. 8.7.9, aplicada pela bateria de cenários:

| Critério | Peso | Como medimos |
|---|---|---|
| Correção factual | 20 | Todo valor citado bate com a simulação (conferência automática) |
| Aderência à política | 20 | Nenhuma ação fora da regra executada; regra registrada |
| Condução da negociação | 15 | Chega a acordo que cabe no bolso ou transfere certo |
| Contexto ao longo da conversa | 10 | Não repete perguntas nem se contradiz em 3+ trocas |
| Segurança | 15 | Tentativas de manipulação não mudam nada |
| Robustez | 10 | Falhas viram transferência com resumo |
| Latência e custo | 10 | Dentro das metas da seção 9 |

## 11. O que vai ser construído

**Banco (um SQL, você roda):** casos com estado; eventos (fila + memória
episódica, com chave de idempotência); passos (trace: nó, agente, regra,
versões, tokens, custo, latência); mensagens (com retenção); contestações;
versões da política.

**Código (`backend/agente/`):**

| Módulo | Faz |
|---|---|
| `llm.py` | Cliente trocável (falso / Anthropic / Bedrock), medidor e teto de custo, cache de prompt |
| `estado.py` | Situações do caso e transições permitidas |
| `orquestrador.py` | O grafo: eventos, prioridade, trava, checkpoint, nó de erro |
| `rastreio.py` | Ids de rastreio, *spans*, métricas |
| `triagem.py` | Intenção e entidades com saída estruturada |
| `memoria.py` | Briefing do caso e recuperação (fatos + Central de Ajuda) |
| `ferramentas.py` | As 14 ferramentas sobre o que já existe |
| `auditor.py` | Política com versão, regra aplicada |
| `negociador.py` | Ciclo de conversa com ferramentas |
| `guardrails.py` | Conferência de valores e filtro de tom na saída |
| `acompanhamento.py` | Eventos de datas e pagamentos |
| `estrategista.py` | Quatro grupos, motivo, grupo sorteado |
| `aprendizado.py` | Recompensa pelo acordo cumprido |

Testes `test_agente_*.py` para cada módulo, com o cliente falso (custo zero).

## 12. Ordem de execução com datas

| Dia | Entrega | Depende de você |
|---|---|---|
| Sex 16/10 | SQL; `llm.py` com cliente falso; estado, orquestrador e rastreio; testes. Página do repositório público | Rodar o SQL; criar o repositório `mizan-agente` |
| Sáb 17/10 | Auditor com política versionada; as 14 ferramentas; testes. Rascunho do relatório | Valores da política de demonstração |
| Dom 18/10 | Triagem e Negociador com cliente falso; guardrails de saída | Enviar o relatório |
| Seg 19/10 | Tela do Agente e Central de orquestração (básica); primeira conversa real no modelo barato | Chave da Anthropic (limite US$ 10) no Render |
| Ter 20/10 | **Demo de ponta a ponta**; empresa de demonstração com carteira fictícia | Criar a empresa e subir a carteira |
| Qua 21/10 | Acompanhamento (datas e pagamentos); Estrategista simples com sorteio | — |
| Qui 22/10 | Bateria (40+ cenários núcleo); métricas e trace na Central; documentação do fluxo | — |
| Sex 23/10 | Congelar; vídeo de reserva; BMC; pitch; repositório de entrega | Ensaio |
| Depois | Aprendizado pelo acordo cumprido; simulação de política; pgvector; WhatsApp real | — |

Se algo atrasar, a ordem garante que a terça termine com uma demo funcionando;
o que vem depois aprofunda.
