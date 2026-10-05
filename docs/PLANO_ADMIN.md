# Plano de execução — ferramentas do administrador

Pedido de 05/10/2026, em ordem de importância para o admin do banco. Cada item
é entregue inteiro (banco → servidor → tela → ajuda → testes → publicação)
antes do próximo. Mesmos princípios de `docs/PLANO_OPERADOR.md`: escopo por
empresa no servidor, nada inventado, falha que não perde trabalho, um fluxo só,
testes antes de publicar.

## O que já existe e o que é novo

| # | Pedido | Situação | Onde |
|---|---|---|---|
| A1 | Painel de resultados ("o que está funcionando") | **Novo** | página Resultados |
| A2 | Desempenho da equipe | Pronto (F3) | Painel da equipe |
| A3 | Distribuição da fila | Pronto (F1) | Dashboard → Distribuir fila |
| A4 | Acordos em andamento (parcelas, quebras) | **Novo** | página Acordos |
| A5 | Confiança no modelo, só leitura | Pronto; ganha resumo "por que confiar" no topo | Performance da IA |

---

## A1 — Painel de resultados

**Pergunta que responde:** "que canal, que condição e que fase de atraso trazem
dinheiro?" Transforma o que o operador registra em decisão.

**Fonte (só dado registrado):**
- `feedbacks` da empresa no período: `pagou`, `valor_recuperado`,
  `canal_cobranca`, `forma_pagamento`, `parcelas`, `desconto_pct`, `predicao_id`.
- Fase de atraso: `dias_em_atraso` da predição ligada ao pagamento, nas mesmas
  faixas do aging (`_aging_label`: 0-30, 31-60, 61-90, 91-180, 181+).
- `contatos` da empresa no período, por canal (WhatsApp, ligação, carta).

**Métricas por grupo:**

| Métrica | Conta |
|---|---|
| Registros | feedbacks do grupo (pagou e não pagou) |
| Taxa de pagamento | pagou ÷ registros |
| Recuperado | soma de `valor_recuperado` dos que pagaram |
| Ticket médio | recuperado ÷ pagos |

**Cortes:** canal de cobrança · à vista × parcelado (`parcelas` > 1) · faixa de
desconto (sem desconto, até 10%, 10–20%, 20–30%, acima de 30%) · fase de atraso.
O que foi registrado sem a informação vai para "Não informado" — nunca é
redistribuído. Segunda tabela: contatos por canal (contatos, efetivos,
promessas).

**Honestidade estatística:** grupo com menos de 30 registros ganha o selo
"amostra pequena" (o número aparece, mas não deve guiar decisão sozinho). A
taxa só mede o que foi registrado: se a equipe só registra quem pagou, a taxa
fica inflada — isso fica escrito na ajuda.

**Servidor:** `GET /resultados?periodo=30d|90d|365d|tudo` (admin; COMANDO com
`empresa_id`).

**Tela:** página **Resultados** (Gestão). Topo com 4 números (registros, taxa,
recuperado, ticket); abas por corte, cada uma com barras horizontais da taxa e
tabela ao lado; destaque automático do grupo com maior taxa entre os de amostra
suficiente ("melhor canal: WhatsApp, 38%").

**Aceite:** números batem com os feedbacks; outra empresa não entra; "Não
informado" separado; operador não acessa (403).

---

## A4 — Acordos em andamento

**Problema:** acordo parcelado em que o devedor paga a 1ª parcela e para. Hoje
o pagamento parcelado vira um registro só e o resto some.

**Regra de negócio:**
- Pagamento confirmado com `parcelas` > 1 cria o **acordo**: N parcelas mensais.
  A 1ª é a que acabou de entrar (paga, no valor registrado); as seguintes vencem
  todo mês no mesmo dia, com o mesmo valor.
- Situação do acordo (calculada, dia de Brasília):

| Situação | Quando |
|---|---|
| Quitado | todas as parcelas pagas |
| Em dia | nenhuma parcela vencida em aberto |
| Atrasado | parcela vencida há até 30 dias |
| Quebrado | parcela vencida há mais de 30 dias (escolha de projeto, escrita na ajuda) |

- Admin marca parcela paga (ou desfaz). Parcela paga entra em "Recebido" do
  painel do operador e da equipe (responsável do devedor).
- Pagamento parcelado registrado antes desta entrega não vira acordo (não há como
  saber o que foi pago depois).

**Banco:** tabela `acordo_parcelas` (uma linha por parcela, agrupadas pelo
pagamento que abriu o acordo) — `sql/migracao_acordos.sql`.

**Servidor:**
- Criação automática nas quatro entradas de pagamento confirmado (mesmo ponto que
  cumpre promessas).
- `GET /acordos?situacao=` (admin/COMANDO): acordos com parcelas, situação,
  pago, em aberto; resumo (em aberto, a vencer em 7 dias, atrasado, quebrado).
- `PATCH /acordos/parcelas/{id}` `{acao: pagar|desfazer}` (admin).

**Tela:** página **Acordos** (Gestão). Quatro números no topo (em aberto · a
vencer em 7 dias · atrasados · quebrados, em valor e quantidade); filtro por
situação; cada acordo como linha expansível com a régua de parcelas (pagas em
verde, vencidas em vermelho, futuras em cinza) e o botão "Marcar paga". Em
Pagamentos, com "Parcelado", o campo vira "Valor recebido agora (1ª parcela)".

**Aceite:** parcelado cria N parcelas com vencimentos mensais; quebrado aparece
depois de 30 dias; parcela paga soma no recebido; operador não mexe.

---

## A5 — Confiança no modelo (complemento)

A tela já mostra acerto (KS/AUC), o que mais pesa e estabilidade. Ganha no topo
um resumo em linguagem de gerente: "O modelo separa bem quem paga de quem não
paga (KS 32, bom)", "Treinado com N casos da empresa em DD/MM", "Estável desde o
treino" — só com os números que a tela já recebe; o que faltar, não aparece.

## Ordem

1. A1 Resultados → `test_resultados_admin.py` → tela → publicação.
2. A4 Acordos → SQL → `test_acordos.py` → tela → publicação.
3. A5 resumo de confiança → publicação.
