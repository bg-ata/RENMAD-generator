-- RENMAD Agenda — cloud storage setup
-- Run this ONCE in your Supabase project: Dashboard → SQL Editor → New query → paste → Run.
-- It creates the single shared table for all agendas and locks it so ONLY logged-in
-- @ata.email users (via the app) can read or write. Nobody else can see the data,
-- even if they somehow reach the database.

create table if not exists public.agendas (
  id          uuid primary key default gen_random_uuid(),
  title       text,
  data        jsonb not null,            -- the whole agenda (same shape the app already uses)
  updated_at  timestamptz not null default now(),
  updated_by  text,                      -- email of the last editor (for the "last edited by" stamp)
  locked_by   text,                      -- email of who currently has it open (turn-taking)
  locked_at   timestamptz
);

alter table public.agendas enable row level security;

-- Helper: is the caller a signed-in ATA team member?
create or replace function public.is_ata() returns boolean
language sql stable as $$
  select coalesce(auth.jwt() ->> 'email', '') like '%@ata.email'
$$;

-- Only ATA team members can read / create / edit / delete agendas.
drop policy if exists ata_select on public.agendas;
drop policy if exists ata_insert on public.agendas;
drop policy if exists ata_update on public.agendas;
drop policy if exists ata_delete on public.agendas;

create policy ata_select on public.agendas for select using ( public.is_ata() );
create policy ata_insert on public.agendas for insert with check ( public.is_ata() );
create policy ata_update on public.agendas for update using ( public.is_ata() ) with check ( public.is_ata() );
create policy ata_delete on public.agendas for delete using ( public.is_ata() );

-- Let the app receive live updates so teammates see each other's changes.
alter publication supabase_realtime add table public.agendas;
