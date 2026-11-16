-- Synthetic local PostgreSQL-only verification. net/cron are no-network stubs.
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted)
select id,'fake-'||login_id,'fake-cipher','connected',1,true from public.profiles;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled) select id,'web:1100000000',true from public.profiles;
update public.kakao_multi_controls set enabled=true,monthly_message_budget=10,monthly_function_budget=30,cost_verified_until=now()+interval '1 day',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick' where singleton;
update public.kakao_weather_controls set daily_attempt_budget=4 where singleton;
insert into auth.sessions(id,user_id) select gen_random_uuid(),id from public.profiles;
create temporary table baseline as select (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) slots,(select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p) prefs;
-- Earlier accepted slots remain unchanged history; no fixed request quota.
insert into public.kakao_multi_test_requests(owner_id,request_slot,cached_weather_only,ticket_hash,created_at,expires_at,status,completed_at)
select id,1,false,repeat('a',64),now()-interval '4 minutes',now()-interval '1 minute','accepted',now()-interval '3 minutes' from public.profiles where login_id='qa_staff';
insert into public.kakao_multi_test_requests(owner_id,request_slot,cached_weather_only,ticket_hash,created_at,expires_at,status,completed_at)
select id,2,true,repeat('b',64),now()-interval '2 minutes',now()+interval '1 minute','accepted',now()-interval '1 minute' from public.profiles where login_id='qa_staff';

do $$declare u uuid;peer uuid;rid uuid:=gen_random_uuid();r jsonb;n bigint;claim jsonb;issue timestamp;bd text;bt text;wx jsonb;bad boolean:=false;begin
 select id into u from public.profiles where login_id='qa_staff';select id into peer from public.profiles where login_id='qa_peer';
 r:=public.kakao_service_request_test(u,rid);if r->>'status'<>'queued' then raise exception 'Repeat request denied: %',r;end if;
 select count(*) into n from net.http_request_queue;
 if public.kakao_service_request_test(u,rid)->>'reused'<>'true' or (select count(*) from net.http_request_queue)<>n then raise exception 'Idempotency failure';end if;
 begin perform public.kakao_service_request_test(peer,rid);exception when others then bad:=true;end;if not bad then raise exception 'Cross owner request allowed';end if;
 if public.kakao_service_request_test(u,gen_random_uuid())->>'reason'<>'previous_request_pending' then raise exception 'Concurrent request not blocked';end if;
 if exists(select 1 from net.http_request_queue where url<>'https://fake.supabase.co/functions/v1/hwarang-kakao-test' or (body->>'ticket') !~ '^[a-f0-9]{64}$') then raise exception 'Unsafe endpoint/ticket';end if;
 select public.kakao_test_claim(ticket_hash) into claim from public.kakao_multi_test_requests where id=rid;
 if claim is null then raise exception 'Could not claim new request';end if;
 -- Compute the current valid issue, keeping the runtime publication-lag logic intact.
 issue:=(clock_timestamp() at time zone 'Asia/Seoul')-interval '10 minutes';
 select max(h) into n from unnest(array[2,5,8,11,14,17,20,23]) h where h<=extract(hour from issue);
 if n is null then issue:=issue-interval '1 day';n:=23;end if;
 bd:=to_char(issue,'YYYYMMDD');bt:=lpad(n::text,2,'0')||'00';
 wx:=public.kakao_test_weather_claim(rid,(claim->>'claim_token')::uuid,bd,bt);
 if wx->>'status'<>'fetch' then raise exception 'First bounded fetch failed: %',wx;end if;
 update public.kakao_weather_cache set forecast=jsonb_build_object('status','ok','day',(claim->>'day')),expires_at=clock_timestamp()+interval '10 minutes',lease_until=null,lease_token=null where base_date=bd and base_time=bt;
 update public.kakao_weather_usage set attempts=3 where day=(clock_timestamp() at time zone 'Asia/Seoul')::date;
 wx:=public.kakao_test_weather_claim(rid,(claim->>'claim_token')::uuid,bd,bt);
 if wx->>'status'<>'cached' or (select attempts from public.kakao_weather_usage where day=(clock_timestamp() at time zone 'Asia/Seoul')::date)<>3 then raise exception 'Cache consumed reserved budget';end if;
 update public.kakao_weather_cache set expires_at=clock_timestamp()-interval '1 second';
 if public.kakao_test_weather_claim(rid,(claim->>'claim_token')::uuid,bd,bt)->>'status'<>'unavailable' or (select attempts from public.kakao_weather_usage where day=(clock_timestamp() at time zone 'Asia/Seoul')::date)<>3 then raise exception 'Morning weather reservation exhausted';end if;
 if not public.kakao_test_complete(rid,(claim->>'claim_token')::uuid,'accepted') then raise exception 'Completion failed';end if;
 -- A fresh explicit request immediately after accepted is allowed, with no sleep.
 rid:=gen_random_uuid();r:=public.kakao_service_request_test(u,rid);if r->>'status'<>'queued' then raise exception 'Fourth test denied';end if;
 update public.kakao_multi_test_requests set status='uncertain' where id=rid;
 if public.kakao_service_request_test(u,gen_random_uuid())->>'reason'<>'previous_request_pending' then raise exception 'Uncertainty retried';end if;
 -- Explicit synthetic resolution only, not an operational recovery procedure.
 update public.kakao_multi_test_requests set status='failed',created_at=created_at-interval '2 minutes',expires_at=expires_at-interval '2 minutes' where id=rid;
 rid:=gen_random_uuid();r:=public.kakao_service_request_test(u,rid);if r->>'status'<>'queued' then raise exception 'Fifth test denied';end if;
 update public.kakao_multi_test_requests set status='failed',created_at=created_at-interval '2 minutes',expires_at=expires_at-interval '2 minutes' where id=rid;
 rid:=gen_random_uuid();r:=public.kakao_service_request_test(u,rid);if r->>'status'<>'queued' then raise exception 'Sixth owner request denied: %',r;end if;
 update public.kakao_multi_test_requests set status='processing',created_at=clock_timestamp()-interval '4 minutes',expires_at=clock_timestamp()-interval '1 second' where id=rid;
 if public.kakao_service_request_test(u,gen_random_uuid())->>'reason'<>'previous_request_pending' then raise exception 'Expired processing retried';end if;
 update public.kakao_multi_test_requests set status='failed' where id=rid;
 if (select count(*) from public.kakao_multi_test_requests where owner_id=u and request_slot in (1,2) and status='accepted')<>2 then raise exception 'Original accepted history changed';end if;
 if exists(select 1 from public.kakao_multi_batches) or exists(select 1 from public.kakao_multi_jobs)
 or exists(select 1 from baseline b where b.slots is distinct from (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) or b.prefs is distinct from (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p)) then raise exception 'Normal schedule/state changed';end if;
 if has_function_privilege('authenticated','private.kakao_test_enqueue(uuid,uuid)','execute') or has_function_privilege('anon','public.kakao_request_test(uuid)','execute') or has_function_privilege('authenticated','public.kakao_service_request_test(uuid,uuid)','execute') or has_function_privilege('authenticated','public.kakao_test_weather_claim(uuid,uuid,text,text)','execute') then raise exception 'ACL leak';end if;
end $$;
-- Authenticated wrapper uses the caller's live session, not a supplied owner.
select set_config('request.jwt.claims',(select jsonb_build_object('sub',p.id,'session_id',s.id)::text from public.profiles p join auth.sessions s on s.user_id=p.id where p.login_id='qa_peer'),false);
set role authenticated;
select public.kakao_request_test(gen_random_uuid())->>'status'='queued' as authenticated_request;
select public.kakao_my_test_status()->>'status'='queued' as authenticated_status;
reset role;
-- More than ten global and five owner requests remain permitted within shared budget.
insert into public.kakao_multi_test_requests(owner_id,ticket_hash,created_at,expires_at,status)
select (select id from public.profiles where login_id='qa_manager'),encode(extensions.gen_random_bytes(32),'hex'),now()-interval '3 minutes',now()-interval '1 minute','failed' from generate_series(1,11);
do $$declare r jsonb;u uuid;rid uuid:=gen_random_uuid();c jsonb;begin
 select id into u from public.profiles where login_id='qa_manager';
 r:=public.kakao_service_request_test(u,rid);if r->>'status'<>'queued' then raise exception 'Global 11+/owner 5+ request denied: %',r;end if;
 -- Only the budget boundary, not a request-count policy, blocks new tests.
 insert into public.kakao_multi_runs(id,entered_at) select gen_random_uuid(),clock_timestamp() from generate_series(1,26);
 select public.kakao_test_claim(ticket_hash) into c from public.kakao_multi_test_requests where id=rid;
 if c is null or (select count(*) from public.kakao_multi_runs)<>28 then raise exception 'Final test function unit denied';end if;
 if not public.kakao_test_complete(rid,(c->>'claim_token')::uuid,'accepted') then raise exception 'Boundary completion failed';end if;
 r:=public.kakao_service_request_test(u,gen_random_uuid());if r->>'reason'<>'function_budget' then raise exception 'Normal two-unit reservation lost: %',r;end if;
 if not private.kakao_service_tick_enter(gen_random_uuid()) or not private.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Reserved normal units unavailable';end if;
 if private.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Shared function budget exceeded';end if;
 if (select monthly_function_budget from public.kakao_multi_controls where singleton)<>30 then raise exception 'Configured budget changed';end if;
 if exists(select 1 from public.kakao_multi_batches) or exists(select 1 from public.kakao_multi_jobs)
 or exists(select 1 from baseline b where b.slots is distinct from (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) or b.prefs is distinct from (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p)) then raise exception 'Normal state changed';end if;
end $$;
set role authenticated;
do $$declare s jsonb:=public.kakao_my_test_status();begin
 if s ? 'daily_limit' or not(s ? 'used_today') then raise exception 'Status quota contract invalid: %',s;end if;
end $$;
reset role;
select 'PASS: unlimited explicit requests within shared budget; no cooldown; immutable IDs, pending/uncertain, ACL, weather reserve, normal two function units and state preserved' as result;
