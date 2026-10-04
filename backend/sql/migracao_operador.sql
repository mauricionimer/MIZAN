-- ═══════════════════════════════════════════════════════════════════
-- Ferramentas do operador: divisão da fila, agenda, roteiros
-- (docs/PLANO_OPERADOR.md). Rodar no SQL Editor do Supabase.
-- Idempotente: pode rodar mais de uma vez. Não apaga nada.
-- ═══════════════════════════════════════════════════════════════════

-- F1 — dono de cada devedor da fila
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS responsavel_id   TEXT;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS responsavel_nome TEXT;
CREATE INDEX IF NOT EXISTS idx_predicoes_carteira_responsavel
  ON predicoes (carteira_id, responsavel_id);

-- F2 — retornos e promessas de pagamento
CREATE TABLE IF NOT EXISTS agenda (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id      TEXT NOT NULL DEFAULT '',
  cpf             TEXT NOT NULL,
  nome            TEXT,
  carteira_id     UUID,
  predicao_id     UUID,
  operador_id     TEXT NOT NULL,
  operador_nome   TEXT NOT NULL DEFAULT '',
  tipo            TEXT NOT NULL CHECK (tipo IN ('promessa', 'retorno')),
  data            DATE NOT NULL,
  hora            TEXT,
  valor           NUMERIC(15,2),
  observacao      TEXT,
  situacao        TEXT NOT NULL DEFAULT 'pendente'
                  CHECK (situacao IN ('pendente', 'cumprida', 'quebrada', 'cancelada')),
  resolvido_em    TIMESTAMPTZ,
  resolvido_por   TEXT,
  contato_id      UUID
);
CREATE INDEX IF NOT EXISTS idx_agenda_empresa_operador ON agenda (empresa_id, operador_id, situacao, data);
CREATE INDEX IF NOT EXISTS idx_agenda_empresa_cpf      ON agenda (empresa_id, cpf, situacao);
ALTER TABLE agenda ENABLE ROW LEVEL SECURITY;

-- F4 — mensagens padrão (da empresa ou pessoais)
CREATE TABLE IF NOT EXISTS roteiros (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id      TEXT NOT NULL DEFAULT '',
  dono_id         TEXT,            -- NULL = roteiro da empresa; preenchido = pessoal
  dono_nome       TEXT,
  titulo          TEXT NOT NULL CHECK (char_length(titulo) BETWEEN 2 AND 80),
  canal           TEXT NOT NULL CHECK (canal IN ('whatsapp', 'sms', 'email', 'telefone')),
  oferta          TEXT,
  texto           TEXT NOT NULL CHECK (char_length(texto) BETWEEN 5 AND 2000)
);
CREATE INDEX IF NOT EXISTS idx_roteiros_empresa ON roteiros (empresa_id, canal);
ALTER TABLE roteiros ENABLE ROW LEVEL SECURITY;

-- Confere: deve listar responsavel_id, responsavel_nome, agenda e roteiros.
SELECT 'predicoes.' || column_name AS objeto FROM information_schema.columns
 WHERE table_name = 'predicoes' AND column_name IN ('responsavel_id', 'responsavel_nome')
UNION ALL
SELECT table_name FROM information_schema.tables WHERE table_name IN ('agenda', 'roteiros');
