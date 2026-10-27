-- Logs operacionais dos agentes. Execute depois de migracao_agente.sql.
-- Não guarda mensagem, nome ou documento de devedor: somente contexto técnico.
CREATE TABLE IF NOT EXISTS agente_logs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id   TEXT NOT NULL,
  nivel        TEXT NOT NULL CHECK (nivel IN ('aviso', 'erro', 'critico')),
  categoria    TEXT NOT NULL,
  mensagem     TEXT NOT NULL,
  agente       TEXT NOT NULL,
  evento_id    UUID REFERENCES agente_eventos(id) ON DELETE SET NULL,
  caso_id      UUID REFERENCES agente_casos(id) ON DELETE SET NULL,
  trace_id     TEXT,
  tentativa    INTEGER,
  detalhe      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_agente_logs_empresa_data
  ON agente_logs (empresa_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_agente_logs_abertos
  ON agente_logs (empresa_id, nivel, criado_em DESC);

ALTER TABLE agente_logs ENABLE ROW LEVEL SECURITY;
