-- ============================================================
-- MIZAN — Schema completo do banco de dados (Supabase / PostgreSQL)
-- Execute no SQL Editor do Supabase: Database → SQL Editor
-- Seguro para rodar várias vezes (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
-- ============================================================

-- ── Carteiras ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS carteiras (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  nome_arquivo     TEXT,
  total_devedores  INTEGER,
  valor_face       NUMERIC(15,2),
  valor_esperado   NUMERIC(15,2),
  score_medio      NUMERIC(5,2),
  modelo_versao    TEXT DEFAULT 'v1',
  empresa_id       TEXT DEFAULT ''
);

ALTER TABLE carteiras ADD COLUMN IF NOT EXISTS empresa_id TEXT DEFAULT '';

-- ── Predições ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predicoes (
  id                          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  carteira_id                 UUID REFERENCES carteiras(id) ON DELETE CASCADE,
  cpf                         TEXT NOT NULL,
  nome                        TEXT,
  produto                     TEXT,
  uf                          TEXT,
  valor_divida                NUMERIC(15,2),
  dias_em_atraso              INTEGER,
  score_recuperabilidade      NUMERIC(5,2),
  valor_esperado_recuperacao  NUMERIC(15,2),
  perfil_cluster              TEXT,
  cluster_id                  INTEGER,
  renda_estimada              NUMERIC(15,2),
  status                      TEXT,
  dados_incompletos           BOOLEAN DEFAULT FALSE,
  aviso_dados                 TEXT DEFAULT '',
  taxa_recuperacao_prevista   NUMERIC(5,4)
);

ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS renda_estimada            NUMERIC(15,2);
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS status                    TEXT;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS dados_incompletos         BOOLEAN DEFAULT FALSE;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS aviso_dados               TEXT DEFAULT '';
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS taxa_recuperacao_prevista NUMERIC(5,4);

-- ── Feedbacks ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedbacks (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  cpf              TEXT NOT NULL,
  pagou            BOOLEAN NOT NULL,
  valor_recuperado NUMERIC(15,2) DEFAULT 0,
  data_pagamento   DATE,
  empresa          TEXT,
  predicao_id      UUID REFERENCES predicoes(id),
  registrado_por   TEXT
);

ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS registrado_por TEXT;

-- ── Usuários ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
  id          TEXT PRIMARY KEY,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  email       TEXT UNIQUE NOT NULL,
  nome        TEXT NOT NULL,
  senha_hash  TEXT NOT NULL,
  role        TEXT NOT NULL DEFAULT 'operador',
  ativo       BOOLEAN NOT NULL DEFAULT true,
  empresa_id  TEXT DEFAULT ''
);

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa_id TEXT DEFAULT '';

-- ── Conexões com bancos externos ─────────────────────────────
CREATE TABLE IF NOT EXISTS conexoes_db (
  id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  usuario_id            TEXT NOT NULL,
  empresa_id            TEXT DEFAULT '',
  nome                  TEXT NOT NULL,
  tipo                  TEXT NOT NULL DEFAULT 'postgres',
  host                  TEXT,
  porta                 INTEGER,
  banco                 TEXT,
  usuario               TEXT,
  senha                 TEXT,
  instance_name         TEXT,
  service_name          TEXT,
  sheets_id             TEXT,
  sheets_aba            TEXT,
  query                 TEXT,
  mapeamento            JSONB,
  ultimo_sync           TIMESTAMPTZ,
  ultimo_sync_por       TEXT,
  carteira_id           UUID,
  intervalo_sync_horas  NUMERIC DEFAULT 1,
  coluna_writeback      TEXT,
  valor_pago            TEXT DEFAULT 'pago',
  valor_nao_pago        TEXT
);

ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS instance_name        TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS service_name         TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_id            TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_aba           TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS mapeamento           JSONB;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS ultimo_sync          TIMESTAMPTZ;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS ultimo_sync_por      TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS empresa_id           TEXT DEFAULT '';
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS carteira_id          UUID;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS intervalo_sync_horas NUMERIC DEFAULT 1;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS coluna_writeback     TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS valor_pago           TEXT DEFAULT 'pago';
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS valor_nao_pago       TEXT;

-- ── Contatos (histórico de abordagem por devedor) ─────────────
CREATE TABLE IF NOT EXISTS contatos (
  id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  cpf                     TEXT NOT NULL,
  canal                   TEXT NOT NULL,
  resultado               TEXT NOT NULL,
  data_contato            DATE,
  observacao              TEXT,
  valor_recuperado        NUMERIC(15,2),
  desconto_oferecido_pct  NUMERIC(5,2),
  acao_bandit_id          INTEGER,
  usuario_id              TEXT,
  usuario_nome            TEXT,
  empresa_id              TEXT DEFAULT ''
);

-- ── Recomendações do bandit (log) ────────────────────────────
CREATE TABLE IF NOT EXISTS recomendacoes (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  cpf        TEXT NOT NULL,
  acao_id    INTEGER,
  canal      TEXT,
  oferta     TEXT,
  score_ucb  NUMERIC(10,6),
  contexto   JSONB
);

-- ── Estado do bandit LinUCB ──────────────────────────────────
CREATE TABLE IF NOT EXISTS bandit_estado (
  id         INTEGER PRIMARY KEY DEFAULT 1,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  estado     JSONB
);

-- ── Auditoria ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auditoria (
  id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  acao           TEXT NOT NULL,
  entidade       TEXT,
  entidade_id    TEXT,
  usuario_id     TEXT,
  usuario_email  TEXT DEFAULT '',
  empresa_id     TEXT DEFAULT '',
  detalhes       JSONB
);

-- ── Tokens de redefinição de senha ───────────────────────────
CREATE TABLE IF NOT EXISTS reset_tokens (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  email      TEXT NOT NULL,
  token      TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  usado      BOOLEAN DEFAULT FALSE
);

-- ── API Keys (legado) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  empresa_nome TEXT NOT NULL UNIQUE,
  api_key      TEXT NOT NULL UNIQUE,
  ativa        BOOLEAN DEFAULT TRUE
);

-- ── Índices ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_predicoes_cpf        ON predicoes(cpf);
CREATE INDEX IF NOT EXISTS idx_predicoes_carteira   ON predicoes(carteira_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_cpf        ON feedbacks(cpf);
CREATE INDEX IF NOT EXISTS idx_feedbacks_predicao   ON feedbacks(predicao_id);
CREATE INDEX IF NOT EXISTS idx_carteiras_empresa    ON carteiras(empresa_id);
CREATE INDEX IF NOT EXISTS idx_contatos_cpf         ON contatos(cpf);
CREATE INDEX IF NOT EXISTS idx_contatos_empresa     ON contatos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_recomendacoes_cpf    ON recomendacoes(cpf);
CREATE INDEX IF NOT EXISTS idx_auditoria_empresa    ON auditoria(empresa_id);
CREATE INDEX IF NOT EXISTS idx_conexoes_usuario     ON conexoes_db(usuario_id);
CREATE INDEX IF NOT EXISTS idx_conexoes_empresa     ON conexoes_db(empresa_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_email       ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_token   ON reset_tokens(token);

-- ── RLS desabilitado (backend usa service role key) ──────────
ALTER TABLE carteiras     DISABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes     DISABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks     DISABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios      DISABLE ROW LEVEL SECURITY;
ALTER TABLE conexoes_db   DISABLE ROW LEVEL SECURITY;
ALTER TABLE contatos      DISABLE ROW LEVEL SECURITY;
ALTER TABLE recomendacoes DISABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_estado DISABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria     DISABLE ROW LEVEL SECURITY;
ALTER TABLE reset_tokens  DISABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys      DISABLE ROW LEVEL SECURITY;
