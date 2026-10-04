-- Condições do acordo em cada pagamento registrado (forma, parcelas, juros, desconto).
-- São o resultado da negociação: servem para medir que condição funciona, não
-- entram no score. Pode rodar mais de uma vez.
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS forma_pagamento   TEXT;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS parcelas          INTEGER;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS com_juros         BOOLEAN;
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS taxa_juros_mensal NUMERIC(6,3);
ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS desconto_pct      NUMERIC(6,2);

-- Confere: deve listar as 5 colunas.
SELECT column_name FROM information_schema.columns
WHERE table_name = 'feedbacks'
  AND column_name IN ('forma_pagamento','parcelas','com_juros','taxa_juros_mensal','desconto_pct');
