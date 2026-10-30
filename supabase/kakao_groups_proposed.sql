create table public.hwarang_kakao_groups (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 80),
  recipients jsonb not null default '[]'::jsonb check (jsonb_typeof(recipients) = 'array' and jsonb_array_length(recipients) <= 200),
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner_id, name)
);
create index hwarang_kakao_groups_owner_idx on public.hwarang_kakao_groups(owner_id, updated_at desc);
alter table public.hwarang_kakao_groups enable row level security;
revoke all on public.hwarang_kakao_groups from anon, authenticated;
grant select, insert, update, delete on public.hwarang_kakao_groups to authenticated;
create policy hwarang_kakao_groups_select on public.hwarang_kakao_groups for select to authenticated using ((select auth.uid()) = owner_id);
create policy hwarang_kakao_groups_insert on public.hwarang_kakao_groups for insert to authenticated with check ((select auth.uid()) = owner_id);
create policy hwarang_kakao_groups_update on public.hwarang_kakao_groups for update to authenticated using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);
create policy hwarang_kakao_groups_delete on public.hwarang_kakao_groups for delete to authenticated using ((select auth.uid()) = owner_id);
create function public.hwarang_kakao_group_touch() returns trigger language plpgsql set search_path = '' as $$
begin new.version := old.version + 1; new.updated_at := now(); return new; end $$;
create trigger hwarang_kakao_groups_touch before update on public.hwarang_kakao_groups for each row execute function public.hwarang_kakao_group_touch();
create table public.hwarang_kakao_template (
  id text primary key check (id = 'briefing-v1'),
  file_bytes bytea not null,
  updated_at timestamptz not null default now()
);
alter table public.hwarang_kakao_template enable row level security;
revoke all on public.hwarang_kakao_template from anon, authenticated;
grant select on public.hwarang_kakao_template to service_role;
