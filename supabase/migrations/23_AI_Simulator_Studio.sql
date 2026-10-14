-- 23: AI Studio. Additive migration; existing ledgers, grants, history and briefing are preserved.
begin;
create or replace function private.studio_can_view(p_actor uuid,p_target_user_id uuid)
returns boolean language sql stable security invoker set search_path='' as $$
 select private.can_user_view(p_actor,p_target_user_id);
$$;

revoke all on function private.studio_can_view(uuid,uuid) from public,anon,authenticated;
grant execute on function private.studio_can_view(uuid,uuid) to service_role;

create table public.hwarang_studio_records (
 id uuid primary key references public.academy_sessions(id),
 user_id uuid not null references public.profiles(id),
 version integer not null default 0,
 data jsonb not null,
 locked_by text,
 updated_at timestamptz not null default now()
);
create table public.hwarang_studio_requests (
 op_key text primary key, session_id uuid not null references public.hwarang_studio_records(id),
 user_id uuid not null references public.profiles(id),
 base_version integer not null, purpose text not null,
 status text not null check(status in ('claimed','processing','received','completed','failed','uncertain')),
 request_id uuid references public.hwarang_ai_request_registry(request_id),
 result jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.hwarang_studio_shares (
 session_id uuid not null references public.hwarang_studio_records(id),
 recipient uuid not null references public.profiles(id),
 fields text[] not null, snapshot jsonb not null,
 active boolean not null default true, updated_at timestamptz not null default now(),
 primary key(session_id,recipient)
);
create table public.hwarang_studio_audit (
 id bigint generated always as identity primary key,
 actor uuid not null references public.profiles(id), session_id uuid not null,
 event text not null, detail jsonb not null default '{}', created_at timestamptz not null default now()
);
alter table public.hwarang_ai_usage_log alter column calculated_cost_usd drop not null;
alter table public.hwarang_ai_usage_log add column if not exists cost_status text not null default 'unknown';
update public.hwarang_ai_usage_log set cost_status='known' where calculated_cost_usd>0;
-- Raw transcripts and hidden customer facts are NEVER copied into manager-readable legacy tables.
alter table public.hwarang_studio_records enable row level security;
alter table public.hwarang_studio_requests enable row level security;
alter table public.hwarang_studio_shares enable row level security;
alter table public.hwarang_studio_audit enable row level security;
revoke all on public.hwarang_studio_records,public.hwarang_studio_requests,public.hwarang_studio_shares,public.hwarang_studio_audit from public,anon,authenticated;
grant all on public.hwarang_studio_records,public.hwarang_studio_requests,public.hwarang_studio_shares,public.hwarang_studio_audit to service_role;
grant usage on sequence public.hwarang_studio_audit_id_seq to service_role;
create index hwarang_studio_owner on public.hwarang_studio_records(user_id,updated_at desc);

create or replace function private.studio_check(p_actor uuid) returns void
language plpgsql security invoker set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active)
 or not exists(select 1 from public.hwarang_app_access where user_id=p_actor and app_code='academy' and is_enabled)
 or not exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code='academy.simulator')
 then raise exception 'STUDIO_ACCESS_DENIED'; end if;
end $$;
revoke all on function private.studio_check(uuid) from public,anon,authenticated;
grant execute on function private.studio_check(uuid) to service_role;

create or replace function public.hwarang_studio_store(p_actor uuid,p_data jsonb,p_version integer,p_op text default null)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare sid uuid; rec public.hwarang_studio_records; v integer; done boolean; payload jsonb;
begin
 perform private.studio_check(p_actor);
 sid:=(p_data->>'id')::uuid;
 if p_version is null or p_version<0 or sid is null or p_data->>'owner' is distinct from p_actor::text or p_data->>'schema' is distinct from '2'
 or not coalesce(p_data->>'mode' in ('PRACTICE','ASSESSMENT'),false) or jsonb_typeof(p_data->'turns') is distinct from 'array'
 or jsonb_array_length(p_data->'turns')>100 or octet_length(p_data::text)>12000000 then raise exception 'INVALID_STUDIO_DATA'; end if;
 if p_data->>'mode'='ASSESSMENT' and not exists(select 1 from public.get_hwarang_effective_permissions(p_actor)
 where permission_code='academy.formal_ai_assessment') then raise exception 'AI_ASSESSMENT_PERMISSION_REQUIRED'; end if;
 if p_version=0 then
  insert into public.academy_cases(id,owner_user_id,title,customer_alias,metadata)
  values(sid,p_actor,'AI 상담 훈련','가상 고객','{"training_engine":"studio"}') on conflict do nothing;
  if not exists(select 1 from public.academy_cases where id=sid and owner_user_id=p_actor and metadata->>'training_engine'='studio') then raise exception 'STUDIO_ACCESS_DENIED'; end if;
  insert into public.academy_sessions(id,case_id,user_id,stage,mode,engine_version,metadata)
  values(sid,sid,p_actor,p_data->>'stage',p_data->>'mode','1.13.0-studio','{"training_engine":"studio"}') on conflict do nothing;
  insert into public.hwarang_studio_records(id,user_id,data) values(sid,p_actor,p_data) on conflict do nothing;
 end if;
 select * into rec from public.hwarang_studio_records where id=sid and user_id=p_actor for update;
 if not found then raise exception 'STUDIO_ACCESS_DENIED'; end if;
 -- Idempotent save after a transport timeout.
 if rec.version=p_version+1 and (rec.data-'version')=(p_data-'version') then return rec.data; end if;
 if rec.version<>p_version then raise exception 'STUDIO_VERSION_CONFLICT'; end if;
 if rec.locked_by is not null and (p_op is distinct from rec.locked_by or not exists(
  select 1 from public.hwarang_studio_requests where op_key=p_op and status in ('completed','failed')))
 then raise exception 'STUDIO_REQUEST_PENDING'; end if;
 if p_version>0 and (rec.data->'case' is distinct from p_data->'case' or rec.data->>'mode' is distinct from p_data->>'mode')
 then raise exception 'STUDIO_IMMUTABLE_CASE'; end if;
 v:=rec.version+1;payload:=jsonb_set(p_data,'{version}',to_jsonb(v));
 update public.hwarang_studio_records set data=payload,version=v,locked_by=null,updated_at=now() where id=sid;
 done:=coalesce((p_data->>'ended')::boolean,false);
 update public.academy_sessions set
 status=case when done and (p_data->'report'<>'null'::jsonb or jsonb_array_length(p_data->'turns')=0) then
  case when p_data->>'end_reason' in ('offtrack','technical','user') then 'stopped' else 'completed' end else 'in_progress' end,
 stage=p_data->>'stage',last_turn_no=jsonb_array_length(p_data->'turns'),resume_allowed=not done,
 ended_at=case when done then now() else null end,
 metadata=jsonb_build_object('training_engine','studio','participated',jsonb_array_length(p_data->'turns')>0,'finished',done and p_data->'report'<>'null'::jsonb and p_data->>'end_reason' not in ('technical','offtrack'))
 where id=sid and user_id=p_actor;
 return payload;
end $$;

create or replace function public.hwarang_studio_get(p_actor uuid,p_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare d jsonb;
begin
 perform private.studio_check(p_actor);
 select data into d from public.hwarang_studio_records where id=p_id and user_id=p_actor;
 if d is null then raise exception 'STUDIO_ACCESS_DENIED';end if;return d;
end $$;

create or replace function public.hwarang_studio_list(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 perform private.studio_check(p_actor);
 return coalesce((select jsonb_agg(x) from (select id,version,updated_at,data->>'mode' mode,data->>'initial_stage' stage,
 data->>'ended' ended,data->>'end_reason' end_reason,jsonb_array_length(data->'turns') turns
 from public.hwarang_studio_records where user_id=p_actor order by updated_at desc limit 50)x),'[]');
end $$;

create or replace function public.hwarang_studio_claim(p_actor uuid,p_id uuid,p_version integer,p_op text,p_purpose text)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare rec public.hwarang_studio_records; req public.hwarang_studio_requests;
begin
 perform private.studio_check(p_actor);
 select * into rec from public.hwarang_studio_records where id=p_id and user_id=p_actor for update;
 if not found then raise exception 'STUDIO_ACCESS_DENIED';end if;
 select * into req from public.hwarang_studio_requests where op_key=p_op;
 if found then
  if req.user_id<>p_actor or req.session_id<>p_id then raise exception 'STUDIO_ACCESS_DENIED';end if;
  return to_jsonb(req)||jsonb_build_object('fresh',false);
 end if;
 if rec.version<>p_version then raise exception 'STUDIO_VERSION_CONFLICT';end if;
 if rec.locked_by is not null or exists(select 1 from public.hwarang_studio_requests where user_id=p_actor and status in ('claimed','processing','uncertain'))
 then raise exception 'STUDIO_REQUEST_PENDING';end if;
 if p_purpose not in ('CUSTOMER','COACH','EVALUATOR','TRANSCRIBE','SPEECH') or char_length(p_op)>180 then raise exception 'INVALID_STUDIO_REQUEST';end if;
 insert into public.hwarang_studio_requests(op_key,session_id,user_id,base_version,purpose,status)
 values(p_op,p_id,p_actor,p_version,p_purpose,'claimed') returning * into req;
 update public.hwarang_studio_records set locked_by=p_op where id=p_id;
 return to_jsonb(req)||jsonb_build_object('fresh',true);
end $$;

create or replace function public.hwarang_studio_request_update(p_actor uuid,p_op text,p_status text,p_request uuid,p_result jsonb)
returns void language plpgsql security invoker set search_path='' as $$
declare old public.hwarang_studio_requests;
begin
 select * into old from public.hwarang_studio_requests where op_key=p_op and user_id=p_actor for update;
 if not found then raise exception 'STUDIO_ACCESS_DENIED';end if;
 if not ((old.status='claimed' and p_status in ('processing','failed','uncertain')) or
         (old.status='processing' and p_status in ('received','failed','uncertain')) or
         (old.status='received' and p_status='completed') or old.status=p_status)
 then raise exception 'INVALID_STUDIO_TRANSITION';end if;
 update public.hwarang_studio_requests set status=p_status,request_id=coalesce(p_request,request_id),
 result=coalesce(p_result,result),updated_at=now() where op_key=p_op;
 if p_status='completed' and p_request is not null then
  insert into public.hwarang_ai_usage_log(request_id,user_id,academy_session_id,ai_role,model,
   input_tokens,cached_tokens,output_tokens,credits_charged,voice_seconds_charged,calculated_cost_usd,cost_status,prompt_version)
  values(p_request,p_actor,old.session_id,case when old.purpose in ('TRANSCRIBE','SPEECH') then 'VOICE' else old.purpose end,
   coalesce(p_result->>'model','unknown'),coalesce((p_result->'usage'->>'input_tokens')::bigint,0),
   coalesce((p_result->'usage'->'input_tokens_details'->>'cached_tokens')::bigint,0),
   coalesce((p_result->'usage'->>'output_tokens')::bigint,0),coalesce((p_result->>'credits')::bigint,0),
   coalesce((p_result->>'seconds')::bigint,0),null,'unknown','studio-1.13.0') on conflict(request_id) do nothing;
 end if;
end $$;

create or replace function public.hwarang_studio_recipients(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 perform private.studio_check(p_actor);
 return coalesce((select jsonb_agg(jsonb_build_object('id',id,'name',display_name)) from public.profiles
 where is_active and id<>p_actor and private.studio_can_view(id,p_actor)),'[]');
end $$;

create or replace function public.hwarang_studio_share(p_actor uuid,p_id uuid,p_recipient uuid,p_fields text[],p_active boolean)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare d jsonb; snap jsonb;
begin
 perform private.studio_check(p_actor);
 select data into d from public.hwarang_studio_records where id=p_id and user_id=p_actor;
 if d is null then raise exception 'STUDIO_ACCESS_DENIED';end if;
 if p_active then
  if not (d->>'ended')::boolean or d->>'mode'<>'PRACTICE' or p_recipient=p_actor
   or not private.studio_can_view(p_recipient,p_actor) then raise exception 'SHARE_SCOPE_DENIED';end if;
  if coalesce(cardinality(p_fields),0)=0 or not p_fields<@array['summary','feedback','transcript']::text[] then raise exception 'INVALID_SHARE_FIELDS';end if;
  snap:=jsonb_build_object('session_id',p_id,'stage',d->>'initial_stage','mode',d->>'mode');
  if 'summary'=any(p_fields) then snap:=snap||jsonb_build_object('summary',jsonb_build_object('status',d->'report'->>'status',
    'levels',(select coalesce(jsonb_agg(jsonb_build_object('criterion',e->>'criterion','level',e->>'level')),'[]') from jsonb_array_elements(coalesce(d->'report'->'rows','[]'))e)));end if;
  if 'feedback'=any(p_fields) then snap:=snap||jsonb_build_object('feedback',d->'report');end if;
  if 'transcript'=any(p_fields) then snap:=snap||jsonb_build_object('transcript',d->'messages');end if;
  insert into public.hwarang_studio_shares(session_id,recipient,fields,snapshot,active) values(p_id,p_recipient,p_fields,snap,true)
  on conflict(session_id,recipient) do update set fields=excluded.fields,snapshot=excluded.snapshot,active=true,updated_at=now();
 else
  update public.hwarang_studio_shares set active=false,updated_at=now() where session_id=p_id and recipient=p_recipient;
 end if;
 insert into public.hwarang_studio_audit(actor,session_id,event,detail) values(p_actor,p_id,case when p_active then 'share' else 'revoke' end,
 jsonb_build_object('recipient',p_recipient,'fields',p_fields));
 return coalesce(snap,'{}');
end $$;

create or replace function public.hwarang_studio_manager(p_actor uuid,p_id uuid default null)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare d jsonb; owner_id uuid; snap jsonb;
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active) then raise exception 'STUDIO_ACCESS_DENIED';end if;
 if p_id is null then
  return coalesce((select jsonb_agg(x) from (select r.id,r.user_id,p.display_name,
    r.data->>'mode' mode, ((r.data->>'ended')::boolean and r.data->'report'<>'null'::jsonb and r.data->>'end_reason' not in ('technical','offtrack')) finished,
    exists(select 1 from public.hwarang_studio_shares s where s.session_id=r.id and s.recipient=p_actor and s.active) shared
   from public.hwarang_studio_records r join public.profiles p on p.id=r.user_id
   where r.user_id<>p_actor and private.studio_can_view(p_actor,r.user_id) and jsonb_array_length(r.data->'turns')>0
   order by r.updated_at desc limit 200)x),'[]');
 end if;
 select data,user_id into d,owner_id from public.hwarang_studio_records where id=p_id;
 if d is null or owner_id=p_actor or not private.studio_can_view(p_actor,owner_id) then raise exception 'STUDIO_ACCESS_DENIED';end if;
 if d->>'mode'='ASSESSMENT' then
  snap:=jsonb_build_object('transcript',d->'messages','feedback',d->'report','end_reason',d->>'end_reason','review_requested',d->'review_requested');
 else
  select snapshot into snap from public.hwarang_studio_shares where session_id=p_id and recipient=p_actor and active;
  if snap is null then raise exception 'SHARE_NOT_GRANTED';end if;
 end if;
 insert into public.hwarang_studio_audit(actor,session_id,event) values(p_actor,p_id,'read');
 return snap;
end $$;

create or replace function public.hwarang_studio_review(p_actor uuid,p_id uuid,p_note text,p_response boolean default false)
returns void language plpgsql security invoker set search_path='' as $$
declare owner_id uuid;
begin
 select user_id into owner_id from public.hwarang_studio_records where id=p_id;
 if owner_id is null or char_length(btrim(p_note))<1 or char_length(p_note)>1000 then raise exception 'INVALID_REVIEW';end if;
 if not exists(select 1 from public.hwarang_studio_records where id=p_id and data->>'mode'='ASSESSMENT') then raise exception 'STUDIO_ACCESS_DENIED';end if;
 if p_response then
  if owner_id=p_actor or not private.studio_can_view(p_actor,owner_id)
   or not exists(select 1 from public.hwarang_studio_records where id=p_id and data->>'mode'='ASSESSMENT') then raise exception 'STUDIO_ACCESS_DENIED';end if;
 else
  if owner_id<>p_actor then raise exception 'STUDIO_ACCESS_DENIED';end if;
 end if;
 insert into public.hwarang_studio_audit(actor,session_id,event,detail) values(p_actor,p_id,
 case when p_response then 'review_response' else 'review_request' end,jsonb_build_object('note',p_note));
end $$;

create or replace function public.hwarang_studio_reviews(p_actor uuid,p_id uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare owner_id uuid; m text;
begin
 select user_id,data->>'mode' into owner_id,m from public.hwarang_studio_records where id=p_id;
 if owner_id is null or (owner_id<>p_actor and (m<>'ASSESSMENT' or not private.studio_can_view(p_actor,owner_id))) then raise exception 'STUDIO_ACCESS_DENIED';end if;
 return coalesce((select jsonb_agg(jsonb_build_object('event',event,'note',detail->>'note','created_at',created_at) order by created_at)
 from public.hwarang_studio_audit where session_id=p_id and event in ('review_request','review_response')),'[]');
end $$;

revoke all on function public.hwarang_studio_store(uuid,jsonb,integer,text) from public,anon,authenticated;
grant execute on function public.hwarang_studio_store(uuid,jsonb,integer,text) to service_role;

revoke all on function public.hwarang_studio_get(uuid,uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_get(uuid,uuid) to service_role;

revoke all on function public.hwarang_studio_list(uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_list(uuid) to service_role;

revoke all on function public.hwarang_studio_claim(uuid,uuid,integer,text,text) from public,anon,authenticated;
grant execute on function public.hwarang_studio_claim(uuid,uuid,integer,text,text) to service_role;

revoke all on function public.hwarang_studio_request_update(uuid,text,text,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_studio_request_update(uuid,text,text,uuid,jsonb) to service_role;

revoke all on function public.hwarang_studio_recipients(uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_recipients(uuid) to service_role;

revoke all on function public.hwarang_studio_share(uuid,uuid,uuid,text[],boolean) from public,anon,authenticated;
grant execute on function public.hwarang_studio_share(uuid,uuid,uuid,text[],boolean) to service_role;

revoke all on function public.hwarang_studio_manager(uuid,uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_manager(uuid,uuid) to service_role;

revoke all on function public.hwarang_studio_review(uuid,uuid,text,boolean) from public,anon,authenticated;
grant execute on function public.hwarang_studio_review(uuid,uuid,text,boolean) to service_role;

revoke all on function public.hwarang_studio_reviews(uuid,uuid) from public,anon,authenticated;
grant execute on function public.hwarang_studio_reviews(uuid,uuid) to service_role;

-- Apply the approved private-practice policy to legacy authenticated table access too.
-- The old permissive organizational policies still constrain formal assessments.
create policy studio_private_sessions on public.academy_sessions as restrictive for select to authenticated
using (user_id=auth.uid() or mode='ASSESSMENT');
create policy studio_private_assessments on public.academy_assessments as restrictive for select to authenticated
using (user_id=auth.uid() or exists(select 1 from public.academy_sessions s where s.id=session_id and s.mode='ASSESSMENT'));
create policy studio_private_cases on public.academy_cases as restrictive for select to authenticated
using (owner_user_id=auth.uid() or exists(select 1 from public.academy_sessions s where s.case_id=academy_cases.id and s.mode='ASSESSMENT'));

create or replace function public.hwarang_studio_pending(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active and role='super_admin') then raise exception 'ADMIN_ACCESS_DENIED';end if;
 return coalesce((select jsonb_agg(jsonb_build_object('op_key',op_key,'user_id',user_id,'purpose',purpose,'status',status,'request_id',request_id,'created_at',created_at))
 from public.hwarang_studio_requests where status in ('claimed','processing','uncertain')),'[]');
end $$;
create or replace function public.hwarang_studio_resolve(p_actor uuid,p_op text,p_delivered boolean,p_note text)
returns void language plpgsql security invoker set search_path='' as $$
declare r public.hwarang_studio_requests; q public.hwarang_ai_request_registry;
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active and role='super_admin') then raise exception 'ADMIN_ACCESS_DENIED';end if;
 if char_length(btrim(p_note))<10 then raise exception 'EVIDENCE_REQUIRED';end if;
 select * into r from public.hwarang_studio_requests where op_key=p_op for update;
 if not found or r.status not in ('claimed','processing','uncertain') or r.updated_at>now()-interval '10 minutes' then raise exception 'REQUEST_NOT_RECONCILABLE';end if;
 select * into q from public.hwarang_ai_request_registry where request_id=r.request_id for update;
 if q.request_id is not null then
  if q.status not in ('reserved','processing') then raise exception 'LEDGER_REVIEW_REQUIRED';end if;
  if r.purpose in ('TRANSCRIBE','SPEECH') then
   -- Delivered audio needs exact duration; never guess the maximum reservation.
   if p_delivered then raise exception 'VOICE_DURATION_REVIEW_REQUIRED';end if;
   perform public.finalize_hwarang_voice_request(q.request_id,'failed',0);
  else
   perform public.finalize_hwarang_ai_request(q.request_id,case when p_delivered then 'completed' else 'failed' end,
     case when p_delivered then q.reserved_credits::integer else 0 end);
  end if;
 elsif p_delivered then raise exception 'LEDGER_REVIEW_REQUIRED';
 end if;
 update public.hwarang_studio_requests set status='failed',updated_at=now() where op_key=p_op;
 update public.hwarang_studio_records set locked_by=null,version=version+1,
  data=jsonb_set(data,'{version}',to_jsonb(version+1)),updated_at=now() where id=r.session_id;
 insert into public.hwarang_studio_audit(actor,session_id,event,detail) values(p_actor,r.session_id,'resolve_request',
  jsonb_build_object('op_key',p_op,'provider_delivered',p_delivered,'note',p_note));
end $$;
revoke all on function public.hwarang_studio_pending(uuid) from public,anon,authenticated;
revoke all on function public.hwarang_studio_resolve(uuid,text,boolean,text) from public,anon,authenticated;
grant execute on function public.hwarang_studio_pending(uuid) to service_role;
grant execute on function public.hwarang_studio_resolve(uuid,text,boolean,text) to service_role;

create table public.hwarang_studio_config(id integer primary key check(id=1),settings jsonb not null default '{}');
insert into public.hwarang_studio_config(id) values(1);
alter table public.hwarang_studio_config enable row level security;
revoke all on public.hwarang_studio_config from public,anon,authenticated;
grant all on public.hwarang_studio_config to service_role;
create or replace function public.hwarang_studio_settings(p_actor uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
begin
 perform private.studio_check(p_actor);
 return (select settings from public.hwarang_studio_config where id=1) || coalesce((select jsonb_object_agg(lower(role_code)||'_model',provider_model)
 from public.hwarang_ai_model_policy where role_code in ('CUSTOMER','COACH','EVALUATOR') and is_active and nullif(provider_model,'') is not null),'{}'::jsonb);
end $$;
create or replace function public.hwarang_studio_configure(p_actor uuid,p_settings jsonb)
returns void language plpgsql security invoker set search_path='' as $$
declare k text;v jsonb;
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active and role='super_admin') then raise exception 'ADMIN_ACCESS_DENIED';end if;
 if jsonb_typeof(p_settings)<>'object' then raise exception 'INVALID_SETTINGS';end if;
 for k,v in select * from jsonb_each(p_settings) loop
  if k in ('customer_model','coach_model','evaluator_model','transcription_model','speech_model') then
   if jsonb_typeof(v)<>'string' or char_length(v#>>'{}') not between 1 and 100 then raise exception 'INVALID_MODEL';end if;
  elsif k in ('customer_credits','coach_credits','evaluator_credits') then
   if jsonb_typeof(v)<>'number' or (v#>>'{}')::integer not between 1 and 10000 then raise exception 'INVALID_CREDITS';end if;
  else raise exception 'INVALID_SETTING_KEY';end if;
 end loop;
 update public.hwarang_studio_config set settings=p_settings where id=1;
 update public.hwarang_ai_model_policy set provider_model=p_settings->>(lower(role_code)||'_model'),updated_by=p_actor,updated_at=now()
 where role_code in ('CUSTOMER','COACH','EVALUATOR') and p_settings ? (lower(role_code)||'_model');
 insert into public.hwarang_activity_log(user_id,app_code,event_code,feature_code,metadata)
 values(p_actor,'academy','studio_settings_changed','academy.simulator',p_settings);
end $$;
revoke all on function public.hwarang_studio_settings(uuid) from public,anon,authenticated;
revoke all on function public.hwarang_studio_configure(uuid,jsonb) from public,anon,authenticated;
grant execute on function public.hwarang_studio_settings(uuid) to service_role;
grant execute on function public.hwarang_studio_configure(uuid,jsonb) to service_role;

notify pgrst,'reload schema';
commit;
