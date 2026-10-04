# HWARANG 관리자센터 V2 · 크레딧 정책 감사

## 반영 완료

- 관리자 전용 Console Navigation
- 운영 대시보드 조치필요 중심화
- 계정 다중 선택 + 크레딧 일괄 지급
- 위험 계정/권한 변경 별도 확인
- 활동 로그 한글화
- ACADEMY 운영 화면
- AI FinOps Dashboard
- 월 AI 예산 경고
- Danger Zone
- 월 기본 1,000 Training Credit
- 구매/추가 Credit 영구 이월
- 월 기본 우선 소진
- KST Lazy Monthly Reset
- Bucket별 reservation / finalize / prune
- 잔여량 1~99% 경고 정책
- 사용자 화면 월 기본 / 구매 크레딧 구분
- 기존 남은 Credit 영구 Bucket 보존
- Voice 별도 유지

## 중요한 운영 원칙

- 월 기본 Credit은 “매월 +1,000 누적”이 아니라 “매월 기본량으로 복원”입니다.
- 구매/추가 Credit은 월 갱신에서 절대 초기화하지 않습니다.
- 경고는 총 실제 사용 가능 Credit을 월 기본량과 비교합니다.
- 월 예산 경고는 알림용이며 자동 Kill Switch로 사용하지 않습니다.
- Voice는 Training Credit과 합치지 않습니다.
