# HWARANG BRIEFING — WORKSPACE LIVE INTEGRATION

## 적용 상태
- Migration 16 기존 적용/검증 완료 전제
- Phase B/C 엔진 유지
- WORKSPACE `브리핑 센터` 추가
- Streamlit 서버에서 기존 `OPENAI_API_KEY` / Supabase server secret을 사용
- 초기 `run_mode=shadow` 보존: 생성 결과는 관리자 미리보기이며 자동 공개하지 않음

## 실제 흐름
1. 최고관리자/콘텐츠 관리자가 브리핑 센터에서 `오늘 브리핑 생성` 클릭
2. Shared Web Discovery 4 lanes 실행
3. Python Freshness/Source/Relevance Gate
4. Shared Event Cluster + Profile Routing
5. Phase C model-only 분석
6. Migration 16 테이블에 Job/Usage/Event/Revision/Snapshot/Issue/Action/Source 저장
7. 브리핑 센터에서 관리자 미리보기
8. validation/coverage gate 통과 시 `공개하기`
9. 일반 사용자는 공개 Snapshot만 조회

## UI
- 사이드바 상단 `브리핑 센터`
- HOME에는 공개 브리핑이 있을 때만 작은 `오늘의 브리핑` 요약
- 브리핑 센터: 오늘 브리핑 / 과거 브리핑
- Profile 카드: MARKET / INSURANCE / NEWS
- 상세: FAST BRIEF → TODAY ACTION → 핵심 이슈 → 참고 이슈 → 출처 → Event Timeline
- 관리자만 `콘텐츠 관리` 및 `공개하기` 노출

## MARKET
- MARKET V1은 Direct/Provider-first 정책 유지
- 검증된 MARKET Direct Source가 없으면 draft는 `coverage_status=insufficient`
- 이 상태는 자동/수동 공개 Gate에서 차단됨
- INSURANCE/NEWS Web Discovery 때문에 MARKET Search를 임의로 추가하지 않음

## OpenAI
- Discovery include: `web_search_call.results`, `web_search_call.action.sources`
- Phase C는 Web Search tool을 제공하지 않는 model-only Structured Output
- `BRIEFING_ROUTINE_MODEL`이 없으면 기존 `BRIEFING_DISCOVERY_MODEL` 재사용

## 이번 적용에 DB migration 없음
Migration 16을 수정/재실행하지 않음.
