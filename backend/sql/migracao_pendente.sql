-- ═══════════════════════════════════════════════════════════════════
-- MIZAN — migração pendente
-- Cole no Supabase: Database → SQL Editor → Run
-- Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════

-- ── 1. Ciclo de cobrança ────────────────────────────────────────────
-- Em que fase a dívida está e o que sobra para o banco depois da comissão.
-- Sem estas, o bloco "Ciclo de cobrança" do dashboard fica vazio.
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS fase_cobranca          TEXT;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS valor_esperado_liquido NUMERIC(15,2);

-- ── 2. Retenção de dados ────────────────────────────────────────────
-- Anonimizar é zerar o identificador e deixar o resto da linha: o modelo
-- aprende de (variáveis → resultado) e nunca precisou saber quem era.
-- O CPF precisa aceitar NULL porque, com string vazia, uma busca por cpf=''
-- casaria de uma vez com todas as linhas anonimizadas.
ALTER TABLE predicoes     ALTER COLUMN cpf DROP NOT NULL;
ALTER TABLE feedbacks     ALTER COLUMN cpf DROP NOT NULL;
ALTER TABLE contatos      ALTER COLUMN cpf DROP NOT NULL;
ALTER TABLE recomendacoes ALTER COLUMN cpf DROP NOT NULL;

ALTER TABLE predicoes     ADD COLUMN IF NOT EXISTS anonimizado_em TIMESTAMPTZ;
ALTER TABLE feedbacks     ADD COLUMN IF NOT EXISTS anonimizado_em TIMESTAMPTZ;
ALTER TABLE contatos      ADD COLUMN IF NOT EXISTS anonimizado_em TIMESTAMPTZ;
ALTER TABLE recomendacoes ADD COLUMN IF NOT EXISTS anonimizado_em TIMESTAMPTZ;

-- A varredura procura sempre a mesma coisa: linha antiga que ainda tem
-- identificador. O índice parcial cobre só essas.
CREATE INDEX IF NOT EXISTS idx_predicoes_retencao
  ON predicoes(created_at) WHERE anonimizado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_feedbacks_retencao
  ON feedbacks(created_at) WHERE anonimizado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_contatos_retencao
  ON contatos(created_at) WHERE anonimizado_em IS NULL;
CREATE INDEX IF NOT EXISTS idx_recomendacoes_retencao
  ON recomendacoes(created_at) WHERE anonimizado_em IS NULL;

-- ── 3. Conferência ──────────────────────────────────────────────────
-- Devem sair 10 linhas, todas com ok = true.
SELECT table_name  AS tabela,
       column_name AS coluna,
       (is_nullable = 'YES') AS ok
  FROM information_schema.columns
 WHERE (table_name IN ('predicoes','feedbacks','contatos','recomendacoes')
        AND column_name IN ('cpf','anonimizado_em'))
    OR (table_name = 'predicoes'
        AND column_name IN ('fase_cobranca','valor_esperado_liquido'))
 ORDER BY tabela, coluna;
