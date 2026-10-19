# Disponibilidade de operador (Plano B)

Quando o caso vai para `com_pessoa`, o devedor recebe o nome de um operador
disponível e o próximo horário real em que ele atende — texto fixo montado
em código a partir de dados reais, a IA nunca inventa nome nem hora.

## Bug corrigido: R3_FREQUENCIA bloqueava o handoff

`agente/auditor.py`: a mensagem fixa de handoff/segurança (`com_pessoa`,
`parar`, `pessoa_errada`, `contestado`, `apoio`) agora usa o tipo de ação
`enviar_mensagem_seguranca`, incluído em `SEGURANCA` — a mesma categoria de
`suspender_contato`/`registrar_contestacao`, que o Auditor nunca bloqueia
(nem por frequência, nem por horário, nem pela situação do caso).

- `agente/negociador.py`: `mensagem_fixa(ctx, fonte=None)` marca
  `ctx.saida["_seguranca"] = True` sempre que devolve um desses textos.
- `agente/grafos.py`: o nó `enviar` audita com `enviar_mensagem_seguranca`
  (só para registro no rastreio; sempre permitida) antes de gravar a
  mensagem, quando `_seguranca` está marcado.
- Teste: `test_agente_disponibilidade.py`, bloco "bug corrigido" — confirma
  que `enviar_mensagem` comum continua bloqueada no limite (R3_FREQUENCIA)
  e que `enviar_mensagem_seguranca` passa (R9_SEGURANCA) no mesmo cenário,
  e um fluxo de ponta a ponta com o devedor no limite semanal pedindo humano.

## Dados novos

`backend/sql/migracao_disponibilidade_operador.sql` (não rodado em produção,
o humano aplica manualmente):

```
disponibilidade_operador(id, empresa_id, usuario_id, dia_semana 0-6,
                          hora_inicio 0-23, hora_fim 1-24, ativo)
```

Convenção de `dia_semana` igual ao resto do projeto (0 = segunda), igual ao
`dias_semana` da política do Auditor.

- `agente/fonte.py`: `FonteMemoria` (lista em memória, para teste) e
  `FonteSupabase` (tabela acima) ganham `disponibilidade_operador`,
  `criar_disponibilidade`, `editar_disponibilidade` (parcial) e
  `remover_disponibilidade` (desativa, não apaga).

## Função determinística

`agente/disponibilidade.py::proximo_atendimento(fonte, empresa_id, agora)`
devolve `{"usuario_id", "nome", "dia", "dia_semana", "hora_inicio"}` do
primeiro operador ativo da empresa com disponibilidade cadastrada a partir
de `agora` (percorre os próximos 14 dias), ou `None` se ninguém tem
disponibilidade cadastrada — nesse caso quem chamou cai na mensagem
genérica de sempre, sem quebrar o fluxo.

## Mensagem do Negociador

`agente/negociador.py::mensagem_fixa`, branch `com_pessoa`: se já existe um
atendimento marcado com dia/hora (fluxo antigo, `marcar_atendimento_humano`),
mantém o texto de sempre. Senão, chama `proximo_atendimento`; achou operador,
monta `"Vou passar sua conversa para a equipe. {Nome} costuma atender
{dia_semana} às {hora}h; se preferir outro horário, é só me avisar."`; não
achou, usa o texto genérico de antes (`FIXAS["com_pessoa"]`).

## API (admin cadastra a disponibilidade)

`agente/api.py`: `disponibilidade`, `criar_disponibilidade`,
`editar_disponibilidade`, `remover_disponibilidade` — escopadas por
`empresa_id`, confere que o operador existe e está ativo na empresa antes
de criar uma faixa.

Rotas em `main.py` (só `role == "admin"` cria/edita/remove; `admin` ou
`comando` lista):

- `GET  /agente/disponibilidade` — faixas cadastradas + lista de operadores
- `POST /agente/disponibilidade` — cria uma faixa
- `PUT  /agente/disponibilidade/{item_id}` — edita campos (parcial)
- `DELETE /agente/disponibilidade/{item_id}` — desativa

## Testes

- `test_agente_disponibilidade.py`: função determinística (pula faixa que já
  começou, acha a próxima, sem operador cai em `None`, operador que saiu não
  conta), handoff de ponta a ponta com nome e horário reais, handoff sem
  disponibilidade cadastrada (mensagem genérica, não quebra), o bug do
  R3_FREQUENCIA corrigido, e o CRUD em `FonteMemoria`.
- `agente/bateria/cenarios.py`: cenário novo `desvio-atendente-com-operador`
  (grupo Desvios) — pede uma pessoa com operador e disponibilidade
  cadastrados, confere que a mensagem tem o nome e o horário, sem IA.
- `agente/bateria/motor.py`: `Cenario` ganhou os campos opcionais
  `operadores` e `disponibilidades` para cenários poderem cadastrar isso.

Suíte inteira (`test_*.py`) e bateria (modo falso) passando, nota 100,
custo US$ 0.

## Pendente

- Frontend: não foi feito. Falta um componente simples em
  `frontend/src/pages` (lista + formulário, usando `pedir()` de
  `frontend/src/api.js`) para o admin cadastrar a disponibilidade pela tela;
  hoje só dá para usar a API diretamente.
- `editar_disponibilidade` não confere de novo se o `usuario_id` (caso
  alguém decida trocá-lo) continua sendo um operador ativo da empresa — hoje
  a API não permite trocar `usuario_id`, só os campos de horário/ativo, então
  não é um buraco, mas vale lembrar se o campo for liberado depois.
