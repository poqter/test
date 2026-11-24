CREATE OR REPLACE FUNCTION public.hwarang_briefing_watchdog_tick(p_probe boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
 if not p_probe and (local_now::time < time '06:30' or local_now::time >= time '09:00') then
   return jsonb_build_object('status','outside_window');
 end if;

 -- Before 08:00 a missing publication is expected. Dispatch only if the
 -- collection due now, or preparation of an enabled edition, is incomplete.
 if not p_probe and local_now::time < time '08:00' then
   if local_now::time < time '07:30' then
     if exists (
       select 1 from public.hwarang_briefing_daily_runs
       where run_key = today::text || case when local_now::time < time '07:20'
         then ':COLLECT_630' else ':COLLECT_720' end and status = 'completed'
     ) then result := 'collection_complete'; end if;
   elsif exists (select 1 from public.hwarang_briefing_profiles
                 where is_enabled and profile_code in ('MARKET','NEWS','INSURANCE'))
     and not exists (
       select 1 from public.hwarang_briefing_profiles p
       where p.is_enabled and p.profile_code in ('MARKET','NEWS','INSURANCE')
       and not exists (
         select 1 from public.hwarang_briefings b
         cross join lateral (
           select r.id from public.hwarang_briefing_revisions r
           where r.briefing_id = b.id order by r.revision_no desc limit 1
         ) latest
         join public.hwarang_briefing_snapshots s on s.revision_id = latest.id
         where b.profile_code = p.profile_code and b.briefing_date = today
       )
     ) then result := 'editions_prepared';
   end if;
   if result is not null then
     insert into public.hwarang_briefing_watchdog_log(briefing_date,outcome,missing_profiles,action)
     values(today,result,missing,operation);
     return jsonb_build_object('status',result,'date',today,'action',operation);
   end if;
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
 )>=15 then result:='daily_dispatch_limit';
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
end $function$;
