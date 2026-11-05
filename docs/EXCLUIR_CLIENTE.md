# Excluir um cliente e todos os dados dele

Pelo painel COMANDO, dá para apagar um cliente (empresa) e **tudo** o que é dele, de uma vez.
**Não dá para desfazer.**

## Como usar

1. **Supabase, uma vez:** rode `backend/sql/migracao_excluir_cliente.sql` no SQL Editor.
   Sem isso, o botão responde que falta rodar esse SQL e **nada é apagado**.
2. Entre como **COMANDO** → **Usuários → aba Empresas** → toque na **lixeira** do cliente.
3. Na janela: marque "Entendo que não dá para desfazer", digite o nome do cliente (ou o código
   dele), a sua senha e o código de 6 dígitos do aplicativo autenticador.
4. Toque em **Excluir tudo** e, em até 5 segundos, toque de novo em **Clique de novo para
   excluir definitivamente**. A janela mostra o que foi apagado.

## O que é apagado

Carteiras, devedores (previsões) e feedbacks; conexões e as permissões delas; chaves de API;
agenda, acordos, ofertas, contatos e roteiros; configuração e imagem da empresa; política e
conversas dos agentes (casos, mensagens, eventos, passos, logs, consultas jurídicas); o Cientista
(ações, eventos, exposições, resultados e bases); recomendações e bandit; os modelos do cliente
(disco e Storage); e **os usuários da empresa** (com os links de redefinição de senha deles).

## O que fica

- **A trilha de auditoria** do cliente, **sem o e-mail** das pessoas (e-mail é dado pessoal). Ela
  ganha um registro `cliente_excluido`, com quem apagou e quantos itens de cada tipo.
- **Usuários COMANDO.** Se houver um COMANDO dentro da empresa, a exclusão é recusada: tire-o da
  empresa antes.
- Dados globais da plataforma (por exemplo as leis do RAG jurídico) e os outros clientes.

## Segurança

- Só **COMANDO**; nome digitado; **senha**; **código do aplicativo** (se ele estiver ligado);
  limite de tentativas; dois cliques.
- O banco apaga tudo **numa transação só**: se algo der errado, nada é apagado.
- O histórico do Cientista é só de acréscimo de propósito. A exclusão é o único caminho que o
  apaga, e só dentro da função do banco. Por fora, apagar continua proibido.
- A função é executada só pelo backend (`service_role`). `anon` e `authenticated` não podem.
- Se a pessoa excluída tinha sessão aberta, ela cai (o usuário deixa de existir).

## Como foi provado

- `backend/test_excluir_cliente.py`: travas, limites, 2FA, erro do banco e arquivos de modelo.
- A função SQL foi testada em um **PostgreSQL 16 de verdade**, com o esquema do projeto e dados de
  dois clientes em todas as 33 tabelas: apagou o cliente pedido, não tocou no outro, manteve a
  auditoria sem e-mail, recusou empresa com COMANDO, recusou `anon`/`authenticated` e manteve o
  histórico do Cientista protegido contra apagar por fora.

## Antes de usar de verdade

- **Faça uma cópia se precisar.** O Supabase grátis não tem backup para restaurar. Uma vez
  excluído, acabou.
- Se o cliente ainda for usado em uma demonstração, exclua **depois**.
