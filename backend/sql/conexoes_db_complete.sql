-- ============================================================
-- MIZAN — Schema completo da tabela conexoes_db
-- Execute no Supabase: Database → SQL Editor → New query → Run
-- Seguro para rodar várias vezes (IF NOT EXISTS em tudo)
-- ============================================================

CREATE TABLE IF NOT EXISTS conexoes_db (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  usuario_id    TEXT NOT NULL,
  empresa_id    TEXT,
  nome          TEXT NOT NULL,
  tipo          TEXT NOT NULL DEFAULT 'postgres',
  host          TEXT,
  porta         INTEGER,
  banco         TEXT,
  usuario       TEXT,
  senha         TEXT,
  instance_name TEXT,
  service_name  TEXT,
  sheets_id     TEXT,
  sheets_aba    TEXT,
  query         TEXT,
  mapeamento    JSONB,
  ultimo_sync   TIMESTAMPTZ,
  carteira_id   UUID
);

-- Colunas adicionadas ao longo do desenvolvimento (seguro repetir):
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS instance_name TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS service_name  TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_id     TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_aba    TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS mapeamento    JSONB;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS ultimo_sync   TIMESTAMPTZ;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS empresa_id    TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS carteira_id   UUID;

-- Índices
CREATE INDEX IF NOT EXISTS idx_conexoes_usuario ON conexoes_db(usuario_id);
CREATE INDEX IF NOT EXISTS idx_conexoes_empresa  ON conexoes_db(empresa_id);
