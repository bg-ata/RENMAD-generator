-- RENMAD Agenda — storage in the RENMAD Dispatch Center's Supabase (dxgvbufsifgowwfggvmr).
-- Applied 19 Oct 2026 via the Supabase MCP (migrations dc_agendas_table + dc_agendas_stamp).
-- Kept here as the record of the schema; re-running it is safe.
-- Before that date agendas lived in a separate free project (timedagenda), whose table
-- anyone could read with the public key. Here only signed-in Dispatch roster members get in.

create table if not exists public.dc_agendas (
  id          uuid primary key default gen_random_uuid(),
  title       text,
  data        jsonb not null,            -- the whole agenda (same shape the app uses)
  updated_at  timestamptz not null default now(),
  updated_by  text,                      -- stamped by dc_stamp() from the signed-in user
  locked_by   text,
  locked_at   timestamptz
);
alter table public.dc_agendas enable row level security;
revoke all on public.dc_agendas from anon;
grant select, insert, update, delete on public.dc_agendas to authenticated;

drop policy if exists dc_agendas_sel on public.dc_agendas;
drop policy if exists dc_agendas_ins on public.dc_agendas;
drop policy if exists dc_agendas_upd on public.dc_agendas;
drop policy if exists dc_agendas_del on public.dc_agendas;
create policy dc_agendas_sel on public.dc_agendas for select to authenticated using ((select dc_access()) is not null);
create policy dc_agendas_ins on public.dc_agendas for insert to authenticated with check ((select dc_access()) is not null);
create policy dc_agendas_upd on public.dc_agendas for update to authenticated using ((select dc_access()) is not null) with check ((select dc_access()) is not null);
create policy dc_agendas_del on public.dc_agendas for delete to authenticated using ((select dc_access()) is not null);

drop trigger if exists dc_agendas_stamp on public.dc_agendas;
create trigger dc_agendas_stamp before insert or update on public.dc_agendas
  for each row execute function public.dc_stamp();

do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename='dc_agendas') then
    alter publication supabase_realtime add table public.dc_agendas;
  end if;
end $$;
