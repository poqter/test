-- =========================================================
-- HWARANG PLATFORM
-- Admin Profile View
-- 관리자 확인용 사용자 목록
-- =========================================================

drop view if exists public.profiles_admin_view;

create view public.profiles_admin_view
with (security_invoker = true)
as
select
    p.login_id,
    p.display_name,

    parent_ou.name as parent_organization_name,
    ou.name as organization_name,
    pos.display_name as position_name,

    case p.role
        when 'super_admin' then '최고관리자'
        when 'admin' then '관리자'
        when 'user' then '일반 사용자'
        else p.role
    end as system_role_name,

    p.is_active,

    p.role as system_role_code,
    p.position_code,
    p.organization_unit_id,
    p.id as user_id,

    p.created_at,
    p.updated_at

from public.profiles p

left join public.organization_units ou
    on ou.id = p.organization_unit_id

left join public.organization_units parent_ou
    on parent_ou.id = ou.parent_id

left join public.positions pos
    on pos.code = p.position_code;