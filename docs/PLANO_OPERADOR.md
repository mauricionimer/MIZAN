# Plano de execução — ferramentas do operador

Quatro features, na ordem de importância para a operação de cobrança. Cada uma é
entregue inteira (banco → servidor → tela → ajuda → testes → publicação) antes da
próxima começar. Escrito em 04/10/2026.

| # | Feature | Problema que resolve | Quem usa |
|---|---|---|---|
| F1 | Divisão da fila | Dois operadores ligando para o mesmo devedor | Admin distribui; operador trabalha a sua |
| F2 | Agenda de retorno e promessas | "Pago dia 15" e "me liga sexta" se perdem | Operador; admin acompanha |
| F3 | Painel do operador | Ninguém sabe quanto fez no dia | Operador; admin vê a equipe |
| F4 | Roteiros de abordagem | Cada operador escreve a mensagem do zero | Operador cria e usa; admin cria os da empresa |

## Princípios (valem para as quatro)

1. **Escopo por empresa no servidor.** Todo dado novo carrega `empresa_id`; toda
   rota filtra pela empresa do usuário logado, nunca pelo que vem na URL ou no
   corpo. COMANDO escolhe a empresa.
2. **Nada inventado.** Números do painel são contagens do que foi registrado.
   "Quanto entrou" é soma de pagamentos confirmados, nunca de promessas.
3. **Falha que não perde trabalho.** Se o SQL novo ainda não rodou, as telas
   antigas seguem funcionando e a nova diz "falta rodar o SQL", em vez de 500.
4. **Um fluxo, não telas soltas.** O operador entra, vê *Minha fila* e *Minha
   agenda*, abre o devedor, usa o roteiro, registra o contato e, se houver
   promessa ou retorno, a data já fica na agenda — tudo sem trocar de tela.
5. **Testes antes de publicar.** Cada feature ganha um teste de servidor próprio;
   a suíte inteira e a navegação (computador e celular) passam antes do push.

## Banco — uma migração só (`backend/sql/migracao_operador.sql`)

| Mudança | Para quê |
|---|---|
| `predicoes.responsavel_id`, `predicoes.responsavel_nome` + índice `(carteira_id, responsavel_id)` | Dono de cada devedor (F1). Na própria linha da fila: filtrar "minha fila" é um `eq`, sem lista de CPFs |
| Tabela `agenda` | Retornos e promessas com data, valor, situação (F2) |
| Tabela `roteiros` | Mensagens padrão da empresa e pessoais (F4) |
| RLS ligado nas tabelas novas | Mesmo padrão das demais: só o servidor (chave de serviço) acessa |

F3 não precisa de tabela: lê `contatos`, `agenda`, `feedbacks` e `predicoes`.

---

## F1 — Divisão da fila

**Regra de negócio.** Cada devedor de uma carteira tem no máximo um responsável
(operador ativo da empresa). O admin reparte; o operador trabalha a sua parte.

**Como o sistema reparte (rodízio pela ordem da fila).** A fila já está ordenada
pelo valor esperado. Distribuir em blocos daria ao primeiro operador só os
melhores devedores. O rodízio em "serpente" (1,2,3,3,2,1,1,2,3…) entrega a cada
operador uma fatia com o mesmo perfil de valor — é o critério justo usado em
mesas de cobrança. Opções: todos os devedores ou só os ainda sem responsável.

**Servidor**
- `POST /carteiras/{id}/distribuir` (admin/COMANDO): `{operadores: [ids], somente_sem_responsavel}`
  → grava `responsavel_*` em lotes; devolve quantos por operador. Recusa
  operador de outra empresa ou inativo.
- `POST /carteiras/{id}/responsavel` (admin/COMANDO): `{cpfs: [...], operador_id | null}` → reatribui ou libera.
- `GET /carteiras/{id}/ranking` ganha `responsavel=me|sem|<id>`; cada item traz `responsavel_nome`.
- `GET /carteiras/{id}/distribuicao`: contagem e valor esperado por operador.
- Reanálise/sincronização da carteira **preserva** o responsável de quem continua nela (por CPF).

**Tela**
- Dashboard, admin: botão **Distribuir fila** → painel com os operadores (marcar quais),
  "só quem está sem responsável", prévia de quantos e quanto valor cada um recebe, confirmar.
  Ao lado, um resumo "Ana 498 · Beto 498 · sem responsável 0".
- Fila: chips **Minha fila · Toda a carteira · Sem responsável**. Operador abre em
  *Minha fila*. Coluna **Responsável**.
- Ficha do devedor, admin: seletor "Responsável" para trocar na hora.

**Aceite:** dois operadores nunca recebem o mesmo devedor; a soma das partes é a
carteira; operador não reparte nem reatribui (403); outra empresa não entra.

---

## F2 — Agenda de retorno e promessas

**Regra de negócio.** Dois tipos:
- **Promessa de pagamento** — data e valor prometidos. Nasce do contato com
  resultado "Prometeu pagar" (data obrigatória).
- **Retorno** — "me liga sexta". Data (e hora opcional), a partir de qualquer contato.

Situações: `pendente → cumprida | quebrada | cancelada`. Promessa vira **cumprida
sozinha** quando um pagamento confirmado do mesmo devedor entra.

**Níveis de aviso (pedido do cliente: alto, médio e safe)**

| Nível | Cor | Quando |
|---|---|---|
| Alto | vermelho | Data já passou e continua pendente (promessa vencida = possível quebra) |
| Médio | âmbar | Vence hoje ou amanhã |
| Safe | verde | Daqui a 2 dias ou mais |

**Servidor**
- `POST /agenda`, `GET /agenda?escopo=minha|equipe&situacao=`, `PATCH /agenda/{id}` (cumprir, quebrar, cancelar, remarcar).
- `GET /agenda/resumo` → contagem por nível (alimenta o aviso do menu).
- `POST /contatos` aceita `agenda: {tipo, data, hora, valor}` e cria o item junto.
- Pagamento confirmado (`/feedback`, confirmar na fila, lote) marca promessas pendentes do CPF como cumpridas.
- Ranking traz `agenda` do devedor (próximo compromisso) para mostrar na linha da fila.

**Tela**
- Página **Agenda** (operador e admin): três colunas/abas Alto · Médio · Safe, cada item
  com devedor, tipo, data, valor, ações (Cumprida · Não pagou · Remarcar · Abrir devedor).
  Admin alterna "Minha" / "Equipe".
- Aviso no menu: número de itens **alto + médio**, em vermelho se houver alto.
- Formulário de contato: com "Prometeu pagar", aparecem **Data prometida** e **Valor**;
  para qualquer resultado, **Agendar retorno** (data e hora).
- Linha da fila: selo "Retorno hoje" / "Promessa vencida".

**Aceite:** promessa vencida aparece em alto; pagamento confirmado cumpre a promessa
sozinho; operador vê só os seus itens; admin vê a equipe.

---

## F3 — Painel do operador

**Métricas (todas contagens reais, por período Hoje · 7 dias · 30 dias)**

| Métrica | Fonte |
|---|---|
| Contatos feitos | `contatos` do operador no período |
| Taxa de contato efetivo | contatos com resultado diferente de "sem resposta" ÷ contatos |
| Promessas feitas | itens de agenda tipo promessa criados por ele |
| Promessas cumpridas / quebradas | situação das promessas dele |
| Recebido da sua carteira | soma de pagamentos confirmados de devedores sob sua responsabilidade |
| Meta do dia | contatos hoje ÷ meta da empresa (se definida em Premissas) |

**Servidor:** `GET /painel/operador?periodo=` (o próprio); `GET /painel/equipe?periodo=` (admin: uma linha por operador).

**Tela:** página **Meu painel** com os números em destaque e a barra da meta; admin
vê a tabela da equipe ordenada por recebido. Premissas ganha **Meta de contatos por
operador por dia**.

**Aceite:** números batem com os registros; operador não vê o colega; sem meta, a barra não aparece.

---

## F4 — Roteiros de abordagem

**Regra de negócio.** Um roteiro é um texto com variáveis, de um canal (WhatsApp,
SMS, e-mail, ligação) e, opcionalmente, de uma oferta do catálogo. Dois donos:
**da empresa** (admin cria, todos usam) e **pessoal** (operador cria, só ele vê).
Sem roteiro cadastrado, valem modelos padrão do Mizan, um por oferta.

Variáveis: `{primeiro_nome} {nome} {valor_divida} {dias_atraso} {valor_proposta}
{parcelas} {valor_parcela} {desconto} {empresa}`.

**Servidor:** `GET/POST/PUT/DELETE /roteiros` (dono pessoal ou admin para os da
empresa); validação de tamanho e de variáveis conhecidas.

**Tela**
- Página **Roteiros**: abas por canal (WhatsApp · SMS · E-mail · Ligação), lista à
  esquerda, editor à direita com botões de variáveis e **prévia ao vivo** com um
  devedor de exemplo; salvar, duplicar, excluir.
- Ficha do devedor: cartão **Mensagem sugerida** — escolhe o roteiro do canal e da
  oferta recomendados, preenche com os dados do devedor e da proposta; botões
  **Copiar** e **Abrir no WhatsApp**.
- Limite conhecido: a base não tem telefone do devedor, então "Abrir no WhatsApp"
  abre o WhatsApp com o texto pronto e o operador escolhe o contato.

**Aceite:** variável desconhecida é recusada; pessoal não aparece para o colega;
operador não edita roteiro da empresa.

---

## Ordem de execução e entregas

1. Migração SQL única (o usuário roda uma vez no Supabase).
2. F1 → teste `test_fila_distribuicao.py` → telas → publicação.
3. F2 → `test_agenda.py` → telas → publicação.
4. F3 → `test_painel_operador.py` → telas → publicação.
5. F4 → `test_roteiros.py` → telas → publicação.
6. Ajuda: uma resposta por feature, ligada ao "?" de cada tela; catálogo de telas e testes de cobertura atualizados.
