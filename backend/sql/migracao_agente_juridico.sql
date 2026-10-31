-- Base jurídica interna do orquestrador (docs/RAG_JURIDICO.md).
--
-- Duas tabelas, só para o backend (RLS ligado e nenhuma política: a chave anon não lê
-- nem grava; o backend usa a service role). Nenhum dado pessoal em claro: os fatos
-- considerados ficam cifrados com a chave Fernet da Mizan (MIZAN_ENCRYPTION_KEY).
--
-- Rode uma vez no SQL Editor do Supabase. Sem estas tabelas o sistema continua
-- decidindo igual; só não guarda o registro (e avisa no log).

create table if not exists agente_consultas_juridicas (
  id               uuid primary key default gen_random_uuid(),
  empresa_id       text not null,
  caso_id          text,
  trace_id         text,
  acao             text not null,
  decisao          text not null check (decisao in ('prosseguir', 'prosseguir_com_condicoes',
                                                    'nao_prosseguir', 'revisao_humana')),
  condicoes        jsonb not null default '[]',
  justificativa    text,
  dispositivos     jsonb not null default '[]',
  fontes           jsonb not null default '[]',
  incertezas       jsonb not null default '[]',
  indice_versao    text,
  consultado_em    timestamptz,
  contexto_cifrado text,
  criado_em        timestamptz not null default now()
);
create index if not exists idx_consultas_juridicas_empresa on agente_consultas_juridicas (empresa_id, criado_em desc);
create index if not exists idx_consultas_juridicas_caso on agente_consultas_juridicas (caso_id, criado_em desc);
alter table agente_consultas_juridicas enable row level security;

-- Conferência da redação na fonte oficial, feita pelo servidor (POST /agente/juridico/conferir).
create table if not exists agente_conferencias_juridicas (
  norma_id      text primary key,
  status        text not null check (status in ('conferida', 'divergente', 'nao_conferida')),
  conferido_em  timestamptz,
  resultado     jsonb not null,
  atualizado_em timestamptz not null default now()
);
alter table agente_conferencias_juridicas enable row level security;
