# 1.15.0 추가 검증

`python -m pytest -q`: 전체 325개.
`python tests/studio_ui/check.py`: API/DB를 테스트 대역으로 바꾼 UI 흐름 검증.
실제 공급자 응답 품질이나 운영 DB 권한 검증으로 해석하지 않습니다.

# 로컬 검증

- Python: `python -m pytest -q`
- 기존 공개 페이지: `node tests/test_briefing_public.mjs`
- 격리 DB: `cd tests/studio_db`, `npm ci`, `node check.mjs`

DB 검사는 PGlite의 PostgreSQL 실행 엔진에서 가상 Auth·계정을 사용합니다. 기존 01의 pgcrypto는 가상 함수로 대체하며 로그인 티켓/암호화 기능을 검증하는 시험은 아닙니다. 23/24와 원장/권한/공유 처리를 검증합니다. 운영 DB나 외부 API에 연결하지 않습니다.
