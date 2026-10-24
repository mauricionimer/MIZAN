# Mizan

Sistema de gestão de carteiras, predição de pagamentos e recomendações (bandit).

## Estrutura

- `backend/` — API em Python (FastAPI), autenticação, integração com banco de dados e modelo de ML.
- `frontend/` — Aplicação web (Vite).
- `testes/` — Massas de dados de exemplo para testes de importação/predição.

## Documentação

- [`docs/FLUXO_AGENTES.md`](docs/FLUXO_AGENTES.md) — fluxos dos agentes com
  entradas, lógica, saídas, limites, passagem para equipe e monitoramento.
- [`docs/FLUXO_AGENTES_MIZAN.pdf`](docs/FLUXO_AGENTES_MIZAN.pdf) — versão em
  PDF da documentação operacional dos agentes.

- [`docs/ARQUITETURA_MIZAN.md`](docs/ARQUITETURA_MIZAN.md) — arquitetura do
  Mizan, framework próprio dos agentes, camadas, integrações e controles.
- [`docs/ARQUITETURA_MIZAN.pdf`](docs/ARQUITETURA_MIZAN.pdf) — versão visual
  em PDF da arquitetura técnica do sistema.

- [`docs/COMPARATIVO_CONCORRENTES.md`](docs/COMPARATIVO_CONCORRENTES.md) —
  critérios e fontes do comparativo competitivo do Mizan.
- [`docs/COMPARATIVO_CONCORRENTES_MIZAN.pdf`](docs/COMPARATIVO_CONCORRENTES_MIZAN.pdf) —
  quadro visual de concorrentes e diferenciais atuais.

- [`docs/BMC_MIZAN.md`](docs/BMC_MIZAN.md) — modelo de negócio do Mizan em
  Business Model Canvas, com hipóteses comerciais e plano de validação.
- [`docs/BMC_MIZAN.pdf`](docs/BMC_MIZAN.pdf) — versão visual em PDF do Business
  Model Canvas.

- [`docs/MODELO.md`](docs/MODELO.md) — documentação do modelo para validação
  independente: dados de treino, variáveis, algoritmo, métricas, versionamento,
  monitoramento e limitações conhecidas.
- [`docs/CARTEIRA_PARA_BACKTEST.md`](docs/CARTEIRA_PARA_BACKTEST.md) — o que
  pedir ao cliente para rodar um backtest com dado real..
