# Passagem para a equipe: resumo inteligente, fila e aprendizado

Pedido do Mauricio (18/10): explorar os resumos do Supervisor. Os cinco itens,
integrados aos agentes, numa ordem em que cada um usa o anterior.

Princípio da casa: a IA escreve e interpreta; o código calcula o que precisa
ser exato (valores, sugestão de proposta, prioridade) e nada quebra se a IA
falhar. Sem SQL novo: tudo fica em `agente_casos.dados` e na `agenda` que já
existem.

## A ficha da passagem (item 5, a base de tudo)

Quando o caso vai para uma pessoa (transferir, marcar atendimento, chamar
pessoa no Acompanhamento), nasce `caso.dados.passagem`:

| Campo | De onde vem |
|---|---|
| motivo | ferramenta que transferiu (pedido_do_devedor, dificuldade_grave, fora_da_politica, falha, atendimento_marcado) |
| situacao, o_que_quer, proximo_passo | Supervisor (IA); reserva: resumo curto de hoje |
| emocao, urgencia | Supervisor (IA, valores fechados); reserva: última leitura da Triagem |
| valor_dito | código: valores em reais que a Triagem leu nas mensagens da pessoa (`dados.valores_ditos`) |
| tentado | código: simulações que o agente apresentou (`dados.simulacoes`) |
| sugestao | código: proposta calculada dentro da política (item 2) |
| prioridade, nivel | código (item 1) |
| retorno | o atendente (item 4) |

`dados.passagens` guarda as 10 últimas, para o aprendizado. Nenhum CPF,
telefone ou nome entra (filtro `limpar_nota` nos textos da IA).

## Item 2 — resumo útil para quem atende

- "Já oferecido": as simulações apresentadas (ex.: 6x de R$ 2.025,00; 9x de R$ 1.200,00).
- "Sugestão": código percorre as condições válidas da política (parcelas
  1–máximo, desconto em passos de 5 até o máximo, entrada mínima) com as mesmas
  contas do simulador e do Auditor:
  - com valor dito: a que mais recupera e cabe no valor (parcela ≤ valor);
  - nada cabe: a de menor parcela, marcada "a mais perto do que a pessoa disse";
  - sem valor dito: o próximo degrau depois da última oferta (mais parcelas).
- O texto do Supervisor recebe a sugestão e o que foi tentado (não inventa número).

## Item 1 — fila inteligente

- Prioridade 0–100, em código: emoção (desesperado 40, irritado 30, ansioso 20,
  triste 15), urgência (alta 30, média 15), motivo dificuldade grave (+30),
  sugestão que cabe no valor dito (+10, fácil de fechar), espera (+1 por hora, até 20).
- Nível: Urgente (≥ 60), Alta (≥ 35), Normal.
- Tela Hoje (`GET /agenda`): itens pendentes do agente ganham a ficha; dentro do
  mesmo dia, a fila ordena por prioridade. Cartão mostra nível, emoção, valor
  dito, já oferecido e sugestão. Se o módulo do agente falhar, a agenda segue igual.

## Item 4 — retorno do atendente

- No cartão: "O resumo ajudou?" Sim / Não (+ comentário opcional curto).
- `POST /agente/passagem/{predicao_id}/retorno` (qualquer usuário da empresa;
  auditado). Grava em `passagem.retorno` e na lista de passagens.
- Nota do Supervisor (% que ajudou, 30 dias) no perfil do Supervisor.

## Item 3 — aprender com as passagens

- `sinais_da_equipe` (código, 7 dias): passagens por motivo e emoção; valor dito
  por faixa; quantas não couberam em nada e o valor típico pedido (mediana);
  nota do resumo.
- Vai para o Cientista junto dos outros resultados (métrica `passagens`, sempre
  "sem evidência": é sinal para virar experimento, não prova). Exemplo de saída
  esperada: "5 de 8 transferências pediram parcela abaixo da menor possível;
  testar 18x com o grupo sorteado".
- Laboratório mostra o bloco "O que as passagens dizem".

## Verificação

`test_agente_passagem.py`: ficha sem CPF; sugestão dentro da política e que
cabe; nada cabe → menor parcela; prioridade e ordenação; retorno e nota;
sinais da semana; IA desligada → ficha em código. Bateria: cenário de
transferência confere a ficha. Gemini real: uma conversa que termina em
pessoa. Suíte inteira, build, conferência visual com mock.

## Ordem

5 → 2 → 1 → 4 → 3, num PR só (são partes do mesmo fluxo), com teste a cada parte.
