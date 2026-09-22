-- ============================================================
-- MIZAN — Schema completo do banco de dados (Supabase / PostgreSQL)
-- Execute no SQL Editor do Supabase: Database → SQL Editor
-- Seguro para rodar várias vezes (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
-- ============================================================

-- ── Carteiras ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS carteiras (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  nome_arquivo     TEXT,
  total_devedores  INTEGER,
  valor_face       NUMERIC(15,2),
  valor_esperado   NUMERIC(15,2),
  score_medio      NUMERIC(5,2),
  modelo_versao    TEXT DEFAULT 'v1',
  empresa_id       TEXT DEFAULT ''
);

ALTER TABLE carteiras ADD COLUMN IF NOT EXISTS empresa_id TEXT DEFAULT '';

-- ── Predições ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predicoes (
  id                          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  carteira_id                 UUID REFERENCES carteiras(id) ON DELETE CASCADE,
  cpf                         TEXT NOT NULL,
  nome                        TEXT,
  produto                     TEXT,
  uf                          TEXT,
  valor_divida                NUMERIC(15,2),
  dias_em_atraso              INTEGER,
  score_recuperabilidade      NUMERIC(5,2),
  valor_esperado_recuperacao  NUMERIC(15,2),
  perfil_cluster              TEXT,
  cluster_id                  INTEGER,
  renda_estimada              NUMERIC(15,2),
  status                      TEXT,
  dados_incompletos           BOOLEAN DEFAULT FALSE,
  aviso_dados                 TEXT DEFAULT '',
  taxa_recuperacao_prevista   NUMERIC(5,4)
);

ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS renda_estimada            NUMERIC(15,2);
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS status                    TEXT;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS dados_incompletos         BOOLEAN DEFAULT FALSE;
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS aviso_dados               TEXT DEFAULT '';
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS taxa_recuperacao_prevista NUMERIC(5,4);

-- Separa as duas grandezas que o sistema tratava como uma só:
--   probabilidade_pagamento  P(o devedor paga alguma coisa) — do classificador
--   taxa_recuperacao_prevista  taxa esperada sobre o saldo (1 − LGD)
-- origem_taxa registra se a taxa veio do price model ('modelo') ou da premissa
-- declarada da empresa ('premissa'), para a interface dizer em que ela se apoia.
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS probabilidade_pagamento   NUMERIC(5,4);
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS origem_taxa               TEXT DEFAULT '';

-- Perda esperada no vocabulário de Basileia. Numa carteira já inadimplente o
-- default aconteceu, então não há PD a prever: EAD é o próprio saldo devedor,
-- LGD é 1 menos a taxa de recuperação, e EL = EAD × LGD.
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS perda_esperada            NUMERIC(15,2);
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS lgd                       NUMERIC(5,4);
-- Despesas fixas mensais do devedor: insumo da margem livre. Sem elas o
-- motor de renegociação não consegue testar se a parcela cabe no bolso.
ALTER TABLE predicoes ADD COLUMN IF NOT EXISTS despesas_mensais          NUMERIC(15,2);

-- ── Feedbacks ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedbacks (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  cpf              TEXT NOT NULL,
  pagou            BOOLEAN NOT NULL,
  valor_recuperado NUMERIC(15,2) DEFAULT 0,
  data_pagamento   DATE,
  empresa          TEXT,
  predicao_id      UUID REFERENCES predicoes(id),
  registrado_por   TEXT
);

ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS registrado_por TEXT;

-- ── Usuários ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
  id          TEXT PRIMARY KEY,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  email       TEXT UNIQUE NOT NULL,
  nome        TEXT NOT NULL,
  senha_hash  TEXT NOT NULL,
  role        TEXT NOT NULL DEFAULT 'operador',
  ativo       BOOLEAN NOT NULL DEFAULT true,
  empresa_id  TEXT DEFAULT ''
);

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa_id TEXT DEFAULT '';

-- ── Conexões com bancos externos ─────────────────────────────
CREATE TABLE IF NOT EXISTS conexoes_db (
  id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  usuario_id            TEXT NOT NULL,
  empresa_id            TEXT DEFAULT '',
  nome                  TEXT NOT NULL,
  tipo                  TEXT NOT NULL DEFAULT 'postgres',
  host                  TEXT,
  porta                 INTEGER,
  banco                 TEXT,
  usuario               TEXT,
  senha                 TEXT,
  instance_name         TEXT,
  service_name          TEXT,
  sheets_id             TEXT,
  sheets_aba            TEXT,
  query                 TEXT,
  mapeamento            JSONB,
  ultimo_sync           TIMESTAMPTZ,
  ultimo_sync_por       TEXT,
  carteira_id           UUID,
  intervalo_sync_horas  NUMERIC DEFAULT 1,
  writeback_habilitado  BOOLEAN DEFAULT FALSE,
  coluna_writeback      TEXT,
  valor_pago            TEXT DEFAULT 'pago',
  valor_nao_pago        TEXT
);

ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS instance_name        TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS service_name         TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_id            TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS sheets_aba           TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS mapeamento           JSONB;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS ultimo_sync          TIMESTAMPTZ;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS ultimo_sync_por      TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS empresa_id           TEXT DEFAULT '';
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS carteira_id          UUID;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS intervalo_sync_horas NUMERIC DEFAULT 1;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS writeback_habilitado BOOLEAN DEFAULT FALSE;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS coluna_writeback     TEXT;
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS valor_pago           TEXT DEFAULT 'pago';
ALTER TABLE conexoes_db ADD COLUMN IF NOT EXISTS valor_nao_pago       TEXT;

-- ── Contatos (histórico de abordagem por devedor) ─────────────
CREATE TABLE IF NOT EXISTS contatos (
  id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  cpf                     TEXT NOT NULL,
  canal                   TEXT NOT NULL,
  resultado               TEXT NOT NULL,
  data_contato            DATE,
  observacao              TEXT,
  valor_recuperado        NUMERIC(15,2),
  desconto_oferecido_pct  NUMERIC(5,2),
  acao_bandit_id          INTEGER,
  usuario_id              TEXT,
  usuario_nome            TEXT,
  empresa_id              TEXT DEFAULT ''
);

-- ── Recomendações do bandit (log) ────────────────────────────
CREATE TABLE IF NOT EXISTS recomendacoes (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  cpf        TEXT NOT NULL,
  empresa_id TEXT DEFAULT '',
  acao_id    INTEGER,
  canal      TEXT,
  oferta     TEXT,
  score_ucb  NUMERIC(10,6),
  contexto   JSONB
);
-- O mesmo CPF pode dever a mais de um cliente. Sem empresa_id, o feedback de
-- um banco treinaria o bandit com a recomendação feita pelo outro.
ALTER TABLE recomendacoes ADD COLUMN IF NOT EXISTS empresa_id TEXT DEFAULT '';

-- ── Estado do bandit LinUCB ──────────────────────────────────
-- Uma linha por empresa: cada cliente aprende a própria política de cobrança
-- e o que um aprende nunca aparece nas recomendações do outro.
CREATE TABLE IF NOT EXISTS bandit_estado (
  id         BIGSERIAL PRIMARY KEY,
  empresa_id TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  estado     JSONB
);

-- Migração de bancos que já tinham o bandit global (uma linha só, id fixo em 1).
-- Idempotente: em base nova cada passo é no-op.
ALTER TABLE bandit_estado ADD COLUMN IF NOT EXISTS empresa_id TEXT;
UPDATE bandit_estado SET empresa_id = '_global'
 WHERE empresa_id IS NULL OR empresa_id = '';
ALTER TABLE bandit_estado ALTER COLUMN empresa_id SET NOT NULL;
-- o upsert do backend usa on_conflict="empresa_id" e precisa da restrição
CREATE UNIQUE INDEX IF NOT EXISTS bandit_estado_empresa_key ON bandit_estado (empresa_id);
-- o id era fixo em 1; com várias empresas tem de andar sozinho
CREATE SEQUENCE IF NOT EXISTS bandit_estado_id_seq OWNED BY bandit_estado.id;
SELECT setval('bandit_estado_id_seq',
              GREATEST(COALESCE((SELECT MAX(id) FROM bandit_estado), 0), 1));
ALTER TABLE bandit_estado ALTER COLUMN id SET DEFAULT nextval('bandit_estado_id_seq');

-- ── Auditoria ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auditoria (
  id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  acao           TEXT NOT NULL,
  entidade       TEXT,
  entidade_id    TEXT,
  usuario_id     TEXT,
  usuario_email  TEXT DEFAULT '',
  empresa_id     TEXT DEFAULT '',
  detalhes       JSONB
);

-- ── Tokens de redefinição de senha ───────────────────────────
CREATE TABLE IF NOT EXISTS reset_tokens (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  email      TEXT NOT NULL,
  token      TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  usado      BOOLEAN DEFAULT FALSE
);

-- ── API Keys (legado) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  empresa_nome TEXT NOT NULL UNIQUE,
  api_key      TEXT NOT NULL UNIQUE,
  ativa        BOOLEAN DEFAULT TRUE
);

-- ── Configuração / branding por empresa ─────────────────────
CREATE TABLE IF NOT EXISTS empresa_config (
  id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  empresa_id     TEXT UNIQUE NOT NULL,
  nome_exibicao  TEXT,
  foto_url       TEXT,
  cor_primaria   TEXT DEFAULT '#2563eb',
  extra          JSONB DEFAULT '{}'::jsonb,
  updated_by     TEXT,
  updated_at     TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE empresa_config ADD COLUMN IF NOT EXISTS extra JSONB DEFAULT '{}'::jsonb;
ALTER TABLE empresa_config ENABLE ROW LEVEL SECURITY;

-- ── Índices ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_predicoes_cpf        ON predicoes(cpf);
CREATE INDEX IF NOT EXISTS idx_predicoes_carteira   ON predicoes(carteira_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_cpf        ON feedbacks(cpf);
CREATE INDEX IF NOT EXISTS idx_feedbacks_predicao   ON feedbacks(predicao_id);
CREATE INDEX IF NOT EXISTS idx_carteiras_empresa    ON carteiras(empresa_id);
CREATE INDEX IF NOT EXISTS idx_contatos_cpf         ON contatos(cpf);
CREATE INDEX IF NOT EXISTS idx_contatos_empresa     ON contatos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_recomendacoes_cpf    ON recomendacoes(cpf);
CREATE INDEX IF NOT EXISTS idx_recomendacoes_emp    ON recomendacoes(empresa_id, cpf);
CREATE INDEX IF NOT EXISTS idx_auditoria_empresa    ON auditoria(empresa_id);
CREATE INDEX IF NOT EXISTS idx_conexoes_usuario     ON conexoes_db(usuario_id);
CREATE INDEX IF NOT EXISTS idx_conexoes_empresa     ON conexoes_db(empresa_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_email       ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_token   ON reset_tokens(token);

-- ── RLS habilitado em todas as tabelas ───────────────────────
-- Estas tabelas guardam CPF, dívida, renda, credenciais e a trilha de
-- auditoria. O backend fala com o banco usando a service role key, que
-- ignora RLS por definição, então ligar RLS não afeta a aplicação.
--
-- O que RLS protege é o outro caminho: a anon key é pública por natureza
-- (vai para o navegador em qualquer front que use Supabase) e o papel
-- `anon` tem as permissões padrão de SELECT/INSERT nestas tabelas. Sem
-- RLS, quem tiver a anon key lê e escreve na base inteira pelo PostgREST.
-- Com RLS ligado e nenhuma política permissiva, tudo é negado.
--
-- Conferido em 20/09/2026 no banco de produção: RLS ligado nas 12 tabelas,
-- zero políticas em pg_policies, e uma consulta com a anon key devolve 200
-- com lista vazia.
--
-- Este arquivo já mandou DISABLE nestas linhas. Rodá-lo de novo desligaria
-- a proteção nas doze tabelas de uma vez. Se algum dia for preciso expor
-- alguma tabela ao `anon`, crie uma política específica em vez de desligar
-- o RLS.
ALTER TABLE carteiras     ENABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes     ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios      ENABLE ROW LEVEL SECURITY;
ALTER TABLE conexoes_db   ENABLE ROW LEVEL SECURITY;
ALTER TABLE contatos      ENABLE ROW LEVEL SECURITY;
ALTER TABLE recomendacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE bandit_estado ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria     ENABLE ROW LEVEL SECURITY;
ALTER TABLE reset_tokens  ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys      ENABLE ROW LEVEL SECURITY;
