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
