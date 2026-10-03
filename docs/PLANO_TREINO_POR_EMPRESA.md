# Plano — treino de modelo por empresa, com descarte dos dados

Objetivo: o perfil COMANDO envia a carteira histórica de um cliente (ex.: Goiás
Bank), o sistema treina um modelo **só daquela empresa**, mostra as métricas
contra o modelo atual, e **descarta os dados**. Nada vai para outras empresas.

## Como está hoje (lido no código, não suposto)
- Há **um** modelo global (`mizan_model.pkl`, `kmeans.pkl`, `scaler.pkl`), cache único em `score.py`.
- O modelo global foi treinado com **alvo simulado** (`train._criar_alvo_simulado`), não com pagamento real.
  `train.treinar(csv)` também usa alvo simulado: **não serve** para o histórico do banco.
- `retrain.py` treina com alvo real, mas a partir dos feedbacks no banco, e o resultado é global.
- Os `.pkl` sobrevivem a deploys via Supabase Storage (`storage_ml.py`), só os 3 arquivos globais.

## Decisões
1. Modelo por empresa em `model/empresas/<slug>/` (slug seguro; `empresa_id` nunca vira caminho cru).
2. Empresa sem modelo próprio **continua no modelo global**. Nada muda para quem não treinou.
3. Treino **só em memória**: o arquivo nunca vai a disco, nem a log, nem ao banco.
4. O que fica registrado (sem dado pessoal): SHA-256 do arquivo, nº de linhas, taxa de pagamento,
   período coberto, colunas, métricas, faixas agregadas do PSI, quem treinou e quando.
5. Treino **não ativa** o modelo. Ativar é ação explícita do COMANDO; dá para voltar ao geral.
6. Alvo real obrigatório (coluna de pagamento). Sem ele, recusa — nunca cai no alvo simulado.
7. Métricas em **validação temporal** (treina no passado, mede no futuro) quando há data;
   sem data, avisa que a validação é embaralhada (menos exigente). KS, Gini, Brier e AUC.
   O modelo atual é medido **no mesmo recorte de teste**, para comparar com justiça.
8. Mínimos de segurança (parâmetros de engenharia, declarados na tela; não são afirmação estatística):
   300 linhas e 30 de cada classe. Abaixo disso, recusa.

## Etapas
1. `model/modelos_empresa.py` — slug, carga com cache por empresa (fallback global), versões, ativar/desativar.
2. `model/treino_empresa.py` — validar, treinar em memória, medir, registrar, descartar.
3. `score.py` / `main.py` — `empresa_id` passa pelo score, explicação, PSI e backtest.
4. Rotas COMANDO — enviar e treinar (tarefa em segundo plano, uma por vez), status, versões, ativar, desativar.
5. `storage_ml.py` — sincroniza também os modelos por empresa.
6. Tela `/comando/treino` + link no painel.
7. Testes (incluindo "nenhum dado pessoal ficou em lugar nenhum"), mutações, suíte, docs.

## Fora de escopo agora
- Retreino automático por empresa (hoje só manual).
- Treino incremental (o algoritmo não permite; reenviar o histórico completo).
