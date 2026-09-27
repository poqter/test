# 화랑 WORKSPACE — 재무·보험 계산기 80개

2026-09-27 검증본입니다. 기존 WORKSPACE에 80개 계산기, 고객용 결과와 설계사용 상세 계산, TXT·CSV 저장을 통합했습니다. 겹치는 기존 계산기는 공통 엔진으로 연결하고, 별도 기능 8개는 추가 도구로 유지합니다.

## 실행

Python 3.12 환경에서 프로젝트 루트 기준:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

기존 로그인 비밀번호 설정은 그대로 사용합니다. 비밀번호·인증 쿠키는 패키지에 포함하지 않았습니다. 반영 절차는 `01_DEPLOY_GUIDE_KO.md`를 확인하세요.

## 검증

- 전체 자동검사 368개 통과.
- 실제 앱의 로그인 → 80개 계산기 선택 → 유효 입력으로 계산·진단 → 고객/상세 2개 화면 → 다운로드 2개 확인.
- 로컬 Streamlit 서버 HTTP 상태 검사 통과.
- 실제 검사 환경: Python 3.12.14, Streamlit 1.64.0. 사용한 의존성 48개를 `constraints.txt`에 기록했습니다.

```bash
PYTHONPATH=tests:. python -m unittest discover -s tests
```

## 함께 확인할 문서

- `docs/FINAL_VALIDATION.md`: 검사 결과와 주요 교정 사항.
- `docs/CALCULATOR_SCOPE_AND_TESTS.md`: 80개 계산기별 구현·검사·범위 제한.
- `docs/LEGAL_REFERENCE_INDEX.json`: 공식 법령·요율 자료 대조 기록.
- `calculator_audit/final_all80_execution.json`: 가상 입력으로 실행한 80개 결과 기록.
- `RELEASE_MANIFEST.json`: 최종 패키지 파일별 SHA-256.

세금 계산에는 적용 기준일과 확인 조건을 표시합니다. 계산별로 확인한 평가액·공제액·적격 여부를 입력하는 항목이 있으며, 신고서 작성·전자신고·모든 특례의 자동 자격판정은 제공하지 않습니다. 비교용 산출세액과 최종 결정세액을 구분해 표시합니다.

원본 화면을 대조해 독립 구현한 계산기입니다. JARVIA 로그인이나 외부 계산 API 없이 화랑 안에서 실행됩니다. 이 패키지는 실제 서버에 배포하지 않았으며, 새 환경의 온라인 패키지 설치와 실제 기기 육안 검사는 수행하지 않았습니다. 기존 `STAGE*` 문서는 개발 이력이며 현재 상태는 이 README와 최종 검증 보고서를 기준으로 합니다.
