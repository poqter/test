"""Confirmed personal patent sale: incremental assessment, not automatic savings."""
from .finance_models import D,num,FinanceResult
from .personal_tax_models import progressive_tax
from .earned_income_tax import wage_deduction
from .corporate_tax import bracket
NAME='특허권 자본화계산기';M=10**12;YN=('아니요','예')
FIELDS={NAME:[('특허권 양도대가',300000000,'원',M),('입증된 실제 필요경비',0,'원',M),('기존 연간 총급여',0,'원',M),('근로소득 외 기존 종합소득금액',0,'원',M),('공통 소득공제',1500000,'원',M),('개인 소유·적정 대가·기타소득 분류·과세 방식 확인','아니요','선택',YN),('법인 당기 손금 인정 상각액 (별도 확인)',0,'원',M),('상각 전 법인 과세표준 단순 추정',0,'원',M),('법인 상각액·소득 확인','아니요','선택',YN)]}
MODES=('종합과세','연간 300만원 이하 분리과세')
FIELDS[NAME]+=[('개인 과세 선택',MODES[0],'선택',MODES),('다른 선택적 분리과세 기타소득금액 (연간 한도 판정용)',0,'원',M)]
def patent(price=300000000,cost=0,salary=0,other=0,deductions=1500000,confirmed='아니요',amortization=0,corp_base=0,corp_confirmed='아니요',mode=MODES[0],other_optional=0):
 price,cost,salary,other,deductions,amortization,corp_base=map(num,(price,cost,salary,other,deductions,amortization,corp_base))
 other_optional=num(other_optional)
 if mode not in MODES:raise ValueError('과세 방식을 확인하세요.')
 if confirmed not in YN or corp_confirmed not in YN:raise ValueError('확인 상태를 선택하세요.')
 if cost>price:raise ValueError('필요경비가 양도대가를 넘는 손실 사례는 별도 검증이 필요합니다.')
 if amortization>price:raise ValueError('이번 취득 특허의 당기 상각액은 양도대가를 초과할 수 없습니다.')
 notes=['법령 대조일 2026-09-27 · 소득세법14조3항8호·21조1항7호·55조·47조·84조, 시행령87조. 국내 거주자의 개인 소유 특허를 적정 대가로 양도하고 기타소득으로 종합과세하는 시나리오입니다.',
 '필요경비는 양도대가60%와 입증된 실제 경비 중 큰 금액입니다. 사업성이 있는 계속·반복 거래와 회사 소유 특허, 직무발명보상금, 현물출자 과세특례는 이 계산 대상이 아닙니다.',
 '급여 비교는 기존 총급여에 같은 금액을 더한 뒤 근로소득공제를 다시 계산합니다. 기존 근로소득공제와 종합소득 누진세율 엔진을 공유합니다. 기존 금융소득 종합과세의 비교과세 등은 지원하지 않습니다.',
 '개인 금액은 종합과세 국세 산출세액 증분입니다. 근로소득세액공제·특별세액공제·지방소득세·원천징수·건강보험료는 미반영이므로 최종 실수령액 또는 확정 절세액으로 표시하지 않습니다. 단일 거래의 기타소득금액 5만원 이하는 과세하지 않습니다. 원천징수 요건을 충족한 연간 선택적 분리과세 기타소득 합계 300만원 이하는 국세20% 분리과세를 선택할 수 있습니다. 다른 기타소득 한도 입력은 기존 종합소득금액에 자동 가산하지 않으므로 선택 과세 방식에 맞게 기존 소득을 입력하세요.',
 '법인은 특허 취득대가 전액을 즉시 비용으로 간주하지 않습니다. 확인된 당기 손금 인정 상각액만 입력해2026년 개시12개월 일반법인 국세 산출세액 차이를 계산합니다. 내용연수·월할·가치평가·손금한도 자동산정과 소규모 특례법인·결손금·공제감면은 미지원입니다.',
 '서로 다른 기간의 법인 세금 감소와 개인 세금을 상계해 순 절세로 단정하지 않습니다. 부가가치세·시가 부인·대금 지급방식은 별도 검증 항목입니다.']
 if confirmed!='예':return FinanceResult({'특허 양도 국세 산출세액 증가':'소유·소득 분류·과세 조건 확인 필요'},'필요경비 차감 후 종합과세 전후 산출세액 비교.',notes)
 expense=max(price*D('.6'),cost);net=price-expense
 taxable=D(0) if net<=50000 else net
 if mode==MODES[1] and taxable+other_optional>3000000:raise ValueError('연간 선택적 분리과세 대상 기타소득금액 합계가 300만원을 초과합니다.')
 old_income=salary-wage_deduction(salary)+other
 old_tax=progressive_tax(max(D(0),old_income-deductions))
 patent_tax=progressive_tax(max(D(0),old_income+taxable-deductions))-old_tax
 if mode==MODES[1]:patent_tax=taxable*D('.20')
 wage_income=salary+price-wage_deduction(salary+price)+other
 wage_tax=progressive_tax(max(D(0),wage_income-deductions))-old_tax
 metrics={'특허 양도 국세 산출세액 증가':patent_tax,'같은 금액 급여 국세 산출세액 증가':wage_tax,'개인 국세 산출세액 차이':wage_tax-patent_tax,'적용 필요경비':expense,'특허 기타소득금액':net,'과세 대상 기타소득금액':taxable,'개인 과세 선택':mode,'법인 당기 국세 산출세액 감소':bracket(corp_base)-bracket(max(D(0),corp_base-amortization)) if corp_confirmed=='예' else '상각액·법인 소득 확인 필요'}
 return FinanceResult(metrics,'개인: 양도 또는 급여 반영 후 국세 산출세액−기존 산출세액. 법인: 확인된 상각 전후 누진세액 차이.',notes,[{'항목':k,'금액 또는 상태':v} for k,v in metrics.items()])
def calculate(name,values):
 if name!=NAME or len(values) not in (9,len(FIELDS[NAME])):raise ValueError('입력 항목을 확인하세요.')
 return patent(*values)
