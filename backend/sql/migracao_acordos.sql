-- ═══════════════════════════════════════════════════════════════════
-- Acordos em andamento (docs/PLANO_ADMIN.md, A4).
-- Uma linha por parcela de acordo parcelado, agrupadas pelo pagamento
-- (feedback) que abriu o acordo. Rodar no SQL Editor do Supabase.
-- Idempotente: pode rodar mais de uma vez. Não apaga nada.
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS acordo_parcelas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id      TEXT NOT NULL DEFAULT '',
  feedback_id     TEXT NOT NULL,
  cpf             TEXT NOT NULL,
  nome            TEXT,
  carteira_id     UUID,
  predicao_id     UUID,
  numero          INTEGER NOT NULL CHECK (numero >= 1),
  total           INTEGER NOT NULL CHECK (total >= 2 AND total <= 120),
  vencimento      DATE NOT NULL,
  valor           NUMERIC(15,2) NOT NULL DEFAULT 0,
  situacao        TEXT NOT NULL DEFAULT 'pendente' CHECK (situacao IN ('pendente', 'paga')),
  pago_em         TIMESTAMPTZ,
  pago_por        TEXT,
  UNIQUE (feedback_id, numero)
);
CREATE INDEX IF NOT EXISTS idx_acordo_parcelas_empresa ON acordo_parcelas (empresa_id, situacao, vencimento);
CREATE INDEX IF NOT EXISTS idx_acordo_parcelas_acordo  ON acordo_parcelas (empresa_id, feedback_id);
ALTER TABLE acordo_parcelas ENABLE ROW LEVEL SECURITY;

-- Confere: deve listar acordo_parcelas.
SELECT table_name FROM information_schema.tables WHERE table_name = 'acordo_parcelas';
