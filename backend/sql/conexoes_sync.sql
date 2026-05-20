-- Adiciona colunas de suporte à sincronização automática na tabela conexoes_db
-- Execute no Supabase: Database → SQL Editor → New query → Run

ALTER TABLE conexoes_db
  ADD COLUMN IF NOT EXISTS mapeamento   JSONB,
  ADD COLUMN IF NOT EXISTS ultimo_sync  TIMESTAMPTZ;
