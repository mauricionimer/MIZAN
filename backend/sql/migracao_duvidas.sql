-- ═══════════════════════════════════════════════════════════════════
-- Dúvidas enviadas pelos usuários ao COMANDO (Central de Ajuda, fase 5)
--
-- Rodar no SQL Editor do Supabase. É idempotente: pode rodar duas vezes.
-- Cria uma tabela nova; não altera nenhuma existente.
-- ═══════════════════════════════════════════════════════════════════

-- A pergunta é gravada JÁ MASCARADA pelo servidor (CPF, CNPJ, e-mail e
-- telefone viram [CPF], [CNPJ]...). `empresa_id` é o da pessoa que perguntou:
-- é o que deixa o administrador ver as dúvidas da própria equipe e só delas.
-- Dúvida de um usuário COMANDO nasce com empresa_id vazio.
CREATE TABLE IF NOT EXISTS duvidas (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  empresa_id    TEXT NOT NULL DEFAULT '',
  autor_id      TEXT NOT NULL,
  autor_email   TEXT NOT NULL DEFAULT '',
  autor_nome    TEXT NOT NULL DEFAULT '',
  pergunta      TEXT NOT NULL CHECK (char_length(pergunta) BETWEEN 3 AND 2000),
  tela          TEXT,
  buscou        TEXT,

  estado          TEXT NOT NULL DEFAULT 'aberta' CHECK (estado IN ('aberta', 'respondida')),
  resposta        TEXT CHECK (resposta IS NULL OR char_length(resposta) BETWEEN 2 AND 4000),
  respondida_por  TEXT,
  respondida_em   TIMESTAMPTZ,
  -- Quando quem perguntou viu a resposta. É o que acende e apaga o aviso na tela.
  visto_em        TIMESTAMPTZ,

  -- A resposta pode virar uma entrada da Central de Ajuda, depois de revisada.
  sugestao_estado        TEXT CHECK (sugestao_estado IN ('pendente', 'aprovada', 'descartada')),
  sugestao_titulo        TEXT,
  sugestao_revisada_por  TEXT,
  sugestao_revisada_em   TIMESTAMPTZ,

  -- Aberta não tem resposta; respondida tem resposta e data. Sem isto, uma
  -- gravação pela metade deixaria a dúvida "respondida" sem texto.
  CONSTRAINT duvidas_resposta_coerente CHECK (
    (estado = 'aberta' AND resposta IS NULL)
    OR (estado = 'respondida' AND resposta IS NOT NULL AND respondida_em IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_duvidas_autor    ON duvidas(autor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_duvidas_empresa  ON duvidas(empresa_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_duvidas_abertas  ON duvidas(created_at) WHERE estado = 'aberta';
CREATE INDEX IF NOT EXISTS idx_duvidas_sugestao ON duvidas(created_at) WHERE sugestao_estado = 'pendente';
-- O aviso "você tem resposta nova" consulta isto a cada página aberta.
CREATE INDEX IF NOT EXISTS idx_duvidas_novidade ON duvidas(autor_id)
  WHERE estado = 'respondida' AND visto_em IS NULL;

ALTER TABLE duvidas ENABLE ROW LEVEL SECURITY;

-- Conferência: deve sair 1 linha com existe = 1 e 5 índices.
SELECT 'tabela' AS item, count(*) AS existe FROM information_schema.tables WHERE table_name = 'duvidas'
UNION ALL
SELECT 'indices', count(*) FROM pg_indexes WHERE tablename = 'duvidas' AND indexname <> 'duvidas_pkey';
