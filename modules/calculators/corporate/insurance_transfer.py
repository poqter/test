"""Insurance rights transferred to a resident officer: confirmed valuation scenarios."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.pension.severance import income_tax
from modules.calculators.corporate.invention_compensation import wage_scenario
KINDS=('현실적인 퇴직에 따른 현물 퇴직급여','재직 중 근로소득·상여','확인 시가 전액 유상 양도')
M=10**12
FIELDS=[('계약 이전 원인',KINDS[0],'선택',KINDS),('대표가 법인에 실제 지급하는 대가',0,'원',M),('해당 이전의 법인 손금 인정 보수액 (확인액)',200000000,'원',M),('이번 보험 외 동일 퇴직의 과세 퇴직급여',0,'원',M),('개인 소득세법상 전체 임원퇴직소득 한도 (2011년 이전 인정분 포함)',200000000,'원',M),('세법상 합산 근속연수 (1년 미만 올림)',10,'년',120),('보험 이전 제외 연간 과세 총급여',80000000,'원',M),('공통 근로소득공제 외 소득공제',1500000,'원',M),('보험 평가액·퇴직 사실·보수 손금·개인 한도 확인','미확인','선택',('미확인','확인'))]
def transfer(value,book,tax_basis,income,small,kind=KINDS[0],paid=0,deductible=200000000,other_retirement=0,limit=200000000,years=10,salary=80000000,deductions=1500000,confirmed='미확인'):
 if confirmed!='확인':raise ValueError('보험 평가액과 이전 원인, 법인 손금액·개인 퇴직소득 한도를 확인하세요.')
 if kind not in KINDS:raise ValueError('계약 이전 원인을 확인하세요.')
 value,book,tax_basis,paid,deductible,other_retirement,limit,salary,deductions=map(num,(value,book,tax_basis,paid,deductible,other_retirement,limit,salary,deductions));income=num(income,-M,M);years=period(years,120)
 if paid>value:raise ValueError('이 화면은 시가 이하 대가의 이전을 비교합니다.')
 benefit=value-paid
 if deductible>benefit:raise ValueError('이전 관련 손금 보수액은 대표가 얻는 이익 이하여야 합니다.')
 if kind==KINDS[2] and (paid!=value or deductible):raise ValueError('시가 유상 양도는 대가=확인 시가, 손금 보수액=0으로 입력하세요.')
 if kind!=KINDS[0] and other_retirement:raise ValueError('다른 퇴직급여는 퇴직 이전 모드에서만 입력하세요.')
 retirement_before=min(other_retirement,limit) if kind==KINDS[0] else D(0)
 retirement_after=min(other_retirement+benefit,limit) if kind==KINDS[0] else D(0)
 retirement_increment=retirement_after-retirement_before
 wage_before=max(D(0),other_retirement-limit) if kind==KINDS[0] else D(0)
 wage_increment=benefit-retirement_increment
 pension_tax=(income_tax(retirement_after,years)[0]-income_tax(retirement_before,years)[0])*D('1.1')
 wage_tax=(wage_scenario(salary+wage_before+wage_increment,deductions)['비교 국세']-wage_scenario(salary+wage_before,deductions)['비교 국세'])*D('1.1')
 corp_change=value-tax_basis-deductible
 corp_tax=(bracket(max(D(0),income+corp_change),small=='예')-bracket(max(D(0),income),small=='예'))*D('1.1')
 metrics={'법인 실제 대가 수령액':paid,'이전 자산 평가액':value,'법인 소득금액 증감':corp_change,'법인 국세·지방세 증감 추정':corp_tax,'대표 현물 수령 이익':benefit,'개인 퇴직소득 증가분':retirement_increment,'개인 근로소득 증가분':wage_increment,'개인 퇴직소득세 증가 추정':pension_tax,'개인 근로소득세 증가 추정':wage_tax,'대표 세후 현물 이익 추정':benefit-pension_tax-wage_tax}
 notes=['법령 대조일 2026-09-27. 소득세법20·22조, 법인세법15·19·52·55조 및 시행령43·44조. 국세청 서면-2022-원천-3587(2023-02-24) 회신의 퇴직소득 및 한도 초과 근로소득 구분을 적용합니다.',
 '확인된 보험계약 권리의 평가액을 입력합니다. 해약환급금이나 납입보험료가 모든 보험의 시가와 같다고 가정하지 않습니다. 명의변경만으로 퇴직급여가 되지 않습니다.',
 '법인 손금 보수액과 개인 퇴직소득 한도는 서로 다른 기준입니다. 이번 이전분의 손금 인정액만 입력하고, 개인 한도에는 같은 퇴직의 다른 급여를 포함합니다. 법인 손금액은 보험자산 장부가액과 다릅니다.',
 '이전 시 자산 평가이익과 인정 보수 손금을 함께 반영합니다. 실제 법인 현금 유입은 대표가 지급한 대가뿐이며 보험 평가액 전액을 현금 수령으로 표시하지 않습니다.',
 '개인 근로세는 근로소득공제·근로소득세액공제와 입력한 공통 소득공제만 적용한 증분입니다. 보험료·특별세액공제·다른 종합소득·중간정산·원천징수 기납부는 미반영입니다. 현물 이전이므로 세금 납부에 별도 현금이 필요할 수 있습니다.',
 '법인 공제감면·결손금 이월·최저한세와 지방세 개별 조정은 미반영합니다. 저가 양도 중 미확인 증여·배당·부당행위 소득처분은 이 모형으로 확정하지 않습니다.',
 '회신: https://taxlaw.nts.go.kr/qt/USEQTA002P.do?ntstDcmId=010000000000584720']
 return FinanceResult(metrics,'법인 소득증감=보험 평가액−세무상 자산−인정 보수 손금. 대표 이익=평가액−실제 대가. 퇴직 이익 중 개인 한도 내 금액은 퇴직소득, 초과분은 근로소득으로 분리하고 전후 세액 차이를 계산합니다.',notes,[{'항목':k,'금액':v} for k,v in [('회계자산',book),('세무자산',tax_basis),('시가와 세무자산 차이',value-tax_basis),('법인 손금 보수',deductible),('기존 퇴직소득 한도 내 금액',retirement_before),('이전 후 퇴직소득 한도 내 금액',retirement_after)]])
