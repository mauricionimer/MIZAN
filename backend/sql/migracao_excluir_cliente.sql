-- Excluir um cliente (empresa) e TODOS os dados dele, de uma vez, numa única transação:
-- ou apaga tudo, ou não apaga nada. Usada pelo painel COMANDO (docs/EXCLUIR_CLIENTE.md).
-- Rode uma vez no SQL Editor do Supabase. Antes de rodar, nada muda.
--
-- O que apaga: carteiras, devedores (previsões) e feedbacks, conexões e permissões, chaves de
-- API, agenda, acordos, ofertas, contatos, roteiros, configuração, política e conversas dos
-- agentes (casos, mensagens, eventos, passos, logs, consultas jurídicas), o Cientista (ações,
-- eventos, exposições, resultados), recomendações, bandit e os usuários da empresa.
-- O que fica: a trilha de auditoria (sem o e-mail, que é dado pessoal) e o COMANDO: a função
-- recusa a empresa que tenha usuário COMANDO.

-- 1. O histórico do Cientista é só de acréscimo: apagar só passa dentro desta função
--    (que liga o aviso mizan.exclusao_cliente), nunca por uma chamada comum à API.
create or replace function public.cientista_evento_imutavel() returns trigger language plpgsql
set search_path = '' as $$
begin
  if tg_op = 'DELETE' and pg_catalog.current_setting('mizan.exclusao_cliente', true) = 'on' then
    return old;
  end if;
  raise exception 'Histórico do Cientista é somente acréscimo';
end $$;

-- 2. A função. Só o backend (service_role) executa; anon e authenticated, não.
create or replace function public.excluir_dados_cliente(p_empresa text)
returns jsonb
language plpgsql
security definer
set search_path = ''
set statement_timeout = '120s'
as $$
declare
  v_resumo jsonb := '{}'::jsonb;
  v_n      bigint;
  v_t      text;
  v_emails text[];
  -- Filhas antes das mães (chaves estrangeiras). Só entram as que existem e têm empresa_id.
  v_tabelas text[] := array[
    'agente_logs', 'agente_contestacoes', 'agente_mensagens', 'agente_eventos', 'agente_passos',
    'agente_consultas_juridicas', 'agente_recomendacoes', 'agente_politicas', 'agente_casos',
    'cientista_resultados', 'cientista_exposicoes', 'cientista_eventos', 'cientista_acoes',
    'cientista_bases', 'acordo_parcelas', 'agenda', 'contatos', 'ofertas_feitas',
    'disponibilidade_operador', 'duvidas', 'roteiros', 'travas', 'recomendacoes', 'bandit_estado',
    'api_keys', 'feedbacks', 'predicoes', 'carteiras', 'conexoes_db', 'empresa_config'];
begin
  if p_empresa is null or pg_catalog.btrim(p_empresa) = '' then
    raise exception 'Empresa vazia.';
  end if;
  if exists (select 1 from public.usuarios u where u.empresa_id = p_empresa and u.role = 'comando') then
    raise exception 'A empresa tem usuário COMANDO: tire-o da empresa antes.';
  end if;
  perform pg_catalog.set_config('mizan.exclusao_cliente', 'on', true);   -- vale só nesta transação

  -- Tabelas que se ligam à empresa por outra chave (devedores pela carteira; permissões pela conexão).
  if pg_catalog.to_regclass('public.feedbacks') is not null and pg_catalog.to_regclass('public.predicoes') is not null
     and pg_catalog.to_regclass('public.carteiras') is not null then
    delete from public.feedbacks f where f.predicao_id in (
      select p.id from public.predicoes p where p.carteira_id in (
        select c.id from public.carteiras c where c.empresa_id = p_empresa));
    get diagnostics v_n = row_count;
    if v_n > 0 then v_resumo := v_resumo || pg_catalog.jsonb_build_object('feedbacks', v_n); end if;
    delete from public.predicoes p where p.carteira_id in (
      select c.id from public.carteiras c where c.empresa_id = p_empresa);
    get diagnostics v_n = row_count;
    if v_n > 0 then v_resumo := v_resumo || pg_catalog.jsonb_build_object('predicoes', v_n); end if;
  end if;
  if pg_catalog.to_regclass('public.conexao_permissoes') is not null and pg_catalog.to_regclass('public.conexoes_db') is not null then
    delete from public.conexao_permissoes cp where cp.conexao_id::text in (
      select c.id::text from public.conexoes_db c where c.empresa_id = p_empresa);
    get diagnostics v_n = row_count;
    if v_n > 0 then v_resumo := v_resumo || pg_catalog.jsonb_build_object('conexao_permissoes', v_n); end if;
  end if;

  -- Tabelas com empresa_id.
  foreach v_t in array v_tabelas loop
    if pg_catalog.to_regclass('public.' || v_t) is not null
       and exists (select 1 from information_schema.columns k
                   where k.table_schema = 'public' and k.table_name = v_t and k.column_name = 'empresa_id') then
      execute pg_catalog.format('delete from public.%I where empresa_id = $1', v_t) using p_empresa;
      get diagnostics v_n = row_count;
      if v_n > 0 then
        v_resumo := v_resumo || pg_catalog.jsonb_build_object(v_t, coalesce((v_resumo ->> v_t)::bigint, 0) + v_n);
      end if;
    end if;
  end loop;

  -- Usuários da empresa (e os links de redefinição de senha deles). A auditoria fica, sem o e-mail.
  select pg_catalog.array_agg(u.email) into v_emails
    from public.usuarios u where u.empresa_id = p_empresa and u.role <> 'comando';
  if pg_catalog.to_regclass('public.reset_tokens') is not null and v_emails is not null then
    delete from public.reset_tokens r where r.email = any (v_emails);
  end if;
  if pg_catalog.to_regclass('public.auditoria') is not null then
    update public.auditoria a set usuario_email = '' where a.empresa_id = p_empresa;
  end if;
  delete from public.usuarios u where u.empresa_id = p_empresa and u.role <> 'comando';
  get diagnostics v_n = row_count;
  if v_n > 0 then v_resumo := v_resumo || pg_catalog.jsonb_build_object('usuarios', v_n); end if;

  return v_resumo;
end $$;

revoke all on function public.excluir_dados_cliente(text) from public;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on function public.excluir_dados_cliente(text) from anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    revoke all on function public.excluir_dados_cliente(text) from authenticated;
  end if;
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function public.excluir_dados_cliente(text) to service_role;
  end if;
end $$;
