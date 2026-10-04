# HWARANG PLATFORM · Supabase

이 폴더는 HWARANG 공통 계정과 ACADEMY 데이터 구조의 SQL 이력을 보관합니다.

## 현재 적용 순서

1. `01_Core_Setup.sql` — 공통 계정, 조직, 직책, 가입코드, 앱 접근권한, 앱간 1회용 진입권
2. `02_Admin_Setup.sql` — 최초 최고관리자와 첫 가입코드 부트스트랩
3. `03_Academy_Data.sql` — Case / Session / Assessment / Learning Profile
4. `04_Admin_View.sql` — 관리자용 사용자 조회 View
5. `05_API_Access.sql` — Data API 권한 보강
6. `06_Platform_Update.sql` — 진입권 정리, 서버측 조직 권한 판정, 관리자 View 확장
7. `07_Permissions_Admin.sql` — 앱·세부기능 권한, 최고관리자 계정관리, 변경이력
8. `08_Pre_API_Engine.sql` — 랜덤 Case/보장분석/제안/음성준비/증거로그용 ACADEMY 필드

이미 실행한 SQL은 과거 이력으로 유지하고 다시 실행할 필요가 없습니다. 새 변경은 다음 번호의 SQL로 추가합니다.

## Streamlit Secrets

WORKSPACE / CALCULATOR / ACADEMY는 같은 Supabase 프로젝트를 사용합니다.

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
SUPABASE_SECRET_KEY = "sb_secret_..."
```

Secret Key는 Streamlit 서버에서만 사용하고 GitHub, 브라우저 JavaScript, 로그에 출력하지 않습니다.

WORKSPACE:

```toml
[external_apps]
calculator_url = "https://hwarang-calculator.streamlit.app"
academy_url = "https://hwarang-academy.streamlit.app"
```

CALCULATOR / ACADEMY:

```toml
[external_apps]
workspace_url = "https://hwarang-workspace.streamlit.app"
```

ACADEMY는 추가로 다음 주소를 사용합니다.

```toml
[academy]
public_url = "https://hwarang-academy.streamlit.app/"
```

## 계정과 직책

- 시스템 권한: `user` / `admin` / `super_admin`
- `admin`은 자동 부여하지 않고 최고관리자가 직접 지정할 때만 사용합니다.
- `super_admin`은 조직 위치와 관계없이 전체 사용자 데이터 열람·권한관리의 기반입니다.
- 실제 직책은 `position_code`로 별도 관리합니다.
- 조직은 `organization_units` 트리로 관리합니다.

## ACADEMY 데이터

`academy_cases`, `academy_sessions`, `academy_assessments`, `academy_learning_profiles`는 ACADEMY 전용 데이터입니다. 공통 계정 테이블과 분리해 유지합니다.

08 migration부터 Case에는 생성기/보장분석/제안 버전이, Session에는 `training_focus`, `interaction_mode`, `evidence_log`가 명시적으로 저장될 수 있습니다.
