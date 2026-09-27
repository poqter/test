"""Employee invention compensation; annual exemption and shared wage engine."""
from modules.calculators.finance.finance_models import D, num, FinanceResult
from modules.calculators.tax.earned_income_tax import wage_deduction, wage_credit
from modules.calculators.tax.personal_tax_models import progressive_tax

NAME = '직무발명보상금계산기'
YN = ('아니요', '예')
RELATIONS = ('일반 직원', '지배주주·특수관계자')
KINDS = ('재직 중 근로소득', '퇴직 후 기타소득')
M = 10**12
FIELDS = {NAME: [
    ('이번 직무발명보상금', 10000000, '원', M),
    ('이번 보상금 제외 연간 과세 총급여', 80000000, '원', M),
    ('같은 해 먼저 적용한 근로소득 직무발명 비과세액', 0, '원', 7000000),
    ('지급자와의 관계', RELATIONS[0], '선택', RELATIONS),
    ('소득 구분', KINDS[0], '선택', KINDS),
    ('공통 소득공제 (근로소득공제 제외)', 1500000, '원', M),
    ('직무발명 해당·소득 분류·관계·연간 비과세 내역 확인', '아니요', '선택', YN),
]}

OTHER_MODES = ('종합과세 산출세액 비교', '연간 300만원 이하 분리과세')
FIELDS[NAME] += [
    ('퇴직 후 보상금에 대응하는 확인된 실제 필요경비', 0, '원', M),
    ('같은 해 먼저 적용한 기타소득 직무발명 비과세액', 0, '원', 7000000),
    ('퇴직 후 기타소득 과세 방식', OTHER_MODES[0], '선택', OTHER_MODES),
    ('근로소득 외 기존 종합소득금액', 0, '원', M),
    ('다른 선택적 분리과세 기타소득금액 (한도 판정용)', 0, '원', M),
]

def wage_scenario(salary, deductions):
    deduction = wage_deduction(salary)
    base = max(D(0), salary - deduction - deductions)
    gross = progressive_tax(base)
    credit = wage_credit(salary, gross)
    return {'과세 총급여': salary, '근로소득공제': deduction, '공통 소득공제': deductions,
            '과세표준': base, '산출국세': gross, '근로소득세액공제': credit,
            '비교 국세': max(D(0), gross-credit)}

def invention(amount=10000000, salary=80000000, used=0, relation=RELATIONS[0],
              kind=KINDS[0], deductions=1500000, confirmed='아니요', actual_expenses=0, used_other=0,
              other_mode=OTHER_MODES[0], other_income=0, other_optional=0):
    amount, salary, deductions = map(num, (amount, salary, deductions))
    used = num(used, 0, 7000000)
    if relation not in RELATIONS or kind not in KINDS or confirmed not in YN:
        raise ValueError('소득 구분·지급자와의 관계·확인 상태를 확인하세요.')
    actual_expenses, used_other, other_income, other_optional = map(num, (actual_expenses, used_other, other_income, other_optional))
    if other_mode not in OTHER_MODES or used + used_other > 7000000:
        raise ValueError('기타소득 과세 방식과 연간 비과세 합계 700만원 한도를 확인하세요.')
    notes = [
        '법령 대조일 2026-09-27 · 2026년 귀속 · 소득세법 시행령 제17조의3·제18조. 재직 중 근로소득과 퇴직 후 기타소득을 구분합니다.',
        '일반 직원의 연간 근로소득 직무발명 비과세 한도는 700만원입니다. 다른 지급자의 금액을 포함해 같은 해 이미 적용한 금액을 입력합니다. 기존 과세 보상금은 기존 과세 총급여에 포함합니다.',
        '개인 사용자의 친족, 법인 사용자의 지배주주등 및 법정 친족·경영지배관계 해당자는 비과세에서 제외합니다. 단순 주주 여부와 같지 않으며 관계를 확인한 뒤 선택합니다.',
        '퇴직 후 보상금은 소득세법21조1항22의2의 기타소득입니다. 근로소득 및 기타소득에 이미 적용한 비과세액을 연간700만원 한도에서 차감합니다. 시행령87조의 60% 의제경비 대상이 아니므로 과세 보상금에 대응하는 확인된 실제 경비만 입력합니다.',
        '기존 근로소득세 계산기의 근로소득공제·근로소득세액공제·누진세율을 공유합니다. 입력한 공통 소득공제는 세 시나리오에 동일하게 적용합니다.',
        '결과는 근로소득세액공제까지 반영한 국세 비교입니다. 특별·표준·자녀·연금계좌 세액공제, 감면, 지방소득세, 사회보험료, 원천징수와 신고 단수처리는 미반영입니다. 확정 절세액·실수령액으로 사용하지 않습니다.',
        '비과세 효과는 동일 보상금 전액을 과세급여로 가정했을 때와 비교합니다. 총급여 변동에 따른 다른 공제 요건 변화는 별도 검토해야 합니다.',
    ]
    formula = '이번 비과세액=min(보상금, 700만원−연간 기사용 비과세액). 관계 제외 시 0원. 지급 전후의 근로소득공제와 근로소득세액공제를 각각 재계산합니다.'
    if confirmed != '예':
        status = '직무발명·소득·관계·연간 내역 확인 필요'
        return FinanceResult({'보상금 국세 증가 추정': status}, formula, notes)
    exempt = min(amount, D(7000000)-used) if relation == RELATIONS[0] else D(0)
    taxable = amount-exempt
    if kind == KINDS[1]:
        exempt = min(amount, D(7000000)-used-used_other) if relation == RELATIONS[0] else D(0)
        taxable = amount-exempt
        if actual_expenses > taxable:
            raise ValueError('실제 필요경비는 비과세 제외 후 과세 보상금을 초과할 수 없습니다.')
        net = taxable-actual_expenses
        taxable_net = D(0) if net <= 50000 else net
        if other_mode == OTHER_MODES[1] and taxable_net+other_optional > 3000000:
            raise ValueError('연간 선택적 분리과세 기타소득금액 합계가 300만원을 초과합니다.')
        before_base = max(D(0), salary-wage_deduction(salary)+other_income-deductions)
        after_base = max(D(0), salary-wage_deduction(salary)+other_income+taxable_net-deductions)
        before_tax = progressive_tax(before_base)
        after_tax = progressive_tax(after_base)
        increment = taxable_net*D('.2') if other_mode == OTHER_MODES[1] else after_tax-before_tax
        withholding = taxable_net*D('.2')
        notes = notes[:4] + [
            '기타소득의 건별 소득금액5만원 이하는 과세최저한을 적용합니다. 원천징수 요건을 충족한 연간 선택적 분리과세 기타소득금액300만원 이하는 국세20% 분리과세를 선택할 수 있습니다. 원천징수는 선납액이며 종합과세 세액에 더하지 않습니다.',
            '종합과세 비교는 근로소득공제와 공통 소득공제 반영 후 세액공제 전 국세 산출세액 증분입니다. 분리과세 비교는 이번 기타소득의 국세입니다. 근로·특별·표준 세액공제, 지방소득세, 사회보험료와 신고 단수처리는 미반영입니다.',
            '다른 기타소득 한도 입력은 한도 판정에만 사용합니다. 기존 종합소득금액에는 해당 과세 방식에 따라 다른 소득을 별도 반영합니다. 실제 경비의 적격성은 증빙으로 확인해야 합니다.',
        ]
        metrics = {'이번 비과세 금액': exempt, '이번 과세 보상금': taxable,
                   '기타소득금액': net, '과세 대상 기타소득금액': taxable_net,
                   '보상금 국세 산출세액 증가 추정': increment,
                   '이번 원천징수 국세 추정 (선납)': withholding, '과세 방식': other_mode}
        rows = [{'항목': key, '금액 또는 구분': value} for key, value in metrics.items()]
        if other_mode == OTHER_MODES[0]:
            rows += [{'항목': '기존 종합소득 과세표준', '금액 또는 구분': before_base},
                     {'항목': '지급 후 종합소득 과세표준', '금액 또는 구분': after_base}]
        return FinanceResult(metrics, '기타소득금액=보상금−남은 연간 비과세액−실제 필요경비. 종합과세는 전후 산출세액 차이, 분리과세는 과세 기타소득금액×20%.', notes, rows)
    if actual_expenses or used_other or other_income or other_optional:
        raise ValueError('재직 중 근로소득 비교에서는 퇴직 후 기타소득 전용 입력을 0으로 설정하세요.')
    before = wage_scenario(salary, deductions)
    after = wage_scenario(salary+taxable, deductions)
    full = wage_scenario(salary+amount, deductions)
    metrics = {'이번 비과세 금액': exempt, '이번 과세 보상금': taxable,
               '보상금 국세 증가 추정': after['비교 국세']-before['비교 국세'],
               '비과세 적용에 따른 국세 감소 추정': full['비교 국세']-after['비교 국세']}
    rows = [dict(시나리오=label, **row) for label, row in
            [('지급 전', before), ('비과세 적용 지급 후', after), ('전액 과세 가정', full)]]
    return FinanceResult(metrics, formula, notes, rows)

def calculate(name, values):
    if name != NAME or len(values) not in (7, len(FIELDS[NAME])):
        raise ValueError('입력 항목을 확인하세요.')
    return invention(*values)
