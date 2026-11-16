-- Preserve existing job IDs; reconcile still runs for every existing safety trigger.
-- Install only the routine: no reconcile, settings update, cron call or network on migration.
begin;
create or replace function private.kakao_cron_reconcile() returns void language plpgsql security definer set search_path='' as $$
declare desired integer[]; target integer; r record; utc_slot integer; utc_backstop integer; dj bigint; bj bigint; gate boolean;
begin
 -- Serializes last-subscriber deletion and concurrent change/add across all user transactions.
 perform pg_advisory_xact_lock(1746948683,20261116);
 if coalesce(current_setting('cron.timezone',true),'GMT') not in ('GMT','UTC') then raise exception 'Cron timezone must be UTC'; end if;
 select coalesce(array_agg(distinct extract(hour from p.delivery_time)::integer*60+extract(minute from p.delivery_time)::integer order by extract(hour from p.delivery_time)::integer*60+extract(minute from p.delivery_time)::integer),'{}'::integer[]) into desired
 from public.kakao_multi_preferences p join public.kakao_multi_connections c using(owner_id)
 where p.enabled and not p.admin_paused and c.status='connected' and c.talk_message_granted and private.kakao_service_owner_active(c.owner_id);
 gate:=coalesce((private.kakao_service_gate()->>'enabled')::boolean,false) and exists(select 1 from public.kakao_multi_controls where singleton and tick_endpoint is not null);
 for r in select * from public.kakao_multi_cron_slots where not slot=any(desired) order by slot loop
  if r.dispatch_job is not null then perform cron.unschedule(r.dispatch_job); end if;
  if r.backstop_job is not null then perform cron.unschedule(r.backstop_job); end if;
  delete from public.kakao_multi_cron_slots where slot=r.slot;
 end loop;
 foreach target in array desired loop
  utc_slot:=(target-540+1440)%1440;utc_backstop:=(target+10-540+1440)%1440;
  select * into r from public.kakao_multi_cron_slots where slot=target;
  dj:=r.dispatch_job;bj:=r.backstop_job;
  if gate then
   if not exists(select 1 from cron.job where jobid=dj and active and jobname='hwarang-kakao-slot-'||target::text and schedule=format('%s %s * * *',utc_slot%60,utc_slot/60) and command=format('select private.kakao_cron_dispatch(%s);',target)) then
   dj:=cron.schedule('hwarang-kakao-slot-'||target::text,format('%s %s * * *',utc_slot%60,utc_slot/60),format('select private.kakao_cron_dispatch(%s);',target));
   end if;
  else
   if dj is not null then perform cron.unschedule(dj); end if;dj:=null;
  end if;
  if not exists(select 1 from cron.job where jobid=bj and active and jobname='hwarang-kakao-backstop-'||target::text and schedule=format('%s %s * * *',utc_backstop%60,utc_backstop/60) and command=format('select private.kakao_cron_backstop(%s);',target)) then
  bj:=cron.schedule('hwarang-kakao-backstop-'||target::text,format('%s %s * * *',utc_backstop%60,utc_backstop/60),format('select private.kakao_cron_backstop(%s);',target));
  end if;
  if r.slot is null then
   insert into public.kakao_multi_cron_slots(slot,dispatch_job,backstop_job) values(target,dj,bj);
  elsif r.dispatch_job is distinct from dj or r.backstop_job is distinct from bj then
   update public.kakao_multi_cron_slots set dispatch_job=dj,backstop_job=bj where slot=target;
  end if;
 end loop;
end $$;
commit;
