-- HWARANG BRIEFING Migration 16 post-apply verification
-- Read-only. Run immediately after Migration 16 in TEST Supabase.

-- 1) Expected 16 briefing tables
with expected(name) as (
  values
  ('hwarang_briefing_profiles'),
  ('hwarang_briefings'),
  ('hwarang_briefing_revisions'),
  ('hwarang_briefing_snapshots'),
  ('hwarang_briefing_events'),
  ('hwarang_briefing_event_updates'),
  ('hwarang_briefing_issues'),
  ('hwarang_briefing_actions'),
  ('hwarang_briefing_sources'),
  ('hwarang_briefing_issue_sources'),
  ('hwarang_briefing_event_update_sources'),
  ('hwarang_briefing_issue_locks'),
  ('hwarang_briefing_jobs'),
  ('hwarang_briefing_checkpoints'),
  ('hwarang_briefing_api_usage'),
  ('hwarang_briefing_audit_log')
)
select e.name,
       to_regclass('public.' || e.name) is not null as exists
from expected e
order by e.name;

-- 2) Seed profiles must be shadow by default
select profile_code, display_name, is_enabled, run_mode, timezone,
       publish_time_kst, collect_cutoff_time_kst, external_share_default
from public.hwarang_briefing_profiles
order by profile_code;

-- Expected: INSURANCE / MARKET / NEWS, all is_enabled=true, run_mode=shadow,
-- external_share_default=false.

-- 3) Permissions
select permission_code, app_code, group_label, display_name,
       default_granted, is_active
from public.hwarang_permissions
where permission_code in ('workspace.briefing','workspace.briefing_manage')
order by permission_code;

-- Expected:
-- workspace.briefing        default_granted=true
-- workspace.briefing_manage default_granted=false

-- 4) RLS must be enabled on all briefing tables
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname='public'
  and c.relkind='r'
  and c.relname like 'hwarang_briefing%'
order by c.relname;

-- Expected: every rls_enabled=true.

-- 5) anon/authenticated must have no table grants
select grantee, table_name, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and table_name like 'hwarang_briefing%'
  and grantee in ('anon','authenticated')
order by grantee, table_name, privilege_type;

-- Expected: zero rows.

-- 6) Service-role grants summary
select table_name, string_agg(privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema='public'
  and table_name like 'hwarang_briefing%'
  and grantee='service_role'
group by table_name
order by table_name;

-- 7) Immutable protection trigger check
select event_object_table as table_name, trigger_name, action_timing, event_manipulation
from information_schema.triggers
where trigger_schema='public'
  and trigger_name like 'hwarang_briefing%immutable%'
order by table_name, trigger_name, event_manipulation;

-- 8) No operational data should exist immediately after migration
select
  (select count(*) from public.hwarang_briefings) as briefings,
  (select count(*) from public.hwarang_briefing_revisions) as revisions,
  (select count(*) from public.hwarang_briefing_snapshots) as snapshots,
  (select count(*) from public.hwarang_briefing_events) as events,
  (select count(*) from public.hwarang_briefing_jobs) as jobs;

-- Expected: all 0.

-- 9) Shared INSURANCE + NEWS discovery budget must match V1.6.0 SPEC
select
  profile_code,
  settings -> 'shared_discovery_pool' ->> 'pool_code' as pool_code,
  (settings -> 'shared_discovery_pool' ->> 'target')::int as target_actions,
  (settings -> 'shared_discovery_pool' ->> 'soft')::int as soft_limit,
  (settings -> 'shared_discovery_pool' ->> 'hard')::int as hard_limit
from public.hwarang_briefing_profiles
where profile_code in ('INSURANCE', 'NEWS')
order by profile_code;

-- Expected for both INSURANCE and NEWS:
-- pool_code=INSURANCE_NEWS, target_actions=4, soft_limit=5, hard_limit=6.

-- 10) One-shot configuration gate
select
  count(*) = 3 as profile_count_ok,
  bool_and(run_mode = 'shadow') as all_shadow_ok,
  bool_and(external_share_default = false) as external_share_default_ok,
  bool_and(
    case profile_code
      when 'MARKET' then publish_time_kst = time '07:30'
      when 'INSURANCE' then publish_time_kst = time '08:00'
      when 'NEWS' then publish_time_kst = time '08:00'
      else false
    end
  ) as publish_times_ok,
  bool_and(
    case
      when profile_code in ('INSURANCE','NEWS') then
        settings -> 'shared_discovery_pool' ->> 'pool_code' = 'INSURANCE_NEWS'
        and (settings -> 'shared_discovery_pool' ->> 'target')::int = 4
        and (settings -> 'shared_discovery_pool' ->> 'soft')::int = 5
        and (settings -> 'shared_discovery_pool' ->> 'hard')::int = 6
      else true
    end
  ) as shared_budget_ok
from public.hwarang_briefing_profiles;

-- Expected: all columns = true.

