-- Requires existing briefing migrations 20-22 and the catch_up workflow patch.
-- Install as postgres in Supabase SQL Editor. Activation is a separate step.
begin;
create extension if not exists pg_cron;
create extension if not exists pg_net;
create extension if not exists supabase_vault;

create table if not exists public.hwarang_briefing_watchdog_config (
 id integer primary key check (id=1),
 enabled boolean not null default false,
 repository text not null default 'poqter/test'
   check (repository ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'),
 branch text not null default 'main',
 workflow text not null default 'hwarang_daily_briefing.yml'
   check (workflow ~ '^[A-Za-z0-9_.-]+\.ya?ml$'),
 last_requested_at timestamptz
);
insert into public.hwarang_briefing_watchdog_config(id) values(1) on conflict do nothing;

create table if not exists public.hwarang_briefing_watchdog_log (
 id bigint generated always as identity primary key,
 checked_at timestamptz not null default now(),
 briefing_date date not null,
 outcome text not null,
 missing_profiles text[] not null default '{}',
 request_id bigint,
 action text
);
alter table public.hwarang_briefing_watchdog_config enable row level security;
alter table public.hwarang_briefing_watchdog_log enable row level security;
revoke all on public.hwarang_briefing_watchdog_config,
 public.hwarang_briefing_watchdog_log from public, anon, authenticated, service_role;

create or replace function public.hwarang_briefing_watchdog_tick(p_probe boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$
declare
 cfg public.hwarang_briefing_watchdog_config;
 local_now timestamp := pg_catalog.timezone('Asia/Seoul',now());
 today date := local_now::date;
 missing text[] := '{}';
 result text;
 token text;
 request bigint;
 operation text := case when p_probe then 'check' else 'catch_up' end;
begin
 -- Serialize overlapping ticks, including manual setup probes.
 select * into cfg from public.hwarang_briefing_watchdog_config where id=1 for update;
 if not found then return jsonb_build_object('status','not_configured'); end if;
 delete from public.hwarang_briefing_watchdog_log where checked_at < now()-interval '14 days';
 if not cfg.enabled and not p_probe then
   return jsonb_build_object('status','disabled');
 end if;
 if not p_probe and (local_now::time < time '07:00' or local_now::time >= time '09:00') then
   return jsonb_build_object('status','outside_window');
 end if;

 select coalesce(array_agg(p.profile_code order by p.profile_code),'{}'::text[])
 into missing from public.hwarang_briefing_profiles p
 where p.is_enabled and p.profile_code in ('MARKET','NEWS','INSURANCE')
 and not exists (
   select 1 from public.hwarang_briefings b
   join public.hwarang_briefing_revisions r on r.id=b.current_published_revision_id
     and r.briefing_id=b.id
   where b.profile_code=p.profile_code and b.briefing_date=today
     and r.publication_status='published'
 );

 if not p_probe and cardinality(missing)=0 then result:='all_published';
 elsif not p_probe and not exists (
   select 1 from public.hwarang_briefing_operating_policy
   where policy_key='WORKSPACE'
     and (scheduled_generation_enabled or automatic_publication_enabled)
 ) then result:='policy_paused';
 elsif not p_probe and exists (
   select 1 from public.hwarang_briefing_daily_runs
   where briefing_date=today and status='running' and lease_until>now()
 ) then result:='generation_running';
 elsif cfg.last_requested_at>now()-interval '9 minutes' then result:='request_cooldown';
 elsif not p_probe and (
   select count(*) from public.hwarang_briefing_watchdog_log
   where briefing_date=today and request_id is not null and action='catch_up'
 )>=12 then result:='daily_dispatch_limit';
 else
   select decrypted_secret into token from vault.decrypted_secrets
   where name='hwarang_briefing_github_token' limit 1;
   if token is null or length(token)<10 then result:='github_token_missing';
   else
     -- pg_net sends after commit. A request ID is NOT confirmation of success.
     select net.http_post(
       url:='https://api.github.com/repos/'||cfg.repository||'/actions/workflows/'||cfg.workflow||'/dispatches',
       headers:=jsonb_build_object('Accept','application/vnd.github+json',
         'Authorization','Bearer '||token,'X-GitHub-Api-Version','2022-11-28',
         'User-Agent','hwarang-briefing-watchdog','Content-Type','application/json'),
       body:=jsonb_build_object('ref',cfg.branch,'inputs',jsonb_build_object('action',operation)),
       timeout_milliseconds:=10000
     ) into request;
     update public.hwarang_briefing_watchdog_config set last_requested_at=now() where id=1;
     result:='dispatch_requested';
   end if;
 end if;
 insert into public.hwarang_briefing_watchdog_log(briefing_date,outcome,missing_profiles,request_id,action)
 values(today,result,missing,request,operation);
 return jsonb_build_object('status',result,'date',today,'missing_profiles',missing,
   'request_id',request,'action',operation);
end $$;
revoke all on function public.hwarang_briefing_watchdog_tick(boolean)
 from public,anon,authenticated,service_role;

-- Keep HTTP status codes beyond pg_net's short response retention period.
alter table public.hwarang_briefing_watchdog_log add column if not exists http_status integer;
alter table public.hwarang_briefing_watchdog_log add column if not exists http_checked_at timestamptz;
alter table public.hwarang_briefing_watchdog_log add column if not exists transport_failed boolean;
create or replace function public.hwarang_briefing_watchdog_collect()
returns void language plpgsql security definer set search_path='' as $$
begin
 update public.hwarang_briefing_watchdog_log l
 set http_status=r.status_code,http_checked_at=now(),
     transport_failed=coalesce(r.timed_out,false) or r.error_msg is not null
 from net._http_response r
 where l.request_id=r.id and l.http_checked_at is null;
end $$;
revoke all on function public.hwarang_briefing_watchdog_collect()
 from public,anon,authenticated,service_role;

-- pg_cron uses UTC: 22:02-23:52 UTC = 07:02-08:52 KST (12 checks/day).
-- Named schedules are updated on reinstallation, not duplicated.
select cron.schedule('hwarang-briefing-watchdog','2,12,22,32,42,52 22,23 * * *',
 'select public.hwarang_briefing_watchdog_collect(); select public.hwarang_briefing_watchdog_tick();');
-- Collect final 08:52 response; no GitHub dispatch / AI call here.
select cron.schedule('hwarang-briefing-watchdog-final-receipt','55 23 * * *',
 'select public.hwarang_briefing_watchdog_collect();');
commit;
