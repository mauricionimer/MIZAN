-- ═══════════════════════════════════════════════════════════════════
-- Disponibilidade do operador: dia da semana e faixa de horário em que
-- cada operador atende (docs/PLANO_DISPONIBILIDADE_OPERADOR.md).
-- Uma tabela nova. Não altera nem apaga nenhuma tabela existente.
-- Idempotente: pode rodar mais de uma vez. Rodar no SQL Editor do Supabase.
-- ═══════════════════════════════════════════════════════════════════

-- Usada para escolher, quando o caso vai para "com_pessoa", o próximo
-- horário real em que um operador atende (agente/disponibilidade.py).
-- dia_semana: 0 = segunda ... 6 = domingo (igual a agente/estado.py e à
-- política do Auditor, que já usa essa convenção em "dias_semana").
CREATE TABLE IF NOT EXISTS disponibilidade_operador (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id     TEXT NOT NULL,
  usuario_id     UUID NOT NULL,
  dia_semana     INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
  hora_inicio    INTEGER NOT NULL CHECK (hora_inicio BETWEEN 0 AND 23),
  hora_fim       INTEGER NOT NULL CHECK (hora_fim BETWEEN 1 AND 24),
  ativo          BOOLEAN NOT NULL DEFAULT TRUE,
  CHECK (hora_inicio < hora_fim)
);
CREATE INDEX IF NOT EXISTS idx_disponibilidade_operador_empresa
  ON disponibilidade_operador (empresa_id, usuario_id, ativo);

-- Só o backend acessa (mesma regra das outras tabelas agente_*).
ALTER TABLE disponibilidade_operador ENABLE ROW LEVEL SECURITY;
