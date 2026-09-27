"""Independent tax scenarios. Reference cases are observations, not authority.

These two models deliberately state their supported tax scope in every export.
Validated scenarios remain distinct from filing or eligibility automation.
"""
from modules.calculators.finance.finance_models import D, FinanceResult, num, period

AS_OF = '2026-09-26'
ISA = 'ISA 절세계산기'
FINANCIAL = '금융소득종합과세계산기'
NAMES = (ISA, FINANCIAL)
M = 10**12
FIELDS = {
    ISA: [('연간 납입액', 20000000, '원', 20000000),
          ('운용 기간', 5, '년', 100), ('연 수익률', 4, '%', 100),
          ('비과세 한도', '일반형 200만원', '선택', ('일반형 200만원', '서민형·농어민 요건 충족 400만원'))],
    FINANCIAL: [('일반 이자소득', 15000000, '원', M),
                ('배당가산 대상이 아닌 일반 배당소득', 12000000, '원', M),
                ('그 밖의 종합소득금액 (필요경비 차감 후)', 50000000, '원', M),
                ('적용 가능한 소득공제 합계', 1500000, '원', M),
                ('배당가산 대상 국내 배당소득 (확인된 금액)', 0, '원', M)],
}


def progressive_tax(base):
    base = num(base, 0, 3*M)
    for ceiling, rate, deduction in (
        (14000000, '.06', 0), (50000000, '.15', 1260000),
        (88000000, '.24', 5760000), (150000000, '.35', 15440000),
        (300000000, '.38', 19940000), (500000000, '.40', 25940000),
        (1000000000, '.42', 35940000), (3*M, '.45', 65940000),
    ):
        if base <= ceiling:
            return base*D(rate)-deduction


def isa(annual=20000000, years=5, rate=4, allowance=2000000):
    annual = num(annual, 0, 20000000)
    years = period(years, 100)
    if years < 3:
        raise ValueError('세제혜택 비교에는 3년 이상 운용 기간을 입력해 주세요.')
    rate = num(rate, 0, 100)/100
    allowance = num(allowance, 2000000, 4000000)
    if allowance not in (2000000, 4000000):
        raise ValueError('비과세 한도는 200만원 또는 요건을 충족한 400만원입니다.')
    paid = balance = general = D(0)
    rows = []
    for year in range(1, years+1):
        contribution = min(annual, D(100000000)-paid)
        paid += contribution
        balance = (balance+contribution)*(1+rate)
        general = (general+contribution)*(1+rate*(1-D('.154')))
        rows.append({'경과 연수': year, '해당 연도 납입액': contribution,
                     '누적 납입액': paid, 'ISA 세전 평가액': balance,
                     '일반계좌 세후 평가액': general})
    profit = balance-paid
    tax = max(D(0), profit-allowance)*D('.099')
    net = balance-tax
    return FinanceResult(
        {'ISA 세후 수익': net-paid, 'ISA 세후 만기 자금': net,
         '일반계좌 세후 만기 자금': general, 'ISA 이용 시 만기 자금 차이': net-general,
         'ISA 세금 (지방세 포함)': tax, '총 납입액': paid},
        '매년 초 납입 후 연복리. 총 납입액 1억원 도달 후 추가 납입 중지. '
        'ISA 세금=max(0, 만기수익−비과세한도)×9.9%. '
        '일반계좌는 매년 발생 수익에 15.4% 과세 후 재투자.',
        [f'법령 대조 기준일 {AS_OF} · 조세특례제한법 제91조의18 (2026-09-18 시행본).',
         '신규 계좌·연초 정액 납입·3년 이상 유지 가정. 연 납입액 최대 2천만원, 총 1억원. 미사용 한도 이월·중도인출·기존 재형저축 등은 미반영.',
         '400만원 한도는 소득 등 법정 요건을 충족한 서민형·농어민에 적용합니다. 나이가 젊다는 이유만으로 적용되지 않습니다.',
         '가입 자격은 금융기관에서 확인해야 합니다. 전 수익이 과세대상 이자라고 가정한 비교로, 국내주식 매매차익·손실통산·수수료·금융소득종합과세는 미반영합니다.',
         '만기 자금 차이는 세액 차이와 과세이연에 따른 복리 차이를 함께 포함합니다. 원 단위 반올림 추정치입니다.'], rows)


def financial(interest=15000000, dividends=12000000, other=50000000, deductions=1500000, eligible_dividend=0):
    interest, dividends, other, deductions = [num(v) for v in (interest, dividends, other, deductions)]
    from modules.calculators.tax.dividend_grossup import finance_tax
    eligible_dividend = num(eligible_dividend)
    income = interest+dividends+eligible_dividend
    other_base = max(D(0), other-deductions)
    ordinary_other_tax = progressive_tax(other_base)
    withheld = income*D('.14')
    excess = max(D(0), income-20000000)
    base = max(D(0), other+excess-deductions)
    comparison = ordinary_other_tax+withheld
    method_a = progressive_tax(base)+D(2800000) if income>20000000 else comparison
    taxes = finance_tax(interest+dividends, eligible_dividend, other, deductions)
    method_a = taxes["일반산출세액"]
    national = taxes["배당공제 후 국세"]
    local = national*D('.1')
    total = national+local
    return FinanceResult(
        {'국세·지방세 합계 (공제 전 추정)': total,
         '금융소득에 따른 세부담 증가분': total-ordinary_other_tax*D('1.1'),
         '일반 금융소득 원천징수 추정액': withheld*D('1.1'),
         '일반 원천징수 대비 추가 부담': max(D(0), total-comparison*D('1.1')),
         '국세 산출세액': taxes['국세 산출세액'], '배당가산액': taxes['배당가산액'], '배당세액공제': taxes['배당세액공제'], '지방세 추정액': local},
        '금융소득 2천만원 초과: A=기본세율(max(0, 기타소득+초과금액−공제))+2천만원×14%; '
        'B=기본세율(max(0, 기타소득−공제))+금융소득×14%; 국세=max(A,B)−배당세액공제. 적격 배당의 종합과세 초과분에 10% 가산하며 공제는 비교세액 초과분 한도. '
        '2천만원 이하 국내 원천징수 일반소득은 B로 비교. 지방세는 국세의 10%로 추정.',
        [f'법령 대조 기준일 {AS_OF} · 소득세법 제62조 (2026-07-01 시행본), 국세청 기본세율표.',
         '국내에서 14% 국세가 원천징수되는 일반 이자·배당만 지원합니다. 배당가산 대상 국내 배당은 별도 입력하며 일반 배당에 중복 입력하지 마세요. 비영업대금, 국외 미원천징수, 비과세·분리과세 특례 소득은 입력하지 마세요.',
         '배당세액공제를 제외한 근로·사업 등 다른 소득의 세액공제·감면 및 기납부세액은 미반영합니다. 표시액은 실제 확정신고 납부액 또는 환급액이 아닙니다.',
         '소득공제 합계에는 본인공제를 포함해 적용 가능한 금액만 입력합니다. 추가 부담은 다른 소득 단독 세액과 일반 원천징수 합계 대비 차이입니다.',
         '원 단위 반올림 비교치이며, 신고서 단수처리·지방세 별도 공제는 이 비교 모델에 포함하지 않습니다.'],
        [{'항목': '금융소득 합계', '금액': income}, {'항목': '2천만원 초과 금액', '금액': excess},
         {'항목': 'A 방식 국세', '금액': method_a}, {'항목': 'B 비교 국세', '금액': comparison},
         {'항목': '기타소득 단독 국세', '금액': ordinary_other_tax}])


def calculate(name, values):
    if name == ISA:
        if len(values) != 4 or values[3] not in FIELDS[ISA][3][3]:
            raise ValueError('ISA 입력 항목을 확인해 주세요.')
        return isa(*values[:3], allowance=2000000 if values[3] == FIELDS[ISA][3][3][0] else 4000000)
    if name == FINANCIAL and len(values) in (4, 5):
        return financial(*values)
    raise ValueError('계산기와 입력 항목을 확인해 주세요.')
