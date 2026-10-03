# HWARANG ACADEMY · Supabase Auth 적용 메모

## 현재 적용 순서
1. Profile Base v1
2. Organization & Position v2
3. Self Signup v3
4. `03_1_HWARANG_ACADEMY_Signup_Security_Patch_v3_1.sql`
5. `03_2_HWARANG_ACADEMY_Data_API_Server_Grants_v3_2.sql`

## Streamlit Secrets
```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
SUPABASE_SECRET_KEY = "sb_secret_..."

[academy]
public_url = "https://hwarang-academy.streamlit.app/"
```

`SUPABASE_SECRET_KEY`는 Streamlit 서버에서만 사용하고 GitHub/브라우저 코드에는 넣지 않습니다.

## 로그인 흐름
사용자는 `login_id + password`만 입력합니다. 서버가 `profiles.login_id`에서 Auth UID를 찾고,
Supabase Auth의 내부 이메일을 확인한 뒤 이메일/비밀번호 인증을 수행합니다.

## 셀프 회원가입
가입코드 확인 → 허용된 지점 선택 → 아이디/비밀번호/이름/이메일 등록 →
Supabase Auth 생성 → DB Trigger가 `role=user`, `position=fp`, 선택 지점을 자동 기록합니다.
