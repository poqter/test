HWARANG WORKSPACE 2026-10-07 audit patch
대상: HWARANG_WORKSPACE_PERFORMANCE_V63_1_HOTFIX_FULL 제공 소스
상태: 로컬 수정 및 회귀 검사 완료. 운영 사이트 배포 전.

수정
- 관리자 AI registry select: id -> request_id
- 관리자 사용자/운영설정/크레딧정책 읽기: 세션 내 15/30초 캐시
- 성공한 관리자 RPC 후 읽기 캐시 무효화
- 공용 PDF 글꼴: bundled NanumGothic + NanumMyeongjo TTF 포함
- 회귀 검사 5개 추가

적용
1. 기존 저장소를 백업합니다.
2. modules/, assets/, tests/를 app.py가 있는 루트에 같은 경로로 반영합니다.
3. 프로젝트 가상환경에서 python -m pytest tests -q 를 실행합니다.
   검수 환경: Python 3.11, Streamlit 1.64.0, pytest 9.1.1, pytest-subtests.
4. 변경 파일을 커밋하고 Streamlit 배포를 갱신·재시작합니다.
5. 새 세션에서 AI 사용량·비용과 질문지/고객용 비교표 PDF를 확인합니다.

DB SQL, Secrets, 권한, 크레딧 정책, 유료 API 설정 변경은 없습니다.
이 묶음은 변경 파일 패치이며 전체 저장소가 아닙니다.
기존 test 폴더 및 requirements.txt를 삭제하거나 교체하지 마세요.
assets/fonts/의 OFL 라이선스를 글꼴 파일과 함께 유지하세요.
롤백 시 원본 모듈을 복원하고 앱을 재시작합니다.

검증 결과: 182 passed, 61 subtests passed.
88개 계산기 UI 실행은 처리되지 않은 예외 0개이며,
6개는 사전 조건 확인 안내에서 중단했습니다.
모든 세법·약관·업로드 집계의 완전 검증을 의미하지 않습니다.
후속 개선 항목은 별도 PDF 보고서에 있습니다.
