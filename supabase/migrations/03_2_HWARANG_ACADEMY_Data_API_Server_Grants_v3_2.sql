-- =========================================================
-- HWARANG ACADEMY
-- Data API Server Grants v3.2
--
-- 프로젝트 생성 시 "Automatically expose new tables"를 끈 경우,
-- 서버용 sb_secret_* 키가 Data API를 통해 필요한 테이블을 읽고
-- 관리할 수 있도록 service_role 권한을 명시적으로 부여합니다.
-- =========================================================

-- Academy 서버가 login_id -> Auth UID를 찾고 프로필을 관리할 수 있도록 허용
grant select, insert, update, delete on table public.profiles to service_role;

-- 로그인 후 화면 표시용 직책/조직 이름 조회
grant select on table public.positions to service_role;
grant select on table public.organization_units to service_role;

-- 향후 관리자 화면에서 가입코드 생성/중지/수정 가능
grant select, insert, update, delete on table public.academy_join_codes to service_role;

-- 서버/공개 회원가입 흐름에서 사용하는 함수 권한을 명시적으로 유지
grant execute on function public.get_joinable_branches(text) to anon, authenticated, service_role;
grant execute on function public.validate_academy_join_code(text) to anon, authenticated, service_role;
grant execute on function public.is_org_descendant(uuid, uuid) to authenticated, service_role;
grant execute on function public.can_view_user(uuid) to authenticated, service_role;

-- 일반 사용자의 기존 최소 권한은 그대로 유지
-- profiles: authenticated는 본인/산하 사용자 SELECT + 본인 display_name UPDATE만 허용
-- academy_join_codes: 일반 사용자는 테이블 직접 조회 불가
