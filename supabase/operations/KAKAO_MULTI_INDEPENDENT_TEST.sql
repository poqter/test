-- One explicitly requested self-test per owner, separate from daily batches and cron.
-- No request is inserted or dispatched by this additive migration.
begin;
create table public.kakao_multi_test_requests (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null unique references public.profiles(id),
 ticket_hash text not null unique check(ticket_hash ~ '^[a-f0-9]{64}$'),
 created_at timestamptz not null default clock_timestamp(),
 expires_at timestamptz not null,
 status text not null default 'queued' check(status in ('queued','processing','accepted','failed','uncertain')),
 claim_token uuid, generation bigint, day date, scope_hash text,
 started_at timestamptz, completed_at timestamptz,
 check(expires_at>created_at and expires_at<=created_at+interval '5 minutes')
);
alter table public.kakao_multi_test_requests enable row level security;
revoke all on public.kakao_multi_test_requests from public,anon,authenticated;
grant select,insert,update on public.kakao_multi_test_requests to service_role;
create function private.kakao_test_claim(p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;c public.kakao_multi_connections;s jsonb;token uuid:=gen_random_uuid();d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
 select * into t from public.kakao_multi_test_requests where ticket_hash=p_ticket_hash for update;
 if not found or t.status<>'queued' or t.expires_at<=clock_timestamp() then return null;end if;
 select * into c from public.kakao_multi_connections where owner_id=t.owner_id;
 if not found or c.status<>'connected' or not c.talk_message_granted or not private.kakao_service_owner_active(t.owner_id)
 or private.kakao_service_legacy_conflict(c.account_id) or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=t.owner_id and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return null;end if;
 -- Account for the single test invocation in the existing bounded function budget.
 if not private.kakao_service_tick_enter(t.id) then return null;end if;
 s:=private.kakao_service_snapshot(t.owner_id,d);
 update public.kakao_multi_test_requests set status='processing',claim_token=token,generation=c.generation,day=d,scope_hash=private.kakao_service_snapshot_hash(s),started_at=clock_timestamp() where id=t.id;
 return jsonb_build_object('id',t.id,'owner_id',t.owner_id,'generation',c.generation,'day',d,'summary',s,'claim_token',token,'encrypted_tokens',c.encrypted_tokens);
end $$;
create function private.kakao_test_validate(p_id uuid,p_claim_token uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_test_requests t join public.kakao_multi_connections c using(owner_id)
 join public.kakao_multi_preferences p using(owner_id)
 where t.id=p_id and t.claim_token=p_claim_token and t.status='processing' and t.expires_at>clock_timestamp()
 and t.day=(clock_timestamp() at time zone 'Asia/Seoul')::date and c.generation=t.generation and c.status='connected' and c.talk_message_granted
 and not p.admin_paused and private.kakao_service_owner_active(t.owner_id) and not private.kakao_service_legacy_conflict(c.account_id)
 and private.kakao_service_snapshot_hash(private.kakao_service_snapshot(t.owner_id,t.day))=t.scope_hash
 and coalesce((private.kakao_service_gate()->>'enabled')::boolean,false))
$$;
create function private.kakao_test_complete(p_id uuid,p_claim_token uuid,p_status text) returns boolean language plpgsql security definer set search_path='' as $$
begin
 if p_status not in ('accepted','failed','uncertain') then return false;end if;
 update public.kakao_multi_test_requests set status=p_status,completed_at=clock_timestamp()
 where id=p_id and claim_token=p_claim_token and status='processing';return found;
end $$;
create function public.kakao_test_claim(p_ticket_hash text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_test_claim(p_ticket_hash)$$;
create function public.kakao_test_validate(p_id uuid,p_claim_token uuid) returns boolean language sql security invoker set search_path='' as $$select private.kakao_test_validate(p_id,p_claim_token)$$;
create function public.kakao_test_complete(p_id uuid,p_claim_token uuid,p_status text) returns boolean language sql security invoker set search_path='' as $$select private.kakao_test_complete(p_id,p_claim_token,p_status)$$;
revoke all on function private.kakao_test_claim(text),public.kakao_test_claim(text),private.kakao_test_validate(uuid,uuid),public.kakao_test_validate(uuid,uuid),private.kakao_test_complete(uuid,uuid,text),public.kakao_test_complete(uuid,uuid,text) from public,anon,authenticated;
grant execute on function private.kakao_test_claim(text),public.kakao_test_claim(text),private.kakao_test_validate(uuid,uuid),public.kakao_test_validate(uuid,uuid),private.kakao_test_complete(uuid,uuid,text),public.kakao_test_complete(uuid,uuid,text) to service_role;
commit;
