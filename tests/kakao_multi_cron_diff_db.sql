-- Local PostgreSQL with recording cron/net stubs only.
alter table cron.job add column active boolean not null default true;
create or replace function cron.schedule(p_name text,p_schedule text,p_command text) returns bigint language plpgsql as $$declare i bigint;begin insert into cron.job(jobname,schedule,command) values(p_name,p_schedule,p_command) on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,active=true returning jobid into i;return i;end $$;
create table cron.audit(action text,jobname text);
alter function cron.schedule(text,text,text) rename to schedule_impl;
create function cron.schedule(p_name text,p_schedule text,p_command text) returns bigint language plpgsql as $$begin insert into cron.audit values('schedule',p_name);return cron.schedule_impl(p_name,p_schedule,p_command);end $$;
alter function cron.unschedule(bigint) rename to unschedule_impl;
create function cron.unschedule(p_id bigint) returns boolean language plpgsql as $$begin insert into cron.audit select 'unschedule',jobname from cron.job where jobid=p_id;return cron.unschedule_impl(p_id);end $$;
insert into public.profiles(login_id,display_name) select 'diff_'||i,'Synthetic '||i from generate_series(0,19)i;
insert into public.hwarang_app_access select id,'workspace',true from public.profiles where login_id like 'diff_%';
insert into public.kakao_multi_connections(owner_id,account_id,encrypted_tokens,status,generation,talk_message_granted) select id,'fake-'||login_id,'fake-cipher','connected',1,true from public.profiles where login_id like 'diff_%';
update public.kakao_multi_controls set enabled=true,monthly_message_budget=1000,monthly_function_budget=2000,cost_verified_until=now()+interval '1 day',tick_endpoint='https://fake.supabase.co/functions/v1/hwarang-kakao/tick' where singleton;
insert into public.kakao_multi_preferences(owner_id,weather_region_key,enabled,delivery_time) select id,'web:1100000000',true,make_time(substring(login_id from 6)::integer,0,0) from public.profiles where login_id like 'diff_%';
create temporary table initial_jobs as select * from cron.job;
do $$begin if (select count(*) from cron.job)<>40 or (select count(*) from cron.audit)<>40 then raise exception '20 distinct slots not scheduled once';end if;end $$;
truncate cron.audit;
-- No-op, weekday, empty-day and weather changes never write cron when slot set is unchanged.
update public.kakao_multi_preferences set enabled=enabled;
update public.kakao_multi_preferences set days=array[1,2,3],send_empty=not send_empty;
update public.kakao_multi_preferences set weather_region_key=null;
update public.kakao_multi_preferences set weather_region_key='web:1100000000';
select private.kakao_cron_reconcile();select private.kakao_cron_reconcile();
do $$begin if exists(select 1 from cron.audit) or exists((select * from initial_jobs except select * from cron.job) union all (select * from cron.job except select * from initial_jobs)) then raise exception 'Unchanged slots rewritten';end if;end $$;
-- One changed owner/time updates only its old and new pairs (unrelated 08:00 ID stays).
update public.kakao_multi_preferences set delivery_time='23:55' where owner_id=(select id from public.profiles where login_id='diff_0');
do $$begin
 if (select count(*) from cron.audit where action='schedule')<>2 or (select count(*) from cron.audit where action='unschedule')<>2 then raise exception 'Single time change rewrote unrelated slots';end if;
 if not exists(select 1 from cron.job j join initial_jobs b using(jobid) where j.jobname='hwarang-kakao-slot-480' and to_jsonb(j)=to_jsonb(b)) then raise exception 'Existing 08:00 job changed';end if;
 if not exists(select 1 from cron.job where jobname='hwarang-kakao-backstop-1435' and schedule='5 15 * * *') then raise exception 'Midnight UTC conversion wrong';end if;
end $$;
truncate cron.audit;
update public.kakao_multi_preferences set enabled=false where owner_id=(select id from public.profiles where login_id='diff_0');
do $$begin if (select count(*) from cron.audit)<>2 then raise exception 'Owner OFF changed wrong slots';end if;end $$;
truncate cron.audit;
update public.kakao_multi_preferences set enabled=true where owner_id=(select id from public.profiles where login_id='diff_0');
do $$begin if (select count(*) from cron.audit)<>2 then raise exception 'Owner ON changed wrong slots';end if;end $$;
-- Shared minute uses existing 08:00 pair without re-registering it.
truncate cron.audit;
update public.kakao_multi_preferences set delivery_time='08:00';
do $$begin if (select count(*) from cron.job)<>2 or (select count(*) from cron.audit where action='schedule')<>0 or (select count(*) from cron.audit where action='unschedule')<>38 then raise exception 'Shared slot merge wrong';end if;end $$;
truncate cron.audit;
update public.kakao_multi_preferences set enabled=false where owner_id=(select id from public.profiles where login_id='diff_1');
update public.kakao_multi_preferences set enabled=true where owner_id=(select id from public.profiles where login_id='diff_1');
update public.kakao_multi_connections set status='revoked' where owner_id=(select id from public.profiles where login_id='diff_1');
update public.kakao_multi_connections set status='connected' where owner_id=(select id from public.profiles where login_id='diff_1');
do $$begin if exists(select 1 from cron.audit) then raise exception 'Shared owner toggles rewrote schedule';end if;end $$;
-- Gate transition changes dispatch only, retains the exact backstop job.
create temporary table shared_jobs as select * from cron.job;
truncate cron.audit;
update public.kakao_multi_controls set enabled=false;
do $$begin if (select count(*) from cron.audit)<>1 or exists(select 1 from cron.job where jobname='hwarang-kakao-slot-480') then raise exception 'Gate OFF dispatch not removed';end if;end $$;
truncate cron.audit;
update public.kakao_multi_controls set enabled=false;
do $$begin if exists(select 1 from cron.audit) then raise exception 'Repeated gate OFF wrote cron';end if;end $$;
update public.kakao_multi_controls set enabled=true;
do $$begin
 if (select count(*) from cron.audit)<>1 then raise exception 'Gate ON changed more than dispatch';end if;
 if not exists(select 1 from cron.job j join shared_jobs b using(jobid) where j.jobname='hwarang-kakao-backstop-480' and to_jsonb(j)=to_jsonb(b)) then raise exception 'Gate toggle replaced backstop';end if;
 if exists(select 1 from net.http_request_queue) then raise exception 'Unexpected network enqueue';end if;
end $$;
truncate cron.audit;
select 'PASS: 20 distinct/shared slots, unchanged saves zero cron writes, one-owner edits, ON/OFF, gate, midnight, 08:00 ID retention' as result;

-- Reconciliation repairs disabled jobs, not merely matching metadata.
update cron.job set active=false;
select private.kakao_cron_reconcile();
do $$begin if (select count(*) from cron.audit where action='schedule')<>2 or exists(select 1 from cron.job where not active) then raise exception 'Inactive cron job not repaired';end if;end $$;
truncate cron.audit;

-- Last-subscriber consent/revocation signals still remove all obsolete schedules.
update public.kakao_multi_connections set talk_message_granted=false,status='revoked';
do $$begin if exists(select 1 from cron.job) or (select count(*) from cron.audit where action='unschedule')<>2 then raise exception 'Consent revocation failed to remove slots';end if;end $$;
truncate cron.audit;
update public.kakao_multi_connections set talk_message_granted=true,status='connected';
do $$begin if (select count(*) from cron.job)<>2 or (select count(*) from cron.audit where action='schedule')<>2 then raise exception 'Consent restoration failed to create slot';end if;end $$;
truncate cron.audit;
update public.kakao_multi_preferences set admin_paused=true;
do $$begin if exists(select 1 from cron.job) then raise exception 'Admin pause left schedule active';end if;end $$;
update public.kakao_multi_preferences set admin_paused=false;
truncate cron.audit;
