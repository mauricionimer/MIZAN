# Plano de execução — ofertas customizáveis, simulador e registro

Pedido de 05/10/2026. Três entregas, cada uma inteira (servidor → tela → ajuda
→ testes → publicação) antes da próxima. Princípios de sempre: escopo por empresa
no servidor, nada inventado (toda conta com fórmula e origem visíveis), falha que
não perde trabalho, um fluxo só.

## Como é hoje

- As propostas da ficha saem de **4 tipos fixos no código** (`ARQUETIPOS_PADRAO`):
  4x sem desconto, 12x, 10% à vista, 30% à vista.
- Cada tipo é uma **família de aprendizado** do bandit: é por ela que o sistema
  aprende "com esta oferta, quantos pagam".
- Juros eram juros simples (`dívida × (1 + i × n)`); como nenhum tipo cobra
  juros, isso nunca apareceu. Com ofertas customizáveis passa a importar.

| # | Entrega | O que resolve |
|---|---|---|
| O1 | Catálogo de ofertas da empresa + alçada | Cada banco define as próprias ofertas e os limites do operador |
| O2 | Simulador "Fazer oferta" | O operador monta a oferta e vê se é boa para quem paga e para o banco |
| O3 | Confirmar "fiz esta oferta" | Registra a oferta, a resposta do devedor e já alimenta Agenda e aprendizado |

---

## O1 — Catálogo de ofertas da empresa

**Cada oferta:** nome · descrição curta · desconto (%) · entrada (% do valor
negociado, 0 = sem entrada) · nº de parcelas (1 = à vista) · juros ao mês (%) ·
ativa sim/não. Até 20 ofertas.

**Família de aprendizado (automática, sem pergunta ao admin):**

| Oferta | Família |
|---|---|
| À vista, desconto até 15% | `avista_10pct` |
| À vista, desconto acima de 15% | `desconto_30pct` |
| Parcelada em até 6x | `parcelado_4x` |
| Parcelada em 7x ou mais | `parcelado_12x` |

Assim uma oferta nova ("Feirão 40% à vista") já começa com a chance de pagar
aprendida da família mais parecida, e o que ela gerar ensina a família.

**Alçada (limites do operador no simulador):** desconto máximo (%), parcelas
máximas, parcela mínima (R$), juros mínimo ao mês (%). Vazio = sem limite.

**Onde fica:** `empresa_config.extra` (`catalogo_ofertas`, `alcada_oferta`) —
sem SQL. Sem catálogo salvo, valem as 4 ofertas atuais (nada muda para quem não
mexer).

**Contas (`backend/ofertas.py`, uma função só para catálogo e simulador):**
- valor negociado = dívida × (1 − desconto)
- entrada = valor negociado × entrada%
- parcela = **tabela Price** sobre o saldo (valor negociado − entrada) com os
  juros do mês; sem juros, saldo ÷ parcelas
- total pago = entrada + parcela × parcelas

**Servidor:** `GET/PUT /empresa/ofertas` (admin edita; operador lê; COMANDO
escolhe a empresa). Validação: nome 2–60, desconto 0–95, entrada 0–90,
parcelas 1–120, juros 0–20, alçada coerente.

**Tela:** página **Ofertas** (Gestão): lista de cartões com a prévia da conta
numa dívida de exemplo, editor lateral, ativar/desativar, duplicar, restaurar
padrão; bloco **Alçada do operador**. As propostas da ficha passam a usar o
catálogo.

**Aceite:** catálogo salvo muda as propostas da ficha; família correta; outra
empresa não lê nem grava; operador não edita.

---

## O2 — Simulador "Fazer oferta"

Na ficha do devedor, aba **Fazer oferta**: escolhe uma oferta do catálogo como
base (ou começa do zero) e ajusta desconto, entrada, parcelas e juros. A análise
atualiza a cada mudança (servidor, `POST /predicoes/{cpf}/simular-oferta`).

**Para quem paga**

| Item | Conta |
|---|---|
| Parcela e total pago | fórmula acima |
| Economia | dívida − total pago (se positivo) |
| Cabe no bolso | parcela ≤ parcela máxima (margem livre × teto das Premissas) |
| Entrada | comparada com a sobra do mês; maior que ela = atenção |

**Para o banco**

| Item | Conta |
|---|---|
| Recebe (nominal) | total pago |
| Recupera | total pago ÷ dívida |
| Chance de pagar | da família da oferta (histórico real da empresa; sem histórico, a do modelo) |
| Valor esperado | valor negociado × chance de pagar (juros compensam o tempo e ficam fora, como nas propostas) |
| Comparação | valor esperado ÷ o da melhor oferta do catálogo que cabe no bolso |
| Venda da carteira | se a Premissa de cessão estiver informada: valor esperado × o que um fundo pagaria (dívida × cessão%) |

**Veredito (regras escritas na ajuda, escolha de projeto):**
- Quem paga: **Boa** se cabe no bolso; **Atenção** se não dá para verificar
  (sem despesas) ou se a entrada passa da sobra do mês; **Ruim** se a parcela
  passa do teto. À vista: Atenção — depende de reserva, não da renda.
- Banco: **Boa** se o valor esperado é ≥ 95% do da melhor oferta; **Atenção**
  entre 80% e 95%; **Ruim** abaixo de 80% ou abaixo do valor de venda.
- Fora da alçada: aviso vermelho e o botão de confirmar fica bloqueado.

**Honestidade:** a chance de pagar vem da família da oferta; o sistema ainda
não estima como 1 ponto de desconto a mais muda a chance — isso fica escrito na
tela.

---

## O3 — Confirmar "fiz esta oferta"

Depois da análise, botão **Confirmar que fiz esta oferta** abre um passo curto:
canal (WhatsApp, ligação, carta/e-mail) e resposta do devedor:

| Resposta | O que o sistema faz |
|---|---|
| Aceitou | registra o contato "Prometeu pagar" e pede a data → promessa na Agenda |
| Vai pensar | contato "Contactado" + retorno na Agenda (data) |
| Recusou | contato "Não quis negociar" |

**Banco:** tabela `ofertas_feitas` (`sql/migracao_ofertas.sql`) com a oferta
completa (condições, parcela, total, chance, valor esperado, vereditos), quem
fez, canal, resposta e o contato criado. O servidor **refaz a conta** na hora de
gravar (não confia no número que veio da tela) e recusa fora da alçada.

**Servidor:** `POST /ofertas` · `GET /ofertas?cpf=` (histórico do devedor).
O contato criado leva a família da oferta: o bandit aprende com ela como já
aprende hoje.

**Tela:** na ficha, abaixo do simulador, **Ofertas feitas a este devedor**
(data, condições, resposta, quem fez).

**Aceite:** oferta confirmada aparece no histórico e na Agenda (aceitou/vai
pensar); fora da alçada é recusada (422); outra empresa não vê.

## Ordem

1. O1 → `test_ofertas_catalogo.py` → página Ofertas → publicação.
2. O2 → `test_simulador_oferta.py` → aba Fazer oferta → publicação.
3. O3 → SQL → `test_ofertas_feitas.py` → confirmar + histórico → publicação.
