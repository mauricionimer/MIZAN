-- ═══════════════════════════════════════════════════════════════════
-- Oferta apresentada no contato
--
-- Rodar no SQL Editor do Supabase. É idempotente: pode rodar duas vezes.
-- Só acrescenta uma coluna; não altera nem apaga dado nenhum.
-- ═══════════════════════════════════════════════════════════════════

-- A tela do devedor envia a oferta que o operador apresentou (ex.: "parcelado_12x").
-- É ela que diz ao aprendizado das ofertas o que foi de fato negociado, e é a ela
-- que um pagamento confirmado depois é creditado. Sem a coluna, o contato com
-- oferta era recusado pelo banco.
ALTER TABLE contatos ADD COLUMN IF NOT EXISTS oferta TEXT;

-- Conferência: deve sair 1.
SELECT count(*) AS coluna_oferta FROM information_schema.columns
WHERE table_name = 'contatos' AND column_name = 'oferta';
