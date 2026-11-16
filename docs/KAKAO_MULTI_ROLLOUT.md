# 카카오 나와의 채팅 브리핑 확장: 검수 및 배포

## 현재 상태
운영 additive DB 5개 migration 및 hwarang-kakao Edge v1을 OFF 상태로 배포했다. 운영 실조회: enabled=false, 예산0, 새 연결/발송/슬롯0, 기존 cron1개와 개인 승인 연결1개 보존. 실제 이용자 OAuth/카카오 실발송은 아직 검증하지 않았다. 새 UI도 flag OFF이며 callback·비밀값·파일럿 검증 전 발송 활성화하지 않는다.
기존 dot_kakao_* 개인 자동화와 연결은 변경하지 않는다. 기존 소유자는 새 시스템에서 제외하고 기존 카카오 account_id의 중복 연결도 차단한다.

## 기능
- 로그인 사용자 JWT+현재 DB 세션/활성/권한 확인. 카카오 연결 이후 callback-only 일회용 확인코드를 본인 캘린더에 입력해야 확정된다.
- 사용자별 시간/요일/빈 일정, 중지/해제. 관리자 실제 조직·직책 범위에서 상태/이력·중지만 관리.
- 본인/동행/공통 일정의 허용된 요약만, 본문과 토큰은 관리 화면에 노출하지 않음.
- 기본 텍스트 200 UTF-16 이하, 시간순/줄바꿈/상태 표시, 짧으면 한 메시지·길면 누락 없이 분할. 3개 제한 없음.
- 기본 텍스트 버튼은 유지. 무버튼 사용자 정의 피드는 잘림 때문에 사용하지 않음.
- 날짜별 유일 배치, 순차 claim, 현재 동의/소속/일정 snapshot 재확인, 불확실 상태 자동 재발송 금지. 예약시각+10분 전체 전달 마감: 실제 접수된 부분은 보존하고 미송신분만 만료, 부분발송 X/Y 표시.
- 지역 미설정 이용자의 날씨를 임의 추정하지 않음. 현재 다중 사용자 worker는 일정만. 기존 개인 날씨 브리핑은 별개 유지.

## 검증 결과
- Node tests/kakao_multi*.test.mjs 통과(최신 개수는 실행 로그 기준).
- Python settings + mobile/scope/back 회귀 통과.
- staging base+dispatch+security patch SQL 적용 성공. Feature gate OFF, 예산0.
- rollback-only 합성 QA 통합7 항목, 실제 authenticated/anon5 항목 통과.
- RLS 켜짐, anon/authenticated의 원본 테이블/서비스 RPC 접근 차단 확인.
- security advisor: 새 테이블 RLS without policy INFO는 의도적 deny-all. 기존 leaked-password warning은 본 작업 범위 밖.
- 병렬 실제 PostgreSQL17/합성 데이터 검수: 같은 job을 두 세션이 claim하면 하나만 성공. 동시 같은시각 신청은 슬롯1개, 동시해제 후0개. 외부통신 없는 loopback 서버를 같은 실행 안에서 시작/종료했다. cron/net은 네트워크 없는 기록 stub이다. staging persistent 발송fixture 거절은 우회하지 않았다.
- 모바일 실화면, 두 사람 실제 카카오 OAuth, 카카오 수신, remote CI/배포 확인 미실시.

## 배포 순서 (모든 단계 완료 전 UI gate false)
1. 최신 main 재확인/독립리뷰. 원본 SQL+보안패치 내용 일치 및 상태 변경 범위 확인.
2. 운영 additive DB 적용: KAKAO_MULTI_DRAFT.sql, KAKAO_MULTI_DISPATCH_DRAFT.sql, KAKAO_MULTI_TICKET_PATCH.sql, KAKAO_MULTI_DYNAMIC_CRON_DRAFT.sql, KAKAO_MULTI_REAUTH_PATCH.sql. security patch는 이미 두 원본에 반영되었으므로 신규 환경에 중복 실행 불필요.
3. 별도 hwarang-kakao Edge 함수 배포. OAuth callback/start 때문에 플랫폼 JWT 검증 대신 /connect의 Auth API+live RPC, /tick의 2분 일회용 티켓 원자적 검증을 사용한다. verify_jwt=false 설정은 보안리뷰 포함.
4. 비밀값 직접 입력: KAKAO_MULTI_TOKEN_KEY(32자 이상), KAKAO_APP_ID=1652822. 기존 KAKAO_REST_API_KEY/KAKAO_CLIENT_SECRET 재사용. 새 암호화 키 변경은 재연결을 요구하므로 무단 회전 금지.
5. 카카오 Redirect URI 추가: https://zaynrfzzrtuiherbhoee.supabase.co/functions/v1/hwarang-kakao/callback
6. cron은 2분 일회용 티켓만 pg_net에 넣는다. 영구 credential을 HTTP queue에 넣지 않는다. 별도 cron 비밀키/Vault 설정은 사용하지 않는다.
7. 실제 두 이용자가 각자 직접 로그인/동의/연결확정 및 해제/다른 계정 차단 시험. 개인 기존 소유자 이용자가 테스트용 다른 계정에 같은 카카오를 연결하지 않도록 한다.
8. Free 요금제/기능 범위 재확인, 보수적 월간 로컬예산 및 cost_verified_until 설정. Free plan에서 overage 청구하지 않는 provider 정책과 별개로 한도 초과는 중단/보류. 유료 API·AI·문자·지도 fallback 없음.
9. 매분 cron은 사용하지 않는다. DYNAMIC_CRON은 신청 HH:MM별 공유 작업을 설정 변경에 맞춰 생성/제거한다. tick_endpoint를 해당 환경으로 지정하고, 먼저 제한 pilot만 검수한다. 같은 시각 배치는 bounded worker 후속 일회용 tick으로 이어 처리하며 예정시각+10분 이후 미송신분은 표시하고 중단한다. 별도 일1회 DB-only 정리 작업은 승인된 템플릿대로 설정한다.
10. Streamlit HWARANG_KAKAO_MULTI_ENABLED=true 및 검증된 코드 공개배포. 기존 공개 git push 자동심사 거절을 다른 채널로 우회 금지.
11. 원격 commit/CI·웹앱 메뉴·OAuth·정해진 시간1회·중복없음 확인 후만 운영 완료 보고.

## 중지
DB kakao_multi_controls.enabled=false 및 Edge KAKAO_MULTI_ENABLED=false; UI flag false. 기존 개인용 경로는 유지.
이미 카카오 API에 접수된 메시지는 취소할 수 없다. accepted는 읽음/휴대폰 수신 확인이 아니다.

## 확정된 인증철회와 일시 오류 구분
- 공식 KOE322 invalid_grant, memo -402(동의 없음)/-101(앱 연결 없음), 저장된 refresh 만료만 재연결 필요로 중지한다. 일반401(-401), 네트워크 timeout,5xx는 임의로 연결을 삭제하지 않는다.
- https://developers.kakao.com/docs/en/kakaologin/trouble-shooting
- https://developers.kakao.com/docs/en/rest-api/error-code
- 관리자 사용자 활성화/앱 접근/권한 변경 후 trusted 운영 DB 세션에서 `select private.kakao_cron_reconcile();` 실행. 광범위 기존 권한테이블 trigger를 추가하지 않는다. 일1회 DB-only 정리도 설치해 잔여 슬롯을 정리한다. 실행 시점에는 항상 현재 권한을 별도로 재검증한다.
- 월경계에는 예약월과 다음달 deadline 양쪽에 보수적으로 계상한다. 이는 서비스 내부 cap이며 provider 전체 사용량 측정이나 과금 정책 확인을 대체하지 않는다.
