-- =========================================================
-- HWARANG ACADEMY
-- Signup Security Patch v3.1
--
-- 가입코드 원문을 신규 Auth 사용자의 metadata에 남기지 않습니다.
-- Self Signup Schema v3 적용 후 1회 실행합니다.
-- =========================================================

create or replace function public.handle_new_academy_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$

declare
    v_login_id text;
    v_display_name text;
    v_org_code text;
    v_join_code text;
    v_org_id uuid;
    v_join public.academy_join_codes%rowtype;

begin
    v_login_id := nullif(btrim(new.raw_user_meta_data ->> 'login_id'), '');
    v_display_name := nullif(btrim(new.raw_user_meta_data ->> 'display_name'), '');
    v_org_code := nullif(btrim(new.raw_user_meta_data ->> 'organization_code'), '');
    v_join_code := nullif(btrim(new.raw_user_meta_data ->> 'join_code'), '');

    if v_login_id is null then raise exception 'LOGIN_ID_REQUIRED'; end if;
    if v_display_name is null then raise exception 'DISPLAY_NAME_REQUIRED'; end if;
    if v_org_code is null then raise exception 'ORGANIZATION_REQUIRED'; end if;
    if v_join_code is null then raise exception 'JOIN_CODE_REQUIRED'; end if;

    if v_login_id !~ '^[A-Za-z0-9._-]{3,32}$' then
        raise exception 'INVALID_LOGIN_ID';
    end if;

    select id into v_org_id
    from public.organization_units
    where code = v_org_code
      and unit_type = 'branch'
      and is_active = true;

    if v_org_id is null then raise exception 'INVALID_ORGANIZATION'; end if;

    select * into v_join
    from public.academy_join_codes
    where code_hash = public.hash_academy_join_code(v_join_code)
      and is_active = true
      and starts_at <= now()
      and (expires_at is null or expires_at > now())
      and (max_uses is null or used_count < max_uses)
    limit 1
    for update;

    if not found then raise exception 'INVALID_JOIN_CODE'; end if;

    if v_join.scope_organization_unit_id is not null then
        if v_join.allow_descendants = true then
            if not public.is_org_descendant(v_join.scope_organization_unit_id, v_org_id) then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        else
            if v_join.scope_organization_unit_id <> v_org_id then
                raise exception 'ORGANIZATION_NOT_ALLOWED';
            end if;
        end if;
    end if;

    insert into public.profiles (
        id, login_id, display_name, role, is_active,
        organization_unit_id, position_code
    ) values (
        new.id, v_login_id, v_display_name, 'user', true,
        v_org_id, 'fp'
    );

    update public.academy_join_codes
    set used_count = used_count + 1
    where id = v_join.id;

    -- 가입코드 원문은 검증 직후 Auth metadata에서 제거합니다.
    update auth.users
    set raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb) - 'join_code'
    where id = new.id;

    return new;

exception
    when unique_violation then
        raise exception 'LOGIN_ID_ALREADY_EXISTS';
end;
$$;
