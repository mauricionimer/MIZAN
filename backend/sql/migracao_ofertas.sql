-- ═══════════════════════════════════════════════════════════════════
-- Ofertas feitas pelo operador (docs/PLANO_OFERTAS.md, O3).
-- Uma linha por oferta confirmada, com as condições, a análise do
-- momento e a resposta do devedor. Rodar no SQL Editor do Supabase.
-- Idempotente: pode rodar mais de uma vez. Não apaga nada.
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ofertas_feitas (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id        TEXT NOT NULL DEFAULT '',
  cpf               TEXT NOT NULL,
  nome              TEXT,
  carteira_id       UUID,
  predicao_id       UUID,
  operador_id       TEXT NOT NULL,
  operador_nome     TEXT NOT NULL DEFAULT '',
  canal             TEXT NOT NULL,
  resposta          TEXT NOT NULL CHECK (resposta IN ('aceitou', 'vai_pensar', 'recusou')),
  base_id           TEXT,
  familia           TEXT,
  desconto_pct      NUMERIC(6,2)  NOT NULL DEFAULT 0,
  entrada_pct       NUMERIC(6,2)  NOT NULL DEFAULT 0,
  n_parcelas        INTEGER       NOT NULL DEFAULT 1,
  juros_mensal_pct  NUMERIC(6,3)  NOT NULL DEFAULT 0,
  valor_divida      NUMERIC(15,2),
  valor_negociado   NUMERIC(15,2),
  entrada           NUMERIC(15,2),
  parcela           NUMERIC(15,2),
  total_pago        NUMERIC(15,2),
  chance_pagar      NUMERIC(6,4),
  valor_esperado    NUMERIC(15,2),
  veredito_devedor  TEXT,
  veredito_banco    TEXT,
  veredito_geral    TEXT,
  agenda_data       DATE,
  contato_id        UUID,
  observacao        TEXT
);
CREATE INDEX IF NOT EXISTS idx_ofertas_feitas_empresa_cpf ON ofertas_feitas (empresa_id, cpf, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ofertas_feitas_empresa_op  ON ofertas_feitas (empresa_id, operador_id, created_at DESC);
ALTER TABLE ofertas_feitas ENABLE ROW LEVEL SECURITY;

-- Confere: deve listar ofertas_feitas.
SELECT table_name FROM information_schema.tables WHERE table_name = 'ofertas_feitas';
