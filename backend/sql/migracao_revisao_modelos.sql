-- Revisão dos modelos (área 5). Opcional: o código funciona sem isto.
--
-- Webhook de pagamento e /feedback/lote passaram a conferir, antes de gravar,
-- se o mesmo pagamento (empresa + CPF + data + valor) já existe. Este índice
-- deixa essa conferência rápida em tabelas grandes. Não é UNIQUE de propósito:
-- bases antigas podem ter repetidos, e um UNIQUE falharia ao ser criado.
CREATE INDEX IF NOT EXISTS idx_feedbacks_idempotencia
    ON feedbacks (empresa, cpf, data_pagamento);
