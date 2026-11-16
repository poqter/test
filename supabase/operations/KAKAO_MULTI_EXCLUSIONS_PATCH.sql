-- REVIEW PATCH: remove identity literals; preserve legacy-owner exclusion in private service data.
begin;
create table public.kakao_multi_exclusions (
 owner_id uuid primary key references public.profiles(id),
 reason text not null default 'legacy_personal' check(reason='legacy_personal'),
 created_at timestamptz not null default now()
);
alter table public.kakao_multi_exclusions enable row level security;
revoke all on public.kakao_multi_exclusions from public,anon,authenticated;
grant select,insert,update,delete on public.kakao_multi_exclusions to service_role;
-- Copy only owner references, never credentials; retain exclusion if legacy connection later revokes.
do $$ begin
 if to_regclass('public.dot_kakao_connections') is not null then
  execute 'insert into public.kakao_multi_exclusions(owner_id) select distinct owner_id from public.dot_kakao_connections where status in (''approved'',''pending_owner_confirmation'') on conflict(owner_id) do nothing';
 end if;
end $$;
create function private.kakao_service_excluded_owner(p_owner uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_exclusions where owner_id=p_owner)
$$;
-- Identify only the old single-column owner exclusion CHECK, without embedding any owner identifier.
do $$ declare c record; owner_att smallint; begin
 select attnum into owner_att from pg_attribute where attrelid='public.kakao_multi_connections'::regclass and attname='owner_id' and not attisdropped;
 for c in select conname from pg_constraint where conrelid='public.kakao_multi_connections'::regclass and contype='c'
 and conkey=array[owner_att]::smallint[] and pg_get_constraintdef(oid) like 'CHECK ((owner_id <> %' and position('::uuid' in pg_get_constraintdef(oid))>0 loop
  execute format('alter table public.kakao_multi_connections drop constraint %I',c.conname);
 end loop;
end $$;
create or replace function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 -- Authenticated owner's abandoned confirmation expires even when delivery gate is OFF.
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
 confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
 where owner_id=u and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 if found then update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=u; end if;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where owner_id=u and expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 select jsonb_build_object('dispatch_ready',coalesce((private.kakao_service_gate()->>'enabled')::boolean,false),'connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'weather_region_key',p.weather_region_key,'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where owner_id=u order by claimed_at desc nulls last,id desc limit 1) j on true;
 return result;
end $$;

create or replace function private.kakao_service_owner_active(p_owner uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.profiles p join public.hwarang_app_access a on a.user_id=p.id
 where p.id=p_owner and p.is_active and a.app_code='workspace' and a.is_enabled
 and not private.kakao_service_excluded_owner(p.id)
 and exists(select 1 from public.get_hwarang_effective_permissions(p.id) ep where ep.permission_code='workspace.sales_activity'))
$$;

create or replace function private.kakao_save_preferences(p_enabled boolean,p_time text,p_days integer[],p_send_empty boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); c public.kakao_multi_connections;
begin
 if p_enabled is null or p_send_empty is null or p_time is null or p_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
 or p_days is null or cardinality(p_days) not between 1 and 7 or not p_days <@ array[0,1,2,3,4,5,6] or array_position(p_days,null) is not null then raise exception 'Invalid preferences'; end if;
 select * into c from public.kakao_multi_connections where owner_id=u for update;
 if not found then raise exception 'Connect first'; end if;
 if p_enabled and (private.kakao_service_excluded_owner(u) or c.status<>'connected' or not c.talk_message_granted) then raise exception 'Reconnect required'; end if;
 if p_enabled and not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=u and private.kakao_weather_region_valid(p.weather_region_key)) then raise exception 'Select weather region first'; end if;
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,send_empty)
 values(u,p_enabled,p_time::time,array(select distinct d from unnest(p_days) d order by d),p_send_empty)
 on conflict(owner_id) do update set enabled=excluded.enabled,delivery_time=excluded.delivery_time,days=excluded.days,send_empty=excluded.send_empty,updated_at=now();
 if not p_enabled then
  update public.kakao_multi_jobs set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status in ('reserved','held');
 end if;
 return private.kakao_my_status();
end $$;

create or replace function private.kakao_confirm_connection(p_receipt_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 if p_receipt_hash is null or p_receipt_hash !~ '^[a-f0-9]{64}$' then raise exception 'Invalid confirmation'; end if;
 update public.kakao_multi_connections set status='connected',confirmation_hash=null,confirmation_expires_at=null,updated_at=now()
 where owner_id=u and status='pending_confirmation' and confirmation_hash=p_receipt_hash and confirmation_expires_at>now() and talk_message_granted and not private.kakao_service_excluded_owner(u) and not private.kakao_service_legacy_conflict(account_id);
 if not found then raise exception 'Invalid confirmation'; end if;
 return private.kakao_my_status();
end $$;
revoke all on function private.kakao_service_excluded_owner(uuid) from public,anon,authenticated;
grant execute on function private.kakao_service_excluded_owner(uuid) to service_role;
commit;
