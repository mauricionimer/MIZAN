# Mizan

Sistema de gestão de carteiras, predição de pagamentos e recomendações (bandit).

## Estrutura

- `backend/` — API em Python (FastAPI), autenticação, integração com banco de dados e modelo de ML.
- `frontend/` — Aplicação web (Vite).
- `testes/` — Massas de dados de exemplo para testes de importação/predição.

## Documentação

- [`docs/MODELO.md`](docs/MODELO.md) — documentação do modelo para validação
  independente: dados de treino, variáveis, algoritmo, métricas, versionamento,
  monitoramento e limitações conhecidas.
- [`docs/CARTEIRA_PARA_BACKTEST.md`](docs/CARTEIRA_PARA_BACKTEST.md) — o que
  pedir ao cliente para rodar um backtest com dado real.
