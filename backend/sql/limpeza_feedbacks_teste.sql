-- ============================================================
-- MIZAN — Limpeza de feedbacks órfãos (sem predicao_id)
-- Execute no Supabase: Database → SQL Editor
-- ⚠️  IRREVERSÍVEL — veja o SELECT antes de confirmar o DELETE
-- ============================================================

-- 1. Primeiro, visualize o que será deletado:
SELECT id, cpf, pagou, valor_recuperado, created_at
FROM feedbacks
WHERE predicao_id IS NULL
ORDER BY created_at DESC;

-- 2. Se o resultado acima parecer correto (apenas dados de teste),
--    execute o DELETE abaixo:
-- DELETE FROM feedbacks WHERE predicao_id IS NULL;
