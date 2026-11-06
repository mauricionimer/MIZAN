# Notificações do Mizan: mapa e plano

**Data:** 06/11/2026 · **Status:** aprovado em 06/11/2026; fases 1 e 2 em execução (plano de execução na seção 11)
**Perfis:** administrador e operador. O COMANDO segue com os avisos que já tem (Dúvidas e telas da plataforma).

---

## Resumo em um minuto

- **Hoje quase nada avisa ninguém.** Existem só os números no menu (Agenda e Dúvidas) e as telas que se
  atualizam sozinhas a cada 2 s.
  - Todo trabalho que o agente passa para a equipe vira um "retorno" na agenda: transferência, reunião,
    pagamento informado e pedido sobre dados pessoais. Só fica sabendo quem abre a Agenda.
  - Contestação e pedido para parar só mudam a situação do caso: não avisam ninguém.
  - O sinal de risco grave vira um retorno comum na agenda, sem nenhum destaque de urgência.
  - Não há lembrete de horário: uma reunião às 14h30 não avisa às 14h.
- **Proposta:**
  - um **sino com central de notificações** para cada pessoa;
  - **aviso na tela** para o que é urgente;
  - **lembretes por horário**: reunião 30 e 5 minutos antes, retorno 15 minutos antes e a agenda do dia às 8h;
  - **escalonamento** para o administrador quando algo urgente fica sem resposta;
  - depois, o aviso do navegador e um resumo diário por e-mail.
- **33 eventos mapeados** (seção 4), cada um com quem recebe, prioridade, quando e para onde o clique leva.
- **Três fases:**
  1. Sino, central, lembretes e os 16 eventos mais importantes (3 a 4 dias).
  2. Aviso do navegador, preferências, horário silencioso, escalonamento, e-mail diário e os outros eventos
     (2 a 3 dias).
  3. Opcional: aviso no celular com o Mizan fechado e no Telegram da equipe (cerca de 3 dias).

---

## 1. O que já existe

| Peça | O que faz hoje | Como entra no plano |
|---|---|---|
| Número da Agenda no menu (`useAvisoAgenda`) | Conta compromissos atrasados e de hoje e amanhã | Continua; o sino não repete o que é só contagem |
| Número das Dúvidas (`useAvisosDeDuvida`) | Respostas novas na Central de Ajuda | Vira também uma notificação (N29) |
| Telas ao vivo (`/mudancas`, a cada 2 s) | Avisa as telas abertas quando agenda ou casos mudam | Ganha o assunto "notificações": o sino atualiza em até 2 s |
| Itens "retorno" que o agente cria | Transferência, reunião, pagamento informado, pedido LGPD e mensagem em caso com a equipe | Cada um passa a gerar a notificação certa para a pessoa certa |
| Aprovação de reunião (`/agente/agenda/{id}/atribuir`) | O administrador escolhe quem atende | Gera "reunião atribuída a você" (N07) |
| Disponibilidade do operador | Dias e horários de trabalho, usados pelo agente | Continua só para o agente; quem decide quando o aviso toca é o horário silencioso de cada pessoa (seção 6) |
| Registro operacional dos agentes (`agente/logs.py`) | Teto de gasto, IA sem cota, falha final | Gera o alerta "agente parado" para o administrador (N30) |
| E-mail (Brevo) | Redefinição de senha, retreino, deriva | Canal do resumo diário (fase 2) |
| Bot do Telegram | Conversa com o devedor | Canal opcional da equipe (fase 3) |
| `AvisoDesfazer` | Aviso fixo no rodapé, que some sozinho | Mesmo estilo para o aviso de urgente |

---

## 2. Princípios

1. **Notifica o que pede ação, ou o que a pessoa precisa saber agora.** O resto vai para o resumo do dia.
2. **Cada notificação tem dono, ação e fim.** Dono é uma pessoa. A ação é o clique ("Abrir conversa",
   "Aprovar reunião"). O fim acontece quando a pessoa lê, ou quando o assunto se resolve sozinho (a reunião
   foi aprovada, o retorno foi cumprido).
3. **Sem barulho.**
   - Mensagens seguidas do mesmo devedor viram uma notificação só.
   - Quem fez a ação não é notificado dela.
   - A prioridade escolhe o canal.
   - Há limite por hora para os alertas de sistema.
4. **Nada urgente se perde.** Urgente sem leitura em 15 minutos vai também para o administrador.
5. **Privacidade.**
   - Dentro do Mizan, a notificação pode trazer o primeiro nome do cliente.
   - Fora dele (navegador, e-mail, Telegram), só o tipo e o horário. Nunca nome, CPF ou valor.
   - Nenhuma notificação leva o CPF.
6. **Notificar nunca atrapalha o atendimento.** Se a notificação falhar, o agente segue (como os logs).
7. **Horário de Brasília e horário silencioso.** Os lembretes usam o fuso de Brasília. No horário
   silencioso de cada pessoa (padrão das 20h às 8h), só o urgente toca; o resto fica no sino, sem tocar.

---

## 3. Quem recebe

- **Operador:** só o que é dele:
  - os devedores pelos quais é responsável;
  - os casos que assumiu;
  - as reuniões atribuídas a ele;
  - os compromissos na agenda dele.
- **Administrador:**
  - tudo que pede decisão: aprovar reunião, contestação, pedido LGPD e escalonamento;
  - o que não tem dono: devedor sem responsável e compromissos que estão com o agente;
  - os alertas de sistema e o resumo da equipe.
- **Regra de destino:** o responsável pelo devedor. Se não houver, ou se o responsável for o agente, todos
  os administradores da empresa recebem.
- **Escalonamento:**
  - urgente não lido em 15 minutos vai também para o administrador (se ele ainda não recebeu o mesmo aviso);
  - o que ficou para trás (atrasados, reuniões sem atendente, mensagens sem resposta) entra no resumo da
    equipe das 8h (N15).

---

## 4. Mapa de eventos

**Prioridades:**
- **Urgente:** sino, aviso na tela e navegador; escala em 15 minutos.
- **Alta:** sino e navegador.
- **Normal:** só o sino.
- **Resumo:** não toca e não vira item próprio; entra nas contagens do resumo da equipe das 8h (N15).

✔ recebe · ○ recebe só se o devedor não tiver responsável · — não recebe.
Na coluna **Fase**, o 1 marca os eventos da primeira entrega.

### 4.1 Conversas e atendimento

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N01 | Devedor escreveu num caso que está com a equipe (inclui contestado, suspenso, quitado) | `grafos.avisar_equipe` | ✔ quem assumiu ou o responsável | ○ | Alta | Na hora; mensagens seguidas se juntam | Conversa do caso | 1 |
| N02 | O agente passou o caso para uma pessoa | `ferramentas._transferir_para_humano` | ✔ | ○ | Alta | Na hora | Ficha de passagem e conversa | 1 |
| N03 | Sinal de risco grave (sofrimento) | `grafos.transferir` (risco) | ✔ | ✔ sempre | **Urgente** | Na hora; escala em 15 min | Conversa do caso | 1 |
| N04 | O link do Telegram foi usado em outro aparelho | `canal_telegram.vincular` | ✔ normal | ✔ alta | Alta | Na hora | Caso | 2 |
| N05 | O caso foi assumido por outra pessoa ou devolvido ao agente | `agente/api.py` `controle_do_gestor` | ✔ quem estava com ele | — | Normal | Na hora | Caso | 2 |

### 4.2 Reuniões (atendimento com uma pessoa)

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N06 | O agente marcou uma reunião e ela espera aprovação | `ferramentas._marcar_atendimento_humano` | ✔ se foi sugerido (normal) | ✔ | Alta | Na hora | Aprovar e escolher quem atende | 1 |
| N07 | Uma reunião foi aprovada e atribuída a você | `agente/api.py` `atribuir` | ✔ | — | Alta | Na hora | Reunião na agenda | 1 |
| N08 | O devedor mudou o horário (a reunião volta para aprovação) | `ferramentas._mover` | ✔ quem estava com ela | ✔ | Alta | Na hora | Aprovar de novo | 1 |
| N09 | O devedor desmarcou a reunião | `ferramentas` desmarcar | ✔ | ✔ normal | Alta | Na hora | Agenda | 1 |
| N10 | Lembrete: reunião em 30 minutos e em 5 minutos | relógio | ✔ | — | Alta (30 min) e **Urgente** (5 min) | 30 e 5 min antes | Reunião e conversa | 1 |
| N11 | Reunião sem atendente a 2 horas do horário | relógio | — | ✔ | **Urgente** | 2 h antes | Aprovar e escolher quem atende | 1 |
| N12 | Reunião passou e não foi registrada como realizada | relógio | ✔ | resumo | Alta | 30 min depois | Agenda | 2 |

### 4.3 Retornos, promessas e pagamentos

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N13 | O assistente deixou uma tarefa na sua agenda que não tem evento próprio (hoje: pagamento parcial para conferir a baixa) | `agente/acompanhamento.py` | ✔ | ○ | Normal | Na hora | Pasta do cliente | 2 |
| N14 | Lembrete de retorno com hora marcada | relógio | ✔ | — | Alta | 15 min antes | Pasta do cliente | 1 |
| N15 | Agenda do dia: compromissos de hoje e atrasados | relógio | ✔ | ✔ resumo da equipe | Normal | 8h, uma vez por dia | Agenda | 1 |
| N16 | A promessa venceu sem pagamento confirmado | relógio | ✔ | resumo | Alta | 9h do dia seguinte | Pasta do cliente | 1 |
| N17 | Compromisso atrasado há mais de 1 dia útil | relógio | — | ✔ | Alta | 9h | Agenda da equipe | 2 |
| N18 | O devedor diz que pagou: conferir | `ferramentas._registrar_pagamento_informado` | ✔ | ○ | Alta | Na hora | Pagamentos | 1 |
| N19 | Um pagamento foi confirmado | `POST /devedores/{cpf}/confirmar-pagamento` e `/webhook/pagamento` | ✔ | resumo | Normal | Na hora | Pasta do cliente | 2 |
| N20 | O agente fechou um acordo | `ferramentas._registrar_aceite` | ✔ | resumo | Normal | Na hora | Pasta do cliente | 2 |
| N21 | Um acordo foi quebrado | `ferramentas._marcar_promessa_quebrada` | ✔ | resumo | Alta | Na hora | Pasta do cliente | 2 |

### 4.4 Pedidos do devedor e LGPD

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N22 | Contestação: o devedor não reconhece a dívida | `ferramentas._abrir_contestacao` | ✔ | ✔ | Alta | Na hora | Caso | 1 |
| N23 | O devedor pediu para parar o contato | `ferramentas._suspender_cobranca` | ✔ | resumo | Normal | Na hora | Caso | 2 |
| N24 | Pedido sobre os dados pessoais (LGPD) | `ferramentas._registrar_pedido_titular` | ✔ normal | ✔ | Alta | Na hora | Pedido e caso | 1 |
| N25 | O prazo do pedido LGPD está perto ou venceu | relógio | — | ✔ | Alta (3 dias antes) e **Urgente** (no dia) | 3 dias antes e no dia | Pedido | 2 |

### 4.5 Equipe

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N26 | Você recebeu devedores (distribuição da fila ou troca de responsável) | `distribuir_fila`, troca de responsável | ✔ | — | Normal | Na hora; vários juntos viram um | Minha fila | 2 |
| N27 | Uma tarefa administrativa vence hoje | relógio | — | ✔ | Normal | 8h | Tarefas | 2 |
| N28 | Mensagem do devedor sem resposta da equipe há 2 horas | relógio | ✔ | ○ | Alta | 2 h depois da mensagem | Conversa do caso | 2 |
| N29 | Sua dúvida foi respondida na Central de Ajuda | Central de Dúvidas | ✔ | ✔ | Normal | Na hora | Resposta | 2 |

### 4.6 Sistema (administrador)

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N30 | O agente parou: teto de gasto do dia, IA sem cota por mais de 15 min, ou eventos que falharam de vez (a falha num caso só já vira transferência, N02) | `agente/logs.py` (`teto_ia`, `ia_aguardando`, `evento_falhou`) | — | ✔ | **Urgente** | Na hora; no máximo 1 por hora | Agentes | 1 |
| N31 | A sincronização com o banco do cliente falhou | `_auto_sync_todas_conexoes` | — | ✔ | Alta | Na hora; 1 por conexão por dia | Conexões | 2 |
| N32 | O Cientista tem proposta para aprovar, ou parou um experimento por dano | `agente/api.py` (recomendação) e `aprendizado/experimentos.py` (parada) | — | ✔ | Normal (proposta) e Alta (parada) | Na hora | Laboratório | 2 |
| N33 | Segurança: 2FA redefinido, ou conta da empresa bloqueada por tentativas de login | `main.py` (2FA, limite de login) | — | ✔ | Normal e Alta | Na hora | Usuários | 2 |

**Fase 1 = 16 eventos:** N01, N02, N03, N06, N07, N08, N09, N10, N11, N14, N15, N16, N18, N22, N24, N30.

---

## 5. Lembretes por horário (o relógio)

Um passo novo no agendador, que já roda a cada minuto. Cada lembrete tem uma chave única
(por exemplo `N10:<id da reunião>:5min`). Se o servidor reiniciar, o lembrete não sai duas vezes. Se o
servidor estava fora no minuto certo, o lembrete sai assim que ele voltar, até o horário do compromisso.

| Lembrete | Antecedência | Para quem |
|---|---|---|
| Reunião | 30 min e 5 min | Operador atribuído |
| Reunião sem atendente | 2 h | Administradores |
| Retorno com hora | 15 min | Dono do compromisso |
| Agenda do dia | 8h | Cada operador; resumo da equipe para o administrador |
| Promessa vencida | 9h do dia seguinte | Dono da promessa |
| Compromisso atrasado | 9h, após 1 dia útil | Administradores |
| Reunião sem registro | 30 min depois | Operador atribuído |
| Pedido LGPD | 3 dias antes do prazo e no dia | Administradores |

---

## 6. Canais

| Canal | Quando avisa | Fase |
|---|---|---|
| **Sino e central de notificações** | Sempre (todas as prioridades, menos "resumo") | 1 |
| **Aviso na tela** (rodapé, como o "Desfazer") | Urgente, com o Mizan aberto | 1 |
| **Número no título da aba**: "(3) Mizan" | Não lidas, com o Mizan aberto em outra aba | 1 |
| **Aviso do navegador** | Urgente e alta, com o Mizan aberto ou minimizado; a pessoa autoriza uma vez | 2 |
| **Resumo diário por e-mail** | 8h, para quem ligar a opção; sem nome, CPF ou valor | 2 |
| **Aviso no celular com o Mizan fechado** | Urgente e alta. No iPhone, só com o Mizan na tela de início | 3 |
| **Telegram da equipe** | Urgente, para quem ligar o próprio Telegram | 3 |

---

## 7. Como funciona por dentro

**Banco (um SQL novo, `backend/sql/migracao_notificacoes.sql`):**

| Coluna | Para quê |
|---|---|
| `id`, `criado_em` | Identificação |
| `empresa_id`, `usuario_id` | De quem é: uma linha por pessoa, o que facilita marcar como lida |
| `tipo`, `categoria` | Código do mapa (N01 a N33, mais `ESC` do escalonamento) e o grupo dele (conversas, reuniões...) |
| `prioridade` | `urgente`, `alta` ou `normal` (o "resumo" não vira linha: entra nas contagens das 8h) |
| `titulo` (até 90 letras), `texto` (até 280) | O que aparece; nunca o CPF |
| `link` | Para onde o clique leva (rota interna do Mizan) |
| `entidade`, `entidade_id` | O que resolve a notificação (compromisso, caso, pedido) |
| `chave` (única por pessoa) | Não duplica o mesmo aviso |
| `agrupadas` | Quantos avisos iguais se juntaram nesta linha ("3 mensagens novas") |
| `lida_em`, `resolvida_em` | Fim da notificação |
| `escalada_em` | Quando o urgente sem leitura foi levado ao administrador |

A tabela tem RLS ligada, como as outras: só o servidor lê e escreve. As notificações lidas são apagadas
depois de 90 dias. As **preferências** de cada pessoa (canais, horário silencioso e categorias) ficam
numa segunda tabela, `notificacao_preferencias` (detalhes em 11.3).

**Servidor:**
- `backend/notificacoes.py`:
  - um **catálogo** com os 33 tipos (texto, prioridade, destino e link);
  - a função `notificar(tipo, empresa, ...)`. Ela escolhe os destinatários pela regra da seção 3,
    junta os repetidos, grava e avisa as telas abertas. Nunca levanta erro (detalhes em 11.4).
  - Somar um evento novo é uma linha no catálogo e uma chamada no lugar onde ele acontece.
- **Gatilhos:** uma chamada em cada lugar da coluna "Nasce em" do mapa.
- **Resolução automática:** quando um compromisso é cumprido ou cancelado, um caso é assumido ou uma
  reunião é aprovada, as notificações ligadas a ele saem da lista de pendentes.
- **Relógio:** `notificacoes.relogio(agora)` no agendador, a cada minuto.
- **Rotas:**
  - `GET /notificacoes` (lista e contagem);
  - `POST /notificacoes/{id}/lida`;
  - `POST /notificacoes/lidas` (todas);
  - na fase 2, `GET` e `PUT /notificacoes/preferencias`.
  - Cada pessoa só vê as próprias notificações.

**Tela:**
- **Sino no cabeçalho**, com o número de não lidas e um ponto vermelho quando há urgente.
- **Painel lateral** (tela cheia no celular):
  - separação "Agora", "Hoje" e "Antes";
  - em cada item, ícone pelo tipo, texto, tempo e o botão da ação;
  - "Marcar todas como lidas".
- **Aviso na tela** para o urgente e **número no título da aba**.
- **Preferências** na engrenagem do próprio painel (fase 2).
- Tudo segue o `design/GUIA_DE_DESIGN.md`, nos tamanhos 390 px e 1280 px e nos temas claro e escuro.

**Tempo real:** as telas ao vivo já perguntam ao servidor a cada 2 s se algo mudou. Ganham o assunto
"notificações", e o sino só busca a lista quando ela muda.

---

## 8. Fases e critério de pronto

| Fase | Entregas | Pronto quando | Esforço |
|---|---|---|---|
| **1. Núcleo** | SQL; `notificacoes.py` com catálogo e regra de destino; os 16 eventos da fase 1; relógio; rotas; sino, painel, aviso na tela e número na aba; testes | Uma reunião pedida pelo agente avisa o administrador em até 2 s; a reunião atribuída avisa o operador e lembra 30 e 5 min antes; o risco grave avisa os dois na hora | 3 a 4 dias |
| **2. Completo** | Os outros 17 eventos; aviso do navegador; preferências e horário silencioso; escalonamento; resumo diário por e-mail; limpeza após 90 dias | Cada pessoa escolhe o que recebe e onde; urgente sem leitura em 15 min chega ao administrador | 2 a 3 dias |
| **3. Fora do Mizan** (opcional) | Aviso no celular com o Mizan fechado (service worker e chave de push); Telegram da equipe | O operador recebe no celular, com o Mizan fechado, o lembrete da reunião em 5 min | Cerca de 3 dias |

---

## 9. Testes

- **Destino:**
  - o operador só recebe o que é dele;
  - o devedor sem responsável vai para os administradores;
  - outra empresa nunca recebe;
  - quem fez a ação não é notificado.
- **Duplicação:** mensagens seguidas viram uma notificação; o lembrete sai uma vez só, mesmo com
  reinício do servidor.
- **Relógio:** horários em Brasília; 30, 5 e 15 minutos; agenda às 8h; nada sai fora do horário do
  operador (menos o urgente).
- **Resolução automática:** a reunião aprovada some da pendência do administrador; o retorno cumprido
  some da do operador.
- **Privacidade:** nenhum texto com CPF; nos canais externos, nem nome nem valor.
- **Segurança:** uma pessoa não lê nem marca a notificação de outra (teste de autorização das rotas).
- **Robustez:** se a tabela falhar, o agente segue atendendo.
- **Tela:** sino, painel e aviso testados com navegador real em 390 px e 1280 px.
- **Fluxos completos:** o agente marca a reunião → o administrador é avisado → aprova → o operador é
  avisado → lembretes. Testado como os testes dos agentes, com a IA simulada.

---

## 10. Decisões (aprovadas em 06/11/2026)

1. **Canais:** sino, aviso na tela e número na aba desde o início. O aviso do navegador vem junto, na
   fase 2, e só liga quando a pessoa autoriza.
2. **Devedor sem responsável:** vai para todos os administradores da empresa.
3. **Horário silencioso:** das 20h às 8h, só o urgente toca. Cada pessoa muda ou desliga.
4. **Lembretes:** reunião 30 e 5 minutos antes, retorno 15 minutos antes, agenda do dia às 8h.
5. **Resumo por e-mail:** desligado por padrão; cada pessoa liga se quiser.
6. **Execução:** fases 1 e 2 juntas, com testes. A fase 3 (celular com o Mizan fechado e Telegram da
   equipe) fica para depois.

---

## 11. Plano de execução

### 11.1 Ordem de construção

Cada passo termina com teste passando antes do próximo.

| # | Passo | Pronto quando |
|---|---|---|
| 1 | SQL: tabelas `notificacoes` e `notificacao_preferencias` | Roda duas vezes sem erro; RLS ligada; apagar um usuário apaga as notificações dele |
| 2 | Núcleo `backend/notificacoes.py`: catálogo, destino, gravação, agrupamento, resolução | Teste do núcleo passa com o armazém em memória |
| 3 | Gatilhos dos eventos "na hora" (agente e rotas) | Cada evento do mapa tem um teste que cria a notificação certa para a pessoa certa |
| 4 | Relógio: lembretes, agenda do dia, prazos, escalonamento, resumo por e-mail e limpeza | Teste com o relógio parado em horários escolhidos; nada sai duas vezes |
| 5 | Rotas `/notificacoes` e versão por pessoa em `/mudancas` | Ninguém lê nem marca a notificação de outra pessoa |
| 6 | Tela: sino, painel, aviso de urgente, número na aba, aviso do navegador, preferências | Testes de `node --test` e navegador real em 390 px e 1280 px, claro e escuro |
| 7 | Suítes da área, revisão do diff e documentação | Nenhum teste que passava passa a falhar |

### 11.2 Arquivos

**Novos:**
- `backend/sql/migracao_notificacoes.sql`: as duas tabelas, índices e RLS.
- `backend/notificacoes.py`: o núcleo.
- `backend/test_notificacoes.py`: os testes do núcleo, dos gatilhos, do relógio e das rotas.
- `frontend/src/lib/notificacoes.js`: contas puras da tela (seções, tempo, o que avisa), testadas por
  `frontend/tests/notificacoes.test.mjs`.
- `frontend/src/components/Notificacoes.jsx` e `useNotificacoes.js`: sino, painel, aviso e preferências.
- `docs/NOTIFICACOES.md`: como funciona e como ligar.

**Alterados, só por acréscimo:**
- `agente/ferramentas.py`: uma chamada em `executar`, depois que a ferramenta deu certo.
- `agente/grafos.py` (mensagem em caso com a equipe), `agente/acompanhamento.py` (pagamento parcial),
  `agente/canal_telegram.py` (link em outro aparelho), `agente/logs.py` (agente parado),
  `agente/fonte.py` (resolução quando o compromisso muda), `agente/api.py` (reunião atribuída, caso
  assumido ou devolvido, recomendação do Cientista), `aprendizado/experimentos.py` (parada por dano).
- `agente/mudancas.py`: contador por pessoa para o assunto "notificações".
- `main.py`: rotas novas, o passo no agendador, e gatilhos em agenda, pagamentos, fila, dúvidas,
  sincronização e segurança.
- `frontend`: `AppShell.jsx` (sino no cabeçalho), `api.js` (cinco chamadas novas) e
  `useMudancasDoServidor.js` (assunto novo).

### 11.3 Banco

`notificacoes`: uma linha por pessoa.
- **Colunas:**
  - `id` e `criado_em`;
  - `empresa_id` e `usuario_id`;
  - `tipo`, `categoria` e `prioridade`;
  - `titulo` e `texto`;
  - `link`, `entidade` e `entidade_id`;
  - `chave` e `agrupadas`;
  - `lida_em`, `resolvida_em` e `escalada_em`.
- **Chave estrangeira:** `usuario_id` aponta para `usuarios(id)` com apagar em cascata. Excluir um
  cliente (função `excluir_dados_cliente`) ou um usuário apaga as notificações dele no mesmo passo, sem
  mexer na função de exclusão.
- **Índice único parcial:** `(usuario_id, chave)` entre as abertas, ou seja, nem lidas nem resolvidas.
  Dois avisos iguais abertos para a mesma pessoa são impossíveis, mesmo com dois servidores no ar
  durante um deploy.
- **Outros índices:** lista por pessoa e data, abertas por pessoa, e resolução por entidade.

`notificacao_preferencias`: uma linha por pessoa que mudou algo.
- **Colunas:** `dados` (JSON com navegador, e-mail, horário silencioso e categorias desligadas) e
  `resumo_enviado_em`.

As duas tabelas têm RLS ligada e nenhuma política, como as outras: só o servidor lê e escreve.

### 11.4 Núcleo (`backend/notificacoes.py`)

- **Catálogo:** para cada tipo, guarda:
  - categoria e prioridade;
  - título e texto, com a versão para vários avisos juntos;
  - título para fora do Mizan (sem nome);
  - o texto do botão e o link;
  - o modo de repetição:
    - **único:** a mesma chave nunca sai duas vezes. Vale para lembretes e eventos de um item.
    - **agrupar:** enquanto o aviso estiver aberto, soma no mesmo ("3 mensagens novas").
- **`notificar(tipo, empresa, para, contexto, chave, entidade, quantidade=1, exceto=None)`:**
  1. escolhe os destinatários pela regra da seção 3 e tira quem fez a ação;
  2. tira quem desligou a categoria, menos no urgente;
  3. grava ou soma, conforme o modo;
  4. sobe o contador da pessoa em `/mudancas`.
- **Nunca atrasa o atendimento:**
  - a gravação vai para uma fila com uma linha de execução só, fora da conversa;
  - a fila em ordem também evita duas gravações ao mesmo tempo no mesmo servidor;
  - um disjuntor para por 2 minutos depois de 3 falhas seguidas (banco fora, tabela ainda não criada);
  - o log de falha sai no máximo uma vez por minuto, sem dado pessoal;
  - `MIZAN_NOTIFICACOES=0` desliga tudo.
- **`resolver(empresa, entidade, id, tipos)`:** tira da lista de pendentes o que perdeu o sentido.
  - Compromisso cumprido, cancelado ou quebrado: resolve os avisos dele.
  - Remarcado: resolve os lembretes do horário antigo.
  - Atribuído: resolve a aprovação pendente.
  - Caso assumido: resolve a transferência.
- **Texto:**
  - só o primeiro nome do devedor;
  - nunca CPF, valor ou texto da conversa;
  - links só para telas internas, com ids.

### 11.5 Gatilhos

| Evento | Onde | Chave (não repete) | Resolve quando |
|---|---|---|---|
| N01 | `grafos.avisar_equipe` | agrupa por caso | O compromisso "Nova mensagem" é resolvido |
| N02, N03 | `executar` → `transferir_para_humano`; risco grave quando a triagem marcou sofrimento grave | compromisso da transferência | O compromisso é resolvido ou o caso é assumido |
| N04 | `canal_telegram.vincular` (tentativa de outro chat) | caso e dia | — |
| N05 | `controle_do_gestor` (assumir e devolver) | caso, ação e hora | — |
| N06, N08 | `executar` → `marcar_atendimento_humano` e `remarcar_compromisso` (reunião) | reunião e horário | Atribuída, desmarcada ou remarcada |
| N07 | `api.atribuir` | reunião e operador | Remarcada (volta para aprovação) ou resolvida |
| N09 | `executar` → `desmarcar_compromisso` (reunião) | reunião | — |
| N13 | `acompanhamento.py` (pagamento parcial) | compromisso | Compromisso resolvido |
| N18 | `executar` → `registrar_pagamento_informado` | caso e data informada | Compromisso resolvido |
| N19 | `_cumprir_promessas` (todas as baixas de pagamento passam por ela) | agrupa por pessoa e dia | — |
| N20, N21 | `executar` → `registrar_aceite` e `marcar_promessa_quebrada` | agrupa por dia; quebra por compromisso | — |
| N22, N23 | `executar` → `abrir_contestacao` e `suspender_cobranca` | caso | — |
| N24 | `executar` → `registrar_pedido_titular` | caso, tipo e dia | Compromisso resolvido |
| N26 | `distribuir_fila` e `atribuir_responsavel` | agrupa por pessoa e dia, somando a quantidade | — |
| N29 | `comando_responder_duvida` | dúvida e resposta | Quem perguntou abre a resposta |
| N30 | `logs.registrar` | teto: empresa e dia; IA ocupada: empresa e hora; falhas: agrupa por hora | — |
| N31 | `_auto_sync_todas_conexoes` | conexão e dia | — |
| N32 | `agente/api.py` (recomendação gravada) e `experimentos.monitorar` (parada por dano) | recomendação ou experimento | — |
| N33 | redefinição de 2FA, senha trocada pelo aplicativo e bloqueio de login | usuário e hora | — |

### 11.6 Relógio

Um passo novo no agendador, a cada minuto, independente do agente estar ligado. Ele só lê:
- compromissos pendentes de ontem a amanhã com hora marcada;
- uma vez por dia, a agenda do dia.

| Tarefa | Quando roda | Janela (se o servidor estava fora) |
|---|---|---|
| N10, N11, N12, N14 | A cada minuto | Até o horário do compromisso; se sobrou menos de 5 min, sai só o de 5 min |
| Escalonamento (urgente sem leitura) | A cada minuto | Até 6 h depois |
| N28 | A cada 5 minutos | Até 26 h depois da mensagem |
| N15, N27 e resumo por e-mail | 8h | Até 12h |
| N16, N17, N25 | 9h | Até 18h |
| Limpeza (lidas com mais de 90 dias, todas com mais de 180) | 3h | Até 6h |

### 11.7 Rotas

| Rota | Faz |
|---|---|
| `GET /notificacoes` | Lista ("pendentes" ou "todas", 30 por vez), contagem de não lidas e de urgentes, e se cada uma deve tocar agora |
| `POST /notificacoes/{id}/lida` | Marca uma como lida (só a própria) |
| `POST /notificacoes/lidas` | Marca todas como lidas |
| `GET /notificacoes/preferencias` | Preferências da pessoa (com os padrões) |
| `PUT /notificacoes/preferencias` | Salva as preferências (valores conferidos) |

- Todas exigem login e filtram pela pessoa e pela empresa dela.
- O COMANDO recebe a lista vazia (o sino não aparece para ele).
- Sem a tabela, a resposta diz "não ligado" e o sino some, sem erro.
- `/mudancas` ganha o assunto `notificacoes`, contado por pessoa.

### 11.8 Tela

- **Sino** no cabeçalho, antes do botão de tema.
  - Mostra o número de não lidas e um ponto vermelho quando há urgente.
  - O nome acessível diz quantas há.
- **Painel:**
  - abre pela direita no computador e em tela cheia no celular;
  - abas "Pendentes" e "Todas", com as seções "Agora", "Hoje" e "Antes";
  - cada item tem ícone pela categoria, texto, tempo, o botão da ação e "Marcar como lida";
  - tem os cinco estados (carregando, vazio, erro com "Tentar de novo", sem permissão e o conteúdo);
  - "Marcar todas como lidas".
- **Aviso de urgente:**
  - no rodapé, no estilo do "Desfazer", com "Abrir" e "Fechar";
  - fechar não marca como lida.
- **Número na aba:** "(3) Mizan".
- **Aviso do navegador:**
  - só depois que a pessoa autoriza nas preferências;
  - só com a aba escondida, e só para urgente e alta (fora do horário silencioso);
  - texto sem nome do devedor.
- **Preferências** (engrenagem no painel):
  - aviso do navegador;
  - resumo por e-mail;
  - horário silencioso;
  - categorias. O urgente sempre chega.
- Com a aba escondida, o sino continua perguntando a cada 20 s à rota leve `/mudancas`, para o aviso do
  navegador chegar.

### 11.9 Testes

- **Núcleo:**
  - destino: responsável, sem responsável, quem assumiu, administradores;
  - quem fez a ação não recebe;
  - outra empresa nunca recebe;
  - categoria desligada, menos no urgente;
  - agrupamento e repetição;
  - disjuntor;
  - nada de CPF ou valor no texto.
- **Gatilhos:** os fluxos completos do agente com a IA simulada, como nos testes atuais. Exemplos:
  - risco grave avisa os dois;
  - reunião pedida avisa o administrador; aprovada, avisa o operador e resolve a pendência do
    administrador;
  - remarcada volta para aprovação; desmarcada resolve tudo.
- **Relógio:** horário de Brasília parado em momentos escolhidos.
  - 30 e 5 min antes;
  - servidor que volta tarde;
  - 8h e 9h;
  - prazos LGPD;
  - escalonamento só para quem ainda não recebeu;
  - limpeza;
  - nada sai duas vezes.
- **Rotas:**
  - autorização (outra pessoa, outra empresa, COMANDO);
  - marcar como lida;
  - preferências inválidas recusadas;
  - sem tabela.
- **Tela:**
  - funções puras com `node --test`;
  - navegador real em 390 px e 1280 px, claro e escuro, com movimento reduzido;
  - vazio, um item, muitos itens e textos longos.
- **Regressão:** as suítes do agente, da agenda, dos pagamentos e da fila rodam antes de subir.

### 11.10 Como ligar e como voltar atrás

1. O código sobe primeiro. Sem a tabela, ele não quebra nada: o sino não aparece e os gatilhos param no
   disjuntor.
2. O SQL roda no Supabase (`backend/sql/migracao_notificacoes.sql`). Em até 2 minutos as notificações
   começam.
3. Para desligar sem deploy de código: `MIZAN_NOTIFICACOES=0` no Render.
4. Para apagar: as tabelas são novas e não têm dependentes; `drop table` das duas volta ao estado de
   antes.

### 11.11 Riscos e como ficam cobertos

| Risco | Como fica coberto |
|---|---|
| Barulho demais | Agrupamento, quem fez não recebe, categorias desligáveis, horário silencioso |
| Aviso perdido | Escalonamento do urgente e resumo das 8h |
| Atraso na conversa com o devedor | Gravação fora da conversa, em fila própria |
| Aviso duplicado | Chave única por pessoa, também no banco |
| Dado pessoal vazando | Só primeiro nome no Mizan; nada pessoal fora dele; sem CPF em lugar nenhum |
| Banco fora ou SQL não rodado | Disjuntor, sino escondido, nada quebra |
