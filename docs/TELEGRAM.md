# Canal Telegram

O devedor conversa com o agente do Mizan pelo Telegram. O agente é o mesmo da tela de
demonstração (Triagem, Negociador, Auditor...): o Telegram só traz a mensagem e leva a resposta de volta.

## Como funciona

1. A equipe abre o caso em **Agentes → Conversas** e toca em **Convite Telegram**: sai um link
   `https://t.me/<bot>?start=<código>` (vale por 7 dias e liga **um** Telegram: o primeiro que abrir).
   **Cada pessoa precisa do próprio link.** Na demonstração com duas pessoas, gere um convite em
   dois devedores diferentes e mande um link para cada uma.
2. O devedor abre o link e toca em **Iniciar**. O chat fica ligado àquele caso.
3. Cada mensagem dele vira um evento `mensagem_devedor` na fila. A resposta do agente (já passada pelo
   Auditor e pelas travas de saída) volta ao mesmo chat. Lembretes do Acompanhamento seguem pelo mesmo caminho.
4. Ligar o chat **não confirma quem é a pessoa**: a confirmação de identidade continua sendo do agente.

## Configuração (uma vez)

1. No Telegram, fale com **@BotFather**: `/newbot`. Guarde o **token** e o **nome de usuário** do bot.
2. No servidor (Render → Environment), defina:

| Variável | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | o token do BotFather (segredo) |
| `TELEGRAM_BOT_USERNAME` | o usuário do bot, sem `@` |
| `TELEGRAM_WEBHOOK_SECRET` | um texto aleatório de 16+ caracteres (`A-Z a-z 0-9 _ -`) |
| `MIZAN_AGENTE_ATIVO` | `1` (já usado pelo agente) |

3. Publique o backend e, no seu computador, aponte o bot para o servidor:

```
python telegram_webhook.py ligar https://SEU-SERVIDOR.onrender.com
python telegram_webhook.py status
```

## A conversa é a mesma do Mizan

O agente do Telegram é o mesmo do chat do Mizan, e a conversa começa do mesmo jeito:

- Ao abrir o convite, quem fala primeiro é o agente, com a mesma abertura da abordagem do plano
  ("Olá, Maria! Aqui é o assistente virtual de …, posso confirmar se estou falando com você?").
  Caso novo passa pelo Estrategista, que escolhe o tom, como no plano. Vale a qualquer hora,
  porque foi a pessoa quem chamou.
- Se o plano já tinha aberto a conversa e ninguém respondeu, essa mesma abertura chega ao Telegram
  (sem duplicar no Mizan).
- Um Telegram novo no caso **recomeça a conversa**. A IA só lê dali para frente, sem testes pela tela
  nem o que outra pessoa disse, e a identidade precisa ser confirmada de novo. No chat do Mizan, uma
  linha marca onde a conversa recomeçou; o histórico anterior continua visível.
- Com o Telegram ligado, a tela do Mizan não escreve como o devedor (a caixa fica bloqueada). Para
  falar com ele, **Assumir o caso** e responder como atendente.

## O que pode dar errado com o link (e o que a pessoa vê)

| Situação | Resposta do bot | O que a equipe vê |
|---|---|---|
| A mesma pessoa abre o link de novo | "Você já está conectado" | nada muda |
| Outra pessoa abre um link já usado | "Este link já foi usado em outro Telegram. Cada pessoa precisa do próprio link" | aviso amarelo no caso |
| A equipe gerou um link mais novo | "Este link foi substituído" | o selo mostra o convite novo |
| Passou de 7 dias | "Este link venceu" | o selo volta a "Sem Telegram" |
| Link cortado ou alterado | "Não reconheci este link" | nada |
| Escreve sem ter aberto um link | "Abra o link que o banco enviou" | nada |

Gerar um convite com o Telegram já ligado (ou com um convite pendente) pede confirmação, porque o link novo
substitui o anterior. **Desligar** solta o chat do caso e invalida o link.

O selo ao lado do nome mostra o estado: **Telegram ligado**, **Convite enviado (vale até…)**, **Sem Telegram** ou
**bloqueou o bot**.

## Quando a equipe assume o caso

Em **Agentes → Conversas**, **Assumir o caso** tira o agente. A caixa de texto passa a ser **Responder como atendente**:
o que a pessoa escreve fica registrado no caso (marcado como "Atendente") e chega no Telegram do devedor. O que o
devedor responde aparece no mesmo chat. O agente não responde por cima. Mensagens de pessoa **não passam pelo
Auditor**: quem escreve responde pelo que diz. **Devolver ao agente** faz o agente voltar a conversar.

- Ao **assumir** e ao **devolver**, o devedor recebe um aviso curto ("uma pessoa da equipe vai continuar…" /
  "o assistente voltou…"). Só para quem já conversou.
- Enquanto o caso está com a equipe, se o devedor escreve, ele recebe uma confirmação fixa de recebimento
  (no máximo uma a cada 30 min, e nenhuma se alguém da equipe respondeu nesse intervalo). Vale também para
  casos suspensos, contestados ou quitados.
- A lista **Com a equipe**, no alto da coluna de devedores, mostra os casos assumidos; quem está esperando
  resposta aparece primeiro, com ponto amarelo.
- Depois de responder, a tela diz se a mensagem **chegou ao Telegram**, se o devedor não tem Telegram ligado,
  se a rede falhou (o texto volta para a caixa) ou se ele bloqueou o bot.
- No histórico, o agente sabe o que foi escrito por uma pessoa e o que foi aviso automático, e não repete nem
  contradiz o que a equipe combinou.

## Entrega

- O que o agente escreve vai ao chat no fim da rodada. Se a rede falhar, vai na rodada seguinte (até 15 min),
  na ordem certa e sem duplicar.
- Resposta velha do agente nunca chega depois de uma mensagem da equipe ou de um aviso de passagem.
- Se o devedor bloqueia o bot, o caso fica marcado e nada é enviado. Quando ele volta a escrever, o canal reabre
  sem despejar mensagens antigas.
- Com o agente desligado (`MIZAN_AGENTE_ATIVO` diferente de `1`), a mensagem fica registrada no caso e o devedor
  recebe "o atendimento automático está pausado" (no máximo a cada 30 min).
- Mensagens chegando em sequência esperam a anterior terminar (até 40 s) em vez de ficar paradas na fila.

## Segurança

- O webhook só aceita chamadas com o cabeçalho `X-Telegram-Bot-Api-Secret-Token` igual ao segredo; sem a variável, recusa (503).
- O token do bot nunca vai para log, rastreio ou resposta; no caso fica só o hash do segredo do convite.
- Só conversa privada. Grupos e bots são ignorados. Foto, áudio e afins recebem "só consigo ler texto" (no máximo a cada 10 min).
- Cada update tem chave própria (`telegram:<update_id>`): reenvio do Telegram não duplica a resposta.
- Falha de rede ao entregar não derruba o atendimento: a mensagem fica registrada no caso.
- LGPD: o caso guarda só o `chat_id` (não o nome nem o usuário do Telegram).

## Limites desta versão

- Só texto. Sem botões; áudio e imagem não são lidos.
- Um chat fica ligado a um caso por vez (ligar a outro desliga o anterior).
- A busca do caso pelo chat usa `dados->telegram->>chat_id` em `agente_casos`; sem índice. Para volume alto,
  vale um índice nessa expressão.
- Não testado contra a API real do Telegram (o ambiente de desenvolvimento não alcança `api.telegram.org`);
  o fluxo foi testado com o envio simulado.
