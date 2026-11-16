-- STAGING ONLY after MISSED_PATCH. All fixtures and mutations roll back, no external calls.
-- Run after 00:11 Asia/Seoul so today's 00:00 slot can be tested without changing server time.
begin;
create temporary table kakao_missed_fixture(owner_id uuid,peer_id uuid,manager_id uuid,user_session uuid,manager_session uuid);
create temporary table kakao_missed_results(name text);
grant select on kakao_missed_fixture to authenticated;
grant insert,select on kakao_missed_results to authenticated;
do $$ declare u uuid; v uuid; m uuid; sid uuid:=gen_random_uuid(); msid uuid:=gen_random_uuid(); d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date; begin
 if (clock_timestamp() at time zone 'Asia/Seoul')::time<'00:11'::time then raise exception 'Run missed test after 00:11 KST'; end if;
 select id into u from public.profiles where login_id='qa_staff';
 select id into v from public.profiles where login_id='qa_peer';
 select id into m from public.profiles where login_id='qa_manager';
 if u is null or v is null or m is null then raise exception 'Synthetic fixtures missing'; end if;
 insert into auth.sessions(id,user_id) values(sid,u),(msid,m);
 insert into kakao_missed_fixture values(u,v,m,sid,msid);
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted,updated_at)
 values(u,'connected',1,'900000000071',repeat('synthetic-cipher',4),true,(d::timestamp at time zone 'Asia/Seoul')-interval '1 hour'),
 (v,'connected',1,'900000000072',repeat('synthetic-cipher',4),true,clock_timestamp())
 on conflict(owner_id) do update set status=excluded.status,generation=excluded.generation,account_id=excluded.account_id,encrypted_tokens=excluded.encrypted_tokens,talk_message_granted=true,updated_at=excluded.updated_at;
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,admin_paused,updated_at)
 values(u,true,'00:00',array[0,1,2,3,4,5,6],false,(d::timestamp at time zone 'Asia/Seoul')-interval '1 hour'),
 (v,true,'00:00',array[0,1,2,3,4,5,6],false,clock_timestamp())
 on conflict(owner_id) do update set enabled=true,delivery_time=excluded.delivery_time,days=excluded.days,admin_paused=false,updated_at=excluded.updated_at;
 update public.kakao_multi_controls set enabled=false;
 -- Yesterday's accepted status must not hide today's missed zero-job batch.
 insert into public.kakao_multi_batches(owner_id,day,generation,status,outcome,completed_at) values(u,d-1,1,'accepted','api_accepted',clock_timestamp()-interval '1 day');
 perform public.kakao_service_expire();
 perform public.kakao_service_expire();
 if (select count(*) from public.kakao_multi_batches where owner_id=u and day=d and outcome='schedule_missed' and status='failed')<>1 then raise exception 'Missing/duplicated missed record'; end if;
 if exists(select 1 from public.kakao_multi_batches where owner_id=v and day=d) then raise exception 'New after-slot subscriber falsely marked missed'; end if;
 if exists(select 1 from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id where b.owner_id=u and b.day=d) then raise exception 'Missed slot created sendable messages'; end if;
 insert into kakao_missed_results values('Missed existing subscription recorded once without jobs; new after-slot subscription excluded');
end $$;
set local role authenticated;
select set_config('request.jwt.claims',(select jsonb_build_object('sub',owner_id,'role','authenticated','session_id',user_session)::text from kakao_missed_fixture),true);
do $$ declare r jsonb; begin
 r:=public.kakao_my_status();
 if r->>'last_outcome'<>'schedule_missed' or r->>'today_outcome'<>'schedule_missed' or r->>'last_attempt_at' is not null then raise exception 'Own missed status absent or falsely reports attempt'; end if;
 insert into kakao_missed_results values('Own authenticated status shows today missed, not yesterday accepted, with no attempt timestamp');
end $$;
select set_config('request.jwt.claims',(select jsonb_build_object('sub',manager_id,'role','authenticated','session_id',manager_session)::text from kakao_missed_fixture),true);
do $$ declare r jsonb; u uuid; begin
 select owner_id into u from kakao_missed_fixture;
 select value into r from jsonb_array_elements(public.kakao_admin_status()) where value->>'owner_id'=u::text;
 if r is null or r->>'today_outcome'<>'schedule_missed' or r->>'last_attempt_at' is not null then raise exception 'Scoped manager missing missed status'; end if;
 insert into kakao_missed_results values('Scoped manager sees missed today without message content or a false send attempt');
end $$;
reset role;
select jsonb_agg(name) as passed from kakao_missed_results;
rollback;
