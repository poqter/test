"""Cash contribution to own corporate employee welfare fund, 2026."""
from modules.calculators.finance.finance_models import D, num, period, FinanceResult
from modules.calculators.corporate.corporate_tax import bracket
from modules.calculators.tax.personal_tax_models import AS_OF
NAME='사내근로복지기금계산기';M=10**12;YN=('아니요','예')
TYPES=('일반 50%','법62조2항1호·3호 등 80% 자격 확인','도급·파견 지원 90% 자격 확인')
FIELDS={NAME:[('당기 현금 출연액',100000000,'원',M),('출연 전 과세표준',500000000,'원',M),('수혜 근로자 수',10,'명',100000),
 ('자체 설립 기금에 대한 손금산입 요건 확인','아니요','선택',YN),('법60조의2 제1항1호 소규모법인 해당','아니요','선택',YN),
 ('당기 출연금 사용한도 구분',TYPES[0],'선택',TYPES),('협의회가 결정한 당기 출연금 사용률',50,'%',100),
 ('기금 설립·목적사업·사용률 의결 및 특례 요건 확인','아니요','선택',YN)]}
def fund(paid=100000000,base=500000000,people=10,confirmed='아니요',small='아니요',kind=TYPES[0],rate=50,use_confirmed='아니요'):
 paid,base=map(num,(paid,base));people=period(people,100000);rate=num(rate,0,100)
 if kind not in TYPES or any(x not in YN for x in (confirmed,small,use_confirmed)):raise ValueError('출연·사용 요건을 확인하세요.')
 cap=(50,80,90)[TYPES.index(kind)]
 if rate>cap:raise ValueError('의결 사용률은 선택한 법정 한도를 초과할 수 없습니다.')
 after=max(D(0),base-paid);saving=(bracket(base,small=='예')-bracket(after,small=='예'))*D('1.1')
 use=paid*rate/100
 return FinanceResult({'회사 현금 출연액':paid,'국세·지방세 산출세액 감소 추정':saving if confirmed=='예' else '손금 요건 미확인',
 '세액 감소 반영 회사 부담 추정':paid-saving if confirmed=='예' else '세액 미확인 — 출연액은 별도 표시',
 '반영 후 과세표준':after if confirmed=='예' else '손금 요건 미확인',
 '당기 출연금 중 사용 예정액':use if use_confirmed=='예' else '사용 요건·의결 미확인',
 '당기 출연금 중 기본재산 잔류액':paid-use if use_confirmed=='예' else '사용 요건·의결 미확인',
 '사용 예정액의 1인당 단순 평균':use/people if use_confirmed=='예' else '사용 예정액 확인 필요'},
 '법인세 공통 누진함수로 출연 전후 과세표준의 산출세액 차이를 비교. 당기 현금 출연액×협의회 의결 사용률을 사용 예정액으로 계산하고 나머지는 기본재산에 남김.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법 시행령19조22호, 근로복지기본법62조 및 시행령46조4항1호.',
 '해당 내국법인이 적법하게 설립한 자체 사내근로복지기금에 현금으로 출연하는 경우입니다. 현물·자기주식·다른 법인의 기금·공동기금 및 별도 출연 세액공제는 이 화면 범위 밖입니다.',
 '당기 출연금은 일반50%, 법정 적격 사례80%, 일정 도급·파견 근로자 지원 조건90% 범위에서 협의회가 정한 비율만 사용합니다. 회사 규모를 고르는 것만으로 특례가 확정되지 않습니다.',
 '기존 기본재산 추가 사용·공동기금 지원 특례·운용수익은 제외합니다. 출연액 전액을 직원에게 당장 지급 가능한 금액으로 표시하지 않습니다. 1인당 평균은 비교 지표이며 균등 현금 지급 권리가 아닙니다.',
 '직원 수혜항목별 소득·증여세 및 급여 대체 가능 여부는 판정하지 않습니다. 모든 복지급부를 자동 비과세로 가정하지 않습니다.',
 '세액 차이는2026년 일반 표준세율 및 동일 지방세 과표 가정, 공제감면·최저한세·결손금 이월효과 반영 전입니다. 실제 환급액이 아니며 출연금이 소득보다 커도 당기 세액 감소는 출연 전 산출세액을 넘지 않습니다.'],
 [{'항목':'법정 사용률 상한','값':str(cap)+'%'},{'항목':'협의회 의결 입력률','값':str(rate)+'%'},
 {'항목':'출연 전 산출세액 (지방 포함)','값':str(bracket(base,small=='예')*D('1.1'))}])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return fund(*values)
