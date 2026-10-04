# HWARANG LOGIN FAST PATH V1

로그인 버튼 클릭 후 홈 화면까지의 네트워크 왕복을 줄이는 패치입니다.

## 변경 파일
- `app.py`
- `modules/shared/hwarang_auth.py`

## 신규 파일
- `supabase/migrations/12_Login_Fast_Path.sql`
- `tests/test_login_fast_path.py`

## 적용 순서
1. `12_Login_Fast_Path.sql`을 Supabase SQL Editor에서 **1회 실행**합니다.
2. 기존 01~11은 다시 실행하지 않습니다.
3. `app.py`, `modules/shared/hwarang_auth.py`를 같은 경로에 덮어씁니다.
4. `tests/test_login_fast_path.py`는 테스트 폴더에 추가합니다.
5. GitHub push → Streamlit 배포합니다.

## 변경 후 정상 로그인 경로
1. `get_hwarang_login_bootstrap` — 로그인 ID → Auth 이메일/UID 확인
2. Supabase Auth — 비밀번호 검증
3. `complete_hwarang_workspace_login` — 프로필·조직·직책·앱 권한·세부 권한·로그인 세션·로그 기록을 한 번에 처리

즉 정상 로그인은 **3번의 순차 네트워크 요청**으로 줄어듭니다.

추가로 로그인 직후 불필요했던 즉시 heartbeat와 `APP_OPENED/home` 중복 로그를 생략합니다.
로그인 기록 자체는 `LOGIN_SUCCESS`로 정상 보존됩니다.

## 배포 안전성
Migration 12가 아직 적용되지 않은 환경에서는 기존 로그인 경로로 자동 fallback합니다.
따라서 권장 적용 순서는 SQL 12 → Python 파일 배포지만, 배포 순서가 잠시 어긋나도 로그인 자체가 바로 중단되지 않도록 구성했습니다.
