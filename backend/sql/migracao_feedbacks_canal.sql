-- Canal de cobrança de cada pagamento registrado (por onde a cobrança chegou ao
-- devedor). Vale para quem pagou e para quem não pagou. Pode rodar mais de uma vez.
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS canal_cobranca TEXT;

-- Confere: deve listar canal_cobranca.
SELECT column_name FROM information_schema.columns
WHERE table_name = 'feedbacks' AND column_name = 'canal_cobranca';
