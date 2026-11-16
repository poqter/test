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

do $$declare u uuid;rid uuid;job uuid;batch uuid;run uuid;claim jsonb;n integer;begin
 select id into u from public.profiles where login_id='qa_staff';
 -- New policy is fail-closed for tests until the operator assigns verified room.
 if private.kakao_function_budget_ok('test',true) then raise exception 'Tests enabled by default';end if;
 update public.kakao_multi_function_budgets set monthly_test_budget=3,monthly_shared_budget=32;
 if private.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Underfunded normal+test allocation allowed';end if;
 update public.kakao_multi_function_budgets set monthly_shared_budget=33;
 for n in 1..3 loop
 rid:=gen_random_uuid();
 if public.kakao_service_request_test(u,rid)->>'status'<>'queued' then raise exception 'Explicit test denied';end if;
 if private.kakao_service_tick_enter(rid) then raise exception 'Test ID entered normal budget';end if;
 select public.kakao_test_claim(ticket_hash) into claim from public.kakao_multi_test_requests where id=rid;
 if claim is null then raise exception 'Test claim failed';end if;
 if jsonb_array_length(private.kakao_service_due(rid))<>0 then raise exception 'Test ID authorized normal due';end if;
 if n=1 then
 -- Even a recent valid test run cannot claim a normal job.
 insert into public.kakao_multi_batches(owner_id,day,generation,status,delivery_deadline) values(u,(clock_timestamp() at time zone 'Asia/Seoul')::date,1,'reserved',clock_timestamp()+interval '10 minutes') returning id into batch;
 insert into public.kakao_multi_jobs(batch_id,owner_id,generation,part,body) values(batch,u,1,1,'synthetic') returning id into job;
 if private.kakao_service_claim(job,rid)->>'reason'<>'invalid_run' then raise exception 'Test ID authorized normal claim';end if;
 end if;
 if not public.kakao_test_complete(rid,(claim->>'claim_token')::uuid,'accepted') then raise exception 'Test completion failed';end if;
 end loop;
 if public.kakao_service_request_test(u,gen_random_uuid())->>'reason'<>'function_budget' then raise exception 'Independent test budget not enforced';end if;
 for n in 1..30 loop if not private.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Test consumed normal reservation at %',n;end if;end loop;
 if private.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Normal budget exceeded';end if;
 if (select count(*) from public.kakao_multi_runs where run_kind='test')<>3 or (select count(*) from public.kakao_multi_runs where run_kind='normal')<>30 then raise exception 'Run classification mismatch';end if;
 if not private.kakao_function_budget_ok('normal',false) then raise exception 'Normal final run validation fails due to test usage';end if;
 -- Shared safety cap remains authoritative even if lowered after allocation.
 update public.kakao_multi_function_budgets set monthly_shared_budget=32;
 if private.kakao_function_budget_ok('normal',false) or private.kakao_function_budget_ok('test',false) then raise exception 'Shared cap bypassed';end if;
 if exists(select 1 from baseline b where b.slots is distinct from (select jsonb_agg(to_jsonb(s)) from public.kakao_multi_cron_slots s) or b.prefs is distinct from (select jsonb_agg(to_jsonb(p)) from public.kakao_multi_preferences p)) then raise exception 'Schedule/settings changed';end if;
 if has_function_privilege('authenticated','private.kakao_function_enter(uuid,text)','execute') or has_table_privilege('authenticated','public.kakao_multi_function_budgets','update') then raise exception 'Budget ACL leak';end if;
end $$;
select 'PASS: independent normal30/test3, shared33, no implicit expansion, normal claim/due isolation, normal schedule unchanged' as result;

-- Service role can inspect the ledger but cannot forge/reclassify/delete rows.
set role service_role;
do $$declare bad boolean;rid uuid;begin
 select id into rid from public.kakao_multi_runs limit 1;
 bad:=false;begin insert into public.kakao_multi_runs(id,run_kind) values(gen_random_uuid(),'test');exception when insufficient_privilege then bad:=true;end;
 if not bad then raise exception 'Service role forged ledger';end if;
 bad:=false;begin update public.kakao_multi_runs set run_kind='test' where id=rid;exception when insufficient_privilege then bad:=true;end;
 if not bad then raise exception 'Service role rewrote ledger';end if;
 bad:=false;begin delete from public.kakao_multi_runs where id=rid;exception when insufficient_privilege then bad:=true;end;
 if not bad then raise exception 'Service role deleted ledger';end if;
end $$;
reset role;
-- Even the definer owner cannot rewrite classification; ordinary claim bookkeeping works.
do $$declare rid uuid;bad boolean:=false;begin
 select id into rid from public.kakao_multi_runs where run_kind='normal' limit 1;
 begin update public.kakao_multi_runs set run_kind='test' where id=rid;exception when others then bad:=true;end;
 if not bad then raise exception 'Definer rewrote immutable run kind';end if;
 update public.kakao_multi_runs set claimed_job=(select id from public.kakao_multi_jobs limit 1) where id=rid;
end $$;
-- A fresh funded normal RPC still inserts despite revoked service table-write grants.
update public.kakao_multi_controls set monthly_function_budget=31 where singleton;
update public.kakao_multi_function_budgets set monthly_shared_budget=34;
set role service_role;
do $$begin
 if not public.kakao_service_tick_enter(gen_random_uuid()) then raise exception 'Service RPC no longer enters normal run';end if;
end $$;
reset role;
select 'PASS: immutable classification; service direct writes denied; definer bookkeeping and service normal RPC work' as acl_result;
