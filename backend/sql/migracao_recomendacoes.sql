-- ═══════════════════════════════════════════════════════════════════
-- Agente Cientista: recomendações versionadas (docs/PLANO_AGENTES_IA.md, etapa 6).
-- Uma tabela nova. Não altera nem apaga nenhuma tabela existente.
-- Idempotente: pode rodar mais de uma vez. Rodar no SQL Editor do Supabase.
-- ═══════════════════════════════════════════════════════════════════

-- Cada análise do Cientista vira uma recomendação "proposta". Só uma pessoa
-- aprova ou recusa. A aprovada entra como orientação no Estrategista; não muda
-- a política nem o bandit. O selo de evidência é calculado em código.
CREATE TABLE IF NOT EXISTS agente_recomendacoes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id     TEXT NOT NULL,
  versao         INTEGER NOT NULL CHECK (versao >= 1),
  texto          TEXT NOT NULL,
  selo           TEXT NOT NULL CHECK (selo IN ('sem evidência', 'indício', 'evidência')),
  origem         TEXT NOT NULL DEFAULT 'codigo' CHECK (origem IN ('ia', 'codigo')),
  relatorio      JSONB NOT NULL DEFAULT '{}'::jsonb,
  resultados     JSONB NOT NULL DEFAULT '{}'::jsonb,
  status         TEXT NOT NULL DEFAULT 'proposta' CHECK (status IN ('proposta', 'aprovada', 'recusada')),
  decidido_por   TEXT,
  decidido_em    TIMESTAMPTZ,
  UNIQUE (empresa_id, versao)
);
CREATE INDEX IF NOT EXISTS idx_agente_recomendacoes_status ON agente_recomendacoes (empresa_id, status, versao DESC);

-- Só o backend acessa (mesma regra das outras tabelas agente_*).
ALTER TABLE agente_recomendacoes ENABLE ROW LEVEL SECURITY;
