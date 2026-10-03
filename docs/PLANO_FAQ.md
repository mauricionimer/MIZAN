# Plano: Central de Ajuda (FAQ) e dúvidas encaminhadas ao COMANDO

**Objetivo.** O operador (e o admin) consegue tirar dúvida sobre **qualquer
métrica e funcionalidade** do Mizan: o que é, como é calculada, de onde vem o
dado, o que fazer com ela e quando não confiar nela. O que a Central não
responder vira uma **dúvida enviada ao COMANDO**, que responde dentro do sistema.

**Princípio.** A resposta nunca é inventada. Toda fórmula e todo número citado
vêm do código e são conferidos por teste. Se o código mudar e o texto não, o
teste quebra.

---

## Decisões já tomadas

| Tema | Decisão |
|---|---|
| Quem vê as dúvidas | **COMANDO vê todas.** O **admin** (o "diretor") vê as da **própria equipe**. O operador vê só as próprias |
| Aviso de resposta | **Só na tela** (sem e-mail) |
| Resposta que vira ajuda | **Passa por revisão** antes de entrar no catálogo |
| IA generativa | **Fora.** O conteúdo é um catálogo estático de perguntas e respostas, com busca local |

## Andamento

| Fase | Estado |
|---|---|
| 1. Mapa do sistema | **Pronta** (`MAPA_DO_SISTEMA.md`) |
| 2. Catálogo de respostas | **Pronta**: 64 entradas em `backend/ajuda/`, validadas contra o código por `test_ajuda_catalogo.py` |
| 3. Busca e página Ajuda | **Pronta** (`/ajuda`, busca local). Qualidade medida em perguntas de teste que nunca serviram para ajuste: resposta certa em 1º lugar **70,3%**, entre as 3 primeiras **87,5%**, recusa de pergunta fora do assunto **91,7%**, precisão quando diz ter certeza **83,7%**. As metas eram 75% e 90%: **ficaram um pouco abaixo**. Ver ressalva abaixo |
| (extra) Tela de Premissas | **Pronta**: `/premissas`, admin e COMANDO, validada e auditada. A ajuda aponta para ela |
| 4. "?" ao lado de cada métrica | A fazer |
| 5. Dúvidas encaminhadas ao COMANDO | A fazer |
| 6. Perguntas sem resposta | A fazer |

## 1. O que existe hoje (levantado no código, não suposto)

A ajuda precisa cobrir cálculos que estão em **dois lugares**:

- **No servidor:** score, probabilidade, valor esperado, fila, fases do ciclo,
  propostas, PSI, KS/Gini, equidade, aprendizado, treino por empresa etc.
- **No navegador:** parte do que aparece na tela é calculado no front. Exemplos:
  - toda a Precificação do Dashboard (`Líquido = VER × (1 − custo%)`,
    `Preço = Líquido ÷ (1 + retorno%)`);
  - a etiqueta de prioridade (recorte por posição na fila);
  - o Alcance da operação.

  Por isso o mapa precisa ler o front também.

Também há **diferença por perfil**. O operador não vê a Precificação, o Ciclo de
cobrança nem "Quem pagou". A ajuda dele não pode explicar telas que ele não tem.

Escopo estimado: **80 a 100 itens**, a confirmar no mapa.

| Área | Exemplos de itens |
|---|---|
| Análise | enviar arquivo, colunas aceitas, limite de 25 MB, conexão com banco, análises anteriores |
| Visão da carteira | total de devedores, valor de face, score médio, devedores prioritários, aging, perfis (clusters), recuperabilidade por decil |
| Fila | ordem da fila, etiqueta de prioridade, filtros, critério (valor esperado ou proporcional por grupo) |
| Ciclo de cobrança | fases (preventiva, administrativa, especializada, write-off), comissão, cessão, "vale mais vender" |
| Alcance | capacidade da equipe, até onde a fila chega, valor esperado ao alcance |
| Precificação | valor esperado, líquido, preço sugerido, lucro, taxa de recuperação, custo e retorno (simulação) |
| Risco | perda esperada, LGD, EAD, PSI |
| Devedor | score, "por que esse score", probabilidade de pagamento, comprometimento de renda, propostas, parcela máxima, desconto, canal e oferta sugeridos |
| Pagamentos | registrar, lote, como isso ensina o sistema |
| Admin | usuários e papéis, chaves de API, conexões, retenção, titular (LGPD), auditoria, perfil da empresa, custos do ciclo |
| COMANDO | visão geral, "empresa suspeita", aprendizado (versões, KS/Gini/Brier, overfitting, calibração), bandit, backtest, treino por empresa, limites do banco |
| Conta | senha, esqueci a senha, sessão |

---

## 2. Fases

Cada fase termina com testes, a suíte inteira e o build passando, e com commit e
push. Antes de seguir, digo o que foi feito e o que achei.

### Fase 1: Mapa do sistema (antes de escrever qualquer resposta)

**Entrega:** `docs/MAPA_DO_SISTEMA.md`. Para cada item:
- tela e perfis que o veem;
- onde é calculado (arquivo e função, front ou back);
- fórmula com as constantes reais;
- dados de entrada;
- de onde vem cada número (dado do cliente, premissa configurável, referência
  declarada no código, ou parâmetro sem fonte).

**Também entrega uma lista de achados.** Ao mapar, vou encontrar inconsistências,
por exemplo um mesmo nome calculado de dois jeitos, ou um número sem fonte. Elas
**não** viram resposta de FAQ: vêm para você decidir antes. Documentar um erro
como se fosse regra seria pior do que não ter ajuda.

**Ponto de decisão:** você olha os achados antes da Fase 2.

### Fase 2: Catálogo de respostas (o conteúdo)

Cada tópico é um arquivo Markdown curto em `docs/ajuda/`, legível no GitHub pelo
celular. Cada entrada tem:

| Campo | Para quê |
|---|---|
| `id` | chave estável (ex.: `psi`, `fila-prioridade`) |
| `perguntas` | 5 a 10 jeitos de perguntar, na linguagem do operador ("por que esse cara tá no topo?") |
| `resposta curta` | 1 a 2 frases, o que aparece no ícone "?" |
| `como é calculado` | a fórmula, com as constantes reais |
| `o que fazer com isso` | como agir |
| `quando não confiar` | limites, avisos, dados faltando |
| `perfis` / `telas` | quem pode ver e onde aparece |
| `fonte` | `arquivo::função` e constantes citadas |

**Testes que impedem o texto de envelhecer:**
1. Toda `fonte` existe no código. Se a função for renomeada, o teste quebra.
2. Toda constante citada tem o valor que o código tem hoje. Por exemplo, se a
   ajuda diz "PSI acima de 0,25 é crítico", o teste lê `model.psi.PSI_CRITICO`.
3. Perfil: entrada marcada só para admin/comando nunca é entregue ao operador.

### Fase 3: Busca e página "Ajuda" (todos os perfis)

**Busca local.** A pergunta não sai do servidor, e nenhuma IA externa é
envolvida. A técnica é TF-IDF sobre as perguntas de cada entrada, mais
sinônimos do domínio ("nota" = score, "baixa" = pagamento, "ranking" = fila) e
sem distinção de acento.

**Medida de qualidade, antes de dizer que funciona:**
- Um conjunto de perguntas de avaliação, escritas à parte das usadas na busca
  (mais ou menos 3 por entrada), mede quantas vezes a resposta certa vem em
  1º lugar e entre as 3 primeiras.
- Também mede se a busca **recusa** perguntas fora do assunto em vez de
  responder qualquer coisa.
- Referência já medida nesta conversa: 71% de acerto em 1º lugar com perguntas
  variantes. As metas da Fase 3 são 75% em 1º lugar e 90% entre as 3 primeiras.
  São metas, não resultado; reporto o número medido.
- Esse conjunto de avaliação vira teste: se a qualidade cair, a suíte acusa.

**Quando não tem certeza, a tela diz isso.** Mostra as 3 respostas mais próximas
e o botão **"Enviar minha dúvida ao COMANDO"** com a pergunta já preenchida.
Responder errado com confiança é exatamente o "robô bobo".

### Fase 4: Ajuda no lugar (ícone "?" ao lado de cada métrica)

Cada métrica nas telas ganha um "?" que abre a resposta curta e o link "ver
mais". É o que mais ajuda o operador, porque ele não precisa saber o nome da
coisa para perguntar.

**Teste de cobertura:**
- todo "?" no front aponta para uma entrada que existe;
- toda entrada marcada com uma tela está ligada a um "?" ou é declarada "só na
  Central".

### Fase 5: Dúvidas encaminhadas ao COMANDO

**Fluxo:**
1. O operador envia a dúvida. Vão junto a tela onde ele estava e o que ele buscou.
2. A dúvida aparece no painel COMANDO, em "Dúvidas", com a contagem de abertas.
3. O COMANDO responde.
4. O operador vê a resposta em "Minhas dúvidas", com um aviso na tela (sem e-mail).
5. O COMANDO pode marcar "sugerir para a Central". A dúvida entra numa fila de
   sugestões, que vira entrada revisada e testada do catálogo (Fase 2).

**Segurança e LGPD:**
- A tela pede para não colocar dado de cliente.
- O servidor **mascara CPF, CNPJ, e-mail e telefone** antes de gravar, mesmo que
  o operador cole.
- Tamanho máximo de 2.000 caracteres e limite de 10 dúvidas por hora por usuário.
- O texto é sempre mostrado como texto, nunca como HTML.
- O operador vê só as próprias dúvidas. O **admin vê as da sua equipe** (as do
  mesmo `empresa_id`). O COMANDO vê todas. Há teste de isolamento entre empresas
  e entre perfis, como nos outros endpoints.
- Responder fica na auditoria. A tabela entra na política de retenção.

**Banco:** nova tabela `duvidas`. O SQL é validado em Postgres local duas vezes
antes de eu te passar para rodar, como sempre.

### Fase 6: O que a Central não soube responder

Cada busca sem resposta é registrada, mascarada e sem identificar quem
perguntou. O COMANDO vê as perguntas mais repetidas sem resposta e os
"não resolveu", que dizem qual entrada escrever ou melhorar.

---

## 3. Fora do escopo agora

- **IA generativa** (um modelo de linguagem respondendo com base no catálogo).
  A arquitetura deixa a porta aberta. Antes disso há uma decisão de contrato e
  LGPD, porque a pergunta sairia do servidor.
- **Ajuda para o cliente final** (o devedor).

## 4. Riscos e como estão cobertos

| Risco | Cobertura |
|---|---|
| Texto fica desatualizado quando o código muda | teste de fonte e de constantes (Fase 2) |
| Busca responde errado com confiança | conjunto de avaliação + limiar + encaminhar ao COMANDO (Fase 3) |
| Operador cola CPF na dúvida | máscara no servidor + aviso na tela (Fase 5) |
| Dúvida de uma empresa vista por outra | teste de isolamento (Fase 5) |
| Ajuda explica tela que o perfil não tem | filtro e teste por perfil (Fase 2) |
| Documentar um erro como regra | achados da Fase 1 vão para você antes |


## Medida da busca (Fase 3) e a ressalva

`python avaliar_busca.py` mede a busca com `ajuda_avaliacao.py`: 3 perguntas por
entrada (2 de ajuste, 1 de teste) e 24 perguntas fora do assunto (12 + 12).
Parâmetros de decisão (limiar, margem, cobertura) foram ajustados **só no
conjunto de ajuste**; o de teste foi medido em separado.

**Ressalva importante:** as perguntas de avaliação e o catálogo foram escritos
pela mesma pessoa (eu), então a medida tende a ser **otimista** em relação a
perguntas reais de operadores. A medida verdadeira vem do uso: a Fase 6 registra
o que a busca não soube responder e transforma isso em respostas novas.

A busca nunca afirma sem mostrar alternativas: mostra sempre as 3 mais próximas, e
quando não tem certeza, diz isso em vez de apresentar uma resposta como certa.
