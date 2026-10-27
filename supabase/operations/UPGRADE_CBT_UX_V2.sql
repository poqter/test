begin;
alter table public.hwarang_exam_attempts add column if not exists source_kind text not null default 'round' check(source_kind in ('round','random','review'));
alter table public.hwarang_exam_attempts add column if not exists parent_attempt_id uuid references public.hwarang_exam_attempts(id);
alter table public.hwarang_exam_attempts add column if not exists review_checked jsonb not null default '[]';
create index if not exists hwarang_exam_parent on public.hwarang_exam_attempts(parent_attempt_id);
create index if not exists hwarang_exam_bank_fk on public.hwarang_exam_attempts(exam_id);

-- Comparison keys only; original JSON text is never rewritten.
create or replace function private.exam_normalize(v jsonb) returns jsonb
language plpgsql immutable security invoker set search_path='' as $$
declare result jsonb;
begin
 case jsonb_typeof(v)
 when 'string' then return to_jsonb(regexp_replace(v#>>'{}','[[:space:]]','','g'));
 when 'array' then select coalesce(jsonb_agg(private.exam_normalize(x) order by n),'[]') into result from jsonb_array_elements(v) with ordinality t(x,n);return result;
 when 'object' then select coalesce(jsonb_object_agg(k,private.exam_normalize(x)),'{}') into result from jsonb_each(v) t(k,x);return result;
 else return v;
 end case;
end $$;
create or replace function private.exam_fingerprint(q jsonb) returns text
language sql immutable security invoker set search_path='' as $$
select md5(private.exam_normalize(jsonb_build_object('question',q->'question','passage',q->'passage','choices',q->'choices','table',q->'table','underlined_text',q->'underlined_text'))::text);
$$;
create or replace function private.exam_random_snapshot(actor uuid,family_code text,track_code text) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare b public.hwarang_exam_bank; slot record; candidate jsonb; chosen jsonb:='[]';used text[]:='{}';selected_sections jsonb;out_sections jsonb;fp text;n integer:=0;bucket text[];pool_data jsonb;seen text[];
begin
 select * into b from public.hwarang_exam_bank where family=family_code and enabled order by id limit 1;
 if not found then raise exception 'EXAM_NOT_FOUND';end if;
 select jsonb_agg(s) into selected_sections from jsonb_array_elements(b.data->'sections') s where track_code='combined' or s->>'key'=track_code;
  with pool as (
   select x||jsonb_build_object('source_exam_id',bank.id,'source_title',bank.title,'source_number',x->'number') item,
    private.exam_fingerprint(x) fingerprint,
    private.exam_normalize(jsonb_build_object('answer',x->'answer','explanation',x->'explanation'))::text solution,
    array(select s->>'key' from jsonb_array_elements(bank.data->'sections') s where (track_code='combined' or s->>'key'=track_code) and s->'numbers' @> jsonb_build_array(x->'number') order by s->>'key') keys
   from public.hwarang_exam_bank bank cross join lateral jsonb_array_elements(bank.data->'questions') x where bank.enabled and bank.family=family_code
  ) select jsonb_agg(jsonb_build_object('item',item,'fp',fingerprint,'keys',to_jsonb(keys))) into pool_data from (
   select distinct on(fingerprint,keys) item,fingerprint,keys from pool p
   where fingerprint in (select fingerprint from pool group by fingerprint having count(distinct solution)=1)
   order by fingerprint,keys,item->>'source_exam_id'
  ) candidates;
 select coalesce(array_agg(distinct private.exam_fingerprint(old)),'{}') into seen from public.hwarang_exam_attempts a cross join lateral jsonb_array_elements(a.snapshot->'questions') old where a.user_id=actor;
 -- Each slot retains its section-membership and point value, including shared questions.
 for slot in select q, array(select s->>'key' from jsonb_array_elements(selected_sections) s where s->'numbers' @> jsonb_build_array(q->'number') order by s->>'key') keys
  from jsonb_array_elements(b.data->'questions') q where exists(select 1 from jsonb_array_elements(selected_sections) s where s->'numbers' @> jsonb_build_array(q->'number')) order by random() loop
  select c->'item',c->>'fp' into candidate,fp from jsonb_array_elements(pool_data) c
   where c->'keys'=to_jsonb(slot.keys) and c->'item'->'points'=slot.q->'points' and not (c->>'fp')=any(used)
   order by ((c->>'fp')=any(seen)),random() limit 1;
  if candidate is null then raise exception 'INSUFFICIENT_UNIQUE_QUESTIONS';end if;
  n:=n+1;used:=array_append(used,fp);
  chosen:=chosen||jsonb_build_array(candidate||jsonb_build_object('number',n,'section_keys',to_jsonb(slot.keys)));
 end loop;
 select jsonb_agg(jsonb_build_object('key',s->>'key','name',s->>'name','numbers',(select jsonb_agg(x->'number') from jsonb_array_elements(chosen) x where x->'section_keys' ? (s->>'key')))) into out_sections from jsonb_array_elements(selected_sections) s;
 return jsonb_build_object('title',case when family_code='life' then '생명보험' else '손해보험' end||' · 랜덤 모의고사','exam_id',b.id,'questions',chosen,'sections',out_sections,'kind','random');
end $$;
revoke all on function private.exam_normalize(jsonb),private.exam_fingerprint(jsonb),private.exam_random_snapshot(uuid,text,text) from public,anon,authenticated;
grant execute on function private.exam_normalize(jsonb),private.exam_fingerprint(jsonb),private.exam_random_snapshot(uuid,text,text) to service_role;
create or replace function private.exam_grade(p_snapshot jsonb,p_answers jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare section jsonb; q jsonb; score integer; out_scores jsonb:='[]'; all_pass boolean:=true;
begin
 for section in select value from jsonb_array_elements(p_snapshot->'sections') loop
  score:=0;
  for q in select value from jsonb_array_elements(p_snapshot->'questions') loop
   if (section->'numbers') @> jsonb_build_array((q->>'number')::integer)
   and p_answers->>(q->>'number')=q->>'answer' then score:=score+case when p_snapshot->>'kind'='review' then 1 else (q->>'points')::integer end;end if;
  end loop;
  if p_snapshot->>'kind'='review' then score:=round(100.0*score/greatest(1,jsonb_array_length(section->'numbers')));end if;
  all_pass:=all_pass and score>=60;
  out_scores:=out_scores||jsonb_build_array(jsonb_build_object('name',section->>'name','score',score,'passed',score>=60));
 end loop;
 return jsonb_build_object('sections',out_scores,'passed',all_pass);
end $$;

create or replace function private.exam_finish(p_id uuid) returns void
language sql security invoker set search_path='' as $$
 update public.hwarang_exam_attempts set status='submitted',
 submitted_at=case when deadline is not null and deadline<now() then deadline else now() end,
 result=private.exam_grade(snapshot,answers),revision=revision+1,updated_at=now()
 where id=p_id and status='active';
$$;

create or replace function private.exam_view(p_id uuid) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare a public.hwarang_exam_attempts; questions jsonb;
begin
 select * into strict a from public.hwarang_exam_attempts where id=p_id;
 select jsonb_agg(case when a.status='submitted' or (a.source_kind='review' and a.review_checked @> jsonb_build_array((q->>'number')::integer)) then q else q-'answer'-'explanation' end order by ord)
 into questions from jsonb_array_elements(a.snapshot->'questions') with ordinality as t(q,ord);
 return (to_jsonb(a)-'snapshot')||jsonb_build_object('title',a.snapshot->>'title','questions',questions,
 'server_now',now(),'remaining_seconds',case when a.deadline is null then null else greatest(0,ceil(extract(epoch from a.deadline-now()))) end);
end $$;

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
 elsif p_action in ('get','save','submit','check') then
  sid:=(p_payload->>'id')::uuid;
  select * into a from public.hwarang_exam_attempts where id=sid for update;
  if not found then raise exception 'EXAM_NOT_FOUND';end if;
  if a.user_id<>p_actor and not (p_action='get' and private.can_user_view(p_actor,a.user_id)) then raise exception 'EXAM_ACCESS_DENIED';end if;
  if a.status='active' and a.deadline<=now() then perform private.exam_finish(sid);return private.exam_view(sid);end if;
  if p_action='get' or a.status='submitted' then return private.exam_view(sid);end if;
  if (p_payload->>'revision')::integer is distinct from a.revision then raise exception 'EXAM_CONFLICT_RELOAD';end if;
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
revoke all on function private.exam_check(uuid),private.exam_grade(jsonb,jsonb),private.exam_finish(uuid),private.exam_view(uuid),public.hwarang_exam(uuid,text,jsonb) from public,anon,authenticated;
grant execute on function private.exam_check(uuid),private.exam_grade(jsonb,jsonb),private.exam_finish(uuid),private.exam_view(uuid),public.hwarang_exam(uuid,text,jsonb) to service_role;
commit;
