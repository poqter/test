"""Keep shareholder cash and corporate retained earnings distinct."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.tax.global_income_tax import comprehensive
from modules.calculators.tax.earned_income_tax import earned
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='개인사업자·법인 비교계산기';M=10**12
MODES=('일반 국내 배당·금융소득 합계 2천만원 이하','종합과세 등 추가 결정세액 확인 입력','일반 금융소득 자동 비교 (배당 외 세액공제 전)')
FIELDS={NAME:[('대표 급여 차감 전 연간 사업이익',300000000,'원',M),('법인 대표 총급여',120000000,'원',M),
 ('실제 배당 인출액',0,'원',M),('본인 포함 기본공제 인원',1,'명',100),('배당 과세 방식',MODES[0],'선택',MODES),
 ('배당 외 일반 금융소득',0,'원',M),('배당 반영에 따른 추가 국세·지방세 확인액',0,'원',M),
 ('종합과세 추가 세액 확인','아니요','선택',('아니요','예')),('법인만 추가되는 손금 비용 (회사 보험료·유지비 등)',0,'원',M),
 ('대표 실제 국민연금 납부액',0,'원',M),('대표 실제 건강·장기요양보험료',0,'원',M),('대표 실제 고용보험료',0,'원',M),
 ('개인사업자 실제 국민연금 납부액',0,'원',M),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',('아니요','예')),('실제 배당 중 배당가산 적격 확인액',0,'원',M)]}
def compare(profit=300000000,salary=120000000,dividend=0,people=1,mode=MODES[0],other_financial=0,extra_tax=0,confirmed='아니요',cost=0,nps=0,health=0,employment=0,sole_nps=0,small='아니요',eligible_dividend=0):
 profit,salary,dividend,other_financial,extra_tax,cost,nps,health,employment,sole_nps=map(num,(profit,salary,dividend,other_financial,extra_tax,cost,nps,health,employment,sole_nps));people=period(people,100)
 eligible_dividend=num(eligible_dividend)
 if eligible_dividend>dividend:raise ValueError('적격 배당은 실제 배당 인출액 이하여야 합니다.')
 if mode!=MODES[2] and eligible_dividend:raise ValueError('배당가산 적격액은 자동 금융소득 비교 방식에서 입력하세요.')
 if mode not in MODES or small not in ('예','아니요') or confirmed not in ('예','아니요'):raise ValueError('계산 조건을 확인해 주세요.')
 if salary+cost>profit:raise ValueError('급여와 법인 추가비용이 사업이익을 넘는 결손 시나리오는 미지원입니다.')
 if mode==MODES[0]:
  if dividend+other_financial>20000000:raise ValueError('금융소득 합계2천만원 초과 시 종합과세 등 확인 입력을 선택하세요. 일률15.4%로 확정하지 않습니다.')
  if extra_tax:raise ValueError('자동 분리과세 방식의 추가 세액 확인액은0이어야 합니다.')
  dt=dividend*D('.154')
 elif mode==MODES[1]:
  if confirmed!='예':raise ValueError('배당가산·배당세액공제를 검토한 추가 결정세액을 확인해 주세요.')
  if not dividend and extra_tax:raise ValueError('배당0원일 때 배당으로 인한 추가 세액은0원입니다.')
  dt=extra_tax
 else:
  if extra_tax:raise ValueError('자동 비교에서는 추가 세액 확인액을0으로 두세요.')
  dt=D(0)
 base=profit-salary-cost;ct=bracket(base,small=='예')*D('1.1');available=base-ct
 if dividend>available:raise ValueError('배당은 당기 세후 잔여이익 이하여야 합니다. 과거 이익잉여금 배당은 미지원입니다.')
 wt=earned(salary=salary,people=people,nps=nps,health=health,employment=employment).metrics['예상 결정세액 (국세+지방세)']
 sole=comprehensive(revenue=profit,expenses=0,people=people,nps=sole_nps).metrics['예상 결정세액 (국세+지방세)']
 basis='확인 공제액을 적용한 예상 결정세액'
 if mode==MODES[2]:
  from modules.calculators.tax.dividend_grossup import finance_tax
  from modules.calculators.tax.earned_income_tax import wage_deduction
  from modules.calculators.tax.personal_tax_models import progressive_tax
  # Same before-other-credits basis for both business structures. Other
  # finance is present in both; eligible dividends only in the company case.
  wage_income=salary-wage_deduction(salary)
  deductions=D(people)*1500000+nps+health+employment
  wt=progressive_tax(max(D(0),wage_income-deductions))*D('1.1')
  combined=finance_tax(other_financial+dividend-eligible_dividend,eligible_dividend,wage_income,deductions)['배당공제 후 국세']*D('1.1')
  dt=combined-wt
  sole=finance_tax(other_financial,0,profit,D(people)*1500000+sole_nps)['배당공제 후 국세']*D('1.1')
  basis='근로·표준 등 세액공제 전 비교 (배당세액공제만 반영)'
 total=ct+wt+dt;retained=available-dividend;cash=salary+dividend-wt-dt-nps-health-employment
 return FinanceResult({'개인사업자 소득세 추정':sole,'법인·대표 합산세액':total,'개인 대비 세액 차이':sole-total,
 '법인세·지방세':ct,'대표 급여 소득세':wt,'배당 추가 세액':dt,'대표 수령 현금 (입력 보험료 차감)':cash,
 '계산 기준':basis,'법인에 남는 당기 이익':retained,'개인사업자 세후이익 (국민연금 차감)':profit-sole-sole_nps},
 '법인과표=사업이익−급여−추가비용. 법인세후이익에서 배당을 차감해 유보액을 표시. 대표현금=급여+실제배당−급여세−배당추가세−입력보험료. 세부담 비교와 자금 귀속을 별도로 표시.',
 [f'법령 대조 기준일 {AS_OF} · 소득세법55·59·62·129조, 법인세법55조, 지방세법103조의20. 공통 소득세·법인세 산식 재사용.',
 '사업이익은 공통 필요경비 차감 후 금액입니다. 법인 추가비용은 적격 손금만 입력하며 대표 개인 보험료와 중복하지 않습니다. 개인사업자 건강보험료 등은 공통 경비에 적절히 반영된 것을 전제로 합니다.',
 '배당0원은 미인출입니다. 유보액은 대표 개인 현금이 아니며 나중에 인출할 때의 세금도 포함하지 않습니다. 현재 세액 차이만으로 법인 전환이 유리하다고 단정하지 않습니다.',
 '자동 배당세는 국내 일반14% 원천징수 배당이고 다른 금융소득과 합계2천만원 이하인 경우에만 지방세 포함15.4%를 적용합니다. 비영업대금·국외 미원천징수·특례배당 등은 미지원입니다.',
 '금융소득 자동 비교에서는 국내 일반 금융소득과 적격 배당의10%가산·비교과세·배당공제를 계산합니다. 개인·법인 모두 근로·표준·특별 등 다른 세액공제를 적용하기 전 기준으로 맞춥니다. 결과는 최종 결정세액이나 확정 실수령액이 아닙니다. 자동 방식의 배당 추가 세액에는 입력한 배당 외 금융소득의 세금도 포함하며, 다른 금융소득 원금은 대표 수령 현금에 더하지 않습니다. 개인사업자 쪽에도 같은 금융소득을 반영합니다.',
 '확인 입력 방식은 원천징수액이 아니라 배당 포함 총 결정세액과 미포함 결정세액의 차액을 넣습니다. 자동 방식에서는 추가 세액 확인액을0으로 둡니다. 적격 배당 확인액은 실제 배당의 일부이며 중복 가산하지 않습니다.',
 '그 밖의 소득·연금저축·특별공제·법인 공제감면·최저한세·설립 양도세·취득세·건강보험 보수외소득 추가부담·급여 손금 적격 판정은 미반영합니다. 기본공제 인원은 본인 포함, 자격을 확인한 인원입니다.',
 '대표현금에는 입력한 실제 보험료만 차감합니다. 미입력 보험료를 면제로 보는 것은 아닙니다. 개인/법인 전체 경제적 이득 또는 확정 신고세액을 의미하지 않습니다.'],
 [{'항목':k,'금액':v} for k,v in [('공통 사업이익',profit),('법인 추가 비용',cost),('법인 과세표준',base),('급여 지급 후 세후 법인이익',available),('실제 배당',dividend),('법인 유보',retained),('대표 수령 현금',cash)]])
def calculate(name,values):
 if name!=NAME or len(values) not in (14,len(FIELDS[NAME])):raise ValueError('입력 항목을 확인해 주세요.')
 return compare(*values)
