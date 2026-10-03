# HWARANG ACADEMY V5.7 적용 안내

## 변경 목적
- ACADEMY 로그인 후 AI 상담 시뮬레이터 진입 시 재로그인하지 않도록 내부 화면 전환으로 변경
- 회원가입 가입코드 입력값 마스킹 해제
- 로그인 아이디의 특정 관리자 예시 제거
- ACADEMY HOME 사용자 문구 정리
- 시뮬레이터에서 ACADEMY HOME 복귀 추가

## 변경 파일
- `academy_app.py`
- `hwarang_academy/service.py`
- `hwarang_academy/frontend/app.js`
- `hwarang_academy/frontend/styles.css`

## 적용
변경 파일만 ZIP을 사용할 경우 프로젝트 루트에 같은 경로로 덮어쓰세요.

```powershell
git status
git add academy_app.py hwarang_academy/service.py hwarang_academy/frontend/app.js hwarang_academy/frontend/styles.css
git commit -m "Fix Academy single-login navigation and auth UX"
git push origin main
```

## 검증 순서
1. ACADEMY에서 로그인
2. HOME의 AI 상담 시뮬레이터 카드 또는 사이드 메뉴 선택
3. 로그인 화면 없이 시뮬레이터로 전환되는지 확인
4. 시뮬레이터 상단 `ACADEMY 홈` 선택 후 로그인 없이 HOME으로 복귀하는지 확인
5. 다시 AI 상담 시뮬레이터로 이동했을 때 동일 Streamlit 세션의 진행 상태가 유지되는지 확인
6. 로그아웃 후 로그인 화면으로 돌아오는지 확인
7. 회원가입 탭에서 가입코드가 평문으로 보이는지 확인
8. 로그인 입력란에 특정 사용자 ID 예시가 없는지 확인

## 참고
현재 상담 이어하기는 동일 Streamlit 세션 메모리 기준입니다. 장기 저장/재접속 후 이어하기는 이후 `Case / Session` DB 모델 연결 단계에서 구현합니다.
