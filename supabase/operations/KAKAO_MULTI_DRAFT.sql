-- REVIEW DRAFT ONLY. Not applied. No cron, no network call, no paid feature enabled.
-- Requires existing private.sales_enabled() and private.sales_scope_for(uuid,boolean).
-- Existing dot_kakao_* objects are deliberately untouched.
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

create table public.kakao_multi_connections (
 owner_id uuid primary key references public.profiles(id),
 account_id text unique, encrypted_tokens text,
 confirmation_hash text check(confirmation_hash ~ '^[a-f0-9]{64}$'), confirmation_expires_at timestamptz,
 status text not null default 'disconnected' check(status in ('disconnected','connecting','pending_confirmation','connected','revoked','reauth_required')),
 generation bigint not null default 0 check(generation>=0),
 talk_message_granted boolean not null default false,
 updated_at timestamptz not null default now(),
 check(status <> 'connected' or (account_id is not null and encrypted_tokens is not null and talk_message_granted))
);
create table public.kakao_multi_preferences (
 owner_id uuid primary key references public.kakao_multi_connections(owner_id),
 delivery_time time not null default '08:00',
 days integer[] not null default array[0,1,2,3,4,5,6],
 enabled boolean not null default false, send_empty boolean not null default true,
 admin_paused boolean not null default false,
 updated_at timestamptz not null default now(),
 check(cardinality(days) between 1 and 7 and days <@ array[0,1,2,3,4,5,6] and array_position(days,null) is null),
 check(extract(second from delivery_time)=0)
);
create table public.kakao_multi_oauth (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references public.kakao_multi_connections(owner_id),
 generation bigint not null,
 ticket_hash text unique check(ticket_hash ~ '^[a-f0-9]{64}$'),
 state_hash text unique check(state_hash ~ '^[a-f0-9]{64}$'),
 browser_hash text check(browser_hash ~ '^[a-f0-9]{64}$'),
 status text not null default 'invited' check(status in ('invited','started','exchanging','consumed','cancelled')),
 expires_at timestamptz not null default now()+interval '10 minutes',
 created_at timestamptz not null default now()
);
create table public.kakao_multi_batches (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references public.kakao_multi_connections(owner_id),
 day date not null, generation bigint not null, delivery_deadline timestamptz,
 -- Frozen content is service-only. Message parts live in normalized jobs, no maximum-three schema.
 status text not null default 'reserved' check(status in ('reserved','sending','accepted','failed','uncertain','cancelled','held')),
 outcome text check(outcome in ('api_accepted','setup_failed','reauth_required','outcome_uncertain','revoked','paused','quota_held','empty_day_skipped','scope_changed','schedule_missed')),
 created_at timestamptz not null default now(), completed_at timestamptz,
 unique(owner_id,day), unique(id,owner_id,generation)
);
create table public.kakao_multi_jobs (
 id uuid primary key default gen_random_uuid(),
 batch_id uuid not null, owner_id uuid not null, generation bigint not null,
 part integer not null check(part>0), body text not null check(length(body) between 1 and 200),
 status text not null default 'reserved' check(status in ('reserved','sending','accepted','failed','uncertain','cancelled')),
 outcome text check(outcome in ('api_accepted','setup_failed','reauth_required','outcome_uncertain','revoked','paused','quota_held','scope_changed','schedule_missed')),
 claimed_at timestamptz, completed_at timestamptz,
 foreign key(batch_id,owner_id,generation) references public.kakao_multi_batches(id,owner_id,generation),
 unique(batch_id,part)
);
create index kakao_multi_jobs_owner on public.kakao_multi_jobs(owner_id,status);
create table public.kakao_multi_controls (
 singleton boolean primary key default true check(singleton),
 enabled boolean not null default false,
 -- Zero means disabled. These are app budgets, NOT proof provider-wide quota remains.
 monthly_message_budget integer not null default 0 check(monthly_message_budget>=0),
 monthly_function_budget integer not null default 0 check(monthly_function_budget>=0),
 cost_verified_until timestamptz,
 updated_at timestamptz not null default now()
);
insert into public.kakao_multi_controls(singleton) values(true);

do $$ declare t text; begin
 foreach t in array array['kakao_multi_connections','kakao_multi_preferences','kakao_multi_oauth','kakao_multi_batches','kakao_multi_jobs','kakao_multi_controls'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from public,anon,authenticated',t);
  execute format('grant select,insert,update,delete on public.%I to service_role',t);
 end loop;
end $$;

create function private.kakao_require_user() returns uuid language plpgsql stable security definer set search_path='' as $$
begin
 if auth.uid() is null or not private.sales_enabled() then raise exception 'Unauthorized' using errcode='42501'; end if;
 return auth.uid();
end $$;
create function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
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
 'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0),
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=u order by b.day desc,b.created_at desc limit 1) j on true;
 return result;
end $$;
create function private.kakao_save_preferences(p_enabled boolean,p_time text,p_days integer[],p_send_empty boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); c public.kakao_multi_connections;
begin
 if p_enabled is null or p_send_empty is null or p_time is null or p_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
 or p_days is null or cardinality(p_days) not between 1 and 7 or not p_days <@ array[0,1,2,3,4,5,6] or array_position(p_days,null) is not null then raise exception 'Invalid preferences'; end if;
 select * into c from public.kakao_multi_connections where owner_id=u for update;
 if not found then raise exception 'Connect first'; end if;
 if p_enabled and (private.kakao_service_excluded_owner(u) or c.status<>'connected' or not c.talk_message_granted) then raise exception 'Reconnect required'; end if;
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,send_empty)
 values(u,p_enabled,p_time::time,array(select distinct d from unnest(p_days) d order by d),p_send_empty)
 on conflict(owner_id) do update set enabled=excluded.enabled,delivery_time=excluded.delivery_time,days=excluded.days,send_empty=excluded.send_empty,updated_at=now();
 if not p_enabled then
  update public.kakao_multi_jobs set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='paused',completed_at=now() where owner_id=u and status in ('reserved','held');
 end if;
 return private.kakao_my_status();
end $$;
create function private.kakao_disconnect() returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 perform 1 from public.kakao_multi_connections where owner_id=u for update;
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=now() where owner_id=u;
 update public.kakao_multi_preferences set enabled=false,updated_at=now() where owner_id=u;
 update public.kakao_multi_oauth set status='cancelled' where owner_id=u and status in ('invited','started','exchanging');
 update public.kakao_multi_jobs set status='cancelled',outcome='revoked',completed_at=now() where owner_id=u and status='reserved';
 update public.kakao_multi_batches set status='cancelled',outcome='revoked',completed_at=now() where owner_id=u and status in ('reserved','held');
 return private.kakao_my_status();
end $$;
create function private.kakao_admin_status() returns jsonb language plpgsql stable security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 select coalesce(jsonb_agg(jsonb_build_object('owner_id',s.member,'label',s.label,'connection_status',coalesce(c.status,'disconnected'),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0)) order by s.label),'[]'::jsonb)
 into result from private.sales_scope_for(u,false) s
 left join public.kakao_multi_connections c on c.owner_id=s.member
 left join public.kakao_multi_preferences p on p.owner_id=s.member
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=s.member order by b.day desc,b.created_at desc limit 1) j on true
 where s.managed and s.member<>u;
 return result;
end $$;
create function private.kakao_admin_pause(p_owner_id uuid,p_paused boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 if p_paused is null or not exists(select 1 from private.sales_scope_for(u,false) s where s.member=p_owner_id and s.member<>u and s.managed) then raise exception 'Forbidden' using errcode='42501'; end if;
 perform 1 from public.kakao_multi_connections where owner_id=p_owner_id for update;
 update public.kakao_multi_preferences set admin_paused=p_paused,updated_at=now() where owner_id=p_owner_id;
 if p_paused then
  update public.kakao_multi_jobs set status='cancelled',outcome='paused',completed_at=now() where owner_id=p_owner_id and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='paused',completed_at=now() where owner_id=p_owner_id and status in ('reserved','held');
 end if;
 -- Unpause does not enable subscription or alter revoked connection/consent.
 return private.kakao_admin_status();
end $$;

create function public.kakao_my_status() returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_my_status() $$;
create function public.kakao_save_preferences(p_enabled boolean,p_time text,p_days integer[],p_send_empty boolean) returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_save_preferences(p_enabled,p_time,p_days,p_send_empty) $$;
create function public.kakao_disconnect() returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_disconnect() $$;
create function public.kakao_admin_status() returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_admin_status() $$;
create function public.kakao_admin_pause(p_owner_id uuid,p_paused boolean) returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_admin_pause(p_owner_id,p_paused) $$;

-- Used by verified service JWT caller; never accept a browser-supplied owner without Auth verification.
create function private.kakao_service_owner_active(p_owner uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.profiles p join public.hwarang_app_access a on a.user_id=p.id
 where p.id=p_owner and p.is_active and a.app_code='workspace' and a.is_enabled
 and not private.kakao_service_excluded_owner(p.id)
 and exists(select 1 from public.get_hwarang_effective_permissions(p.id) ep where ep.permission_code='workspace.sales_activity'))
$$;
create function private.kakao_service_begin(p_owner uuid,p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare c public.kakao_multi_connections; t public.kakao_multi_oauth;
begin
 if not private.kakao_service_owner_active(p_owner) or p_ticket_hash is null or p_ticket_hash !~ '^[a-f0-9]{64}$' then raise exception 'Unauthorized' using errcode='42501'; end if;
 insert into public.kakao_multi_connections(owner_id) values(p_owner) on conflict(owner_id) do nothing;
 select * into c from public.kakao_multi_connections where owner_id=p_owner for update;
 -- Rate bound, does not reveal existing OAuth nonce.
 if exists(select 1 from public.kakao_multi_oauth where owner_id=p_owner and created_at>now()-interval '1 minute') then raise exception 'Please wait before reconnecting'; end if;
 update public.kakao_multi_connections set generation=generation+1,status='connecting',encrypted_tokens=null,account_id=null,confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=now()
 where owner_id=p_owner returning * into c;
 insert into public.kakao_multi_preferences(owner_id,enabled) values(p_owner,false)
 on conflict(owner_id) do update set enabled=false,updated_at=now();
 update public.kakao_multi_oauth set status='cancelled' where owner_id=p_owner and status in ('invited','started','exchanging');
 update public.kakao_multi_jobs set status='cancelled',outcome='revoked',completed_at=now() where owner_id=p_owner and status='reserved';
 update public.kakao_multi_batches set status='cancelled',outcome='revoked',completed_at=now() where owner_id=p_owner and status in ('reserved','held');
 insert into public.kakao_multi_oauth(owner_id,generation,ticket_hash) values(p_owner,c.generation,p_ticket_hash) returning * into t;
 return jsonb_build_object('id',t.id,'owner_id',t.owner_id,'generation',t.generation);
end $$;
create function private.kakao_service_legacy_conflict(p_account_id text) returns boolean language plpgsql stable security definer set search_path='' as $$
declare conflict boolean:=false;
begin
 if p_account_id is null or to_regclass('public.dot_kakao_connections') is null then return false; end if;
 execute 'select exists(select 1 from public.dot_kakao_connections where account_id=$1 and status in (''approved'',''pending_owner_confirmation''))' into conflict using p_account_id;
 return conflict;
end $$;
create function private.kakao_service_finish(p_ticket_id uuid,p_generation bigint,p_account_id text,p_encrypted_tokens text,p_receipt_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_oauth; c public.kakao_multi_connections;
begin
 select * into t from public.kakao_multi_oauth where id=p_ticket_id;
 if not found then raise exception 'Invalid connection'; end if;
 -- Consistent connection-first order shared by revoke/begin/finish.
 select * into c from public.kakao_multi_connections where owner_id=t.owner_id for update;
 select * into t from public.kakao_multi_oauth where id=p_ticket_id for update;
 if p_generation is null or t.status<>'exchanging' or t.expires_at<=now() or t.generation<>p_generation or c.generation<>p_generation or c.status<>'connecting'
 or not private.kakao_service_owner_active(t.owner_id) or p_account_id is null or p_account_id !~ '^[0-9]{1,20}$'
 or private.kakao_service_legacy_conflict(p_account_id) or p_receipt_hash is null or p_receipt_hash !~ '^[a-f0-9]{64}$' or p_encrypted_tokens is null or length(p_encrypted_tokens) not between 40 and 32768 then raise exception 'Invalid connection'; end if;
 update public.kakao_multi_connections set status='pending_confirmation',confirmation_hash=p_receipt_hash,confirmation_expires_at=now()+interval '10 minutes',account_id=p_account_id,encrypted_tokens=p_encrypted_tokens,talk_message_granted=true,updated_at=now() where owner_id=t.owner_id;
 update public.kakao_multi_preferences set enabled=false,updated_at=now() where owner_id=t.owner_id;
 update public.kakao_multi_oauth set status='consumed',state_hash=null,browser_hash=null where id=p_ticket_id;
 return jsonb_build_object('pending_confirmation',true);
end $$;
create function public.kakao_service_begin(p_owner uuid,p_ticket_hash text) returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_service_begin(p_owner,p_ticket_hash) $$;
create function public.kakao_service_finish(p_ticket_id uuid,p_generation bigint,p_account_id text,p_encrypted_tokens text,p_receipt_hash text) returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_service_finish(p_ticket_id,p_generation,p_account_id,p_encrypted_tokens,p_receipt_hash) $$;

create function private.kakao_service_gate() returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object('enabled',c.enabled and coalesce(c.cost_verified_until>now(),false) and c.monthly_message_budget>0 and c.monthly_function_budget>0,
 'monthly_message_budget',c.monthly_message_budget,'monthly_function_budget',c.monthly_function_budget,'cost_verified_until',c.cost_verified_until)
 from public.kakao_multi_controls c where singleton
$$;
create function public.kakao_service_gate() returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_service_gate() $$;

create function private.kakao_confirm_connection(p_receipt_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();
begin
 if p_receipt_hash is null or p_receipt_hash !~ '^[a-f0-9]{64}$' then raise exception 'Invalid confirmation'; end if;
 update public.kakao_multi_connections set status='connected',confirmation_hash=null,confirmation_expires_at=null,updated_at=now()
 where owner_id=u and status='pending_confirmation' and confirmation_hash=p_receipt_hash and confirmation_expires_at>now() and talk_message_granted and not private.kakao_service_excluded_owner(u) and not private.kakao_service_legacy_conflict(account_id);
 if not found then raise exception 'Invalid confirmation'; end if;
 return private.kakao_my_status();
end $$;
create function public.kakao_confirm_connection(p_receipt_hash text) returns jsonb language sql security invoker set search_path='' as $$ select private.kakao_confirm_connection(p_receipt_hash) $$;

-- Default EXECUTE privileges must be removed for EVERY new function, including private helpers.
do $$ declare f record; target text; begin
 for f in select n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) args
 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname in ('public','private') and p.proname like 'kakao\_%' escape '\' loop
  target:=format('%I.%I(%s)',f.nspname,f.proname,f.args);
  execute 'revoke all on function '||target||' from public,anon,authenticated,service_role';
  if f.proname like 'kakao_service_%' then execute 'grant execute on function '||target||' to service_role';
  else execute 'grant execute on function '||target||' to authenticated'; end if;
 end loop;
end $$;
grant usage on schema private to authenticated,service_role;
-- Tables remain service only. These RPCs expose only deliberate projections and mutations.
commit;
