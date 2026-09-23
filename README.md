# 화랑 WORKSPACE · 12단계 테스트 서버 배포 후보

**먼저 `01_DEPLOY_GUIDE_KO.md`를 확인하세요.**

11단계 수정 후 재감사본 전체를 포함합니다. 보장분석 상품명 문자 출력, XLSX 내부 연결 검사, 의존성 버전 고정이 반영돼 있습니다. 직원 명단과 보너스 매칭은 그대로 유지하며 화면의 개인정보 안내는 제거한 상태입니다.

- 실행 파일: `app.py`
- 의존성: `requirements.txt` + `constraints.txt`를 함께 반영
- 설정: `.streamlit/config.toml` 포함, 기존 로그인 secrets 유지
- 자동 검사: `python -m unittest discover -s tests`
- 실행: `python -m streamlit run app.py`
- 파일 검증 목록: `RELEASE_MANIFEST.json`
- 상세 수정/검사 기록: `STAGE11_RECHECK.md`
- 현재 패키지 범위: `STAGE12_RELEASE_NOTES.md`

현재 검사 환경에서 104개 테스트가 통과한 코드입니다. 새 환경 설치 및 실제 PC·모바일 육안 검사는 완료되지 않았습니다. 본 ZIP은 테스트 서버용이며 실제 서버에 자동 배포하지 않습니다.

이전 단계 문서는 개발 이력입니다. 현재 적용 절차와 검증 상태는 이 README 및 위 안내 파일을 기준으로 합니다.
