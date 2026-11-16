-- Local synthetic fixtures only. No external weather or Kakao requests.
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted) select id,'fake-'||login_id,'cipher','connected',1,true from public.profiles;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled) select id,'web:1100000000',true from public.profiles;
update public.kakao_multi_preferences set delivery_time=date_trunc('minute',(clock_timestamp() at time zone 'Asia/Seoul')+interval '1 hour')::time;
update public.kakao_multi_controls set enabled=true,monthly_message_budget=10,monthly_function_budget=30,cost_verified_until=now()+interval '1 day',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick';
create temporary table normal_baseline as select (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) slots,(select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p) prefs;
do $$declare issue timestamp;h integer;bd text;bt text;d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;r jsonb;t jsonb;rid uuid:=gen_random_uuid();u uuid;bad boolean:=false;begin
 if (select test_daily_attempt_budget from public.kakao_weather_controls)<>0 or (select normal_daily_attempt_budget<>daily_attempt_budget from public.kakao_weather_controls) then raise exception 'Migration expanded budget';end if;
 update public.kakao_weather_controls set daily_attempt_budget=4,normal_daily_attempt_budget=2,test_daily_attempt_budget=2;
 issue:=(clock_timestamp() at time zone 'Asia/Seoul')-interval '10 minutes';
 select max(x) into h from unnest(array[2,5,8,11,14,17,20,23]) x where x<=extract(hour from issue);
 if h is null then issue:=issue-interval '1 day';h:=23;end if;
 bd:=to_char(issue,'YYYYMMDD');bt:=lpad(h::text,2,'0')||'00';
 select id into u from public.profiles where login_id='qa_staff';
 perform public.kakao_service_request_test(u,rid);
 select public.kakao_test_claim(ticket_hash) into t from public.kakao_multi_test_requests where id=rid;
 if t is null then raise exception 'Test claim fixture failed';end if;
 if public.kakao_test_weather_claim(rid,gen_random_uuid(),bd,bt)->>'status'<>'unavailable' then raise exception 'Invalid claim passed';end if;
 r:=public.kakao_test_weather_claim(rid,(t->>'claim_token')::uuid,bd,bt);
 if r->>'status'<>'fetch' then raise exception 'First test fetch denied: %',r;end if;
 -- Retry during an active cache lease does not consume another allocation.
 if public.kakao_test_weather_claim(rid,(t->>'claim_token')::uuid,bd,bt)->>'status'<>'wait' or (select attempts from public.kakao_weather_usage where day=d)<>1 then raise exception 'Lease duplicate consumed';end if;
 update public.kakao_weather_cache set lease_until=null,lease_token=null;
 r:=public.kakao_test_weather_claim(rid,(t->>'claim_token')::uuid,bd,bt);
 if r->>'status'<>'fetch' then raise exception 'Second test fetch denied';end if;
 update public.kakao_weather_cache set lease_until=null,lease_token=null;
 if public.kakao_test_weather_claim(rid,(t->>'claim_token')::uuid,bd,bt)->>'status'<>'unavailable' then raise exception 'Test stole normal allocation';end if;
 -- Both reserved normal fetches remain available after the tests exhaust their pool.
 if public.kakao_service_weather_claim('web:1100000000',d,bd,bt)->>'status'<>'fetch' then raise exception 'Normal allocation lost1';end if;
 update public.kakao_weather_cache set lease_until=null,lease_token=null;
 if public.kakao_service_weather_claim('web:1100000000',d,bd,bt)->>'status'<>'fetch' then raise exception 'Normal allocation lost2';end if;
 update public.kakao_weather_cache set lease_until=null,lease_token=null;
 if public.kakao_service_weather_claim('web:1100000000',d,bd,bt)->>'status'<>'unavailable' then raise exception 'Shared/normal cap exceeded';end if;
 if (select attempts<>4 or test_attempts<>2 from public.kakao_weather_usage where day=d) then raise exception 'Bad ledger';end if;
 update public.kakao_weather_cache set forecast=jsonb_build_object('status','ok','day',d::text),expires_at=clock_timestamp()+interval '10 minutes';
 if public.kakao_service_weather_claim('web:1100000000',d,bd,bt)->>'status'<>'cached' or public.kakao_test_weather_claim(rid,(t->>'claim_token')::uuid,bd,bt)->>'status'<>'cached' then raise exception 'Exhausted budget blocked cache';end if;
 if (select attempts<>4 or test_attempts<>2 from public.kakao_weather_usage where day=d) then raise exception 'Cache consumed allocation';end if;
 update public.kakao_weather_cache set forecast=jsonb_build_object('status','ok','day',(d-1)::text);
 if public.kakao_service_weather_claim('web:1100000000',d,bd,bt)->>'status'<>'unavailable' then raise exception 'Wrong date cache accepted';end if;
 begin update public.kakao_weather_controls set test_daily_attempt_budget=3;exception when check_violation then bad:=true;end;
 if not bad then raise exception 'Allocation sum exceeded shared cap';end if;
 if has_function_privilege('anon','private.kakao_weather_claim_kind(text,date,text,text,text)','execute') or has_function_privilege('authenticated','private.kakao_weather_claim_kind(text,date,text,text,text)','execute') or has_function_privilege('service_role','private.kakao_weather_claim_kind(text,date,text,text,text)','execute') then raise exception 'Helper ACL leak';end if;
 if exists(select 1 from public.kakao_multi_batches) or exists(select 1 from public.kakao_multi_jobs) or exists(select 1 from normal_baseline b where b.slots is distinct from (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) or b.prefs is distinct from (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p)) then raise exception 'Normal state changed';end if;
end $$;
select 'PASS: separated weather allocations, cache reuse, claim ACL and normal isolation';
-- Deterministic priority boundaries and KST day wrapping; fixture changes are rolled back.
begin;
update public.kakao_multi_preferences set enabled=false;
update public.kakao_multi_preferences set enabled=true,delivery_time='08:00',days=array[1],weather_region_key='web:1100000000' where owner_id=(select id from public.profiles where login_id='qa_staff');
do $$declare u uuid;r jsonb;t public.kakao_multi_test_requests;c public.kakao_weather_cache;d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;begin
 select id into u from public.profiles where login_id='qa_staff';
 if private.kakao_weather_normal_priority(60,127,'2026-11-16 07:53:59+09') or not private.kakao_weather_normal_priority(60,127,'2026-11-16 07:54:00+09') or not private.kakao_weather_normal_priority(60,127,'2026-11-16 08:09:59+09') or private.kakao_weather_normal_priority(60,127,'2026-11-16 08:10:00+09') then raise exception 'Priority interval incorrect';end if;
 if private.kakao_weather_normal_priority(98,76,'2026-11-16 08:00+09') or private.kakao_weather_normal_priority(60,127,'2026-11-17 08:00+09') then raise exception 'Wrong grid/weekday guarded';end if;
 update public.kakao_multi_preferences set delivery_time='23:55' where owner_id=u;
 if not private.kakao_weather_normal_priority(60,127,'2026-11-17 00:02+09') or private.kakao_weather_normal_priority(60,127,'2026-11-17 00:05+09') then raise exception 'Yesterday KST wrap failed';end if;
 update public.kakao_multi_preferences set delivery_time='00:02',days=array[2] where owner_id=u;
 if not private.kakao_weather_normal_priority(60,127,'2026-11-16 23:57+09') or private.kakao_weather_normal_priority(60,127,'2026-11-16 23:55+09') then raise exception 'Tomorrow KST wrap failed';end if;
 insert into public.kakao_multi_batches(owner_id,day,generation,status,completed_at) values(u,'2026-11-17',1,'accepted',clock_timestamp());
 if private.kakao_weather_normal_priority(60,127,'2026-11-16 23:57+09') then raise exception 'Completed normal still guarded';end if;
 delete from public.kakao_multi_batches where owner_id=u;
 update public.kakao_multi_connections set talk_message_granted=false,status='reauth_required' where owner_id=u;
 if private.kakao_weather_normal_priority(60,127,'2026-11-16 23:57+09') then raise exception 'No consent still guarded';end if;
 update public.kakao_multi_connections set talk_message_granted=true,status='connected' where owner_id=u;
 update public.kakao_multi_preferences set delivery_time=date_trunc('minute',clock_timestamp() at time zone 'Asia/Seoul')::time,days=array[0,1,2,3,4,5,6] where owner_id=u;
 select * into c from public.kakao_weather_cache limit 1;
 -- Direct internal helper here avoids changing a test request's snapshot fixture.
 update public.kakao_weather_usage set attempts=0,test_attempts=0;
 update public.kakao_weather_cache set forecast=null,expires_at=null,lease_until=null,lease_token=null,retry_after=null;
 r:=private.kakao_weather_claim_kind('web:1100000000',d,c.base_date,c.base_time,'test');
 if r->>'status'<>'unavailable' or (select attempts from public.kakao_weather_usage where day=d)<>0 then raise exception 'Imminent normal test cache miss consumed';end if;
 update public.kakao_weather_cache set forecast=jsonb_build_object('status','ok','day',d::text),expires_at=clock_timestamp()+interval '10 minutes';
 if private.kakao_weather_claim_kind('web:1100000000',d,c.base_date,c.base_time,'test')->>'status'<>'cached' then raise exception 'Priority guard blocked cache hit';end if;
 update public.kakao_weather_cache set forecast=null,expires_at=null;
 if private.kakao_service_weather_claim('web:1100000000',d,c.base_date,c.base_time)->>'status'<>'fetch' then raise exception 'Priority guard blocked normal fetch';end if;
 if has_function_privilege('service_role','private.kakao_weather_normal_priority(integer,integer,timestamptz)','execute') then raise exception 'Priority helper exposed';end if;
end $$;
rollback;
select 'PASS: same-grid normal priority -6m/+10m; yesterday/today/tomorrow KST, consent and cache hit';
