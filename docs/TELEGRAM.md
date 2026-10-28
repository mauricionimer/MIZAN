# Canal Telegram

O devedor conversa com o agente do Mizan pelo Telegram. O agente é o mesmo da tela de
demonstração (Triagem, Negociador, Auditor...): o Telegram só traz a mensagem e leva a resposta de volta.

## Como funciona

1. A equipe abre o caso em **Agentes → Conversas** e toca em **Convite Telegram**: sai um link
   `https://t.me/<bot>?start=<código>` (vale uma vez e por 7 dias).
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

## Quando a equipe assume o caso

Em **Agentes → Conversas**, **Assumir o caso** tira o agente. A caixa de texto passa a ser **Responder como atendente**:
o que a pessoa escreve fica registrado no caso (marcado como "Atendente") e chega no Telegram do devedor. O que o
devedor responde aparece no mesmo chat. O agente não responde por cima. Mensagens de pessoa **não passam pelo
Auditor**: quem escreve responde pelo que diz. **Devolver ao agente** faz o agente voltar a conversar.

## Segurança

- O webhook só aceita chamadas com o cabeçalho `X-Telegram-Bot-Api-Secret-Token` igual ao segredo; sem a variável, recusa (503).
- O token do bot nunca vai para log, rastreio ou resposta; no caso fica só o hash do segredo do convite.
- Só conversa privada com texto. Grupos, fotos, áudios e bots são ignorados.
- Cada update tem chave própria (`telegram:<update_id>`): reenvio do Telegram não duplica a resposta.
- Falha de rede ao entregar não derruba o atendimento: a mensagem fica registrada no caso.
- LGPD: o caso guarda só o `chat_id` (não o nome nem o usuário do Telegram).

## Limites desta versão

- Só texto. Sem botões, áudio ou imagem.
- Um chat fica ligado a um caso por vez (ligar a outro desliga o anterior).
- A busca do caso pelo chat usa `dados->telegram->>chat_id` em `agente_casos`; sem índice. Para volume alto,
  vale um índice nessa expressão.
- Não testado contra a API real do Telegram (o ambiente de desenvolvimento não alcança `api.telegram.org`);
  o fluxo foi testado com o envio simulado.
