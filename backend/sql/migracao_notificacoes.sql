-- ═══════════════════════════════════════════════════════════════════
-- Notificações para administradores e operadores
-- (docs/PLANO_NOTIFICACOES.md e docs/NOTIFICACOES.md).
-- Duas tabelas novas. Não altera nem apaga nenhuma tabela existente.
-- Idempotente: pode rodar mais de uma vez. Rodar no SQL Editor do Supabase.
-- ═══════════════════════════════════════════════════════════════════

-- Uma linha por pessoa que recebe. Nunca guarda CPF, valor ou texto da conversa:
-- o título e o texto levam no máximo o primeiro nome do devedor.
CREATE TABLE IF NOT EXISTS notificacoes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),     -- muda quando outro aviso igual se junta a este
  empresa_id     TEXT NOT NULL DEFAULT '',
  usuario_id     TEXT NOT NULL,
  tipo           TEXT NOT NULL CHECK (char_length(tipo) BETWEEN 2 AND 12),
  categoria      TEXT NOT NULL CHECK (categoria IN ('conversas', 'reunioes', 'retornos', 'pedidos', 'equipe', 'sistema')),
  prioridade     TEXT NOT NULL CHECK (prioridade IN ('urgente', 'alta', 'normal')),
  titulo         TEXT NOT NULL CHECK (char_length(titulo) BETWEEN 1 AND 120),
  texto          TEXT CHECK (texto IS NULL OR char_length(texto) <= 300),
  -- Só telas internas do Mizan ("/pasta/<id>?aba=conversa"): nunca um endereço de fora.
  link           TEXT CHECK (link IS NULL OR (char_length(link) <= 300 AND link LIKE '/%' AND link NOT LIKE '//%')),
  acao           TEXT CHECK (acao IS NULL OR char_length(acao) <= 40),      -- texto do botão ("Abrir conversa")
  entidade       TEXT CHECK (entidade IS NULL OR char_length(entidade) <= 40),
  entidade_id    TEXT CHECK (entidade_id IS NULL OR char_length(entidade_id) <= 80),
  chave          TEXT NOT NULL CHECK (char_length(chave) BETWEEN 1 AND 200),
  agrupadas      INTEGER NOT NULL DEFAULT 1 CHECK (agrupadas >= 1),
  lida_em        TIMESTAMPTZ,
  resolvida_em   TIMESTAMPTZ,
  escalada_em    TIMESTAMPTZ
);

-- Lista de cada pessoa (mais recentes primeiro) e contagem das abertas.
CREATE INDEX IF NOT EXISTS idx_notificacoes_usuario
  ON notificacoes (usuario_id, atualizado_em DESC);
CREATE INDEX IF NOT EXISTS idx_notificacoes_abertas
  ON notificacoes (usuario_id, prioridade) WHERE lida_em IS NULL AND resolvida_em IS NULL;
-- Resolver os avisos de um compromisso ou caso que perdeu o sentido.
CREATE INDEX IF NOT EXISTS idx_notificacoes_entidade
  ON notificacoes (empresa_id, entidade, entidade_id) WHERE resolvida_em IS NULL;
-- Escalonamento do urgente sem leitura (o relógio olha a cada minuto).
CREATE INDEX IF NOT EXISTS idx_notificacoes_urgentes
  ON notificacoes (criado_em) WHERE prioridade = 'urgente' AND lida_em IS NULL
  AND resolvida_em IS NULL AND escalada_em IS NULL;
-- Dois avisos iguais abertos para a mesma pessoa são impossíveis, mesmo com dois
-- servidores no ar durante um deploy.
CREATE UNIQUE INDEX IF NOT EXISTS uq_notificacoes_abertas
  ON notificacoes (usuario_id, chave) WHERE lida_em IS NULL AND resolvida_em IS NULL;

-- Preferências de cada pessoa (só existe a linha de quem mudou algo; o resto usa o padrão).
CREATE TABLE IF NOT EXISTS notificacao_preferencias (
  usuario_id         TEXT PRIMARY KEY,
  empresa_id         TEXT NOT NULL DEFAULT '',
  dados              JSONB NOT NULL DEFAULT '{}'::jsonb,
  resumo_enviado_em  DATE,                                 -- último resumo por e-mail (não manda duas vezes no dia)
  atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Apagar um usuário (ou excluir o cliente inteiro, pela função excluir_dados_cliente)
-- apaga as notificações e as preferências dele no mesmo passo.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'usuarios' AND column_name = 'id'
               AND data_type = 'text') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_notificacoes_usuario') THEN
      ALTER TABLE notificacoes ADD CONSTRAINT fk_notificacoes_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_notificacao_preferencias_usuario') THEN
      ALTER TABLE notificacao_preferencias ADD CONSTRAINT fk_notificacao_preferencias_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE;
    END IF;
  ELSE
    RAISE NOTICE 'usuarios.id não é texto: as notificações ficam sem a ligação que apaga junto com o usuário.';
  END IF;
END $$;

-- Só o backend acessa (mesma regra das outras tabelas): RLS ligada e nenhuma política.
ALTER TABLE notificacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notificacao_preferencias ENABLE ROW LEVEL SECURITY;

-- A API do Supabase passa a enxergar as tabelas novas na hora.
NOTIFY pgrst, 'reload schema';

-- Confere: deve mostrar 2 tabelas, rls_ligada = true nas duas e apaga_com_usuario = 2.
SELECT
  (SELECT count(*) FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name IN ('notificacoes', 'notificacao_preferencias')) AS tabelas,
  (SELECT bool_and(relrowsecurity) FROM pg_class
    WHERE relname IN ('notificacoes', 'notificacao_preferencias') AND relkind = 'r') AS rls_ligada,
  (SELECT count(*) FROM pg_constraint
    WHERE conname IN ('fk_notificacoes_usuario', 'fk_notificacao_preferencias_usuario')) AS apaga_com_usuario;
