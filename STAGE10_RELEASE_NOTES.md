# 화랑 WORKSPACE 10단계 수정 작업본

2026-09-23 / 8단계 전체 프로젝트에 9단계 감사 결과와 사용자의 변경 요청을 반영했습니다. 9단계는 감사 단계이며 별도 앱 변경본이 아니었습니다.

## 사용자 요청 반영

- 홈·상담·비교표·고객자료·도움말의 개인정보 안내와 입력 자제 문구 제거.
- 초기화·내용 검토·출처 확인 같은 실제 업무 기능 유지.
- 상담 준비 체크리스트와 고객자료 양식의 관련 문구도 정리.
- 직원 명단 24개 항목과 보너스 매칭은 유지. 명단 분리 작업은 이번 사용자 지시에 따라 제외.

이것은 화면 문구 정리이며 새로운 저장 기능을 추가한 것이 아닙니다.

## 감사 후 수정

### Excel 출력

리모델링의 사용자 문자열은 명시적으로 문자 셀로 기록합니다. `=2+2`라는 신규안 이름이 Excel 수식으로 변하지 않습니다. 실적 표와 수수료 출력의 문자열, 보장분석의 회사명·계약 정보·보장 표시명도 문자로 기록하도록 보완했습니다. 보장분석의 직접 생성한 SUM/시트참조 수식은 유지합니다.

### 오류 처리

기존 파서·출력의 화면 오류에 예외 객체를 그대로 삽입하는 경로를 고정 문구와 PROCESS_FAILED 코드로 바꿨습니다. 원문을 새 로그로 옮기지 않았습니다.

### 업로드

- 파일당 20MB, 현재 세션에 남아 있는 업로드 객체의 합산 60MB.
- 동일 업로드 객체 중복 계산 방지, 현재 파일을 나머지 용량에서 제외하고 새 크기 합산.
- XLSX 필수 파일 확인과 관련 XML 구문 검사. 일반 ZIP을 XLSX로 이름만 바꾼 경우 거절.
- 기존 압축 구조 한도에 더해 통합문서 총 100,000행·2,000,000셀 처리 한도 적용.
- PDF 구조 읽기, 암호화 파일 거절, 최대 100페이지 처리 한도 적용.
- 검증 실패 시 해당 실행 중단. 정상 파일의 객체와 읽기 위치 유지.
- PDF 검사에 `pypdf` 사용. 새 requirements를 함께 적용해야 합니다.

이 한도는 파일 처리 기준이며 업로드 전 네트워크 전송량 제한이나 실제 호스팅 메모리 상한을 보장하는 기능은 아닙니다. 크기·페이지·행 한도를 넘는 기존 대용량 자료는 이제 거절될 수 있습니다.

### 사용 흐름·문서

업무 제목 위·아래에 중복 표시되던 순서 표시를 한 곳으로 정리했습니다. 도구 전체 이동과 관련 도구 이동은 각 용도로 유지합니다. 기능 대응표는 현재 구현과 과거 Stage 2 이력을 구분했습니다.

## 적용 순서

1. 기존 테스트 저장소 백업.
2. ZIP 전체를 동일 프로젝트 위치에 반영. 특히 modules, data, requirements.txt를 함께 적용.
3. 기존 secrets 설정 유지 후 의존성 설치/서버 재시작.
4. 기존 업무 제목 아래 ‘업무 화면 개편 10단계’ 확인.
5. 홈·상담·고객자료 안내 문구, 리모델링 특수문자 상품명 출력, 정상/손상 파일 업로드 확인.

서버에 직접 배포하지 않았습니다. 롤백은 8단계 전체 백업과 당시 requirements를 복원합니다.

## 검사와 남은 범위

기존 업무 코드 보존 검사는 이번에 허용한 변경 구간을 정확히 역적용한 뒤 원본 해시를 비교합니다. 실제 변경 내용은 docs/STAGE10_ALLOWED_EDITS.json에 기록했습니다. 변경 구간 밖의 계산·매칭·명단 변경은 검사에서 실패합니다.

최신 세법·실손·청구 기준의 전수 대조, 실제 PC·모바일 브라우저와 출력물 육안검사, 실서비스 동시 사용자 부하검사는 이번 작업에서 수행하지 않았습니다. 다음 출시감사의 미검증 항목으로 남깁니다. 기존 감사 보고서의 직원 명단 분리 권고는 이번 사용자 결정으로 적용 대상에서 제외합니다.

## 최종 실행 결과

전체 자동 검사 96개 통과(83.377초). 추가로 컨벤션·썸머·매니저 Excel 표의 =2+2 문자열이 문자 셀로 유지되는 것을 확인했습니다. 직원 명단 AST는 8단계와 동일합니다.

8단계 대비 수정 26개·신규 3개입니다.

수정: FEATURE_MATRIX.md, README.md, data/checklists.json, data/customer_material_templates.json, modules/analyzer.py, modules/commission_calculator.py, modules/comparison_builder.py, modules/consultation_helper.py, modules/convention.py, modules/customer_materials.py, modules/education_center.py, modules/inheritance_tax.py, modules/insurance_claim_guide.py, modules/insurer_portal.py, modules/legacy_workflow.py, modules/manager_results.py, modules/remodeling.py, modules/summer.py, modules/upload_ui.py, modules/validators.py, modules/workbench.py, modules/workspace_tools.py, modules/workspace_v2.py, requirements.txt, tests/test_app_registry.py, tests/test_legacy_workflow.py

신규: STAGE10_RELEASE_NOTES.md, docs/STAGE10_ALLOWED_EDITS.json, tests/test_stage10_fixes.py
