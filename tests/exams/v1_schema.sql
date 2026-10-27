begin;
create table if not exists public.hwarang_exam_bank (
 id text primary key, title text not null, family text not null check(family in ('life','nonlife')),
 revision text not null, data jsonb not null, enabled boolean not null default true
);
create table if not exists public.hwarang_exam_attempts (
 id uuid primary key, user_id uuid not null references public.profiles(id),
 exam_id text not null references public.hwarang_exam_bank(id), mode text not null check(mode in ('exam','practice')),
 track text not null check(track in ('main','third','combined')), snapshot jsonb not null,
 answers jsonb not null default '{}', flags jsonb not null default '[]', cursor integer not null default 0,
 revision integer not null default 0, status text not null default 'active' check(status in ('active','submitted')),
 started_at timestamptz not null default now(), deadline timestamptz, submitted_at timestamptz,
 result jsonb, updated_at timestamptz not null default now()
);
create unique index if not exists hwarang_exam_one_active on public.hwarang_exam_attempts(user_id) where status='active';
create index if not exists hwarang_exam_user_date on public.hwarang_exam_attempts(user_id,started_at desc);
alter table public.hwarang_exam_bank enable row level security;
alter table public.hwarang_exam_attempts enable row level security;
revoke all on public.hwarang_exam_bank,public.hwarang_exam_attempts from public,anon,authenticated;
grant all on public.hwarang_exam_bank,public.hwarang_exam_attempts to service_role;

create or replace function private.exam_check(p_actor uuid) returns void
language plpgsql security invoker set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active)
 or not exists(select 1 from public.hwarang_app_access where user_id=p_actor and app_code='academy' and is_enabled)
 or not exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code='academy.assessment')
 then raise exception 'EXAM_ACCESS_DENIED'; end if;
end $$;

create or replace function private.exam_grade(p_snapshot jsonb,p_answers jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare section jsonb; q jsonb; score integer; out_scores jsonb:='[]'; all_pass boolean:=true;
begin
 for section in select value from jsonb_array_elements(p_snapshot->'sections') loop
  score:=0;
  for q in select value from jsonb_array_elements(p_snapshot->'questions') loop
   if (section->'numbers') @> jsonb_build_array((q->>'number')::integer)
   and p_answers->>(q->>'number')=q->>'answer' then score:=score+(q->>'points')::integer;end if;
  end loop;
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
 select jsonb_agg(case when a.status='submitted' then q else q-'answer'-'explanation' end order by ord)
 into questions from jsonb_array_elements(a.snapshot->'questions') with ordinality as t(q,ord);
 return (to_jsonb(a)-'snapshot')||jsonb_build_object('title',a.snapshot->>'title','questions',questions,
 'remaining_seconds',case when a.deadline is null then null else greatest(0,ceil(extract(epoch from a.deadline-now()))) end);
end $$;

create or replace function public.hwarang_exam(p_actor uuid,p_action text,p_payload jsonb default '{}') returns jsonb
language plpgsql security invoker set search_path='' as $$
declare a public.hwarang_exam_attempts; b public.hwarang_exam_bank; sid uuid; snap jsonb; sections jsonb;
 nums jsonb; qs jsonb; kv record; q jsonb; out_rows jsonb; target uuid; desired text;
begin
 perform private.exam_check(p_actor);
 if p_action='catalog' then
  return coalesce((select jsonb_agg(jsonb_build_object('id',id,'title',title,'family',family) order by id)
   from public.hwarang_exam_bank where enabled),'[]');
 elsif p_action='start' then
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
   order by rec.started_at desc limit 1000) r;
  return out_rows;
 elsif p_action='roster' then
  if not exists(select 1 from public.profiles where id=p_actor and (role='super_admin' or position_code in ('team_leader','deputy_branch_manager','branch_manager','division_head','chief_representative'))) then raise exception 'EXAM_ACCESS_DENIED';end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id',p.id,'display_name',p.display_name,'organization_id',p.organization_unit_id,'organization_name',o.name,'groups',(select coalesce(jsonb_agg(jsonb_build_object('id',anc.id,'name',anc.name,'type',anc.unit_type)),'[]') from public.organization_units anc where private.is_org_descendant(anc.id,p.organization_unit_id))))
   from public.profiles p left join public.organization_units o on o.id=p.organization_unit_id where p.is_active and private.can_user_view(p_actor,p.id)),'[]');
 elsif p_action in ('get','save','submit') then
  sid:=(p_payload->>'id')::uuid;
  select * into a from public.hwarang_exam_attempts where id=sid for update;
  if not found then raise exception 'EXAM_NOT_FOUND';end if;
  if a.user_id<>p_actor and not (p_action='get' and private.can_user_view(p_actor,a.user_id)) then raise exception 'EXAM_ACCESS_DENIED';end if;
  if a.status='active' and a.deadline<=now() then perform private.exam_finish(sid);return private.exam_view(sid);end if;
  if p_action='get' or a.status='submitted' then return private.exam_view(sid);end if;
  if (p_payload->>'revision')::integer is distinct from a.revision then raise exception 'EXAM_CONFLICT_RELOAD';end if;
  if p_action='save' then
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
