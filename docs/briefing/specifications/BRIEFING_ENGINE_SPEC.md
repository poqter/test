# 화랑 브리핑 공통 엔진 명세 V1.8.0

- 기준일 2026-10-08 / Asia/Seoul.
- 출시 범위·수량·일정: BRIEFING_V1_IMPLEMENTATION_SCOPE.md.
- Profile별 콘텐츠: NEWS_BRIEFING_SPEC.md / INSURANCE_BRIEFING_SPEC.md / MARKET_BRIEFING_SPEC.md.
- 설계 기준이며 운영 적용 완료를 의미하지 않는다.

## 1. 공통 흐름

직접 수집 → 날짜/관련성/중복 규칙 → 필요한 검색/검증 → Shared Event → 묶음 요약/해설 → QA → immutable Snapshot → 내부 게시 → 외부 Payload → 고객 공유/PDF.

고객 읽기·펼치기·복사·과거 조회·PDF 렌더링은 저장 결과를 읽는다. 별도 AI 호출이나 별도 고객 수집기를 만들지 않는다.

## 2. 실행 모드·일정

shadow는 미리보기까지, manual은 관리자 승인, auto는 정규 Gate 통과 후 게시다. is_enabled=false는 Profile Kill Switch다. external_auto_share_enabled는 내부 게시와 별개의 조직 외부 정책이다.

초기 배포는 shadow, 3~5 영업일 관찰 후 manual/auto로 전환한다. Scheduler는 Streamlit 접속과 독립이며 keepalive와 구분한다.

목표: 06:30 준비, MARKET 07:00 수집 마감/07:30 공개, NEWS·INSURANCE 07:30 마감/08:00 공개. 08:10 미완료 복구 최대 1회. 실제 마감/게시 시각 기록, UTC/KST·날짜 전환 검수. 공개를 기다리며 worker를 장시간 sleep하지 않는다.

## 3. 상태 계약

| 구분 | 값 |
|---|---|
| Job | scheduled / collecting / normalizing / validating / analyzing / generating / completed / failed |
| Publication | draft / published / partial / hidden |
| Revision | initial / update / correction / regeneration |
| Validation | ok / required / rejected |
| Coverage | healthy / degraded / insufficient |
| Evidence | official_confirmed / multi_source / reported / single_source / conflicted |
| Selection | core / light_digest / excluded |
| 내부·고객 PDF 각각 | not_requested / pending / ready / failed |

기존 저장 enum 호환을 유지한다. UI는 생성 중/공개/정정/지연/비공개를 매핑한다. 지연 안내 때문에 임의 DB enum을 추가하지 않는다.

Job completed≠published, PDF failed≠웹 게시 실패다. insufficient를 이슈 없음으로 해석하지 않는다. 일부 endpoint 실패만으로 전체 게시를 막지 않고 분야의 실제 탐지·필수 근거·QA를 평가한다.

## 4. 시각·최근성

timezone-aware 저장과 KST 표시. briefing_date, collection_window_start, collection_cutoff_at, 기사 published_at/updated_at, retrieved_at, generated_at, snapshot_created_at, 게시시각을 구분한다. 지표 as_of는 별도다.

뉴스 구간은 **전날 00:00 KST부터 해당 생성의 수집 마감까지**다. 과거 36h CORE/96h LIGHT 기준을 대체한다. 저장 enum core_window/light_window 호환이 필요해도 새 구간으로 판정한다.

발행일 미확인은 원문 meta/JSON-LD/time으로 보강한다. API 제공일·Crawled·수집일을 원문 발행일로 바꾸지 않는다. 새 사실 없는 재배포·오래된 자료는 정상 일간 기사에서 제외한다. 배경은 실제 날짜를 표시해 상세에 연결하고 수량에 넣지 않는다.

지표는 해당 시장의 마지막 확인 관측일을 사용하며 뉴스 구간과 분리한다.

## 5. Source 계약

필수 메타데이터: source_code, source_family_code, source_name, endpoint_role, source_kind, source_tier, collector_provider, publisher_name/domain, title, url/canonical_url, published_at/updated_at/retrieved_at/last_verified_at, access_status, fingerprint, untrusted_external.

추가: 발행시각 근거, description/preview 근거·길이, source_config_version, 이용 조건 및 ai_input_allowed/external_display_allowed 확인.

수집 endpoint와 실제 publisher, Provider URL과 원문 URL을 구분한다. access_status는 ok/unavailable/moved/blocked/rate_limited/credential_missing/unknown 등 실제 원인이다.

허용된 여러 종합·경제·보험 RSS/피드 우선. 공식 API는 지표·정책 검증용이다. 공식기관 필수 quota·고정 기관 Lane을 강제하지 않는다. HTML 게시판 Parser 대량 추가, 전문/사진 복제, 유료벽·차단 우회를 하지 않는다.

네이버 API는 신규 경로·AI 입력/저장/외부 표시 조건 확인 전 기본 AI 소스에서 제외한다. Google News 비공식 RSS도 공식 API의 안정성·권한 보장으로 취급하지 않는다. 두 서비스 없이 기본 엔진이 작동해야 한다.

## 6. 보완 검색·분석

기존 Responses web_search는 Coverage 부족·중요 확인에 사용한다. 검색은 후보 탐지, model-only 분석은 선별·요약으로 분리한다. 정상 직접 후보가 충분하면 추가 검색 0회.

세 Profile 통합 추천 검색 상한: Target 0~4 / Hard 6회/일. 사용자 승인 전 신규 유료 자동 실행을 허가하는 값이 아니다.

web_tool_calls, 실제 search_actions, search_retry_count, 검색 콘텐츠 토큰을 분리 계측한다. 과금되는 실제 도구 호출에도 별도 상한(초기 추천 Hard 6/일)과 금액 예산을 적용한다. 실제 검색 없는 Lane 재시도는 최대 1회이며 Hard 6에 포함한다. 기사 수를 채우는 추가 검색·기사당 독립 호출은 금지한다.

AI는 묶음 요약·실제 근거 해설·필요한 상담 문구를 작성한다. 날짜/변화/단위/URL/중복은 규칙으로 처리한다. routine_model/escalation_model 설정과 실제 model_id를 기록하고 운영 모델을 확인 없이 단정하지 않는다.

빈 영향·상담 필드는 정상일 수 있다. 모든 기사에 Action Intelligence 필드를 요구해 실패시키지 않는다. 수치·원인·Source/도구 URL은 모델이 만들지 않는다.

## 7. Shared Event·Profile

동일 URL·제목·키워드·시각 등을 규칙으로 묶고 필요할 때만 model-only 보조한다. Event는 event_key/title/source_refs/routed_profiles/first_seen/last_seen을 갖는다.

한 Event를 여러 Profile이 재사용하되 고객 통합 화면은 주 섹션에 한 번만 배치한다. 후보를 화면 상한 전에 폐기하지 않고 전체 적격 풀에서 선별한다.

대표 UI와 내부 CORE를 구분한다. 수량은 공통 범위와 각 Profile을 따른다. 편중 점검은 보조이며 낮은 품질 기사로 강제 quota를 채우지 않는다. 새 사실 없는 사건의 대표 반복을 피하고 정정/조건 변경은 Revision에 기록한다.

복잡한 장기 타임라인 UI는 후속이지만 기존 Event Update·감사 구조를 삭제하지 않는다.

## 8. 입력 안전·권한

외부 문서는 UNTRUSTED SOURCE DATA로 경계를 둔다. script/style/iframe/광고/메뉴 제거, 길이 제한, HTML escape, http/https 링크만 허용. 외부 문서의 도구 실행·키 요구·지시 변경 요청을 따르지 않는다.

내부 화면은 기존 로그인·조직 경계·allowed_tools·관리 권한을 서버/DB에서도 검증한다. AI 도구 링크는 실제 Tool Registry와 사용자 권한에 한정한다.

RLS·immutable trigger·기존 seed를 보존한다. Migration 16 재실행/초기화 금지. 새 migration은 서버 최댓값 확인 후 다음 번호다. 운영 DB 미확인 상태를 완료라고 표시하지 않는다.

## 9. 비용·Lock·복구

Idempotency: organization_id + briefing_date + profile + briefing_type. 공유 수집도 조직·날짜·source_config_version으로 잠근다. 원자적 Lock/lease로 동시·완료 Job 중복 유료 실행을 막는다.

성공한 URL/Event/분석 checkpoint를 재사용한다. source별 HTTP timeout과 최대 1회 추가 요청. 정규 생성의 **유료 단계 복구는 전체 Job 기준 최대 1회**이며 JSON repair/Profile recovery/08:10 복구를 겹쳐 무제한 호출하지 않는다.

요청 결과가 불명확하면 저장 상태·Provider response ID를 확인하고 즉시 중복 요청하지 않는다. Target/Soft/Hard 비용 한도를 일/월에 적용하고 요청 전 예약·후 사용량 정산한다.

모델·입출력/캐시/검색 토큰·tool/action·재시도·추정/실제 비용·실패 단계를 기록한다. 예산 부족 시 검증된 범위로 축약/지연 안내하며 과거 자료를 오늘 내용으로 바꾸지 않는다. 미승인 신규 유료 기능은 비활성이다.

## 10. Snapshot·정정·보관

게시 Snapshot immutable. 수정·재생성은 새 Revision/Snapshot, 최신 포인터와 외부 허용 상태는 별도다. 수동 잠금·관리자 미리보기/비교/게시/숨김/정정/재생성/공유 차단을 유지한다.

Audit: actor/time/action/organization/profile/Job/Revision/Snapshot/issue ID/게시·공유 변경. 비밀번호·키·민감 원문을 기록하지 않는다.

장기 보관: Snapshot/Revision/Source 근거·공유 메타/중요 감사. 기본 장기 미보관: 기사 전문/raw HTML/언론 사진/대용량 원시 시세. 임시 데이터 즉시 또는 1~7일 정리, 운영 로그 90일. 이력은 최근 30일 기본+날짜 검색.

## 11. 외부 Payload·공개 Gate

외부 DTO는 allowlist다. 내부 Snapshot 전체를 전송한 뒤 CSS로 숨기지 않는다.

허용: 날짜/발행·정정시각/승인 제목·짧은 요약/경제 해설·영향/보험 생활정보/허용된 지표 값·관측일·출처/원문/발신자 표시값.

제외: 상담 준비·내부 전략·개별 고객/계약·점수/확신도·도구/관리 경로·비용/로그·키/권한·raw 분석.

생성 external_share_allowed 기본 false. 조직 external_auto_share_enabled를 켜도 published + validation=ok + 분야/외부 QA + 표시 권한을 모두 통과한 Snapshot만 true. partial/required/rejected/hidden 차단. 후보 실패만으로 기존 정상본을 숨기지 않되 실제 기준일 표시.

NEWS/MARKET의 상담 not_applicable만으로 중립 고객 뉴스를 막지 않는다. 상담 문구와 외부 공개 정책은 별개다. 정상 승인 본문을 기본 공유 구성으로 제공해 매일 기사별 승인을 강제하지 않는다.

## 12. 발신자·공유 링크

링크 생성은 로그인 설계사만, 서버가 현재 세션·조직·외부 게시본 검증. 요청의 임의 user_id/name을 신뢰하지 않는다.

논리 필드: share_id/비추측 token_hash, organization_id, created_by_user_id, sender_display_name/job_title, briefing_date, Profile별 공개 날짜·판본 연결, active_revision_set, active/created_at/revoked_at, og/public_payload_version.

이름·직책은 생성 당시 등록값으로 보존한다. 직책은 접근 role이 아니다. 누락은 등록 안내, 추정/하드코딩 금지. 로그아웃·열람자·전달로 발신자가 바뀌지 않는다. 프로필 변경은 새 링크에 적용하고 기존 링크 변경은 새 공유판본으로 처리한다.

같은 날짜 정상 승인 정정판은 공개 포인터를 갱신하고 정정시각 표시, 이전판 이력 유지. 링크는 고객별 추적 URL이 아니다.

## 13. 비로그인 HTTP·OG·회수

얇은 공개 HTTPS Gateway에서 허용 DTO만 반환한다. Streamlit 로그인 세션·JS에 의존하지 않는다. 최소 비용 후보는 Cloudflare Worker, 실제 설정·배포는 별도다.

서버 HTML에 og:title/description/image/url. 이미지 기본 1200×630, 간결한 날짜·핵심 문장·이름 뒤 직책·작은 화랑. 고정 템플릿으로 만들어 매일 생성형 이미지 API를 호출하지 않는다.

본문·이미지·PDF 요청은 active/공유 허용/게시 상태를 서버에서 검사한다. Storage 원본은 비공개. Supabase anon에 내부 테이블 전체 읽기를 열지 않는다. 서비스 키는 서버만 사용하고 오류에도 노출하지 않는다.

캐시 키: share_id + date + revision_set + sender_version. 계정별 이름 혼선 차단. 정정 시 OG version URL 변경, CDN/cache 정책과 회수 Gate 검수.

본문 클릭 이후 회수/숨김은 차단해야 한다. 이미 전송한 메시지·카카오 미리보기 캐시·다운로드 PDF의 삭제까지 보장하지 않는다.

카카오 문구는 저장된 날짜·제목·이름/직책·링크의 템플릿. 복사/Web Share만 제공하며 자동 발송·수신자 목록·알림톡은 후속이다.

## 14. UI·PDF

짧은 제목·요약·출처·링크 기본 노출, 긴 해설/상담 펼치기. 모바일 360~430px, 본문 16~18px·행간 약 1.6·큰 글자. 200% 확대·키보드·포커스·44px 터치 목표·색상 외 상태 검수.

내부/고객 PDF 각각 상태 관리, 같은 Snapshot on-demand 렌더링, AI 재호출 없음. 캐시 키에 판본/변형/발신자 포함. 한글 폰트·여백·자연스러운 페이지·제목/본문 분리 방지·원문 하이퍼링크. 웹 성공과 PDF 실패를 분리한다.

## 15. 자체 검수·실제 확인

Codex: 기존 날짜 전량 탈락·보험 과잉 라우팅·점수 척도·검색 action 없음·정상 후보 누락 Fixture, 새 기간/수량/지표/근거, Lock/retry/비용/상태, RLS/외부 DTO/이름 위조/회수/캐시, 모바일/OG/PDF와 기존 WORKSPACE 회귀.

오프라인 Gate 후 사용자 예산 안에서 대표 실제 생성 1회 우선. 수정은 먼저 오프라인 재검수하고 영향을 받은 연결만 추가 확인한다. Shadow 관찰에 매일 사용자 진단을 요구하지 않는다.

현재 첨부 엔진 기준은 1.7.2-stage1이다. 상태는 코드 존재/오프라인 검증/운영 검증/미구현으로 구분해 기록한다.

