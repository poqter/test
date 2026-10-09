-- Additive after 19/20. Never reinitialize Migration 16 or existing accounts.
begin;
do $$ begin
 if to_regclass('public.hwarang_briefing_daily_runs') is null or to_regclass('public.hwarang_briefing_public_shares') is null
 or to_regclass('public.hwarang_ai_runtime_config') is null then
  raise exception 'Apply existing account/security and daily operation migrations 19/20 first; never reinitialize Migration 16';
 end if;
end $$;
create table if not exists public.hwarang_briefing_operating_policy (
 policy_key text primary key check(policy_key='WORKSPACE'),
 scheduled_generation_enabled boolean not null default false,
 automatic_publication_enabled boolean not null default false,
 external_sharing_approved boolean not null default false,
 approved_by uuid references public.profiles(id), approved_at timestamptz,
 updated_at timestamptz not null default now()
);
alter table public.hwarang_briefing_operating_policy add column if not exists scheduled_generation_enabled boolean not null default false;
insert into public.hwarang_briefing_operating_policy(policy_key) values('WORKSPACE') on conflict do nothing;
create table if not exists public.hwarang_briefing_calendar_days (
 day date primary key, is_business_day boolean not null, holiday_name text not null default ''
);
alter table public.hwarang_briefing_operating_policy enable row level security;
alter table public.hwarang_briefing_calendar_days enable row level security;
revoke all on public.hwarang_briefing_operating_policy,public.hwarang_briefing_calendar_days from anon,authenticated;
grant select,insert,update on public.hwarang_briefing_operating_policy,public.hwarang_briefing_calendar_days to service_role;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('briefing-share-assets','briefing-share-assets',false,4000000,array['application/pdf','image/png'])
on conflict(id) do update set public=false,file_size_limit=4000000,allowed_mime_types=excluded.allowed_mime_types;

create or replace function public.hwarang_verified_briefing_days(p_profile text)
returns integer language sql stable security definer set search_path='' as $$
 select count(distinct b.briefing_date)::integer
 from public.hwarang_briefings b join public.hwarang_briefing_revisions r on r.briefing_id=b.id
 join public.hwarang_briefing_snapshots s on s.revision_id=r.id
 join public.hwarang_briefing_calendar_days c on c.day=b.briefing_date and c.is_business_day
 where b.profile_code=p_profile and b.briefing_date between (now() at time zone 'Asia/Seoul')::date-30 and (now() at time zone 'Asia/Seoul')::date
 and r.validation_status='ok' and r.coverage_status='healthy'
 and s.qa_payload->>'internal_body_ready'='true'
$$;

create or replace function public.hwarang_set_briefing_policy(p_actor uuid,p_automatic boolean,p_external boolean,p_scheduled boolean default false)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if not exists(select 1 from public.profiles where id=p_actor and is_active and role='super_admin') then
  raise exception 'Highest administrator approval required';
 end if;
 update public.hwarang_briefing_operating_policy set scheduled_generation_enabled=p_scheduled,automatic_publication_enabled=p_automatic,
  external_sharing_approved=p_external,approved_by=p_actor,
  approved_at=case when p_external then now() else null end,updated_at=now() where policy_key='WORKSPACE';
 if not found then raise exception 'Launch policy unavailable'; end if;
 update public.hwarang_briefing_revisions r set external_share_allowed=p_external and r.external_qa_passed
 from public.hwarang_briefing_snapshots s where s.revision_id=r.id and r.publication_status='published'
 and r.validation_status='ok' and r.coverage_status='healthy' and s.qa_payload->>'public_body_ready'='true';
 insert into public.hwarang_briefing_audit_log(actor_type,actor_user_id,action,details)
 values('user',p_actor,'BRIEFING_ORGANIZATION_POLICY_CHANGED',jsonb_build_object('scheduled_generation',p_scheduled,'automatic',p_automatic,'external',p_external));
 return true;
end $$;

-- Policy gates apply on every read. Disabling the policy closes old links too.
create or replace function public.hwarang_read_public_briefing(p_token text)
returns jsonb language sql stable security definer set search_path='' as $$
 select ps.public_packet from public.hwarang_briefing_public_shares ps
 join public.hwarang_briefing_revisions r on r.id=ps.revision_id
 join public.hwarang_briefings b on b.id=r.briefing_id and b.current_published_revision_id=r.id
 join public.hwarang_briefing_snapshots s on s.revision_id=r.id
 join public.hwarang_briefing_operating_policy op on op.policy_key='WORKSPACE' and op.external_sharing_approved
 join public.profiles u on u.id=ps.sender_user_id and u.is_active
 where ps.token=p_token and ps.revoked_at is null and ps.expires_at>now()
 and r.publication_status='published' and r.validation_status='ok' and r.coverage_status='healthy'
 and r.external_share_allowed and r.external_qa_passed
 and s.qa_payload->>'internal_body_ready'='true' and s.qa_payload->>'public_body_ready'='true'
 and ps.public_packet->>'schema'='hwarang-share-v3'
 and p_token ~ '^[A-Za-z0-9_-]{32,64}$'
 limit 1
$$;

create or replace function public.hwarang_publish_briefing(p_briefing uuid,p_revision uuid,p_actor uuid default null)
returns boolean language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_revisions; s public.hwarang_briefing_snapshots; allowed boolean;
begin
 if p_actor is not null and not exists(select 1 from public.profiles u where u.id=p_actor and u.is_active
 and (u.role='super_admin' or exists(select 1 from public.get_hwarang_effective_permissions(p_actor) where permission_code='workspace.briefing_manage'))) then
 raise exception 'Briefing manager required'; end if;
 perform 1 from public.hwarang_briefings where id=p_briefing for update;
 select * into r from public.hwarang_briefing_revisions where id=p_revision and briefing_id=p_briefing for update;
 if not found or r.validation_status<>'ok' or r.coverage_status<>'healthy' or r.publication_status='hidden' then
  raise exception 'Briefing validation incomplete';
 end if;
 if p_actor is null and not exists(select 1 from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE' and automatic_publication_enabled) then
  raise exception 'Automatic publication approval required';
 end if;
 select * into s from public.hwarang_briefing_snapshots where revision_id=r.id;
 if not found or coalesce(s.qa_payload->>'internal_body_ready','')<>'true' then raise exception 'Internal body validation incomplete'; end if;
 if coalesce(jsonb_typeof(s.content_payload->'issues'),'null')<>'array' then raise exception 'Issues missing'; end if;
 if jsonb_array_length(s.content_payload->'issues')<2 then raise exception 'Insufficient issues'; end if;
 if s.content_payload->>'profile_code'='MARKET' and coalesce(s.content_payload->'market_metrics'->>'complete','')<>'true' then
  raise exception 'Market observations incomplete';
 end if;
 allowed=coalesce(s.qa_payload->>'public_body_ready','')='true'
   and exists(select 1 from public.hwarang_briefing_operating_policy where policy_key='WORKSPACE' and external_sharing_approved);
 update public.hwarang_briefing_revisions set publication_status='published',published_at=now(),
  external_qa_passed=coalesce(s.qa_payload->>'public_body_ready','')='true',external_share_allowed=allowed,approved_by=p_actor where id=r.id;
 update public.hwarang_briefings set current_published_revision_id=r.id where id=p_briefing;
 insert into public.hwarang_briefing_audit_log(actor_type,actor_user_id,action,briefing_id,revision_id,details)
 values(case when p_actor is null then 'system' else 'user' end,p_actor,'BRIEFING_PUBLISHED',p_briefing,r.id,jsonb_build_object('external_allowed',allowed));
 return true;
end $$;

-- The existing global AI OFF switch now also prevents briefing reservations.
create or replace function public.hwarang_reserve_briefing_request(p_date date,p_kind text)
returns boolean language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_daily_budget;
begin
 if not exists(select 1 from public.hwarang_ai_runtime_config where config_id=1 and service_enabled) then raise exception 'AI_SERVICE_DISABLED'; end if;
 insert into public.hwarang_briefing_daily_budget(briefing_date) values(p_date) on conflict do nothing;
 select * into r from public.hwarang_briefing_daily_budget where briefing_date=p_date for update;
 if p_kind='web' and r.web_requests<6 and r.search_actions<6 then
  update public.hwarang_briefing_daily_budget set web_requests=web_requests+1 where briefing_date=p_date;return true;
 elsif p_kind='analysis' and r.analysis_requests<4 then
  update public.hwarang_briefing_daily_budget set analysis_requests=analysis_requests+1 where briefing_date=p_date;return true;
 end if;
 return false;
end $$;
revoke all on function public.hwarang_verified_briefing_days(text),public.hwarang_set_briefing_policy(uuid,boolean,boolean,boolean),
 public.hwarang_read_public_briefing(text),public.hwarang_publish_briefing(uuid,uuid,uuid),public.hwarang_reserve_briefing_request(date,text) from public,anon,authenticated;
grant execute on function public.hwarang_verified_briefing_days(text),public.hwarang_set_briefing_policy(uuid,boolean,boolean,boolean),
 public.hwarang_read_public_briefing(text),public.hwarang_publish_briefing(uuid,uuid,uuid),public.hwarang_reserve_briefing_request(date,text) to service_role;
commit;
