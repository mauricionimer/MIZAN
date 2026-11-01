-- Estado + histórico na mesma transação. Aplicar antes de habilitar o Laboratório.
begin;
create table if not exists public.cientista_acoes (
 id uuid primary key default gen_random_uuid(), empresa_id text not null,
 tipo text not null check (tipo in ('coleta_dados','retreino_score','experimento_bandit')),
 chave text not null, status text not null default 'proposta', dados jsonb not null,
 criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
 unique(empresa_id,tipo,chave)
);
create unique index if not exists cientista_um_experimento on public.cientista_acoes(empresa_id)
 where tipo='experimento_bandit' and status in ('executando','em_observacao');
create table if not exists public.cientista_eventos (
 id bigint generated always as identity primary key, empresa_id text not null,
 acao_id uuid not null references public.cientista_acoes(id), ator text not null,
 evento text not null, motivo text not null, dados jsonb not null,
 criado_em timestamptz not null default now()
);
create index if not exists cientista_eventos_empresa on public.cientista_eventos(empresa_id,acao_id,id);
create or replace function public.cientista_evento_imutavel() returns trigger language plpgsql as $$
begin raise exception 'Histórico do Cientista é somente acréscimo'; end $$;
do $$ begin
 if not exists (select 1 from pg_trigger where tgrelid='public.cientista_eventos'::regclass and tgname='cientista_evento_imutavel') then
  create trigger cientista_evento_imutavel before update or delete on public.cientista_eventos
   for each row execute function public.cientista_evento_imutavel();
 end if;
end $$;
create table if not exists public.cientista_exposicoes (
 id uuid primary key default gen_random_uuid(), empresa_id text not null,
 experimento_id uuid not null references public.cientista_acoes(id), pessoa text not null,
 grupo text not null check(grupo in ('controle','tratamento')), acao_id int not null check(acao_id between 0 and 11),
 contexto jsonb not null, criado_em timestamptz not null default now(),
 unique(empresa_id,experimento_id,pessoa)
);
create table if not exists public.cientista_resultados (
 id uuid primary key default gen_random_uuid(), empresa_id text not null,
 exposicao_id uuid not null references public.cientista_exposicoes(id), chave text not null,
 dados jsonb not null, criado_em timestamptz not null default now(), unique(empresa_id,chave)
);
do $$ begin
 if not exists (select 1 from pg_trigger where tgrelid='public.cientista_exposicoes'::regclass and tgname='cientista_exposicao_imutavel') then
  create trigger cientista_exposicao_imutavel before update or delete on public.cientista_exposicoes
   for each row execute function public.cientista_evento_imutavel();
 end if;
 if not exists (select 1 from pg_trigger where tgrelid='public.cientista_resultados'::regclass and tgname='cientista_resultado_imutavel') then
  create trigger cientista_resultado_imutavel before update or delete on public.cientista_resultados
   for each row execute function public.cientista_evento_imutavel();
 end if;
end $$;
create index if not exists cientista_exposicoes_empresa on public.cientista_exposicoes(empresa_id,experimento_id);
create index if not exists cientista_resultados_empresa on public.cientista_resultados(empresa_id,exposicao_id);
alter table public.cientista_acoes enable row level security;
alter table public.cientista_eventos enable row level security;
alter table public.cientista_exposicoes enable row level security;
alter table public.cientista_resultados enable row level security;
revoke all on public.cientista_acoes, public.cientista_eventos, public.cientista_exposicoes, public.cientista_resultados from anon, authenticated;
grant all on public.cientista_acoes, public.cientista_eventos, public.cientista_exposicoes, public.cientista_resultados to service_role;
grant usage,select on sequence public.cientista_eventos_id_seq to service_role;
create table if not exists public.cientista_bases (
 empresa_id text not null, sha256 text not null, conteudo_cifrado text not null,
 criado_em timestamptz not null default now(), primary key(empresa_id,sha256)
);
alter table public.cientista_bases enable row level security;
revoke all on public.cientista_bases from anon, authenticated;
grant select,insert on public.cientista_bases to service_role;
do $$ begin
 if not exists (select 1 from pg_trigger where tgrelid='public.cientista_bases'::regclass and tgname='cientista_base_imutavel') then
  create trigger cientista_base_imutavel before update or delete on public.cientista_bases
   for each row execute function public.cientista_evento_imutavel();
 end if;
end $$;
create or replace function public.cientista_criar(p_empresa text,p_tipo text,p_chave text,p_dados jsonb,p_ator text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare r cientista_acoes;
begin
 if p_dados ? '_snapshot_cifrado' then
  insert into cientista_bases(empresa_id,sha256,conteudo_cifrado)
  values(p_empresa,p_dados->'coorte'->>'sha256',p_dados->>'_snapshot_cifrado')
  on conflict(empresa_id,sha256) do nothing;
 end if;
 p_dados := p_dados - '_snapshot_cifrado';
 insert into cientista_acoes(empresa_id,tipo,chave,dados) values(p_empresa,p_tipo,p_chave,p_dados)
 on conflict(empresa_id,tipo,chave) do nothing returning * into r;
 if r.id is null then
  select * into r from cientista_acoes where empresa_id=p_empresa and tipo=p_tipo and chave=p_chave;
 else
  insert into cientista_eventos(empresa_id,acao_id,ator,evento,motivo,dados)
  values(p_empresa,r.id,p_ator,'proposta','Avaliação determinística dos dados e dos critérios',to_jsonb(r));
 end if;
 return to_jsonb(r);
end $$;
create or replace function public.cientista_transicao(p_empresa text,p_id uuid,p_esperado text,p_status text,p_dados jsonb,p_ator text,p_motivo text)
returns jsonb language plpgsql security invoker set search_path=public as $$
declare r cientista_acoes;
begin
 if not ((p_esperado='proposta' and p_status in ('aprovada','recusada')) or
         (p_esperado in ('aprovada','erro') and p_status in ('executando','expirada')) or
         (p_esperado='executando' and p_status in ('concluida','em_observacao','erro')) or
         (p_esperado='em_observacao' and p_status in ('em_observacao','encerrada')) or
         (p_esperado='concluida' and p_status='concluida') or
         (p_esperado='encerrada' and p_status='encerrada')) then raise exception 'Transição inválida'; end if;
 update cientista_acoes set status=p_status,dados=dados||p_dados,atualizado_em=now()
 where id=p_id and empresa_id=p_empresa and status=p_esperado returning * into r;
 if r.id is null then return null; end if;
 insert into cientista_eventos(empresa_id,acao_id,ator,evento,motivo,dados)
 values(p_empresa,r.id,p_ator,p_status,p_motivo,to_jsonb(r));
 return to_jsonb(r);
end $$;
revoke all on function public.cientista_criar(text,text,text,jsonb,text) from public,anon,authenticated;
revoke all on function public.cientista_transicao(text,uuid,text,text,jsonb,text,text) from public,anon,authenticated;
grant execute on function public.cientista_criar(text,text,text,jsonb,text) to service_role;
grant execute on function public.cientista_transicao(text,uuid,text,text,jsonb,text,text) to service_role;
alter table public.recomendacoes add column if not exists experimento_id uuid;
alter table public.recomendacoes add column if not exists exposicao_id uuid;
commit;
