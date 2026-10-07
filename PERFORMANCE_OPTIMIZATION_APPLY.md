# 화랑 WORKSPACE 성능 최적화 적용 안내

## 산출물 상태

- 기준: `HWARANG_WORKSPACE_BRIEFING_STAGE1_FULL` 최신 Stage 1 통파일
- WORKSPACE build: `hwarang-2026.10.07-platform-v63-performance`
- Briefing engine: `1.7.2-stage1` 유지
- Migration 16: 수정/재실행 금지, 그대로 유지
- 신규 corrective migration: `supabase/migrations/17_Workspace_Performance_Login_Only.sql`

## 핵심 변경

1. 메뉴/페이지 `APP_OPENED`, heartbeat, logout 일반 활동 추적 제거. WORKSPACE 일반 활동기록은 로그인 성공만 유지.
2. 관리자 Audit, Credit/Voice Ledger, 브리핑 공개/수정 Audit 등 상태 변경 이력은 유지.
3. 메뉴 이동 callback + 권한목록 1회 계산 재사용으로 불필요한 rerun/설정 재조회 축소.
4. ACADEMY/계산기 launch ticket은 기존 새 탭 UX를 유지하면서 45초간 유효 URL 재사용.
5. 로그인 후 주기적 권한 재검증은 Migration 17 적용 시 단일 auth-context RPC 사용. 미적용 환경은 기존 경로 fallback.
6. 홈/브리핑 허브는 Profile summary를 일괄 조회하고 선택 Profile만 전체 Bundle 조회.
7. 과거 브리핑 목록 N+1 제거, Event Timeline 일괄 조회.
8. 관리자센터 짧은 read cache + AI 일간 aggregate view 사용. 상세 AI 원장은 요청 시만 로드.
9. 반복 PDF/Excel 생성 캐시, 업로드 Excel 파싱 캐시, 정적 JSON/로고 캐시, 일부 heavy export import 지연.
10. 단기납 비교기의 인위적 0.25초 대기 제거.

## 적용 순서

1. 현재 테스트 서버/저장소를 백업한다.
2. 전체 통파일을 사용하는 경우 새 `HWARANG_WORKSPACE_PERFORMANCE_V63_FULL.zip`을 저장소 루트에 덮어쓴다. 변경파일만 적용하는 경우 `HWARANG_WORKSPACE_PERFORMANCE_V63_PATCH.zip`을 저장소 루트 기준으로 덮어쓴다.
3. Supabase SQL Editor에서 **Migration 17을 1회만** 실행한다.
4. `POST_MIGRATION17_VERIFY.sql`을 실행해 함수와 로그인 기록을 읽기 검증한다.
5. Streamlit 테스트 앱을 재시작한다.
6. 로그인 → 홈 → 일반 도구 3~4개 → 브리핑 센터 → 관리자센터 → ACADEMY/계산기 새 탭 순으로 smoke test한다.

## 적용 후 확인

- 로그인 성공 시 `profiles.last_login_at` 갱신 및 `LOGIN_SUCCESS` 1건 기록.
- WORKSPACE 메뉴 이동으로 `APP_OPENED`/heartbeat가 추가되지 않음.
- 관리자센터의 오늘 로그인 수와 최근 로그인 표시가 정상.
- 사용자 권한 변경, Credit/Voice 조정, 브리핑 공개/정정 Audit는 정상 유지.
- 홈/일반 메뉴 이동 후 체감 대기 감소.
- 브리핑 홈 카드/과거 목록/Timeline 정상 표시.
- ACADEMY와 종합 계산기 새 탭 로그인 연결 정상.

## 검증 결과

- `python -m compileall`: 통과
- 성능/로그인 집중 테스트: **12 passed**
- Streamlit AppTest 3개를 제외한 기존 회귀테스트: **142 passed, 61 subtests passed**
- 제외 사유: 현재 빌드 컨테이너에 `streamlit` 패키지가 없어 `streamlit.testing.v1.AppTest` 3개 모듈을 collect할 수 없음.
- 운영 서버, 실제 브라우저 픽셀/네트워크 성능, 실제 Supabase Migration 17 적용은 이 패키지 제작 과정에서 직접 수행하지 않음.

## 되돌리기

- 코드 문제: 배포 전 보관한 이전 Stage 1 코드로 되돌린다.
- Migration 17은 기존 테이블 데이터를 삭제하지 않고 함수 동작을 교체한다. 롤백이 필요하면 Migration 12의 `complete_hwarang_workspace_login` 정의를 별도 corrective migration으로 복원해야 하며, 이미 적용한 Migration 17 파일 자체를 수정해서 재사용하지 않는다.
