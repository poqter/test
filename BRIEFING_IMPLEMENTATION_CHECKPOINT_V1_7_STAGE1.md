# 화랑 브리핑 개발 진행 기준 · V1.7 Stage 1

- 작성일: 2026-10-06, Asia/Seoul
- 기준 통파일: `insurance_tools_Test.zip`, SHA-256 `4a1302456d9993a34dcd352ebecb189df980b45339288769850344346f72ca32`
- 단계: `1.7.1` 실환경 생성·SHADOW 저장 확인, 수집 품질 보완과 무료 출처 점검 구현 완료
- 엔진 버전: **`1.7.2-stage1`**
- 운영 서버/DB 배포: 제가 직접 실행하지 않음. 전달된 19:58 KST 진단에서 `1.7.1-stage1` 배포 일치·저장 완료 확인
- 이번 작업의 프로젝트 OpenAI API 호출 및 DB 쓰기: 0회
- 이번 작업은 정식 출시 완료본이나 최종 청사진 승인을 의미하지 않는다.

## 1. 이 문서의 적용 범위와 프로젝트 소스 관리

프로젝트 공용 소스의 **같은 이름 체크포인트 MD를 이 최신판으로 교체**한다. 기존 5개 브리핑 명세는 유지한다. 프로젝트에 첨부한 통파일을 최신 구현으로 맞추려면 `HWARANG_WORKSPACE_BRIEFING_STAGE1_FULL.zip`을 사용하고, 이전 통파일은 되돌리기용으로 보관한다. 구현된 항목은 이 문서의 최신 체크포인트를 우선 적용한다. 기존 파일의 `V1.6 구현 완료` 표현을 고객판·PDF·예약 생성까지 완료했다는 뜻으로 해석하지 않는다.

| 기존 명세의 규칙 | 이번 적용 기준 |
|---|---|
| CORE 수에 따라 LIGHT 2/3/5개 | CORE 수와 독립적으로 최대 7개, 화면 기본 5개와 더보기 2개 |
| 게시일 없는 검색 후보 즉시 제외 | 명시적 게시 메타데이터 확인 후 36h/96h 기준 적용. 여전히 미확인하면 제외 |
| Search 실행만으로 healthy 가능 | 실제 날짜·범위 통과 후보와 공식 확인 경로를 함께 판단 |
| 모델이 출력한 도구 코드 그대로 저장 | 현재 활성 등록 도구만 허용하고 최대 2개로 제한 |
| FAST BRIEF에 첫 이슈 요약 사용 | 표시 이슈 전체의 분야와 건수를 종합하는 기본 개요 |
| TODAY ACTION 그룹별 최대 4개 | 전체 최대 3개, 해당 이슈로 이동하는 연결 포함 |
| 모든 검색을 끝낸 뒤 한도 검사 | 매 요청 전에 검사하고 응답 직후 실제 검색 수를 반영 |
| 실패 진단에 오류 문구만 기록 | 요청별 응답 ID·검색 동작·사용량·부분 후보·중단 단계 보존 |
| 검색 없는 Lane에서 바로 재시도 | 기본 4개 Lane 먼저 실행, 남은 예산에서 최대 2회 재시도 |
| 반환된 모든 검색 기록을 완료 검색처럼 표시 | 완료·미확정·실패·상태 미상 구분, 한도에는 모두 보수적으로 반영 |
| RSS HTML 전체를 분류 입력으로 사용 | 화면에 읽히는 본문만 사용, GA는 독립 약어로 판별 |
| 직접 출처 실패 원인 없이 유료 재생성 | 무료 HTTP 점검 JSON으로 상태·게시일·설정 출처를 먼저 확인 |

최종 청사진의 남은 운영 결정은 공유 미리보기의 첫 출시 포함 여부, 고객판 자동 공개 정책, 개발/운영 예산 상한이다. 이 결정 전에는 고객판 자동 공개·정기 유료 호출을 활성화하지 않는다. 화면 시안은 선택한 간결한 카드와 등록 이름+업무 직책 기준을 유지한다.

## 2. 소스에서 확인한 현재 상태

1. 공통 Phase B/C, Supabase Repository/Runtime, WORKSPACE 브리핑 센터와 관리자 미리보기 경로가 존재한다.
2. 첨부 명세는 Migration 16의 적용·검증 완료를 기록하고 있다. 이번 작업에서 운영 DB를 직접 조회해 재확인한 것은 아니다.
3. 첨부 명세에 기록된 최근 실환경 결과는 세 Profile `CORE 0 / LIGHT 0 / coverage insufficient`이다.
4. 검색 URL에 제목·게시일이 빠졌거나 검색 결과가 홈페이지/오래된 기사인 경우 이를 복구·진단하는 단계가 부족했다.
5. MARKET 직접 출처/Provider, 예약 생성, 외부 고객판과 공유 미리보기, PDF는 추가 구현과 실환경 검증이 필요하다.

저장된 `web_discovery_v160_final.json`도 검토했다. 파일 내부 엔진 표기는 `briefing-engine-v1.5.2`이고 최신 서버 실행의 완전한 원본 응답은 아니다. 날짜가 있는 직접 수집 표본은 재생했지만 HTML 원문이 없는 검색 표본의 게시일 복구 성공률은 실환경에서 별도로 확인해야 한다.

### 2026-10-06 실제 실패 진단의 판정

전달된 `briefing_stage1_run_diagnostics(1).json`은 17:27 KST의 `1.7.0-stage1` 실행이며, `Shared Discovery hard limit exceeded`로 실패했다. 코드 흐름상 Phase B 검색을 마친 뒤 누적 검색 수 검사에서 중단되어 Phase C 기사 분석과 브리핑 본문 저장에는 진입하지 못했다. Job 상태 정리의 성공 여부는 이 작은 JSON으로 확인할 수 없다.

확인된 코드 결함은 **전체 검색 이후의 한도 검사**, **실패 전에 사용한 검색·토큰 기록 누락**, **실패 응답의 상세 진단 부족**이다. 전달된 JSON에는 요청별 검색 수·응답 ID·전체 배포 파일 해시가 없어, 실제 응답에서 검색이 여러 번 반환됐는지와 배포 코드가 모두 일치하는지를 구분할 수 없다. 실제 초과 횟수나 청구액을 추정해서 채우지 않는다.

이번 수정은 확인된 제어·기록 결함을 보완한다. 실제 서버의 오류가 완전히 해결됐다는 판정은 수정본의 응답과 저장 결과를 확인한 후 내린다.

### 2026-10-06 19:58 KST 최신 완료 진단

`briefing_stage1_run_diagnostics (1).json`은 `1.7.1-stage1`, `completed`이며 브리핑 Python 모듈 22개의 해시가 전달 패키지와 모두 일치한다. 파일명에 괄호 앞 공백이 없는 이전 실패 JSON과 구분한다.

| 항목 | 실제 서버 진단에서 확인한 결과 |
|---|---|
| 저장 | INSURANCE와 NEWS 모두 SHADOW draft 저장 완료 |
| 보험 | CORE 0 / LIGHT 0, 기존 판정 degraded |
| 국내 뉴스 | CORE 3 / LIGHT 5, degraded |
| 최신 유효 후보 | 8개, 모두 행정안전부 직접 출처 |
| 금융위원회 직접 출처 | failed, HTTP 상태와 설정 URL은 구버전 진단에 없어 원인 미확인 |
| Web 후보 | 원시 56개, 최신·범위 검사를 통과한 후보 0개 |
| 게시일 보완 | HTTP 24회, 날짜 확인 11개 모두 오래된 자료, 나머지 미확인·첨부·목록 등 |
| 검색 요청 | 기본 Lane 3개 실행, 마지막 종합·경제언론 Lane은 한도에 걸려 생략 |
| 반환된 검색 기록 | completed 3개 + searching 3개, 총 6개 |
| 토큰 | 입력 46,839 / 출력 7,584, 검색 입력이 39,227로 대부분 차지 |

이는 생성·저장 흐름의 성공이며 종합 브리핑 품질 확보나 출시 승인은 아니다. 검색 기록 6개를 완료 검색 6회 또는 확정 청구 횟수로 해석하지 않는다. 미확정 기록의 청구 여부는 이 JSON으로 판단할 수 없어 한도에는 계속 포함한다.

보험 분석에 행정안전부 사건 2개가 들어갔지만 진단의 본문은 700자 표본이라 정확한 분류 트리거는 복원할 수 없다. 코드에서 확인한 HTML 속성·스크립트와 GA 부분 문자열의 오탐 경로를 수정하고 다음 진단에 실제 일치 표현을 추가했다. 사건 요약과 점수의 완전한 분석 출력은 이번 JSON에 없으므로 기사 해설의 정확성까지 검수했다고 주장하지 않는다.

## 3. 이번에 구현하고 검증한 항목

### 게시일·원문 확인

- 원본 `published_at`이 확인된 경우 그대로 사용한다.
- 미확인 경우 HTML의 명시적 게시 메타데이터, 기사 JSON-LD `datePublished`, 게시일로 표시된 `<time>`을 확인한다.
- 수정일, 수집일, 홈페이지 갱신일, 일반 본문 날짜, 상대 날짜를 게시일로 대체하지 않는다.
- 한국 출처의 시간대 없는 명시적 날짜는 KST로 해석하고, 시간대가 불명확한 해외 날짜는 제외한다. 날짜만 있는 자료는 해당 지역 00:00으로 보수적으로 계산한다.
- HTTP 메타데이터 확인은 한 실행 기준 최대 24요청, 기본 시간 예산 35초, 요청 timeout 최대 5초, 원문 최대 512KB, 리다이렉트 최대 2회로 제한한다. DNS/네트워크 지연 때문에 전체 경과 시간을 정확히 35초로 보장하는 설정은 아니다.
- 같은 프로세스에서 확인 성공은 6시간, 실패는 20분 캐시한다. 모델 호출·Search Action을 추가하지 않는다.
- HTTP/HTTPS와 공개 네트워크 목적지만 허용하고, 리다이렉트 목적지를 다시 검사한다. 다른 발행기관으로 이동하면 공식 자료의 날짜로 오인하지 않고 제외한다.
- HTML 전체나 기사 전문을 DB에 저장하지 않는다.

### 검색·선별·저장

- 4개 검색 Lane에 기준 시각과 최근 36/96시간 범위, 사전 정의한 기관·언론 도메인을 제공한다.
- KST 절대 날짜와 날짜 검색어를 제공하고, 한 번의 도구 호출·하나의 쿼리·첫 검색 결과의 기사 원문만 요청한다. 이는 프롬프트 개선이며 실환경 최신 기사 확보나 한도 준수를 보장하는 장치는 아니다.
- 요청마다 `max_tool_calls=1`, 병렬 Tool 호출 비활성화를 지정한다.
- 요청 직전 누적 검색 수와 API 요청 수를 검사한다. Discovery API 요청 자체는 실행당 최대 **6회**로 줄였다.
- 기본 4개 Lane을 먼저 실행하고, 검색이 없었던 Lane만 남은 예산 안에서 Lane당 1회, 전체 최대 2회 재시도한다. HTTP 실패·불완전 응답·한도 초과·DB 사용량 저장 실패에서는 자동 재시도하지 않는다.
- 응답마다 반환된 검색 기록·Tool 수·토큰·응답 ID를 즉시 기록한다. 완료·미확정·실패·상태 미상과 실제 쿼리를 구분해 기록한다. 모든 검색 기록을 한도에 포함하며 6개 초과 시 실제 값을 보존하고 추가 호출·분석을 중단한다. 미확정 Tool 기록은 수집 후보의 근거로 사용하지 않는다.
- RSS/Atom 본문은 HTML 속성·스크립트·스타일을 제거하고 최대 12,000자로 제한한다. GA는 영문 단어 내부에서 일치하지 않도록 하며 보험 분류 근거 표현을 기록한다.
- 다른 Profile에서 넘어온 후보만으로 보험 수집 경로가 확보됐다고 판정하지 않는다. 해당 Profile을 목표로 수집한 날짜 유효 후보 또는 공식 확인 경로를 함께 판단한다.
- 날짜 확인이 필요한 명백한 목록·PDF·다운로드 URL은 HTTP 요청 전에 제외해 24회 한도를 기사 원문에 우선 사용한다. URL의 날짜를 실제 게시일로 추정하지 않는다.
- 정확히 한도에 도달하면 남은 Lane은 실행하지 않고 이유를 기록한다. 일부만 수집한 결과는 기존 날짜·출처·coverage 기준을 그대로 적용하며 이번 테스트는 SHADOW 상태로만 저장한다.
- API 사용량 저장 자체가 실패하면 추가 유료 요청을 멈춘다. 응답이 없는 실패 요청은 사용량 미확인으로 기록하며 0원 실행으로 취급하지 않는다.
- URL만 있는 Search Source도 보존하고, 인용 제목 또는 HTML 메타데이터와 병합한다.
- 공식 출처 여부는 모델/기사의 자기소개 대신 서버 출처 목록으로 정한다.
- CORE 상한 INSURANCE 8 / MARKET 5 / NEWS 7은 유지한다. 대표 1개 강조와 CORE 1개 제한을 혼동하지 않는다.
- 내부 관련 뉴스 최대 7개. 목표를 채우기 위해 낮은 점수나 오래된 자료를 올리지 않는다.
- 표시 상한 전의 적격 분석 풀을 내부 Snapshot JSON에 보존한다. 추후 고객판 국내 뉴스 최대 10개 선정에 사용한다.
- CORE 표시 초과 항목은 원래 분류를 보존한다.
- 미등록·비활성 도구 코드를 제거한다. 조직/사용자 권한과 실제 도구 이동 버튼은 기존 shell Gate를 적용하는 다음 단계에서 완성한다.
- 모델 결과의 JSON 스키마, 이벤트 키 일치, 중복 키, 카테고리, 필수 제목·요약을 검사한다. 부적합 결과를 정상 콘텐츠처럼 저장하지 않는다.
- 요청하지 않은 Profile의 분석 호출을 실행하지 않는다.
- Job 생성 도중 실패하면 이미 만든 Job을 실패 상태로 정리해 잠금 잔류를 줄인다. 기존 DB의 active Job 유일성 제약은 유지한다.

### 화면·진단

- 대표 핵심 카드 기본 펼침, 나머지 핵심 보존.
- 관련 뉴스 제목·요약·출처·게시 시각·원문 링크, 기본 5개와 더보기 2개.
- TODAY ACTION에서 실제 연결 이슈로 이동.
- 서버 시간대와 관계없이 KST 표시.
- 수집 불충분과 중요한 뉴스 없음의 의미를 구분하고 공개를 차단.
- 관리자에게만 생성 진단과 전체 실행 진단 JSON 다운로드 제공.
- 관리자 생성 전 서버 설정 점검과 1회 유료 실행 확인 체크 제공.
- **개발 검증 버전 `1.7.2-stage1`**을 표시하고, 브리핑 모듈 파일 해시를 수정 패키지의 `STAGE1_CHANGED_FILES.json`과 비교한다. 일부 파일 누락·구버전 혼합이면 유료 생성 버튼과 Runtime 호출을 차단한다.
- 관리자에게 **배포 진단 다운로드 · API 호출 없음**을 제공한다. 비밀 키 값·인증 헤더는 포함하지 않는다.
- **직접 출처 점검 · 유료 API 없음**은 명시적으로 눌렀을 때만 공개 RSS/Atom에 접속한다. OpenAI 호출과 DB 쓰기는 없고 rerun에도 자동 재실행하지 않는다. 설정 출처·최종 주소·HTTP 상태·실패 종류·게시일·최신 후보 수를 JSON으로 제공한다. 민감한 URL 쿼리 값과 예외 본문은 내보내지 않는다.
- 직접 출처는 공개 목적지를 검사하고 리다이렉트를 매번 재검사한다. 다른 발행기관으로 이동하면 중단한다. 출처당 리다이렉트 최대 2회·응답 최대 2MB·요청 timeout 최대 10초이며 HTML 오류 페이지와 XML 선언을 정상 피드로 취급하지 않는다.
- degraded에는 일부 출처만 확보됐다는 경고를 표시한다. 표시 이슈가 하나도 없는 과거 degraded draft는 화면에서 공개하지 못하게 한다.
- 성공과 실패 진단에 동일한 엔진/진단 스키마 버전을 포함한다. 실패 시 요청별 사용량·Tool 동작 ID/종류/상태·후보 표본·중단 단계·실패한 Job 정리를 보존한다.
- 분석 응답도 검증 전에 사용량을 기록한다. 구조화 출력이 잘못되면 요청 이벤트 키·검증 경로·제한된 출력 표본을 관리자 진단에 남겨 오프라인 검토에 사용한다.
- 부분 진단은 기존 Job `metadata`에 저장한다. 기사 전문이나 API 키는 저장하지 않으며 DB 스키마·SQL은 변경하지 않는다.
- 이번 관리자 테스트 생성은 DB Profile 모드와 관계없이 SHADOW로 저장한다. 기존 공개본의 포인터를 자동 변경하지 않는다.
- MARKET 힌트를 가진 직접 출처가 없으면 이번 관리자 실행은 INSURANCE·NEWS만 생성한다. MARKET 자료가 연결되면 세 Profile을 생성하되 MARKET 데이터 제공·지연·종가 표기 정책은 별도로 검증해야 한다.

## 4. 검증 결과와 한계

| 검증 | 결과 |
|---|---|
| 수정 전 기존 테스트 | 76개 통과, 하위 검사 61개 통과 |
| 최초 Stage 1 테스트 | 122개 통과, 하위 검사 61개 통과 |
| 이번 수정 후 전체 테스트 | **169개 통과, 하위 검사 61개 통과** |
| 4개 기본 검색·재시도 순서·요청 6회 제한 | 자동 검증 통과 |
| 반환된 검색 기록 6개 도달/7개 초과 | 다음 요청 차단·실제 초과 값 보존·분석 중단 확인 |
| completed + searching 혼합 응답 | 3+3 구분, 한도 6 유지, 마지막 Lane 생략, 미확정 출처 사용 안 함 확인 |
| 무료 직접 출처 점검 | 성공·503·XML 오류·HTML 오류·빈 Atom·크기·공개 리다이렉트·민감 값 제거 확인 |
| 본문·GA 분류와 보험 수집 경로 | HTML 오탐 제거·독립 약어 인식·NEWS만으로 보험 Coverage 오판 방지 확인 |
| 중간 HTTP/불완전 응답·사용량 저장 실패 | 이전 응답 보존·추가 호출 중단 확인 |
| 부분 배포·잘못된 분석 JSON/스키마·Job 정리 실패 | 유료 생성 차단·세부 실패 기록 확인 |
| 게시일 추출·수정일 배제·캐시·예산·위험 URL·리다이렉트 | 자동 검증 통과 |
| CORE 독립 관련 뉴스 7개·상한 전 후보 보존 | 자동 검증 통과 |
| 수집 불충분·MARKET 교차 뉴스만으로 건강도 오판 방지 | 자동 검증 통과 |
| 등록 도구 검증·모델 출력 계약·Job 실패 정리 | 자동 검증 통과 |
| Streamlit 컴포넌트 실행 | 기존 화면 동작과 실패 진단 다운로드, 배포 오류 시 유료 버튼 차단, rerun 후 중복 생성 없음 확인 |
| 이전 실행 표본 재생 | API 0회 / DB 0회, 날짜 확인된 16개 후보와 16개 사건 유지 |
| 최신 완료 진단의 메타데이터 재생 | API 0회 / DB 0회, 8개 후보·8개 사건·완료 3+미확정 3 유지 |
| 이전 작은 실패 JSON | 상세 응답 없음으로 실제 원인 재현 불가. 누락된 검색 수는 미확인 값으로 유지 |
| 새로운 상세 실패 진단의 모의 재생 | 저장한 요청 메타데이터에서 초과/중단을 오프라인 재현 |
| Python 컴파일·diff 공백 검사 | 통과 |

테스트 중 HTTP 요청을 강제로 차단했다. 검증 환경은 Python 3.12, Streamlit 1.64.0, requests 2.34.2, jsonschema 4.26.0이다. 앱의 requirements/constraints는 변경하지 않았다.

Streamlit 테스트는 실제 컴포넌트와 rerun 흐름을 실행한 검사다. 브라우저 픽셀, 실제 모바일, 로그인 계정, Kakao 미리보기, 운영 DB, 실제 API의 출력 품질을 직접 확인했다는 뜻은 아니다.

`STAGE1_LATEST_DIAGNOSTIC_REPLAY_RESULT.json`은 후보·요청 메타데이터 재생 결과다. HTML 원문과 전체 RSS 본문, 실제 분석 응답이 없으므로 게시일 복구의 11개 결과나 CORE 3 / LIGHT 5를 다시 생성한 검사가 아니다. 700자 본문 표본에서는 보험 후보 0개이며 실제 전체 본문에서 같은 결과라고 단정하지 않는다.

## 5. 병선님 필수 확인 — 이번에는 무료 직접 출처 점검

### 적용

1. 현재 테스트 서버 버전을 보관한다.
2. 최신 `HWARANG_BRIEFING_STAGE1_PATCH.zip`을 기존 저장소 **루트에 덮어쓰기**한다. 원본 또는 이전 Stage 1 모두에 적용 가능한 누적 패치다. `app.py`와 `modules/`가 있는 위치이며, **새 모듈과 `STAGE1_CHANGED_FILES.json`도 반드시 포함**한다.
3. 새 폴더에서 통째로 검토할 경우 `HWARANG_WORKSPACE_BRIEFING_STAGE1_FULL.zip`을 사용한다. 두 ZIP을 차례로 적용할 필요는 없다.
4. 기존 GitHub/Streamlit 배포 절차로 테스트 앱에 적용하고 앱을 다시 시작한다. 실행 진입점은 기존 `app.py` 그대로다.
5. **SQL 실행 없음. Migration 16 수정·재실행 없음.** 기존 로그인/조직/크레딧 구조와 배포 Secret을 유지한다. 추가 서비스 가입도 없다.

### 무료 점검 한 번

1. 테스트 앱에서 콘텐츠 관리자 계정으로 로그인한다.
2. 브리핑 센터 → 콘텐츠 관리에 **개발 검증 버전 `1.7.2-stage1`**이 표시되는지 확인한다. 배포 파일 불일치가 있으면 **배포 진단 다운로드 · API 호출 없음**으로 받은 `briefing_stage1_deployment_diagnostics.json`을 전달한다.
3. **직접 출처 점검 · 유료 API 없음**을 한 번 누른다. 유료 실행 확인 체크나 ‘오늘 브리핑 생성’은 필요 없다.
4. **직접 출처 점검 JSON 다운로드**로 `briefing_direct_source_diagnostics.json`을 받아 전달한다. 성공·실패 어느 경우든 같은 JSON을 전달하면 된다. Secret 값은 채팅에 보내지 않는다.
5. 무료 점검 결과에서 금융위원회 실패 원인을 제가 확인한 뒤 출처 설정 또는 수집 코드를 보완한다. 이번 단계에서 같은 유료 브리핑을 반복 생성하지 않는다.

이번 사용자 확인이 필요한 이유는 최신 JSON에도 실패한 금융위원회 출처의 설정 주소·HTTP 상태·오류 종류가 없고, 제가 병선님 서버의 네트워크와 Secret 설정을 직접 읽을 수 없기 때문이다. 계정/실서버 확인은 병선님이 맡고 반복 코드 검수는 제가 맡기로 한 원칙에 따른 최소 관문이다. 결과를 받으면 추가 유료 실행 없이 확인 가능한 수정부터 진행한다.

금융위원회 공식 RSS 안내의 보도자료 주소는 `http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111`이다. 공식 안내에 등록됐다는 사실과 실제 동작 여부는 별개다. 이번 진단에는 현재 설정 URL이 없어 주소 오류라고 단정하거나 이 주소로 Secret을 임의 변경하지 않는다. 참고: [금융위원회 RSS 안내](https://www.fsc.go.kr/ut060101).

이번 무료 점검은 공개 출처의 HTTP 접속만 하며 프로젝트 OpenAI API 호출·DB 쓰기는 0회다. 등록 모델·출력 토큰 상한·검색 한도·유료 Provider 설정은 늘리지 않았다.

이후 새 유료 생성이 필요하면 이유와 최소 범위를 먼저 설명한다. 기본 Shared Search 목표는 4개 Lane, 반환 검색 기록 한도는 완료·미확정을 합쳐 6개다. Discovery API 요청은 전체 최대 6회, 분석은 요청된 Profile당 최대 1회이며 MARKET이 없으면 최대 2회다. 반환 Tool 상태로 실제 청구를 추정하지 않는다. 현재 JSON의 토큰 수는 관측 사용량이며 금액은 프로젝트 사용 내역으로 확인한다. 월 예산 자동 제어·운영 예약은 후속 단계에서 승인된 예산으로 구현한다.

## 6. 정식 서비스까지의 진행 순서

| 단계 | 제가 담당할 작업 | 병선님 필수 관문 | 현재 상태 |
|---|---|---|---|
| 1 데이터 선별 정상화 | 날짜 확인, 검색 범위, 건강도, 상한, 회귀 검사, 진단 | 수정본 배포와 무료 직접 출처 점검 | 생성·저장 성공 확인, 출처 품질 보완 검수 완료, 금융위 실서버 점검 대기 |
| 2 내부 업무 화면 완성 | 상담 준비, 상태별 복사, 실제 권한 기반 도구 이동, 팀 1분 브리핑, 어제 이후 변화 | 완성 화면의 상담 표현·사용감 확인을 묶어서 진행 | 예정 |
| 3 MARKET·운영 기반 | Provider/공식 직접 출처 검증, 예약 생성, 예산 예약·잠금·재시도·장애 복구 | 필요한 계정/유료 가입과 운영 예산 확정 | 예정 |
| 4 고객판·공유·PDF | 경제 5~7·국내 7~10, 쉬운 해설·영향·평가, 모바일 읽기, 이름+직책의 간결한 미리보기, 내부/외부 PDF | 실제 휴대폰·메신저·공유 링크·PDF 묶음 확인 | 예정 |
| 5 비공개 관찰 | 3~5영업일 생성 관찰, 비용·출처·품질·정정·실패 기록 검수 | 초기 공개본의 내용과 공개 정책 확인 | 예정 |
| 6 정식 출시 | 출시 점검, 정상본 복구 경로, 모니터링, 적용 안내 | 최종 출시 승인 | 예정 |

대표 핵심 1개, 관련 뉴스 5~7개, 고객 경제/금융 5~7개, 국내 주요 뉴스 7~10개는 그대로 유지한다. 고객판의 경제 기사는 사실 → 쉬운 해설 → 영향 → 조건부 평가 → 원문으로 구성한다. 고객판은 승인된 같은 날짜 MARKET+NEWS와 허용된 Public DTO를 사용하며 내부 영업전략·점수·계정 식별자를 공개하지 않는다.

관련 뉴스/고객판은 품질을 통과한 실제 기사 수만 표시한다. 다양한 출처·주제는 부드럽게 조정하며 고객판을 채우기 위한 별도 고비용 수집을 기본으로 추가하지 않는다.

## 7. 업무 분담과 방향 변경 원칙

- 제가 처리: 코드/문서 대조, 경계값, 스키마, 중복, 날짜, 권한 Gate, fixture 재생, 실패 처리, 회귀 검사, PDF 일관성 등 반복 검증과 수정.
- 병선님이 처리: 실제 계정/서버 연결, 요금 발생 실행과 새 유료 가입, 실제 기기/메신저에서의 사용감, 보험 상담 표현의 현업 판단, 최종 출시 승인.
- 제가 운영 서버에 접근할 수 있는 환경이 제공되면 그 범위에서 적용·읽기 검증을 이어갈 수 있다. 이번 작업은 첨부 ZIP의 수정본 제작까지다.
- 문제 재현에는 저장 결과를 우선 사용한다. 동일 비용 테스트를 원인 설명 없이 반복 요청하지 않는다.
- 일반 버그는 승인 범위 안에서 수정하고, 기능 묶음이 완료될 때 적용 파일을 전달한다.
- 기능 범위·공개 정책·DB 구조·운영 비용이 바뀌면 이유, 변경 전후, 정확한 추가/교체 파일명, 적용 순서, 재검증 항목, 되돌리기를 함께 안내한다.
- 새 DB 변경이 필요하면 실제 다음 미사용 Migration 번호를 확인한다. 16을 덮어쓰지 않고 17로 임의 단정하지 않는다.

## 8. 이번 버전 되돌리기

통파일과 변경파일은 새 테스트 Snapshot을 저장할 수 있지만 기존 공개 Snapshot을 삭제하지 않는다. 코드 문제가 확인되면 보관한 테스트 앱 버전으로 되돌린다. 이번 적용에 DB 스키마 변경은 없어 역방향 SQL은 필요 없다. 새 SHADOW 기록은 감사용으로 보존하고, 삭제가 필요한 경우에는 별도 대상으로 확인한다.

다음 대화에는 **직접 출처 점검 JSON**을 전달하면 된다. 기존 5개 명세는 유지하고 같은 이름 체크포인트 MD만 최신판으로 교체한다. 최종 개발 범위와 고객판 설계 방향은 바뀌지 않았으며 이번 수정은 Stage 1 수집 품질과 진단 보완이다.

## 2026-10-07 WORKSPACE Performance Patch

- WORKSPACE build: `hwarang-2026.10.07-platform-v63-performance`
- Briefing engine version remains **`1.7.2-stage1`**; Event selection, Source policy, cost controls, Snapshot/Revision semantics and Migration 16 are unchanged.
- Normal-user telemetry is reduced to successful WORKSPACE login only. Menu/page-open, heartbeat and logout activity writes are no longer emitted by the WORKSPACE shell.
- A new corrective `Migration 17` preserves `LOGIN_SUCCESS` + `profiles.last_login_at`, stops creating WORKSPACE presence rows, and adds a one-call periodic auth-context RPC. Migration 16 is not edited or rerun.
- Navigation reuses the already calculated allowed-tool list and uses widget callbacks to avoid avoidable second reruns.
- External ACADEMY/CALCULATOR launch tickets retain the existing one-click/new-tab behavior but reuse a still-valid launch URL for 45 seconds instead of reissuing tickets on ordinary reruns.
- Briefing home/hub/history reads now use batched summary queries; the selected Profile alone loads its full Bundle; Event Timeline reads are batched.
- Administrator dashboard read-only queries use short session TTLs; main AI summaries use the daily aggregate view and detailed raw usage is opt-in.
- PDF/Excel/static content paths reuse unchanged-input results and move expensive PDF/Excel imports closer to the actual export path where safe.
- Artificial 250 ms delay in the short-pay comparison result path was removed.
- Source/package verification performed in the build environment: Python compile-all passed; non-Streamlit regression suite **142 passed + 61 subtests passed**; targeted performance/login tests **12 passed**. Three Streamlit AppTest modules could not be collected in this build container because the container does not include the `streamlit` package. This is not an actual deployed-page/browser performance measurement.
- Operational DB/server application is **not** claimed complete. Apply `17_Workspace_Performance_Login_Only.sql` once together with the code deployment, run `POST_MIGRATION17_VERIFY.sql`, then restart and smoke-test login/navigation/admin/briefing on the test server.
