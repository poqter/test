# 화랑 WORKSPACE · Calculator 분리 배포 안내

## 최종 구조

같은 GitHub 저장소를 Streamlit Community Cloud에서 두 개의 앱으로 배포합니다.

| 앱 | Main file path | 접근 방식 |
|---|---|---|
| 화랑 WORKSPACE | `app.py` | 기존 비밀번호 로그인 유지 |
| 화랑 CALCULATOR | `calculator_app.py` | 별도 로그인 없이 공개 |

WORKSPACE의 `종합계산기(80개)` 버튼은 Calculator 앱을 **새 탭**으로 엽니다. 기존 WORKSPACE 탭은 닫히지 않으므로 로그인 상태와 진행 중인 화면이 그대로 유지됩니다.

## 배포 순서

### 1. Calculator 앱을 먼저 생성

Streamlit Community Cloud에서 **Create app**을 선택하고 다음과 같이 지정합니다.

- Repository: WORKSPACE와 같은 저장소
- Branch: 테스트에 사용하는 동일 브랜치
- Main file path: `calculator_app.py`
- App URL: 원하는 Calculator 전용 주소
- Advanced settings → Python version: **3.12**

Calculator 앱에는 WORKSPACE의 `[passwords]` Secrets를 넣지 않아도 됩니다. Python 3.12는 현재 고정된 pandas·PDF 라이브러리 조합과 맞추기 위한 배포 기준입니다.

### 2. 생성된 Calculator URL 확인

Calculator 앱이 배포되면 실제 주소를 복사합니다.

```text
https://<calculator-app-name>.streamlit.app
```

### 3. WORKSPACE 앱 Secrets에 Calculator URL 추가

기존 WORKSPACE 앱의 **App settings → Secrets**에서 현재 `[passwords]` 설정은 유지하고 아래 구역만 추가합니다.

```toml
[external_apps]
calculator_url = "https://<calculator-app-name>.streamlit.app"
```

예시 전체 형태:

```toml
[passwords]
Admin = "기존 비밀번호"
Manager1 = "기존 비밀번호"

[external_apps]
calculator_url = "https://<calculator-app-name>.streamlit.app"
```

Calculator URL이 등록되지 않았거나 형식이 올바르지 않으면 WORKSPACE의 계산기 링크는 비활성화됩니다.

### 4. WORKSPACE 앱 재부팅 확인

WORKSPACE의 Main file path는 기존처럼 `app.py`를 유지합니다. Secrets 저장 후 앱이 다시 실행되면 다음 위치에서 Calculator가 새 탭으로 열리는지 확인합니다.

- 홈 화면의 `종합계산기(80개)` 카드
- 사이드바의 `종합계산기(80개)` 메뉴
- 기능 검색 결과의 계산기 항목

## 사용 흐름

```text
WORKSPACE 로그인
    ↓
종합계산기(80개) ↗ 클릭
    ↓
새 탭에서 CALCULATOR 실행
    ↓
기존 WORKSPACE 탭은 로그인·작업 상태 유지
```

Calculator가 장시간 미사용으로 Sleep 상태라면 새 탭에서 Streamlit 깨우기 화면이 먼저 나타날 수 있습니다. Calculator를 깨우는 동안에도 기존 WORKSPACE 탭에는 영향이 없습니다.

## 기존 1시간 토큰 변경

별도 Calculator 앱은 공개형으로 운영하므로 기존 계산기 새 탭용 구조였던 다음 항목을 제거했습니다.

- 일회성 grant
- token 전달·검증
- claim window
- 1시간 lease
- owner별 revoke
- `dedicated_tab.py`, `tab_access.py`
- `launcher.js`, `receiver.js`

Calculator URL을 통해 WORKSPACE의 보호 기능으로 우회 진입할 수는 없습니다. Calculator에서 메인 WORKSPACE 기능을 직접 실행하지 않으며, WORKSPACE URL에 접근하면 기존 로그인 검사가 그대로 적용됩니다.

## 로컬 실행

로컬 개발 시 WORKSPACE에서 Calculator 링크를 활성화하려면 환경변수를 사용할 수 있습니다.

```text
HW_CALCULATOR_URL=http://localhost:8502
```

터미널을 두 개 열어 각각 실행합니다.

```bash
streamlit run app.py --server.port 8501
streamlit run calculator_app.py --server.port 8502
```

## 배포 직후 확인 항목

1. WORKSPACE 로그인 화면과 기존 비밀번호가 정상 동작하는지
2. 계산기 링크가 새 탭으로 열리는지
3. 원래 WORKSPACE 탭의 로그인 상태와 입력 화면이 유지되는지
4. Calculator 첫 화면에 80개 전체 목록이 표시되는지
5. 검색·카테고리·계산기 열기·목록 복귀가 동작하는지
6. Calculator Sleep 상태에서 일반 사용자가 깨울 수 있는지
7. 대표 계산기의 계산·PDF·CSV 다운로드가 동작하는지
8. 모바일과 데스크톱에서 카드 및 입력 화면이 잘리지 않는지
