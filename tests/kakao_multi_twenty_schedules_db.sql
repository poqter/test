-- LOCAL SYNTHETIC DATABASE ONLY. Requires recording cron/net stubs.
-- Test clock replaces clock_timestamp in installed private Kakao functions only;
-- never apply this fixture/mutation to any deployed database.
create function private.qa_clock() returns timestamptz language sql stable as $$select current_setting('qa.clock')::timestamptz$$;
select set_config('qa.clock','2030-01-07 00:00:00+09',false);
do $$declare f record;begin
 for f in select pg_get_functiondef(p.oid) definition from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='private' and p.proname like 'kakao_%' loop
 execute replace(f.definition,'clock_timestamp()','private.qa_clock()');
 end loop;
end $$;
insert into public.profiles(login_id,display_name) select 'twenty_'||i,'Synthetic '||i from generate_series(0,19)i;
insert into public.hwarang_app_access select id,'workspace',true from public.profiles where login_id like 'twenty_%';
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted,updated_at)
select id,'fake-'||login_id,'fake-cipher','connected',1,true,'2030-01-06 00:00+09' from public.profiles where login_id like 'twenty_%';
-- Synthetic enlarged budgets for load testing only. Production values are untouched.
update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=2000,cost_verified_until='2030-02-01 00:00+09',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick' where singleton;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled,delivery_time,days,updated_at)
select id,'web:1100000000',true,make_time(4+(substring(login_id from 8)::integer),0,0),array[1], '2030-01-06 00:00+09' from public.profiles where login_id like 'twenty_%';
do $$declare i integer;due jsonb;run uuid;r jsonb;begin
 if (select count(*) from public.kakao_multi_cron_slots)<>20 or (select count(*) from cron.job)<>40 then raise exception 'Expected 20 slots/40 cron jobs';end if;
 perform private.kakao_cron_reconcile();perform private.kakao_cron_reconcile();
 if (select count(*) from cron.job)<>40 then raise exception 'Duplicate cron registration';end if;
 for i in 0..19 loop
 perform set_config('qa.clock',('2030-01-07'::date+make_time(4+i,0,0))::text||'+09',false);
 run:=gen_random_uuid();if not private.kakao_service_tick_enter(run) then raise exception 'Run denied';end if;
 update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;due:=private.kakao_service_due(run);
 if jsonb_array_length(due)<>1 then raise exception 'Distinct slot % due count: %',i,due;end if;
 if due->0->>'owner_id'<>(select id::text from public.profiles where login_id='twenty_'||i) then raise exception 'Wrong slot recipient';end if;
 r:=private.kakao_service_reserve((due->0->>'owner_id')::uuid,(due->0->>'day')::date,1,array['Synthetic briefing'],due->0->>'scope_hash');
 if jsonb_array_length(private.kakao_service_due(run))<>0 then raise exception 'Duplicate owner/day due';end if;
 end loop;
 if (select count(*) from public.kakao_multi_batches)<>20 or (select count(*) from public.kakao_multi_jobs)<>20 then raise exception '20-owner reservation missing';end if;
end $$;
-- A shared minute produces one dispatch/backstop pair for all 20 owners.
update public.kakao_multi_preferences set delivery_time='08:00',days=array[1,2,3,4,5,6,0],updated_at='2030-01-07 00:00+09';
do $$begin
 if (select count(*) from public.kakao_multi_cron_slots)<>1 or (select count(*) from cron.job)<>2 then raise exception 'Shared slot not deduplicated';end if;
 if not exists(select 1 from cron.job where jobname='hwarang-kakao-slot-480' and schedule='0 23 * * *') then raise exception 'KST to UTC conversion incorrect';end if;
end $$;
select set_config('qa.clock','2030-01-08 08:00:00+09',false);
do $$declare run uuid:=gen_random_uuid();begin
 perform private.kakao_service_tick_enter(run);update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;
 if jsonb_array_length(private.kakao_service_due(run))<>20 then raise exception 'Shared minute missing owners';end if;
end $$;
-- Only the selected weekday is eligible, and changing one user's time adds one slot.
update public.kakao_multi_preferences set days=array[1];
do $$declare run uuid:=gen_random_uuid();begin
 perform private.kakao_service_tick_enter(run);update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;
 if jsonb_array_length(private.kakao_service_due(run))<>0 then raise exception 'Wrong weekday eligible';end if;
end $$;
update public.kakao_multi_preferences set delivery_time='09:30' where owner_id=(select id from public.profiles where login_id='twenty_0');
do $$begin if (select count(*) from cron.job)<>4 then raise exception 'Time change did not create second pair';end if;end $$;
update public.kakao_multi_preferences set delivery_time='09:30';
do $$begin if (select count(*) from cron.job)<>2 or exists(select 1 from public.kakao_multi_cron_slots where slot=480) then raise exception 'Last subscriber old slot retained';end if;end $$;
-- Monday 23:55 remains Monday's scheduled day at Tuesday 00:02; expires at 00:05.
update public.kakao_multi_preferences set delivery_time='23:55',days=array[1],updated_at='2030-01-07 00:00+09';
select set_config('qa.clock','2030-01-15 00:02:00+09',false);
do $$declare run uuid:=gen_random_uuid();due jsonb;begin
 perform private.kakao_service_tick_enter(run);update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;due:=private.kakao_service_due(run);
 if jsonb_array_length(due)<>20 or exists(select 1 from jsonb_array_elements(due)x where x->>'day'<>'2030-01-14') then raise exception 'KST midnight previous-day/weekday mismatch';end if;
 if not exists(select 1 from cron.job where jobname='hwarang-kakao-backstop-1435' and schedule='5 15 * * *') then raise exception 'Midnight backstop conversion wrong';end if;
end $$;
select set_config('qa.clock','2030-01-15 00:05:00+09',false);
do $$declare run uuid:=gen_random_uuid();begin
 perform private.kakao_service_tick_enter(run);update public.kakao_multi_runs set entered_at=private.qa_clock() where id=run;
 if jsonb_array_length(private.kakao_service_due(run))<>0 then raise exception 'Late send permitted';end if;
 perform private.kakao_cron_backstop(1435);perform private.kakao_cron_backstop(1435);
 if (select count(*) from public.kakao_multi_batches where day='2030-01-14' and outcome='schedule_missed')<>20 then raise exception 'Backstop duplicate/missing rows';end if;
 if exists(select 1 from net.http_request_queue) then raise exception 'Fixture unexpectedly enqueued network';end if;
end $$;
select 'PASS: 20 distinct times, shared slot, weekdays, time changes, deduplicated cron, KST midnight and no late retries' as result;
