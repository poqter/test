# 최종본 적용 안내

이 ZIP은 변경 파일만 담은 패치가 아닌 **전체 앱 실행본**입니다. 계산기 80개와 기존 화랑 기능을 함께 포함합니다.

## 1. 파일 반영

1. 기존 프로젝트를 백업하거나 되돌릴 수 있는 커밋을 남깁니다.
2. ZIP을 별도 폴더에 풀고, 최상위 `app.py`를 기존 프로젝트의 `app.py`와 같은 위치에 반영합니다.
3. `modules/`, `assets/`, `data/`, `requirements.txt`, `constraints.txt`, `.streamlit/config.toml`을 함께 반영합니다.
4. 기존 `.streamlit/secrets.toml` 또는 서버 Secrets의 `[passwords]` 설정을 유지합니다. ZIP에 비밀번호 설정은 없습니다.
5. `.git`, 개인 가상환경, 사용자 보관 파일은 덮어쓰거나 삭제하지 않습니다.

새 계산기는 홈의 재무·보험 계산기에서 사용합니다. 범주 또는 검색으로 찾은 뒤 입력과 확인 조건을 검토하고 `계산하기`를 누릅니다. 결과가 표시된 뒤 입력을 바꾸면 다시 계산해야 합니다.

## 2. 로컬 실행

검사 환경은 Python 3.12.14 / Linux / Streamlit 1.64.0입니다. Windows PowerShell 예:

```powershell
py -3.12 -m venv .venv_hwarang
.\.venv_hwarang\Scripts\python.exe -m pip install -r requirements.txt
.\.venv_hwarang\Scripts\python.exe -m streamlit run app.py
```

의존성은 실제 검사 환경의 버전으로 고정했습니다. `requirements.txt`와 `constraints.txt`를 같은 위치에 두세요. 새 환경의 온라인 설치는 이번 검증에 포함되지 않았으므로 해당 환경의 설치 결과를 확인해야 합니다.

## 3. 재검사

PowerShell:

```powershell
$env:PYTHONPATH = "tests;."
.\.venv_hwarang\Scripts\python.exe -m unittest discover -s tests
```

Linux/macOS:

```bash
PYTHONPATH=tests:. python -m unittest discover -s tests
```

전체 368개 검사에는 로그인과 계산기 80개 실행이 포함됩니다. 테스트의 로그인 비밀번호는 가상 입력이며 운영 Secrets를 변경하지 않습니다. 고객·직원 데이터 대신 합성 데이터를 사용합니다.

## 4. 서버 반영

기존 Streamlit 배포 저장소에 코드를 반영하고 실행 파일을 `app.py`로 지정합니다. 저장소·브랜치·Python 버전·Secrets가 기존 앱과 일치하는지 확인합니다. 이번 작업에서는 원격 저장소 푸시나 서버 배포를 수행하지 않았습니다.

반영 후 로그인, 계산기 검색, 고객용 TXT, 상세 CSV, 비상장주식 평가액의 증여·상속·가업승계 이동을 확인하세요. 기존 보장분석·제안서·포털 기능의 검사도 패키지에 포함되어 있습니다.

## 5. 법령과 계산 범위

법령·요율 대조일은 각 계산 화면과 결과에 표시합니다. 지원하는 연도와 거래 유형을 벗어난 값을 사용하지 마세요. 적격 확인 선택은 자동 심사가 아니라 확인한 사실을 반영하는 입력입니다. 세액공제 전 비교와 최종 결정세액 확인 입력을 구별하고, 입력한 가정과 범위가 함께 담긴 결과를 고객에게 전달하세요.

80개별 계산 범위와 테스트 연결은 `docs/CALCULATOR_SCOPE_AND_TESTS.md`에 있습니다.
