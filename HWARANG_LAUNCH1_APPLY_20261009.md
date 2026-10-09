# 화랑 WORKSPACE LAUNCH1 적용 안내

2026-10-09 · 플랫폼 `hwarang-2026.10.09-platform-v65-launch1` · 브리핑 엔진 `1.10.0-launch`.

**이 통파일 한 개에 AUTHFIX1·REAUDIT2와 재검수 보고서 6번의 추가 구현을 모두 포함했습니다. 이전 패치를 따로 적용하지 않습니다. 현재 운영 사이트에 반영한 상태는 아닙니다.**

## 1. 적용 순서 — 처음 한 번

1. 기존 소스와 DB 설정을 백업하고, 통파일의 압축을 풀어 기존 저장소 경로에 반영합니다. ZIP 자체를 저장소에 올리는 방식은 아닙니다. `app.py`, `modules`, `.github`, `requirements.txt`, `constraints.txt`, `STAGE1_CHANGED_FILES.json`과 신규 파일을 함께 반영합니다. 앱 재시작 뒤 위 버전이 보이는지 확인합니다. 기존 Secret과 고객·계정 데이터는 유지합니다.
2. Supabase에 기존 Migration 19·20이 적용돼 있는지 확인합니다. 미적용이면 순서대로 적용하고, 신규 `supabase/migrations/21_Briefing_Launch_Readiness.sql`을 추가 실행합니다. 기존 Migration 16은 초기화 스크립트이므로 다시 실행하지 않습니다. 21은 조직 운영 정책·영업일·비공개 공유 파일·서버 공유 검수를 추가합니다.
3. 아래 고객 읽기 페이지를 한 번 배포하고 `BRIEFING_PUBLIC_BASE_URL`을 Streamlit Secret에 추가합니다. 경제 지표는 3번의 공급원 설정을 따릅니다. 지표가 연결되지 않아도 종합·보험 영역은 독립적으로 검수할 수 있습니다.
4. GitHub Actions에서 **HWARANG Daily Briefing → Run workflow → action `check`**를 먼저 실행합니다. 이 작업은 OpenAI 호출 0회이며, 설정·피드·최근 실행 기록을 확인합니다. `briefing-operation-status.json`이 결과입니다. 이 단계의 실패 원인 검토와 버전·뉴스 출처·날짜·권한·PDF 검수는 Codex에게 맡기면 됩니다.

현재 GitHub 연결은 코드 쓰기에 403을 반환했습니다. 사용자 계정으로 코드 반영하거나 연결의 쓰기 권한을 수정하는 단계가 필요합니다. 이번 작업에서 커밋·PR·운영 배포를 완료한 것은 아닙니다.

## 2. 고객 읽기 페이지 — 무료 Worker 구성

Streamlit 링크만으로는 카카오톡이 읽는 첫 HTTP 응답에 개인별 OG를 보장할 수 없습니다. Supabase 기본 주소의 Edge Function도 HTML을 일반 텍스트로 바꾸므로, 이번 구현은 **Cloudflare Worker에서 HTML을 반환하고 기존 Supabase를 읽는 구성**입니다. 기능 명세의 HTTP 공유 요구는 그대로이며 배포 방식을 확정한 것입니다.

- Cloudflare의 Workers & Pages에서 `hwarang-briefing-reader` Worker를 만듭니다. Free 플랜과 `workers.dev` 주소를 사용합니다. 별도 도메인·KV·D1·R2·Workers AI는 필요하지 않습니다.
- 코드 편집기에 `public_reader/worker.js` 전체를 넣습니다. 이 파일에는 필요한 코드가 모두 있고 npm 설치가 필요하지 않습니다. CLI를 사용하는 경우 `public_reader/wrangler.toml`도 제공합니다.
- Worker의 Settings → Variables and Secrets에 `SUPABASE_URL`과 **`SUPABASE_SERVICE_ROLE_KEY`를 Secret 유형**으로 등록합니다. 두 번째 값은 해당 Supabase의 서버용 secret 또는 service_role 키입니다. `sb_secret_*`와 기존 JWT형 키를 모두 지원합니다. 코드에 키를 적지 않습니다.
- 생성된 Worker의 실제 HTTPS 주소를 Streamlit의 `BRIEFING_PUBLIC_BASE_URL`에 넣습니다. 예시 주소 대신 자신의 배포 주소를 사용합니다. Cloudflare Access 로그인 제한은 고객 읽기 주소에 걸지 않습니다.
- 브리핑 운영 관리의 “고객 공유 페이지 연결 확인”으로 설정을 확인합니다. 실제 비로그인 본문·OG와 PDF는 정상 공개본으로 공유 링크를 만든 뒤 검수합니다. 연결 확인만으로 본문 검수 통과를 뜻하지는 않습니다.

공유 링크의 본문·미리보기·PDF는 모두 현재 판본/공개 상태/조직 정책/만료/회수/공유자 활성 여부를 서버에서 확인합니다. 이름과 직함은 링크 생성 시 등록된 값을 고정합니다. 문구 정정은 새 판본을 저장하고 같은 링크의 본문·PDF를 갱신합니다. 이미 보낸 카카오톡 미리보기 캐시와 이미 내려받은 PDF를 회수할 수는 없습니다.

Cloudflare Free의 현재 한도는 계정당 하루 100,000 요청입니다. 한도 안에서 Worker 요금이 없으며 초과 시 오류가 발생합니다. Supabase 저장·전송과 기존 GitHub Actions의 사용 한도는 각 계정 요금제에 따릅니다. 유료 플랜으로 자동 변경하지 않습니다.

## 3. 경제 지표 — 실제 공급원과 이용 권한 연결

구현한 어댑터는 FMP 지수/일간 환율 + 미국 재무부 10년 명목 CMT, 또는 FMP 지수 + 한국은행 ECOS 환율 + 재무부 CMT입니다. 기존 승인된 JSON/FILE/URL 경로도 유지합니다.

| 설정 | 넣을 내용 | 위치 |
|---|---|---|
| `BRIEFING_MARKET_PROVIDER` | `fmp_treasury` 또는 `fmp_ecos_treasury` | Streamlit Secret·GitHub Actions Variable |
| `FMP_API_KEY` | 실제 가입한 공급원의 키 | 양쪽 Secret |
| `ECOS_API_KEY` | ECOS 환율을 선택한 경우 | 양쪽 Secret |
| `BRIEFING_MARKET_EXTERNAL_ALLOWED` | 고객 웹/PDF 표시를 허용하는 계약을 확인한 뒤 `true` | 양쪽 설정 |
| `BRIEFING_MARKET_LICENSE_REFERENCE` | 확인한 계약·허용 근거의 식별 문구 | 양쪽 설정 |

FMP 어댑터는 실제 `^KS11`, `^KQ11`, `^GSPC`, `^IXIC` 지원을 조회해 확인합니다. 해당 플랜이 코스피·코스닥을 제공하지 않으면 없는 값을 만들거나 ETF로 대신하지 않습니다. **API 키 보유만으로 6개 지수 지원·고객 표시 계약이 확보되는 것은 아닙니다.** 공급원 플랜의 지원/아침 가용 시각/고객 웹·PDF 표시/총 견적을 확인해 신청해야 합니다. 이번 작업에서 새 유료 서비스에 가입하지 않았습니다.

ECOS 환율 정의는 `731Y001/D/0000001`의 일간 원/달러 매매기준율입니다. FMP 환율과 다른 기준이므로 두 시계열의 변화량을 섞지 않습니다. 재무부 값은 일간 명목 10년 CMT이며 거래소 종가로 표시하지 않습니다. 내부 코드 `USDKRW`는 명세의 원/달러 `USD_KRW`에 해당합니다.

6개 실제 값·단위·최근 관측일·같은 기준의 이전 값을 먼저 확인합니다. 미설정/수신 실패/누락이면 경제판의 OpenAI 호출 전에 중단합니다. 고객용 지표에는 이전 관측일·Provider·정의·표시 허용 근거까지 있어야 합니다. 표시 권한이 없는 정상 지표는 직원 화면에서만 볼 수 있습니다.

`BRIEFING_MARKET_OBSERVATIONS_JSON/FILE/URL`을 이미 쓰면 이 입력이 어댑터보다 우선합니다. 테스트용 가상 값을 운영 Secret으로 넣지 않습니다. `docs/briefing/qa`의 숫자는 화면 검수용입니다.

## 4. 유료 검수 1회와 정식 운영 설정

사용자가 허용한 **유료 검수 1회는 아직 사용하지 않았습니다.** 기존 API를 이용하는 한 번의 브리핑 생성 검수 범위로 기록했습니다. 새 구독·계약 체결이나 유료 반복 재시도 권한으로 확대하지 않습니다.

- 적용 중에는 조직 설정의 **“매일 자동 생성”을 꺼 둡니다.** 신규 정책의 기본값도 꺼짐입니다. 교육 AI를 켜 두어도 브리핑 예약 생성은 별도로 멈출 수 있습니다.
- 무료 연결 검사에서 버전·DB·피드가 확인된 뒤, 필요한 영역의 “오늘 브리핑 생성” 한 번으로 검수합니다. 한 번의 생성 안에는 뉴스 수집과 분석에 필요한 여러 API 요청이 포함될 수 있습니다. 실패하면 진단을 확인하며 유료 생성 버튼을 반복해서 누르지 않습니다.
- 정식 운영을 결정하면 최고관리자가 “매일 자동 생성”, “관찰 3영업일 이후 자동 공개”, “검증된 고객용 본문 공유 허용”을 설정합니다. 생성과 공개 설정을 구분했으며 매일 수동 승인할 필요는 없습니다.
- 자동 공개는 영역별로 검증된 3영업일을 관찰한 뒤 가능합니다. 한국 공휴일은 관찰 일수에서 제외하되 휴일 뉴스 수집 자체는 중단하지 않습니다. 최초 정상 자료는 관리자가 검수 후 수동 공개할 수 있습니다.
- 전체 AI OFF는 브리핑의 유료 요청도 막습니다. 저장된 자료 읽기·공유·PDF에는 OpenAI 호출이 없습니다. 사용량은 브리핑과 교육 AI를 구분해 표시합니다. 단가 미설정·응답 미확인은 0원으로 단정하지 않습니다.

현재 뉴스 기본 피드는 한국경제 5개 영역, 매일경제 2개 영역, 보험저널입니다. 기존 기관 RSS 설정은 함께 사용합니다. 뉴스가 충분하면 해당 웹 검색을 생략하고, 부족할 때만 기존 검색을 보조로 사용합니다. 발행일 없는 목록·과거/마감 이후 기사·중복은 정상 기사로 채우지 않습니다.

예약 목표는 KST 06:30 준비 → 07:00 경제 수집 → 07:30 경제 공개/종합·보험 수집 → 08:00 종합·보험 공개 → 08:10 최대 한 번 복구입니다. GitHub Actions 예약은 지연될 수 있습니다. Keep Alive 성공을 브리핑 예약 성공으로 계산하지 않습니다.

## 5. 본인이 반드시 확인할 내용 — 한 번에 묶기

1. **설정·요금:** 소스/SQL/공유 페이지를 반영하고, 지표 공급원의 지원·고객 표시 조건·요금을 결정합니다. 기존 OpenAI 키는 그대로 사용합니다. 운영 승인 전 자동 생성은 꺼 둡니다.
2. **본인 계정:** 실제 현재/새 비밀번호는 본인이 입력합니다. 변경 후 재로그인, 초기화 메일 실제 수신과 링크로 재설정 후 재로그인을 한 번 확인합니다. Supabase Auth Site URL/Redirect URL은 `https://hwarang-workspace.streamlit.app/`입니다. Reset Password 메일 링크는 아래 템플릿을 사용합니다.
3. **실제 휴대폰:** 정상 공개본 링크를 카카오톡으로 열어 이름+실제 직함, 비로그인 본문·큰 글자·원문 링크·PDF를 확인합니다. 화면/출처/정정/차단 등의 반복 검수는 Codex가 진행합니다. 마지막으로 정식 고객 제공 여부를 결정합니다.

```html
<a href="https://hwarang-workspace.streamlit.app/?recovery_token={{ .TokenHash }}">비밀번호 재설정</a>
```

SMTP 서버 발송 설정·발신자 허용·실제 수신은 소스 테스트만으로 확인할 수 없습니다. 발송 실패 시 계정 서버의 오류 코드와 Auth 로그를 확인합니다. 비밀번호나 API 키를 대화에 보낼 필요는 없습니다.

## 6. 명세 파일과 다음 검수

기존 5개 명세를 삭제하지 않습니다. `docs/briefing/specifications`에 업로드한 V1.8 설계 기준을 원문 그대로 포함했고, `docs/briefing/LAUNCH1_CHECKPOINT.md`에 구현 상태·서버 배포 방식·남은 운영 확인을 기록했습니다. 설계 기준과 구현 완료를 구분합니다.

검수 보고서는 `HWARANG_LAUNCH1_REVIEW_20261009.md`, 변경 파일은 `LAUNCH1_MANIFEST.json`입니다. 운영 반영 뒤에는 버전·무료 진단부터 Codex가 확인하고 허용된 유료 검수 1회를 진행하면 됩니다.

공식 참고: [Supabase HTML 제한](https://supabase.com/docs/guides/functions/http-methods), [Supabase API 키](https://supabase.com/docs/guides/getting-started/api-keys), [Worker 무료 한도](https://developers.cloudflare.com/workers/platform/limits/), [Worker Secret 설정](https://developers.cloudflare.com/workers/configuration/secrets/).
