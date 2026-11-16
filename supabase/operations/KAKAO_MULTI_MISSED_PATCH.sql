-- REVIEW PATCH: explicit missed schedule status; never delayed automatic delivery.
begin;
do $$ declare t text; c record; outcome_att smallint; begin
 foreach t in array array['kakao_multi_batches','kakao_multi_jobs'] loop
  select attnum into outcome_att from pg_attribute where attrelid=('public.'||t)::regclass and attname='outcome' and not attisdropped;
  for c in select conname from pg_constraint where conrelid=('public.'||t)::regclass and contype='c' and conkey=array[outcome_att]::smallint[] loop
   execute format('alter table public.%I drop constraint %I',t,c.conname);
  end loop;
  execute format('alter table public.%I add constraint %I check(outcome in (''api_accepted'',''setup_failed'',''reauth_required'',''outcome_uncertain'',''revoked'',''paused'',''quota_held'',''empty_day_skipped'',''scope_changed'',''schedule_missed''))',t,t||'_outcome_check');
 end loop;
end $$;
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
 select jsonb_build_object('dispatch_ready',coalesce((private.kakao_service_gate()->>'enabled')::boolean,false),'connection_status',coalesce(c.status,'disconnected'),
 'enabled',coalesce(p.enabled,false),'time',coalesce(left(p.delivery_time::text,5),'08:00'),
 'weather_region_key',p.weather_region_key,'days',coalesce(to_jsonb(p.days),'[0,1,2,3,4,5,6]'::jsonb),'send_empty',coalesce(p.send_empty,true),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end,
 'can_manage',exists(select 1 from private.sales_scope_for(u,false) s where s.managed and s.member<>u),
 'legacy_personal',private.kakao_service_excluded_owner(u))
 into result from (select u id) me
 left join public.kakao_multi_connections c on c.owner_id=me.id
 left join public.kakao_multi_preferences p on p.owner_id=me.id
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=u order by b.day desc,b.created_at desc limit 1) j on true;
 return result;
end $$;

create or replace function private.kakao_admin_status() returns jsonb language plpgsql stable security definer set search_path='' as $$
declare u uuid:=private.kakao_require_user(); result jsonb;
begin
 select coalesce(jsonb_agg(jsonb_build_object('owner_id',s.member,'label',s.label,'connection_status',coalesce(c.status,'disconnected'),
 'admin_paused',coalesce(p.admin_paused,false),'last_outcome',j.outcome,'last_attempt_at',j.claimed_at,'last_day',j.day,'today_outcome',case when j.day=(clock_timestamp() at time zone 'Asia/Seoul')::date then j.outcome end) order by s.label),'[]'::jsonb)
 into result from private.sales_scope_for(u,false) s
 left join public.kakao_multi_connections c on c.owner_id=s.member
 left join public.kakao_multi_preferences p on p.owner_id=s.member
 left join lateral(select b.day,coalesce(b.outcome,x.outcome) outcome,x.claimed_at from public.kakao_multi_batches b
 left join lateral(select outcome,claimed_at from public.kakao_multi_jobs where batch_id=b.id order by claimed_at desc nulls last,part desc limit 1) x on true
 where b.owner_id=s.member order by b.day desc,b.created_at desc limit 1) j on true
 where s.managed and s.member<>u;
 return result;
end $$;

create or replace function private.kakao_service_expire() returns integer language plpgsql security definer set search_path='' as $$
declare expired_job record; n integer:=0; at_time timestamptz:=clock_timestamp(); added integer:=0;
begin
 -- Acquire affected connection locks first, in stable order, before touching job rows.
 perform c.owner_id from public.kakao_multi_connections c where
 (c.status='pending_confirmation' and c.confirmation_expires_at<=clock_timestamp()) or exists(
 select 1 from public.kakao_multi_jobs x join public.kakao_multi_batches b on b.id=x.batch_id where x.owner_id=c.owner_id and
 ((x.status='reserved' and b.day<(clock_timestamp() at time zone 'Asia/Seoul')::date) or (x.status='sending' and x.claimed_at<clock_timestamp()-interval '5 minutes')))
 or exists(select 1 from public.kakao_multi_preferences p where p.owner_id=c.owner_id and p.enabled and not p.admin_paused
 and c.status='connected' and c.talk_message_granted and private.kakao_service_owner_active(c.owner_id)
 and extract(dow from at_time at time zone 'Asia/Seoul')::integer=any(p.days)
 and at_time>=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')+interval '10 minutes'
 and p.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and c.updated_at<=(((at_time at time zone 'Asia/Seoul')::date+p.delivery_time) at time zone 'Asia/Seoul')
 and not exists(select 1 from public.kakao_multi_batches b where b.owner_id=c.owner_id and b.day=(at_time at time zone 'Asia/Seoul')::date)) order by c.owner_id for update;
 -- Never send yesterday's leftover reservations on a later day.
 update public.kakao_multi_jobs j set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp()
 from public.kakao_multi_batches b where b.id=j.batch_id and b.day<(clock_timestamp() at time zone 'Asia/Seoul')::date and j.status='reserved';
 update public.kakao_multi_batches set status='cancelled',outcome='scope_changed',completed_at=clock_timestamp()
 where day<(clock_timestamp() at time zone 'Asia/Seoul')::date and status in ('reserved','held');
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
commit;
