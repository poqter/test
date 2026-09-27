"""Employee severance estimate and post-2023 retirement-income tax schedule."""
from datetime import date
from calendar import monthrange
from decimal import ROUND_DOWN
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
NAME='퇴직금계산기';M=10**12
FIELDS={NAME:[('입사일','2006-09-26','날짜',None),('퇴직일 (마지막 근무일 다음 날)','2026-09-26','날짜',None),('정산 후 새 산정 시작일 (미정산은 입사일)','2006-09-26','날짜',None),('평균임금 산입 3개월 임금총액',15000000,'원',M),('평균임금 산정일수 (0은 실제 3개월 자동)',0,'일',366),('1일 통상임금',0,'원',M),('4주 평균 주 소정근로시간',40,'시간',168),('추가 퇴직 위로금 (과세대상)',0,'원',M),('확인된 법정 비과세액 (총액에 포함)',0,'원',M),('이전 중간정산 퇴직소득금액 (세금 합산 시)',0,'원',M),('이전 중간정산 소득세 (지방세 제외)',0,'원',M)]}
NTS='https://s.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7880&mi=6600'
LABOR='https://www.moel.go.kr/retirementpayCal.do'
def dt(x):
 try:return x if isinstance(x,date) else date.fromisoformat(str(x))
 except (TypeError,ValueError):raise ValueError('날짜 형식을 확인해 주세요.') from None
def shift_months(d,n):
 y,m=divmod(d.year*12+d.month-1+n,12);m+=1
 return date(y,m,min(d.day,monthrange(y,m)[1]))
def tax_years(start,end):
 years=end.year-start.year
 anniversary=date(end.year,start.month,min(start.day,monthrange(end.year,start.month)[1]))
 return max(1,years+(end>anniversary))
def income_tax(gross,years):
 gross=num(gross);years=period(years,120)
 y=D(years)
 deduction=y*1000000 if y<=5 else D(5000000)+(y-5)*2000000 if y<=10 else D(15000000)+(y-10)*2500000 if y<=20 else D(40000000)+(y-20)*3000000
 annual=max(D(0),gross-deduction)*12/y
 exempt=annual if annual<=8000000 else D(8000000)+(annual-8000000)*D('.6') if annual<=70000000 else D(45200000)+(annual-70000000)*D('.55') if annual<=100000000 else D(61700000)+(annual-100000000)*D('.45') if annual<=300000000 else D(151700000)+(annual-300000000)*D('.35')
 base=max(D(0),annual-exempt)
 bands=[(14000000,'.06',0),(50000000,'.15',1260000),(88000000,'.24',5760000),(150000000,'.35',15440000),(300000000,'.38',19940000),(500000000,'.40',25940000),(1000000000,'.42',35940000),(M,'.45',65940000)]
 for ceiling,rate,offset in bands:
  if base<=ceiling:annual_tax=base*D(rate)-offset;break
 else:annual_tax=base*D('.45')-65940000
 tax=annual_tax*y/12
 return tax,[{'단계':'세법상 근속연수','금액 또는 연수':y},{'단계':'과세 퇴직소득','금액 또는 연수':gross},{'단계':'근속연수공제','금액 또는 연수':deduction},{'단계':'환산급여','금액 또는 연수':annual},{'단계':'환산급여공제','금액 또는 연수':exempt},{'단계':'환산 과세표준','금액 또는 연수':base},{'단계':'환산 산출세액','금액 또는 연수':annual_tax},{'단계':'퇴직소득 산출세액','금액 또는 연수':tax}]
def calculate(name,values):
 if name!=NAME or len(values)!=11:raise ValueError('입력 항목 수를 확인해 주세요.')
 hire,end,start=map(dt,values[:3]);wages,denominator,ordinary,hours,bonus,exempt,previous,paid=[num(v,0,f[3]) for v,f in zip(values[3:],FIELDS[NAME][3:])]
 if not hire<=start<end:raise ValueError('입사일 ≤ 산정 시작일 < 퇴직일이어야 합니다.')
 if end.year<2023:raise ValueError('이 화면은 2023년 이후 퇴직의 공제표를 적용합니다.')
 anniversary=date(hire.year+1,hire.month,min(hire.day,monthrange(hire.year+1,hire.month)[1]))
 eligible=end>=anniversary and hours>=15
 days=(end-start).days;denominator=period(denominator,366,True) or (end-max(hire,shift_months(end,-3))).days
 daily=max(wages/D(denominator),ordinary)
 gross=(daily*30*D(days)/365 if eligible else D(0))+bonus
 if exempt>gross:raise ValueError('비과세액은 이번 퇴직급여 총액 이하여야 합니다.')
 if paid and not previous:raise ValueError('이전 납부세액과 이전 퇴직소득금액을 함께 입력해 주세요.')
 if previous and start==hire:raise ValueError('중간정산 합산 시 새 산정 시작일을 입력해 주세요.')
 taxable=gross-exempt;years=tax_years(hire if previous else start,end)
 tax,rows=income_tax(taxable+previous,years);due=tax-paid
 # Scenario amounts only: actual withholding truncation/settlement must be reconciled separately.
 local=due*D('.1')
 notes=['세법 공제표 적용: 2023년 이후 퇴직 · 법령 대조 기준일 2026-09-26','일반 근로자의 퇴직금제도 기준입니다. DC형 적립금·임원 한도·공적연금 특례는 포함하지 않습니다. 원 단위 반올림 추정세액이며 실제 원천징수 단수처리와 차이가 날 수 있습니다.','임금총액은 상여·연차수당 산입분 및 법정 제외기간을 반영한 금액을 입력합니다. 제외기간이 있으면 산정일수도 조정합니다. 1일 통상임금과 비교해 큰 금액을 적용합니다.','중간정산은 새 산정 시작일부터 급여를 계산합니다. 이전 금액을 단순 차감하지 않습니다. 이전 소득·납부세액 입력 시 입사일부터의 연속 근속기간으로 세금 합산을 추정합니다. 중복근무·기간 제외·복수 정산 특례는 별도 반영하지 않습니다.','퇴직 위로금에 근속연수별 자동 비과세나 일률적 60% 감면을 적용하지 않습니다. 비과세액은 해당 법정 근거가 확인된 경우에만 입력합니다.',NTS,LABOR]
 if not eligible:notes.append('계속근로 1년 또는 주15시간 요건 미충족으로 법정 퇴직금은 0원입니다. 별도 약정 지급액은 추가 퇴직 위로금에 입력할 수 있습니다.')
 if due<0:notes.append('기납부세액이 합산 추정세액보다 커서 차감세액이 음수입니다. 환급을 가정한 값입니다.')
 return FinanceResult({'이번 세전 퇴직급여':gross,'예상 차감 소득세':due,'예상 지방소득세':local,'예상 세후 수령액':gross-due-local,'적용 1일 임금':daily},'퇴직금=max(평균임금,통상임금)×30×정산후재직일수/365; 환산급여공제·기본세율 적용 후 ×근속연수/12, 이전 납부세액 차감',notes,rows)
def run():
 from modules.calculators.coverage.coverage_calculator_ui import run as render
 render(NAME,FIELDS,calculate,'퇴직금·퇴직소득세 · 일반 근로자 추정')
