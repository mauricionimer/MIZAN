# Notificações do Mizan

O sino no topo da tela avisa o administrador e o operador do que precisa deles: mensagem nova num caso
com a equipe, reunião para aprovar, lembrete de horário, pagamento para conferir, risco grave e mais.
O plano completo, com o mapa dos 33 eventos, está em `docs/PLANO_NOTIFICACOES.md`.

---

## Como ligar (uma vez)

1. Rode `backend/sql/migracao_notificacoes.sql` no SQL Editor do Supabase.
   - Pode rodar mais de uma vez.
   - No fim, a conferência deve mostrar `tabelas = 2`, `rls_ligada = true` e `apaga_com_usuario = 2`.
2. Em até 10 minutos (o tempo do disjuntor, se o servidor já tinha tentado antes), os avisos começam.
   Para começar na hora, reinicie o serviço no Render.

Antes do SQL nada quebra: o sino não aparece e os gatilhos param no disjuntor, com uma linha de log por
minuto no máximo ("rode backend/sql/migracao_notificacoes.sql").

## Como desligar

- **Sem deploy:** `MIZAN_NOTIFICACOES=0` no Render desliga tudo. O sino some e nada é gravado.
- **Apagar de vez:** `drop table notificacoes; drop table notificacao_preferencias;`. São tabelas novas,
  sem dependentes.

---

## O que cada pessoa recebe

- **Operador:** o que é dele.
  - mensagens novas nos casos dele;
  - casos passados para ele;
  - reuniões atribuídas a ele, com lembrete 30 e 5 minutos antes;
  - retornos com hora marcada, 15 minutos antes;
  - a agenda do dia às 8h;
  - promessas vencidas, pagamentos informados e confirmados, contestações e pedidos para parar;
  - devedores recebidos na fila e dúvidas respondidas.
- **Administrador:**
  - o que pede decisão: aprovar reunião, reunião sem atendente 2 horas antes, contestação, pedido sobre
    dados pessoais e prazo dele;
  - o que não tem dono: devedor sem responsável ou com o assistente;
  - o resumo da equipe às 8h e os atrasados às 9h;
  - o sistema: agente parado, conexão que falhou, Cientista e segurança da conta.
- **Regra de destino:** o responsável pelo devedor; sem responsável (ou com o assistente), todos os
  administradores da empresa. Quem fez a ação não recebe.
- **COMANDO:** não tem sino. Segue com os avisos que já tem.

## Prioridades e onde aparece

| Prioridade | Sino | Aviso no topo da tela | Aviso do navegador | No horário silencioso |
|---|---|---|---|---|
| Urgente | Sim | Sim | Sim (se a pessoa ligou) | Toca igual |
| Alta | Sim | Não | Sim (se a pessoa ligou) | Fica no sino, sem tocar |
| Normal | Sim | Não | Não | Fica no sino |

- **Escalonamento:** urgente sem leitura em 15 minutos vai também para os administradores que ainda
  não o receberam.
- **Número na aba:** "(3) Mizan".
- **Resumo por e-mail às 8h:** só para quem liga nas preferências. Leva só contagens por assunto.

## Onde fica guardado

- **No sino**, no topo de todas as telas: as mais recentes, com as abas "Não lidas" e "Todas".
- **Na página Notificações** (menu, logo abaixo de "Hoje"), com o número de não lidas no menu:
  - o histórico dos últimos 90 dias, agrupado por dia;
  - filtro por assunto, com quantas não lidas há em cada um, e "Só urgentes";
  - "Marcar todas como lidas" e "Preferências".
  - O sino e a página andam juntos: marcar como lida num muda o outro na hora.
- Cada pessoa vê só as suas. O COMANDO não tem o item no menu; se abrir o endereço, vê a explicação.

## Preferências (engrenagem no painel)

- **Aviso do navegador:** liga só depois que a pessoa autoriza no navegador. O texto é genérico
  ("Atendimento urgente"), sem o nome do cliente.
- **Resumo por e-mail:** desligado por padrão.
- **Horário silencioso:** das 20h às 8h por padrão; cada pessoa muda ou desliga.
- **Assuntos:** cada um pode ser desligado. O urgente sempre chega.

---

## Privacidade

- **No sino:** só o primeiro nome do devedor. Nunca CPF, valor ou texto da conversa.
- **Fora do Mizan** (navegador, e-mail): nem o nome.
- **Links:** só para telas internas. O banco recusa outro endereço, e a tela troca qualquer outro pelo
  Início.
- **Retenção:** as lidas ou resolvidas são apagadas depois de 90 dias; qualquer uma, depois de 180.
- **Exclusões:** apagar um usuário, ou excluir o cliente inteiro, apaga as notificações e as
  preferências dele no mesmo passo.
- **Logs:** guardam só o tipo do erro, sem destinatário nem texto.

## Como funciona por dentro

- **Núcleo:** `backend/notificacoes.py`.
  - Catálogo dos tipos, regra de destino, gravação, agrupamento ("Maria mandou 3 mensagens"),
    resolução, relógio e leitura.
- **Gravação fora da conversa:** a gravação vai para uma fila com uma linha de execução só.
  - A conversa com o devedor não espera.
  - Nada é gravado duas vezes ao mesmo tempo.
  - Um disjuntor para por 2 minutos depois de 3 falhas seguidas (10 minutos se a tabela não existe).
- **Sem repetição:** cada aviso tem uma chave. O banco garante um só aberto por pessoa e chave, mesmo
  com dois servidores no ar durante um deploy.
- **Relógio:** um passo no agendador, a cada minuto, mesmo com o agente desligado.
  - Lembretes;
  - escalonamento;
  - mensagens sem resposta a cada 5 minutos;
  - agenda do dia e e-mail às 8h;
  - promessas, atrasados e prazos LGPD às 9h;
  - limpeza às 3h.
- **Tempo real:** `/mudancas` traz a versão das notificações de cada pessoa. O sino atualiza em até 2 s
  com a aba aberta e em até 20 s com ela escondida (para o aviso do navegador).
- **Rotas:**
  - `GET /notificacoes` (filtros: `filtro`, `categoria`, `prioridade`; devolve também `por_categoria`);
  - `POST /notificacoes/{id}/lida`;
  - `POST /notificacoes/lidas`;
  - `GET` e `PUT /notificacoes/preferencias`.
  - Cada pessoa só vê e marca as próprias, dentro da empresa dela.
- **Tela:** `frontend/src/components/Notificacoes.jsx` e `useNotificacoes.jsx` (sino, painel e aviso) e
  `frontend/src/pages/Notificacoes.jsx` (a página), com as contas puras em `frontend/src/lib/notificacoes.js`.

## Testes

- `python backend/test_notificacoes.py`:
  - núcleo, gatilhos do agente e das rotas;
  - relógio com a hora parada;
  - rotas e autorização;
  - também entra na prova de segurança.
- `node --test frontend/tests/notificacoes.test.mjs`: as contas da tela.
- `node frontend/tests/notificacoes.ui.mjs`: navegador real em 390 px e 1280 px, claro e escuro, com a
  API simulada. `MIZAN_FOTOS=<pasta>` guarda as fotos.

## Somar um evento novo

1. Uma linha no `CATALOGO` de `backend/notificacoes.py`: categoria, prioridade, texto, link e modo.
2. Uma chamada a `notificacoes.notificar(...)` no lugar onde o evento acontece.
3. Um teste em `test_notificacoes.py`.

Nunca ponha CPF, valor ou texto da conversa no texto do aviso. O teste confere os modelos.
