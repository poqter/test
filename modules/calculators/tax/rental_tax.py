"""2026 residential rent scenarios with explicit actual expense assumptions."""
from modules.calculators.finance.finance_models import D, FinanceResult, num, period
from modules.calculators.tax.personal_tax_models import progressive_tax, AS_OF

NAME = '임대소득세계산기'
M = 10**12
FIELDS = {NAME: [
    ('연간 월세 수입',18000000,'원',M),
    ('부부합산 보유 주택 수',2,'채',100),
    ('간주임대료 주택 수 (소형주택 제외)',2,'채',100),
    ('기준시가 12억원 초과 주택 수',0,'채',100),
    ('국내 저가 1주택 외 과세 1주택 여부','아니오','선택',('아니오','예 (고가 또는 국외 1주택)')),
    ('간주임대료 대상 주택의 보증금 합계',0,'원',M),
    ('보증금 유지 일수 (연중 동일 금액)',365,'일',365),
    ('신고 방식','장부','선택',('장부','추계')),
    ('보증금 운용 관련 확인된 금융수익',0,'원',M),
    ('분리과세 등록임대 요건','미충족','선택',('미충족','전 주택 충족')),
    ('임대 외 종합소득금액',0,'원',M),
    ('종합과세 필요경비 (확인액 또는 시나리오)',7200000,'원',M),
    ('종합과세 소득공제 합계 (본인 포함)',1500000,'원',M),
    ('종합과세 국세 세액공제 (확인액)',0,'원',M),
]}


def rental(rent=18000000, homes=2, nonsmall=2, expensive=0,
           taxable_single=False, deposit=0, days=365, books=True,
           deposit_income=0, registered=False, other=0, expenses=7200000,
           deductions=1500000, credits=0):
    rent,deposit,deposit_income,other,expenses,deductions,credits = map(
        num,(rent,deposit,deposit_income,other,expenses,deductions,credits))
    homes=period(homes,100,True);nonsmall=period(nonsmall,100,True)
    expensive=period(expensive,100,True);days=period(days,365,True)
    if not expensive<=nonsmall<=homes:
        raise ValueError('고가주택 수 ≤ 소형주택 제외 주택 수 ≤ 전체 주택 수를 확인해 주세요.')
    if not homes and (rent or deposit):
        raise ValueError('임대 수입·보증금이 있으면 주택 수를 입력해 주세요.')
    if not books and deposit_income:
        raise ValueError('추계신고는 보증금 운용 금융수익을 차감하지 않습니다. 해당 입력을 0으로 바꿔주세요.')
    taxed_rent=rent if homes>=2 or (homes==1 and (expensive or taxable_single)) else D(0)
    liable = (nonsmall>=3 and deposit>300000000) or (expensive>=2 and deposit>1200000000)
    deemed=max(D(0),(deposit-D(300000000))*D('.6')*D('.031')*D(days)/365-(deposit_income if books else 0)) if liable else D(0)
    revenue=taxed_rent+deemed
    if expenses>revenue and revenue:
        raise ValueError('필요경비가 과세 임대수입을 초과합니다. 결손금 통산 사례는 별도 검증 대상입니다.')
    rental_income=max(D(0),revenue-expenses)
    base=max(D(0),other+rental_income-deductions)
    other_tax=max(D(0),progressive_tax(max(D(0),other-deductions))-credits)
    combined=max(D(0),progressive_tax(base)-credits)
    comprehensive=(combined-other_tax)*D('1.1')
    sep_allowance=D(4000000 if registered else 2000000) if other<=20000000 else D(0)
    sep_base=max(D(0),revenue*D('.4' if registered else '.5')-sep_allowance)
    separate=sep_base*D('.154') if revenue<=20000000 else None
    chosen='종합과세' if separate is None or comprehensive<=separate else '분리과세'
    if not revenue:chosen='과세 임대수입 없음'
    return FinanceResult(
        {'입력 조건상 임대 세부담 증가액':min(comprehensive,separate) if separate is not None else comprehensive,
         '입력 조건상 유리한 방식':chosen,'과세 임대수입':revenue,'간주임대료':deemed,
         '분리과세 임대 세부담':separate if separate is not None else '선택 불가 (수입 2천만원 초과)',
         '종합과세 임대 세부담 증가액':comprehensive},
        '간주임대료 대상: 비소형3주택 이상·보증금3억원 초과 또는 고가2주택 이상·보증금12억원 초과. '
        '계산액=max(0,(대상보증금−3억원)×60%×3.1%×일수/365−장부 확인 금융수익). '
        '분리과세=(수입−50%/60%경비−조건부200/400만원)×14%×1.1. '
        '종합과세 증가액=(임대합산 결정국세−임대제외 결정국세)×1.1.',
        [f'법령 기준일 {AS_OF} · 2026년 귀속 · 소득세법 제25조, 시행령 제53조(2026-07-01), 시행규칙 제23조(2026-05-22), 국세청 주택임대소득 안내.',
         '고가2주택의 12억원은 과세 대상 판정 기준입니다. 계산식의 차감액은 3억원입니다. 소형주택(40㎡ 이하·기준시가 2억원 이하)은 2026년 간주임대료 주택 수와 보증금에서 제외합니다.',
         '주택 수와 대상 보증금은 법령상 부부합산·공동소유 판정을 마친 값으로 입력합니다. 연중 주택 수·보증금이 바뀌거나 공동사업 배분이 있으면 이 단일기간 모델을 사용할 수 없습니다.',
         '분리과세 등록요건은 지자체·세무서 등록과 임대료 증가율 5% 이하 등 충족을 의미합니다. 등록·미등록 혼합, 임대기간별 배분, 소형주택 세액감면은 미반영합니다.',
         '종합과세 필요경비는 실제 장부금액 또는 명시한 시나리오입니다. 기본 720만원은 예시이며 법정 경비율이 아닙니다. 두 방식은 같은 다른 소득·공제를 전제로 한 임대 때문에 늘어난 세금으로 비교합니다.',
         '입력한 국세 공제액을 두 종합과세 시나리오에 동일 적용합니다. 소득 변화에 따라 공제액이 달라지면 재산출해야 합니다. 지방세는 국세의 10% 비교 추정, 기납부세액·가산세·건강보험료 미반영.'],
        [{'항목':'과세 월세','금액':taxed_rent},{'항목':'종합과세 임대소득금액','금액':rental_income},
         {'항목':'종합과세 과세표준','금액':base},{'항목':'분리과세 과세표준','금액':sep_base if separate is not None else '해당 없음'},
         {'항목':'임대 제외 결정국세','금액':other_tax},{'항목':'임대 합산 결정국세','금액':combined}])


def calculate(name,values):
    if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인해 주세요.')
    for i in (4,7,9):
        if values[i] not in FIELDS[NAME][i][3]:raise ValueError('선택 항목을 확인해 주세요.')
    v=list(values);v[4]=v[4]!='아니오';v[7]=v[7]=='장부';v[9]=v[9]=='전 주택 충족'
    return rental(*v)
