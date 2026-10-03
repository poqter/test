-- =========================================================
-- HWARANG PLATFORM
-- BOOTSTRAP SUPER ADMIN + FIRST JOIN CODE
--
-- 실행 순서:
-- 1) 01_HWARANG_PLATFORM_CORE_SCHEMA_v1.sql 성공
-- 2) Supabase > Authentication > Users 에서 본인 Auth user 생성
--    - 실제 이메일
--    - 원하는 비밀번호
--    - Auto confirm ON
-- 3) 아래 두 값만 직접 수정 후 실행
--
--    YOUR_AUTH_EMAIL
--    YOUR_NEW_JOIN_CODE
--
-- 가입코드는 채팅/GitHub에 올리지 않는 것을 권장합니다.
-- =========================================================

begin;

-- ---------------------------------------------------------
-- 1. 최초 super_admin 지정
-- rockexe / 박병선 / 드림지점 / 팀장 / super_admin
-- ---------------------------------------------------------
update public.profiles p
set
    login_id = 'rockexe',
    display_name = '박병선',
    role = 'super_admin',
    is_active = true,
    organization_unit_id = (
        select id
        from public.organization_units
        where code = 'DREAM_BRANCH'
    ),
    position_code = 'team_leader'
from auth.users u
where p.id = u.id
  and lower(u.email) = lower('YOUR_AUTH_EMAIL');


-- 최초 관리자가 실제로 갱신되었는지 검사
do $$
begin
    if not exists (
        select 1
        from public.profiles
        where login_id = 'rockexe'
          and role = 'super_admin'
          and is_active = true
    ) then
        raise exception 'BOOTSTRAP_ADMIN_NOT_FOUND - YOUR_AUTH_EMAIL을 확인하세요.';
    end if;
end
$$;


-- ---------------------------------------------------------
-- 2. 첫 HWARANG 공통 가입코드 생성
-- 기존 대화에 노출된 예전 코드는 재사용하지 않는 것을 권장
-- ---------------------------------------------------------
insert into public.hwarang_join_codes (
    name,
    code_hash,
    scope_organization_unit_id,
    allow_descendants,
    is_active,
    max_uses,
    created_by
)
values (
    'HWARANG 공통 가입코드',

    private.hash_hwarang_join_code(
        'YOUR_NEW_JOIN_CODE'
    ),

    -- null = 모든 지점 가입 가능
    null,

    true,
    true,

    -- null = 사용횟수 제한 없음
    null,

    (
        select id
        from public.profiles
        where login_id = 'rockexe'
    )
)
on conflict (code_hash)
do update set
    name = excluded.name,
    is_active = true,
    scope_organization_unit_id = excluded.scope_organization_unit_id,
    allow_descendants = excluded.allow_descendants,
    max_uses = excluded.max_uses,
    created_by = excluded.created_by;


commit;


-- ---------------------------------------------------------
-- 3. 확인용 조회
-- ---------------------------------------------------------
select
    p.login_id,
    p.display_name,
    p.role,
    pos.display_name as position_name,
    ou.name as organization_name,
    p.is_active
from public.profiles p
left join public.positions pos
    on pos.code = p.position_code
left join public.organization_units ou
    on ou.id = p.organization_unit_id
where p.login_id = 'rockexe';


select
    name,
    is_active,
    used_count,
    max_uses,
    scope_organization_unit_id,
    created_at
from public.hwarang_join_codes
order by created_at desc;
