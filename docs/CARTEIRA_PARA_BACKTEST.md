# Carteira histórica para backtest

O que pedir ao cliente antes da prova de conceito, e por quê.

A pergunta que o backtest responde não é "o modelo é bom" — é **"na sua
carteira, priorizando do meu jeito, você teria recuperado mais do que
recuperou?"**. Para responder isso é preciso uma carteira em que a cobrança
já aconteceu e o desfecho é conhecido.

---

## O mínimo

Uma planilha (CSV ou Excel), uma linha por devedor, de uma safra de cobrança
**já encerrada**:

| coluna | o que é | obrigatória |
|---|---|---|
| `cpf` | identificador do devedor (pode vir anonimizado, ver abaixo) | sim |
| `valor_divida` | saldo devedor no início da cobrança | sim |
| `dias_em_atraso` | dias de atraso no início da cobrança | sim |
| `pagou` | houve pagamento? `1/0`, `sim/não`, `true/false` | sim |
| `valor_recuperado` | quanto entrou de fato | muito recomendada |
| `renda_estimada` | renda do devedor | melhora bastante |
| `produto` | cartão, consignado, pessoal, cheque… | melhora |
| `uf` | estado | melhora |
| `despesas_mensais` | despesas fixas mensais | ativa a margem livre |

Sem `valor_recuperado`, o backtest assume que quem pagou quitou integralmente
— o que superestima a recuperação. Ele declara essa ressalva no relatório.

---

## O ponto que decide a validade

**Todos os dados precisam ser da foto ANTES da cobrança começar.**

Se `dias_em_atraso` for o valor de hoje, e não o do início da safra, ele já
carrega o desfecho: quem pagou parou de envelhecer. O modelo acerta, o KS
vem altíssimo, e nada disso se repete em produção.

É o erro mais comum e o mais caro, porque só aparece depois. O backtest
recusa colunas que entregam a resposta (`data_pagamento`, `status_pagamento`,
`quitado`, `valor_pago`…) e sinaliza KS acima de 50 como suspeito em vez de
ótimo — mas ele não tem como adivinhar um `dias_em_atraso` contaminado.

Vale perguntar explicitamente: *"esses campos são de qual data?"*

---

## Tamanho

- **Abaixo de 200 linhas**: o relatório sai, com ressalva. Serve de conversa,
  não de prova.
- **1.000 a 5.000 linhas**: suficiente para um resultado com significado.
- **Precisa dos dois desfechos.** Uma safra só de inadimplentes, ou só de
  quem pagou, não permite medir separação.

Uma safra fechada de 6 a 12 meses atrás costuma ser o pedido mais fácil de
atender: é antiga o bastante para o desfecho estar consolidado e recente o
bastante para ser representativa.

---

## Privacidade

Nada aqui exige identificar ninguém.

- `cpf` pode vir como hash ou como um id sequencial. O backtest só o usa para
  contar linhas.
- Nome, telefone, endereço e e-mail **não são necessários** — não peça.
- A análise de crédito tem base legal própria na LGPD (Art. 7º, X — proteção
  ao crédito), mas o princípio da minimização continua valendo: pedir menos
  dado é mais defensável e acelera a aprovação interna do cliente.

Dizer isso na hora do pedido costuma destravar a conversa com o jurídico
deles.

---

## O que sai do outro lado

```
python backend/backtest.py carteira_historica.csv
```

O relatório traz:

1. **KS e Gini** sobre o desfecho real — o modelo separa quem pagou de quem
   não pagou?
2. **Taxa de pagamento por decil** — num modelo que funciona, cai do primeiro
   decil para o décimo.
3. **Quanto se recupera trabalhando só o topo da fila**, em quatro
   capacidades operacionais (10%, 20%, 30%, 50% da base), comparando:
   - Mizan por valor esperado
   - Mizan por score puro
   - maior dívida primeiro — o que a maioria das operações faz
   - ordem aleatória
   - o teto teórico, com a fila perfeita
4. **O ganho sobre a prática atual**, em reais.

O relatório diz com todas as letras quando o Mizan **não** supera a prática
atual. Um número que só sabe ser favorável não serve para conversar com uma
mesa de risco — e seria descoberto na primeira pergunta.
