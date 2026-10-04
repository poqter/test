# HWARANG PRE-API FINAL V1 — 적용 파일

이번 패키지는 **변경/추가 파일만** 들어 있습니다. 자동 패치 스크립트는 없습니다.

## 덮어쓰기
- `academy_app.py`
- `modules/shared/ai_guardrails.py`
- `modules/shared/admin_center_ui.py`
- `modules/shared/academy_credit_ui.py`
- `hwarang_academy/pre_api/constants.py`
- `hwarang_academy/pre_api/__init__.py`

## 새로 추가
- `supabase/migrations/10_Pre_API_Finalization.sql`
- `hwarang_academy/pre_api/api_contracts.py`
- `hwarang_academy/pre_api/prompt_builder.py`
- `hwarang_academy/pre_api/state_validator.py`
- `hwarang_academy/pre_api/mock_ai.py`
- `hwarang_academy/pre_api/runtime.py`
- `hwarang_academy/pre_api/readiness.py`
- `tests/test_pre_api_finalization.py`

## 적용 순서
1. 위 파일을 저장소의 동일한 경로에 복사/덮어쓰기
2. Supabase SQL Editor에서 `10_Pre_API_Finalization` 새 Query 생성
3. `10_Pre_API_Finalization.sql` 전체를 **1회 실행**
4. 기존 01~09는 다시 실행하지 않음
5. Git commit/push 후 WORKSPACE/ACADEMY 화면 확인

## 정상 상태
- AI 서비스는 여전히 OFF가 기본값
- OpenAI API 호출 없음
- 훈련 크레딧: Text Customer / Coach / Formal Evaluator 공용
- 음성 이용량: 별도
- Voice V1: GPT-Live-1
- 정상 사용에 분당 호출 제한 없음
- Voice 30분 hard cap
- 1계정 1개 활성 AI Session
- 동일 요청 중복 호출 방지
- 관리자센터에서 훈련 크레딧과 음성 이용량을 각각 관리

`PRE_API_FINAL_AUDIT.md`에 API 연결 직전 최종 상태를 정리했습니다.
