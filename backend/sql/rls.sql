-- ============================================================
-- MIZAN — Row Level Security (RLS)
-- Execute no Supabase: Database → SQL Editor → New query → Run
--
-- O backend usa a SERVICE ROLE KEY que bypassa o RLS.
-- O RLS bloqueia qualquer acesso direto com a chave anon/authenticated.
-- ============================================================

-- Tabelas com dados de clientes
ALTER TABLE carteiras     ENABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes     ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE contatos      ENABLE ROW LEVEL SECURITY;
ALTER TABLE recomendacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE conexoes_db   ENABLE ROW LEVEL SECURITY;

-- Tabelas do sistema
ALTER TABLE usuarios      ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys      ENABLE ROW LEVEL SECURITY;
ALTER TABLE reset_tokens  ENABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_estado ENABLE ROW LEVEL SECURITY;

-- Sem políticas explícitas = bloqueio total para anon/authenticated.
-- A service role key usada pelo backend bypassa automaticamente.
-- Nenhuma row é exposta caso alguém descubra a chave anon do projeto.

-- Permissões de uso das conexões: sem RLS, quem tem a chave anon gravava aqui e
-- liberava para um operador uma conexão que o admin não liberou.
ALTER TABLE conexao_permissoes ENABLE ROW LEVEL SECURITY;
