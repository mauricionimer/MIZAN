# Mapa do sistema: o que cada número é e de onde vem

Base da Central de Ajuda (`PLANO_FAQ.md`, Fase 1). Tudo aqui foi lido no código.
Nada é suposição; onde o código não diz a origem de um número, está escrito.

Perfis: **comando** (vê tudo), **admin** (o "diretor": vê a equipe da própria
empresa), **operador** (trabalha a fila).
Origem do número: **dado** (vem do cliente), **modelo** (calculado por modelo
treinado), **premissa** (configurável, com padrão declarado), **referência**
(vem do material técnico citado no código), **escolha nossa** (decisão de
engenharia sem fonte externa).

---

## 0. O estado do modelo hoje: leia antes de tudo

O modelo ativo (`versions.json`) é `vs_20260921_231839`: **alvo simulado**, 3.000
linhas sintéticas. Existe uma versão "real" com **10 amostras**, que não está ativa.
Consequências que a Central tem de dizer com todas as letras:

- O **score** é uma nota de um modelo treinado em dados simulados. Ordena segundo
  premissas declaradas, **não segundo o histórico de uma carteira real**.
- A **probabilidade de pagamento** é `score/100`. Foi calibrada (Platt) contra o
  alvo simulado, então não é probabilidade medida.
- O **valor esperado** (dívida × taxa) herda isso.
- Os **motivos do score** ("região com recuperação *historicamente* maior")
  usam a palavra "historicamente", que hoje **não é verdade**. Ver achado A5.

Isso muda quando entra a carteira real de um cliente (treino por empresa).
A Central precisa mostrar **o estado atual do modelo** (simulado ou real, por
empresa) no topo, e não só explicar fórmulas.

---

## 1. Análise e fila

| Item | Tela / perfis | Onde é calculado | Fórmula e constantes | Origem |
|---|---|---|---|---|
| **Score de recuperabilidade** (0–100) | fila, devedor / todos | `model/score.py::score_carteira` | `score = round(P(pagou) × 100, 1)`. P vem do HistGradientBoosting calibrado (Platt) sobre as variáveis da carteira + o cluster | modelo |
| **Probabilidade de pagamento** | devedor, propostas / todos | `main._analisar_df` | `score / 100`, limitado a [0, 1] | modelo |
| **Taxa de recuperação prevista** | resumo / todos | `main._analisar_df` | com *price model* treinado: o que ele devolve (`origem_taxa = modelo`). Sem ele: `probabilidade × recuperacao_se_pagar` (`origem_taxa = premissa`) | modelo ou premissa |
| `recuperacao_se_pagar` | config da empresa | `main._premissa_recuperacao_se_pagar` | padrão **1,0** (pagou = pagou tudo). Aceita 0 < v ≤ 1 | premissa |
| **Valor esperado de recuperação** | fila, resumo / todos | `main._analisar_df` | `dívida × taxa_recuperacao_prevista` | modelo/premissa |
| **Valor esperado líquido** | ordena a fila / todos | `model/ciclo.py::liquido` | na fase especializada: `esperado × (1 − comissão%)`. Sem comissão configurada: igual ao bruto | premissa (comissão: configurada pela empresa) |
| **Fila (rank)** | fila / todos | `main._analisar_df` + `model/priorizacao.py::ordenar` | ordena por **valor esperado líquido**, decrescente. Alternativa `proporcional_por_grupo`: cada UF recebe fatia proporcional ao seu tamanho; dentro dela vale o valor esperado | escolha nossa (política da empresa em `criterio_priorizacao`) |
| **Prioridade Alta / Média / Baixa** | fila, devedor / todos | `frontend/utils/prioridade.js` (**no navegador**) | posição ÷ total: ≤ 20% **Alta**, ≤ 50% **Média**, resto **Baixa** | escolha nossa (cortes 20/50) |
| **Devedores Prioritários** (card) | visão da carteira / todos | `Dashboard.jsx` | `floor(total × 20%)`. É só o tamanho da faixa "Alta", não uma medida | escolha nossa |
| **Score médio** | visão da carteira / todos | `_analisar_df` | média simples do score da carteira | modelo |
| **Valor de face** | visão da carteira / todos | `_analisar_df` | soma de `valor_divida` | dado |
| **Dados incompletos** | fila / todos | `score.py::_avaliar_qualidade_dados` | marca devedor sem valor da dívida, dias de atraso ou renda (antes de imputar) | dado |

**Alcance da operação** (`/carteiras/{id}/alcance` e `utils/alcance.js`, ambos
fazem a mesma conta): soma de `valor_esperado_recuperacao` (**bruto**) dos N
primeiros da fila, onde N é a capacidade informada. `% = soma ÷ valor esperado
total da carteira`. Origem: dado (capacidade, informada pelo gestor) e modelo.

## 2. Ciclo de cobrança e perdas

| Item | Onde | Regra | Origem |
|---|---|---|---|
| **Fase** | `model/ciclo.py::fase_de` | `< 0` preventiva · `0–30` administrativa · `31–360` especializada · `> 360` write-off (limites **inclusivos** em 30 e 360) | referência (Vol. 5, §26 do material técnico) |
| **Comissão** | `custos_de_config` | só existe se a empresa configurar `comissao_especializada_pct` (0–100). Faixa de mercado citada: 10–25%, **não é aplicada por padrão** | premissa |
| **Cessão** | `valor_cessao` | `valor de face × cessao_pct%`, só com `cessao_pct` configurado. Faixa citada: 2–5% | premissa |
| **"Vale mais vender"** | `_analisar_df` | no write-off: `valor_se_vendida > esperado_cobrando` | derivado |
| **EAD** | `_analisar_df` | exposição = saldo devedor (é dado: o default já ocorreu) | dado |
| **LGD** | `_analisar_df` | `1 − taxa_recuperacao_prevista`, em [0, 1] | modelo/premissa |
| **Perda esperada** | `_analisar_df` | `EAD − valor esperado de recuperação` (= `EAD × LGD`) | derivado |
| **Aging** (5 faixas) | `main._aging_label` | `<30` · `30–59` · `60–89` · `90–179` · `180+` dias | escolha nossa |

## 3. Precificação (Dashboard, **admin e comando; o operador não vê**)

Calculada **no navegador** (`Dashboard.jsx`), sobre o resumo da carteira:

```
Líquido  = VER × (1 − custo%)          custo% = slider, 5–50, padrão 25
Preço    = Líquido ÷ (1 + retorno%)    retorno% = slider, 10–80, padrão 30
Lucro    = Líquido − Preço
Taxa de recuperação estimada = VER ÷ valor de face
```

`VER` = valor esperado de recuperação **bruto** da carteira. Os padrões 25 e 30
são **escolha nossa**, só pontos de partida do simulador. Não são do cliente nem
do mercado.

## 4. Devedor individual

| Item | Onde | Regra | Origem |
|---|---|---|---|
| **Por que esse score?** | `score.py::explicar_predicao` | para cada variável, troca só ela pela referência do treino (mediana ou moda), mantém as outras e o cluster, e mede quantos **pontos** o score mudaria. Mostra até **3** favoráveis e **3** desfavoráveis, com impacto ≥ **1 ponto** | método próprio (what-if) |
| **Comprometimento de renda** | `train/score::_adicionar_derivadas` | `dívida ÷ renda`, limitado a [0, 10] | derivado |
| **Perfil (cluster)** | `score.py` | KMeans sobre as variáveis; o rótulo ("Crônico · Alto Comprometimento · Cartão") sai de limites de dias (60/180), comprometimento (0,3/0,7) e produto | escolha nossa (limites dos rótulos) |
| **Margem livre** | `model/proposta.py::calcular_margem` | `(renda − despesas) × (1 − buffer%)`. **Sem despesas informadas não há margem** e nenhuma proposta é sugerida | referência + premissa (buffer padrão 30%) |
| **Parcela máxima** | `parcela_maxima` | `margem × comprometimento_max%` (padrão 100%) | premissa |
| **Propostas** (4 arquétipos) | `ARQUETIPOS_PADRAO` | 4x sem desconto · 12x · 10% à vista · 30% à vista | escolha nossa (ponto de partida, ajustável) |
| **Valor esperado da proposta** | `proposta.avaliar` | `dívida × (1 − desconto) × PoP` (juros embutidos **não** contam) | referência (conferida contra as simulações do material) |
| **PoP por oferta** | `bandit.pop_por_oferta` | `(pagamentos + 10 × pop_base) ÷ (tentativas + 10)`. `10` = suavização | escolha nossa |
| **Proposta sugerida** | `avaliar` | entre as parceladas que cabem no bolso, a de maior valor esperado. À vista fica como alternativa. Sem feedback por oferta todas têm a mesma PoP, e o sistema avisa | referência |
| **Canal e oferta recomendados** ("IA") | `model/bandit.py` (LinUCB) | 12 ações = 3 canais × 4 ofertas. Escolhe `argmax(θ·x + α·√(xᵀA⁻¹x))`, α = 1,0, contexto de 14 números. Um bandit **por empresa** | método |
| **Recompensa do bandit** | `main._fechar_loop_bandit` | pagou: `valor recuperado ÷ dívida` (máx. 1); pagou sem valor e sem dívida: 0,5; não pagou: 0 | escolha nossa |

## 5. Pagamentos e resultados

| Item | Onde | Regra | Origem |
|---|---|---|---|
| **Registrar pagamento** | `/feedback`, `/devedores/{cpf}/confirmar-pagamento`, `/feedback/lote`, `/webhook/pagamento` | grava o desfecho; alimenta bandit, price model e retreino | dado |
| **Resultados reais** ("Quem pagou") | `/performance` | agrupa feedbacks por faixa de score: **Alta ≥ 70**, **Média 40–69**, **Baixa < 40**; taxa de pagamento por faixa | escolha nossa (cortes 70/40) |
| **Acurácia geral** | `/performance` | acerta se `(score ≥ 40 e pagou)` ou `(score < 40 e não pagou)`. Corte **40** | escolha nossa |
| **Empresa suspeita** (COMANDO) | `comando_visao_geral` | `devedores analisados ≥ 50` **e** `taxa de feedback < 5%` | escolha nossa |

## 6. Qualidade do modelo (COMANDO)

| Item | Onde | Regra | Origem |
|---|---|---|---|
| **KS** | `diagnostico._ks_gini` | maior distância entre as curvas acumuladas de quem pagou e de quem não pagou, escala 0–100. Leitura: `<20` fraco · `20–30` regular · `30–40` bom · `40–50` forte · `>50` **suspeito** (provável vazamento) | referência |
| **Gini** | idem | `(2 × AUC − 1) × 100`. `<20` fraco · `20–40` regular · `40–60` bom · `>60` forte | referência |
| **AUC / Brier** | `diagnostico.avaliar_qualidade` | AUC e erro quadrático médio das probabilidades no holdout (20%) | padrão estatístico |
| **Overfitting** | idem | `acurácia no treino − acurácia na validação cruzada`: `≥ 0,10` moderado, `≥ 0,20` severo | escolha nossa |
| **Dados suficientes** | idem | `amostras ÷ variáveis ≥ 20` | escolha nossa ("regra prática") |
| **Calibração por faixa** | idem | 5 faixas: probabilidade média prevista × taxa real observada | padrão |
| **PSI** | `model/psi.py` | `Σ (p_atual − p_treino) × ln(p_atual / p_treino)` em 10 faixas do score. `< 0,10` estável · `0,10–0,25` atenção · `> 0,25` crítico | referência de mercado |
| **Deriva do score** (`/admin/drift`) | `main.detectar_drift` | diferença entre o score médio dos últimos 30 dias e o de **todo o histórico**; alerta se `> 10` pontos | escolha nossa |
| **Equidade** | `model/equidade.py` | razão entre a fatia selecionada do grupo menos e do mais favorecido; alerta abaixo de **0,80**; grupo precisa de ≥ 30 | prática (EEOC), **não** é lei nem referência do projeto |
| **Backtest** | `backtest.py` | compara filas (valor esperado, score, maior dívida) em capacidades de 10/20/30/50% sobre uma carteira histórica com resultado | método |

## 7. Aprendizado e treino

- **Retreino automático** (`scheduler.py`): periodicamente, com ≥ N feedbacks novos, treina e **promove sozinho** se a acurácia melhorar.
- **Treino por empresa** (COMANDO): ver `MODELO.md` §11.
- **Bandit**: um por empresa; α ajustável pelo COMANDO.
- **Retenção/LGPD**: prazo configurável de 30 a 3.650 dias; anonimiza em vez de apagar; pedido de titular (art. 18) por CPF.

---

# Achados

Itens que descobri ao mapear. **Nenhum foi documentado como regra.** A letra
indica o que fazer: **C** = corrigir (erro claro de código), **D** = decisão sua
(política ou método), **T** = texto que precisa mudar.

## Erros de código (C): **corrigidos** na mesma entrega

Os cinco foram corrigidos e cobertos por `test_resultados_escala.py`, cujo stub
impõe o teto de mil linhas e um `in_` curto. Rodado contra o código anterior, o
teste reprova 11 verificações; com a correção, nenhuma. Valores abaixo descrevem
o defeito que existia.

| # | Onde | Problema | Efeito |
|---|---|---|---|
| **C1** | `/performance` e `/performance/pagamentos` (`main.py` ~4115, 4250) | a lista de predições da carteira é lida sem paginar | o PostgREST corta em 1.000 linhas. Com 2.603 devedores (a base de produção hoje), feedbacks de quem está fora das 1.000 primeiras **somem** de "Resultados reais" |
| **C2** | `/performance`, `/performance/pagamentos`, `/feedbacks/status` (~4141, 4290, 4385) | `feedbacks ... .limit(5000)` | o servidor entrega no máximo ~1.000, e **de todas as empresas**: com mais de 1.000 feedbacks globais mais novos, uma empresa pode ver os números de outras filtrados a quase nada |
| **C3** | `/performance` (~4157) | `.in_("id", pred_ids)` com até 1.000 ids numa só URL | a medição no Supabase real mostrou que 800 ids já falham: a rota quebra com ~600+ feedbacks |
| **C4** | `comando_visao_geral`, detalhe da empresa e `/comando/carteiras` (~732–775, 894) | `carteiras` e `feedbacks` lidos sem paginar | "valor recuperado real", nº de feedbacks e a bandeira de **empresa suspeita** saem de só 1.000 linhas |
| **C5** | lotes de `in_` com 500 ids (`retrain`, status da carteira, métricas por versão) | o diagnóstico do banco mediu: 400 ids passam, 800 falham. 500 estava no meio, sem medida | risco no retreino e nas telas de feedback. Agora todos usam `ITENS_POR_IN` (100). O diagnóstico passou a testar 500 e 600 também, para dar o limite exato |

### Achados da Fase 2 (escrevendo as respostas): corrigidos

| # | Onde | Problema | Correção |
|---|---|---|---|
| **C7** | `/predicoes/{cpf}/propostas` | a rota não pedia ao banco a coluna `despesas_mensais`. O caminho "a carteira traz as despesas" nunca funcionou: a margem livre só existia se o operador digitasse as despesas | a coluna agora é lida; `test_proposta.py` cobre |
| **C8** | `model/bandit.py` | todo resultado com recompensa positiva contava como **pagamento**. "Contactado" (0,05) e "prometeu pagar" (0,2) inflavam a chance de pagamento por oferta, que escolhe a proposta sugerida | `atualizar(..., pagou=)` conta pagamento só quando pagou; `test_loop_oferta.py` cobre. **O histórico já gravado continua inflado** e não dá para separar depois |
| **C9** | `POST /feedback/lote` | a tela esconde o lote do operador, mas a rota aceitava operador: qualquer operador com o token registrava pagamentos em lote. `/feedback` já barrava | mesma barreira; `test_feedback_escopo.py` cobre |
| **C10** | conexões de banco | `_resolver_credenciais` decifrava a senha **salva** de qualquer `conexao_id` da requisição, sem conferir de quem era, e a usava contra o host que a requisição indicasse: bastava apontar o host para um servidor próprio para receber a senha do cliente. Em volta: operador testava conexão com host e senha digitados; qualquer usuário da empresa editava a conexão; as rotas de permissão aceitavam conexão de outra empresa | conexão só é usada por quem pode (comando, admin da empresa, operador liberado) e **contra o servidor salvo**; operador só usa conexão salva; editar é de admin e comando; permissões conferem a empresa. `test_conexoes_escopo.py` reprova 14 verificações no código anterior |

### Ainda abertos (sem correção nesta entrega)

| # | Onde | Problema |
|---|---|---|
| **C6** | filtro "pago / não pago / pendente" da fila | envia a lista de CPFs na consulta; com milhares de feedbacks a URL estoura |
| **E1** | premissas da empresa | recuperação se pagar, comissão, cessão, critério da fila, buffer e teto de parcela **não têm tela**: só a API as grava. O aviso do sistema manda "configurar", mas não há onde |
| **D8** | página do devedor | a "Urgência" (≥70 Alta, ≥40 Média) vem só do score e pode contradizer a Prioridade (posição na fila). É um terceiro critério |
| **D9** | renda ausente | quando a coluna de renda não existe, vira 0, e a razão dívida ÷ renda vira 0 (o devedor parece sem comprometimento) |
| **D10** | `price_model.pkl` | é um só para todas as empresas: se for treinado, passa a valer para todas, inclusive as que têm modelo próprio |
| **D12** | conexão Google Sheets salva | o cadastro da conexão não guarda as credenciais da conta de serviço, então a sincronização (manual e automática) falha para Sheets. Só a análise avulsa, com as credenciais coladas, funciona |
| **D11** | registrar contato | o operador pode marcar "Pagou" no contato, o que treina o bandit mas não confirma o pagamento (isso é do admin) |

## Decisões suas (D)

| # | Questão |
|---|---|
| **D1** | **O retreino automático mistura todas as empresas** (`_buscar_feedbacks` não filtra empresa) e o *price model* também. O modelo global resultante pontua todos os clientes. Isso contradiz o princípio do treino por empresa (o que um banco ensina ao modelo não é de outro). E promove sozinho. Opções: manter, restringir o automático ao que for da empresa, ou desligar o automático e deixar só o manual |
| **D2** | **"Aprendizado offline" do bandit**: quando não há recomendação prévia, ele escolhe uma ação sozinho e a atualiza com o resultado, como se tivesse sido executada. A ação **não foi feita**, e isso contamina as taxas por oferta que alimentam as propostas |
| **D3** | **Dois "líquidos"**: o card do Dashboard (`VER × (1 − custo%)`, controle deslizante) e o valor esperado líquido do ciclo (comissão por fase, configurada pela empresa). São conceitos diferentes com o mesmo nome |
| **D4** | **Duas "derivas"**: o PSI (por carteira, contra o treino, com régua) e `/admin/drift` (média de 30 dias contra o histórico inteiro, limite fixo de 10 pontos, sem separar empresas, e o histórico inclui os próprios 30 dias) |
| **D5** | **Alcance usa o bruto** enquanto a fila é ordenada pelo **líquido**. Com comissão configurada, o topo da fila não é o topo do bruto |
| **D6** | O diagnóstico de qualidade (`/admin/modelo/qualidade`) **retreina um modelo novo** sobre os feedbacks para medir. Mede "esse tipo de modelo com esses dados", **não o modelo que está ativo**, e com k de clusters diferente. Também é global |
| **D7** | A fronteira entre aging e fase: dia 30 cai na faixa de aging "30–59" mas na fase "administrativa" |

## Textos (T)

| # | Onde | Problema |
|---|---|---|
| **T1** (A5) | `REASON_CODES` (`score.py`) | "recuperação **historicamente** maior/menor" para produto e região. Com o alvo simulado, não há histórico |
| **T2** | `bandit.recomendar` | a justificativa "Baseado em N interações com **perfis similares**" cita a média da ação **inteira**, não de perfis parecidos. E chama de "calibrado" com apenas 3 interações |
| **T3** | `Recuperabilidade` | a descrição não diz que o modelo está em dados simulados |

## O que ainda não foi mapeado

Telas sem cálculo de métrica: login, senha, usuários e papéis, chaves de API,
conexões de banco e permissões, retenção e titular, auditoria, perfil da empresa,
upload (colunas e limites). Entram na Fase 2 em linguagem de procedimento, não de
fórmula.
