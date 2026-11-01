-- Em PostgreSQL temporário com a migração aplicada. ON_ERROR_STOP=1.
do $$
declare r jsonb; id1 uuid; id2 uuid; n int;
begin
 r := cientista_criar('teste-a','retreino_score','base1','{"coorte":{"sha256":"abc"}}','admin');
 id1 := (r->>'id')::uuid;
 if cientista_criar('teste-a','retreino_score','base1','{}','outro')->>'id' <> id1::text then raise exception 'não idempotente'; end if;
 if cientista_transicao('teste-b',id1,'proposta','aprovada','{}','intruso','teste') is not null then raise exception 'vazamento entre empresas'; end if;
 perform cientista_transicao('teste-a',id1,'proposta','aprovada','{}','admin','aprovou');
 if cientista_transicao('teste-a',id1,'proposta','recusada','{}','admin2','atrasado') is not null then raise exception 'CAS falhou'; end if;
 select count(*) into n from cientista_eventos where acao_id=id1;
 if n <> 2 then raise exception 'histórico incompleto ou duplicado: %', n; end if;
 begin
  update cientista_eventos set motivo='adulterado' where acao_id=id1;
  raise exception using errcode='ZX001',message='histórico mutável';
 exception when raise_exception then null;
 end;
 begin
  perform cientista_transicao('teste-a',id1,'aprovada','concluida','{}','admin','pular execução');
  raise exception using errcode='ZX001',message='pulo indevido';
 exception when raise_exception then null;
 end;
 r:=cientista_criar('teste-a','experimento_bandit','exp1','{}','admin'); id1:=(r->>'id')::uuid;
 perform cientista_transicao('teste-a',id1,'proposta','aprovada','{}','admin','aprovou');
 perform cientista_transicao('teste-a',id1,'aprovada','executando','{}','admin','iniciou');
 r:=cientista_criar('teste-a','experimento_bandit','exp2','{}','admin'); id2:=(r->>'id')::uuid;
 perform cientista_transicao('teste-a',id2,'proposta','aprovada','{}','admin','aprovou');
 begin
  perform cientista_transicao('teste-a',id2,'aprovada','executando','{}','admin','iniciou');
  raise exception using errcode='ZX001',message='dois experimentos ativos';
 exception when unique_violation then null;
 end;
 if (select status from cientista_acoes where id=id2)<>'aprovada' then raise exception 'efeito parcial'; end if;
end $$;
set role authenticated;
do $$
begin
 begin
  perform cientista_criar('teste-a','coleta_dados','ataque','{}','admin');
  raise exception using errcode='ZX001',message='RPC pública';
 exception when insufficient_privilege then null;
 end;
 begin
  perform * from cientista_eventos;
  raise exception using errcode='ZX001',message='leitura pública';
 exception when insufficient_privilege then null;
 end;
end $$;
reset role;
select 'auditoria, idempotência, isolamento, CAS, exclusão de experimentos e permissões: OK' as resultado;
do $$
declare r jsonb;
begin
 r:=cientista_criar('teste-base','retreino_score','hash','{"coorte":{"sha256":"sha"},"_snapshot_cifrado":"cifrado"}','admin');
 if r->'dados' ? '_snapshot_cifrado' then raise exception 'base vazou no relatório'; end if;
 if not exists(select 1 from cientista_bases where empresa_id='teste-base' and sha256='sha' and conteudo_cifrado='cifrado') then raise exception 'base não persistida'; end if;
 begin
  update cientista_bases set conteudo_cifrado='mudou' where empresa_id='teste-base';
  raise exception using errcode='ZX001',message='base mutável';
 exception when raise_exception then null;
 end;
end $$;
