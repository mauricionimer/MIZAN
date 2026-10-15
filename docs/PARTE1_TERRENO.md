# Parte 1 — preparar o terreno dos agentes

Primeira parte do `PLANO_EXECUCAO_AGENTES.md`. Objetivo: deixar pronta a base
que todos os agentes vão usar, **sem ligar nada em produção** e **sem gastar
nada de IA**. Nenhum agente conversa com ninguém nesta parte.

## O que entra

| # | Peça | Arquivo | Pronto quando |
|---|---|---|---|
| 1 | Tabelas do agente | `backend/sql/migracao_agente.sql` | Você rodou no Supabase e a conferência no fim lista as 6 tabelas |
| 2 | Situações do caso e mudanças permitidas | `backend/agente/estado.py` | Testes cobrem cada mudança proibida |
| 3 | Cliente de IA trocável, com cliente falso e teto de custo | `backend/agente/llm.py` | Testes rodam sem chave e sem custo |
| 4 | Rastreio (id por evento, um *span* por passo) | `backend/agente/rastreio.py` | Cada passo grava nó, agente, duração, tokens e custo |
| 5 | Orquestrador: fila de eventos, prioridade, trava por caso, idempotência, grafo, checkpoint e nó de erro | `backend/agente/orquestrador.py` | Testes de cada regra de coordenação |
| 6 | Guarda dos dados (memória para testes, Supabase para produção) | `backend/agente/repositorio.py` | Mesmos testes passam nas duas |
| 7 | Página do repositório público | `README.md` do AGENTESMIZAN | Explica o projeto sem número inventado |

## O que não entra (fica para as próximas partes)

Triagem, Negociador, Auditor, ferramentas, telas, chave da Anthropic, WhatsApp.
Nenhuma rota nova no `main.py`: o código fica parado até a Parte 2 ligá-lo.

## Decisões desta parte

- **Seis tabelas novas, nenhuma alterada.** O SQL só cria (`IF NOT EXISTS`), não
  apaga nem muda tabela existente. Pode rodar mais de uma vez.
- **Preço dos modelos não vem escrito no código.** Entra por variável de
  ambiente na segunda (19/10), conferido na página oficial da Anthropic. O
  cliente falso custa zero.
- **Teto de custo** por dia e por empresa, em dólar, por variável de ambiente.
  Passou do teto, o agente para e o caso vai para uma pessoa.
- **Trava por caso** com prazo, no mesmo padrão do `travas.py`: um processo que
  morre segurando a trava não bloqueia o caso para sempre.
- **Evento que falha duas vezes** vira "falhou" (a fila de falhas do curso) e
  fica visível para a Central, em vez de sumir.
- **Nó de erro**: qualquer passo que quebra tenta mais uma vez; quebrou de novo,
  o caso vai para uma pessoa com o motivo registrado.

## Ordem

1. Plano (este arquivo).
2. SQL → **você roda** (Supabase → SQL Editor → colar → Run).
3. `estado.py`, `llm.py`, `rastreio.py`, `repositorio.py`, `orquestrador.py`, com testes.
4. Bateria completa do backend passando → publicar nas duas branches.
5. README do repositório público.

## Situação

Concluída em 15/10: SQL rodado no Supabase (6 tabelas conferidas).

## O que você faz

- Rodar `backend/sql/migracao_agente.sql` no Supabase e me mandar o resultado
  da última consulta (a lista de tabelas).
- Nada mais nesta parte.
