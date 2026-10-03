-- =========================================================
-- HWARANG PLATFORM
-- Data API Access
-- =========================================================

-- Schema 접근
grant usage on schema public
to anon, authenticated, service_role;

grant usage on schema private
to anon, authenticated, service_role;


-- HWARANG 공통 데이터
grant select, insert, update, delete
on table public.profiles
to service_role;

grant select, insert, update, delete
on table public.positions
to service_role;

grant select, insert, update, delete
on table public.organization_units
to service_role;

grant select, insert, update, delete
on table public.hwarang_join_codes
to service_role;

grant select, insert, update, delete
on table public.hwarang_app_access
to service_role;

grant select, insert, update, delete
on table public.hwarang_app_launch_tickets
to service_role;


-- 일반 로그인 사용자
grant select
on table public.positions
to authenticated;

grant select
on table public.organization_units
to authenticated;

grant select (
    id,
    login_id,
    display_name,
    role,
    is_active,
    organization_unit_id,
    position_code,
    created_at,
    updated_at
)
on table public.profiles
to authenticated;

grant select
on table public.hwarang_app_access
to authenticated;


-- 회원가입 관련 RPC
grant execute
on function public.validate_hwarang_join_code(text)
to anon, authenticated, service_role;

grant execute
on function public.get_joinable_branches(text)
to anon, authenticated, service_role;


-- 앱간 인증 RPC
grant execute
on function public.issue_hwarang_app_launch_ticket(uuid, text)
to service_role;

grant execute
on function public.consume_hwarang_app_launch_ticket(text, text)
to service_role;