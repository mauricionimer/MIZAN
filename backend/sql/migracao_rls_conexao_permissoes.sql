-- RLS na conexao_permissoes (plano de segurança, S12).
-- Era a única tabela dos scripts sem RLS. A chave anon do Supabase é pública
-- por natureza (e esteve no .env versionado); quem protege é o RLS. Sem ele,
-- quem tinha a chave anon gravava nesta tabela pela API do Supabase.
alter table conexao_permissoes enable row level security;

-- Conferência: deve retornar zero linhas.
--   select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
--    where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
