"""Pure Decimal scenario calculations; amounts are KRW, rates are decimals."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

D = Decimal
ZERO = D(0)


def number(value, low=0, high=10**12):
    try:
        result = D(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("숫자를 입력해 주세요.") from None
    if not result.is_finite() or not D(str(low)) <= result <= D(str(high)):
        raise ValueError(f"입력 범위는 {low:,} 이상 {high:,} 이하입니다.")
    return result


def integer(value, high=1200):
    result = number(value, high=high)
    if result != result.to_integral_value():
        raise ValueError("기간과 나이는 정수로 입력해 주세요.")
    return int(result)


def won(value):
    with localcontext() as ctx:
        ctx.prec = 60
        return D(value).quantize(D(1), rounding=ROUND_HALF_UP)


def accumulation(rate, months):
    rate = number(rate, -.20, .30)
    months = integer(months)
    growth = (1 + rate) ** (D(months) / 12)
    if rate == 0:
        return growth, D(months)
    monthly = (1 + rate) ** (D(1) / 12) - 1
    return growth, (growth - 1) / monthly


def calculate(kind, values):
    """Return unrounded output; UI/export apply identical KRW rounding."""
    with localcontext() as ctx:
        ctx.prec = 60
        def money(key): return number(values[key])
        def count(key, high=1200): return integer(values[key], high)
        if kind == 'total':
            p, n, k = money('premium'), count('months'), count('paid')
            if k > n: raise ValueError("기납입 개월은 전체 납입 개월을 넘을 수 없습니다.")
            return {'총 납입 예정': p*n, '기납입 추정': p*k, '향후 납입 예정': p*(n-k)}
        if kind == 'coverage':
            need = money('living')*12*count('years', 100)+money('debt')+money('oneoff')
            return {'총 필요 재원': need, '가정상 부족 재원': max(ZERO, need-money('assets')-money('existing'))}
        if kind == 'income':
            monthly = max(ZERO, money('spending')-money('income'))
            need = monthly*count('duration')
            return {'월 부족액': monthly, '기간 필요액': need, '추가 준비액': max(ZERO, need-money('reserve'))}
        if kind == 'waiver':
            return {'조건 충족 가정 시 면제액': money('premium')*count('months')*number(values['ratio'], 0, 100)/100}
        if kind == 'family':
            need = money('living')*12*count('years', 100)
            return {'생활자금 필요액': need, '추가 준비액': max(ZERO, need-money('assets'))}
        if kind == 'education':
            annual, years, wait = money('annual'), count('years', 100), count('wait', 100)
            inflation = number(values['inflation'], -.10, .30)
            need = sum((annual*(1+inflation)**(wait+k) for k in range(years)), ZERO)
            return {'예상 교육비 총액': need, '추가 준비액': max(ZERO, need-money('assets'))}
        if kind == 'debt':
            return {'부채 정리 부족액': max(ZERO, money('debt')-money('assets'))}
        if kind in ('saving', 'goal'):
            p, n = money('assets'), count('months')
            growth, factor = accumulation(values['rate'], n)
            if kind == 'saving':
                if n == 0: raise ValueError("월 저축액 계산에는 1개월 이상의 기간이 필요합니다.")
                gap = max(ZERO, money('target')-p*growth)
                return {'목표 달성 월 저축액': gap/factor, '현재 자금의 예상 미래가치': p*growth}
            return {'예상 적립액': p*growth+money('saving')*factor, '투입 원금 합계': p+money('saving')*n}
        if kind == 'inflation':
            future = money('amount')*(1+number(values['inflation'], -.10, .30))**count('years', 100)
            return {'미래 필요액': future, '현재 대비 증감액': future-money('amount')}
        if kind == 'retirement':
            age, retire, end = count('age', 120), count('retire', 120), count('end', 120)
            if not age <= retire < end: raise ValueError("현재 나이 ≤ 은퇴 나이 < 계획 종료 나이로 입력해 주세요.")
            monthly = max(ZERO, money('living')-money('pension'))*(1+number(values['inflation'], -.10, .30))**(retire-age)
            need = monthly*12*(end-retire)
            return {'은퇴 시점 월 부족액': monthly, '은퇴 기간 필요액': need, '추가 준비액': max(ZERO, need-money('assets'))}
        raise ValueError("지원하지 않는 계산 모드입니다.")
