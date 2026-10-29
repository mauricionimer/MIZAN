-- Chave de API só pelo hash (plano de segurança, S3).
--
-- Uma chave do formato antigo (mizan_test_…) ficou versionada em frontend/.env
-- de maio a setembro de 2026 e foi para o JavaScript público. O código antigo
-- ainda a aceitava pela coluna em texto puro.
--
-- ORDEM: rode DEPOIS do deploy do backend que só consulta api_key_hash. Antes
-- dele, a versão antiga ainda lê a coluna api_key e quebraria.
--
-- Antes de rodar, confira quem ainda usa chave antiga:
--   select id, empresa_id, rotulo, ultimo_uso from api_keys where api_key is not null;

create extension if not exists pgcrypto;

-- 1) Revoga as chaves do formato antigo (a vazada é uma delas).
update api_keys set ativa = false where api_key like 'mizan_test_%';

-- 2) Garante o hash de qualquer chave que ainda só exista em texto.
update api_keys set api_key_hash = encode(sha256(convert_to(api_key, 'UTF8')), 'hex')
 where api_key_hash is null and api_key is not null;

-- 3) Apaga o texto puro.
alter table api_keys drop column if exists api_key;
