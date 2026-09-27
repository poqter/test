# 80개 계산기 적용 범위와 검증 연결표

기준일: 2026-09-27. 아래 80개는 각각 실제 계산 엔진과 고객용·설계사용 결과 화면을 갖습니다. 원본 코드 복제본이 아니라 관찰한 입력·결과와 공식 기준을 바탕으로 구현한 화랑 코드입니다.

완료 판정은 각 계산기에 명시한 적용 범위의 수치 계산·진단 및 출력 검증을 의미합니다. 모든 법적 자격을 서류 없이 판정하거나 모든 신고 특례를 처리한다는 의미는 아닙니다. 확인액 입력, 미지원 조건, 비교용 가정은 화면·다운로드에도 표시합니다.

전체 80개 로그인 후 실행 증거: `calculator_audit/final_all80_execution.json`. 모든 항목은 `tests/test_all80_workspace.py`에서 고객/설계사 2개 화면과 다운로드 2개까지 검사합니다. 개별 테스트는 원본 대조 사례, 교정 사례, 경계값과 잘못된 입력을 확인합니다.

## 공통 적용 범위

- 입력한 값은 계산 버튼을 누른 시점의 스냅샷으로 결과·TXT·CSV에 함께 보존합니다.
- 세금·수익·보험료는 화면에 표시된 연도와 조건의 계산입니다. 법정 신고서 생성·전자신고·미래 법령 자동 갱신 기능은 없습니다.
- 지방세를 국세의 10%로 추정하는 모델, 산출세액만 비교하는 모델, 실제 납부보험료 확인 입력 모델을 구분합니다.
- 정책자금·신고 의무 등 진단형 계산기는 진단과 관련 수치를 출력합니다. 승인이나 법적 적격성을 보장하지 않습니다.
- 표시액은 모델별 반올림 또는 절사 규칙을 따릅니다. 상세 계산값은 표시 자릿수보다 정밀할 수 있습니다.

## 항목별 연결표

| 번호 | 계산기 | 구현 파일 | 개별 검사 |
|---:|---|---|---|
| 1 | 상속세계산기 | estate_calculator.py | test_estate_business.py, test_estate_calculator.py, test_estate_skipping.py, test_gift_comparisons.py |
| 2 | 양도소득세계산기 | capital_gains_tax.py | test_capital_gains_tax.py, test_housing_surcharge.py |
| 3 | 증여세계산기 | gift_tax.py, gift_planning.py, gift_comparisons.py | test_gift_comparisons.py, test_gift_tax.py |
| 4 | 근로소득세계산기 | earned_income_tax.py | test_corporate_sixth_batch.py, test_income_tax_batch.py |
| 5 | 종합소득세계산기 | global_income_tax.py | test_bookkeeping_credit.py, test_income_tax_batch.py |
| 6 | 임대소득세계산기 | rental_tax.py | test_income_tax_batch.py |
| 7 | 금융소득종합과세계산기 | personal_tax_models.py | test_personal_tax_models.py |
| 8 | ISA 절세계산기 | personal_tax_models.py | test_personal_tax_models.py |
| 9 | 주택담보대출 이자공제계산기 | mortgage_deduction.py | test_mortgage_deduction.py |
| 10 | 4대보험계산기 | social_insurance.py | test_insurance_startup.py |
| 11 | 창업중소기업 세액감면계산기 | startup_tax_credit.py | test_insurance_startup.py |
| 12 | 연금계산기 | pension_models.py, pension_calculator_ui.py | test_pension_models.py |
| 13 | 은퇴계산기 | retirement_plan.py | test_planning_exports.py, test_retirement_plan.py |
| 14 | 퇴직금계산기 | severance.py | test_planning_exports.py, test_severance.py |
| 15 | 연금저축·IRP 세액공제계산기 | pension_credit.py, retirement_models.py | test_pension_credit.py, test_planning_exports.py, test_retirement.py |
| 16 | 국민연금 수령시기계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 17 | 주택연금계산기 | housing_pension.py | test_housing_pension.py, test_planning_exports.py |
| 18 | 일시금·연금 세금비교계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 19 | 은퇴크레바스계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 20 | 3층연금 점검계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 21 | 연금 인출기간계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 22 | 사적연금 과세계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 23 | IRP 적립계산기 | retirement_models.py | test_planning_exports.py, test_retirement.py |
| 24 | 은퇴저축계산기 | retirement_remaining.py | test_calculator_exports.py, test_planning_exports.py, test_retirement_remaining.py |
| 25 | 연금 인출순서계산기 | retirement_remaining.py | test_calculator_exports.py, test_planning_exports.py, test_retirement_remaining.py |
| 26 | 사망보장 필요액계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 27 | 중대질병 보장계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 28 | 간병·장기요양 필요액계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 29 | 자녀보험 필요액계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 30 | 적정보험료계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 31 | 정기·종신 비교계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 32 | 의료비 부담계산기 | coverage_models.py | test_calculator_center_routes.py, test_coverage.py, test_planning_exports.py |
| 33 | 미래가치계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 34 | 복리계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 35 | 수익률계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 36 | 재무계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 37 | 투자수익계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 38 | 현재가치계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 39 | 비상자금 진단계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 40 | 목표자금 계획계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 41 | 기회비용계산기 | finance_models.py, finance_calculator_ui.py | test_calculator_center_routes.py, test_capital_gains_tax.py, test_corporate_batch.py, test_corporate_second_batch.py, test_corporate_third_batch.py, test_estate_skipping.py, test_finance_models.py, test_finance_ui.py, test_planning_exports.py, test_workspace_finance_integration.py |
| 42 | 비상장주식 평가계산기 | unlisted_valuation.py | test_last_eight_exports.py, test_unlisted_valuation.py, test_valuation_transfer.py |
| 43 | 인정이자계산기 | deemed_interest.py | test_corporate_batch.py |
| 44 | 급여vs배당 비교계산기 | salary_dividend.py | test_last_eight_exports.py, test_salary_dividend.py |
| 45 | 개인사업자·법인 비교계산기 | corp_vs_individual.py | test_corporate_dividend_auto.py, test_corporate_second_batch.py |
| 46 | 임원퇴직금 한도계산기 | executive_severance.py | test_corporate_batch.py |
| 47 | 가지급금 정밀진단계산기 | deemed_interest_diagnostic.py | test_corporate_second_batch.py |
| 48 | 가업승계 세부담계산기 | business_succession.py | test_business_succession.py |
| 49 | 명의신탁주식계산기 | nominee_trust.py | test_corporate_ninth_batch.py |
| 50 | 이익소각계산기 | profit_retirement.py | test_corporate_seventh_batch.py |
| 51 | 차등배당계산기 | differential_dividend.py | test_differential_dividend.py, test_differential_settlement.py |
| 52 | 법인청산 세부담계산기 | corporate_liquidation.py | test_corporate_seventh_batch.py |
| 53 | 지주회사 수입배당금계산기 | holding_company.py | test_holding_company.py |
| 54 | 합병 세부담계산기 | merger_tax.py | test_merger_tax.py |
| 55 | 특정법인 증여의제계산기 | family_corp_gift.py | test_family_corp_gift.py, test_specific_corp_transaction.py |
| 56 | 키맨리스크계산기 | corporate_funding.py | test_corporate_funding.py, test_last_eight_exports.py, test_planning_exports.py |
| 57 | 지분 매입자금계산기 | corporate_funding.py | test_corporate_funding.py, test_last_eight_exports.py, test_planning_exports.py |
| 58 | 승계 재원계산기 | corporate_funding.py | test_corporate_funding.py, test_last_eight_exports.py, test_planning_exports.py |
| 59 | 법인세계산기 | corporate_tax.py | test_corporate_batch.py |
| 60 | 업무용승용차 비용계산기 | vehicle_expense.py | test_corporate_fifth_batch.py |
| 61 | 접대비 한도계산기 | entertainment_limit.py | test_corporate_fifth_batch.py |
| 62 | 고용증대 세액공제계산기 | employment_credit.py | test_employment_credit.py |
| 63 | 연구인력개발비 세액공제계산기 | rnd_credit.py | test_rnd_credit.py |
| 64 | 직무발명보상금계산기 | invention_compensation.py | test_invention_compensation.py |
| 65 | 특허권 자본화계산기 | patent_capitalization.py | test_patent_capitalization.py |
| 66 | 이월결손금계산기 | carryforward_loss.py | test_corporate_fourth_batch.py |
| 67 | 주식매수선택권계산기 | stock_option.py | test_last_eight_exports.py, test_options_accounts.py |
| 68 | 사내근로복지기금계산기 | welfare_fund.py | test_corporate_sixth_batch.py |
| 69 | 법인 4대보험계산기 | corporate_social_insurance.py | test_corporate_third_batch.py |
| 70 | 법인세 중간예납계산기 | corporate_interim_tax.py | test_corporate_third_batch.py |
| 71 | 부가세 예정신고 선택계산기 | vat_preliminary.py | test_corporate_fourth_batch.py |
| 72 | 법인 부동산 보유·양도 비교계산기 | corp_real_estate.py | test_corp_real_estate.py |
| 73 | 취득세 중과계산기 | acquisition_tax.py | test_acquisition_tax.py |
| 74 | 특수관계자 임대료계산기 | related_party_rent.py | test_corporate_ninth_batch.py |
| 75 | 상여금·복리후생비 비교계산기 | bonus_welfare.py | test_corporate_sixth_batch.py |
| 76 | DC부담금 한도계산기 | dc_contribution.py | test_corporate_second_batch.py |
| 77 | 법인보험 만기계산기 | corporate_insurance_maturity.py | test_corporate_sixth_batch.py, test_insurance_transfer.py |
| 78 | 성실신고 대상판정계산기 | sincere_report.py | test_corporate_third_batch.py |
| 79 | 해외금융계좌 신고계산기 | overseas_accounts.py | test_last_eight_exports.py, test_options_accounts.py |
| 80 | 정책자금 자격진단계산기 | policy_fund.py | test_last_eight_exports.py, test_policy_fund.py, test_salary_dividend.py |

## 항목별 추가 범위 제한

아래는 계산 결과가 적용되지 않는 사례 또는 확인값을 입력해야 하는 사항입니다. 세무 판정과 서류 원장 자동화를 계산식 구현과 구분합니다.

### 상속세계산기

- 비거주자 과세, 장애인 기대여명 통계 자동 조회, 가족관계·대습 요건 자동 판정
- 사전증여 수증자별 세액공제 한도는 확인액 입력
- 가업·영농 적격 서류와 사후관리 추징 자동 판정

### 양도소득세계산기

- 상속·증여 취득과 이월과세
- 공동소유·겸용주택·용도변경·분양권·입주권
- 연간 복수 양도 합산 및 세액감면
- 거주 비과세·주택 수·지역 및 경과규정의 자격은 확인 입력

### 증여세계산기

- 부담부증여 다주택·혼합자산·수증자 취득세
- 사전증여를 상속합산 기간 안에 자동 연결하는 날짜별 원장
- 과거 증여 신고서의 공제·과표·산출세액은 중복 제거한 확인액 입력
- 가업·창업 증여특례 및 국외세액공제는 별도 검토

### 근로소득세계산기

- 기부금 종류별 한도 및 이월은 확인액 입력
- 교육비 자격·개인별 한도는 확인액 입력
- 추가 인적공제·출산입양·카드·월세·감면 미반영

### 종합소득세계산기

- 혼합 근로소득 세액공제는 확인액 입력
- 기장의무 자격, 최저한세·감면 조합은 확인 필요
- 결손금 통산·이월 및 소득공제 종합한도 자동화 제외
- 추가 공제와 표준공제의 적격 조합은 확인 입력

### 임대소득세계산기

- 연중 주택수·보증금 변동 적수 및 공동사업 배분
- 등록·미등록 혼합과 소형주택 세액감면
- 소득 변화에 따른 다른 공제액 변동은 확인 입력

### 금융소득종합과세계산기

- 국내 일반14% 원천징수 이자·배당 및 확인된 배당가산 대상 지원
- 비영업대금·국외 미원천징수·특례 분리과세·다른 소득 세액공제 제외

### ISA 절세계산기

- 신규 계좌·연초 정액 납입·3년 이상 유지·일반 과세 이자 가정
- 미사용 한도 이월·중도인출·주식 매매차익·손익통산·금융종합과세 미반영

### 비상장주식 평가계산기

- 자기주식 상호참조·종류주식·평가심의 등 확장 범위
- 기존 상속·증여 화면과 평가액 연결
- 최종 통합 감사

### 인정이자계산기

- 복수금리·귀속자·연도에 걸친 사업연도
- 가중평균 금리 자동 산출·선택 이력
- 인정이자 제외 및 상계요건 자동 판정
- 소득처분·원천징수와 신고 단수처리

### 개인사업자·법인 비교계산기

- 자동 금융소득 비교는 배당공제 외 다른 세액공제 적용 전; 최종 결정세액 비교는 확인액 모드 사용
- 개인·법인 보험료는 실제 확인액 입력; 설립·전환 관련 세금 전체 비교 제외
- 급여 손금 적격, 과거 이익잉여금 배당, 공제감면·결손 제외

### 임원퇴직금 한도계산기

- 정관·지급규정별 법인 손금한도 자동 산출
- 중간정산·합산근무·2011년 말 가정 금액 자동 계산
- 초과분 소득처분 및 실제 세액 통합

### 가지급금 정밀진단계산기

- 변동 잔액·복수 금리 정밀진단 연결
- 상여처분·회수 특례 자동 판정
- 법인세·사회보험·원금 상환 기간 및 해결방안 동일범위 비교

### 가업승계 세부담계산기

- 평가된 주식가액 연결 지원; 사업무관자산·한도초과·다중수증자·과거특례 제외
- 사후관리 추징·적격증빙 자동 판정 제외

### 명의신탁주식계산기

- 과거 연도·미명의개서 의제시기 및 평가 자동화
- 신고공제·감정수수료·가산세와 최종납부액
- 실소유자 및 조세회피 목적 증빙 자동판정

### 이익소각계산기

- 배당 재원별 적격성은 확인 선택; 적격 배당가산·공제 계산 지원
- 취득가액 특례·증여주식·현물 시가·부당행위 판정 제외

### 차등배당계산기

- 원래 소득유형·연간 과세표준·분리과세 세율은 확인 입력
- 1년 반복거래·복수 증여자·최대주주 자격 자동판정 제외
- 과거 세대생략 증여 복합·최초/정산 신고기한 자동판정 제외

### 법인청산 세부담계산기

- 배당 재원별 적격성은 확인 선택; 적격 배당가산·공제 계산 지원
- 취득가액 특례·증여주식·현물 시가·부당행위 판정 제외
- 자기자본 세무조정·분할분배·중간신고·기납부·현물·지방세 안분 자동화 제외

### 지주회사 수입배당금계산기

- 종전 지주회사 경과규정 자격·세율
- 다수 피출자법인 합산·일별 적수 원장
- 적용제외 배당·법인·보유기간 자동판정
- 공제감면·결손금·지방세·단기사업연도 최종세액

### 합병 세부담계산기

- 양도가액·순자산 세무조정 자동화
- 법인지방소득세·취득세·주주 의제배당
- 자산조정계정·사후관리 추징·공제감면·이월결손금
- 법정 월수 날짜 자동산정·적격증빙 판정

### 특정법인 증여의제계산기

- 간접 출자경로·사업부문·지배주주 및 기업 규모 자동 판정
- 과세제외매출·세후영업이익 세무조정 자동계산
- 특례·외국세액·신고 단수

### 법인세계산기

- 비과세·소득공제와 최저한세 과표 가산조정
- 단기 사업연도·연결납세·추가법인세
- 공제감면 항목별 자격·순서·이월 원장
- 농특세 자동 분류·지방세 조례와 안분·단수처리

### 업무용승용차 비용계산기

- 일부기간 업무전용보험·번호판 변경 및 금융리스 소유특례
- 매각·임차종료·해산·처분손실과 다년 이월 원장
- 비달력·단기사업연도·개인사업자·2016년 이전 취득 및 신고 단수처리

### 접대비 한도계산기

- 전통시장·온누리·지역사랑상품권 추가한도 및 중복 적격성
- 정부출자기관70% 및 금융업 수입특례 자동계산
- 건별 증빙 판정·자산계상 배부·신고 단수

### 고용증대 세액공제계산기

- 2027·2028년 과거3개연도 유지분 계산
- 월별 근로자 원장·자격 자동판정
- 종전제도 경과공제·추징·추가공제
- 최저한세·이월·농특세·중복공제
- 창업·합병·다지역·비달력 사업연도

### 연구인력개발비 세액공제계산기

- 최저한세·공제 순서·이월공제 및 실제 당기 사용액
- 신성장·원천기술·국가전략기술 별도 공제
- 비용 적격·기업 규모·졸업 유예 자동판정
- 단기 사업연도·합병·분할·사업양수 조정

### 직무발명보상금계산기

- 직무발명 요건·법정 특수관계 및 다수 지급자 내역 자동판정
- 특별·표준·자녀·연금 세액공제·지방세·보험료·최종 신고 단수처리

### 특허권 자본화계산기

- 지방세·원천징수·세액공제·실수령
- 특허평가·귀속·사업소득 분류 자동판정
- 법인상각 연수·월할·한도 자동화·현물출자특례

### 이월결손금계산기

- 합병·분할·연결납세 및 사업연도 변경
- 100% 공제 자격 자동판정과 과거 사용액 원장 연계
- 공제감면·최저한세·신고 단수처리

### 사내근로복지기금계산기

- 80/90% 사용특례 세부 자격 및 기본재산 추가사용 자동판정
- 현물·자기주식·공동기금·별도 세액공제
- 수혜항목별 직원 과세와

### 법인 4대보험계산기

- 직원별 보험 가입조건과 보험별 서로 다른 기준보수
- 대표자·임원·고령자·일용직·외국인 및 지원감면·요율유예
- 연간 정산·월별변동 및 신고서 단수처리

### 법인세 중간예납계산기

- 합병분할·연결·비영리·외국법인·특례법인
- 다른 결산월·기한후납부·개별연장·휴업확인
- 가결산 과표 및 공제감면·최저한세 자동 산출

### 부가세 예정신고 선택계산기

- 조기환급 유형별 적격성 자동판정
- 매출·매입·공제 항목에서 예정기간 납부세액 자동계산
- 신설·폐업·수시부과·징수유예·개별 연장

### 법인 부동산 보유·양도 비교계산기

- 취득·보유·지방·부가가치세와 자금 인출 세금 포함 총비용 비교 제외
- 주택 추가과세 제외·비사업용은 확인 선택; 미등기·권리양도 제외
- 다주택·공동소유·복수 매각·증여 취득 등 개인 특례 제외
- 매각손실의 당기 과표 감소 지원; 미래 결손금 이월·공제감면·소규모법인 제외

### 취득세 중과계산기

- 중과 적용·제외 업종·산업단지·설립 설치 전입 시점 자동판정
- 중과 제외 주택·농지·원시 무상취득·중복 중과·감면
- 지방교육세·농어촌특별세 및 단수처리
- 취득 부대비용 및 과세표준 자동산정

### 특수관계자 임대료계산기

- 단기 계약·기간별 조건변경
- 특수관계·예외·경제적 합리성 증빙 판정
- 상대방 과세·소득처분·원천징수 및 최종 세액

### 상여금·복리후생비 비교계산기

- 직원별 상이 급여·추가 공제 원장
- 급부 유형별 비과세·근로소득 제외 자동판정 및 지급월 원천징수
- 보험별 추가 보수 정산과 회사 법인세·부가세 효과

### DC부담금 한도계산기

- 직원별 휴직·입퇴사·과거근속 및 지연이자
- 복수 임원 개별한도와 퇴직충당금 전환
- 최저한세·공제감면·이월결손금과의 연동

### 법인보험 만기계산기

- 보험종류별 과거 손금·유보 원장 자동검증
- 공제감면·결손금·원천징수 정산

### 성실신고 대상판정계산기

- 공동사업장·세부 업종코드 및 주업종 동률 판정
- 법인 성실신고확인 별도 요건 자동판정
- 비용공제 세액한도·이월·추징·미제출 가산세
