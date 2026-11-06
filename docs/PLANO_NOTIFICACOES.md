# Notificações do Mizan: mapa e plano

**Data:** 06/11/2026 · **Status:** proposta para aprovação (decisões na seção 10)
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
| Aprovação de reunião (`/agente/agenda/{id}/atribuir`) | O administrador escolhe quem atende | Gera "reunião atribuída a você" (N08) |
| Disponibilidade do operador | Dias e horários de trabalho | Os lembretes respeitam o horário de cada um |
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
7. **Horário de Brasília e horário de trabalho.** Os lembretes usam o fuso de Brasília. Fora do horário
   do operador, só o urgente avisa na hora; o resto espera o início do turno.

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
  - urgente não lido em 15 minutos vai também para o administrador;
  - prioridade alta não resolvida até o fim do dia entra no resumo do administrador.

---

## 4. Mapa de eventos

**Prioridades:**
- **Urgente:** sino, aviso na tela e navegador; escala em 15 minutos.
- **Alta:** sino e navegador.
- **Normal:** só o sino.
- **Resumo:** só no resumo diário.

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
| N13 | Um retorno novo entrou na sua agenda (pelo agente ou pelo administrador) | `fonte.criar_agenda`, `POST /agenda` | ✔ | ○ | Normal | Na hora; vários juntos viram um | Agenda | 2 |
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
| N28 | O caso que você atendeu voltou a precisar de você | `grafos.avisar_equipe` com caso devolvido | ✔ | — | Alta | Na hora | Conversa | 2 |
| N29 | Sua dúvida foi respondida na Central de Ajuda | Central de Dúvidas | ✔ | ✔ | Normal | Na hora | Resposta | 2 |

### 4.6 Sistema (administrador)

| # | Evento | Nasce em | Operador | Admin | Prioridade | Quando | O clique leva para | Fase |
|---|---|---|:-:|:-:|---|---|---|:-:|
| N30 | O agente parou: teto de gasto do dia, IA sem cota por mais de 15 min, ou falha final | `agente/logs.py` (`teto_ia`, `ia_aguardando`, `falha_final`) | — | ✔ | **Urgente** | Na hora; no máximo 1 por hora | Agentes | 1 |
| N31 | A sincronização com o banco do cliente falhou | `_auto_sync_todas_conexoes` | — | ✔ | Alta | Na hora; 1 por conexão por dia | Conexões | 2 |
| N32 | O Cientista tem proposta para aprovar, ou parou um experimento por dano | `backend/aprendizado` | — | ✔ | Normal (proposta) e Alta (parada) | Na hora | Laboratório | 2 |
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
| `tipo` | Código do mapa (N01 a N33) |
| `prioridade` | `urgente`, `alta`, `normal` ou `resumo` |
| `titulo` (até 90 letras), `texto` (até 280) | O que aparece; nunca o CPF |
| `link` | Para onde o clique leva (rota interna do Mizan) |
| `entidade`, `entidade_id` | O que resolve a notificação (compromisso, caso, pedido) |
| `chave` (única por pessoa) | Não duplica o mesmo aviso |
| `agrupadas` | Quantos avisos iguais se juntaram nesta linha ("3 mensagens novas") |
| `lida_em`, `resolvida_em` | Fim da notificação |
| `entregue` | Por quais canais externos já saiu, e quando |

A tabela tem RLS ligada, como as outras: só o servidor lê e escreve. As notificações lidas são apagadas
depois de 90 dias. Na fase 2 entram as **preferências** de cada pessoa: canais por tipo e horário
silencioso.

**Servidor:**
- `backend/notificacoes.py`:
  - um **catálogo** com os 33 tipos (texto, prioridade, destino e link);
  - a função `notificar(tipo, empresa, contexto)`. Ela escolhe os destinatários pela regra da seção 3,
    junta os repetidos, grava e avisa as telas abertas. Nunca levanta erro.
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
- **Preferências** em "Minha conta" (fase 2).
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

## 10. Decisões (com a minha recomendação)

1. **Canais da fase 1:** sino, aviso na tela e número na aba. *Recomendo:* começar assim; o aviso do
   navegador entra na fase 2.
2. **Devedor sem responsável:** vai para todos os administradores, ou para um "plantonista" escolhido.
   *Recomendo:* todos os administradores, até a equipe crescer.
3. **Horário silencioso padrão:** das 20h às 8h, só o urgente avisa. *Recomendo:* esse padrão,
   ajustável por pessoa na fase 2.
4. **Antecedência dos lembretes:** reunião 30 e 5 minutos antes, retorno 15 minutos antes, agenda do
   dia às 8h. *Recomendo:* esses valores, configuráveis por empresa depois.
5. **Resumo diário por e-mail:** desligado por padrão, cada pessoa liga se quiser. *Recomendo:* sim.
6. **Execução:** depois de aprovado, a fase 1 sobe com testes. Para funcionar, é preciso rodar um SQL
   no Supabase, que eu mando junto.
