-- =========================================================
-- HWARANG PLATFORM
-- 12 LOGIN FAST PATH v1
--
-- Apply ONCE after 11_API_Preflight_Fixes.sql.
-- Normal WORKSPACE sign-in becomes three sequential requests:
--   1) lightweight login bootstrap RPC
--   2) Supabase Auth password verification
--   3) complete-login RPC (profile/authz/session/logging together)
-- =========================================================

begin;

-- 1. Minimal pre-auth bootstrap. Service-role only.
-- 01_Core_Setup already provides profiles_login_id_unique_ci on lower(login_id),
-- so no redundant index is added here.
create or replace function public.get_hwarang_login_bootstrap(
    p_login_id text
)
returns table(
    user_id uuid,
    auth_email text,
    is_active boolean
)
language sql
stable
security definer
set search_path = ''
as $$
    select
        p.id,
        p.auth_email,
        p.is_active
    from public.profiles p
    where lower(p.login_id) = lower(btrim(p_login_id))
    order by p.created_at asc
    limit 1;
$$;

revoke all on function public.get_hwarang_login_bootstrap(text)
from public, anon, authenticated;

grant execute on function public.get_hwarang_login_bootstrap(text)
to service_role;

-- 2. Post-password completion.
-- Position, organization, app access, feature permissions, session creation,
-- last_login_at and LOGIN_SUCCESS are all handled in this single RPC.
create or replace function public.complete_hwarang_workspace_login(
    p_user_id uuid
)
returns table(
    platform_session_id uuid,
    user_id uuid,
    login_id text,
    display_name text,
    role text,
    is_active boolean,
    position_code text,
    position_name text,
    organization_unit_id uuid,
    organization_name text,
    organization_code text,
    app_access jsonb,
    feature_permissions text[]
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_profile record;
    v_app_access jsonb;
    v_permissions text[];
begin
    select
        p.id as user_id,
        p.login_id,
        p.display_name,
        p.role,
        p.is_active,
        p.position_code,
        pos.display_name as position_name,
        p.organization_unit_id,
        org.name as organization_name,
        org.code as organization_code
    into v_profile
    from public.profiles p
    left join public.positions pos
      on pos.code = p.position_code
    left join public.organization_units org
      on org.id = p.organization_unit_id
    where p.id = p_user_id
      and p.is_active = true
    limit 1;

    if not found then
        raise exception 'LOGIN_CONTEXT_NOT_FOUND';
    end if;

    if not exists (
        select 1
        from public.hwarang_app_access aa
        where aa.user_id = p_user_id
          and aa.app_code = 'workspace'
          and aa.is_enabled = true
    ) then
        raise exception 'WORKSPACE_ACCESS_REQUIRED';
    end if;

    select jsonb_build_object(
        'workspace',
        coalesce((
            select aa.is_enabled
            from public.hwarang_app_access aa
            where aa.user_id = p_user_id
              and aa.app_code = 'workspace'
            limit 1
        ), false),
        'calculator',
        coalesce((
            select aa.is_enabled
            from public.hwarang_app_access aa
            where aa.user_id = p_user_id
              and aa.app_code = 'calculator'
            limit 1
        ), false),
        'academy',
        coalesce((
            select aa.is_enabled
            from public.hwarang_app_access aa
            where aa.user_id = p_user_id
              and aa.app_code = 'academy'
            limit 1
        ), false)
    )
    into v_app_access;

    select coalesce(
        array_agg(ep.permission_code order by ep.permission_code),
        array[]::text[]
    )
    into v_permissions
    from public.get_hwarang_effective_permissions(p_user_id) ep;

    insert into public.hwarang_user_sessions(
        user_id,
        source_app,
        status,
        login_at,
        last_seen_at
    )
    values (
        p_user_id,
        'workspace',
        'active',
        now(),
        now()
    )
    returning id into platform_session_id;

    update public.profiles p
    set last_login_at = now()
    where p.id = p_user_id;

    insert into public.hwarang_activity_log(
        user_id,
        platform_session_id,
        app_code,
        event_code,
        feature_code,
        outcome,
        metadata
    )
    values (
        p_user_id,
        platform_session_id,
        'workspace',
        'LOGIN_SUCCESS',
        'home',
        'success',
        jsonb_build_object('login_path','fast_v1')
    );

    user_id := v_profile.user_id;
    login_id := v_profile.login_id;
    display_name := v_profile.display_name;
    role := v_profile.role;
    is_active := v_profile.is_active;
    position_code := v_profile.position_code;
    position_name := v_profile.position_name;
    organization_unit_id := v_profile.organization_unit_id;
    organization_name := v_profile.organization_name;
    organization_code := v_profile.organization_code;
    app_access := coalesce(v_app_access, '{}'::jsonb);
    feature_permissions := coalesce(v_permissions, array[]::text[]);

    return next;
end;
$$;

revoke all on function public.complete_hwarang_workspace_login(uuid)
from public, anon, authenticated;

grant execute on function public.complete_hwarang_workspace_login(uuid)
to service_role;

commit;
