-- HWARANG BRIEFING Migration 16 preflight
-- Read-only. Run in TEST Supabase SQL Editor before Migration 16.

select
  to_regclass('public.profiles') as profiles_table,
  to_regclass('public.hwarang_permissions') as permissions_table,
  to_regprocedure('private.set_updated_at()') as set_updated_at_function,
  to_regclass('public.hwarang_briefing_profiles') as briefing_profiles_existing,
  to_regclass('public.hwarang_briefings') as briefings_existing,
  to_regclass('public.hwarang_briefing_snapshots') as snapshots_existing;

-- Expected:
-- profiles_table              = public.profiles
-- permissions_table           = public.hwarang_permissions
-- set_updated_at_function     = private.set_updated_at()
-- briefing_profiles_existing  = null
-- briefings_existing          = null
-- snapshots_existing          = null

select column_name, data_type, is_nullable
from information_schema.columns
where table_schema='public'
  and table_name='hwarang_permissions'
  and column_name in (
    'permission_code','app_code','group_label','display_name','description',
    'sort_order','default_granted','is_active','updated_at'
  )
order by ordinal_position;

-- Expected: all columns referenced by Migration 16 are present.

-- 3) Migration 16 must be completely unapplied: all 16 target tables must be absent
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
       to_regclass('public.' || e.name) as existing_table
from expected e
where to_regclass('public.' || e.name) is not null
order by e.name;

-- Expected: zero rows.

-- 4) Migration 16 uses ON CONFLICT(permission_code).
--    hwarang_permissions.permission_code therefore needs a UNIQUE/PK constraint or unique index.
select
  i.relname as unique_index_name,
  pg_get_indexdef(ix.indexrelid) as index_definition
from pg_class t
join pg_namespace n on n.oid = t.relnamespace
join pg_index ix on ix.indrelid = t.oid
join pg_class i on i.oid = ix.indexrelid
where n.nspname = 'public'
  and t.relname = 'hwarang_permissions'
  and ix.indisunique
  and pg_get_indexdef(ix.indexrelid) ilike '%(permission_code)%';

-- Expected: at least one row.

