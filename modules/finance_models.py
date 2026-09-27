"""Independent deterministic financial models; KRW, nominal annual rates (%).

UI, charts and exports consume the same numeric result. No external calls.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP, ROUND_DOWN
from typing import Any

D = Decimal
ZERO = D(0)
ONE = D(1)

@dataclass
class FinanceResult:
    metrics: dict[str, Any]
    formula: str
    assumptions: list[str]
    rows: list[dict] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)
    rounding: str = ROUND_HALF_UP

    def display(self):
        result = {}
        for key,value in self.metrics.items():
            unit = self.units.get(key,'원')
            if isinstance(value,str):
                result[key] = value
            else:
                places = D('.01') if unit == '%' else D('.1') if unit in ('개월','년') else ONE
                result[key] = f'{D(value).quantize(places,rounding=self.rounding):,}{unit}'
        return result


def num(value, minimum=0, maximum=10**12):
    try:
        n = D(str(value))
    except (ValueError, InvalidOperation):
        raise ValueError('숫자를 입력해 주세요.') from None
    if not n.is_finite() or not D(str(minimum)) <= n <= D(str(maximum)):
        raise ValueError(f'입력 범위는 {minimum} ~ {maximum}입니다.')
    return n


def period(value, maximum=1440, allow_zero=False):
    n = num(value,0 if allow_zero else 1,maximum)
    if n != int(n):
        raise ValueError('납입 횟수는 정수여야 합니다.')
    return int(n)


def coefficients(rate, n, beginning=False):
    """Accumulation factor and future value of 1 paid each period."""
    if rate <= -1:
        raise ValueError('기간 수익률은 -100%보다 커야 합니다.')
    growth = (1+rate)**n
    annuity = D(n) if rate == 0 else (growth-1)/rate
    return growth, annuity*(1+rate if beginning else 1)


def fv(principal, payment, rate, n, beginning=False):
    growth, annuity = coefficients(rate,n,beginning)
    return principal*growth + payment*annuity


def schedule(principal,payment,rate,n,per_year,beginning=False):
    rows=[]
    checkpoints=set(range(per_year,n+1,per_year))|{0,n}
    for k in sorted(checkpoints):
        balance=fv(principal,payment,rate,k,beginning)
        paid=principal+payment*k
        rows.append({'경과 연수':float(D(k)/per_year),'납입 원금':paid,'누적 수익':balance-paid,'총 자금':balance})
    return rows


def tvm(mode, principal=0, payment=0, target=0, years=10, rate=5,
        frequency=12, compounding=None, beginning=False):
    """Solve FV, PMT, nominal annual rate, PV or first whole payment period.

    frequency = payments per year. compounding = interest credits per year.
    Different frequencies use equivalent periodic rates, not a second formula.
    """
    with localcontext() as ctx:
        ctx.prec=48
        p,c,t = [num(x) for x in (principal,payment,target)]
        freq=period(frequency,365)
        if freq not in (1,2,4,12,365):
            raise ValueError('지원하지 않는 납입 주기입니다.')
        comp=period(compounding if compounding is not None else freq,365)
        if comp not in (1,2,4,12,365):
            raise ValueError('지원하지 않는 복리 주기입니다.')
        y=num(years,1/freq,120)
        n=period(y*freq,120*freq)
        annual=num(rate,-99.99,100)/100
        def periodic(a): return (1+a/comp)**(D(comp)/freq)-1
        r=periodic(annual)
        metadata={}
        if mode=='payment':
            growth,annuity=coefficients(r,n,beginning)
            c=max(ZERO,(t-p*growth)/annuity)
            metadata={'필요 정기 납입액':c}
        elif mode=='principal':
            growth,annuity=coefficients(r,n,beginning)
            p=max(ZERO,(t-c*annuity)/growth)
            metadata={'필요 시작 자금':p}
        elif mode=='rate':
            if p+c==0:
                raise ValueError('시작 자금 또는 정기 납입액이 있어야 수익률을 계산할 수 있습니다.')
            low,high=D('-.9999'),D(1)
            if not fv(p,c,periodic(low),n,beginning)<=t<=fv(p,c,periodic(high),n,beginning):
                raise ValueError('필요 연 수익률이 계산 범위(-99.99%~100%) 밖입니다.')
            for _ in range(180):
                mid=(low+high)/2
                if fv(p,c,periodic(mid),n,beginning)<t:low=mid
                else:high=mid
            annual=(low+high)/2;r=periodic(annual)
            metadata={'필요 연 수익률':annual*100}
        elif mode=='period':
            if p>=t:n=0
            else:
                limit=120*freq
                # First actual payment date reaching target; cannot round down.
                if fv(p,c,r,limit,beginning)<t:
                    raise ValueError('현재 조건으로 120년 이내에 목표에 도달하지 않습니다.')
                lo,hi=0,limit
                while lo<hi:
                    mid=(lo+hi)//2
                    if fv(p,c,r,mid,beginning)>=t:hi=mid
                    else:lo=mid+1
                n=lo
            metadata={'필요 납입 횟수':D(n),'필요 기간':D(n)/freq}
        elif mode!='future':
            raise ValueError('지원하지 않는 계산 방식입니다.')
        future=fv(p,c,r,n,beginning);paid=p+c*n
        metrics={**metadata,'예상 최종 자금':future,'투입 원금 합계':paid,'예상 운용 수익':future-paid}
        return FinanceResult(metrics,
            'FV = P(1+i)^n + C × ((1+i)^n−1)/i × (기초 납입이면 1+i). i = (1+연 명목수익률/복리횟수)^(복리횟수/납입횟수)−1. i=0이면 FV=P+C×n.',
            ['수익률 일정, 세금·수수료·물가 미반영.','필요 기간은 목표에 도달하는 최초의 납입일로 올림합니다.','역산한 납입액·시작 자금은 반올림 전 값을 이용합니다. 실제 원 단위 납입에는 소액 차이가 있습니다.'],
            schedule(p,c,r,n,freq,beginning),{'필요 연 수익률':'%','필요 납입 횟수':'회','필요 기간':'년'})


def future_value(principal=10000000, annual_payment=200000, years=20, rate=6, beginning=True):
    return tvm('future',principal=principal,payment=annual_payment,years=years,rate=rate,frequency=1,beginning=beginning)


def investment(mode='future',principal=20000000,monthly=200000,target=100000000,
               years=15,rate=6,frequency=12):
    """Reference's quarterly/annual mode groups monthly deposits at period end."""
    frequency=period(frequency,12)
    if frequency not in (1,2,4,12):raise ValueError('지원하지 않는 복리 주기입니다.')
    result=tvm(mode,principal=principal,payment=num(monthly)*12/frequency,target=target,
               years=years,rate=rate,frequency=frequency)
    if mode=='payment':
        result.metrics={'필요 월 납입액':result.metrics.pop('필요 정기 납입액')*frequency/12,**result.metrics}
    result.assumptions.insert(0,'월 저축액을 복리 주기별로 합산하여 각 주기 말에 투입합니다. 분기 복리는 월 저축액의 3배를 분기 말에 납입합니다.')
    return result


def compound(principal=10000000,years=10,rate=5,frequency=12):
    result=tvm('future',principal=principal,years=years,rate=rate,frequency=frequency)
    result.rounding=ROUND_DOWN
    result.assumptions.append('원 미만 절사. 연 이자율은 명목이자율입니다.')
    return result


def present_value(mode='lump',amount=10000000,years=10,rate=6,beginning=True):
    with localcontext() as ctx:
        ctx.prec=48
        amount=num(amount);n=period(years,120);r=num(rate,-99.99,100)/100
        growth,annuity=coefficients(r,n,beginning)
        if mode=='lump':
            present=amount/growth
            return FinanceResult({'현재가치':present,'현재가치와 미래금액의 차이':amount-present},
                '현재가치 = 미래 일시금 ÷ (1+연 할인율)^연수',['연간 할인, 세금·수수료 미반영.'])
        if mode!='annuity':raise ValueError('지원하지 않는 현재가치 계산 방식입니다.')
        future=amount*annuity;present=future/growth;paid=amount*n
        return FinanceResult({'현재가치':present,'미래가치':future,'총 원금':paid,'총 이자':future-paid},
            '연금 현재가치 = 정기 입금액 × 연금종가계수 ÷ (1+연 할인율)^연수. 연초 납입은 계수에 (1+연 할인율)을 곱합니다.',
            ['매년 동일 금액을 선택한 시점에 납입합니다. 세금·수수료 미반영.'],schedule(ZERO,amount,r,n,1,beginning))


def emergency(expense,months=6,cash=0,deposits=0,other=0,debt=0):
    expense=num(expense,1);months=period(months,1200)
    cash,deposits,other,debt=[num(x) for x in (cash,deposits,other,debt)]
    liquid=cash+deposits+other;net=max(ZERO,liquid-debt);available=net;need=expense*months
    return FinanceResult({'부족한 비상자금':max(ZERO,need-net),'목표 대비 충족률':net/need*100,
        '순유동자산':net,'필요 비상자금':need,'유동자산 합계':liquid,'사용 가능한 생활비 기간':available/expense},
        '순유동자산 = 현금 + 단기예적금 + 기타유동자산 − 단기부채. 필요액 = 월 필수지출 × 목표 개월.',
        ['자산은 즉시 사용할 수 있는 금액으로 입력합니다. 부채가 자산을 넘으면 사용 가능한 순유동자산은 0으로 표시합니다.'],units={'목표 대비 충족률':'%','사용 가능한 생활비 기간':'개월'})


def goals(items,budget=0):
    if not 1<=len(items)<=3:raise ValueError('목표는 1~3개 입력해 주세요.')
    budget=num(budget);rows=[];total=ZERO
    for item in items:
        target=num(item.get('target',0));p=num(item.get('principal',0));y=num(item.get('years',10),1,120)
        annual=num(item.get('rate',4),-99.99,100)/100
        r=(1+annual)**(ONE/12)-1;n=period(y*12)
        growth,annuity=coefficients(r,n)
        payment=max(ZERO,(target-p*growth)/annuity)
        total+=payment
        rows.append({'목표':str(item.get('name','목표'))[:100],'목표 금액':target,'기간 (년)':y,'월 필요액':payment})
    return FinanceResult({'매달 필요한 저축액':total,'부족액':max(ZERO,total-budget),'저축 가능액':budget},
        '목표별 월 필요액 = max(0, 목표 − 현재자금×(1+월수익률)^개월) ÷ 월말 적립계수. 월수익률=(1+연 유효수익률)^(1/12)−1. 목표별 필요액을 합산합니다.',
        ['각 목표의 준비 자금을 중복 배정하지 마세요. 물가·세금·수수료 미반영.'],rows)


def opportunity(monthly,years=20,rate=4):
    monthly=num(monthly,1);years=period(years,120);r=num(rate,-99.99,100)/1200
    future=fv(ZERO,monthly,r,years*12);rows=[]
    for delay in (5,10):
        if delay>=years:
            rows.append({'시작 지연 (년)':delay,'지연 후 자금':ZERO,'줄어드는 금액':future,'목표 달성 월 납입액':'남은 기간 없음'})
        else:
            _,a=coefficients(r,(years-delay)*12)
            delayed=monthly*a
            rows.append({'시작 지연 (년)':delay,'지연 후 자금':delayed,'줄어드는 금액':future-delayed,'목표 달성 월 납입액':future/a})
    return FinanceResult({'기간 후 모였을 금액':future,'월 금액':monthly,'기간':D(years)},
        '월말 적립. 월수익률=연 명목수익률/12. 5년·10년 지연 시 같은 종료일까지 적립한 미래가치를 비교합니다.',
        ['수익률 일정, 세금·수수료·물가 미반영.'],rows,{'기간':'년'})
