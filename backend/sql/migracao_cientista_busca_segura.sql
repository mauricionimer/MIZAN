-- Fixa o caminho de busca da função de auditoria; não altera registros.
begin;
alter function public.cientista_evento_imutavel() set search_path = '';
commit;
