-- Preserve saved answers and completed results; abort never grades an attempt.
alter table public.hwarang_exam_attempts add column if not exists aborted_at timestamptz;
alter table public.hwarang_exam_attempts drop constraint hwarang_exam_attempts_status_check;
alter table public.hwarang_exam_attempts add constraint hwarang_exam_attempts_status_check check(status in ('active','submitted','aborted'));
create or replace function public.hwarang_exam(p_actor uuid,p_action text,p_payload jsonb default '{}') returns jsonb
language plpgsql security invoker set search_path='' as $$
declare a public.hwarang_exam_attempts; b public.hwarang_exam_bank; sid uuid; snap jsonb; sections jsonb;
 parent public.hwarang_exam_attempts; nums jsonb; qs jsonb; kv record; q jsonb; out_rows jsonb; target uuid; desired text;
begin
 perform private.exam_check(p_actor);
 if p_action='catalog' then
  return coalesce((select jsonb_agg(jsonb_build_object('id',id,'title',title,'family',family) order by id)
   from public.hwarang_exam_bank where enabled),'[]');
 elsif p_action in ('start','random_start','review_start') then
  perform pg_advisory_xact_lock(hashtextextended(p_actor::text,41));
  select * into a from public.hwarang_exam_attempts where user_id=p_actor and status='active' for update;
  if found then
   if a.deadline is null or a.deadline>now() then return private.exam_view(a.id);end if;
   perform private.exam_finish(a.id);
  end if;
  sid:=(p_payload->>'id')::uuid;
  select * into a from public.hwarang_exam_attempts where id=sid;
  if found then
   if a.user_id<>p_actor then raise exception 'EXAM_ACCESS_DENIED';end if;
   return private.exam_view(a.id);
  end if;
  if p_action='review_start' then
   select * into parent from public.hwarang_exam_attempts where id=(p_payload->>'parent_id')::uuid and user_id=p_actor and status='submitted';
   if not found then raise exception 'EXAM_ACCESS_DENIED';end if;
   select jsonb_agg(x order by (x->>'number')::integer),jsonb_agg(x->'number') into qs,nums
    from jsonb_array_elements(parent.snapshot->'questions') x where parent.answers->>(x->>'number') is distinct from x->>'answer';
   if qs is null then raise exception 'NO_WRONG_QUESTIONS';end if;
   snap:=jsonb_build_object('title',parent.snapshot->>'title','kind','review','questions',qs,'sections',jsonb_build_array(jsonb_build_object('key','review','name','오답 복습 정답률','numbers',nums)));
   insert into public.hwarang_exam_attempts(id,user_id,exam_id,mode,track,snapshot,source_kind,parent_attempt_id)
    values(sid,p_actor,parent.exam_id,'practice',parent.track,snap,'review',parent.id);
   return private.exam_view(sid);
  elsif p_action='random_start' then
   if coalesce(p_payload->>'mode','') not in ('exam','practice') or coalesce(p_payload->>'track','') not in ('main','third','combined') then raise exception 'INVALID_EXAM_OPTIONS';end if;
   snap:=private.exam_random_snapshot(p_actor,p_payload->>'family',p_payload->>'track');
   insert into public.hwarang_exam_attempts(id,user_id,exam_id,mode,track,snapshot,source_kind,deadline)
    values(sid,p_actor,snap->>'exam_id',p_payload->>'mode',p_payload->>'track',snap,'random',case when p_payload->>'mode'='exam' then now()+interval '50 minutes' else null end);
   return private.exam_view(sid);
  end if;
  select * into b from public.hwarang_exam_bank where id=p_payload->>'exam_id' and enabled;
  if not found then raise exception 'EXAM_NOT_FOUND';end if;
  if coalesce(p_payload->>'mode','') not in ('exam','practice') or coalesce(p_payload->>'track','') not in ('main','third','combined') then raise exception 'INVALID_EXAM_OPTIONS';end if;
  select jsonb_agg(s) into sections from jsonb_array_elements(b.data->'sections') s
    where p_payload->>'track'='combined' or s->>'key'=p_payload->>'track';
  select jsonb_agg(distinct n) into nums from jsonb_array_elements(sections) s, jsonb_array_elements(s->'numbers') n;
  select jsonb_agg(item order by (item->>'number')::integer) into qs from jsonb_array_elements(b.data->'questions') item where nums @> jsonb_build_array((item->>'number')::integer);
  snap:=jsonb_build_object('title',b.title,'revision',b.revision,'sections',sections,'questions',qs);
  insert into public.hwarang_exam_attempts(id,user_id,exam_id,mode,track,snapshot,deadline)
  values(sid,p_actor,b.id,p_payload->>'mode',p_payload->>'track',snap,case when p_payload->>'mode'='exam' then now()+interval '50 minutes' else null end);
  return private.exam_view(sid);
 elsif p_action in ('list','team') then
  if p_action='team' and not exists(select 1 from public.profiles where id=p_actor and (role='super_admin' or position_code in ('team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative'))) then raise exception 'EXAM_ACCESS_DENIED';end if;
  -- Finalize expired records on a read as well; disconnected clients cannot extend a test.
  for a in select * from public.hwarang_exam_attempts where status='active' and deadline<=now()
    and (user_id=p_actor or (p_action='team' and private.can_user_view(p_actor,user_id))) for update loop
    perform private.exam_finish(a.id);
  end loop;
  select coalesce(jsonb_agg(row_data order by started_at desc),'[]') into out_rows from (
   select rec.started_at,(to_jsonb(rec)-'snapshot'-'answers'-'flags')||jsonb_build_object('title',rec.snapshot->>'title','display_name',p.display_name,
     'organization_id',p.organization_unit_id,'organization_name',o.name) row_data
   from public.hwarang_exam_attempts rec join public.profiles p on p.id=rec.user_id left join public.organization_units o on o.id=p.organization_unit_id
   where (p_action='list' and rec.user_id=p_actor) or (p_action='team' and private.can_user_view(p_actor,rec.user_id))
   order by rec.started_at desc limit 10000) r;
  return out_rows;
 elsif p_action='roster' then
  if not exists(select 1 from public.profiles where id=p_actor and (role='super_admin' or position_code in ('team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative'))) then raise exception 'EXAM_ACCESS_DENIED';end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id',p.id,'display_name',p.display_name,'organization_id',p.organization_unit_id,'organization_name',o.name,'groups',(select coalesce(jsonb_agg(jsonb_build_object('id',anc.id,'name',anc.name,'type',anc.unit_type)),'[]') from public.organization_units anc where private.is_org_descendant(anc.id,p.organization_unit_id))))
   from public.profiles p left join public.organization_units o on o.id=p.organization_unit_id where p.is_active and private.can_user_view(p_actor,p.id)),'[]');
 elsif p_action in ('get','save','submit','check','abort') then
  sid:=(p_payload->>'id')::uuid;
  select * into a from public.hwarang_exam_attempts where id=sid for update;
  if not found then raise exception 'EXAM_NOT_FOUND';end if;
  if a.user_id<>p_actor and not (p_action='get' and private.can_user_view(p_actor,a.user_id)) then raise exception 'EXAM_ACCESS_DENIED';end if;
  if a.status='active' and a.deadline<=now() then perform private.exam_finish(sid);return private.exam_view(sid);end if;
  if p_action='get' or a.status<>'active' then return private.exam_view(sid);end if;
  if (p_payload->>'revision')::integer is distinct from a.revision then raise exception 'EXAM_CONFLICT_RELOAD';end if;
  if p_action='abort' then
   update public.hwarang_exam_attempts set status='aborted',aborted_at=now(),updated_at=now(),revision=revision+1
    where id=sid and status='active';
   return private.exam_view(sid);
  end if;
  if p_action='check' then
   if a.source_kind<>'review' then raise exception 'INVALID_EXAM_ACTION';end if;
   if not exists(select 1 from jsonb_array_elements(a.snapshot->'questions') x where x->'number'=p_payload->'number') or not (a.answers ? (p_payload->>'number')) then raise exception 'ANSWER_REQUIRED';end if;
   update public.hwarang_exam_attempts set review_checked=case when review_checked @> jsonb_build_array(p_payload->'number') then review_checked else review_checked||jsonb_build_array(p_payload->'number') end,revision=revision+1,updated_at=now() where id=sid;
   return private.exam_view(sid);
  end if;
  if p_action='save' then
   if a.source_kind='review' and exists(select 1 from jsonb_array_elements(a.review_checked) n where p_payload->'answers'->>(n#>>'{}') is distinct from a.answers->>(n#>>'{}')) then raise exception 'REVIEW_ALREADY_CHECKED';end if;
   if jsonb_typeof(p_payload->'answers') is distinct from 'object' or jsonb_typeof(p_payload->'flags') is distinct from 'array' then raise exception 'INVALID_ANSWERS';end if;
   for kv in select * from jsonb_each(p_payload->'answers') loop
    select value into q from jsonb_array_elements(a.snapshot->'questions') where value->>'number'=kv.key;
    if q is null or not exists(select 1 from jsonb_array_elements(q->'choices') c where c->'number'=kv.value) then raise exception 'INVALID_ANSWER';end if;
   end loop;
   for q in select value from jsonb_array_elements(p_payload->'flags') loop
    if not exists(select 1 from jsonb_array_elements(a.snapshot->'questions') x where x->'number'=q) then raise exception 'INVALID_FLAG';end if;
   end loop;
   if coalesce((p_payload->>'cursor')::integer,-1) not between 0 and jsonb_array_length(a.snapshot->'questions')-1 then raise exception 'INVALID_CURSOR';end if;
   update public.hwarang_exam_attempts set answers=p_payload->'answers',flags=p_payload->'flags',cursor=(p_payload->>'cursor')::integer,revision=revision+1,updated_at=now() where id=sid;
  else perform private.exam_finish(sid);end if;
  return private.exam_view(sid);
 end if;
 raise exception 'INVALID_EXAM_ACTION';
end $$;

revoke all on function public.hwarang_exam(uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_exam(uuid,text,jsonb) to service_role;
