-- LOCAL MOCK DB ONLY (pg_cron/pg_net functions stubbed). All mutations ROLLBACK.
-- Expected standard cron.job(jobid,jobname,schedule,command) mock; no real scheduler/network.
begin;
create temporary table kakao_dynamic_results(name text);
do $$ declare u uuid; v uuid; d date:=(clock_timestamp() at time zone 'Asia/Seoul')::date; t text:=repeat('a',64); n integer; r record; begin
 select id into u from public.profiles where login_id='qa_staff';
 select id into v from public.profiles where login_id='qa_peer';
 if u is null or v is null then raise exception 'Synthetic QA profiles required'; end if;
 update public.kakao_multi_controls set enabled=false,tick_endpoint=null;
 insert into public.kakao_multi_connections(owner_id,status,generation,account_id,encrypted_tokens,talk_message_granted,updated_at)
 values(u,'connected',1,'900000000081',repeat('cipher',10),true,(d::timestamp at time zone 'Asia/Seoul')-interval '2 days'),
 (v,'connected',1,'900000000082',repeat('cipher',10),true,(d::timestamp at time zone 'Asia/Seoul')-interval '2 days')
 on conflict(owner_id) do update set status='connected',account_id=excluded.account_id,encrypted_tokens=excluded.encrypted_tokens,talk_message_granted=true,updated_at=excluded.updated_at;
 insert into public.kakao_multi_preferences(owner_id,enabled,delivery_time,days,admin_paused,updated_at)
 values(u,true,'08:00',array[0,1,2,3,4,5,6],false,(d::timestamp at time zone 'Asia/Seoul')-interval '2 days'),
 (v,true,'08:00',array[0,1,2,3,4,5,6],false,(d::timestamp at time zone 'Asia/Seoul')-interval '2 days')
 on conflict(owner_id) do update set enabled=true,delivery_time='08:00',days=excluded.days,admin_paused=false,updated_at=excluded.updated_at;
 if (select count(*) from public.kakao_multi_cron_slots where slot=480)<>1 then raise exception 'Same-time slot not shared'; end if;
 if exists(select 1 from public.kakao_multi_cron_slots where dispatch_job is not null) then raise exception 'Gate off scheduled network dispatch'; end if;
 if private.kakao_service_enqueue_tick(gen_random_uuid(),0) then raise exception 'Gate off enqueued network'; end if;
 insert into kakao_dynamic_results values('Same HHMM shares one slot; gateOFF no dispatch job/request');
 update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=1000,cost_verified_until=clock_timestamp()+interval '1 hour',tick_endpoint='https://example.supabase.co/functions/v1/hwarang-kakao/tick';
 select c.schedule into t from cron.job c join public.kakao_multi_cron_slots s on s.dispatch_job=c.jobid where s.slot=480;
 if t<>'0 23 * * *' then raise exception '08:00 KST incorrectly mapped: %',t; end if;
 select c.schedule into t from cron.job c join public.kakao_multi_cron_slots s on s.backstop_job=c.jobid where s.slot=480;
 if t<>'10 23 * * *' then raise exception '08:10 KST incorrectly mapped'; end if;
 if exists(select 1 from cron.job c join public.kakao_multi_cron_slots s on c.jobid in(s.dispatch_job,s.backstop_job) where c.schedule='* * * * *') then raise exception 'Minute polling introduced'; end if;
 insert into kakao_dynamic_results values('UTC mapping 08:00->23:00, backstop08:10->23:10, no minute polling');
 update public.kakao_multi_preferences set enabled=false where owner_id=u;
 if not exists(select 1 from public.kakao_multi_cron_slots where slot=480) then raise exception 'First unsubscribe deleted shared slot'; end if;
 update public.kakao_multi_preferences set enabled=false where owner_id=v;
 if exists(select 1 from public.kakao_multi_cron_slots where slot=480) then raise exception 'Last unsubscribe left orphan slot'; end if;
 insert into kakao_dynamic_results values('Slot retained until last subscriber leaves');
 update public.kakao_multi_preferences set enabled=true,delivery_time='23:55',days=array[extract(dow from d-1)::integer],updated_at=(d::timestamp at time zone 'Asia/Seoul')-interval '2 days' where owner_id=u;
 update public.kakao_multi_preferences set enabled=true,delivery_time='23:55',days=array[extract(dow from d)::integer],updated_at=(d::timestamp at time zone 'Asia/Seoul')-interval '2 days' where owner_id=v;
 select c.schedule into t from cron.job c join public.kakao_multi_cron_slots s on s.backstop_job=c.jobid where s.slot=1435;
 if t<>'5 15 * * *' then raise exception 'Midnight wrap backstop wrong: %',t; end if;
 if (clock_timestamp() at time zone 'Asia/Seoul')::time>='00:05'::time then
  perform private.kakao_cron_backstop(1435);
  if not exists(select 1 from public.kakao_multi_batches where owner_id=u and day=d-1 and outcome='schedule_missed') then raise exception 'Prior-day midnight miss omitted'; end if;
  if exists(select 1 from public.kakao_multi_batches where owner_id=v and day=d-1) then raise exception 'Wrong weekday counted missed'; end if;
  insert into kakao_dynamic_results values('23:55+10min midnight wrap records prior day only for selected weekday');
 end if;
 insert into public.kakao_multi_tick_tickets(ticket_hash,expires_at,used_at) values(repeat('f',64),clock_timestamp()+interval '2 minutes',clock_timestamp());
 if public.kakao_service_continue(repeat('f',64),false) then raise exception 'No-progress tick continued'; end if;
 if not exists(select 1 from public.kakao_multi_tick_tickets where ticket_hash=repeat('f',64) and continued_at is not null) then raise exception 'No-progress parent not settled'; end if;
 if public.kakao_service_continue(repeat('f',64),true) then raise exception 'Settled parent reused'; end if;
 insert into kakao_dynamic_results values('No-progress settled once; same parent cannot later start another child');
end $$;
select jsonb_agg(name) as passed from kakao_dynamic_results;
rollback;
