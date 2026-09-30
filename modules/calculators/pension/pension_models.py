"""Monthly real-value retirement cashflow. No external code or network dependencies."""
from dataclasses import dataclass
from modules.calculators.finance.finance_models import D, num, period, coefficients, FinanceResult

@dataclass
class PensionPlan:
    age:int=45
    retire:int=60
    end:int=90
    expense:float=3000000
    expense_future:bool=False
    assets:float=80000000
    saving:float=500000
    saving_years:int|None=None
    direct:float|None=None
    pension:float=1100000
    pension_start:int=65
    normal_age:int=65
    adjust:bool=True
    pension_growth:float=2.5
    before_rate:float=5
    after_rate:float=3.5
    inflation:float=2.5
    extra:float=300000
    extra_years:int|None=None
    delay:int=5

def monthly(real_rate):return real_rate**(D(1)/12)-1

def contribution_factor(rate,months,paid_months):
    return coefficients(rate,paid_months)[1]*(1+rate)**(months-paid_months)

def calculate(p:PensionPlan):
    age=period(p.age,120,True);retire=period(p.retire,120,True);end=period(p.end,120,True)
    if not age<=retire<end:raise ValueError('현재 나이 ≤ 은퇴 나이 < 자금 사용 종료 나이로 입력해 주세요.')
    start=period(p.pension_start,120,True);normal=period(p.normal_age,65)
    if not 60<=normal<=65:raise ValueError('정상 개시 나이는 60~65세입니다.')
    if p.adjust and abs(start-normal)>5:raise ValueError('자동 조정 수령 시점은 정상 개시 나이의 전후 5년 이내입니다.')
    expense,assets,saving,pension,extra=map(num,[p.expense,p.assets,p.saving,p.pension,p.extra])
    inf,before,after,growth=[num(v,-99,100)/100 for v in (p.inflation,p.before_rate,p.after_rate,p.pension_growth)]
    pre=monthly((1+before)/(1+inf));post=monthly((1+after)/(1+inf));pg=monthly((1+growth)/(1+inf))
    years=retire-age;months=years*12;n=(end-retire)*12
    sy=years if p.saving_years is None else period(p.saving_years,120,True)
    ey=years if p.extra_years is None else period(p.extra_years,120,True)
    if sy>years or ey>years:raise ValueError('납입 기간은 은퇴까지 남은 기간을 넘을 수 없습니다.')
    delay=period(p.delay,120,True)
    if p.expense_future:expense/=(1+inf)**years
    adjustment=D(1)
    if p.adjust:
        adjustment+=D(start-normal)*(D('.06') if start<normal else D('.072'))
    pension*=adjustment
    projected=num(p.direct) if p.direct is not None else assets*(1+pre)**months+saving*contribution_factor(pre,months,sy*12)
    first=max(1,(start-retire)*12+1)
    flows=[];need=D(0)
    for m in range(1,n+1):
        # Start-age anniversary begins a new payment year; first payment is month end.
        elapsed=max(0,(retire-start)*12+m-1)
        receipt=pension*(1+pg)**elapsed if m>=first else D(0)
        draw=expense-receipt
        need+=draw/(1+post)**m
        flows.append((m,receipt,draw))
    need=max(D(0),need);gap=max(D(0),need-projected)
    factor=contribution_factor(pre,months,months)
    required=gap/factor if factor else None
    added=extra*contribution_factor(pre,months,ey*12)
    balance=projected;augmented=projected+added;rows=[];depleted=None
    for m,receipt,draw in flows:
        balance=balance*(1+post)-draw;augmented=augmented*(1+post)-draw
        if balance<0 and depleted is None:depleted=D(retire)+D(m)/12
        if m%12==0 or m==n:
            rows.append({'나이':D(retire)+D(m)/12,'월 생활비':expense,'월 국민연금':receipt,'현재 계획 잔액':balance,'추가 납입 후 잔액':augmented})
    delayed_months=max(0,months-delay*12)
    delayed_factor=contribution_factor(pre,delayed_months,delayed_months)
    metrics={'은퇴시점 필요자산 (오늘 가치)':need,'은퇴시점 예상자산 (오늘 가치)':projected,'부족액':gap,'추가 월 저축액':required if required is not None else ('0원' if gap==0 else '은퇴시점 목돈 보완 필요'),'추가 납입 후 부족액':max(D(0),need-projected-added),'자금 소진 나이':f'{depleted:.1f}세' if depleted else '기간 내 소진 없음','적용 월 국민연금':pension,'미룬 뒤 필요한 월 저축액':gap/delayed_factor if delayed_factor else '납입 가능 기간 없음'}
    notes=['모든 결과는 오늘 구매력 기준입니다. 월 저축액도 실질금액을 유지하도록 물가만큼 증가하는 가정입니다.','월말 납입·인출을 가정하고 국민연금은 개시 나이 도달 후 첫 달 말부터 반영합니다. 실제 최초 지급월과 지급일은 공단 예상연금액 자료로 확인해야 합니다.','수익률·물가·연금 증가율은 고정 가정이며 세금·수수료는 자산 현금흐름에서 제외합니다.','국민연금 자동 조정은 수령 자격을 충족한 경우의 단순 전액 수령 가정입니다. 가입기간·소득에 따른 자격/감액 및 부양가족연금은 별도입니다.','정상 개시 나이는 출생연도에 맞게 지정합니다. 1952년 이전 60세, 1953~56년 61세, 1957~60년 62세, 1961~64년 63세, 1965~68년 64세, 1969년 이후 65세.']
    return FinanceResult(metrics,'월 실질수익률=((1+명목수익률)/(1+물가상승률))^(1/12)−1. 필요자산=은퇴 이후 월 생활비−국민연금 현금흐름의 할인합계. 추가 저축액=부족액÷월말 적립계수.',notes,rows)
