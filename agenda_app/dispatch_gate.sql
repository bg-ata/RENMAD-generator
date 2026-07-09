-- RENMAD Agenda — switch from the shared-passcode login to the Dispatch Center gate.
-- Run this ONCE in the AGENDA Supabase project (abxsnwmjbcnhjhzydqii — NOT the
-- Dispatch project): Dashboard → SQL Editor → New query → paste → Run.
--
-- Before: only a signed-in @ata.email session (the shared passcode account) could
-- read/write agendas. Now the app validates the Dispatch Center login instead, so
-- the browser talks to this database with the publishable (anon) key. These policies
-- let that key read/write agendas. Access control now lives in the app's Dispatch
-- gate; this database trusts requests that reach it through the app.
-- Idempotent — safe to re-run.

alter table public.agendas enable row level security;

drop policy if exists ata_select on public.agendas;
drop policy if exists ata_insert on public.agendas;
drop policy if exists ata_update on public.agendas;
drop policy if exists ata_delete on public.agendas;

drop policy if exists dc_select on public.agendas;
drop policy if exists dc_insert on public.agendas;
drop policy if exists dc_update on public.agendas;
drop policy if exists dc_delete on public.agendas;

create policy dc_select on public.agendas for select to anon, authenticated using ( true );
create policy dc_insert on public.agendas for insert to anon, authenticated with check ( true );
create policy dc_update on public.agendas for update to anon, authenticated using ( true ) with check ( true );
create policy dc_delete on public.agendas for delete to anon, authenticated using ( true );
