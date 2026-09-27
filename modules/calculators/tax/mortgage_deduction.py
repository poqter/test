"""Modern acquisition-loan deduction; shares the earned-income tax engine.

Scope is deliberately restricted to 2024+ ordinary purchase loans. Historical
loans, refinancing and presale rights need their own transitional-rule audit.
"""
from datetime import date
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import AS_OF
from modules.calculators.tax.earned_income_tax import earned

NAME = '주택담보대출 이자공제계산기'
YESNO = ('아니요', '예')
TYPES = ('고정금리·비거치식 모두 충족', '고정금리만 충족', '비거치식만 충족', '둘 다 미충족')
ROLES = ('세대주', '실거주 세대원·세대주가 주택자금 공제 미신청', '요건 미충족')
M = 10**12
FIELDS = {NAME: [
    ('연간 실제 이자상환액', 6000000, '원', M),
    ('연간 총급여 (비과세 제외)', 70000000, '원', M),
    ('취득 당시 주택 기준시가 (매매가 아님)', 500000000, '원', M),
    ('소유권 이전·보존 등기일 (2024년 이후 일반 취득)', '2024-01-01', '날짜', 0),
    ('최초 차입일 (신규 취득대출)', '2024-01-01', '날짜', 0),
    ('약정 상환기간', 15, '년', 60),
    ('법정 고정금리·비거치식 요건', TYPES[0], '선택', TYPES),
    ('연말 세대 전체 주택 수', 1, '채', 100),
    ('연말 세대주·세대원 요건', ROLES[0], '선택', ROLES),
    ('근로소득 거주자·본인 소유 주택·본인 채무·적격 금융기관 저당대출 확인', YESNO[0], '선택', YESNO),
    ('다른 주택자금·청약저축 공제액 (개별 요건·한도 적용 후)', 0, '원', 4000000),
    ('기본공제 인원 (본인 포함)', 1, '명', 100),
    ('공적연금 실제 본인 납부액', 0, '원', M),
    ('건강·장기요양보험 실제 본인 납부액', 0, '원', M),
    ('고용보험 실제 본인 납부액', 0, '원', M),
]}


def _date(value):
    try:
        return value if type(value) is date else date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError('날짜를 YYYY-MM-DD 형식으로 입력해 주세요.') from None


def mortgage(interest=6000000, salary=70000000, standard_value=500000000,
             registered='2024-01-01', borrowed='2024-01-01', years=15,
             loan_type=TYPES[0], houses=1, role=ROLES[0], eligible=YESNO[0],
             other_housing=0, people=1, pension=0, health=0, employment=0):
    interest, salary, standard_value, other_housing, pension, health, employment = map(
        num, (interest, salary, standard_value, other_housing, pension, health, employment))
    years = period(years, 60); houses = period(houses, 100, True)
    people = period(people, 100)
    if loan_type not in TYPES or role not in ROLES or eligible not in YESNO:
        raise ValueError('공제 요건 선택을 확인해 주세요.')
    registered, borrowed = _date(registered), _date(borrowed)
    if not date(2024, 1, 1) <= registered <= date(2026, 12, 31):
        raise ValueError('현재 자동 판정은 2024~2026년 취득·신규 차입만 지원합니다. 과거 대출은 경과규정 검증 대상입니다.')
    if not date(2024, 1, 1) <= borrowed <= date(2026, 12, 31):
        raise ValueError('2024~2026년 신규 차입일을 입력해 주세요. 대환·승계·기간연장은 현재 자동 판정 범위 밖입니다.')
    if other_housing > 4000000:
        raise ValueError('다른 주택자금·청약저축은 개별 요건과 합산 400만원 한도 적용 후 입력해 주세요.')
    # A calendar-month deadline, not a 90-day approximation.
    import calendar
    month_index = registered.year * 12 + registered.month - 1 + 3
    end_year, month0 = divmod(month_index, 12)
    deadline = date(end_year, month0+1, min(registered.day, calendar.monthrange(end_year, month0+1)[1]))
    nominal_limit = (20000000 if loan_type == TYPES[0] else
                     8000000 if loan_type == TYPES[3] else 18000000) if years >= 15 else (
                     6000000 if years >= 10 and loan_type != TYPES[3] else 0)
    reasons = []
    if eligible != YESNO[1]: reasons.append('적격 근로자·소유자·채무자·대출기관 요건 미확인')
    if houses >= 2: reasons.append('연말 세대 전체 2주택 이상')
    if role == ROLES[2]: reasons.append('세대주 또는 실거주 세대원 요건 미충족')
    if standard_value > 600000000: reasons.append('취득 당시 기준시가 6억원 초과')
    if not registered <= borrowed <= deadline:
        reasons.append('등기일 이후 3개월 이내 신규 차입 범위 밖: 예외는 별도 확인 필요')
    if not nominal_limit: reasons.append('상환기간·상환방식 요건 미충족')
    available = max(D(0), D(nominal_limit)-other_housing) if not reasons else D(0)
    deduction = min(interest, available)
    # Same engine as the standalone earned calculator; compare optimal standard
    # vs itemized in both scenarios, retaining all other supplied inputs.
    args = dict(salary=salary, people=people, nps=pension, health=health, employment=employment)
    before = earned(**args, housing=other_housing)
    after = earned(**args, housing=other_housing+deduction)
    key = '예상 결정세액 (국세+지방세)'
    saving = before.metrics[key]-after.metrics[key]
    rows = [{'구분': title, **row} for title, result in (('이자공제 전', before), ('이자공제 후', after)) for row in result.rows]
    return FinanceResult(
        {'이자 소득공제 대상액': deduction,
         '입력 조건에서 예상 세금 감소액': saving,
         '공제 전 예상 결정세액': before.metrics[key],
         '공제 후 예상 결정세액': after.metrics[key],
         '상환 유형별 합산 공제한도': D(nominal_limit),
         '다른 주택공제 차감 후 사용 가능 한도': available,
         '절세 반영 이자 부담 추정': interest-saving,
         '요건 판정': ' / '.join(reasons) if reasons else '입력한 일반 취득 요건 충족'},
        '이자공제 대상액=min(실제 이자, 유형별 합산 한도−다른 주택자금·청약 공제). '
        '근로소득세 엔진으로 공제 전후 각각 특별·표준공제를 비교하고, 결정세액 차이를 계산합니다.',
        [f'법령 대조 기준일 {AS_OF} · 2026년 귀속 · 소득세법 제52조 제5·6항, 시행령 제112조 제8·9항.',
         '2024년 이후 일반 주택 취득·신규 차입을 지원합니다. 2023년 이전 취득, 대환·승계·기간연장, 분양권·중도금, 공동차입과 중도 조건변경은 아직 자동 판정하지 않습니다.',
         '6억원 판단은 매매대금이 아닌 취득 당시 기준시가입니다. 총급여만으로 자격을 제한하지 않습니다. 세대주·주택 수는 연말 기준이며 배우자 등 세대원 소유 주택을 포함합니다.',
         '고정금리는 차입금 70% 이상을 상환기간 중 고정(5년 이상 단위 변경 포함)하는 법정 방식입니다. 비거치식은 거치 1년 이내 및 법정 매년 최소 원금상환 기준을 확인한 경우만 선택합니다.',
         '최초 차입 날짜의 예외 인정은 자동 판정하지 않습니다. 실제 금융기관 증명서와 등기자료를 확인해 주세요.',
         '세금 비교는 근로소득만 있는 거주자·입력한 인적/사회보험/주택 공제에 한정합니다. 연금계좌·보험·의료·교육·기부·자녀 등 추가 세액공제에 따라 실제 절세액이 달라집니다. 지방세 10% 추정 및 원 단위 반올림입니다.',
         '다른 주택공제액은 개별 자격을 확인한 값입니다. 고객 결과와 상세 결과는 같은 입력 시나리오를 사용합니다.'], rows)


def calculate(name, values):
    if name != NAME or len(values) != len(FIELDS[NAME]):
        raise ValueError('계산기 입력 항목을 확인해 주세요.')
    return mortgage(*values)
