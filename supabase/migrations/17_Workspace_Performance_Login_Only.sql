-- HWARANG corrective migration 17: WORKSPACE performance + login-only activity.
-- Apply once after Migration 16. Migration 16 remains unchanged.
begin;

create or replace function public.get_hwarang_workspace_context(p_user_id uuid)
returns table(
    user_id uuid, login_id text, display_name text, role text, is_active boolean,
    position_code text, position_name text, organization_unit_id uuid,
    organization_name text, organization_code text, app_access jsonb,
    feature_permissions text[]
)
language plpgsql stable security definer set search_path = '' as $$
declare v_profile record; v_app_access jsonb; v_permissions text[];
begin
    select p.id as user_id, p.login_id, p.display_name, p.role, p.is_active,
           p.position_code, pos.display_name as position_name, p.organization_unit_id,
           org.name as organization_name, org.code as organization_code
      into v_profile
      from public.profiles p
      left join public.positions pos on pos.code=p.position_code
      left join public.organization_units org on org.id=p.organization_unit_id
     where p.id=p_user_id limit 1;
    if not found then return; end if;
    select jsonb_build_object(
      'workspace',coalesce((select aa.is_enabled from public.hwarang_app_access aa where aa.user_id=p_user_id and aa.app_code='workspace' limit 1),false),
      'calculator',coalesce((select aa.is_enabled from public.hwarang_app_access aa where aa.user_id=p_user_id and aa.app_code='calculator' limit 1),false),
      'academy',coalesce((select aa.is_enabled from public.hwarang_app_access aa where aa.user_id=p_user_id and aa.app_code='academy' limit 1),false)
    ) into v_app_access;
    select coalesce(array_agg(ep.permission_code order by ep.permission_code),array[]::text[])
      into v_permissions from public.get_hwarang_effective_permissions(p_user_id) ep;
    user_id:=v_profile.user_id; login_id:=v_profile.login_id; display_name:=v_profile.display_name;
    role:=v_profile.role; is_active:=v_profile.is_active; position_code:=v_profile.position_code;
    position_name:=v_profile.position_name; organization_unit_id:=v_profile.organization_unit_id;
    organization_name:=v_profile.organization_name; organization_code:=v_profile.organization_code;
    app_access:=coalesce(v_app_access,'{}'::jsonb); feature_permissions:=coalesce(v_permissions,array[]::text[]);
    return next;
end; $$;
revoke all on function public.get_hwarang_workspace_context(uuid) from public,anon,authenticated;
grant execute on function public.get_hwarang_workspace_context(uuid) to service_role;

create or replace function public.complete_hwarang_workspace_login(p_user_id uuid)
returns table(
    platform_session_id uuid, user_id uuid, login_id text, display_name text, role text,
    is_active boolean, position_code text, position_name text, organization_unit_id uuid,
    organization_name text, organization_code text, app_access jsonb, feature_permissions text[]
)
language plpgsql security definer set search_path='' as $$
declare v_context record;
begin
    select * into v_context from public.get_hwarang_workspace_context(p_user_id) limit 1;
    if not found or not coalesce(v_context.is_active,false) then raise exception 'LOGIN_CONTEXT_NOT_FOUND'; end if;
    if not coalesce((v_context.app_access->>'workspace')::boolean,false) then raise exception 'WORKSPACE_ACCESS_REQUIRED'; end if;
    platform_session_id:=null; user_id:=v_context.user_id; login_id:=v_context.login_id;
    display_name:=v_context.display_name; role:=v_context.role; is_active:=v_context.is_active;
    position_code:=v_context.position_code; position_name:=v_context.position_name;
    organization_unit_id:=v_context.organization_unit_id; organization_name:=v_context.organization_name;
    organization_code:=v_context.organization_code; app_access:=coalesce(v_context.app_access,'{}'::jsonb);
    feature_permissions:=coalesce(v_context.feature_permissions,array[]::text[]);
    update public.profiles p set last_login_at=now() where p.id=p_user_id;
    insert into public.hwarang_activity_log(user_id,platform_session_id,app_code,event_code,feature_code,outcome,metadata)
    values(p_user_id,null,'workspace','LOGIN_SUCCESS',null,'success','{}'::jsonb);
    return next;
end; $$;
revoke all on function public.complete_hwarang_workspace_login(uuid) from public,anon,authenticated;
grant execute on function public.complete_hwarang_workspace_login(uuid) to service_role;
commit;
