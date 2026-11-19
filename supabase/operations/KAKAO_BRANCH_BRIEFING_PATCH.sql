-- Additive branch-manager briefing; preserve existing consent, quotas and job ordering.
alter table public.kakao_multi_batches add column branch_parts integer not null default 0 check(branch_parts>=0);
CREATE OR REPLACE FUNCTION private.kakao_service_snapshot(p_owner uuid, p_day date)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 select jsonb_build_object(
 'identity',jsonb_build_object('owner_id',me.id,'unit',me.organization_unit_id,'position',me.position_code,'role',me.role),
 'preferences',(select jsonb_build_object('time',p.delivery_time,'days',p.days,'send_empty',p.send_empty,'enabled',p.enabled,'weather_region_key',p.weather_region_key,'weather_catalog',(select jsonb_build_object('nx',r.nx,'ny',r.ny,'forecast_code',r.forecast_code,'enabled',r.enabled,'verified_at',r.verified_at) from public.kakao_weather_regions r where r.region_key=p.weather_region_key)) from public.kakao_multi_preferences p where p.owner_id=me.id),
 'branch',case when me.position_code='branch_manager' then
 (select jsonb_build_object('name',u.name,'members',coalesce((select jsonb_agg(jsonb_build_object(
 'id',m.id,'name',m.display_name,'count',s.work_count,
 'state',case when s.work_count>0 then 'scheduled' when s.leave_count>0 then 'leave'
 when exists(select 1 from public.sales_empty_days d where d.owner=m.id and d.day=p_day) then 'empty'
 when m.position_code in ('branch_manager','division_head','chief_representative') then 'excluded' else 'missing' end)
 order by m.display_name,m.id)
 from public.profiles m cross join lateral (
 select count(*) filter(where e.kind<>'휴무' or e.start_time is not null) work_count,
 count(*) filter(where e.kind='휴무' and e.start_time is null) leave_count
 from public.sales_events e join public.profiles author on author.id=e.owner
 where e.unit=me.organization_unit_id and author.organization_unit_id=me.organization_unit_id and author.is_active
 and (e.owner=m.id or e.companion=m.id) and not e.common
 and e.day=p_day and e.deleted_at is null and e.status not in ('취소','연기')
 ) s where m.organization_unit_id=me.organization_unit_id and m.is_active and m.id<>me.id
 and m.position_code is distinct from 'branch_manager'),'[]'::jsonb))
 from public.organization_units u where u.id=me.organization_unit_id and u.is_active) end,
 'empty_explicit',exists(select 1 from public.sales_empty_days x where x.owner=me.id and x.day=p_day),
 'events',coalesce((select jsonb_agg(jsonb_build_object(
 'id',e.id,'day',e.day,'start_time',e.start_time,'time_pending',e.time_pending,'title',e.title,'kind',e.kind,'status',e.status,
 'own',e.owner=me.id,'companion',e.companion=me.id,'common',e.common,
 'end_time',case when e.owner=me.id then e.end_time end,'place',case when e.owner=me.id then e.place end)
 order by e.start_time nulls last,e.id)
 from public.sales_events e join public.profiles author on author.id=e.owner
 where e.unit=me.organization_unit_id and author.organization_unit_id=me.organization_unit_id and author.is_active
 and e.day=p_day and e.deleted_at is null and (e.owner=me.id or e.companion=me.id or e.common)),'[]'::jsonb))
 from public.profiles me where me.id=p_owner and private.kakao_service_owner_active(p_owner)
$function$
;
CREATE OR REPLACE FUNCTION private.kakao_service_reserve(p_owner uuid, p_day date, p_generation bigint, p_parts text[], p_scope_hash text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare ctl public.kakao_multi_controls; c public.kakao_multi_connections; pref public.kakao_multi_preferences;
 summary jsonb; bid uuid; used bigint; local_now timestamp:=clock_timestamp() at time zone 'Asia/Seoul'; n integer;
begin
 if not private.kakao_welcome_regular_allowed(p_owner,p_day) or p_day is null or p_day not in (local_now::date,local_now::date-1) or p_generation is null or p_scope_hash is null then return jsonb_build_object('status','invalid'); end if;
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
 if jsonb_array_length(summary->'events')=0 and not pref.send_empty and (summary->'branch' is null or summary->'branch'='null'::jsonb) then
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
end $function$
;
CREATE OR REPLACE FUNCTION private.kakao_service_claim(p_job_id uuid, p_run_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
 if not found or run.run_kind<>'normal' or run.claimed_job is not null or run.entered_at<=clock_timestamp()-interval '2 minutes' then return jsonb_build_object('claimed',false,'reason','invalid_run'); end if;
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
 or not private.kakao_function_budget_ok('normal',false) then
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
 return jsonb_build_object('claimed',true,'job_id',j.id,'claim_token',token,'owner_id',j.owner_id,'generation',j.generation,'part',j.part,'body',j.body,'message_kind',case when j.part<=b.branch_parts then 'branch' else 'personal' end,'encrypted_tokens',c.encrypted_tokens);
end $function$
;

create function private.kakao_service_reserve_branch(p_owner uuid,p_day date,p_generation bigint,p_parts text[],p_scope_hash text,p_branch_parts integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if p_branch_parts is null or p_branch_parts<1 or p_branch_parts>=coalesce(cardinality(p_parts),0)
 or not exists(select 1 from public.profiles where id=p_owner and position_code='branch_manager')
 then return jsonb_build_object('status','invalid_parts'); end if;
 result:=private.kakao_service_reserve(p_owner,p_day,p_generation,p_parts,p_scope_hash);
 if result->>'status'='reserved' then
  update public.kakao_multi_batches set branch_parts=p_branch_parts where id=(result->>'batch_id')::uuid;
 end if;
 return result;
end $$;
revoke all on function private.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer) from public,anon,authenticated;
create function public.kakao_service_reserve_branch(p_owner uuid,p_day date,p_generation bigint,p_parts text[],p_scope_hash text,p_branch_parts integer)
returns jsonb language sql set search_path='' as $$
 select private.kakao_service_reserve_branch(p_owner,p_day,p_generation,p_parts,p_scope_hash,p_branch_parts)
$$;
revoke all on function public.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer) from public,anon,authenticated;
grant execute on function private.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer),public.kakao_service_reserve_branch(uuid,date,bigint,text[],text,integer) to service_role;

create or replace function private.kakao_welcome_claim(p_ticket_hash text) returns jsonb language plpgsql security definer set search_path='' as $$
declare w public.kakao_multi_welcomes;c public.kakao_multi_connections;s jsonb;token uuid:=gen_random_uuid();parts jsonb;
begin
 perform 1 from public.kakao_multi_controls where singleton for update;
 select * into w from public.kakao_multi_welcomes where ticket_hash=p_ticket_hash;
 if not found then return null;end if;
 select * into c from public.kakao_multi_connections where owner_id=w.owner_id for update;
 select * into w from public.kakao_multi_welcomes where id=w.id for update;
 if w.status<>'queued' or w.ticket_expires_at<=clock_timestamp() or w.expires_at<=clock_timestamp() or w.day<>(clock_timestamp() at time zone 'Asia/Seoul')::date then return null;end if;
 if c.status<>'connected' or c.generation<>w.generation or not c.talk_message_granted or not private.kakao_service_owner_active(w.owner_id)
 or private.kakao_service_legacy_conflict(c.account_id) or not exists(select 1 from public.kakao_multi_preferences p where p.owner_id=w.owner_id and p.enabled and not p.admin_paused and private.kakao_weather_region_valid(p.weather_region_key)) then return null;end if;
 if exists(select 1 from public.kakao_multi_jobs where batch_id=w.batch_id and status in('sending','uncertain','failed','cancelled')) then return null;end if;
 s:=private.kakao_service_snapshot(w.owner_id,w.day);
 if w.scope_hash is not null and w.scope_hash<>private.kakao_service_snapshot_hash(s) then return null;end if;
 if not private.kakao_service_tick_enter(gen_random_uuid()) then return null;end if;
 update public.kakao_multi_welcomes set status='processing',claim_token=token,scope_hash=private.kakao_service_snapshot_hash(s) where id=w.id;
 update public.kakao_multi_batches set scope_hash=private.kakao_service_snapshot_hash(s) where id=w.batch_id;
 select jsonb_agg(body order by part) into parts from public.kakao_multi_jobs where batch_id=w.batch_id;
 return jsonb_build_object('id',w.id,'owner_id',w.owner_id,'day',w.day,'generation',w.generation,'summary',s,'claim_token',token,'encrypted_tokens',c.encrypted_tokens,'expires_at',w.expires_at,'parts',parts,'branch_parts',(select branch_parts from public.kakao_multi_batches where id=w.batch_id),'next_part',coalesce((select min(part) from public.kakao_multi_jobs where batch_id=w.batch_id and status='reserved'),1));
end $$;

create function private.kakao_welcome_reserve_branch(p_id uuid,p_claim_token uuid,p_parts text[],p_branch_parts integer)
returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if p_branch_parts is null or p_branch_parts<1 or p_branch_parts>=coalesce(cardinality(p_parts),0)
 or not exists(select 1 from public.kakao_multi_welcomes w join public.profiles p on p.id=w.owner_id where w.id=p_id and p.position_code='branch_manager') then return jsonb_build_object('reserved',false);end if;
 result:=private.kakao_welcome_reserve(p_id,p_claim_token,p_parts);
 if result->>'reserved'='true' then
 update public.kakao_multi_batches b set branch_parts=p_branch_parts from public.kakao_multi_welcomes w where w.id=p_id and b.id=w.batch_id;
 end if;
 return result;
end $$;
revoke all on function private.kakao_welcome_reserve_branch(uuid,uuid,text[],integer) from public,anon,authenticated;
create function public.kakao_welcome_reserve_branch(p_id uuid,p_claim_token uuid,p_parts text[],p_branch_parts integer)
returns jsonb language sql set search_path='' as $$select private.kakao_welcome_reserve_branch(p_id,p_claim_token,p_parts,p_branch_parts)$$;
revoke all on function public.kakao_welcome_reserve_branch(uuid,uuid,text[],integer) from public,anon,authenticated;
grant execute on function private.kakao_welcome_reserve_branch(uuid,uuid,text[],integer),public.kakao_welcome_reserve_branch(uuid,uuid,text[],integer) to service_role;
