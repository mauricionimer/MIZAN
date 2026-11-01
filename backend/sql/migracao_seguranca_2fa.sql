-- Verificação em duas etapas (2FA) e limite de login que sobrevive a reinícios.
-- docs/SEGURANCA_2FA.md. Rode uma vez no SQL Editor do Supabase.
--
-- Antes desta migração o sistema funciona como antes (ninguém é obrigado ao 2FA).
-- Depois dela, admin e comando passam a configurar o 2FA no próximo acesso.

-- 1. 2FA no cadastro. O segredo fica cifrado com a chave Fernet da Mizan
--    (MIZAN_ENCRYPTION_KEY); os códigos de recuperação, só como hash com sal.
alter table usuarios add column if not exists totp_ativo        boolean not null default false;
alter table usuarios add column if not exists totp_segredo      text;
alter table usuarios add column if not exists totp_pendente     text;
alter table usuarios add column if not exists totp_pendente_em  timestamptz;
alter table usuarios add column if not exists totp_ativado_em   timestamptz;
alter table usuarios add column if not exists totp_ultimo_passo bigint;
alter table usuarios add column if not exists totp_recuperacao  jsonb;

-- 2. Tentativas de login e de código erradas: uma linha por erro, chave em HMAC
--    (sem e-mail nem IP em texto). Só o backend acessa (RLS ligado, sem política).
create table if not exists login_tentativas (
  id        bigint generated always as identity primary key,
  chave     text        not null,
  criado_em timestamptz not null default now()
);
create index if not exists idx_login_tentativas_chave  on login_tentativas (chave, criado_em desc);
create index if not exists idx_login_tentativas_criado on login_tentativas (criado_em);
alter table login_tentativas enable row level security;

-- A tabela antiga (rate_limit_login, com e-mail em texto) deixa de ser usada.
-- Depois de conferir que o login funciona, pode apagá-la:
-- drop table if exists rate_limit_login;
