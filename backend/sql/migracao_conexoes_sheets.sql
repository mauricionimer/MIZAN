-- ═══════════════════════════════════════════════════════════════════
-- Credencial da conta de serviço nas conexões Google Sheets salvas
--
-- Rodar no SQL Editor do Supabase. É idempotente: pode rodar duas vezes.
-- Só acrescenta uma coluna; não altera nem apaga dado nenhum.
-- ═══════════════════════════════════════════════════════════════════

-- Sem ela, a conexão Sheets salva não guardava a credencial e a sincronização
-- (manual e automática) falhava. O servidor grava o JSON CIFRADO, com a mesma
-- chave da senha de banco (MIZAN_ENCRYPTION_KEY), e nunca o devolve à tela.
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_credenciais TEXT;

-- Conferência: deve sair 1.
SELECT count(*) AS coluna_sheets_credenciais FROM information_schema.columns
WHERE table_name = 'conexoes_db' AND column_name = 'sheets_credenciais';
