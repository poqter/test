-- =========================================================
-- HWARANG PLATFORM
-- CORE SCHEMA v1
--
-- Fresh project only.
-- HWARANG 공통 계정 / 조직 / 직책 / 가입 / 앱 권한 / 앱간 1회용 진입권
--
-- 적용 전제:
-- - 새 Supabase 프로젝트
-- - Data API ON
-- - Automatically expose new tables OFF 권장
-- - Automatic RLS ON/OFF와 무관하게 이 SQL에서 명시적으로 RLS 설정
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 0. Extensions / private schema
-- ---------------------------------------------------------
create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;

revoke all on schema private from public;
grant usage on schema private to anon, authenticated, service_role;


-- ---------------------------------------------------------
-- 1. 공통 updated_at 함수
-- ---------------------------------------------------------
create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

revoke all on function private.set_updated_at() from public;


-- ---------------------------------------------------------
-- 2. 직책 마스터
-- ---------------------------------------------------------
create table public.positions (
    code text primary key,
    display_name text not null unique,
    rank_order integer not null unique,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

insert into public.positions (code, display_name, rank_order)
values
    ('chief_representative', '총괄대표', 600),
    ('division_head', '본부장', 500),
    ('branch_manager', '지점장', 400),
    ('deputy_branch_manager', '부지점장', 300),
    ('team_leader', '팀장', 200),
    ('fp', 'FP', 100);


-- ---------------------------------------------------------
-- 3. 조직 트리
-- root / head_unit / branch / team
-- ---------------------------------------------------------
create table public.organization_units (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    unit_type text not null
        check (unit_type in ('root', 'head_unit', 'branch', 'team')),
    parent_id uuid references public.organization_units(id) on delete restrict,
    sort_order integer not null default 0,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint organization_units_no_self_parent
        check (parent_id is null or parent_id <> id)
);

create index organization_units_parent_idx
    on public.organization_units(parent_id);

create trigger organization_units_set_updated_at
before update on public.organization_units
for each row execute function private.set_updated_at();


-- root
insert into public.organization_units
    (code, name, unit_type, parent_id, sort_order)
values
    ('HWARANG', '화랑', 'root', null, 0);

-- head units
insert into public.organization_units
    (code, name, unit_type, parent_id, sort_order)
values
    ('HWARANG_DIRECT', '화랑직할', 'head_unit',
        (select id from public.organization_units where code='HWARANG'), 10),
    ('DONGVAN_HQ', '동반본부', 'head_unit',
        (select id from public.organization_units where code='HWARANG'), 20),
    ('VISION_HQ', '비전본부', 'head_unit',
        (select id from public.organization_units where code='HWARANG'), 30),
    ('BISANG_HQ', '비상본부', 'head_unit',
        (select id from public.organization_units where code='HWARANG'), 40);

-- branches
insert into public.organization_units
    (code, name, unit_type, parent_id, sort_order)
values
    ('JISA_DIRECT', '지사직할', 'branch',
        (select id from public.organization_units where code='HWARANG_DIRECT'), 10),
    ('DONGHAENG_BRANCH', '동행지점', 'branch',
        (select id from public.organization_units where code='HWARANG_DIRECT'), 20),

    ('DONGVAN_DIRECT', '동반직할', 'branch',
        (select id from public.organization_units where code='DONGVAN_HQ'), 10),
    ('DONGGYEONG_BRANCH', '동경지점', 'branch',
        (select id from public.organization_units where code='DONGVAN_HQ'), 20),
    ('SEONGJANG_BRANCH', '성장지점', 'branch',
        (select id from public.organization_units where code='DONGVAN_HQ'), 30),

    ('VISION_DIRECT', '비전직할', 'branch',
        (select id from public.organization_units where code='VISION_HQ'), 10),
    ('STAR_BRANCH', '스타지점', 'branch',
        (select id from public.organization_units where code='VISION_HQ'), 20),
    ('DREAM_BRANCH', '드림지점', 'branch',
        (select id from public.organization_units where code='VISION_HQ'), 30),

    ('BISANG_DIRECT', '비상직할', 'branch',
        (select id from public.organization_units where code='BISANG_HQ'), 10),
    ('PERSONAL_BRANCH', '퍼스널지점', 'branch',
        (select id from public.organization_units where code='BISANG_HQ'), 20),
    ('VIP_BRANCH', 'VIP지점', 'branch',
        (select id from public.organization_units where code='BISANG_HQ'), 30);


-- ---------------------------------------------------------
-- 4. HWARANG 사용자 프로필
-- auth.users 1:1 연결
-- ---------------------------------------------------------
create table public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,

    -- 사용자가 로그인 화면에서 입력하는 HWARANG ID
    login_id text,

    -- Auth 이메일 복사본. 일반 사용자는 조회 불가, 서버 로그인 변환용
    auth_email text,

    display_name text,

    -- 시스템 권한. 조직 직책과 별도
    role text not null default 'user'
        check (role in ('user', 'admin', 'super_admin')),

    is_active boolean not null default false,

    organization_unit_id uuid
        references public.organization_units(id) on delete restrict,

    position_code text not null default 'fp'
        references public.positions(code) on delete restrict,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint profiles_login_id_format
        check (
            login_id is null
            or (
                char_length(login_id) between 3 and 32
                and login_id ~ '^[A-Za-z0-9._-]+$'
            )
        ),

    constraint profiles_display_name_length
        check (
            display_name is null
            or char_length(display_name) between 1 and 60
        )
);

create unique index profiles_login_id_unique_ci
    on public.profiles(lower(login_id))
    where login_id is not null;

create unique index profiles_auth_email_unique_ci
    on public.profiles(lower(auth_email))
    where auth_email is not null;

create index profiles_organization_unit_idx
    on public.profiles(organization_unit_id);

create index profiles_position_code_idx
    on public.profiles(position_code);

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function private.set_updated_at();


-- ---------------------------------------------------------
-- 5. 조직 하위 여부
-- ---------------------------------------------------------
create or replace function private.is_org_descendant(
    p_ancestor uuid,
    p_descendant uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    with recursive org_tree as (
        select id
        from public.organization_units
        where id = p_ancestor and is_active = true

        union all

        select child.id
        from public.organization_units child
        join org_tree parent
          on child.parent_id = parent.id
        where child.is_active = true
    )
    select exists (
        select 1 from org_tree where id = p_descendant
    );
$$;

revoke all on function private.is_org_descendant(uuid, uuid) from public;
grant execute on function private.is_org_descendant(uuid, uuid)
    to authenticated, service_role;


-- ---------------------------------------------------------
-- 6. super_admin 여부
-- ---------------------------------------------------------
create or replace function private.is_super_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles
        where id = (select auth.uid())
          and role = 'super_admin'
          and is_active = true
    );
$$;

revoke all on function private.is_super_admin() from public;
grant execute on function private.is_super_admin()
    to authenticated, service_role;


-- ---------------------------------------------------------
-- 7. 조직 산하 사용자 열람 범위
--
-- 본인: 항상
-- super_admin: 전체
-- 총괄대표: root 산하
-- 본부장: head_unit 산하
-- 지점장/부지점장: branch 산하
-- 팀장: team 산하 FP만
-- FP: 본인만
-- ---------------------------------------------------------
create or replace function private.can_view_user(
    p_target_user_id uuid
)
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    v_viewer_id uuid;
    v_viewer_role text;
    v_viewer_org uuid;
    v_viewer_position text;
    v_viewer_unit_type text;

    v_target_org uuid;
    v_target_position text;
begin
    v_viewer_id := auth.uid();

    if v_viewer_id is null then
        return false;
    end if;

    if v_viewer_id = p_target_user_id then
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
    where p.id = v_viewer_id
      and p.is_active = true;

    if not found then
        return false;
    end if;

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

revoke all on function private.can_view_user(uuid) from public;
grant execute on function private.can_view_user(uuid)
    to authenticated, service_role;


-- ---------------------------------------------------------
-- 8. HWARANG 가입코드
-- ---------------------------------------------------------
create table public.hwarang_join_codes (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    code_hash text not null unique,

    -- null이면 모든 branch 선택 가능
    scope_organization_unit_id uuid
        references public.organization_units(id) on delete restrict,

    allow_descendants boolean not null default true,

    is_active boolean not null default true,
    starts_at timestamptz not null default now(),
    expires_at timestamptz,

    max_uses integer,
    used_count integer not null default 0,

    created_by uuid references public.profiles(id) on delete set null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint hwarang_join_codes_max_uses_check
        check (max_uses is null or max_uses > 0),

    constraint hwarang_join_codes_used_count_check
        check (used_count >= 0),

    constraint hwarang_join_codes_expiry_check
        check (expires_at is null or expires_at > starts_at)
);

create trigger hwarang_join_codes_set_updated_at
before update on public.hwarang_join_codes
for each row execute function private.set_updated_at();


create or replace function private.hash_hwarang_join_code(
    p_code text
)
returns text
language sql
immutable
set search_path = ''
as $$
    select encode(
        extensions.digest(
            upper(btrim(p_code)),
            'sha256'
        ),
        'hex'
    );
$$;

revoke all on function private.hash_hwarang_join_code(text) from public;


create or replace function private.validate_hwarang_join_code_impl(
    p_code text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.hwarang_join_codes jc
        where jc.code_hash = private.hash_hwarang_join_code(p_code)
          and jc.is_active = true
          and jc.starts_at <= now()
          and (jc.expires_at is null or jc.expires_at > now())
          and (jc.max_uses is null or jc.used_count < jc.max_uses)
    );
$$;

revoke all on function private.validate_hwarang_join_code_impl(text) from public;
grant execute on function private.validate_hwarang_join_code_impl(text)
    to anon, authenticated, service_role;


create or replace function public.validate_hwarang_join_code(
    p_code text
)
returns boolean
language sql
stable
set search_path = ''
as $$
    select private.validate_hwarang_join_code_impl(p_code);
$$;

revoke all on function public.validate_hwarang_join_code(text) from public;
grant execute on function public.validate_hwarang_join_code(text)
    to anon, authenticated, service_role;


create or replace function private.get_joinable_branches_impl(
    p_code text
)
returns table (
    organization_code text,
    organization_name text,
    parent_name text
)
language sql
stable
security definer
set search_path = ''
as $$
    with valid_code as (
        select
            jc.scope_organization_unit_id,
            jc.allow_descendants
        from public.hwarang_join_codes jc
        where jc.code_hash = private.hash_hwarang_join_code(p_code)
          and jc.is_active = true
          and jc.starts_at <= now()
          and (jc.expires_at is null or jc.expires_at > now())
          and (jc.max_uses is null or jc.used_count < jc.max_uses)
        limit 1
    )
    select
        branch.code,
        branch.name,
        parent.name
    from valid_code vc
    join public.organization_units branch
      on branch.unit_type = 'branch'
     and branch.is_active = true
    left join public.organization_units parent
      on parent.id = branch.parent_id
    where
        vc.scope_organization_unit_id is null
        or (
            vc.allow_descendants = true
            and private.is_org_descendant(
                vc.scope_organization_unit_id,
                branch.id
            )
        )
        or (
            vc.allow_descendants = false
            and vc.scope_organization_unit_id = branch.id
        )
    order by parent.sort_order, branch.sort_order;
$$;

revoke all on function private.get_joinable_branches_impl(text) from public;
grant execute on function private.get_joinable_branches_impl(text)
    to anon, authenticated, service_role;


create or replace function public.get_joinable_branches(
    p_code text
)
returns table (
    organization_code text,
    organization_name text,
    parent_name text
)
language sql
stable
set search_path = ''
as $$
    select * from private.get_joinable_branches_impl(p_code);
$$;

revoke all on function public.get_joinable_branches(text) from public;
grant execute on function public.get_joinable_branches(text)
    to anon, authenticated, service_role;


-- ---------------------------------------------------------
-- 9. 앱 접근권한
-- ---------------------------------------------------------
create table public.hwarang_app_access (
    user_id uuid not null
        references public.profiles(id) on delete cascade,

    app_code text not null
        check (app_code in ('workspace', 'calculator', 'academy')),

    is_enabled boolean not null default true,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    primary key (user_id, app_code)
);

create index hwarang_app_access_app_idx
    on public.hwarang_app_access(app_code, is_enabled);

create trigger hwarang_app_access_set_updated_at
before update on public.hwarang_app_access
for each row execute function private.set_updated_at();


create or replace function private.ensure_default_app_access()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.hwarang_app_access(user_id, app_code, is_enabled)
    values
        (new.id, 'workspace', true),
        (new.id, 'calculator', true),
        (new.id, 'academy', true)
    on conflict (user_id, app_code) do nothing;

    return new;
end;
$$;

revoke all on function private.ensure_default_app_access() from public;


create trigger on_profile_created_app_access
after insert on public.profiles
for each row execute function private.ensure_default_app_access();


-- ---------------------------------------------------------
-- 10. Auth user -> HWARANG profile 자동 생성
--
-- signup_mode = hwarang_self_signup:
--   join_code / login_id / display_name / organization_code 필수
--   user + FP + 선택지점 + active=true
--
-- Dashboard 등 관리자가 직접 만든 Auth user:
--   inactive placeholder profile 생성
--   이후 bootstrap/admin 화면에서 활성화
-- ---------------------------------------------------------
create or replace function private.handle_new_hwarang_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_mode text;

    v_login_id text;
    v_display_name text;
    v_org_code text;
    v_join_code text;

    v_org_id uuid;
    v_join public.hwarang_join_codes%rowtype;
begin
    v_mode := coalesce(new.raw_user_meta_data ->> 'signup_mode', '');

    if v_mode <> 'hwarang_self_signup' then
        insert into public.profiles (
            id,
            auth_email,
            role,
            is_active,
            position_code
        )
        values (
            new.id,
            lower(new.email),
            'user',
            false,
            'fp'
        )
        on conflict (id) do nothing;

        return new;
    end if;

    v_login_id :=
        nullif(btrim(new.raw_user_meta_data ->> 'login_id'), '');

    v_display_name :=
        nullif(btrim(new.raw_user_meta_data ->> 'display_name'), '');

    v_org_code :=
        nullif(btrim(new.raw_user_meta_data ->> 'organization_code'), '');

    v_join_code :=
        nullif(btrim(new.raw_user_meta_data ->> 'join_code'), '');

    if v_login_id is null then
        raise exception 'LOGIN_ID_REQUIRED';
    end if;

    if v_display_name is null then
        raise exception 'DISPLAY_NAME_REQUIRED';
    end if;

    if v_org_code is null then
        raise exception 'ORGANIZATION_REQUIRED';
    end if;

    if v_join_code is null then
        raise exception 'JOIN_CODE_REQUIRED';
    end if;

    if v_login_id !~ '^[A-Za-z0-9._-]{3,32}$' then
        raise exception 'INVALID_LOGIN_ID';
    end if;

    select id
    into v_org_id
    from public.organization_units
    where code = v_org_code
      and unit_type = 'branch'
      and is_active = true;

    if v_org_id is null then
        raise exception 'INVALID_ORGANIZATION';
    end if;

    select *
    into v_join
    from public.hwarang_join_codes
    where code_hash = private.hash_hwarang_join_code(v_join_code)
      and is_active = true
      and starts_at <= now()
      and (expires_at is null or expires_at > now())
      and (max_uses is null or used_count < max_uses)
    limit 1
    for update;

    if not found then
        raise exception 'INVALID_JOIN_CODE';
    end if;

    if v_join.scope_organization_unit_id is not null then
        if v_join.allow_descendants = true then
            if not private.is_org_descendant(
                v_join.scope_organization_unit_id,
                v_org_id
            ) then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        else
            if v_join.scope_organization_unit_id <> v_org_id then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        end if;
    end if;

    insert into public.profiles (
        id,
        login_id,
        auth_email,
        display_name,
        role,
        is_active,
        organization_unit_id,
        position_code
    )
    values (
        new.id,
        v_login_id,
        lower(new.email),
        v_display_name,
        'user',
        true,
        v_org_id,
        'fp'
    );

    update public.hwarang_join_codes
    set used_count = used_count + 1
    where id = v_join.id;

    -- 가입코드 원문을 Auth metadata에 남기지 않음
    update auth.users
    set raw_user_meta_data =
        coalesce(raw_user_meta_data, '{}'::jsonb) - 'join_code'
    where id = new.id;

    return new;

exception
    when unique_violation then
        raise exception 'LOGIN_ID_ALREADY_EXISTS';
end;
$$;

revoke all on function private.handle_new_hwarang_user()
    from public, anon, authenticated;


create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_hwarang_user();


-- Auth 이메일 변경 시 profile에도 동기화
create or replace function private.sync_profile_auth_email()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if new.email is distinct from old.email then
        update public.profiles
        set auth_email = lower(new.email)
        where id = new.id;
    end if;

    return new;
end;
$$;

revoke all on function private.sync_profile_auth_email() from public;


create trigger on_auth_user_email_changed
after update of email on auth.users
for each row execute function private.sync_profile_auth_email();


-- 이 SQL 실행 전에 이미 존재하는 Auth user가 있으면 placeholder profile 생성
insert into public.profiles (
    id,
    auth_email,
    role,
    is_active,
    position_code
)
select
    u.id,
    lower(u.email),
    'user',
    false,
    'fp'
from auth.users u
on conflict (id) do nothing;


-- ---------------------------------------------------------
-- 11. WORKSPACE -> ACADEMY/CALCULATOR 1회용 진입권
-- ---------------------------------------------------------
create table public.hwarang_app_launch_tickets (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references public.profiles(id) on delete cascade,

    target_app text not null
        check (target_app in ('academy', 'calculator', 'workspace')),

    token_hash text not null unique,

    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    consumed_at timestamptz,

    constraint hwarang_launch_ticket_expiry_check
        check (expires_at > created_at)
);

create index hwarang_launch_ticket_lookup_idx
    on public.hwarang_app_launch_tickets(token_hash, target_app);


create or replace function private.hash_launch_ticket(
    p_ticket text
)
returns text
language sql
immutable
set search_path = ''
as $$
    select encode(
        extensions.digest(p_ticket, 'sha256'),
        'hex'
    );
$$;

revoke all on function private.hash_launch_ticket(text) from public;


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


create or replace function public.issue_hwarang_app_launch_ticket(
    p_user_id uuid,
    p_target_app text
)
returns text
language sql
set search_path = ''
as $$
    select private.issue_launch_ticket_impl(p_user_id, p_target_app);
$$;

revoke all on function public.issue_hwarang_app_launch_ticket(uuid, text)
    from public, anon, authenticated;
grant execute on function public.issue_hwarang_app_launch_ticket(uuid, text)
    to service_role;


create or replace function private.consume_launch_ticket_impl(
    p_ticket text,
    p_target_app text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_user_id uuid;
begin
    update public.hwarang_app_launch_tickets
    set consumed_at = now()
    where token_hash = private.hash_launch_ticket(p_ticket)
      and target_app = p_target_app
      and consumed_at is null
      and expires_at > now()
    returning user_id into v_user_id;

    if v_user_id is null then
        raise exception 'INVALID_OR_EXPIRED_LAUNCH_TICKET';
    end if;

    if not exists (
        select 1
        from public.profiles p
        join public.hwarang_app_access a
          on a.user_id = p.id
         and a.app_code = p_target_app
         and a.is_enabled = true
        where p.id = v_user_id
          and p.is_active = true
    ) then
        raise exception 'APP_ACCESS_DENIED';
    end if;

    return v_user_id;
end;
$$;

revoke all on function private.consume_launch_ticket_impl(text, text) from public;
grant execute on function private.consume_launch_ticket_impl(text, text)
    to service_role;


create or replace function public.consume_hwarang_app_launch_ticket(
    p_ticket text,
    p_target_app text
)
returns uuid
language sql
set search_path = ''
as $$
    select private.consume_launch_ticket_impl(p_ticket, p_target_app);
$$;

revoke all on function public.consume_hwarang_app_launch_ticket(text, text)
    from public, anon, authenticated;
grant execute on function public.consume_hwarang_app_launch_ticket(text, text)
    to service_role;


-- ---------------------------------------------------------
-- 12. RLS
-- ---------------------------------------------------------
alter table public.positions enable row level security;
alter table public.organization_units enable row level security;
alter table public.profiles enable row level security;
alter table public.hwarang_join_codes enable row level security;
alter table public.hwarang_app_access enable row level security;
alter table public.hwarang_app_launch_tickets enable row level security;


-- ---------------------------------------------------------
-- 13. Grants
-- ---------------------------------------------------------
revoke all on table public.positions from anon, authenticated;
revoke all on table public.organization_units from anon, authenticated;
revoke all on table public.profiles from anon, authenticated;
revoke all on table public.hwarang_join_codes from anon, authenticated;
revoke all on table public.hwarang_app_access from anon, authenticated;
revoke all on table public.hwarang_app_launch_tickets from anon, authenticated;

grant usage on schema public to anon, authenticated, service_role;

-- 일반 로그인 사용자가 화면에 필요한 공통 조직/직책 조회
grant select on table public.positions to authenticated;
grant select on table public.organization_units to authenticated;

-- auth_email 제외 컬럼만 일반 사용자 조회 허용
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
on public.profiles to authenticated;

grant update (display_name)
on public.profiles to authenticated;

-- 자신의 앱 권한 확인
grant select
on public.hwarang_app_access to authenticated;

-- service_role: 서버 전용 전체 접근
grant select, insert, update, delete on table public.positions to service_role;
grant select, insert, update, delete on table public.organization_units to service_role;
grant select, insert, update, delete on table public.profiles to service_role;
grant select, insert, update, delete on table public.hwarang_join_codes to service_role;
grant select, insert, update, delete on table public.hwarang_app_access to service_role;
grant select, insert, update, delete on table public.hwarang_app_launch_tickets to service_role;


-- ---------------------------------------------------------
-- 14. RLS policies
-- ---------------------------------------------------------
create policy positions_authenticated_read
on public.positions
for select
to authenticated
using (true);


create policy organization_units_authenticated_read
on public.organization_units
for select
to authenticated
using (true);


create policy profiles_select_scope
on public.profiles
for select
to authenticated
using (
    private.can_view_user(id)
);


create policy profiles_update_own
on public.profiles
for update
to authenticated
using (
    (select auth.uid()) = id
)
with check (
    (select auth.uid()) = id
);


create policy hwarang_join_codes_super_admin_select
on public.hwarang_join_codes
for select
to authenticated
using (
    private.is_super_admin()
);

create policy hwarang_join_codes_super_admin_insert
on public.hwarang_join_codes
for insert
to authenticated
with check (
    private.is_super_admin()
);

create policy hwarang_join_codes_super_admin_update
on public.hwarang_join_codes
for update
to authenticated
using (
    private.is_super_admin()
)
with check (
    private.is_super_admin()
);

create policy hwarang_join_codes_super_admin_delete
on public.hwarang_join_codes
for delete
to authenticated
using (
    private.is_super_admin()
);


create policy hwarang_app_access_select_own
on public.hwarang_app_access
for select
to authenticated
using (
    user_id = (select auth.uid())
);


-- launch ticket table은 클라이언트 직접 접근 금지
-- service_role만 직접 사용


commit;
