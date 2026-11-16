-- REVIEW DRAFT ONLY: replaces minute polling. Requires pg_cron, pg_net and TICKET_PATCH.
-- No secret, owner identifier, message body or persistent key is embedded in cron commands.
-- cron.timezone MUST be GMT/UTC; Korea slots are converted to UTC explicitly.
begin;
alter table public.kakao_multi_batches add column if not exists delivery_deadline timestamptz;
alter table public.kakao_multi_controls add column tick_endpoint text;
alter table public.kakao_multi_controls add constraint kakao_multi_tick_endpoint_check
 check(tick_endpoint is null or tick_endpoint ~ '^https://[a-z0-9]+\.supabase\.co/functions/v1/hwarang-kakao/tick$');
alter table public.kakao_multi_tick_tickets add column chain_id uuid not null default gen_random_uuid(),
 add column hop bigint not null default 0 check(hop>=0), add column continued_at timestamptz;
create table public.kakao_multi_cron_slots (
 slot integer primary key check(slot between 0 and 1439), dispatch_job bigint, backstop_job bigint
);
alter table public.kakao_multi_cron_slots enable row level security;
revoke all on public.kakao_multi_cron_slots from public,anon,authenticated;
grant select,insert,update,delete on public.kakao_multi_cron_slots to service_role;

-- All recurring network schedules call this fixed routine with a server-generated integer slot.
create function private.kakao_service_has_work() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_connections c join public.kakao_multi_preferences p using(owner_id)
 cross join lateral (values((clock_timestamp() at time zone 'Asia/Seoul')::date),((clock_timestamp() at time zone 'Asia/Seoul')::date-1)) dates(scheduled_day)
 where c.status='connected' and c.talk_message_granted and p.enabled and not p.admin_paused and private.kakao_service_owner_active(c.owner_id)
 and extract(dow from dates.scheduled_day)::integer=any(p.days)
 and (clock_timestamp() at time zone 'Asia/Seoul')>=(dates.scheduled_day+p.delivery_time)
 and (clock_timestamp() at time zone 'Asia/Seoul')<(dates.scheduled_day+p.delivery_time)+interval '10 minutes'
 and not exists(select 1 from public.kakao_multi_batches b where b.owner_id=c.owner_id and b.day=dates.scheduled_day))
 or exists(select 1 from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id where j.status='reserved' and b.delivery_deadline is not null and clock_timestamp()<b.delivery_deadline and b.status in ('reserved','sending') and b.day between (clock_timestamp() at time zone 'Asia/Seoul')::date-1 and (clock_timestamp() at time zone 'Asia/Seoul')::date
 and not exists(select 1 from public.kakao_multi_jobs busy where busy.owner_id=j.owner_id and busy.status='sending')
 and not exists(select 1 from public.kakao_multi_jobs prior where prior.batch_id=j.batch_id and prior.part<j.part and prior.status<>'accepted'))
$$;
create function private.kakao_service_enqueue_tick(p_chain uuid,p_hop bigint) returns boolean language plpgsql security definer set search_path='' as $$
declare ctl public.kakao_multi_controls; ticket text; request_id bigint;
begin
 select * into ctl from public.kakao_multi_controls where singleton for update;
 if not found or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false) or ctl.tick_endpoint is null
 or p_chain is null or p_hop is null or p_hop<0 or not private.kakao_service_has_work() then return false; end if;
 -- Local worker invocation budget; not a guarantee about provider-wide requests/charges.
 if (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>=ctl.monthly_function_budget then return false; end if;
 ticket:=encode(extensions.gen_random_bytes(32),'hex');
 insert into public.kakao_multi_tick_tickets(ticket_hash,expires_at,chain_id,hop)
 values(encode(extensions.digest(ticket,'sha256'),'hex'),clock_timestamp()+interval '2 minutes',p_chain,p_hop);
 request_id:=net.http_post(url:=ctl.tick_endpoint,headers:='{"Content-Type":"application/json"}'::jsonb,
 body:=jsonb_build_object('ticket',ticket),timeout_milliseconds:=60000);
 return request_id is not null;
end $$;
create function private.kakao_cron_dispatch(p_slot integer) returns boolean language plpgsql security definer set search_path='' as $$
declare local_now timestamp:=clock_timestamp() at time zone 'Asia/Seoul';
begin
 if p_slot is null or p_slot not between 0 and 1439 then return false; end if;
 -- Recurring dispatch is allowed only at its own minute, never as a late replay.
 if extract(hour from local_now)::integer*60+extract(minute from local_now)::integer<>p_slot then return false; end if;
 if not exists(select 1 from public.kakao_multi_cron_slots where slot=p_slot and dispatch_job is not null) then return false; end if;
 return private.kakao_service_enqueue_tick(gen_random_uuid(),0);
end $$;
create function private.kakao_service_continue(p_tick_hash text,p_progress boolean default false) returns boolean language plpgsql security definer set search_path='' as $$
declare t public.kakao_multi_tick_tickets; ctl public.kakao_multi_controls; result boolean;
begin
 -- Same controls-first order as enqueue; claims are once per consumed tick.
 select * into ctl from public.kakao_multi_controls where singleton for update;
 select * into t from public.kakao_multi_tick_tickets where ticket_hash=p_tick_hash for update;
 if not found or t.used_at is null or t.continued_at is not null or t.created_at<=clock_timestamp()-interval '2 minutes' then return false; end if;
 update public.kakao_multi_tick_tickets set continued_at=clock_timestamp() where ticket_hash=p_tick_hash;
 if p_progress is distinct from true then return false; end if;
 result:=private.kakao_service_enqueue_tick(t.chain_id,t.hop+1);
 return result;
end $$;
create function public.kakao_service_continue(p_tick_hash text,p_progress boolean default false) returns boolean language sql security invoker set search_path='' as $$ select private.kakao_service_continue(p_tick_hash,p_progress) $$;

-- DB-only backstop records current/prior-day zero-reservation misses, including midnight wrap.
create function private.kakao_cron_backstop(p_slot integer) returns integer language plpgsql security definer set search_path='' as $$
declare at_time timestamptz:=clock_timestamp(); d date; added integer:=0; total integer:=0; target_time time;
begin
 if p_slot is null or p_slot not between 0 and 1439 then return 0; end if;
 perform private.kakao_service_expire();
 target_time:=make_time(p_slot/60,p_slot%60,0);
 -- Lock the union of today's/yesterday's affected owners once in stable order.
 perform c.owner_id from public.kakao_multi_connections c join public.kakao_multi_preferences p using(owner_id)
 where p.delivery_time=target_time and exists(
 select 1 from (values((at_time at time zone 'Asia/Seoul')::date),((at_time at time zone 'Asia/Seoul')::date-1)) dates(day)
 where at_time>=((dates.day+target_time) at time zone 'Asia/Seoul')+interval '10 minutes')
 order by c.owner_id for update of c;
 for d in select (at_time at time zone 'Asia/Seoul')::date union all select (at_time at time zone 'Asia/Seoul')::date-1 loop
  insert into public.kakao_multi_batches(owner_id,day,generation,delivery_deadline,status,outcome,completed_at)
  select c.owner_id,d,c.generation,((d+target_time) at time zone 'Asia/Seoul')+interval '10 minutes','failed','schedule_missed',at_time from public.kakao_multi_connections c join public.kakao_multi_preferences p using(owner_id)
  where p.delivery_time=target_time and c.status='connected' and c.talk_message_granted and p.enabled and not p.admin_paused
  and private.kakao_service_owner_active(c.owner_id) and extract(dow from d)::integer=any(p.days)
  and at_time>=((d+target_time) at time zone 'Asia/Seoul')+interval '10 minutes'
  and p.updated_at<=((d+target_time) at time zone 'Asia/Seoul') and c.updated_at<=((d+target_time) at time zone 'Asia/Seoul')
  on conflict(owner_id,day) do nothing;
  get diagnostics added=row_count;total:=total+added;
 end loop;
 return total;
end $$;

create function private.kakao_cron_reconcile() returns void language plpgsql security definer set search_path='' as $$
declare desired integer[]; target integer; r record; utc_slot integer; utc_backstop integer; dj bigint; bj bigint; gate boolean;
begin
 -- Serializes last-subscriber deletion and concurrent change/add across all user transactions.
 perform pg_advisory_xact_lock(1746948683,20261116);
 if coalesce(current_setting('cron.timezone',true),'GMT') not in ('GMT','UTC') then raise exception 'Cron timezone must be UTC'; end if;
 select coalesce(array_agg(distinct extract(hour from p.delivery_time)::integer*60+extract(minute from p.delivery_time)::integer),'{}'::integer[]) into desired
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
  dj:=null;
  if gate then
   dj:=cron.schedule('hwarang-kakao-slot-'||target::text,format('%s %s * * *',utc_slot%60,utc_slot/60),format('select private.kakao_cron_dispatch(%s);',target));
  else
   select dispatch_job into dj from public.kakao_multi_cron_slots where slot=target;
   if dj is not null then perform cron.unschedule(dj); end if;dj:=null;
  end if;
  bj:=cron.schedule('hwarang-kakao-backstop-'||target::text,format('%s %s * * *',utc_backstop%60,utc_backstop/60),format('select private.kakao_cron_backstop(%s);',target));
  insert into public.kakao_multi_cron_slots(slot,dispatch_job,backstop_job) values(target,dj,bj)
  on conflict(slot) do update set dispatch_job=excluded.dispatch_job,backstop_job=excluded.backstop_job;
 end loop;
end $$;
create function private.kakao_cron_sync_trigger() returns trigger language plpgsql security definer set search_path='' as $$
begin perform private.kakao_cron_reconcile();return null;end $$;
create trigger kakao_prefs_schedule_sync after insert or update or delete on public.kakao_multi_preferences for each statement execute function private.kakao_cron_sync_trigger();
create trigger kakao_connections_schedule_sync after insert or update of status,generation,talk_message_granted or delete on public.kakao_multi_connections for each statement execute function private.kakao_cron_sync_trigger();
create trigger kakao_controls_schedule_sync after update on public.kakao_multi_controls for each statement execute function private.kakao_cron_sync_trigger();
create trigger kakao_exclusions_schedule_sync after insert or update or delete on public.kakao_multi_exclusions for each statement execute function private.kakao_cron_sync_trigger();
-- Optional daily DB-only maintenance, explicitly installed by the operator after staging verification:
-- select cron.schedule('hwarang-kakao-daily-cleanup','15 15 * * *',
-- 'select private.kakao_service_expire(); delete from public.kakao_multi_tick_tickets where expires_at<clock_timestamp()-interval ''1 day''; select private.kakao_cron_reconcile();');

create or replace function private.kakao_my_status() returns jsonb language plpgsql volatile security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 -- Authenticated owner's abandoned confirmation expires even when delivery gate is OFF.
 update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
 confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
 where owner_id=u and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 if found then update public.kakao_multi_preferences set enabled=false,updated_at=clock_timestamp() where owner_id=u; end if;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where owner_id=u and expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 select jsonb_build_object('connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0),
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=u order by b.day desc,b.created_at desc limit 1) j on true;
 return result;
end $$;

create or replace function private.kakao_admin_status() returns jsonb language plpgsql stable security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 select coalesce(jsonb_agg(jsonb_build_object('owner_id',s.member,'label',s.label,'connection_status',coalesce(c.status,'disconnected'),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,'accepted_parts',coalesce(j.accepted_parts,0),'total_parts',coalesce(j.total_parts,0)) order by s.label),'[]'::jsonb)
 into result from private.sales_scope_for(u,false) s
 left join public.kakao_multi_connections c on c.owner_id=s.member
 left join public.kakao_multi_preferences p on p.owner_id=s.member
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id and z.status='accepted') accepted_parts,
 (select count(*) from public.kakao_multi_jobs z where z.batch_id=b.id) total_parts from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=s.member order by b.day desc,b.created_at desc limit 1) j on true
 where s.managed and s.member<>u;
 return result;
end $$;

create or replace function private.kakao_service_reserve(p_owner uuid,p_day date,p_generation bigint,p_parts text[],p_scope_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare ctl public.kakao_multi_controls; c public.kakao_multi_connections; pref public.kakao_multi_preferences;
 summary jsonb; bid uuid; used bigint; local_now timestamp:=clock_timestamp() at time zone 'Asia/Seoul'; n integer;
begin
 if p_day is null or p_day not in (local_now::date,local_now::date-1) or p_generation is null or p_scope_hash is null then return jsonb_build_object('status','invalid'); end if;
 select * into ctl from public.kakao_multi_controls where singleton for update;
 if not found or not ctl.enabled or ctl.cost_verified_until is null or ctl.cost_verified_until<=clock_timestamp() or ctl.monthly_message_budget<=0 or ctl.monthly_function_budget<=0 then return jsonb_build_object('status','disabled'); end if;
 select * into c from public.kakao_multi_connections where owner_id=p_owner for update;
 if not found or c.generation<>p_generation or c.status<>'connected' or not c.talk_message_granted or not private.kakao_service_owner_active(p_owner) then return jsonb_build_object('status','inactive'); end if;
 select * into pref from public.kakao_multi_preferences where owner_id=p_owner;
 if not found or not pref.enabled or pref.admin_paused or not extract(dow from p_day)::integer=any(pref.days)
 or local_now<p_day+pref.delivery_time or local_now>=p_day+pref.delivery_time+interval '10 minutes' then return jsonb_build_object('status','not_due'); end if;
 if exists(select 1 from public.kakao_multi_batches where owner_id=p_owner and day=p_day) then return jsonb_build_object('status','already_reserved'); end if;
 summary:=private.kakao_service_snapshot(p_owner,p_day);
 if summary is null or private.kakao_service_snapshot_hash(summary) is distinct from p_scope_hash then return jsonb_build_object('status','scope_changed'); end if;
 if jsonb_array_length(summary->'events')=0 and not pref.send_empty then
  insert into public.kakao_multi_batches(owner_id,day,generation,scope_hash,delivery_deadline,status,outcome,completed_at) values(p_owner,p_day,p_generation,p_scope_hash,((p_day+pref.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes','cancelled','empty_day_skipped',clock_timestamp()) returning id into bid;
  return jsonb_build_object('batch_id',bid,'status','empty_day_skipped','job_ids','[]'::jsonb);
 end if;
 n:=cardinality(p_parts);
 if p_parts is null or n<1 or array_ndims(p_parts)<>1 or exists(select 1 from unnest(p_parts) part where part is null or length(part) not between 1 and 200) then return jsonb_build_object('status','invalid_parts'); end if;
 -- All reserved and historical jobs count conservatively, even cancelled/failed. No refund races.
 select count(*) into used from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id
 where (b.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or b.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'));
 if used+n>ctl.monthly_message_budget then
  insert into public.kakao_multi_batches(owner_id,day,generation,scope_hash,delivery_deadline,status,outcome) values(p_owner,p_day,p_generation,p_scope_hash,((p_day+pref.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes','held','quota_held') returning id into bid;
  return jsonb_build_object('batch_id',bid,'status','quota_held','job_ids','[]'::jsonb);
 end if;
 insert into public.kakao_multi_batches(owner_id,day,generation,scope_hash,delivery_deadline) values(p_owner,p_day,p_generation,p_scope_hash,((p_day+pref.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes') returning id into bid;
 insert into public.kakao_multi_jobs(batch_id,owner_id,generation,part,body) select bid,p_owner,p_generation,ordinality::integer,body from unnest(p_parts) with ordinality a(body,ordinality);
 return jsonb_build_object('batch_id',bid,'status','reserved','job_ids',(select jsonb_agg(id order by part) from public.kakao_multi_jobs where batch_id=bid));
end $$;

create or replace function private.kakao_service_claim(p_job_id uuid,p_run_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare ctl public.kakao_multi_controls; c public.kakao_multi_connections; pref public.kakao_multi_preferences;
 j public.kakao_multi_jobs; b public.kakao_multi_batches; run public.kakao_multi_runs; token uuid;
begin
 -- Read only to identify owner. Real mutation order: controls -> connection -> run -> job.
 select * into j from public.kakao_multi_jobs where id=p_job_id;
 if not found then return jsonb_build_object('claimed',false,'reason','missing'); end if;
 select * into ctl from public.kakao_multi_controls where singleton for update;
 if not found or not ctl.enabled or ctl.cost_verified_until is null or ctl.cost_verified_until<=clock_timestamp() or ctl.monthly_message_budget<=0 or ctl.monthly_function_budget<=0 then return jsonb_build_object('claimed',false,'reason','disabled'); end if;
 select * into c from public.kakao_multi_connections where owner_id=j.owner_id for update;
 select * into run from public.kakao_multi_runs where id=p_run_id for update;
 if not found or run.claimed_job is not null or run.entered_at<=clock_timestamp()-interval '2 minutes' then return jsonb_build_object('claimed',false,'reason','invalid_run'); end if;
 select * into j from public.kakao_multi_jobs where id=p_job_id for update;
 select * into b from public.kakao_multi_batches where id=j.batch_id;
 select * into pref from public.kakao_multi_preferences where owner_id=j.owner_id;
 if j.status<>'reserved' or b.status not in ('reserved','sending') then return jsonb_build_object('claimed',false,'reason','not_reserved'); end if;
 if b.delivery_deadline is null or clock_timestamp()>=b.delivery_deadline then
  update public.kakao_multi_jobs set status='cancelled',outcome='schedule_missed',completed_at=clock_timestamp() where batch_id=b.id and status='reserved';
  update public.kakao_multi_batches set status='failed',outcome='schedule_missed',completed_at=clock_timestamp() where id=b.id;
  return jsonb_build_object('claimed',false,'reason','schedule_missed');
 end if;
 if pref.owner_id is null or c.owner_id is null or private.kakao_service_legacy_conflict(c.account_id) or c.status<>'connected' or not c.talk_message_granted or c.generation<>j.generation or not pref.enabled or pref.admin_paused
 or not private.kakao_service_owner_active(j.owner_id) or b.day not between (clock_timestamp() at time zone 'Asia/Seoul')::date-1 and (clock_timestamp() at time zone 'Asia/Seoul')::date
 or private.kakao_service_snapshot_hash(private.kakao_service_snapshot(j.owner_id,b.day)) is distinct from b.scope_hash then
  update public.kakao_multi_jobs set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where batch_id=b.id and status='reserved';
  update public.kakao_multi_batches set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp() where id=b.id;
  return jsonb_build_object('claimed',false,'reason','scope_changed');
 end if;
 if (select count(*) from public.kakao_multi_jobs x join public.kakao_multi_batches y on y.id=x.batch_id where (y.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or y.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')))>ctl.monthly_message_budget
 or (select count(*) from public.kakao_multi_runs where entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))>ctl.monthly_function_budget then
  update public.kakao_multi_batches set status='held',outcome='quota_held' where id=b.id;
  update public.kakao_multi_jobs set status='cancelled',outcome='quota_held',completed_at=clock_timestamp() where batch_id=b.id and status='reserved';
  return jsonb_build_object('claimed',false,'reason','quota_held');
 end if;
 if exists(select 1 from public.kakao_multi_jobs where owner_id=j.owner_id and status='sending')
 or exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and part<j.part and status<>'accepted') then return jsonb_build_object('claimed',false,'reason','previous_incomplete'); end if;
 token:=gen_random_uuid();
 update public.kakao_multi_jobs set status='sending',claimed_at=clock_timestamp(),claim_token=token where id=j.id;
 update public.kakao_multi_batches set status='sending' where id=b.id;
 update public.kakao_multi_runs set claimed_job=j.id where id=p_run_id;
 return jsonb_build_object('claimed',true,'job_id',j.id,'claim_token',token,'owner_id',j.owner_id,'generation',j.generation,'part',j.part,'body',j.body,'encrypted_tokens',c.encrypted_tokens);
end $$;

create or replace function private.kakao_service_complete(p_job_id uuid,p_claim_token uuid,p_status text) returns boolean language plpgsql security definer set search_path='' as $$
declare j public.kakao_multi_jobs; outcome_value text; deadline timestamptz;
begin
 if p_status is null or p_status not in ('accepted','uncertain','failed') or p_claim_token is null then return false; end if;
 select * into j from public.kakao_multi_jobs where id=p_job_id;
 if not found then return false; end if;
 perform 1 from public.kakao_multi_connections where owner_id=j.owner_id for update;
 select * into j from public.kakao_multi_jobs where id=p_job_id for update;
 if j.status<>'sending' or j.claim_token is distinct from p_claim_token then return false; end if;
 select delivery_deadline into deadline from public.kakao_multi_batches where id=j.batch_id;
 outcome_value:=case when p_status='failed' and exists(select 1 from public.kakao_multi_batches where id=j.batch_id and outcome='reauth_required') then 'reauth_required' when p_status='failed' and (deadline is null or deadline<=clock_timestamp()) then 'schedule_missed' else case p_status when 'accepted' then 'api_accepted' when 'uncertain' then 'outcome_uncertain' else 'setup_failed' end end;
 update public.kakao_multi_jobs set status=p_status,outcome=outcome_value,completed_at=clock_timestamp(),claim_token=null where id=j.id;
 if p_status<>'accepted' then
  update public.kakao_multi_jobs set status='cancelled',outcome=outcome_value,completed_at=clock_timestamp() where batch_id=j.batch_id and status='reserved';
  update public.kakao_multi_batches set status=p_status,outcome=outcome_value,completed_at=clock_timestamp() where id=j.batch_id;
 elsif (deadline is null or deadline<=clock_timestamp()) and exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and status='reserved') then
  update public.kakao_multi_jobs set status='cancelled',outcome='schedule_missed',completed_at=clock_timestamp() where batch_id=j.batch_id and status='reserved';
  update public.kakao_multi_batches set status='failed',outcome='schedule_missed',completed_at=clock_timestamp() where id=j.batch_id;
 elsif not exists(select 1 from public.kakao_multi_jobs where batch_id=j.batch_id and status<>'accepted') then
  update public.kakao_multi_batches set status='accepted',outcome='api_accepted',completed_at=clock_timestamp() where id=j.batch_id;
 end if;
 return true;
end $$;

create or replace function private.kakao_service_expire() returns integer language plpgsql security definer set search_path='' as $$
declare expired_job record; n integer:=0; at_time timestamptz:=clock_timestamp(); added integer:=0;
begin
 perform pg_advisory_xact_lock(1746948683,20261117);
 -- Acquire affected connection locks first, in stable order, before touching job rows.
 perform c.owner_id from public.kakao_multi_connections c where
 (c.status='pending_confirmation' and c.confirmation_expires_at<=clock_timestamp()) or exists(
 select 1 from public.kakao_multi_jobs x join public.kakao_multi_batches b on b.id=x.batch_id where x.owner_id=c.owner_id and
 ((x.status='reserved' and (b.delivery_deadline is null or b.delivery_deadline<=at_time)) or (x.status='reserved' and b.day<(clock_timestamp() at time zone 'Asia/Seoul')::date) or (x.status='sending' and x.claimed_at<clock_timestamp()-interval '5 minutes')))
 or exists(select 1 from public.kakao_multi_preferences p where p.owner_id=c.owner_id and p.enabled and not p.admin_paused
 and c.status='connected' and c.talk_message_granted and private.kakao_service_owner_active(c.owner_id)
 and extract(dow from at_time at time zone 'Asia/Seoul')::integer=any(p.days)
 and at_time>=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes'
 and p.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and c.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and not exists(select 1 from public.kakao_multi_batches b where b.owner_id=c.owner_id and b.day=(at_time at time zone 'Asia/Seoul')::date)) order by c.owner_id for update;
 -- Already accepted parts are immutable. Expire only unsent reservations.
 update public.kakao_multi_jobs j set status='cancelled',outcome='schedule_missed',completed_at=at_time
 from public.kakao_multi_batches b where b.id=j.batch_id and j.status='reserved' and (b.delivery_deadline is null or b.delivery_deadline<=at_time);
 update public.kakao_multi_batches b set status='failed',outcome='schedule_missed',completed_at=at_time
 where b.status in ('reserved','sending') and (b.delivery_deadline is null or b.delivery_deadline<=at_time)
 and exists(select 1 from public.kakao_multi_jobs x where x.batch_id=b.id and x.status='cancelled' and x.outcome='schedule_missed');
 -- A previous-day 23:55 reservation remains eligible until its immutable 00:05 deadline.
 -- Abandoned OAuth confirmation must not retain live token ciphertext indefinitely.
 for expired_job in select owner_id from public.kakao_multi_connections where status='pending_confirmation' and confirmation_expires_at<=clock_timestamp() order by owner_id loop
  update public.kakao_multi_connections set status='revoked',generation=generation+1,encrypted_tokens=null,account_id=null,
   confirmation_hash=null,confirmation_expires_at=null,talk_message_granted=false,updated_at=clock_timestamp()
  where owner_id=expired_job.owner_id and status='pending_confirmation' and confirmation_expires_at<=clock_timestamp();
 end loop;
 update public.kakao_multi_oauth set ticket_hash=null,state_hash=null,browser_hash=null,
 status=case when status='consumed' then 'consumed' else 'cancelled' end
 where expires_at<=clock_timestamp() and (ticket_hash is not null or state_hash is not null or browser_hash is not null);
 for expired_job in select id,claim_token from public.kakao_multi_jobs where status='sending' and claimed_at<clock_timestamp()-interval '5 minutes' order by owner_id,id loop
  if private.kakao_service_complete(expired_job.id,expired_job.claim_token,'uncertain') then n:=n+1; end if;
 end loop;
 -- Record a missed reservation, but never fabricate or late-send its message parts.
 insert into public.kakao_multi_batches(owner_id,day,generation,status,outcome,completed_at)
 select c.owner_id,(at_time at time zone 'Asia/Seoul')::date,c.generation,'failed','schedule_missed',at_time
 from public.kakao_multi_connections c where exists(select 1 from public.kakao_multi_preferences p where p.owner_id=c.owner_id and p.enabled and not p.admin_paused
 and c.status='connected' and c.talk_message_granted and private.kakao_service_owner_active(c.owner_id)
 and extract(dow from at_time at time zone 'Asia/Seoul')::integer=any(p.days)
 and at_time>=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes'
 and p.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and c.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and not exists(select 1 from public.kakao_multi_batches b where b.owner_id=c.owner_id and b.day=(at_time at time zone 'Asia/Seoul')::date))
 on conflict(owner_id,day) do nothing;
 get diagnostics added=row_count;
 n:=n+added;
 return n;
end $$;

create or replace function private.kakao_service_validate_claim(p_job_id uuid,p_claim_token uuid) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id
 join public.kakao_multi_connections c on c.owner_id=j.owner_id join public.kakao_multi_preferences p on p.owner_id=j.owner_id
 where j.id=p_job_id and j.claim_token=p_claim_token and j.status='sending' and b.status in ('reserved','sending') and b.delivery_deadline is not null and clock_timestamp()<b.delivery_deadline and j.claimed_at>clock_timestamp()-interval '5 minutes'
 and not private.kakao_service_legacy_conflict(c.account_id) and c.status='connected' and c.talk_message_granted and c.generation=j.generation and p.enabled and not p.admin_paused
 and private.kakao_service_owner_active(j.owner_id) and b.day between (clock_timestamp() at time zone 'Asia/Seoul')::date-1 and (clock_timestamp() at time zone 'Asia/Seoul')::date
 and private.kakao_service_snapshot_hash(private.kakao_service_snapshot(j.owner_id,b.day))=b.scope_hash
 and coalesce((private.kakao_service_gate()->>'enabled')::boolean,false)
 and exists(select 1 from public.kakao_multi_controls ctl where ctl.singleton
 and (select count(*) from public.kakao_multi_jobs x join public.kakao_multi_batches y on y.id=x.batch_id where (y.created_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul') or y.delivery_deadline>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul')))<=ctl.monthly_message_budget
 and (select count(*) from public.kakao_multi_runs r where r.entered_at>=(date_trunc('month',clock_timestamp() at time zone 'Asia/Seoul') at time zone 'Asia/Seoul'))<=ctl.monthly_function_budget))
$$;

create or replace function private.kakao_service_pending(p_limit integer default 25) returns jsonb language sql stable security definer set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',q.id) order by q.created_at,q.batch_id,q.part),'[]'::jsonb) from (
 select j.id,b.created_at,j.batch_id,j.part from public.kakao_multi_jobs j join public.kakao_multi_batches b on b.id=j.batch_id
 where b.delivery_deadline is not null and clock_timestamp()<b.delivery_deadline and not exists(select 1 from public.kakao_multi_jobs busy where busy.owner_id=j.owner_id and busy.status='sending') and j.status='reserved' and b.status in ('reserved','sending') and b.day between (clock_timestamp() at time zone 'Asia/Seoul')::date-1 and (clock_timestamp() at time zone 'Asia/Seoul')::date
 order by b.created_at,j.batch_id,j.part limit greatest(1,least(coalesce(p_limit,25),100))) q
$$;

create or replace function private.kakao_service_due(p_run_id uuid,p_limit integer default 50) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare local_now timestamp:=clock_timestamp() at time zone 'Asia/Seoul'; result jsonb;
begin
 if not exists(select 1 from public.kakao_multi_runs where id=p_run_id and entered_at>clock_timestamp()-interval '2 minutes')
 or not coalesce((private.kakao_service_gate()->>'enabled')::boolean,false) then return '[]'::jsonb; end if;
 select coalesce(jsonb_agg(jsonb_build_object('owner_id',q.owner_id,'generation',q.generation,'day',q.scheduled_day,
 'summary',q.summary,'scope_hash',private.kakao_service_snapshot_hash(q.summary))),'[]'::jsonb) into result
 from (select c.owner_id,c.generation,dates.scheduled_day,private.kakao_service_snapshot(c.owner_id,dates.scheduled_day) summary
 from public.kakao_multi_connections c join public.kakao_multi_preferences p using(owner_id)
 cross join lateral (values(local_now::date),(local_now::date-1)) dates(scheduled_day)
 where c.status='connected' and c.talk_message_granted and p.enabled and not p.admin_paused
 and private.kakao_service_owner_active(c.owner_id)
 and extract(dow from dates.scheduled_day)::integer=any(p.days)
 and local_now>=dates.scheduled_day+p.delivery_time and local_now<dates.scheduled_day+p.delivery_time+interval '10 minutes'
 and not exists(select 1 from public.kakao_multi_batches b where b.owner_id=c.owner_id and b.day=dates.scheduled_day)
 order by dates.scheduled_day+p.delivery_time,c.owner_id limit greatest(1,least(coalesce(p_limit,50),100))) q;
 return result;
end $$;

-- The only public entrypoint here is service_continue and it requires service_role.
do $$ declare f record; target text; begin
 for f in select n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) args from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname in ('public','private') and (p.proname like 'kakao_cron_%' or p.proname in ('kakao_service_has_work','kakao_service_enqueue_tick','kakao_service_continue')) loop
  target:=format('%I.%I(%s)',f.nspname,f.proname,f.args);
  execute 'revoke all on function '||target||' from public,anon,authenticated,service_role';
  if f.proname='kakao_service_continue' then execute 'grant execute on function '||target||' to service_role'; end if;
 end loop;
end $$;
-- Do NOT run reconcile during migration; no cron or network is activated by this file alone.
commit;
