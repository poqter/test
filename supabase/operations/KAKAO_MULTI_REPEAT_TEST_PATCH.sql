-- Explicit user-triggered repeat tests: preserved history, separate from daily batches/cron.
-- Global 10/day, owner 5/day, >=60 seconds between requests, no uncertain retry.
begin;
alter table public.kakao_multi_test_requests drop constraint if exists kakao_test_owner_slot_key;
alter table public.kakao_multi_test_requests drop constraint if exists kakao_multi_test_requests_request_slot_check;
alter table public.kakao_multi_test_requests drop constraint if exists kakao_test_second_cached_only;
alter table public.kakao_multi_test_requests alter column request_slot drop not null,alter column request_slot drop default;
create index if not exists kakao_test_owner_created on public.kakao_multi_test_requests(owner_id,created_at desc);
create index if not exists kakao_test_created on public.kakao_multi_test_requests(created_at);

create or replace function private.kakao_test_claim(p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;c public.kakao_multi_connections;s jsonb;cached jsonb;function_budget integer;token uuid:=gen_random_uuid();d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
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
 -- Atomically leave two shared function units for the normal tick/send path.
 select monthly_function_budget into function_budget from public.kakao_multi_controls where singleton for update;
 if (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>=function_budget-2 then return null;end if;
 -- Account for the single test invocation in the existing bounded function budget.
 if not private.kakao_service_tick_enter(t.id) then return null;end if;
 s:=private.kakao_service_snapshot(t.owner_id,d);
 update public.kakao_multi_test_requests set status='processing',claim_token=token,generation=c.generation,day=d,scope_hash=private.kakao_service_snapshot_hash(s),started_at=clock_timestamp() where id=t.id;
 return jsonb_build_object('id',t.id,'owner_id',t.owner_id,'generation',c.generation,'day',d,'summary',s,'claim_token',token,'encrypted_tokens',c.encrypted_tokens,'cached_weather_only',t.cached_weather_only,'cached_weather',cached);
end $$;

create function private.kakao_test_enqueue(p_owner uuid,p_request_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;c public.kakao_multi_connections;ctl public.kakao_multi_controls;
 ticket text;network_id bigint;at_time timestamptz:=clock_timestamp();day_start timestamptz:=(date_trunc('day',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul');last_time timestamptz;endpoint text;
begin
 if p_owner is null or p_request_id is null then raise exception 'Invalid request';end if;
 -- Serialize idempotency, cooldown and both caps across every caller.
 perform pg_advisory_xact_lock(1746948683,20261119);
 select * into t from public.kakao_multi_test_requests where id=p_request_id;
 if found then
  if t.owner_id<>p_owner then raise exception 'Request belongs to another owner';end if;
  return jsonb_build_object('id',t.id,'status',case when t.status='queued' and t.expires_at<=at_time then 'expired' when t.status='processing' and t.expires_at<=at_time then 'uncertain' else t.status end,'reused',true);
 end if;
 select * into ctl from public.kakao_multi_controls where singleton;
 if not found or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 or ctl.tick_endpoint is null or ctl.tick_endpoint !~ '^https://[a-z0-9]+\.supabase\.co/functions/v1/hwarang-kakao/tick$' then return jsonb_build_object('status','blocked','reason','service_unavailable');end if;
 select * into c from public.kakao_multi_connections where owner_id=p_owner;
 if not found or c.status<>'connected' or not c.talk_message_granted or not private.kakao_service_owner_active(p_owner)
 or private.kakao_service_legacy_conflict(c.account_id)
 or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=p_owner and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return jsonb_build_object('status','blocked','reason','connection_unavailable');end if;
 if exists(select 1 from public.kakao_multi_test_requests where owner_id=p_owner and (status in ('processing','uncertain') or (status='queued' and expires_at>at_time))) then return jsonb_build_object('status','blocked','reason','previous_request_pending');end if;
 if (select count(*) from public.kakao_multi_test_requests where owner_id=p_owner and created_at>=day_start)>=5
 or (select count(*) from public.kakao_multi_test_requests where created_at>=day_start)>=10 then return jsonb_build_object('status','blocked','reason','daily_limit');end if;
 select max(created_at) into last_time from public.kakao_multi_test_requests where owner_id=p_owner;
 if last_time>at_time-interval '60 seconds' then return jsonb_build_object('status','blocked','reason','cooldown','retry_after',last_time+interval '60 seconds');end if;
 -- Reserve room for at least a normal tick and a normal send; both paths also enforce the shared budget.
 if (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',at_time at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>=ctl.monthly_function_budget-2 then return jsonb_build_object('status','blocked','reason','function_budget');end if;
 ticket:=encode(extensions.gen_random_bytes(32),'hex');
 insert into public.kakao_multi_test_requests(id,owner_id,ticket_hash,created_at,expires_at,cached_weather_only)
 values(p_request_id,p_owner,encode(extensions.digest(ticket,'sha256'),'hex'),at_time,at_time+interval '3 minutes',false);
 endpoint:=regexp_replace(ctl.tick_endpoint,'/hwarang-kakao/tick$','/hwarang-kakao-test');
 network_id:=net.http_post(url:=endpoint,headers:='{"Content-Type":"application/json"}'::jsonb,body:=jsonb_build_object('ticket',ticket),timeout_milliseconds:=60000);
 if network_id is null then raise exception 'Could not queue test';end if;
 return jsonb_build_object('id',p_request_id,'status','queued','reused',false);
end $$;
create function private.kakao_request_test(p_request_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
begin return private.kakao_test_enqueue(private.kakao_require_user(),p_request_id);end $$;
create function public.kakao_request_test(p_request_id uuid) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_request_test(p_request_id)$$;
create function public.kakao_service_request_test(p_owner uuid,p_request_id uuid) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_test_enqueue(p_owner,p_request_id)$$;
create function private.kakao_my_test_status() returns jsonb language plpgsql security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user();t public.kakao_multi_test_requests;at_time timestamptz:=clock_timestamp();used integer;
begin
 select count(*) into used from public.kakao_multi_test_requests where owner_id=u and created_at>=(date_trunc('day',at_time at time zone 'Asia/Seoul') at time zone 'Asia/Seoul');
 select * into t from public.kakao_multi_test_requests where owner_id=u order by created_at desc,id desc limit 1;
 if not found then return jsonb_build_object('status','none','used_today',used,'daily_limit',5);end if;
 return jsonb_build_object('id',t.id,'status',case when t.status='queued' and t.expires_at<=at_time then 'expired' when t.status='processing' and t.expires_at<=at_time then 'uncertain' else t.status end,'created_at',t.created_at,'completed_at',t.completed_at,'used_today',used,'daily_limit',5);
end $$;
create function public.kakao_my_test_status() returns jsonb language sql security invoker set search_path='' as $$select private.kakao_my_test_status()$$;

create function private.kakao_test_weather_claim(p_id uuid,p_claim_token uuid,p_base_date text,p_base_time text) returns jsonb language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_test_requests;r public.kakao_weather_regions;c public.kakao_weather_cache;budget integer;used integer;kst date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
 if not private.kakao_test_validate(p_id,p_claim_token) then return jsonb_build_object('status','unavailable');end if;
 select * into t from public.kakao_multi_test_requests where id=p_id and claim_token=p_claim_token;
 if not found or not private.kakao_weather_request_valid(t.day,p_base_date,p_base_time) then return jsonb_build_object('status','unavailable');end if;
 select r0.* into r from public.kakao_multi_preferences p join public.kakao_weather_regions r0 on r0.region_key=p.weather_region_key
 where p.owner_id=t.owner_id and r0.enabled and r0.verified_at is not null and r0.forecast_code is not null;
 if not found then return jsonb_build_object('status','unavailable');end if;
 -- Same controls-first lock order as shared claim; reservation check and increment are atomic.
 select daily_attempt_budget into budget from public.kakao_weather_controls where singleton for update;
 if not found or budget<=0 then return jsonb_build_object('status','unavailable','region_name',r.label);end if;
 select * into c from public.kakao_weather_cache where nx=r.nx and ny=r.ny and forecast_day=t.day and base_date=p_base_date and base_time=p_base_time;
 if found and c.forecast is not null and c.forecast->>'status'='ok' and c.forecast->>'day'=t.day::text and c.expires_at>clock_timestamp() then
  return jsonb_build_object('status','cached','forecast',c.forecast,'region_name',r.label,'forecast_code',r.forecast_code);
 end if;
 select coalesce((select attempts from public.kakao_weather_usage where day=kst),0) into used;
 if used>=budget-1 then return jsonb_build_object('status','unavailable','region_name',r.label);end if;
 return private.kakao_service_weather_claim(r.region_key,t.day,p_base_date,p_base_time);
end $$;
create function public.kakao_test_weather_claim(p_id uuid,p_claim_token uuid,p_base_date text,p_base_time text) returns jsonb language sql security invoker set search_path='' as $$select private.kakao_test_weather_claim(p_id,p_claim_token,p_base_date,p_base_time)$$;

revoke all on function private.kakao_test_enqueue(uuid,uuid),public.kakao_service_request_test(uuid,uuid),private.kakao_test_weather_claim(uuid,uuid,text,text),public.kakao_test_weather_claim(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function private.kakao_test_enqueue(uuid,uuid),public.kakao_service_request_test(uuid,uuid),private.kakao_test_weather_claim(uuid,uuid,text,text),public.kakao_test_weather_claim(uuid,uuid,text,text) to service_role;
revoke all on function private.kakao_request_test(uuid),public.kakao_request_test(uuid),private.kakao_my_test_status(),public.kakao_my_test_status() from public,anon;
grant execute on function private.kakao_request_test(uuid),public.kakao_request_test(uuid),private.kakao_my_test_status(),public.kakao_my_test_status() to authenticated;
commit;
