-- Tabela de permissões de acesso a conexões de banco de dados por operador
-- Execute no Supabase SQL Editor

CREATE TABLE IF NOT EXISTS conexao_permissoes (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conexao_id  TEXT NOT NULL,
  operador_id TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (conexao_id, operador_id)
);

-- Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_conexao_permissoes_conexao ON conexao_permissoes (conexao_id);
CREATE INDEX IF NOT EXISTS idx_conexao_permissoes_operador ON conexao_permissoes (operador_id);
