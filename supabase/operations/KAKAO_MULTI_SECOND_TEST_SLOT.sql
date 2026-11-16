-- Adds only the second explicitly requested test slot; never resets/retries slot 1.
begin;
alter table public.kakao_multi_test_requests add column request_slot integer not null default 1 check(request_slot in (1,2)),add column cached_weather_only boolean not null default false;
alter table public.kakao_multi_test_requests drop constraint kakao_multi_test_requests_owner_id_key;
alter table public.kakao_multi_test_requests add constraint kakao_test_owner_slot_key unique(owner_id,request_slot),add constraint kakao_test_second_cached_only check(request_slot=1 or cached_weather_only);
create or replace function private.kakao_test_claim(p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;c public.kakao_multi_connections;s jsonb;cached jsonb;token uuid:=gen_random_uuid();d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
 select * into t from public.kakao_multi_test_requests where ticket_hash=p_ticket_hash for update;
 if not found or t.status<>'queued' or t.expires_at<=clock_timestamp() then return null;end if;
 select * into c from public.kakao_multi_connections where owner_id=t.owner_id;
 if not found or c.status<>'connected' or not c.talk_message_granted or not private.kakao_service_owner_active(t.owner_id)
 or private.kakao_service_legacy_conflict(c.account_id) or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=t.owner_id and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return null;end if;
 if t.cached_weather_only then
  select wc.forecast||jsonb_build_object('region_name',r.label) into cached
  from public.kakao_multi_preferences pref join public.kakao_weather_regions r on r.region_key=pref.weather_region_key
  join public.kakao_weather_cache wc on wc.nx=r.nx and wc.ny=r.ny
  where pref.owner_id=t.owner_id and wc.forecast_day=d and wc.expires_at>clock_timestamp()
  and wc.forecast->>'status'='ok' order by wc.expires_at desc limit 1;
  if cached is null then return null;end if;
 end if;
 -- Account for the single test invocation in the existing bounded function budget.
 if not private.kakao_service_tick_enter(t.id) then return null;end if;
 s:=private.kakao_service_snapshot(t.owner_id,d);
 update public.kakao_multi_test_requests set status='processing',claim_token=token,generation=c.generation,day=d,scope_hash=private.kakao_service_snapshot_hash(s),started_at=clock_timestamp() where id=t.id;
 return jsonb_build_object('id',t.id,'owner_id',t.owner_id,'generation',c.generation,'day',d,'summary',s,'claim_token',token,'encrypted_tokens',c.encrypted_tokens,'cached_weather_only',t.cached_weather_only,'cached_weather',cached);
end $$;
commit;
