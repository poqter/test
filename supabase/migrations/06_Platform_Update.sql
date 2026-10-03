-- =========================================================
-- HWARANG PLATFORM
-- PLATFORM OPTIMIZATION v1
--
-- 목적
-- 1. 로그인/관리 화면 운영 정보 보강
-- 2. 앱간 1회용 진입권 누적 방지
-- 3. 향후 ACADEMY 관리자 조회를 위한 서버측 권한 판정 준비
-- 4. 관리자용 profiles View 확장
--
-- 기존 01~05가 적용된 현재 프로젝트에서 1회 실행합니다.
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. 사용자 운영 메타데이터
-- ---------------------------------------------------------
alter table public.profiles
add column if not exists last_login_at timestamptz;


-- ---------------------------------------------------------
-- 2. 조직 열람 권한의 공통 판정 함수
--
-- RLS는 auth.uid()를 사용하는 private.can_view_user()를 계속 사용하고,
-- 서버(service_role)는 향후 ACADEMY 관리자 화면에서
-- public.can_hwarang_user_view(viewer, target)를 사용할 수 있습니다.
-- ---------------------------------------------------------
create or replace function private.can_user_view(
    p_viewer_user_id uuid,
    p_target_user_id uuid
)
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    v_viewer_role text;
    v_viewer_org uuid;
    v_viewer_position text;
    v_viewer_unit_type text;

    v_target_org uuid;
    v_target_position text;
begin
    if p_viewer_user_id is null or p_target_user_id is null then
        return false;
    end if;

    if p_viewer_user_id = p_target_user_id then
        return true;
    end if;

    select
        p.role,
        p.organization_unit_id,
        p.position_code,
        ou.unit_type
    into
        v_viewer_role,
        v_viewer_org,
        v_viewer_position,
        v_viewer_unit_type
    from public.profiles p
    left join public.organization_units ou
        on ou.id = p.organization_unit_id
    where p.id = p_viewer_user_id
      and p.is_active = true;

    if not found then
        return false;
    end if;

    -- HWARANG 최고관리자는 조직 배치와 무관하게 전체 조회
    if v_viewer_role = 'super_admin' then
        return true;
    end if;

    select
        p.organization_unit_id,
        p.position_code
    into
        v_target_org,
        v_target_position
    from public.profiles p
    where p.id = p_target_user_id
      and p.is_active = true;

    if not found or v_target_org is null then
        return false;
    end if;

    if v_viewer_position = 'fp' then
        return false;
    end if;

    if v_viewer_position = 'chief_representative' then
        return
            v_viewer_org is not null
            and v_viewer_unit_type = 'root'
            and private.is_org_descendant(v_viewer_org, v_target_org);
    end if;

    if v_viewer_position = 'division_head' then
        return
            v_viewer_org is not null
            and v_viewer_unit_type = 'head_unit'
            and private.is_org_descendant(v_viewer_org, v_target_org);
    end if;

    if v_viewer_position in ('branch_manager', 'deputy_branch_manager') then
        return
            v_viewer_org is not null
            and v_viewer_unit_type = 'branch'
            and private.is_org_descendant(v_viewer_org, v_target_org)
            and v_target_position in ('deputy_branch_manager', 'team_leader', 'fp');
    end if;

    if v_viewer_position = 'team_leader' then
        return
            v_viewer_org is not null
            and v_viewer_unit_type = 'team'
            and private.is_org_descendant(v_viewer_org, v_target_org)
            and v_target_position = 'fp';
    end if;

    return false;
end;
$$;

revoke all on function private.can_user_view(uuid, uuid) from public;


create or replace function private.can_view_user(
    p_target_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select private.can_user_view(
        auth.uid(),
        p_target_user_id
    );
$$;

revoke all on function private.can_view_user(uuid) from public;
grant execute on function private.can_view_user(uuid)
to authenticated, service_role;


create or replace function public.can_hwarang_user_view(
    p_viewer_user_id uuid,
    p_target_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select private.can_user_view(
        p_viewer_user_id,
        p_target_user_id
    );
$$;

revoke all on function public.can_hwarang_user_view(uuid, uuid)
from public, anon, authenticated;

grant execute on function public.can_hwarang_user_view(uuid, uuid)
to service_role;


-- ---------------------------------------------------------
-- 3. 앱간 1회용 진입권 정리
-- ---------------------------------------------------------
create index if not exists hwarang_launch_ticket_expiry_idx
on public.hwarang_app_launch_tickets(expires_at);

create index if not exists hwarang_launch_ticket_consumed_idx
on public.hwarang_app_launch_tickets(consumed_at)
where consumed_at is not null;


create or replace function private.prune_hwarang_launch_tickets()
returns void
language sql
volatile
security definer
set search_path = ''
as $$
    delete from public.hwarang_app_launch_tickets
    where
        expires_at < now() - interval '1 day'
        or consumed_at < now() - interval '1 day';
$$;

revoke all on function private.prune_hwarang_launch_tickets() from public;


create or replace function private.issue_launch_ticket_impl(
    p_user_id uuid,
    p_target_app text
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_ticket text;
begin
    if p_target_app not in ('academy', 'calculator', 'workspace') then
        raise exception 'INVALID_TARGET_APP';
    end if;

    if not exists (
        select 1
        from public.profiles p
        join public.hwarang_app_access a
          on a.user_id = p.id
         and a.app_code = p_target_app
         and a.is_enabled = true
        where p.id = p_user_id
          and p.is_active = true
    ) then
        raise exception 'APP_ACCESS_DENIED';
    end if;

    -- 별도 스케줄러 없이 발급 시점에 오래된 티켓을 가볍게 정리합니다.
    perform private.prune_hwarang_launch_tickets();

    v_ticket := encode(extensions.gen_random_bytes(32), 'hex');

    insert into public.hwarang_app_launch_tickets (
        user_id,
        target_app,
        token_hash,
        expires_at
    )
    values (
        p_user_id,
        p_target_app,
        private.hash_launch_ticket(v_ticket),
        now() + interval '60 seconds'
    );

    return v_ticket;
end;
$$;

revoke all on function private.issue_launch_ticket_impl(uuid, text) from public;
grant execute on function private.issue_launch_ticket_impl(uuid, text)
to service_role;


-- ---------------------------------------------------------
-- 4. 관리자용 사용자 View 확장
-- ---------------------------------------------------------
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

    coalesce(workspace_access.is_enabled, false) as workspace_access,
    coalesce(calculator_access.is_enabled, false) as calculator_access,
    coalesce(academy_access.is_enabled, false) as academy_access,

    p.last_login_at,

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
    on pos.code = p.position_code

left join public.hwarang_app_access workspace_access
    on workspace_access.user_id = p.id
   and workspace_access.app_code = 'workspace'

left join public.hwarang_app_access calculator_access
    on calculator_access.user_id = p.id
   and calculator_access.app_code = 'calculator'

left join public.hwarang_app_access academy_access
    on academy_access.user_id = p.id
   and academy_access.app_code = 'academy';

revoke all on table public.profiles_admin_view from anon, authenticated;
grant select on table public.profiles_admin_view to service_role;

commit;
