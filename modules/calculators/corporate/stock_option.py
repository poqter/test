"""Exercise gain and confirmed venture exemption; employee national tax delta."""
from datetime import date
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.corporate.invention_compensation import wage_scenario
NAME='주식매수선택권계산기';M=10**12
TYPES=('일반기업·특례 미적용','벤처기업·법정 비과세 요건 확인')
FIELDS={NAME:[('행사 시 1주당 시가',50000,'원',M),('1주당 행사가액',20000,'원',M),('행사 주식수',10000,'주',10**10),('행사이익 제외 연간 과세 총급여',80000000,'원',M),('비과세 적용',TYPES[0],'선택',TYPES),('부여일','2024-01-01','날짜',None),('행사일','2026-09-27','날짜',None),('같은 해 이미 적용한 비과세액 (전체 벤처기업)',0,'원',200000000),('해당 벤처기업 누적 기사용 비과세액',0,'원',500000000),('공통 소득공제 (근로소득공제 제외)',1500000,'원',M),('국내 재직 근로소득·주식수·시가·비과세 내역 확인','미확인','선택',('미확인','확인'))]}
def option(market=50000,strike=20000,shares=10000,salary=80000000,kind=TYPES[0],grant='2024-01-01',exercise='2026-09-27',annual_used=0,total_used=0,deductions=1500000,confirmed='미확인'):
 market,strike,salary,deductions=map(num,(market,strike,salary,deductions));shares=period(shares,10**10,True)
 annual_used=num(annual_used,0,200000000);total_used=num(total_used,0,500000000)
 grant=date.fromisoformat(str(grant));exercise=date.fromisoformat(str(exercise))
 if kind not in TYPES:raise ValueError('기업 유형을 확인하세요.')
 if grant>exercise:raise ValueError('부여일은 행사일보다 늦을 수 없습니다.')
 if exercise.year!=2026 or exercise>date(2026,9,27):raise ValueError('2026년 귀속, 대조일까지의 행사 사례를 지원합니다.')
 if confirmed!='확인':raise ValueError('국내 재직 근로소득 및 법정 적용 요건을 확인해 주세요.')
 gain=max(D(0),(market-strike)*shares)
 exempt=min(gain,D(200000000)-annual_used,D(500000000)-total_used) if kind==TYPES[1] else D(0)
 taxable=gain-exempt
 before=wage_scenario(salary,deductions);after=wage_scenario(salary+taxable,deductions);full=wage_scenario(salary+gain,deductions)
 delta=after['비교 국세']-before['비교 국세']
 return FinanceResult({'행사이익':gain,'이번 비과세액':exempt,'과세 행사이익':taxable,'행사로 증가한 근로소득 국세 추정':delta,'비과세 적용에 따른 국세 감소':full['비교 국세']-after['비교 국세'],'주식 매수에 필요한 현금':strike*shares},
 '(행사 시가−행사가액)×주식수, 이익 최저 0원. 비과세=min(행사이익, 연간 2억원 잔여, 해당 벤처기업 누적 5억원 잔여). 전후 급여의 국세 차이.',[
 '법령 대조일 2026-09-27 · 조세특례제한법 제16조의2 (2026-09-18 시행) · 2026년 귀속.',
 '벤처기업 표시만으로 비과세되지 않습니다. 적격 벤처기업 임원·종업원, 2027-12-31 이전 부여 및 법정 부여 방식·신청 요건을 확인한 경우에 선택합니다. 벤처기업육성법 제16조의3에 따른 부여 또는 코넥스기업의 상법상 부여가 대상입니다.',
 '연간 기사용액은 다른 벤처기업의 비과세액도 포함하고, 누적 기사용액은 해당 벤처기업별로 입력합니다. 같은 해 해당 기업의 사용액은 두 입력에 모두 포함합니다.',
 '국내 재직 근로소득만 있는 경우입니다. 공통 근로소득공제·근로소득세액공제 엔진으로 행사 전후를 비교합니다. 기타 공제·감면, 지방소득세, 사회보험, 신고 단수처리는 제외합니다.',
 '퇴직 후 기타소득, 외국 근무·외국 법인, 납부특례 및 양도 시 과세 특례, 매각 시 양도소득세는 별도 계산 대상입니다. 행사차익은 주식 평가상 이익이며 현금 실수령이 아닙니다.'
 ],[dict(시나리오=k,**v) for k,v in [('행사 전',before),('비과세 적용 행사 후',after),('비과세 미적용 가정',full)]])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력을 확인하세요.')
 return option(*values)
