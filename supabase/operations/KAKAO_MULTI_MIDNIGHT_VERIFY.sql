-- LOCAL MOCK DB ONLY: harness replaces source clock_timestamp()/now() in temporary SQL copies.
-- Never add test-clock parameters to deployed functions. All fixtures roll back.
begin;
set local test.kakao_clock='2026-11-16 15:02:00+00'; -- Tuesday00:02 KST, Monday23:55 still valid.
create temporary table kakao_midnight_results(name text);
do $$
declare first_owner uuid; first_batch uuid; j1 uuid; j2 uuid; run uuid; items jsonb; item jsonb; reserved jsonb; claim jsonb; summary jsonb; sid uuid:=gen_random_uuid(); n integer:=0;
begin
 if to_regprocedure('private.kakao_test_clock()') is null then raise exception 'Local mock harness required'; end if;
 insert into public.profiles(login_id,display_name) select 'midnight_'||i,'Synthetic Midnight '||i from generate_series(1,27) i;
 insert into public.hwarang_app_access select id,'workspace',true from public.profiles where login_id like 'midnight_%';
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted,updated_at)
 select id,'connected',1,'mock-'||login_id,repeat('cipher',10),true,'2026-11-16 13:00+00'::timestamptz from public.profiles where login_id like 'midnight_%';
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,updated_at)
 select id,true,'23:55',array[1],'2026-11-16 13:00+00'::timestamptz from public.profiles where login_id like 'midnight_%';
 update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=1000,cost_verified_until='2026-11-17 16:00+00';
 run:=gen_random_uuid();perform public.kakao_service_tick_enter(run);items:=public.kakao_service_due(run,25);
 if jsonb_array_length(items)<>25 then raise exception 'After-midnight first page missing'; end if;
 for item in select value from jsonb_array_elements(items) loop
  if item->>'day'<>'2026-11-16' then raise exception 'Scheduled day changed at midnight'; end if;
  reserved:=public.kakao_service_reserve((item->>'owner_id')::uuid,'2026-11-16',1,case when n=0 then array['first','second'] else array['one'] end,item->>'scope_hash');
  if reserved->>'status'<>'reserved' then raise exception 'Previous-day reserve failed: %',reserved; end if;
  if n=0 then first_owner:=(item->>'owner_id')::uuid;first_batch:=(reserved->>'batch_id')::uuid;end if;n:=n+1;
 end loop;
 items:=public.kakao_service_due(run,25);
 if jsonb_array_length(items)<>2 then raise exception 'Users beyond25 lost after midnight'; end if;
 for item in select value from jsonb_array_elements(items) loop
  reserved:=public.kakao_service_reserve((item->>'owner_id')::uuid,(item->>'day')::date,1,array['one'],item->>'scope_hash');
  if reserved->>'status'<>'reserved' then raise exception 'After-midnight second-page reserve failed'; end if;
 end loop;
 insert into kakao_midnight_results values('27 Monday23:55 users reserve Monday batches in25+2 pages at Tuesday00:02');
 if not private.kakao_service_has_work() or jsonb_array_length(public.kakao_service_pending(100))<>28 then raise exception 'Prior-day pending/continuation omitted'; end if;
 select id into j1 from public.kakao_multi_jobs where batch_id=first_batch and part=1;
 select id into j2 from public.kakao_multi_jobs where batch_id=first_batch and part=2;
 run:=gen_random_uuid();perform public.kakao_service_tick_enter(run);claim:=public.kakao_service_claim(j1,run);
 if not coalesce((claim->>'claimed')::boolean,false) or not public.kakao_service_validate_claim(j1,(claim->>'claim_token')::uuid) then raise exception 'Previous-day claim/validate failed'; end if;
 perform public.kakao_service_complete(j1,(claim->>'claim_token')::uuid,'accepted');perform public.kakao_service_expire();
 if (select count(*) from public.kakao_multi_jobs where status='reserved')<>27 then raise exception 'Midnight cleanup cancelled live previous-day jobs'; end if;
 insert into kakao_midnight_results values('Pending/claim/validate/expire preserve previous-day reservations before00:05');
 perform set_config('test.kakao_clock','2026-11-16 15:04:59+00',true);
 run:=gen_random_uuid();perform public.kakao_service_tick_enter(run);claim:=public.kakao_service_claim(j2,run);
 if not public.kakao_service_validate_claim(j2,(claim->>'claim_token')::uuid) then raise exception '00:04:59 rejected'; end if;
 perform set_config('test.kakao_clock','2026-11-16 15:05:00+00',true);
 if public.kakao_service_validate_claim(j2,(claim->>'claim_token')::uuid) then raise exception '00:05 cutoff allowed outbound'; end if;
 perform public.kakao_service_complete(j2,(claim->>'claim_token')::uuid,'failed');perform public.kakao_service_expire();
 if exists(select 1 from public.kakao_multi_jobs where status='reserved') or jsonb_array_length(public.kakao_service_pending(100))<>0 or private.kakao_service_has_work() then raise exception 'Expired jobs drive continuation'; end if;
 if (select status from public.kakao_multi_jobs where id=j1)<>'accepted' then raise exception 'Accepted part overwritten'; end if;
 insert into auth.sessions(id,user_id) values(sid,first_owner);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',first_owner,'role','authenticated','session_id',sid)::text,true);summary:=public.kakao_my_status();
 if summary->>'last_outcome'<>'schedule_missed' or (summary->>'accepted_parts')::int<>1 or (summary->>'total_parts')::int<>2 then raise exception 'Partial counts wrong: %',summary; end if;
 insert into kakao_midnight_results values('00:05 blocks outbound and cancels unsent;1/2 accepted remains visible');
end $$;
select jsonb_agg(name) as passed from kakao_midnight_results;
rollback;
