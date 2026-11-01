# Relatório TERCEIRA ENTREGA — Mizan

**Período:** 18/10/2026 a 01/11/2026 · **Envio:** 01/11/2026  
**Repositório (evidência):** [github.com/mauricionimer/MIZAN](https://github.com/mauricionimer/MIZAN)  
**No período:** 144 commits na branch principal, com dois pull requests revisados e integrados:
[#28 Segurança](https://github.com/mauricionimer/MIZAN/pull/28) e
[#29 Cientista](https://github.com/mauricionimer/MIZAN/pull/29).

A partir desta entrega, a evidência é o repositório principal do produto, onde os agentes
estão integrados. O de 18/10 era o `AGENTESMIZAN`.

---

## 1. Metas das últimas semanas

1. **Evolução da cibersegurança:** fechar as falhas do plano de segurança e provar a
   correção com testes automáticos.
2. **Conexão do Cientista com o ML:** o agente Cientista passa a propor o retreino dos
   modelos e os experimentos do bandit, com aprovação humana e trilha de auditoria.
3. **Integração com o Telegram e funcionamento do fluxo de conversa:** o devedor negocia
   com o agente pelo Telegram, no mesmo fluxo do chat do Mizan.
4. **Legislação:** base jurídica interna (LGPD, CDC e normas de crédito), consultada pelo
   agente antes de ações com impacto jurídico.

## 2. As metas foram cumpridas?

**Sim, as quatro.**

| Meta | Situação | Evidência principal |
|---|---|---|
| 1. Cibersegurança | Cumprida | [PR #28](https://github.com/mauricionimer/MIZAN/pull/28) · [Prova de segurança](PROVA_SEGURANCA_RESULTADO.md): APROVADA em 01/11, 18 de 18 etapas |
| 2. Cientista com o ML | Cumprida | [PR #29](https://github.com/mauricionimer/MIZAN/pull/29) · 21 testes do aprendizado aprovados |
| 3. Telegram e conversa | Cumprida | Commits de 27/10 a 31/10 · testes do canal e bateria de cenários aprovados |
| 4. Legislação | Cumprida | [22ec793](https://github.com/mauricionimer/MIZAN/commit/22ec793) e correções do PR #29 · testes jurídicos aprovados |

### O que foi feito em cada meta

**Meta 1: Cibersegurança** (PR #28, 29/10)

- **Itens do plano corrigidos** (S1 a S16 e S18):
    - limite de tentativas de login por e-mail e por IP;
    - senhas com PBKDF2 de 600 mil iterações;
    - chaves de API e tokens de redefinição guardados só como hash;
    - documentação da API fechada em produção;
    - erro interno que nunca aparece na resposta;
    - RLS na tabela de permissões;
    - CSP, HSTS e bloqueio de iframe no frontend;
    - sessão de no máximo 30 dias;
    - CPF mascarado na tela;
    - limite de rodadas de IA por conversa no Telegram.
- **Segredos obrigatórios:** o servidor só sobe com segredo forte (JWT com 32 ou mais
  caracteres) e chave de criptografia válida. Os dois foram configurados no Render, com
  deploy aprovado.
- **Dependências atualizadas:** pip-audit e npm audit sem vulnerabilidade conhecida.
- **Prova automática:** `backend/prova_seguranca.py` refeita no código atual, com
  resultado **APROVADO** (18/18).

**Meta 2: Cientista conectado ao ML** (PR #29, 31/10)

- **Avaliação diária:** o Cientista verifica se há resultados confirmados suficientes
  (mínimo de 300 pessoas, 30 pagamentos, 30 não pagamentos e 30 dias de maturidade) e
  propõe coleta de dados ou retreino do score.
- **Nada treina sem aprovação humana:**
    - o servidor confere de novo os critérios e o hash da base;
    - treina os modelos de score e de preço da empresa;
    - o candidato nasce inativo, e só o COMANDO ativa, com volta à versão anterior.
- **Experimentos do bandit (LinUCB):** sorteio estável entre grupos, duração de 60 dias e
  parada se a taxa de pagamento cair.
- **Auditoria:**
    - base cifrada e com hash;
    - eventos imutáveis no banco (gatilhos e RLS);
    - exportação verificável;
    - painel no Laboratório.

**Meta 3: Telegram e fluxo de conversa** (27/10 a 31/10)

- **Convite por pessoa:** o devedor conversa com o agente pelo Telegram a partir de um
  link único, e o banco guarda só o hash do segredo.
- **Identidade e passagem humana:** a identidade é confirmada de novo no canal novo. Quando
  o caso passa para um atendente, ele responde pelo Mizan e a resposta chega ao Telegram.
- **Mesma conversa do chat do Mizan:** cada mensagem passa pelo mesmo fluxo de agentes
  (Triagem, Negociador, Auditor e travas de saída).
- **Mais rápido:** em simulação, as três primeiras respostas caíram de 7,0/8,8/10,6 s para
  4,8/4,9/6,4 s. O "digitando…" aparece na hora e o `/start` some da conversa.
- **Agendamento sem duplicar:** cada tipo de compromisso tem um só ativo, e remarcar move o
  existente.
- **Telas ao vivo:** agenda e casos se atualizam sozinhos em cerca de 2 s.

**Meta 4: Legislação** (31/10)

- **Base jurídica interna:** 8 normas federais e 1.348 dispositivos, estruturados por
  artigo, parágrafo, inciso e alínea, com origem, versão e commit do acervo. As normas são:
    - LGPD e CDC;
    - Cadastro Positivo;
    - trechos do Código Civil e do Marco Civil;
    - Decretos 11.150 e 11.567;
    - Resolução CMN 4.949.
- **Busca híbrida:** termos exatos mais semântica local.
- **Decisão em código:** prosseguir, prosseguir com condições, não prosseguir ou revisão
  humana. Fonte ausente, conflitante ou desatualizada sempre leva à revisão humana.
- **Quando o agente consulta:**
    - antes de aplicar o plano;
    - antes de iniciar contatos;
    - antes de abrir o Telegram;
    - antes de registrar um acordo;
    - diante de pedidos do titular dos dados e de contestações.
- **Registro de cada decisão:** fontes e incertezas, fatos cifrados e leitura só por
  administrador.
- **Na conversa:**
    - o agente não cita lei por conta própria;
    - registra os pedidos sobre dados pessoais;
    - antes do acordo, mostra o valor total e as parcelas (CDC, art. 52).
- **Banco de produção:** as tabelas de registro foram criadas em 01/11.

## 3. O que impediu ou ficou pendente

Nenhuma meta foi bloqueada. Ficaram pendências que não impediram o cumprimento:

- **Legislação: conferência oficial.** O texto das leis ainda não foi conferido na fonte
  oficial (Planalto); o servidor de produção precisa rodar essa etapa. Até lá, as normas
  aparecem como "não conferidas", e as decisões que exigem texto conferido vão para
  revisão humana.
- **Legislação: Decreto 11.150.** O texto do acervo está desatualizado (Decreto
  11.567/2023) e fica sinalizado.
- **Cientista.** O retreino depende de um volume de resultados reais que ainda não existe:
  300 pessoas com desfecho confirmado. Falta confirmar que as migrações do aprendizado
  foram aplicadas em produção.
- **Testes.** Os testes ligados às quatro metas passam:
    - segurança: 18 de 18 etapas na prova;
    - Cientista: 21 testes do aprendizado, mais o teste do agente;
    - Telegram e conversa: 6 arquivos, mais a bateria de cenários;
    - legislação: 3 arquivos.

    Na suíte completa do backend (126 arquivos), ainda falham três testes antigos, fora
    destas metas (links da Central de Ajuda, otimização de páginas e API de treino). Os
    testes de treino do modelo de score passam de 25 minutos quando rodam em paralelo.
    Esses pontos entram na próxima entrega.

## 4. Link de evidência do progresso

[github.com/mauricionimer/MIZAN/blob/master/docs/RELATORIO_01_11.md](https://github.com/mauricionimer/MIZAN/blob/master/docs/RELATORIO_01_11.md)
(este relatório, com os links para cada commit, documento e teste).

## 5. Documento de referência: o que foi atualizado e feito

### Por meta

| Meta | Commits | Documentação | Testes |
|---|---|---|---|
| 1. Cibersegurança | [5d2f141](https://github.com/mauricionimer/MIZAN/commit/5d2f141), [230d5bf](https://github.com/mauricionimer/MIZAN/commit/230d5bf), [933b15d](https://github.com/mauricionimer/MIZAN/commit/933b15d), [4860abd](https://github.com/mauricionimer/MIZAN/commit/4860abd) | [PROVA_SEGURANCA_RESULTADO.md](PROVA_SEGURANCA_RESULTADO.md) | `test_seguranca_estatico`, `test_seguranca_plano` e mais 14 testes de segurança |
| 2. Cientista com o ML | [364349b](https://github.com/mauricionimer/MIZAN/commit/364349b), [ffb53c2](https://github.com/mauricionimer/MIZAN/commit/ffb53c2), [b9c8c2c](https://github.com/mauricionimer/MIZAN/commit/b9c8c2c) | [CIENTISTA_APRENDIZADO.md](CIENTISTA_APRENDIZADO.md) | `test_cientista_aprendizado`, `test_cientista_api`, `test_agente_cientista` |
| 3. Telegram e conversa | [10c4ab0](https://github.com/mauricionimer/MIZAN/commit/10c4ab0), [b424be0](https://github.com/mauricionimer/MIZAN/commit/b424be0), [793ba7a](https://github.com/mauricionimer/MIZAN/commit/793ba7a), [c1fed1b](https://github.com/mauricionimer/MIZAN/commit/c1fed1b), [f885922](https://github.com/mauricionimer/MIZAN/commit/f885922), [28d5fd5](https://github.com/mauricionimer/MIZAN/commit/28d5fd5), [d3b8072](https://github.com/mauricionimer/MIZAN/commit/d3b8072), [9b646c3](https://github.com/mauricionimer/MIZAN/commit/9b646c3) | [TELEGRAM.md](TELEGRAM.md) | `test_agente_telegram`, `test_telegram_conexao`, `test_agente_conversa`, `test_agente_agendamento`, `test_mudancas`, bateria de cenários |
| 4. Legislação | [22ec793](https://github.com/mauricionimer/MIZAN/commit/22ec793), [364349b](https://github.com/mauricionimer/MIZAN/commit/364349b) | [RAG_JURIDICO.md](RAG_JURIDICO.md) | `test_juridico_base`, `test_juridico_fluxos`, `test_correcoes_juridicas` |

### Outras atualizações do período

- **Experiência de uso (19 a 24/10):**
    - login com fundo animado e hub de entrada;
    - pastas de devedores com semáforo dos agentes;
    - indicadores em bento;
    - correções da auditoria de UX ([PR #27](https://github.com/mauricionimer/MIZAN/pull/27)).
- **Agenda da equipe (19 a 21/10):** operadores, demandas e aprovação do administrador;
  cadastro da disponibilidade de horário de cada operador.
- **Escritório dos agentes (21/10):** visão em pixel art com telemetria real de cada agente.
- **Desempenho (23/10):** menos consultas ao banco e carregamento antecipado das páginas.
- **Negociador (24/10):** abertura mais humana e condução da conversa para o pagamento.
- **Documentação (24/10):**
    - [arquitetura](ARQUITETURA_MIZAN.md);
    - [fluxo dos agentes](FLUXO_AGENTES.md);
    - [BMC](BMC_MIZAN.md);
    - [comparativo de concorrentes](COMPARATIVO_CONCORRENTES.md);
    - [entregáveis do AKCIT Camp](../ENTREGAVEIS_AKCIT_2026.md).
- **Revisão geral (18/10):** escopo por empresa, idempotência de webhooks, sessões e
  limites de uso.
- **Integração do PR #29 (01/11):** cinco testes que quebraram com a mudança do bandit e do
  registro jurídico foram ajustados ([b2e0122](https://github.com/mauricionimer/MIZAN/commit/b2e0122),
  [4e3a12c](https://github.com/mauricionimer/MIZAN/commit/4e3a12c)). A prova de segurança
  foi refeita no commit `4e3a12c`.

### Como conferir

- **Histórico do período:** `git log --since=2026-10-18` no repositório.
- **Prova de segurança:** `cd backend && python prova_seguranca.py`.
- **Testes de uma meta:** `python test_juridico_base.py`, por exemplo, ou
  `python -m pytest test_cientista_aprendizado.py`.
