"""Annual pay comparison; labels do not create a tax exemption."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.tax.earned_income_tax import earned
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='상여금·복리후생비 비교계산기';M=10**12;YN=('아니요','예')
FIELDS={NAME:[('1인당 추가 지급·혜택 금액',1000000,'원',M),('동일 급여·공제 조건의 인원',20,'명',100000),
 ('1인당 추가 지급 전 연간 과세 총급여',60000000,'원',M),('본인 포함 기본공제 인원',1,'명',100),
 ('기존 연간 국민연금 납부액',0,'원',M),('기존 연간 건강·요양보험료',0,'원',M),('기존 연간 고용보험료',0,'원',M),
 ('복지안 중 법정 비과세·근로소득 제외 확인액',0,'원',M),('복지안 제외금액의 법적 요건 확인','아니요','선택',YN),
 ('상여안 추가 본인 보험료: 연금,건강요양,고용 (미확인 빈칸)','','문자',100),
 ('복지안 추가 본인 보험료: 연금,건강요양,고용 (미확인 빈칸)','','문자',100),
 ('상여안 추가 회사 보험료 1인당 확인액 (미확인 빈칸)','','문자',30),
 ('복지안 추가 회사 보험료 1인당 확인액 (미확인 빈칸)','','문자',30)]}
def parse_insurance(value):
 if not str(value).strip():return None
 values=str(value).split(',')
 if len(values)!=3:raise ValueError('본인 추가 보험료를 연금,건강요양,고용 순서로 입력하세요.')
 return tuple(num(x.strip()) for x in values)
def compare(amount=1000000,count=20,salary=60000000,people=1,nps=0,health=0,employment=0,exempt=0,confirmed='아니요',bonus_own='',welfare_own='',bonus_company='',welfare_company=''):
 amount,salary,nps,health,employment,exempt=map(num,(amount,salary,nps,health,employment,exempt));count=period(count,100000);people=period(people,100)
 if amount*count>M or salary+amount>M:raise ValueError('총 지급액 또는 합산 급여는1조원 이하여야 합니다.')
 if confirmed not in YN or exempt>amount:raise ValueError('제외금액은 지급액 이하여야 합니다.')
 if exempt and confirmed!='예':raise ValueError('복지안 제외금액의 법적 요건을 확인하세요. 미확인 시 제외액0원으로 비교합니다.')
 own=[parse_insurance(bonus_own),parse_insurance(welfare_own)]
 company=[None if not str(x).strip() else num(str(x).strip()) for x in (bonus_company,welfare_company)]
 before=earned(salary=salary,people=people,nps=nps,health=health,employment=employment).metrics['예상 결정세액 (국세+지방세)']
 rows=[];taxes=[];nets=[];costs=[]
 for i,(name,added) in enumerate((('상여 지급',amount),('복지 지급',amount-exempt))):
  ins=own[i] or (D(0),D(0),D(0))
  after=earned(salary=salary+added,people=people,nps=nps+ins[0],health=health+ins[1],employment=employment+ins[2]).metrics['예상 결정세액 (국세+지방세)']
  tax=after-before;net=(amount-tax-sum(ins))*count if own[i] is not None else '본인 추가 보험료 확인 필요'
  cost=(amount+company[i])*count if company[i] is not None else '회사 추가 보험료 확인 필요'
  taxes.append(tax*count);nets.append(net);costs.append(cost)
  rows.append({'방식':name,'1인당 과세급여 증가':added,'전체 추가 소득세 추정':tax*count,'전체 순혜택 추정':net,'전체 회사 지출':cost})
 diff_net=nets[1]-nets[0] if all(not isinstance(x,str) for x in nets) else '보험료 미확인'
 diff_cost=costs[0]-costs[1] if all(not isinstance(x,str) for x in costs) else '보험료 미확인'
 return FinanceResult({'총 지급·혜택 금액':amount*count,'상여안 추가 소득세 추정':taxes[0],'복지안 추가 소득세 추정':taxes[1],
 '상여안 전체 순혜택 추정':nets[0],'복지안 전체 순혜택 추정':nets[1],
 '복지안 선택 시 직원 순혜택 증가':diff_net,'복지안 선택 시 회사 지출 감소':diff_cost},
 '동일 조건 직원의 추가 지급 전후 근로소득 결정세액 차이×인원. 제외 요건 확인액만 복지안 과세급여에서 제외. 확인된 보험료 증가를 반영해 순혜택과 회사 지출 비교.',
 [f'법령 대조 기준일 {AS_OF} · 소득세법20·47·55·59조 및 공통 근로소득세 계산식. 2026년 연간 비교이며 지급월 원천징수액이 아닙니다.',
 '복리후생비라는 계정명이나 현물·상품권 지급만으로 비과세가 되지 않습니다. 법정 근거가 확인되지 않은 명절 상여·선물은 두 안 모두 과세 가정입니다. 30만원을 보편적인 비과세 기준으로 적용하지 않습니다.',
 '동일한 급여·기본공제·보험료 조건의 직원 집단만 비교합니다. 급여가 다른 직원을 평균급여로 묶으면 실제 합계와 달라집니다. 특별공제·자녀·세액감면 등 다른 항목은0으로 가정합니다.',
 '추가 보험료는 지급월 즉시 일률 부과되는 것이 아닙니다. 보험별 보수 정의·상한·정산·국민연금 반영시기를 확인한 금액을 입력하세요. 본인 보험료가 빈칸이면 추가 보험료 공제 전 소득세만 표시하고 순혜택은 미확인으로 남깁니다.',
 '0,0,0은 본인 추가보험료가 실제0으로 확인된 경우에만 입력합니다. 회사보험료는 산재 및 고용안정분 등을 포함한 확인액입니다. 두 안 모두 입력해야 차이를 계산합니다.',
 '현물의 순혜택은 평가금액에서 세금·보험료를 뺀 경제적 비교이며 현금 실수령액이 아닙니다. 물품 취득원가와 평가액 차이·부가세·회사 법인세 효과·임원상여 손금한도는 미반영입니다.'],rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return compare(*values)
