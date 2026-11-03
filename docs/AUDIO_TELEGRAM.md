# Áudio no Telegram

O devedor pode mandar áudio no Telegram. O Mizan transcreve e o agente responde por texto.

## O que muda para quem usa

- **Devedor:** manda uma mensagem de voz (ou um arquivo de áudio) e recebe a resposta por texto,
  como se tivesse escrito.
- **Equipe:** na conversa do caso, o áudio aparece como texto com 🎤 na frente, por exemplo:
  `🎤 Quero pagar em 3 vezes`. Quando não deu para ouvir, aparece só o aviso, como
  `🎤 [áudio de 0:42 não transcrito]`. O áudio em si não fica guardado.
- **Central:** cada transcrição vira um passo "Transcreveu o áudio do devedor", com o custo e a
  duração. O que foi dito não aparece ali.

## Quando não dá para ouvir

| Situação | O que a pessoa recebe |
|---|---|
| Áudio com mais de 2 minutos | "Seu áudio passou de 2 minutos. Pode mandar um áudio mais curto ou escrever?" |
| Arquivo em formato que o Gemini não abre | Pede uma mensagem de voz ou texto |
| Silêncio ou fala que não dá para entender | "Não consegui entender o áudio. Pode repetir ou escrever?" |
| Gemini fora do ar, sem cota ou teto do dia atingido | "Não consegui ouvir seu áudio agora. Pode escrever o que precisa?" |
| Mais de 30 áudios no dia na mesma conversa | "Recebi muitos áudios por hoje. Pode escrever o que precisa?" (no máximo uma vez por hora) |

## Proteções

- A transcrição segue o mesmo caminho de uma mensagem escrita: triagem, travas, negociador,
  consulta jurídica e revisão humana. Nenhuma etapa é pulada.
- O Gemini recebe a ordem de só transcrever. Se o áudio pedir para mudar regras, o pedido vira
  texto do devedor e passa pelas mesmas travas de qualquer mensagem.
- **Aceite de acordo por áudio:** só é registrado depois que a pessoa leu, por escrito, o valor
  total, as parcelas e o valor de cada uma. Assim um número mal transcrito não vira acordo
  (`ferramentas._conferir_aceite`).
- O áudio é baixado do Telegram só na memória e descartado depois da transcrição. Não vai para
  disco, banco, log nem rastreio. O token do bot nunca é impresso.
- O mesmo áudio reenviado pelo Telegram não é transcrito de novo.

## Configuração (Render)

Por padrão, nada precisa mudar. O áudio liga sozinho quando o agente usa o Gemini
(`MIZAN_AGENTE_CLIENTE=gemini` e `GEMINI_API_KEY`) e usa o mesmo modelo da Triagem.

| Variável | Para que serve | Padrão |
|---|---|---|
| `MIZAN_AUDIO` | `0` desliga (volta o aviso "só leio texto") | ligado |
| `MIZAN_AUDIO_MAX_S` | Duração máxima, em segundos | `120` |
| `MIZAN_AUDIO_POR_DIA` | Áudios por conversa por dia | `30` |
| `MIZAN_MODELO_AUDIO` | Outro modelo do Gemini só para áudio (cota separada no plano grátis). Precisa ser da mesma geração do da Triagem (com `thinkingLevel`) e ter preço em `MIZAN_AGENTE_PRECOS` | modelo da Triagem |

O custo entra no teto diário da empresa (`MIZAN_AGENTE_TETO_DIA_USD`), como o resto da IA. Um
minuto de áudio dá uns 1.920 tokens de entrada.

## Custo e privacidade

- **Plano grátis do Gemini:** não custa nada, mas a cota é dividida com a Triagem. Pelos termos
  do Google, o conteúdo enviado no plano grátis pode ser usado para melhorar os produtos dele e
  ser lido por revisores.
- **Com devedores de verdade:** ative a cobrança no projeto do Google Cloud da chave (plano pago).
  Nada muda no código.

## Onde está

| Peça | Arquivo |
|---|---|
| Transcrição, limites e marca 🎤 | `backend/agente/audio.py` |
| Recebimento, download e avisos | `backend/agente/canal_telegram.py` (`_ouvir`, `_baixar_arquivo`) |
| Regra do aceite por áudio | `backend/agente/ferramentas.py` (`_conferir_aceite`) |
| Instrução ao negociador | `backend/agente/negociador.py` (`negociador-v15`) |
| Testes | `backend/test_agente_audio.py` (também na prova de segurança) |

## Como testar em produção

1. Ligue um Telegram a um caso de teste (convite na tela do caso).
2. Mande uma mensagem de voz dizendo, por exemplo, "quero negociar, meu CPF começa com 123".
3. A resposta deve chegar por texto, e o caso deve mostrar `🎤 quero negociar...`.
4. Mande um áudio em silêncio: deve chegar "Não consegui entender o áudio".
5. Se aparecer "Não consegui ouvir seu áudio agora", veja no log do Render a linha
   `[Telegram] áudio não transcrito: ...`, que mostra o motivo técnico.
