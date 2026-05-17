-- ============================================================
-- MIZAN — Schema do banco de dados (Supabase / PostgreSQL)
-- Execute no SQL Editor do Supabase: Database → SQL Editor
-- ============================================================

-- Carteiras: cada CSV analisado pelo Mizan
CREATE TABLE IF NOT EXISTS carteiras (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  nome_arquivo     TEXT,
  total_devedores  INTEGER,
  valor_face       NUMERIC(15,2),
  valor_esperado   NUMERIC(15,2),
  score_medio      NUMERIC(5,2),
  modelo_versao    TEXT DEFAULT 'v1'
);

-- Predicoes: score gerado por devedor em cada análise
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
  cluster_id                  INTEGER
);

-- Feedbacks: resultados reais enviados pelas empresas parceiras
CREATE TABLE IF NOT EXISTS feedbacks (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  cpf              TEXT NOT NULL,
  pagou            BOOLEAN NOT NULL,
  valor_recuperado NUMERIC(15,2) DEFAULT 0,
  data_pagamento   DATE,
  empresa          TEXT,
  predicao_id      UUID REFERENCES predicoes(id)
);

-- API Keys: autenticação das empresas parceiras
CREATE TABLE IF NOT EXISTS api_keys (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  empresa_nome TEXT NOT NULL UNIQUE,
  api_key      TEXT NOT NULL UNIQUE,
  ativa        BOOLEAN DEFAULT TRUE
);

-- Índices para buscas frequentes
CREATE INDEX IF NOT EXISTS idx_predicoes_cpf        ON predicoes(cpf);
CREATE INDEX IF NOT EXISTS idx_predicoes_carteira   ON predicoes(carteira_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_cpf        ON feedbacks(cpf);
CREATE INDEX IF NOT EXISTS idx_feedbacks_predicao   ON feedbacks(predicao_id);

-- Desabilita RLS para desenvolvimento (reabilitar em produção com policies)
ALTER TABLE carteiras  DISABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes  DISABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks  DISABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys   DISABLE ROW LEVEL SECURITY;

-- API key de exemplo para testes
INSERT INTO api_keys (empresa_nome, api_key)
VALUES ('empresa_teste', 'mizan_test_' || gen_random_uuid()::text)
ON CONFLICT DO NOTHING;
