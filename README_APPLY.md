# HWARANG API PREFLIGHT FIX V1

기준 소스: Git HEAD `3ffbb7bc91caf1aabbb55f197df21d028079dbcc`

## 적용 방법
이 ZIP은 **변경/추가 파일만** 들어 있습니다. 자동 패치 스크립트는 없습니다.

1. ZIP 안 파일을 저장소의 동일 경로에 복사/덮어쓰기합니다.
2. Supabase SQL Editor에서 새 Query `11_API_Preflight_Fixes`를 만듭니다.
3. `supabase/migrations/11_API_Preflight_Fixes.sql` 전체를 **1회 실행**합니다.
4. 기존 01~10은 다시 실행하지 않습니다.
5. GitHub push → Streamlit 배포합니다.
6. 최고관리자 WORKSPACE → 관리자 센터 → 시스템 설정 → `PRE-API 자가진단 실행`을 눌러 확인합니다.
7. 실제 OpenAI API 연결 전까지 AI 서비스/Text/Voice/AI 정식평가는 계속 OFF로 둡니다.

## 이번 수정 핵심
- Voice 예약 만료: 10분 고정 → 허용 Voice 시간 + 10분 buffer
- 1인 1 AI Session: PostgreSQL advisory lock으로 원자적 강제
- reservation RPC에서 Session 소유권/진행상태/lock 재검증
- 차단 로그: RAISE rollback 문제 제거, `blocked` registry + activity log 영구 기록
- idempotency 동시 race에서도 이중 이용량 예약 방지
- Retry: 같은 request_id/reservation을 재사용하는 `start_hwarang_ai_request` 추가
- Formal AI 평가: 동일 source snapshot의 DB unique + repository/runtime 재사용
- Customer AI에서 hidden coverage_analysis / proposal_state / raw insurance_state 제거
- 보험정보는 Python이 승인한 `insurance_memory`만 Customer AI에 공개
- 입력창/기존 deterministic backend/API guardrail을 모두 2,400자로 정렬
- 관리자 시간 표시 Asia/Seoul 고정
- `jsonschema` direct runtime dependency 명시
- 관리자센터에 외부 API를 쓰지 않는 PRE-API 배포환경 자가진단 추가

## 검증 결과
- Python compile: PASS
- pytest: **40 passed**
- unittest subtests: **58 passed**
- Random generated cases: **1,000 / failures 0**
- Customer hidden analysis/proposal leak: PASS
- Insurance disclosure projection: PASS
- Evaluator snapshot reuse: PASS
- Voice/Training separation regression: PASS
- Frontend / deterministic backend / API input limit 2,400 정렬: PASS

## 주의
`11_API_Preflight_Fixes.sql`은 정적 검사를 완료했지만 실제 Supabase 실행은 사용자의 프로젝트에서 처음 수행됩니다.
SQL Editor에서 오류가 발생하면 그 오류를 그대로 전달해 주세요.
