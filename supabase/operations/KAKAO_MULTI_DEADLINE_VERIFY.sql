-- LOCAL SYNTHETIC/MOCK DB ONLY. No external API. Rollback all fixture changes.
begin;
create temporary table kakao_deadline_results(name text);
do $$ declare u uuid; sid uuid:=gen_random_uuid(); run uuid:=gen_random_uuid(); d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date;
 snap jsonb; b jsonb; j1 uuid; j2 uuid; claim jsonb; projection jsonb;
begin
 select id into u from public.profiles where login_id='qa_staff';
 insert into auth.sessions(id,user_id) values(sid,u);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',u,'role','authenticated','session_id',sid)::text,true);
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted) values(u,'connected',1,'900000000077',repeat('dummy',10),true);
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time) values(u,true,to_char(clock_timestamp() at time zone 'Asia/Seoul','HH24:MI')::time);
 update public.kakao_multi_controls set enabled=true,monthly_message_budget=100,monthly_function_budget=100,cost_verified_until=clock_timestamp()+interval '1 hour';
 snap:=private.kakao_service_snapshot(u,d);
 b:=public.kakao_service_reserve(u,d,1,array['part one','part two'],private.kakao_service_snapshot_hash(snap));
 if b->>'status'<>'reserved' then raise exception 'Reservation failed %',b; end if;
 select id into j1 from public.kakao_multi_jobs where batch_id=(b->>'batch_id')::uuid and part=1;
 select id into j2 from public.kakao_multi_jobs where batch_id=(b->>'batch_id')::uuid and part=2;
 perform public.kakao_service_tick_enter(run);
 claim:=public.kakao_service_claim(j1,run);
 if not coalesce((claim->>'claimed')::boolean,false) then raise exception 'Claim failed'; end if;
 if not public.kakao_service_validate_claim(j1,(claim->>'claim_token')::uuid) then raise exception 'Premature cutoff'; end if;
 update public.kakao_multi_batches set delivery_deadline=clock_timestamp()+interval '100 milliseconds' where id=(b->>'batch_id')::uuid;
 perform pg_sleep(0.2);
 if public.kakao_service_validate_claim(j1,(claim->>'claim_token')::uuid) then raise exception 'Expired claim allowed'; end if;
 insert into kakao_deadline_results values('Claim valid before cutoff and denied after cutoff');
 -- Simulate already-in-flight request accepted after cutoff; do not erase true acceptance.
 if not public.kakao_service_complete(j1,(claim->>'claim_token')::uuid,'accepted') then raise exception 'Acceptance lost'; end if;
 if (select status from public.kakao_multi_jobs where id=j1)<>'accepted' then raise exception 'Accepted part overwritten'; end if;
 if (select status from public.kakao_multi_jobs where id=j2)<>'cancelled' then raise exception 'Unsent tail not expired'; end if;
 projection:=public.kakao_my_status();
 if projection->>'last_outcome'<>'schedule_missed' or (projection->>'accepted_parts')::int<>1 or (projection->>'total_parts')::int<>2 then raise exception 'Partial outcome wrong: %',projection; end if;
 insert into kakao_deadline_results values('In-flight acceptance preserved; only unsent tail expires; UI sees 1/2 partial');
 perform public.kakao_service_tick_enter(gen_random_uuid());
 if exists(select 1 from jsonb_array_elements(public.kakao_service_pending(25)) x where x->>'id'=j2::text) then raise exception 'Expired tail returned for retry'; end if;
 insert into kakao_deadline_results values('Expired tail excluded from retry/next slot work');
end $$;
select jsonb_agg(name) as passed from kakao_deadline_results;
rollback;
