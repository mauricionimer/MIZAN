-- ═══════════════════════════════════════════════════════════════════
-- Agentes do Mizan — Parte 1 (docs/PARTE1_TERRENO.md).
-- Seis tabelas novas. Não altera nem apaga nenhuma tabela existente.
-- Idempotente: pode rodar mais de uma vez. Rodar no SQL Editor do Supabase.
-- ═══════════════════════════════════════════════════════════════════

-- Política da empresa, com versão. Cada decisão do Auditor registra a versão
-- que estava valendo. Versão nova não apaga a anterior.
CREATE TABLE IF NOT EXISTS agente_politicas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id      TEXT NOT NULL,
  versao          INTEGER NOT NULL CHECK (versao >= 1),
  regras          JSONB NOT NULL DEFAULT '{}'::jsonb,
  ativa           BOOLEAN NOT NULL DEFAULT FALSE,
  criado_por      TEXT,
  UNIQUE (empresa_id, versao)
);
CREATE INDEX IF NOT EXISTS idx_agente_politicas_ativa ON agente_politicas (empresa_id, ativa);

-- Um caso por devedor em atendimento. É o estado do grafo e o checkpoint.
CREATE TABLE IF NOT EXISTS agente_casos (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id       TEXT NOT NULL,
  predicao_id      UUID NOT NULL,
  situacao         TEXT NOT NULL DEFAULT 'novo' CHECK (situacao IN (
                     'novo', 'so_lembrete', 'em_contato', 'negociando',
                     'acordo_ativo', 'atrasado', 'pagamento_em_conferencia',
                     'contestado', 'suspenso', 'com_pessoa', 'quitado', 'quebrado')),
  grupo            TEXT,
  grupo_controle   BOOLEAN NOT NULL DEFAULT FALSE,
  proxima_data     DATE,
  tentativas       INTEGER NOT NULL DEFAULT 0,
  versao_politica  INTEGER,
  resumo           TEXT,
  ultimo_passo     TEXT,
  dados            JSONB NOT NULL DEFAULT '{}'::jsonb,
  trava_dono       TEXT,
  trava_ate        TIMESTAMPTZ,
  UNIQUE (empresa_id, predicao_id)
);
CREATE INDEX IF NOT EXISTS idx_agente_casos_situacao ON agente_casos (empresa_id, situacao, proxima_data);

-- Fila de eventos e memória episódica do caso. A chave impede o mesmo evento
-- de ser processado duas vezes (idempotência).
CREATE TABLE IF NOT EXISTS agente_eventos (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id      TEXT NOT NULL,
  caso_id         UUID NOT NULL REFERENCES agente_casos(id) ON DELETE CASCADE,
  tipo            TEXT NOT NULL,
  origem          TEXT NOT NULL DEFAULT 'sistema',
  chave           TEXT NOT NULL,
  prioridade      INTEGER NOT NULL DEFAULT 50,
  dados           JSONB NOT NULL DEFAULT '{}'::jsonb,
  situacao        TEXT NOT NULL DEFAULT 'pendente' CHECK (situacao IN ('pendente', 'processando', 'feito', 'falhou')),
  tentativas      INTEGER NOT NULL DEFAULT 0,
  erro            TEXT,
  trace_id        TEXT,
  disponivel_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  concluido_em    TIMESTAMPTZ,
  UNIQUE (empresa_id, chave)
);
CREATE INDEX IF NOT EXISTS idx_agente_eventos_fila ON agente_eventos (situacao, prioridade DESC, criado_em);
CREATE INDEX IF NOT EXISTS idx_agente_eventos_caso ON agente_eventos (empresa_id, caso_id, criado_em);

-- Rastreio: um passo (span) por nó executado, com versões, tokens, custo e duração.
CREATE TABLE IF NOT EXISTS agente_passos (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id       TEXT NOT NULL,
  trace_id         TEXT NOT NULL,
  caso_id          UUID,
  evento_id        UUID,
  no               TEXT NOT NULL,
  agente           TEXT NOT NULL,
  resultado        TEXT NOT NULL CHECK (resultado IN ('ok', 'erro', 'bloqueado')),
  duracao_ms       INTEGER NOT NULL DEFAULT 0,
  regra            TEXT,
  versao_politica  INTEGER,
  modelo           TEXT,
  versao_prompt    TEXT,
  tokens_entrada   INTEGER NOT NULL DEFAULT 0,
  tokens_saida     INTEGER NOT NULL DEFAULT 0,
  custo_usd        NUMERIC(12,6) NOT NULL DEFAULT 0,
  detalhe          JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_agente_passos_trace ON agente_passos (trace_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_agente_passos_custo ON agente_passos (empresa_id, criado_em);

-- Mensagens trocadas com o devedor, com data para apagar (retenção).
CREATE TABLE IF NOT EXISTS agente_mensagens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id  TEXT NOT NULL,
  caso_id     UUID NOT NULL REFERENCES agente_casos(id) ON DELETE CASCADE,
  direcao     TEXT NOT NULL CHECK (direcao IN ('entrada', 'saida')),
  texto       TEXT NOT NULL,
  trace_id    TEXT,
  apagar_em   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_agente_mensagens_caso ON agente_mensagens (empresa_id, caso_id, criado_em);

-- Contestações do devedor. Enquanto aberta, o agente não cobra.
CREATE TABLE IF NOT EXISTS agente_contestacoes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id     TEXT NOT NULL,
  caso_id        UUID NOT NULL REFERENCES agente_casos(id) ON DELETE CASCADE,
  motivo         TEXT NOT NULL,
  situacao       TEXT NOT NULL DEFAULT 'aberta' CHECK (situacao IN ('aberta', 'resolvida')),
  resolvida_em   TIMESTAMPTZ,
  resolvida_por  TEXT
);
CREATE INDEX IF NOT EXISTS idx_agente_contestacoes_caso ON agente_contestacoes (empresa_id, caso_id, situacao);

-- Mesma regra das outras tabelas (sql/rls.sql): só o backend acessa.
ALTER TABLE agente_politicas    ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente_casos        ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente_eventos      ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente_passos       ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente_mensagens    ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente_contestacoes ENABLE ROW LEVEL SECURITY;

-- Confere: deve listar as 6 tabelas.
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'agente\_%'
ORDER BY table_name;
