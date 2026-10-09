-- Additive upgrade after migrations 18 and 19. Does not delete existing news.
begin;
create table if not exists public.hwarang_briefing_daily_runs (
 run_key text primary key, briefing_date date not null, group_code text not null,
 owner_token uuid, attempts integer not null default 0 check(attempts between 0 and 2),
 status text not null default 'waiting' check(status in ('waiting','running','failed','blocked','completed')),
 lease_until timestamptz, checkpoint jsonb not null default '{}'::jsonb,
 updated_at timestamptz not null default now()
);
create table if not exists public.hwarang_briefing_daily_budget (
 briefing_date date primary key, web_requests integer not null default 0,
 search_actions integer not null default 0,
 analysis_requests integer not null default 0
);
create table if not exists public.hwarang_briefing_public_shares (
 token text primary key check(length(token)>=32), revision_id uuid not null references public.hwarang_briefing_revisions(id),
 sender_user_id uuid not null references public.profiles(id), public_packet jsonb not null,
 created_at timestamptz not null default now(), revoked_at timestamptz,
 expires_at timestamptz not null default now()+interval '30 days'
);
alter table public.hwarang_briefing_daily_runs enable row level security;
alter table public.hwarang_briefing_daily_budget enable row level security;
alter table public.hwarang_briefing_public_shares enable row level security;
revoke all on public.hwarang_briefing_daily_runs,public.hwarang_briefing_daily_budget,public.hwarang_briefing_public_shares from anon,authenticated;
grant select,insert,update on public.hwarang_briefing_daily_runs,public.hwarang_briefing_daily_budget,public.hwarang_briefing_public_shares to service_role;
create or replace function public.hwarang_claim_briefing_run(p_key text,p_date date,p_group text,p_owner uuid,p_retry boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_daily_runs;
begin
 insert into public.hwarang_briefing_daily_runs(run_key,briefing_date,group_code) values(p_key,p_date,p_group) on conflict do nothing;
 select * into r from public.hwarang_briefing_daily_runs where run_key=p_key for update;
 if r.status in ('completed','blocked') or (r.status='running' and r.lease_until>now())
   or r.attempts>=2 or (r.attempts>0 and not p_retry) then
   return jsonb_build_object('claimed',false,'status',r.status,'checkpoint',r.checkpoint);
 end if;
 update public.hwarang_briefing_daily_runs set owner_token=p_owner,attempts=attempts+1,status='running',lease_until=now()+interval '20 minutes',updated_at=now() where run_key=p_key returning * into r;
 return jsonb_build_object('claimed',true,'checkpoint',r.checkpoint,'attempts',r.attempts);
end $$;
create or replace function public.hwarang_checkpoint_briefing_run(p_key text,p_owner uuid,p_checkpoint jsonb,p_status text default 'running')
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if p_status not in ('running','failed','blocked','completed') then raise exception 'Invalid run status'; end if;
 update public.hwarang_briefing_daily_runs set checkpoint=p_checkpoint,status=p_status,
 lease_until=now()+interval '20 minutes',updated_at=now() where run_key=p_key and owner_token=p_owner and status='running' and lease_until>now();
 return found;
end $$;
create or replace function public.hwarang_reserve_briefing_request(p_date date,p_kind text)
returns boolean language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_daily_budget;
begin
 insert into public.hwarang_briefing_daily_budget(briefing_date) values(p_date) on conflict do nothing;
 select * into r from public.hwarang_briefing_daily_budget where briefing_date=p_date for update;
 if p_kind='web' and r.web_requests<6 and r.search_actions<6 then
  update public.hwarang_briefing_daily_budget set web_requests=web_requests+1 where briefing_date=p_date; return true;
 elsif p_kind='analysis' and r.analysis_requests<4 then
  update public.hwarang_briefing_daily_budget set analysis_requests=analysis_requests+1 where briefing_date=p_date; return true;
 end if;
 return false;
end $$;
create or replace function public.hwarang_observe_briefing_search(p_date date,p_actions integer)
returns void language plpgsql security definer set search_path='' as $$
begin
 if p_actions<0 then raise exception 'Invalid search count'; end if;
 update public.hwarang_briefing_daily_budget set search_actions=search_actions+p_actions where briefing_date=p_date;
end $$;
revoke all on function public.hwarang_observe_briefing_search(date,integer) from public,anon,authenticated;
grant execute on function public.hwarang_observe_briefing_search(date,integer) to service_role;
create or replace function public.hwarang_publish_briefing(p_briefing uuid,p_revision uuid,p_actor uuid default null)
returns boolean language plpgsql security definer set search_path='' as $$
declare r public.hwarang_briefing_revisions; s public.hwarang_briefing_snapshots;
begin
 select * into r from public.hwarang_briefing_revisions where id=p_revision and briefing_id=p_briefing for update;
 if not found or r.validation_status<>'ok' or r.coverage_status<>'healthy' or r.publication_status='hidden' then raise exception 'Briefing validation incomplete'; end if;
 select * into s from public.hwarang_briefing_snapshots where revision_id=r.id;
 if not found or coalesce(s.qa_payload->>'public_body_ready','')<>'true' or coalesce(s.external_content_payload->>'schema','')<>'hwarang-public-v2' then raise exception 'Public body validation incomplete'; end if;
 if coalesce(jsonb_typeof(s.external_content_payload->'issues'),'null')<>'array' then raise exception 'Public issues missing'; end if;
 if jsonb_array_length(s.external_content_payload->'issues')=0 then raise exception 'Public issues empty'; end if;
 if s.external_content_payload->>'profile_code'='MARKET' then
  if coalesce(jsonb_typeof(s.external_content_payload->'market_metrics'),'null')<>'array' then raise exception 'Market observations missing'; end if;
  if jsonb_array_length(s.external_content_payload->'market_metrics')<>6 then raise exception 'Market observations incomplete'; end if;
 end if;
 update public.hwarang_briefing_revisions set publication_status='published',published_at=now(),external_qa_passed=true,external_share_allowed=true,approved_by=p_actor where id=r.id;
 update public.hwarang_briefings set current_published_revision_id=r.id where id=p_briefing;
 insert into public.hwarang_briefing_audit_log(actor_type,actor_user_id,action,briefing_id,revision_id,details) values(case when p_actor is null then 'system' else 'user' end,p_actor,'BRIEFING_PUBLISHED',p_briefing,r.id,'{}');
 return true;
end $$;
revoke all on function public.hwarang_claim_briefing_run(text,date,text,uuid,boolean),public.hwarang_checkpoint_briefing_run(text,uuid,jsonb,text),public.hwarang_reserve_briefing_request(date,text),public.hwarang_publish_briefing(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.hwarang_claim_briefing_run(text,date,text,uuid,boolean),public.hwarang_checkpoint_briefing_run(text,uuid,jsonb,text),public.hwarang_reserve_briefing_request(date,text),public.hwarang_publish_briefing(uuid,uuid,uuid) to service_role;
commit;
