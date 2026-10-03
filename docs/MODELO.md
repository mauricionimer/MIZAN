# Documentação do modelo — Mizan

Documento para validação independente de modelos. Descreve o que o modelo é,
do que ele foi feito, como é medido e onde não se deve confiar nele.

Tudo aqui foi extraído do código em `backend/model/`, não de memória. Onde um
número aparece, a origem está citada. Onde não há número, está escrito que não
há — a ausência é informação para quem valida.

**Última revisão:** setembro de 2026
**Versão do documento:** 1

---

## 1. Identificação e finalidade

| | |
|---|---|
| Nome | Modelo de recuperabilidade Mizan |
| Tipo | Classificador binário com calibração de probabilidade |
| Saída | `score_recuperabilidade`, 0 a 100 — probabilidade estimada de pagamento |
| Uso | Ordenar a fila de cobrança e alimentar o cálculo de valor esperado |
| Decisão que apoia | Em quem a equipe de cobrança gasta o próximo contato |
| Decisão que **não** apoia | Concessão de crédito, negativação, protesto, ação judicial |

O modelo **não decide sozinho**. Ele produz um score; a ordem da fila é
calculada a partir do valor esperado (`score × dívida × fatores de fase`), e a
política de ordenação é configurável por empresa (`backend/model/priorizacao.py`).
O operador vê a fila, não é obrigado a segui-la, e registra o resultado real.

---

## 2. Dados de treino — a limitação que precede todas as outras

**O modelo em produção hoje está treinado em dados sintéticos, e o alvo
sintético é derivado das mesmas variáveis que o modelo depois lê.**

`_criar_alvo_simulado` (`backend/model/train.py`) constrói o alvo como soma
ponderada:

| Componente | Peso |
|---|---|
| Dias em atraso (invertido, teto 360) | 40% |
| Comprometimento de renda (invertido, teto 2×) | 25% |
| Produto | 20% |
| Tentativas de contato | 15% |
| Score de bureau, quando existe | ±20 pontos |
| Promessa quebrada | −30 pontos |

O classificador então treina para prever esse número a partir de — entre
outras — dias em atraso, comprometimento de renda, produto e tentativas de
contato.

Isso é **circular**. Métricas altas nessa configuração medem a capacidade do
modelo de reaprender uma fórmula, não de prever pagamento. Uma mesa de crédito
deve tratar qualquer KS produzido sobre dados sintéticos como não informativo.

O sistema sinaliza isso sozinho: `procedencia` (`backend/model/retrain.py`)
carrega `tipo_alvo`, `n_feedbacks_reais` e `nivel`, e as telas mostram o aviso
"modelo em calibração inicial" enquanto não houver resultado real registrado.

**O que desfaz a limitação:** feedback real. A partir de 30 pagamentos ou
não-pagamentos registrados (`MIN_FEEDBACKS_DEFAULT = 30`), o retreino passa a
usar desfecho observado — `pagou` de `feedbacks`, com as variáveis buscadas em
`predicoes` pelo `predicao_id`. Trinta é o mínimo para as métricas terem
significado estatístico, não o suficiente para confiar no modelo.

### Validação em base pública

Como métrica sobre dado sintético não prova nada, o pipeline foi validado na
**Statlog German Credit** (1.000 casos, 700 bons / 300 maus), com conferência
de integridade em execução contra os valores publicados
(`backend/validacao/validar_pipeline.py`).

| Configuração | KS | AUC | Brier |
|---|---|---|---|
| Calibração por holdout 20% | 36,8 | 0,719 | 0,185 |
| Calibração por validação cruzada (cv=5) — **em uso** | **43,0** | **0,754** | **0,175** |

Duas ressalvas que fazem parte do resultado:

1. German Credit é base de **concessão**, não de cobrança. Ela valida o
   cálculo das métricas e a escolha do algoritmo. Não diz nada sobre o
   desempenho do produto numa carteira de inadimplentes.
2. **No mesmo recorte, uma regressão logística supera este pipeline por 1,9
   de KS.** Gradient boosting precisa de volume, e 700 linhas de treino não é
   volume. Quando houver carteira real de cliente, se a amostra for pequena o
   scorecard logístico pode ser a escolha melhor — e isso deve ser medido, não
   presumido.

---

## 3. Variáveis

Colunas de entrada obrigatórias: `cpf`, `valor_divida`, `dias_em_atraso`.
Opcionais e usadas quando presentes: `nome`, `produto`, `status`, `uf`,
`renda_estimada`.

Derivadas em `_adicionar_derivadas`:

| Derivada | Fórmula |
|---|---|
| `comprometimento_renda` | `valor_divida / renda_estimada`, limitado a 10 |
| `log_valor_divida` | `log1p(valor_divida)` |
| `log_renda` | `log1p(renda_estimada)` |
| `valor_por_dia` | `valor_divida / (dias_em_atraso + 1)` |
| `mes_analise` | mês corrente, 1 a 12 |

Numéricas e categóricas são **detectadas automaticamente** (`_detectar_features`):
qualquer coluna numérica vira variável, e qualquer categórica com cardinalidade
baixa vira *one-hot*. Consequência para quem valida: **o conjunto de variáveis
depende do arquivo que o cliente enviou.** Duas carteiras diferentes produzem
modelos com entradas diferentes. O `feature_names` gravado junto ao artefato
registra o que cada versão usou.

Faltantes: numéricas preenchidas pela mediana, categóricas pela moda, ambas
gravadas no metadado da versão para aplicar o mesmo valor em predição.

---

## 4. Algoritmo

- **Classificador:** `HistGradientBoostingClassifier` (scikit-learn), com
  `max_iter=200`, `max_depth=4`, `learning_rate=0.05`,
  `min_samples_leaf = max(5, n/30)`, `l2_regularization=1.0`,
  `class_weight="balanced"`, `random_state=42`.
- **Segmentação:** `KMeans`, com k escolhido pelo método do cotovelo entre 2 e
  10. O cluster entra como variável adicional do classificador.
- **Calibração:** `CalibratedClassifierCV` com `method="sigmoid"` (Platt) e
  `cv=5`, aplicada quando há ao menos 200 amostras e as duas classes.
  Calibração é monotônica: não altera ordenação, só a escala da probabilidade.
- **Validação interna:** `StratifiedKFold`, com número de folds limitado pela
  classe minoritária.
- **Semente fixa** (`random_state=42`) em classificador, KMeans e folds: o
  treino é reprodutível.

---

## 5. Métricas e réguas

Implementadas em `backend/model/diagnostico.py`.

| Métrica | O que responde |
|---|---|
| KS | O modelo separa quem paga de quem não paga |
| Gini | `2 × AUC − 1` — poder de ordenação |
| Brier | Calibração: quando diz 30%, 30% pagam |
| Matriz de confusão, precisão, revocação, F1 | Desempenho no ponto de corte |
| Gap treino − CV | Sinal de sobreajuste |
| Amostras por variável | Complexidade adequada ao volume (mínimo 20) |

Réguas aplicadas:

```
KS    < 20 fraco · 20–30 regular · 30–40 bom · 40–50 forte · > 50 suspeito
Gini  < 20 fraco · 20–40 regular · 40–60 bom · > 60 forte
```

**KS acima de 50 é sinalizado como suspeito, não como ótimo**: em crédito,
separação alta demais costuma indicar vazamento — alguma variável que carrega
a resposta. O sistema não comemora esse número.

Nenhuma métrica é calculada abaixo de 30 amostras
(`MIN_AMOSTRAS_DIAGNOSTICO = 30`); abaixo disso o sistema informa que não há
base, em vez de exibir um número sem significado.

---

## 6. Versionamento e promoção

Cada treino gera uma versão `vs_AAAAMMDD_HHMMSS` com três artefatos
(classificador, KMeans, scaler + metadados) e um registro contendo tipo de
alvo, número de amostras, métricas de treino, carteiras analisadas, predições
feitas, feedbacks recebidos e acurácia real observada.

Promoção a modelo ativo exige no mínimo 30 amostras de treino. Furar esse
mínimo requer `forcar=True` explícito. Antes dessa trava, um modelo treinado
em dez linhas podia virar o que decide a fila em produção.

O histórico de versões fica visível na tela de Aprendizado, com a versão ativa
marcada e o momento da promoção.

**Não há champion/challenger.** A promoção é manual ou por retreino
automático; não existe execução paralela de duas versões com divisão de
tráfego. É uma lacuna conhecida, listada na seção 9.

---

## 7. Monitoramento

**PSI (Population Stability Index)** — `backend/model/psi.py`. Compara a
distribuição de scores da carteira atual com a de referência gravada no
modelo, faixa a faixa.

**Estado atual: inativo.** A referência gravada é degenerada — os scores do
treino sintético não produzem faixas utilizáveis —, e o sistema devolve o
motivo em vez de um número. Isso aparece na tela como indisponibilidade
declarada, não como "estável".

O PSI passa a funcionar quando houver uma carteira real servindo de
referência. Amostra atual mínima para cálculo: 20 scores.

---

## 8. Explicabilidade, equidade e dados pessoais

**Explicabilidade.** `explicar_predicao` (`backend/model/score.py`) devolve as
contribuições por variável e até três *reason codes* — o motivo em linguagem
comum do que puxou o score para cima ou para baixo. Exposto em
`GET /predicoes/{cpf}/explicacao`. Atende ao direito de revisão de decisão
automatizada (LGPD, art. 20).

**Equidade.** `backend/model/equidade.py` mede paridade demográfica e
igualdade de oportunidade por atributo, com mínimo de 30 casos por grupo e o
limiar dos 80% (regra dos 4/5) para sinalizar atenção. **O corte de 4/5 vem da
prática de mercado norte-americana (EEOC), não de regulação brasileira nem da
referência técnica do projeto** — está declarado como tal no código.

Achado registrado sem maquiagem, e com a ressalva de origem: numa **carteira
construída** em que duas regiões pagam exatamente igual (40%) e diferem apenas
no tamanho das dívidas, a ordenação por valor esperado dá à região de dívidas
menores **19% da atenção** que a outra recebe — e **22%** contando apenas quem
pagou. O número é de um cenário montado para isolar o efeito, não de carteira
de cliente; o efeito, não a magnitude, é o que se espera reproduzir em dado
real. Não é defeito de implementação: é propriedade de maximizar valor
recuperado, já que valor esperado é probabilidade vezes dívida e dívida menor
perde sempre. Como renda e tamanho de dívida andam juntos, a fila que recupera
mais também desprioriza a região mais pobre. `priorizacao.py` oferece uma
política alternativa, proporcional, configurável por empresa. **O padrão
continua sendo valor esperado puro** — a escolha da política é do cliente e
deve ser uma decisão consciente, não um efeito colateral.

**Dados pessoais.** `backend/model/retencao.py` separa identidade de
aprendizado: vencido o prazo configurado pela empresa, `cpf` e `nome` saem da
linha e as variáveis permanecem, de modo que o modelo continua aprendendo sem
que o registro aponte para alguém. Nada roda sem a empresa configurar um
prazo. Ver `docs/` e a política de privacidade do produto para o alcance e os
limites do termo "anonimizado".

---

## 9. Limitações conhecidas

Em ordem de gravidade para quem for validar:

1. **O modelo em produção é treinado em alvo sintético derivado das próprias
   variáveis de entrada.** Qualquer métrica nesse regime é circular. Enquanto
   `procedencia.nivel` for `sintetico`, o score serve para organizar trabalho,
   não para fundamentar decisão de risco.
2. **Perde para regressão logística em base pequena** — 1,9 de KS na German
   Credit. A escolha do algoritmo deve ser remedida quando houver dado real.
3. **PSI inativo.** Não há monitoramento de deriva funcionando hoje.
4. **Sem champion/challenger.** Não há como comparar duas versões em produção
   com tráfego dividido.
5. **Conjunto de variáveis dependente do arquivo do cliente.** Modelos de
   clientes diferentes não são comparáveis entre si.
6. **Sem *uplift modeling*.** O modelo estima quem paga, não quem paga *por
   causa* do contato. Cobrar quem pagaria de qualquer jeito (*self-cure*)
   gasta esforço sem gerar recuperação — e o sistema hoje não distingue os
   dois casos.
7. **`mes_analise` usa o mês corrente na predição**, o que introduz uma
   variável que muda sozinha ao longo do ano sem que nada na carteira mude.
8. **Rate limiting existe apenas no login.** Upload e predição não têm limite
   por cliente.

---

## 10. O que muda quando chegar carteira real

Na ordem em que deve ser feito:

1. Retreinar com desfecho observado e **medir de novo**, sem reaproveitar
   nenhuma métrica desta versão.
2. Comparar contra uma regressão logística no mesmo recorte, e adotar a que
   ganhar (item 2 das limitações).
3. Gravar a distribuição de referência do PSI a partir da carteira real,
   ligando o monitoramento de deriva.
4. Rodar a análise de equidade sobre desfecho real e levar o resultado à
   decisão de política de ordenação.
5. Avaliar *self-cure* e *uplift*, que só são mensuráveis com grupo de
   controle — alguém que não foi contatado.
6. Só então discutir champion/challenger, que exige volume para ter poder
   estatístico.

---

## 11. Modelo por empresa, treinado sem guardar os dados

O perfil COMANDO pode enviar a carteira histórica de um cliente (tela
`/comando/treino`), treinar um modelo **só dele** e ativá-lo. O arquivo é
descartado; o plano e as decisões estão em `PLANO_TREINO_POR_EMPRESA.md`.

**O que o código garante** (cada item tem teste, e o teste foi quebrado de
propósito para confirmar que pega o defeito):

- Alvo é pagamento real. Sem a coluna de resultado, recusa; não cai no alvo
  simulado. Valor de resultado que não sabe ler é erro, não palpite.
- CPF, nome e contatos saem do DataFrame antes do ajuste. Nenhum `.csv`, CPF ou
  nome fica em disco: os `.json` e `.pkl` gerados são varridos no teste.
- Treinar não ativa. Ativar é ação do COMANDO, auditada; se o modelo novo for
  pior que o atual (AUC) na mesma fatia de teste, pede confirmação.
- Empresa sem modelo próprio usa o modelo global, como antes. O modelo de uma
  empresa nunca pontua outra.
- `empresa_id` nunca vira caminho cru (`slug()` + conferência de que o destino
  está dentro da pasta).

**Como as métricas são medidas.** O modelo é treinado no passado e medido no
período mais recente (20%), que ele não viu — se o arquivo tem data. Sem data,
a fatia é aleatória e a tela avisa que isso tende a ser mais favorável. O
modelo que a empresa usa hoje é medido na **mesma** fatia. O modelo guardado é
refeito com todos os dados; as métricas mostradas são as do modelo treinado
só no passado. KS acima de 50 e variável que sozinha separa quase perfeitamente
(AUC ≥ 0,90) geram aviso de provável vazamento.

**O que fica registrado**, sem dado pessoal: SHA-256 do arquivo, nome, número de
linhas, taxa de pagamento, período, colunas do modelo, métricas, faixas do PSI,
quem treinou e quando.

**Limites medidos** (Python 3.12 local, não o Render):

| Linhas no treino | Tempo | Pico de memória do processo |
|---|---|---|
| 100 mil | ~37 s | ~310 MB (167 MB só de bibliotecas) |
| 200 mil | ~44 s | ~410 MB |

Por isso o treino usa no máximo 100 mil linhas (amostra aleatória, com aviso),
ajustável em `MIZAN_TREINO_MAX_LINHAS` num plano com mais memória. O pico é do
processo isolado: com a API no ar e uma análise em curso, o plano de 512 MB fica
apertado. Um treino por vez, entre instâncias (`travas`).

**Limitações assumidas.** Não há treino incremental: para refazer, reenvia-se o
histórico completo. O backtest segue usando o modelo global. O modelo é derivado
de dados pessoais; ele não contém registros individuais, mas não deve ser
descrito como "anônimo" em contrato.
