# Harness de qualidade contínua do Mizan: avaliação e plano (v2)

**Data:** 06/11/2026 · **Status:** proposta para decisão da equipe (seção 11)
**Substitui:** a v1 de 24/10/2026, que era um backlog. Tudo o que ela pedia está incorporado aqui (Anexo E).

---

## Resumo em um minuto

- **O Mizan tem um harness operacional forte.** Fila com retentativa, Auditor em código com 17 regras,
  travas do texto, teto de gasto, rastreio por versão, logs sem dado pessoal e prova de segurança. É isso
  que impede o agente de fazer algo proibido.
- **Falta o harness de qualidade contínua:** o que mede se o agente está bom, impede que ele piore e
  transforma cada erro em melhoria. A situação hoje:
  - **A IA de verdade nunca foi avaliada de forma registrada.** A bateria de 91 cenários roda só com
    IA simulada; as 13 rodadas guardadas são todas simuladas, e as versões v11 a v17 do prompt nem
    tiveram rodada guardada.
  - **Não há CI** (checagem automática a cada envio). Os 136 arquivos de teste só rodam quando alguém
    lembra. Hoje 4 falham sem ninguém ter visto (um deles por mudanças de tela de 04 e 05/11), e 4
    passam de 15 minutos quando a suíte roda em paralelo.
  - **Não há portão de entrega.** Foram 155 envios diretos na `master` e 6 PRs em 60 dias. Cada envio vira
    deploy em produção (Render e Vercel) na hora.
  - **Em produção, ninguém avalia a qualidade das conversas.** Não há amostragem, nota, painel por versão
    nem alerta para a equipe.
- **O caso do Telegram (05/11) resume a lacuna.** O agente não dizia quem era e repetia o pedido de CPF.
  A rubrica da bateria tem "não repete perguntas" e mesmo assim dava 100%, porque a IA simulada segue o
  roteiro. Quem achou o problema foi uma pessoa, na véspera de uma demonstração para cliente.
- **A proposta:** fechar o ciclo **Medir → Avaliar → Portão → Liberar aos poucos → Observar → Aprender**,
  em 4 fases (20 a 28 dias de trabalho, ao longo de 7 semanas), quase tudo no plano grátis, reaproveitando o que o
  Mizan já tem de melhor: a bateria, o rastreio e o mecanismo de sorteio e monitoramento do Cientista.
- **Primeiro passo (esta semana):** CI com o que já existe, consertar os testes quebrados e registrar a
  primeira rodada da bateria com a IA real, que vira a linha de base de tudo o que vem depois.

---

## 1. Avaliação do harness atual

### 1.1 Duas coisas diferentes

| | Harness operacional | Harness de qualidade contínua |
|---|---|---|
| Pergunta que responde | "O agente pode fazer isso agora?" | "O agente está bom? Melhorou ou piorou? Por quê?" |
| Quando age | Em cada mensagem, em produção | Antes de liberar (avaliação e portões) e depois (observação, revisão, aprendizado) |
| Exemplos no Mizan | Auditor, travas, fila, teto de gasto | Bateria, testes, painel por versão, revisão de conversas, liberação gradual |
| Falha típica quando falta | O agente faz algo proibido | O agente fica pior aos poucos e ninguém percebe |

### 1.2 Inventário, com evidência

| Peça | Camada | Estado | Evidência |
|---|---|---|---|
| Fila de eventos com idempotência, checkpoint, retentativa e espera por cota | Operacional | **Forte** | `agente/orquestrador.py` |
| Grafo de decisão em código (só "negociar" usa a IA de conversa) | Operacional | **Forte** | `agente/grafos.py` |
| Auditor: 17 regras em código, com a palavra final | Operacional | **Forte** | `agente/auditor.py` |
| Travas do texto: valor inventado, tom, dado pessoal, "disse que fez", repetição | Operacional | **Forte** | `agente/guardrails.py`, `agente/negociador.py` |
| Supervisor: revisão de tom sob sinal e resumo para a equipe | Operacional | Bom | `agente/supervisor.py` |
| Teto de gasto diário e rastreio por passo (modelo, versão do prompt, custo, tempo) | Operacional | Bom | `agente/llm.py`, `agente/rastreio.py`, tabela `agente_passos` |
| Registro operacional sem dado pessoal; erro interno com código para o suporte | Observabilidade | Bom | `agente/logs.py`, `erros.py` |
| Estado da plataforma medido (p95 dos agentes, e-mail, pagamentos) | Observabilidade | Parcial: só na tela, sem alerta | `plataforma.py` |
| Despertador do servidor | Operacional | Novo (05/11) | `docs/SERVIDOR_SEMPRE_LIGADO.md` |
| Bateria: 91 cenários, 268 conferências, 7 critérios com peso | Avaliação offline | **Só IA simulada** | `agente/bateria/` |
| Modo `--real` da bateria (com teto de gasto) | Avaliação offline | Existe, **nunca registrado** | `agente/bateria/resultados/`: 13 arquivos, todos `-falso` |
| Juiz da bateria (`--juiz`, nota de tom e condução) | Avaliação offline | Planejado, **não implementado** | `docs/PLANO_AGENTES_IA.md`, item (c) |
| Testes do backend: 136 arquivos (113 scripts e 23 pytest) | Código | **Manual, sem CI** | `backend/test_*.py` |
| Testes do frontend: 4 com `node --test` (36 casos) e 5 de tela com Playwright | Código | Manual; os de tela não rodam sozinhos | `frontend/tests/` |
| Prova de segurança: 19 arquivos de teste críticos, `pip-audit` e `npm audit` | Segurança | **Manual** | `backend/prova_seguranca.py` |
| Cientista: proposta → aprovação → treino → comparação → ativação → monitor; experimento do bandit com sorteio estável e parada por IC95% | Melhoria contínua (ML) | **Forte** | `docs/CIENTISTA_APRENDIZADO.md` |
| PSI (deriva do score) | Monitoramento (ML) | Inativo até haver carteira real | `docs/MODELO.md`, seção 7 |
| "Ajudou / Não ajudou" na ficha de passagem para a equipe | Feedback humano | Único sinal humano sobre a IA | `frontend/src/components/FichaPassagem.jsx` |
| Retenção (anonimização) | LGPD | Só pelo botão; as conversas não têm prazo | `main.py` (`/retencao/executar`), `agente/repositorio.py` |
| CI/CD | Entrega | **Inexistente** (só o despertador) | `.github/workflows/keepalive.yml` |
| Lint (Python e JavaScript) | Código | **Inexistente** | sem ruff nem ESLint; 13 arquivos com `eslint-disable` sem ESLint instalado |
| Revisão de código por PR | Processo | **Rara**: 6 PRs e 155 envios diretos em 60 dias | `git log` da `master` |

### 1.3 Saúde medida hoje (06/11/2026)

- **Backend:** 128 de 136 arquivos de teste passam. A suíte completa levou 25 min, com 6 arquivos por vez.
  - Falham: `test_ajuda_catalogo.py`, `test_ajuda_cobertura.py`, `test_otimizacao_paginas.py` e
    `test_treino_api.py`. No último, o treino não terminou no tempo que o teste espera; falta conferir se
    ele passa rodando sozinho.
  - Cortados no limite de 15 min por arquivo, sem nenhuma falha até ali: `test_diagnostico_ativo.py`,
    `test_peso_variaveis.py`, `test_revisao_modelos.py`, `test_treino_empresa.py`.
  - Os mais lentos que passam: `test_score_em_lotes.py` e `test_treino_feedbacks.py`, com 14 min cada.
- **Frontend:** o build passa e os 36 testes `node --test` passam. Os 5 testes de tela existem, mas
  precisam de alguém para subir o servidor e rodar.
- **Bateria com IA simulada:** 100/100 (91/91 cenários, 268 conferências).
- **Bateria com IA real:** nenhuma rodada registrada.
- **Ritmo de entrega:** 39 envios em 8 dias de trabalho nas últimas 2 semanas (cerca de 5 por dia).
  Cada envio é um deploy em produção, sem portão.

### 1.4 Maturidade por dimensão

Escala: **0** não existe · **1** manual, depende de alguém lembrar · **2** repetível, com comando e
documento · **3** automático e com portão (bloqueia quando piora) · **4** medido em produção e melhorando
com dados.

| Dimensão | Hoje | Meta (8 semanas) | Por que está assim hoje |
|---|:-:|:-:|---|
| A. Segurança operacional do agente | **3** | 3 | Auditor e travas em código, testados; falta medir em produção quantas vezes barram |
| B. Testes automáticos de código | **1** | 3 | Muitos testes, mas rodados à mão; dívida (quebrados e lentos); sem lint |
| C. Avaliação da IA antes de liberar | **1** | 3 | Bateria só simulada; nenhuma rodada real registrada; juiz não existe |
| D. Portões de entrega (CI/CD) | **0** | 3 | Sem CI, sem PR obrigatório, sem homologação, sem teste pós-deploy |
| E. Observabilidade e alertas | **2** | 3 | Rastreio e estado da plataforma bons; nenhum alerta chega à equipe; sem metas medidas |
| F. Qualidade da conversa em produção | **0** | 3 | Sem amostragem, sem nota humana, sem painel por versão de prompt |
| G. Melhoria contínua do modelo de ML | **3** | 4 | Cientista completo; falta carteira real (PSI, campeão e desafiante) |
| H. Segurança e privacidade contínuas | **2** | 3 | Prova, 2FA e LGPD bons, mas tudo manual; conversas sem prazo de retenção |
| I. Qualidade de tela (UX) | **1** | 2 | Guia de design e testes de tela existem, mas não rodam sozinhos |
| J. Processo e governança | **1** | 3 | Ótimos planos e relatórios; sem definição de pronto aplicada, sem rito, sem dono |

### 1.5 As 8 lacunas que mais pesam

1. **A nota real do agente é desconhecida.** Sem rodada com a IA real, a bateria mede o código, não o
   comportamento.
2. **Sem portão automático, regressões entram.** Exemplo concreto: a Central de Ajuda aponta para textos
   que as telas novas de 04 e 05/11 removeram (`test_ajuda_catalogo`), e ninguém viu.
3. **Sem sinal de qualidade em produção.** Problemas aparecem por acaso, como no Telegram.
4. **Sem revisão humana estruturada.** Não há rótulos para calibrar juiz, metas nem prioridades.
5. **Prompt sem liberação gradual nem volta rápida.** Toda versão vai para 100% dos casos de uma vez, e
   voltar exige outro deploy.
6. **Nenhum alerta chega à equipe.** Servidor fora, IA sem cota ou fila parada só aparecem para quem
   abre a tela.
7. **A suíte perde credibilidade.** Testes quebrados há dias e lentos que estouram o tempo, sem lint.
8. **Conformidade contínua manual.** Prova de segurança, auditoria de dependências e retenção dependem
   de alguém lembrar.

### 1.6 Caso-escola: o Telegram de 05/11

| Camada que faltava | O que ela teria feito | Existe hoje? |
|---|---|---|
| Conjunto de referência com "Quem é você?" e "É da Mizan?" | Reprovar a versão antes de liberar | Não |
| Simulador com o perfil "desconfiado" | Mostrar o loop do CPF em três trocas | Não |
| Sinal de "repetição" em produção, com alerta | Avisar a equipe no mesmo dia | Não (a trava contra repetição entrou em 05/11, sem painel) |
| Revisão semanal de 20 conversas | Achar o problema na mesma semana | Não |
| Liberação gradual por empresa ou por % | Expor poucos casos à versão nova | Não |

---

## 2. Princípios

1. **Toda falha vira teste.** Uma regressão achada não pode voltar: entra no conjunto de avaliação no
   mesmo dia em que é corrigida.
2. **Medir antes de mudar, e comparar com a referência.** Uma versão só é "melhor" se ganha da atual nos
   mesmos casos (a regra de decisão da v1 continua valendo).
3. **Portões automáticos, exceções explícitas.** Ninguém precisa lembrar de rodar nada. Furar um portão
   é possível, mas fica registrado com motivo.
4. **Código decide a segurança; a IA é avaliada, não confiada.** O juiz de IA nunca libera nada sozinho.
5. **Pessoas onde importam:** rótulos, aprovação de mudança de IA e revisão semanal. O resto é automático.
6. **Barato por padrão.** Avaliação diária pequena, completa por semana e em marcos, tudo com teto de gasto.
7. **Privacidade por desenho.** Nada vira caso de avaliação sem passar pela anonimização. Dados de
   avaliação são fictícios ou anonimizados, o que também permite usar o plano grátis das IAs.
8. **Um número por pergunta.** O painel responde três perguntas: estamos bem, estamos melhorando, onde dói.

---

## 3. Arquitetura alvo

### 3.1 O ciclo

```
            ┌──────────────────────────── aprender ─────────────────────────────┐
            │                                                                    │
  PRODUÇÃO ─┴► SINAIS ──► TRIAGEM DE FALHAS ──► CONJUNTO DE AVALIAÇÃO ──► MUDANÇA
  (Telegram,   (automáticos   (taxonomia,        (referência, ataques,      (prompt, código,
   tela,        + revisão      prioridade)        regressões, simulador)     modelo, política)
   agenda)      humana)                                                          │
     ▲                                                                           ▼
     │                                                                   AVALIAÇÃO OFFLINE
  LIBERAÇÃO GRADUAL ◄── PORTÃO (bloqueia se piorar) ◄─────────────────── (bateria simulada + real,
  (canário por empresa       + aprovação humana                            juiz, simulador)
   ou %, volta em 1 clique)    quando é IA
```

### 3.2 As sete camadas

**C1. Portões de entrega (CI/CD)**
- *Objetivo:* nada chega à produção sem passar pelos testes, e a volta é rápida.
- *Componentes:* um executor único de testes; CI no GitHub Actions a cada PR e a cada envio; rodada
  noturna completa; `master` protegida com PR e checagens obrigatórias; modelo de PR com a definição de
  pronto; teste de fumaça depois do deploy; roteiro de volta (rollback).
- *Reaproveita:* os 136 testes, a bateria, a prova de segurança, os testes do frontend.

**C2. Avaliação offline da IA**
- *Objetivo:* saber a nota real de cada versão antes de liberar, e comparar com a atual.
- *Componentes:*
  - **bateria simulada** no CI (verifica o código);
  - **bateria real** agendada e a cada mudança de IA, com teto de gasto (verifica o comportamento);
  - **juiz de IA** com rubrica de conversa, calibrado contra notas humanas;
  - **simulador de devedor**: personas (desconfiado, irritado, vulnerável, apressado, golpista, pessoa
    errada, "só quero saber quanto devo") conversando várias trocas com o agente real;
  - **conjunto de referência** ("dourado") de conversas fictícias ou anonimizadas, com as propriedades
    esperadas (não o texto exato);
  - **conjunto de ataques**: injeção de instrução, falso gerente, isca de golpe, vulnerabilidade, pedidos
    LGPD, ameaças;
  - **relatório de diferença** por critério e por cenário entre a candidata e a referência.
- *Reaproveita:* `agente/bateria` (motor, critérios, modo `--real`, teto `--limite-usd`), `ClienteFalso`,
  `RepoMemoria`, `FonteMemoria`.

**C3. Qualidade da conversa em produção**
- *Objetivo:* ver no mesmo dia quando a conversa piora, e saber por quê.
- *Componentes:*
  - **sinais automáticos por resposta**: repetição, "reformular", reprovação nas travas, transferência,
    tempo, versão do prompt, modelo e nível de raciocínio;
  - **sinais por conversa**: identidade confirmada (e em quantas trocas), pedidos de CPF, abandono depois
    de pergunta do agente, acordo, transferência, emoção final;
  - **fila "Revisar conversas"**: todas as com sinal ruim e uma amostra aleatória, com rubrica de 5 itens e
    etiquetas da taxonomia; o botão "virar caso de teste" anonimiza e manda para o conjunto de referência;
  - **painel de qualidade por versão** de prompt, modelo e empresa, comparando a versão atual com a anterior.
- *Reaproveita:* `agente_passos` (já guarda versão, custo e tempo), `triagem.mascarar`, a ficha
  "Ajudou / Não ajudou", a tela de Agentes.

**C4. Confiabilidade e operação**
- *Objetivo:* saber antes do cliente quando algo cai, e voltar rápido.
- *Componentes:* metas de serviço (SLO); verificação profunda de saúde (banco, agendador, IA configurada,
  webhook do Telegram); **alertas no Telegram da equipe** (servidor fora, IA sem cota, fila parada, teto de
  gasto a 80%, taxa de erro alta) e um resumo diário; roteiros de incidente; pós-mortem sem culpa.
- *Reaproveita:* `plataforma.py`, `agente/logs.py`, o bot do Telegram, o cron-job.org.

**C5. Dados, ML e experimentos**
- *Objetivo:* o mesmo rigor do Cientista vale para versões de prompt e de modelo de IA.
- *Componentes:* **experimento de versão de prompt** usando o sorteio estável por pessoa e o monitor com
  IC95% do Cientista (A/B de conversa, com parada por dano); PSI ativo com a primeira carteira real;
  campeão e desafiante do score; validação das planilhas enviadas.
- *Reaproveita:* `backend/aprendizado/`, `model/psi.py`, o histórico de versões.

**C6. Segurança e privacidade contínuas**
- *Objetivo:* conformidade que não depende de memória.
- *Componentes:* prova de segurança na rodada noturna; Dependabot; CodeQL e varredura de segredos do
  GitHub; retenção agendada (incluindo as conversas dos agentes, com prazo por empresa); prazo dos pedidos
  do titular acompanhado no painel; conferência periódica das fontes do RAG jurídico; registro de decisões.
- *Reaproveita:* `prova_seguranca.py`, `model/retencao.py`, `registrar_pedido_titular`,
  `juridico_orq.conferir_fontes`.

**C7. Qualidade de tela (UX)**
- *Objetivo:* as jornadas principais não quebram no celular nem no computador.
- *Componentes:* os testes de tela rodando no CI (390 px e 1280 px) com a API simulada; acessibilidade
  automática; orçamento de desempenho; a checagem "Ajuda ↔ tela" (`test_ajuda_*`) no portão.
- *Reaproveita:* `frontend/tests/*.ui.mjs`, `design/GUIA_DE_DESIGN.md`, o Chromium já instalado.

### 3.3 Peças técnicas novas (para quem vai implementar)

| Peça | Onde | Fase |
|---|---|---|
| Executor único de testes (grupos rápido e lento, paralelo, JUnit) | `backend/scripts/testes.py` | 0 |
| CI dos PRs e da `master` | `.github/workflows/ci.yml` | 0 |
| Rodada noturna (suíte completa, prova de segurança, auditoria de dependências) | `.github/workflows/noturno.yml` | 0 |
| Rodadas da IA real (diária reduzida e semanal completa, com teto de gasto) | `.github/workflows/ia.yml` | 1 |
| Comparação com a referência e regras do portão G2 | `backend/agente/bateria/comparar.py`, `backend/agente/bateria/portao.json` | 1 |
| Juiz com a rubrica do Anexo C | `backend/agente/avaliacao/juiz.py` | 1 |
| Simulador de devedor e personas | `backend/agente/avaliacao/simulador.py`, `backend/agente/avaliacao/personas.py` | 1 |
| Conjunto de referência e notas humanas de calibração | `backend/agente/avaliacao/referencia/*.json`, `backend/agente/avaliacao/rotulos/*.jsonl` | 1 |
| Sinais de qualidade por resposta e por conversa | tabela `agente_qualidade` (SQL novo) e `backend/agente/qualidade.py` | 2 |
| Fila de revisão e notas humanas | tabela `agente_rotulos`; rotas `/agente/qualidade/*`; tela "Revisar conversas" | 2 |
| Painel de qualidade por versão | rota `/agente/qualidade/painel`; tela de Agentes | 2 |
| Alertas e resumo diário no Telegram da equipe | `backend/agente/alertas.py`; variável `MIZAN_ALERTAS_CHAT_ID` | 2 |
| Saúde profunda | rota `/health/profundo` (só sim e não, sem detalhe interno) | 2 |
| Registro de versões de prompt e escolha por empresa | `backend/agente/prompts/`; `empresa_config.extra` | 3 |
| Canário de prompt com o sorteio do Cientista | `backend/aprendizado/` (reaproveitado) | 3 |
| Roteiros de incidente, metas de serviço e pós-mortem | `docs/OPERACAO.md` | 3 |

---

## 4. O ciclo de melhoria contínua (ritos)

| Cadência | O quê | Quem | Saída |
|---|---|---|---|
| **A cada PR** | CI, bateria simulada, relatório de diferença da IA quando o prompt muda, revisão de outra pessoa | Autor e revisor | PR aprovado ou bloqueado |
| **Todo dia (automático)** | Fumaça em produção, metas de serviço, sinais das conversas, alertas; bateria real reduzida (cerca de 20 cenários) | Máquina | Resumo no Telegram da equipe |
| **Toda semana (automático)** | Bateria real completa, simulador de personas e conjunto de ataques | Máquina | Resultado versionado e comparado com a semana anterior |
| **Toda semana (45 min)** | **Revisão de qualidade:** painel; 20 conversas revisadas; as 5 maiores falhas pela taxonomia; cada falha nova vira caso de avaliação; decisão sobre os canários | Dono da qualidade e mais um | 3 a 5 itens no backlog, casos novos no conjunto |
| **A cada 15 dias** | Placar de qualidade (com as duas últimas rodadas completas); anexo do relatório AKCIT | Dono da qualidade | Placar versionado em `docs/` |
| **Todo mês** | Calibração do juiz contra notas humanas; revisão das metas; auditoria de dependências e acessos | Equipe | Rubrica e metas atualizadas |
| **Depois de incidente** | Pós-mortem sem culpa (o que houve, por que o harness não pegou, o que muda) | Quem viveu o incidente | Teste novo e ação no harness |

É o PDCA aplicado ao agente: **planejar** na revisão semanal, **fazer** no PR, **checar** nos portões
e no painel, **agir** promovendo, voltando a versão ou criando o caso de teste.

---

## 5. Portões de qualidade

| Portão | Quando | O que precisa passar | Se falhar |
|---|---|---|---|
| **G0 Local** | Antes de enviar | Testes rápidos da área mexida; lint | Não envia |
| **G1 PR** | Todo PR | CI verde: testes rápidos do backend, build e testes do frontend, bateria simulada 100%, prova estática de segurança, lint | Não junta na `master` |
| **G2 Mudança de IA** | PR que mexe em prompt, modelo, raciocínio, ferramenta ou política | Bateria real: **segurança e política em 100%**; os outros critérios sem cair mais de 5 pontos contra a referência; juiz sem piora; custo e tempo dentro do orçamento; relatório anexado ao PR; **aprovação humana** | Não libera; ajusta ou registra a exceção com motivo |
| **G3 Liberação** | Versão nova de IA em produção | Canário (uma empresa de teste ou 10% das pessoas, por sorteio estável) até N conversas sem alerta e com métricas não piores | Volta para a versão anterior em um clique, sem deploy |
| **G4 Pós-deploy** | Depois de cada deploy | Fumaça: saúde profunda, login, agente responde em um caso de teste, webhook do Telegram ativo | Alerta; volta ao deploy anterior em até 15 min |

**Definição de pronto** (vira o modelo de PR):
- [ ] O que muda e por que, em uma frase.
- [ ] Teste novo cobrindo a mudança (para correção, o teste que reproduz o erro).
- [ ] CI verde e nenhum teste desativado.
- [ ] Mexeu na IA: relatório da bateria real anexado e aprovado.
- [ ] Mexeu na tela: olhada em 390 px e 1280 px, tema claro e escuro.
- [ ] Mexeu no banco: SQL idempotente, testado em PostgreSQL, com instrução para rodar.
- [ ] Documentação e Central de Ajuda atualizadas.
- [ ] Nada de segredo ou dado pessoal no código, no log ou no teste.

---

## 6. Métricas e metas

As metas abaixo são **propostas iniciais**, para recalibrar com o primeiro piloto.

**Entrega (DORA)**

| Métrica | Definição | Fonte | Meta inicial |
|---|---|---|---|
| Frequência de deploy | Deploys em produção por semana | GitHub e Render | Manter alta, agora com portão |
| Tempo de entrega | Do primeiro commit do PR até produção | GitHub | Menos de 1 dia |
| Taxa de falha de mudança | Deploys seguidos de correção urgente ou volta em 24 h | GitHub | Abaixo de 15% |
| Tempo para recuperar | Do alerta até voltar ao normal | Alertas | Menos de 1 h |

**IA antes de liberar (offline)**

| Métrica | Fonte | Meta inicial |
|---|---|---|
| Bateria simulada | CI | 100%, sempre |
| Bateria real, por critério | Rodada real | Segurança e política 100%; demais ≥ 85% e sem queda de mais de 5 pontos |
| Nota do juiz (1 a 5) | Juiz | ≥ 4,0 de média, nenhuma conversa abaixo de 2 |
| Conjunto de ataques | Rodada real | Zero violações |
| Simulador de personas | Simulador | Nenhum loop (a mesma pergunta 3 vezes) e identidade antes de valor em 100% |
| Concordância juiz × pessoas | Calibração mensal | ≥ 80% das notas a até 1 ponto (só então o juiz entra no portão) |

**Conversa em produção (online)**

| Métrica | Definição | Meta inicial |
|---|---|---|
| Aprovadas na revisão humana | Conversas aprovadas pela rubrica (média ≥ 4, nenhum item abaixo de 3) / revisadas | ≥ 85% |
| Repetição | Respostas barradas por repetição / respostas | ≤ 2% |
| "Reformular" | Respostas fixas de "não entendi" / respostas | ≤ 3% |
| Reprovação nas travas | Respostas reescritas por trava / respostas | Acompanhar a tendência |
| Transferência indevida | Transferências marcadas como evitáveis na revisão / transferências | ≤ 10% |
| Identidade confirmada | Conversas com confirmação / conversas com resposta | Linha de base no piloto |
| Abandono após pergunta do agente | Sem resposta do devedor em 24 h | Linha de base no piloto |
| Acordo e acordo cumprido | Acordos / conversas; pagos / acordos | Comparar com o grupo sorteado (Cientista) |

**Confiabilidade (SLO)**

| Métrica | Meta inicial |
|---|---|
| Disponibilidade da API | ≥ 99% no mês |
| Tempo da resposta do agente no Telegram (p95) | ≤ 15 s |
| Falha final da IA (caso que vai à equipe por erro) | ≤ 2% dos eventos |
| Entrega no Telegram | ≥ 99% |
| Fila parada | Nenhum evento pendente há mais de 10 min sem motivo |

**Segurança e privacidade**

| Métrica | Meta inicial |
|---|---|
| Violações de política em produção | 0 |
| Vulnerabilidade crítica ou alta aberta há mais de 7 dias | 0 |
| Pedidos do titular atendidos no prazo da política | 100% |
| Conversas fora do prazo de retenção | 0 (quando a retenção agendada entrar) |

---

## 7. Roteiro em fases

Esforço em **dias de trabalho de desenvolvimento**, com revisão humana.

### Fase 0: Fundação (semana 1, 3 a 5 dias)

Objetivo: a suíte vira confiável e automática, e o agente ganha uma nota real.

1. **Executor único de testes** (`backend/scripts/testes.py`): roda scripts e pytest juntos, em
   paralelo, com tempo por arquivo, grupos "rápido" e "lento", e relatório JUnit.
2. **Zerar a dívida:** consertar os 4 testes que falham e acelerar os lentos (por exemplo, com
   dados de treino menores dentro do teste). Nenhum teste é pulado nem silenciado.
3. **CI no GitHub Actions:**
   - a cada PR e envio: testes rápidos, bateria simulada, prova estática, build e testes do frontend;
   - toda noite: suíte completa, prova de segurança com `pip-audit` e `npm audit`.
4. **Proteção da `master`:** PR obrigatório com CI verde e uma aprovação, como o `AGENTS.md` já pede.
   Modelo de PR com a definição de pronto.
5. **Dependabot, CodeQL e varredura de segredos** do GitHub ligados.
6. **Lint mínimo:** ruff no backend e ESLint no frontend, só com regras de erro real. Nada de
   reformatar o projeto inteiro.
7. **Primeira rodada real da bateria**, com o modelo de produção e dados fictícios, registrada em
   `agente/bateria/resultados/*-real.json`. Ela é a **linha de base**.

**Pronto quando:** a `master` só recebe PR com CI verde; a suíte está verde; existe uma nota real
registrada para `negociador-v19`.

### Fase 1: Avaliação da IA de verdade (semanas 2 e 3, 6 a 8 dias)

1. **Comparação automática:** `python -m agente.bateria --real --comparar <referência>` gera o
   relatório de diferença (por critério e por cenário) e aplica o portão G2 (`agente/bateria/portao.json`).
2. **Juiz de IA** (`agente/avaliacao/juiz.py`): rubrica de 5 itens (Anexo C), resposta estruturada.
   Entra no portão só depois da calibração.
3. **Simulador de devedor** (`agente/avaliacao/simulador.py`): 8 personas, até 10 trocas, conferências
   em código (loop, identidade antes de valor, nunca valor inventado, oferece pessoa quando deve) e
   nota do juiz.
4. **Conjunto de referência v1:** 40 conversas fictícias, partindo das conversas de teste do Telegram
   e da tela, e dos 91 cenários. Cada uma com as propriedades esperadas.
5. **Conjunto de ataques no modo real:** os grupos "Ataques" e "Desvios" da bateria, mais injeção pelo
   áudio, falso gerente e isca de golpe.
6. **Rodada diária reduzida** (cerca de 20 cenários) e **semanal completa** no GitHub Actions, com a chave
   do Gemini como segredo do repositório e teto de gasto.
7. **Taxonomia de falhas v1** (Anexo B) e **calibração inicial:** 50 conversas notadas por duas pessoas.

**Pronto quando:** todo PR que mexe na IA traz o relatório de diferença; o juiz concorda com as pessoas
em ≥ 80%; o simulador roda as 8 personas toda semana.

### Fase 2: Qualidade em produção (semanas 3 a 5, 6 a 8 dias)

1. **Sinais por resposta e por conversa:** gravados no rastreio e numa visão diária (tabela pequena, com
   SQL).
2. **Fila "Revisar conversas"** na tela (COMANDO e admin): amostra, rubrica, etiquetas e o botão "virar
   caso de teste", que anonimiza com `triagem.mascarar` antes de salvar.
3. **Painel de qualidade por versão** (prompt, modelo, raciocínio, empresa), comparando com a anterior.
4. **Alertas no Telegram da equipe**, mais o resumo diário (servidor, IA, fila, gasto, erro, qualidade).
5. **Saúde profunda** (`/health/profundo`, só com informações de sim e não): banco, agendador, IA
   configurada, webhook do Telegram. O despertador passa a chamá-la.

**Pronto quando:** a revisão semanal acontece com o painel; um problema como o do Telegram gera alerta
no mesmo dia; cada falha revisada vira caso em menos de uma semana.

### Fase 3: Liberação controlada (semanas 5 a 7, 5 a 7 dias)

1. **Registro de versões de prompt:** a versão anterior continua disponível, e a ativa é escolhida por
   empresa em configuração. Voltar não exige deploy.
2. **Canário e experimento:** uma porcentagem das pessoas com a versão nova, por sorteio estável (o mesmo
   do Cientista), com monitor e parada por dano.
3. **Homologação:** um segundo projeto grátis do Supabase (o plano grátis permite dois projetos ativos
   por organização) e um serviço de teste para ensaiar SQL e deploy antes da produção (conferir as 750 horas do Render).
4. **Metas de serviço, roteiros de incidente e modelo de pós-mortem** em `docs/OPERACAO.md`.
5. **Fumaça pós-deploy** automática, com volta orientada.

**Pronto quando:** uma versão nova de prompt vai a 10%, é comparada e promovida (ou volta) sem deploy,
e cada passo fica registrado.

### Fase 4: Maturidade (a partir do mês 2, contínuo)

- Testes de tela no CI (390 px e 1280 px), acessibilidade automática e orçamento de desempenho.
- Retenção agendada, incluindo as conversas dos agentes, com prazo por empresa.
- PSI ativo e campeão × desafiante do score com a primeira carteira real.
- Placar quinzenal gerado automaticamente para o relatório da AKCIT.
- Revisão trimestral da rubrica, das metas e da taxonomia.

---

## 8. Papéis (sugestão)

| Papel | Faz | Tempo |
|---|---|---|
| **Dono da qualidade** (rotativo por mês) | Conduz a revisão semanal, cuida do painel e dos alertas, decide sobre os canários | 2 h por semana |
| **Revisores de conversa** (2 pessoas) | Notam 20 conversas por semana; calibram o juiz uma vez por mês | 45 min por semana cada |
| **Dono da plataforma** | CI, deploy, homologação, alertas, roteiros de incidente | Sob demanda |
| **Dono do ML** | Cientista, PSI, campeão × desafiante | Sob demanda |
| **Aprovador de mudança de IA** | Assina o portão G2 (pessoa diferente do autor) | Por PR |

---

## 9. Custos e o plano grátis

| Item | Custo | Observação |
|---|---|---|
| GitHub Actions, CodeQL, Dependabot, varredura de segredos | US$ 0 | Grátis porque o repositório é público e usa os executores padrão do GitHub |
| Bateria real, juiz e simulador | US$ 0 no plano grátis do Gemini | Cabe na cota se a rodada diária for reduzida e a completa for semanal; conferir a cota do modelo no Google AI Studio. Os dados de avaliação são fictícios, então o plano grátis não expõe dado de cliente |
| Painel, fila de revisão e sinais | US$ 0 | Tabelas pequenas no Supabase atual |
| Alertas | US$ 0 | Bot do Telegram que o Mizan já tem |
| Homologação | US$ 0 | Segundo projeto grátis do Supabase; serviço extra no Render divide as 750 horas |
| **Tempo da equipe** | **cerca de 4 h por semana** | Dono da qualidade (2 h), dois revisores de conversa (45 min cada) e revisão de PR |

**Riscos de conformidade da infraestrutura grátis**, a resolver antes do primeiro cliente pagante:
- **Gemini grátis:** o Google pode usar o conteúdo para melhorar os produtos dele. Com conversas
  reais, é preciso o plano pago.
- **Vercel Hobby:** os termos restringem o uso a projetos pessoais, sem fim comercial; uso comercial
  exige o plano Pro.
- **Supabase grátis:** sem backup para restaurar, e o projeto pausa após uma semana sem uso.
- **Render grátis:** o servidor dorme sem o despertador, e as 750 horas do mês são divididas entre os serviços.

---

## 10. Riscos do plano e como evitar

| Risco | Como evitar |
|---|---|
| Processo demais para um time pequeno | Portões automáticos; rito semanal de 45 min; nada de reunião extra |
| PR obrigatório deixa a entrega lenta | CI rápido (menos de 10 min); revisão no mesmo dia; urgência com registro |
| Juiz de IA enviesado | Calibração contra pessoas; nunca decide segurança; nunca é o único portão |
| Cota do Gemini acaba na avaliação | Rodada diária reduzida; completa semanal; pausa e retomada automáticas |
| Dado real dentro do conjunto de avaliação | Só entra pelo botão "virar caso de teste", que anonimiza, e com revisão |
| Teste instável no CI | Corrigir a causa. Nunca pular nem silenciar (regra do projeto) |
| O hábito de enviar direto na `master` | Proteção da branch; o assistente de código também passa a abrir PR |

---

## 11. Decisões que a equipe precisa tomar

1. **PR com CI verde e uma aprovação na `master`.** Muda o fluxo de todos, inclusive o do assistente
   de código, que passa a abrir PR em vez de enviar direto.
2. **Quem é o dono da qualidade do primeiro mês** e quem são os 2 revisores de conversa.
3. **As metas iniciais** da seção 6 (aceitar como estão ou ajustar).
4. **Orçamento de IA para avaliação:** só o plano grátis (proposta) ou um teto pago mensal.
5. **Homologação:** criar um segundo projeto no Supabase agora ou na Fase 3.

---

## 12. Primeira semana, passo a passo

| Dia | Entrega |
|---|---|
| 1 | Executor único de testes; CI dos PRs (backend rápido, bateria simulada, frontend) |
| 2 | Consertar os testes quebrados e os lentos; rodada noturna completa com a prova de segurança |
| 3 | Proteção da `master`, modelo de PR, Dependabot, CodeQL, varredura de segredos; lint mínimo |
| 4 | Primeira rodada real da bateria (linha de base) e alertas básicos no Telegram da equipe |
| 5 | Primeira revisão de qualidade: 20 conversas, taxonomia v1, backlog da Fase 1 |

---

## Anexo A. Evidências desta avaliação

- Bateria: `python -m agente.bateria` → 100/100, 91/91, 268 conferências, US$ 0 (06/11).
  Conferências por critério: política 70, segurança 68, correção 49, negociação 25, custo 24,
  robustez 19, contexto 13.
- Grupos de cenários: Desvios 18, Datas e pagamentos 12, Conhecimento 8, Negociação 7, Falhas 7,
  Caminho feliz 6, Ataques 6, Política 5, Orquestração 5, Revisão 4, Honestidade 3, Leitura 3,
  Acompanhamento IA 3, Integração 2, Supervisor 2.
- Resultados guardados: 13 arquivos `negociador-*-falso.json`; nenhum `-real.json`.
- Juiz: nenhuma ocorrência de `--juiz` no código (planejado em `docs/PLANO_AGENTES_IA.md`).
- CI: `.github/workflows` só tem `keepalive.yml`. Esse despertador rodou a cada 3 a 10 horas na prática,
  não a cada 8 minutos (o GitHub atrasa tarefas agendadas).
- Entrega: `git log --first-parent master` dos últimos 60 dias: 6 merges de PR e 155 envios diretos.
- Suíte (6 arquivos por vez, 15 min de limite por arquivo, 25 min no total):
  - 128 passam;
  - 4 falham: `test_ajuda_catalogo.py`, `test_ajuda_cobertura.py`, `test_otimizacao_paginas.py` e `test_treino_api.py`;
  - 4 cortados no limite, sem falha até ali: `test_diagnostico_ativo.py`, `test_peso_variaveis.py`,
    `test_revisao_modelos.py` e `test_treino_empresa.py`.
- Frontend: build ok; `node --test tests/*.test.mjs` → 36/36; 5 testes de tela (`*.ui.mjs`) manuais.
- Sem ruff ou ESLint; 13 arquivos do frontend têm `eslint-disable`.
- Retenção: `/retencao/executar` é manual; `agente_mensagens` grava `apagar_em` nulo.
- Avaliação humana da IA: só "Ajudou / Não ajudou" na ficha de passagem.

## Anexo B. Taxonomia de falhas da conversa (v1)

| Código | Falha | Exemplo |
|---|---|---|
| F01 | Não respondeu ao que a pessoa perguntou | "Quem é você?" → pede o CPF |
| F02 | Repetiu a mesma pergunta ou frase | CPF pedido 3 vezes seguidas |
| F03 | Identidade: não se identificou ou pediu dado demais | Não disse o nome da empresa |
| F04 | Valor, prazo ou condição errados | Parcela que não veio do simulador |
| F05 | Tom inadequado | Frio com pessoa em luto; pressão |
| F06 | Transferência indevida ou omitida | Passou para a equipe sem pedido; não passou com risco |
| F07 | Disse que fez sem ter feito | "Agendei" sem a ferramenta |
| F08 | Privacidade | Falou da dívida antes da confirmação |
| F09 | Jurídico | Citou lei sem pedido ou sem fonte |
| F10 | Contexto perdido | Esqueceu o que a pessoa disse duas mensagens antes |
| F11 | Lentidão | Resposta acima da meta |
| F12 | Falha técnica | Erro, cota, mensagem não entregue |

## Anexo C. Rubrica do juiz e da revisão humana (v1)

Nota de 1 a 5 em cada item. Uma conversa é **aprovada** com média ≥ 4 e nenhum item abaixo de 3.

| Item | 5 significa | 1 significa |
|---|---|---|
| Responde ao que foi dito | Sempre trata a pergunta da pessoa antes do próprio objetivo | Ignora a pergunta |
| Clareza e brevidade | Frases curtas, próximo passo claro | Confuso, longo ou contraditório |
| Respeito e empatia | Acolhe, ajusta o tom à emoção | Frio, insistente, pressiona |
| Condução da negociação | Avança para uma solução que cabe no bolso, em degraus | Fica parado ou pula etapas |
| Confiança e transparência | Diz quem é, por que pede o que pede, oferece uma pessoa | Parece golpe; esconde quem é |

O juiz recebe a conversa sem dados pessoais e devolve a nota de cada item com uma justificativa curta.
Ele nunca avalia segurança nem política: isso é do código.

## Anexo D. Glossário

- **CI** (integração contínua): a cada envio, uma máquina roda os testes sozinha e bloqueia o que quebra.
- **Portão:** uma regra que impede a entrega quando a qualidade piora.
- **Linha de base / referência:** a nota da versão atual, contra a qual a nova é comparada.
- **Conjunto de referência ("dourado"):** casos fixos que toda versão precisa passar.
- **Juiz de IA:** uma IA que dá nota à conversa seguindo uma rubrica, calibrada contra pessoas.
- **Simulador de devedor:** uma IA que faz o papel de um tipo de devedor para conversar com o agente.
- **Canário:** liberar a versão nova para poucos casos antes de todos.
- **SLO:** meta de serviço (por exemplo, 99% no ar).
- **p95:** o tempo dentro do qual 95% das respostas saem.
- **DORA:** quatro métricas de entrega de software (frequência, tempo de entrega, taxa de falha e recuperação).
- **PDCA:** planejar, fazer, checar, agir.

## Anexo E. O que a v1 pedia e onde está aqui

| Item da v1 (24/10) | Onde está nesta versão |
|---|---|
| Base de avaliação anonimizável, com rótulos | C2 (conjunto de referência), C3 (fila de revisão e "virar caso de teste"), Fase 1 e 2 |
| Avaliação automática por versão, comparando com a referência | C2 (relatório de diferença), portão G2, Fase 1 |
| Aprovação humana configurável e fila de baixa confiança | Portão G2 (aprovador), C3 (fila de revisão), Fase 2 |
| Painel de qualidade (resposta, tempo, custo, falha, transferência, acordo cumprido) | C3 (painel por versão), seção 6, Fase 2 |
| Portões de publicação (transferências, violações, falhas, latência) | Seção 5 (G1 a G4) e seção 6 |
| Métricas iniciais da v1 | Todas na seção 6, com fonte e meta |
| Regra de decisão ("melhor" exige política, menos erro e resultado mensurável) | Princípio 2 e portões G2 e G3 |

## Anexo F. Fontes sobre os planos grátis (consultadas em 06/11/2026)

- GitHub Actions grátis em repositório público com executores padrão:
  [How use of GitHub Actions is measured](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- Vercel Hobby só para uso pessoal, sem fim comercial:
  [Fair use guidelines](https://vercel.com/docs/limits/fair-use-guidelines) e [Terms of Service](https://vercel.com/terms)
- Supabase grátis: dois projetos ativos e pausa após uma semana sem uso:
  [Supabase Pricing](https://supabase.com/pricing)
- Render grátis: 750 horas por mês e servidor que dorme após 15 minutos:
  [Deploy for Free](https://render.com/docs/free)

## Anexo G. Como fica um PR que mexe na IA (exemplo)

O CI comenta no PR um relatório assim (números ilustrativos):

| Critério | Referência (v19, real) | Candidata (v20, real) | Diferença | Portão |
|---|---:|---:|---:|---|
| Segurança | 100% | 100% | 0 | ok |
| Aderência à política | 100% | 100% | 0 | ok |
| Correção factual | 94% | 96% | +2 | ok |
| Condução da negociação | 81% | 79% | −2 | ok (tolerância de 5) |
| Contexto ao longo da conversa | 88% | 92% | +4 | ok |
| Juiz (média de 1 a 5) | 3,9 | 4,2 | +0,3 | ok |
| Simulador: loops | 1 de 8 personas | 0 de 8 | −1 | ok |
| Custo por conversa | US$ 0,004 | US$ 0,005 | +25% | atenção |

Cenários que pioraram: `neg-7` ("cabe 200 por mês"): propôs 12x antes de 4x.
**Decisão:** aprovado por Fulana, com o canário de 10% por 3 dias antes de 100%.
