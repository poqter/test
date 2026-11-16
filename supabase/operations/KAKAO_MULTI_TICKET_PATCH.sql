-- One-use tick credentials: no persistent credential enters pg_net request headers/body.
begin;
create table public.kakao_multi_tick_tickets (
 ticket_hash text primary key check(ticket_hash ~ '^[a-f0-9]{64}$'),
 expires_at timestamptz not null, used_at timestamptz,
 created_at timestamptz not null default clock_timestamp()
);
alter table public.kakao_multi_tick_tickets enable row level security;
revoke all on public.kakao_multi_tick_tickets from public,anon,authenticated;
grant select,insert,update,delete on public.kakao_multi_tick_tickets to service_role;
create function private.kakao_service_consume_tick(p_ticket_hash text) returns boolean
language plpgsql security definer set search_path='' as $$
begin
 if p_ticket_hash is null or p_ticket_hash !~ '^[a-f0-9]{64}$' then return false; end if;
 update public.kakao_multi_tick_tickets set used_at=clock_timestamp()
 where ticket_hash=p_ticket_hash and used_at is null and expires_at>clock_timestamp();
 return found;
end $$;
create function public.kakao_service_consume_tick(p_ticket_hash text) returns boolean
language sql security invoker set search_path='' as $$ select private.kakao_service_consume_tick(p_ticket_hash) $$;
revoke all on function private.kakao_service_consume_tick(text),public.kakao_service_consume_tick(text) from public,anon,authenticated;
grant execute on function private.kakao_service_consume_tick(text),public.kakao_service_consume_tick(text) to service_role;
commit;
