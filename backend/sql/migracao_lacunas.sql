-- ═══════════════════════════════════════════════════════════════════
-- O que a Central de Ajuda não soube responder (Central de Ajuda, fase 6)
--
-- Rodar no SQL Editor do Supabase. É idempotente: pode rodar duas vezes.
-- Cria uma tabela nova; não altera nenhuma existente.
-- ═══════════════════════════════════════════════════════════════════

-- Cada linha é uma busca em que a Central não teve certeza, ou um "isto não
-- resolveu" explícito. NÃO há quem perguntou: nem usuário, nem empresa. Só o
-- perfil (operador, admin ou comando), porque o que um diretor pergunta é
-- diferente do que um operador pergunta, e isso orienta o que escrever.
--
-- O texto já vem mascarado pelo servidor (CPF, CNPJ, telefone e e-mail viram
-- [CPF]...). `chave` é o mesmo texto normalizado (sem acento, sem palavras de
-- ligação), usado só para agrupar variações da mesma pergunta.
CREATE TABLE IF NOT EXISTS ajuda_lacunas (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tipo         TEXT NOT NULL CHECK (tipo IN ('sem_resposta', 'nao_resolveu')),
  pergunta     TEXT NOT NULL CHECK (char_length(pergunta) BETWEEN 2 AND 300),
  chave        TEXT NOT NULL CHECK (char_length(chave) BETWEEN 1 AND 300),
  -- só em 'nao_resolveu': a resposta que foi mostrada e não resolveu
  entrada_id   TEXT,
  perfil       TEXT NOT NULL CHECK (perfil IN ('operador', 'admin', 'comando')),
  -- o COMANDO marca como tratada quando escreveu a resposta que faltava
  tratada_em   TIMESTAMPTZ,
  tratada_por  TEXT
);

CREATE INDEX IF NOT EXISTS idx_ajuda_lacunas_chave ON ajuda_lacunas(chave, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ajuda_lacunas_data  ON ajuda_lacunas(created_at DESC);

ALTER TABLE ajuda_lacunas ENABLE ROW LEVEL SECURITY;

-- Conferência: deve sair tabela = 1 e indices = 2.
SELECT 'tabela' AS item, count(*) AS existe FROM information_schema.tables WHERE table_name = 'ajuda_lacunas'
UNION ALL
SELECT 'indices', count(*) FROM pg_indexes WHERE tablename = 'ajuda_lacunas' AND indexname <> 'ajuda_lacunas_pkey';
