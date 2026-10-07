-- Read-only verification for Migration 17.
select p.proname, pg_get_function_arguments(p.oid) args
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname in ('get_hwarang_workspace_context','complete_hwarang_workspace_login')
order by p.proname;
select source_app,status,count(*) session_rows from public.hwarang_user_sessions group by source_app,status order by source_app,status;
select user_id,app_code,event_code,created_at from public.hwarang_activity_log where event_code='LOGIN_SUCCESS' order by created_at desc limit 20;
