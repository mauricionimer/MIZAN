# Plano detalhado: agentes que pensam com IA (17 a 23/10/2026)

Princípio: **a IA decide; o código só impede o que é proibido** (Auditor e travas)
**e garante o que precisa ser exato** (contas, sorteio do grupo de comparação,
selo de evidência). Todo agente com IA tem um caminho em código se a IA falhar,
for desligada ou estourar o teto: o sistema nunca para por falta de IA.

Entrega: um PR por etapa, com suíte inteira verde (Python 3.12), bateria 100%
com IA simulada, uma rodada curta com o Gemini de verdade e o critério de
aceite cumprido. Merge e produção só com o OK do Mauricio.

---

## Etapa 0 — Base comum (antes de tudo, ~2 h)

Problema: o `ClienteFalso` responde numa fila única, em ordem. Se Acompanhamento,
Supervisor ou Estrategista passarem a chamar a IA, os roteiros dos 71 cenários
atuais desalinham.

| Arquivo | Mudança |
|---|---|
| `agente/llm.py` | `ClienteFalso(roteiro)` aceita lista (como hoje) **ou** dicionário `{papel: [respostas]}`. Com lista, só triagem e negociador consomem a fila (comportamento atual). Papel novo sem roteiro → `SemRoteiro`, e o agente usa o caminho em código. |
| `agente/llm.py` | `ia_ligada(papel)`: lê `MIZAN_IA_PAPEIS` (padrão `"triagem,negociador"`, igual a hoje). É o botão de cada agente, sem deploy: tirar o papel da lista volta ao código. |
| `agente/llm.py` | `modelo_para(papel)` aceita os papéis novos (`MIZAN_MODELO_ACOMPANHAMENTO`, `_ESTRATEGISTA`, `_SUPERVISOR`, `_CIENTISTA`); sem variável, usa o modelo da triagem. |
| `agente/orquestrador.py` | `ctx.ia_ou_codigo(papel, gerar, reserva)`: chama a IA se ligada; falha, teto ou `SemRoteiro` → `reserva()`, com o passo marcado `"origem": "codigo"` e o motivo. |
| `test_agente_llm.py` | Fila por papel; lista antiga intacta; papel desligado nunca chama a IA. |

Aceite: suíte e bateria iguais a hoje (nada muda com a configuração padrão).

---

## Etapa 1 — Caderno do caso (integração entre os agentes)

Os agentes não conversam entre si. Cada um deixa **decisão e motivo** no caso;
o próximo lê antes de agir. É o que aparece no rastreio e na tela.

Contrato (`caso.dados.caderno`, as 15 últimas):
```
{"agente": "estrategista|triagem|negociador|acompanhamento|supervisor|cientista|equipe",
 "quando": ISO, "decisao": "codigo_curto", "motivo": "até 200 caracteres", "trace_id": "..."}
```
Regras: o caderno nunca guarda texto literal do devedor nem CPF ou identificador.
O motivo escrito por IA passa por um filtro (`guardrails.limpar_nota`: tira
dígitos de CPF ou telefone e corta em 200 caracteres).

| Arquivo | Mudança |
|---|---|
| `agente/estado.py` | `anotar(caso, agente, decisao, motivo, trace_id)` e `caderno(caso, n)`. |
| `agente/estrategista.py` | `plano(aplicar=True)` anota `grupo:<g>` com o motivo. |
| `agente/triagem.py` | Anota só se houver sinal ou emoção forte (etapa 2); nada em "outro". |
| `agente/negociador.py` | Fim da rodada: nota montada **em código** pelas ferramentas que rodaram (ex.: `simulou 3x R$ 270,00`, `aceite registrado`, `agendou 19/10 14:00`). Sem ferramenta: nenhuma nota. Briefing ganha `"caderno"` com as 6 últimas. |
| `agente/acompanhamento.py` | Anota `lembrou`, `procurou_no_atraso`, `passou_para_pessoa`. |
| `agente/api.py` | `controle_do_gestor` anota `equipe: assumiu/devolveu`. `ver_caso` devolve `caderno`. |
| `frontend/src/pages/Agente.jsx` | Painel "Caderno do caso" abaixo dos passos, com o chip de cor de cada agente. |

Testes (`test_agente_caderno.py`):
- ordem e limite de 15;
- sem CPF no motivo;
- o Negociador recebe o caderno no briefing;
- a nota do Negociador sai das ferramentas, não do texto;
- assumir e devolver anotam.

Bateria: `cad-1` (o Estrategista anota, o Negociador lê o motivo no briefing) e
`cad-2` (o caderno não guarda o texto do devedor).

Aceite: numa conversa, o caderno mostra Estrategista → Triagem → Negociador em
ordem, e o briefing do Negociador traz o que o Estrategista decidiu.

---

## Etapa 2 — Triagem enriquecida (triagem-v3)

Campos novos no JSON da Triagem:
```
"emocao": "calmo|ansioso|irritado|triste|desesperado",
"urgencia": "baixa|media|alta",
"ironia": true|false,
"resumo": "uma linha, sem dado pessoal"
```
- `_validar`: campo inválido ou ausente vira o padrão (`calmo`, `baixa`,
  `false`, `""`), sem derrubar a triagem.
- As regras em código continuam antes e mandam: segurança por regra não chama a
  IA e não pode ser desfeita.
- Negociador (prompt v5):
  - briefing com emoção e urgência;
  - irritado ou desesperado → oferecer uma pessoa;
  - ironia → não tratar como aceite.
- Trava nova em código: com `ironia=true`, o aceite (`registrar_aceite`) nesta
  rodada é bloqueado pelo Auditor (regra `R13_IRONIA`) até uma confirmação
  explícita na mensagem seguinte. Pega o "ah claro, aceito, com o dinheiro que
  eu não tenho".
- Caderno: anota `triagem: irritado/alta` quando foge do normal.
- Tela: chip de emoção no passo da Triagem.

Testes: validação tolerante; ironia bloqueia o aceite; a regra continua antes
da IA; o resumo sem dígitos.

Bateria: `tri-1` (ironia não vira aceite), `tri-2` (irritado → oferece pessoa),
`tri-3` (urgência alta: "vão me negativar amanhã?" → consulta a base).

IA real: 10 frases medidas (ironia, raiva, pressa, neutras), com acerto relatado.

---

## Etapa 3 — Acompanhamento com IA

Hoje: três textos prontos (lembrete, atraso, sem resposta). Passa a ser IA
escolhendo **uma ação de um cardápio fechado** e escrevendo a mensagem.

| Fase | Cardápio |
|---|---|
| lembrete (antes da data) | `lembrar`, `esperar` |
| venceu | `procurar`, `oferecer_remarcar`, `chamar_pessoa`, `esperar` |
| sem_resposta | `chamar_pessoa`, `esperar_mais` (no máximo 1 vez por compromisso) |

- Entrada da IA:
  - compromisso (valor, data);
  - situação;
  - caderno;
  - última emoção da Triagem;
  - contatos nos últimos 7 dias;
  - política (horário, frequência).
- Saída (JSON): `{"acao": ..., "motivo": ..., "mensagem": ...}`.
- Código:
  - ação fora do cardápio → reserva;
  - o Auditor confere (R2 horário, R3 frequência);
  - a mensagem passa pelas travas: valores só os do compromisso, sem ameaça,
    sem "fiz" sem ter feito;
  - `chamar_pessoa` executa `transferir_para_humano` com o resumo (o Supervisor
    melhora na etapa 5);
  - `oferecer_remarcar` só convida; quem remarca é o Negociador, com a
    ferramenta, quando a pessoa responder.
- Reserva: IA desligada, falha, JSON inválido ou duas reprovações → o texto
  pronto de hoje, sem mudança.
- Grupo sorteado e casos com pessoa: continuam pulados antes da IA.
- Caderno: anota a ação e o motivo.
- Prompt: `acompanhamento-v1`. Modelo: flash-lite. 1 chamada por data.

Testes (`test_agente_acompanhamento_ia.py`):
- cada ação do cardápio;
- ação inventada → reserva;
- valor errado na mensagem → reprova → reserva;
- R3 bloqueia `procurar`;
- `chamar_pessoa` transfere;
- IA desligada = comportamento atual.

Bateria: `aco-1` (lembrete personalizado), `aco-2` (atraso com pessoa irritada →
chama uma pessoa), `aco-3` (IA tenta valor diferente → texto pronto).

Aceite: os testes antigos do Acompanhamento passam sem mudança (IA desligada).

---

## Etapa 4 — Estrategista com IA (20 por dia)

Continua em código, sem mudança: a separação em quatro grupos, o sorteio do
grupo de comparação e a regra de quem nunca é cobrado.

Novo (`agente/estrategista_ia.py`):
- Pega os 20 primeiros do grupo "contato" do dia, não sorteados e sem decisão
  nos últimos 7 dias.
- Ficha por devedor (lista fechada):
  - valor da dívida;
  - dias de atraso;
  - produto;
  - chance (faixa);
  - histórico do caso (caderno, acordos, quebras);
  - recomendação do bandit (`model.bandit.recomendar`: canal, oferta, modo,
    nº de interações);
  - ofertas dentro da política.

  **Fora da ficha:** região, renda, idade, gênero, CPF e nome completo. O bandit
  continua usando o contexto dele; a IA só vê a recomendação.
- Saída (JSON):
  `{"decisao": "abordar|adiar", "tom": "direto|acolhedor|informativo", "oferta_inicial": <família do catálogo>, "concorda_bandit": bool, "raciocinio": "até 300 caracteres"}`
- Código confere:
  - `oferta_inicial` existe no catálogo e cabe na política;
  - `adiar` só até 7 dias;
  - fora disso, a decisão é descartada e vale o padrão de hoje (abordar,
    sem oferta).
- Uso:
  - o raciocínio vai para o caderno e para o Plano do dia (coluna nova "Por
    quê (IA)");
  - a abordagem usa o tom; a primeira mensagem tem o corpo escrito pela IA,
    mas a apresentação "assistente virtual de..." é fixa, e o corpo passa pelas
    travas (sem valor);
  - o briefing do Negociador ganha `oferta_inicial` e `tom`.
- Lotes: no máximo 10 chamadas por minuto, com uma pausa entre elas; o Plano
  mostra "analisando 7/20".
- Rastreio: `concorda_bandit` registrado, para medir quantas vezes a IA
  discorda e o que acontece depois.
- Prompt: `estrategista-v1`.

Testes:
- ficha sem campos proibidos (teste que falha se aparecer região ou renda);
- oferta fora do catálogo → padrão;
- sorteado nunca vai para a IA;
- limite de 20;
- IA desligada = plano de hoje.

Bateria: `est-1` (discorda do bandit, com motivo), `est-2` (adiar),
`est-3` (oferta inválida → padrão).

---

## Etapa 5 — Supervisor (novo agente)

(a) **Resumo para a pessoa**
- Quando o caso vai para alguém da equipe (`transferir_para_humano`,
  `marcar_atendimento_humano`, `chamar_pessoa`), o Supervisor recebe o caderno
  e as últimas 10 mensagens e escreve:
  `{"situacao", "oferecido", "o_que_quer", "emocao", "proximo_passo"}`.
- Vai para `caso.resumo`, para a observação da Agenda e para o caderno.
- Reserva: o resumo de hoje.

(b) **Revisão sob sinal**
- Antes de enviar, só quando houver triagem irritado ou desesperado, alerta de
  manipulação ou uma reprovação nas travas nesta rodada.
- Saída: `{"aprovado": bool, "problema": "..."}`. Reprovado → o Negociador
  reescreve uma vez com o problema; reprovou de novo → envia a versão que
  passou nas travas e anota.
- **Não é trava de segurança**: não acrescenta nada, só aprova ou pede
  reescrita; travas e Auditor continuam valendo depois.

(c) **Juiz da bateria real**
- `python -m agente.bateria --real --juiz` → nota de tom e condução por
  cenário, separada da nota das travas.

Arquivos: `agente/supervisor.py` (novo), ganchos em `negociador.py`,
`ferramentas.py` (transferências), `acompanhamento.py`, `bateria/__main__.py`.
Prompt: `supervisor-v1`.

Testes: o resumo sem CPF; revisão só sob sinal (contar as chamadas); reprovação
leva a uma reescrita; IA desligada → resumo de hoje e sem revisão.

Bateria: `sup-1` (resumo na transferência), `sup-2` (mensagem fria para pessoa
irritada → reescrita), `sup-3` (sem sinal → nenhuma chamada ao Supervisor).

---

## Etapa 6 — Agente Cientista (versão mínima)

Ferramentas estatísticas em código (`agente/ciencia.py`):

| Ferramenta | Faz |
|---|---|
| `comparar_grupos` | Agente vs. sorteado: taxa de pagamento, R$ recebido por R$ de dívida, quebra; intervalo de confiança de 95% (Wilson para taxas, bootstrap para R$/R$) |
| `composicao` | Os grupos são comparáveis? Diferença de chance média, valor e atraso entre agente e sorteado |
| `segmentos` | O mesmo, por produto e por faixa de atraso, só com n ≥ 30 por grupo |
| `bandit` | `model.bandit.convergencia_stats`: tentativas, recompensa média e incerteza por combinação |

Dados: casos do agente (`agente_casos.grupo_controle`) + pagamentos
(`feedbacks.pagou`, `valor_recuperado`) da empresa.

**Selo de evidência decidido em código**, não pela IA:
- `sem evidência`: n < 30 por grupo, ou o intervalo cruza zero;
- `indício`: o intervalo não cruza zero, mas a composição difere;
- `evidência`: o intervalo não cruza zero e os grupos são comparáveis.

Agente (`agente/cientista.py`, prompt `cientista-v1`):
- formula até 3 hipóteses;
- chama as ferramentas;
- escreve o relatório: hipótese, resultado com números das ferramentas, selo,
  condições de uso e próximo experimento.
- Travas: todo número do relatório tem que ter vindo de uma ferramenta (a mesma
  lógica dos valores do Negociador); o texto não pode dizer "comprovado" ou
  "causou" com selo diferente de `evidência`.

Recomendação:
- tabela `agente_recomendacoes` (SQL novo, que o Mauricio roda antes do
  merge): versão, texto, selo, status `proposta|aprovada|recusada`, quem
  aprovou;
- a aprovação não muda a política: a recomendação aprovada entra no briefing do
  Estrategista como orientação.

O bandit continua aprendendo só com dinheiro que entrou (sem mudança).

Tela: aba "Laboratório":
- botão "Gerar análise";
- relatório com selo colorido;
- aprovar ou recusar;
- faixa "dados fictícios" quando a carteira for de demonstração.

Testes:
- selo em código (amostra pequena → sem evidência, diga a IA o que disser);
- número inventado no relatório → reprova;
- "comprovado" com indício → reprova;
- a aprovação não altera a política.

---

## Transversal

- Configuração em produção (Render): `MIZAN_IA_PAPEIS` liga os agentes um por
  um; `MIZAN_MODELO_<PAPEL>` escolhe o modelo. Desligar um agente = tirar o
  papel da lista.
- Custo e limite (plano gratuito, flash-lite, 15 por minuto):
  - mensagem do devedor: 2–4 chamadas (hoje), mais 1 só com sinal;
  - data: 1;
  - Plano do dia: 20, em lote;
  - Cientista: ~5 por análise.
  - O teto diário de custo (`MIZAN_AGENTE_TETO_DIA_USD`) vale para todos.
- Rastreio: todo passo de IA com agente, modelo, versão do prompt, tokens,
  custo e `origem: ia|codigo`.
- Docs de entrega, a cada etapa: tabela "o que é IA e o que é código", fluxo,
  roteiro, README.
- Versões de prompt: `triagem-v3`, `negociador-v5`, `acompanhamento-v1`,
  `estrategista-v1`, `supervisor-v1`, `cientista-v1`, registradas no rastreio e
  nos resultados da bateria.

## Cronograma

| Dia | Entrega | PR |
|---|---|---|
| 17/10 | Etapas 0, 1 e 2 | 2 PRs (0+1, 2) |
| 18/10 | Etapa 3 | 1 PR |
| 19/10 | Etapa 4 + ensaio com IA real | 1 PR |
| 20/10 | Etapa 5 | 1 PR |
| 21/10 | Etapa 6 (+ SQL) | 1 PR |
| 22–23/10 | Congelar, ensaio completo, docs e pitch | — |

Se apertar: a etapa 6 vai para a final (28/11), e o pitch mostra as etapas 1–5.

## Riscos e respostas

| Risco | Resposta |
|---|---|
| Mais IA, mais pontos de falha | Reserva em código por agente e botão `MIZAN_IA_PAPEIS` |
| Limite de 15 por minuto no plano gratuito | Lotes no Estrategista; Supervisor só sob sinal; espera do 429 até 30 s |
| IA vazando dado pessoal no caderno ou no resumo | Filtro em código e ficha fechada; testes que falham se aparecer CPF, região ou renda |
| Cientista "descobrindo" coisa em dado fictício | Selo em código, trava de números e de "comprovado", faixa "dados fictícios" |
| Mudanças quebrando os 71 cenários atuais | Etapa 0 (fila por papel) e configuração padrão igual à de hoje |
