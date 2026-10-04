# HWARANG ADMIN CENTER V2 + CREDIT POLICY V1

기준 소스: GitHub main `8a75d8bb2521b64947b879ce7674a60131704080`

## 적용 방법

이 ZIP은 **변경/추가 파일만** 포함합니다. 자동 패치 스크립트는 없습니다.

1. ZIP 안 파일을 저장소의 동일 경로에 복사/덮어쓰기합니다.
2. Supabase SQL Editor에서 새 Query `13_Admin_Center_V2_Credit_Buckets`를 만듭니다.
3. `supabase/migrations/13_Admin_Center_V2_Credit_Buckets.sql` 전체를 **1회 실행**합니다.
4. 기존 01~12는 다시 실행하지 않습니다.
5. GitHub push → Streamlit 배포합니다.
6. 최고관리자 WORKSPACE → 관리자 센터를 열어 화면과 정책을 확인합니다.
7. 실제 OpenAI API 연결 전까지 AI 서비스/Text/Voice/AI 정식평가는 OFF 유지가 안전합니다.

## 관리자 센터 V2

- 관리자센터 토글 제거 → `관리자 센터 →` 버튼 진입
- 관리자센터 진입 시 일반 WORKSPACE 사이드바를 관리자 전용 Navigation으로 교체
- 대시보드: 핵심 지표 / 운영상태 / 조치 필요 / 최근 활동 / 월 AI 예산
- 계정·권한: 검색·필터 Toolbar / 다중 선택 / 내부 상세 페이지
- 사용자 상세: 개요 / 권한 / 활동 / ACADEMY / AI 이용량
- 위험 권한 변경만 2단계 확인
- 사용자 활동 코드 한글화
- ACADEMY Session / 평가 운영 화면
- AI FinOps: 오늘·월 비용 / 사용자별 / 모델별 / 실패·차단 / 상세 원장
- 시스템 설정: AI 서비스 / 크레딧·예산 정책 / 모델 / Guardrail / 진단 / Danger Zone
- Lazy Loading + 활동/ACADEMY Pagination
- AI 긴급정지는 일반 설정과 분리

## 훈련 크레딧 정책

기본값:
- 월 기본 훈련 크레딧: **1,000**
- 잔여 이용량 경고 기준: **20%**
- 경고 설정 가능 범위: **1~99%**
- 신규 사용자 Voice 기본량: **0분**
- 월 AI 운영 예산: **$50** (관리자가 변경 가능)
- 예산 경고: **80%**

### Bucket

1. **월 기본 크레딧**
   - 매월 1일 KST 기준으로 설정된 기본량으로 복원
   - 미사용분은 다음 달로 누적되지 않음

2. **구매/추가 크레딧**
   - 월 변경과 무관하게 계속 보존
   - 만료 없음
   - 구매 / 프로모션·보상 / 관리자 조정 출처를 원장에 구분

### 소진 순서

`월 기본 → 구매/추가`

API 예약과 실제 정산도 같은 순서로 원자적으로 처리합니다.

예:
- 10월 기본 1,000 전부 사용
- 구매 1,000 후 500 사용 → 구매 잔여 500
- 11월 → 월 기본 1,000 + 구매 잔여 500 = 총 1,500
- 이후 다시 월 기본 1,000부터 먼저 사용

## 경고 방식

경고는 “얼마 사용했는가”가 아니라 **얼마 남았는가** 기준입니다.

기본 제공량이 1,000이고 경고 기준이 20%라면:
- 총 실제 사용 가능 크레딧이 200 이하 → 경고
- 100 이하 → 이용량 추가 필요
- 0 → 이용 한도 도달

월 기본을 모두 사용했더라도 구매 크레딧이 500 남아 있다면 경고하지 않습니다.

## 기존 크레딧 보호

Migration 13 적용 전 기존에 남아 있던 Training Credit은
**구매/영구 Bucket으로 이전**하여 다음 월 갱신에서 사라지지 않게 처리합니다.

## 검증

- Python syntax compile: PASS
- pytest: **50 passed**
- unittest subtests: **58 passed**
- Random generated cases: **1,000 / failures 0**
- Migration 13 static checks: PASS
