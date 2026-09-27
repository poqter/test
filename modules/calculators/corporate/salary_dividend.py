"""Three withdrawal scenarios, same personal gross receipt, shared tax engines."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.dividend_grossup import finance_tax
from modules.calculators.tax.earned_income_tax import wage_deduction
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.social_insurance import insurance, floor10
NAME='급여vs배당 비교계산기';M=10**12
YN=('아니오','예'); GROSS=('배당가산 적격 배당','배당가산 비대상 배당')
FIELDS={NAME:[('추가 인출 전 세무상 법인소득',500000000,'원',M),('적격 미사용 이월결손금',0,'원',M),('현재 연간 과세 총급여',120000000,'원',M),('기존 일반 금융소득 (배당가산 비대상)',5000000,'원',M),('본인 지분율',100.0,'%',100),('추가로 받을 세전 금액',100000000,'원',M),('국민연금·건강보험 부과 대상',YN[1],'선택',YN),('고용·산재 적용 근로자 해당',YN[0],'선택',YN),('확인된 산재보험 총요율',0.0,'%',100),('이월결손금 100% 공제 대상',YN[1],'선택',YN),('법인세 소규모법인 20% 첫구간 해당',YN[0],'선택',YN),('새 배당의 배당가산 구분',GROSS[0],'선택',GROSS),('공통 소득공제 (근로소득공제 제외)',1500000,'원',M),('전체 주주에게 지급 가능한 배당가능이익 확인액',500000000,'원',M),('임원보수 손금·배당 절차·국내 거주자·2026년 12개월 가정 확인','미확인','선택',('미확인','확인'))]}
def annual_insurance(salary,on,employee,accident):
 if on=='아니오' and employee=='아니오':return D(0),D(0)
 own=company=D(0)
 for month in range(1,13):
  r=insurance(month,salary/12,salary/12,salary/12,'예' if on=='예' else '아니요','예' if on=='예' else '아니요','예' if employee=='예' else '아니요','예' if employee=='예' else '아니요',accident_rate=str(accident if employee=='예' else 0))
  own+=r.metrics['본인 부담 월 보험료'];company+=r.metrics['사업주 부담 월 보험료']
 return own,company

def nonwage_health(financial):
 monthly=min(D(4591740),max(D(0),financial-D(20000000))/12*D('.0719'))
 health=floor10(monthly);care=floor10(health*D('.009448')/D('.0719'))
 return (health+care)*12

def compare(profit=500000000,loss=0,salary=120000000,other_fin=5000000,share=100,withdraw=100000000,on='예',employee='아니오',accident=0,full_loss='예',small='아니오',grossup=GROSS[0],deductions=1500000,distributable=500000000,confirmed='미확인'):
 profit,loss,salary,other_fin,withdraw,deductions,distributable=map(num,(profit,loss,salary,other_fin,withdraw,deductions,distributable));share=num(share,0,100);accident=num(accident,0,100)
 if share<=0:raise ValueError('배당 비교에는 0% 초과 본인 지분율이 필요합니다.')
 if any(v not in YN for v in (on,employee,full_loss,small)) or grossup not in GROSS:raise ValueError('적용 조건을 확인하세요.')
 if confirmed!='확인':raise ValueError('손금 요건·배당가능이익·국내 소득 구분 및 비교 가정을 확인해 주세요.')
 def ct(income):
  income=max(D(0),income);base=income-min(loss,income*(1 if full_loss=='예' else D('.8')))
  return bracket(base,small=='예')*D('1.1')
 before_own,before_company=annual_insurance(salary,on,employee,accident)
 before_tax=finance_tax(other_fin,0,salary-wage_deduction(salary),deductions)['배당공제 후 국세']*D('1.1')
 before_health=nonwage_health(other_fin) if on=='예' else D(0)
 corp_before=ct(profit);rows=[];metrics={}
 for label,ratio in [('급여 100%',D(1)),('배당 100%',D(0)),('혼합 50:50',D('.5'))]:
  added_salary=withdraw*ratio;dividend=withdraw-added_salary;all_dividends=dividend/share*100
  own,company=annual_insurance(salary+added_salary,on,employee,accident);own_delta=own-before_own;company_delta=company-before_company
  ordinary=other_fin+(dividend if grossup==GROSS[1] else 0);eligible=dividend if grossup==GROSS[0] else 0
  t=finance_tax(ordinary,eligible,salary+added_salary-wage_deduction(salary+added_salary),deductions)
  personal_delta=t['배당공제 후 국세']*D('1.1')-before_tax
  extra_health=(nonwage_health(other_fin+dividend)-before_health) if on=='예' else D(0)
  corp=ct(profit-added_salary-company_delta);net=withdraw-personal_delta-own_delta-extra_health
  feasible=all_dividends<=distributable
  metrics[label+' 개인 수령 추정']=net if feasible else '배당가능이익 확인액 부족'
  rows.append({'시나리오':label,'추가 급여':added_salary,'본인 배당':dividend,'전체 주주 배당 필요액':all_dividends,'개인 세금 증가 추정':personal_delta,'본인 보수보험 증가':own_delta,'보수 외 보험 증가 가정':extra_health,'회사 보험 증가':company_delta,'법인세·지방세 추정':corp,'법인세 감소 추정':corp_before-corp,'회사 지출 증가 (법인세 효과 반영)':added_salary+company_delta+all_dividends-(corp_before-corp),'배당가산액':t['배당가산액'],'배당세액공제':t['배당세액공제'],'개인 수령 추정':net,'배당가능이익 확인': '범위 내' if feasible else '부족'})
 notes=['법령·요율 대조일 2026-09-27 · 2026년 개시 12개월 법인·국내 거주 개인의 일반 급여/배당 시나리오. 법인세 10/20/22/25%, 소규모 해당 시 첫 구간 20%.',
 '동일한 본인 세전 추가 수령액을 비교합니다. 회사의 동일 비용 예산 비교가 아닙니다. 지분율 100% 미만이면 전체 주주에게 필요한 비례 배당액도 표시합니다. 차등배당은 제외합니다.',
 '배당가산 적격 부분은 금융소득 2천만원 초과분 범위에서 10% 가산하고 비교산출세액을 밑돌지 않는 범위로 배당세액공제합니다. 기타 금융소득은 국내 14% 일반 원천징수·가산 비대상으로 한정합니다.',
 '근로소득공제는 자동 반영합니다. 입력 공통 소득공제를 모든 시나리오에 동일 적용하며, 보험료 증가에 따른 소득공제 변화·근로소득 및 특별세액공제·감면은 미반영입니다. 따라서 실수령 확정액이나 최적 절세안이 아닌 공제 가정에 따른 비교입니다.',
 '급여를 12개월 균등 지급하고 해당 월 법정 상하한·요율을 적용하는 보험료 시나리오입니다. 임원은 고용·산재 적용 여부가 다르므로 기본적으로 제외합니다. 납부예외·지역가입·정산·보수신고 시차는 제외합니다.',
 '배당에 따른 보수 외 보험료는 현재 2026년 요율이 동일하게 적용된다고 가정한 연간 비교이며 실제 다음 연도 고지액이 아닙니다. 다른 보수 외 소득·보험료 공제 시차는 반영하지 않습니다.',
 '배당가능이익은 상법상 검토한 전체 주주 지급 가능액이며 회사 당기 세전이익과 다릅니다. 자금 조달·유동성·퇴직금 증가·공제감면·최저한세·특별 법인지방세 조정은 별도 검토합니다.']
 return FinanceResult(metrics,'급여·배당을 100:0, 0:100, 50:50으로 분리하여 세금·보험료 증가분을 계산합니다. 본인 수령 추정=추가 세전금액−개인세 증가−보험 증가.',notes,rows)
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return compare(*values)
