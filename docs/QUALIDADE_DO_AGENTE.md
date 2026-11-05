# Qualidade do agente de conversa: o que dá para ajustar

O agente é o mesmo no Telegram e na conversa dentro do Mizan (mesmo modelo, mesmas instruções,
mesmas ferramentas). A qualidade depende de quatro coisas.

## 1. O modelo (a maior alavanca)

Variável no Render: `MIZAN_MODELO_NEGOCIADOR` (e `MIZAN_MODELO_TRIAGEM` para entender a mensagem).
Modelos maiores seguem instruções muito melhor do que os menores ("lite"). No plano grátis do Google
os maiores têm menos cota por minuto. O modelo precisa ter preço em `MIZAN_AGENTE_PRECOS`.

## 2. Quanto a IA "pensa" antes de responder

Variável no Render: `MIZAN_RACIOCINIO_NEGOCIADOR` com `minimal`, `low` (padrão), `medium` ou `high`.
Mais raciocínio acompanha melhor as regras e responde mais certo, mas demora mais e gasta mais
cota. Para a demonstração, vale testar `medium`. Valor inválido é ignorado. Vale também para
`MIZAN_RACIOCINIO_TRIAGEM`.

## 3. As instruções (prompt)

`backend/agente/negociador.py` (versão em `VERSAO_PROMPT`). Regras importantes de conversa:
- diz quem é e de qual empresa fala quando perguntam (resposta pronta, em código);
- antes de confirmar o CPF não fala de valor, mas conversa: cumprimenta, explica por que pede 3 dígitos,
  tira dúvidas gerais, oferece uma pessoa;
- responde primeiro ao que a pessoa disse e não repete a mesma pergunta (há uma trava em código).

## 4. Como avaliar

- `python -m agente.bateria`: cenários com IA simulada (confere regras e segurança, não o estilo).
- Estilo e naturalidade só se avaliam com a IA real: repita no Telegram uma lista fixa de perguntas
  (cumprimento, "quem é você?", "é golpe?", "não vou passar o CPF", "quanto eu devo?", "posso falar com
  uma pessoa?", "só consigo pagar 200 por mês") antes e depois de cada mudança de modelo ou de
  `MIZAN_RACIOCINIO_NEGOCIADOR`.
