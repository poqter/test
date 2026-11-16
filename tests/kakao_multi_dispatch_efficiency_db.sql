-- Synthetic local database only. Preserves existing due/deadline/scope/owner guards.
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted) select id,'fake-'||login_id,'fake-cipher','connected',1,true from public.profiles;
update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=100,cost_verified_until=clock_timestamp()+interval '1 day',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick';
do $$begin if to_regclass('public.kakao_multi_function_budgets') is not null then update public.kakao_multi_function_budgets set monthly_shared_budget=100,monthly_test_budget=0;end if;end $$;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled,delivery_time,send_empty,days) select id,'web:1100000000',true,date_trunc('minute',clock_timestamp() at time zone 'Asia/Seoul')::time,true,array[0,1,2,3,4,5,6] from public.profiles;
do $$declare u record;s jsonb;r jsonb;d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;parts text[];pending jsonb;job uuid;other uuid;run uuid;n bigint;begin
 for u in select * from public.profiles loop
 s:=private.kakao_service_snapshot(u.id,d);select array_agg('part '||i) into parts from generate_series(1,30)i;
 r:=private.kakao_service_reserve(u.id,d,1,parts,private.kakao_service_snapshot_hash(s));
 if r->>'status'<>'reserved' then raise exception 'Fixture reserve failed %',r;end if;
 end loop;
 pending:=private.kakao_service_pending(3);
 if jsonb_array_length(pending)<>3 or (select count(distinct x->>'owner_id') from jsonb_array_elements(pending)x)<>3 or exists(select 1 from jsonb_array_elements(pending)x where x->>'part'<>'1' or x->>'atomic_claim'<>'true') then raise exception 'Unfair/invalid advertised pending: %',pending;end if;
 pending:=private.kakao_service_pending(25);
 if exists(select 1 from(select x->>'owner_id' owner,(x->>'part')::integer part,lag((x->>'part')::integer) over(partition by x->>'owner_id' order by a.n) prior from jsonb_array_elements(pending) with ordinality a(x,n)) t where prior is not null and part<>prior+1) then raise exception 'Legacy sequential worker part order changed';end if;
 select j.id into job from public.kakao_multi_jobs j join public.profiles p on p.id=j.owner_id where p.login_id='qa_staff' and j.part=1;
 select j.id into other from public.kakao_multi_jobs j join public.profiles p on p.id=j.owner_id where p.login_id='qa_staff' and j.part=2;
 r:=public.kakao_service_begin_job(other);if r->>'claimed'='true' then raise exception 'Out-of-order begin bypass';end if;
 select count(*) into n from public.kakao_multi_runs;
 r:=public.kakao_service_begin_job(job);if r->>'claimed'<>'true' or (select count(*) from public.kakao_multi_runs)<>n+1 then raise exception 'Combined admission claim failed: %',r;end if;
 if public.kakao_service_begin_job(job)->>'claimed'='true' then raise exception 'Duplicate combined claim';end if;
 if exists(select 1 from jsonb_array_elements(private.kakao_service_pending(100))x where x->>'owner_id'=(select id::text from public.profiles where login_id='qa_staff')) then raise exception 'Sending owner exposed';end if;
 if not private.kakao_service_complete(job,(r->>'claim_token')::uuid,'accepted') then raise exception 'Completion failed';end if;
 -- Old worker two-RPC path still works with the new schema and pending shape.
 run:=gen_random_uuid();if not private.kakao_service_tick_enter(run) then raise exception 'Legacy budget failed';end if;
 r:=private.kakao_service_claim(other,run);if r->>'claimed'<>'true' then raise exception 'Legacy claim path broken';end if;
 -- Cancelled welcome-marker batches remain outside normal pending.
 update public.kakao_multi_batches set status='cancelled' where owner_id=(select id from public.profiles where login_id='qa_manager');
 if exists(select 1 from jsonb_array_elements(private.kakao_service_pending(100))x where x->>'owner_id'=(select id::text from public.profiles where login_id='qa_manager')) then raise exception 'Cancelled welcome marker exposed';end if;
 -- Exhausted admission cannot claim a remaining job or append a budget row.
 select count(*) into n from public.kakao_multi_runs;update public.kakao_multi_controls set monthly_function_budget=n;
 select j.id into job from public.kakao_multi_jobs j join public.profiles p on p.id=j.owner_id where p.login_id='qa_peer' and j.part=1;
 if public.kakao_service_begin_job(job)->>'reason'<>'quota_held' or (select count(*) from public.kakao_multi_runs)<>n or (select status from public.kakao_multi_jobs where id=job)<>'reserved' then raise exception 'Atomic quota guard failed';end if;
 if has_function_privilege('authenticated','public.kakao_service_begin_job(uuid)','execute') or has_function_privilege('anon','private.kakao_service_begin_job(uuid)','execute') then raise exception 'Combined RPC ACL leak';end if;
end $$;
select 'PASS: fair owner pending, same-owner sequence, new atomic and legacy claims, duplicate rejection, cancelled exclusion, quota admission and ACL' as result;
