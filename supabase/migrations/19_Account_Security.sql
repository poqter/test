-- Apply once after 18. No account/password is reset by this migration.
begin;
create table if not exists public.hwarang_account_security (
 user_id uuid primary key references auth.users(id) on delete cascade,
 credentials_changed_at timestamptz not null
);
alter table public.hwarang_account_security enable row level security;
revoke all on public.hwarang_account_security from public, anon, authenticated;
grant select,insert,update,delete on public.hwarang_account_security to service_role;
create table if not exists public.hwarang_account_recovery_audit (
 id uuid primary key default gen_random_uuid(),
 actor_id uuid not null references public.profiles(id),
 target_id uuid not null references public.profiles(id),
 verification_method text not null check (verification_method in ('기존 등록 연락처로 통화','대면 확인','소속 책임자 확인')),
 created_at timestamptz not null default now()
);
alter table public.hwarang_account_recovery_audit enable row level security;
revoke all on public.hwarang_account_recovery_audit from public,anon,authenticated;
grant select,insert on public.hwarang_account_recovery_audit to service_role;
create or replace function private.hwarang_credentials_changed()
returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.encrypted_password is distinct from old.encrypted_password
    or new.email is distinct from old.email then
  insert into public.hwarang_account_security(user_id,credentials_changed_at)
  values(new.id,clock_timestamp()) on conflict(user_id) do update
   set credentials_changed_at=excluded.credentials_changed_at;
  delete from public.hwarang_app_launch_tickets where user_id=new.id;
 end if;
 if new.email is distinct from old.email then
  update public.profiles set auth_email=new.email where id=new.id;
 end if;
 return new;
end $$;
revoke all on function private.hwarang_credentials_changed() from public,anon,authenticated;
drop trigger if exists hwarang_credentials_changed on auth.users;
create trigger hwarang_credentials_changed after update of encrypted_password,email on auth.users
for each row execute function private.hwarang_credentials_changed();
commit;
