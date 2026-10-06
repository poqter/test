# HWARANG BRIEFING V1.6 — Phase B 적용 메모

## 적용 상태

- Migration 16: TEST Supabase 적용 및 구조 Gate 검증 완료
- Phase B: Collection + Shared Discovery Integration 백엔드 코드 추가
- UI / 게시 / PDF / Scheduler: 아직 미적용 (후속 Phase C~F)

## 이번 변경 파일

- `.streamlit/secrets.example.toml`
- `data/briefing_direct_sources.example.json`
- `modules/briefing/__init__.py`
- `modules/briefing/models.py`
- `modules/briefing/config.py`
- `modules/briefing/normalize.py`
- `modules/briefing/gates.py`
- `modules/briefing/direct_sources.py`
- `modules/briefing/openai_discovery.py`
- `modules/briefing/clustering.py`
- `modules/briefing/phase_b.py`
- `modules/briefing/repository.py`
- `scripts/briefing_phase_b_smoke.py`
- `tests/test_briefing_phase_b.py`

## 구현 내용

1. INSURANCE/NEWS 4개 focused Search lane
2. Web Tool Call / 실제 Search Action 분리 계측
3. Search Action 미발생 Lane bounded retry 1회
4. CORE 36h / LIGHT 96h Freshness Gate
5. 게시시각 미확인 및 96h 초과 후보 차단
6. 보험 사회보험/계산기성 false positive 1차 차단
7. URL/Publisher/Fingerprint 정규화 및 URL 중복제거
8. Shared Event 보수적 title-Jaccard cluster
9. Profile Routing 및 동일 Event 다중 Profile 연결
10. Direct RSS/Atom Adapter 기반 구조
11. Supabase service-role 운영 Repository 골격
12. Shared Discovery Target 4 / Soft 5 / Hard 6 코드 상수화

## Direct Source Endpoint

현재 SPEC과 업로드된 최신 소스에는 Phase 0에서 검증한 실제 공식 RSS/API Endpoint URL 목록이 포함되어 있지 않다.
따라서 임의 URL을 하드코딩하지 않고 `BRIEFING_DIRECT_SOURCES_JSON` 배포 환경값으로 주입하도록 구현했다.
실제 Endpoint 목록이 확보되면 코드 구조 변경 없이 설정만 추가하면 된다.

## 검증

- `python -m compileall`: PASS
- 전체 `unittest`: 24 tests PASS
- 기존 WORKSPACE UI / 로그인 / ACADEMY / Credit / Voice 코드 수정 없음

## 2026-10-06 후속 반영

### WORKSPACE UX
- 접힌 사이드바 재열기 control이 Streamlit 1.64 header zero-height CSS에 의해 잘리지 않도록 48px 투명 interaction layer로 수정
- collapsed/expand sidebar control을 40px 클릭영역, high z-index로 고정

### 관리자센터
- Dashboard의 `최근 로그인 · 활동`을 `최근 로그인` 전용으로 변경
- Dashboard query는 `LOGIN_SUCCESS` 최근 12건만 조회
- 글로벌 `활동 기록` 메뉴 제거
- 사용자별 활동은 계정 상세의 활동 탭에서만 조회
- 사용자별 활동 조회기간을 최근 7/30/90일로 제한 가능

### BRIEFING Phase B Live Smoke 준비
- `modules/briefing/preflight.py` 추가
- `scripts/briefing_phase_b_preflight.py` 추가
- OpenAI/Direct Source 네트워크 호출 없이 Live Smoke 전 필수 환경설정 검사
- `BRIEFING_DIRECT_SOURCES_JSON` example secret 항목 추가
- Phase C로는 Live Smoke Gate 통과 후 이동

### 검증
- `python -m compileall`: PASS
- 기존 unittest: 24 tests PASS
- 신규/Phase B pytest: 13 tests PASS

## 2026-10-06 후속 반영

### WORKSPACE UX
- 접힌 사이드바 재열기 control이 Streamlit 1.64 header zero-height CSS에 의해 잘리지 않도록 48px 투명 interaction layer로 수정
- collapsed/expand sidebar control을 40px 클릭영역, high z-index로 고정

### 관리자센터
- Dashboard의 `최근 로그인 · 활동`을 `최근 로그인` 전용으로 변경
- Dashboard query는 `LOGIN_SUCCESS` 최근 12건만 조회
- 글로벌 `활동 기록` 메뉴 제거
- 사용자별 활동은 계정 상세의 활동 탭에서만 조회
- 사용자별 활동 조회기간을 최근 7/30/90일로 제한 가능

### BRIEFING Phase B Live Smoke 준비
- `modules/briefing/preflight.py` 추가
- `scripts/briefing_phase_b_preflight.py` 추가
- OpenAI/Direct Source 네트워크 호출 없이 Live Smoke 전 필수 환경설정 검사
- `BRIEFING_DIRECT_SOURCES_JSON` example secret 항목 추가
- Phase C로는 Live Smoke Gate 통과 후 이동

### 검증
- `python -m compileall`: PASS
- 기존 unittest: 24 tests PASS
- 신규/Phase B pytest: 13 tests PASS
