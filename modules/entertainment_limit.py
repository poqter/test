"""Corporate business entertainment ceiling; official return's revenue ordering."""
from .finance_models import D,num,period,FinanceResult
from .personal_tax_models import AS_OF
NAME='접대비 한도계산기';M=10**12;YN=('아니요','예')
FIELDS={NAME:[('총 수입금액 (특수관계 거래 포함)',5000000000,'원',M),('총 수입 중 특수관계인 거래',0,'원',M),
 ('기업업무추진비 총 지출 (문화비 포함, 사적 지출 제외)',50000000,'원',M),('증빙요건 미충족 손금불산입액',0,'원',M),
 ('적격 문화비 (총 지출에 포함된 금액)',0,'원',M),('중소기업 해당 확인','예','선택',YN),
 ('사업연도 월수',12,'개월',12),('시행령42조2항 소규모 부동산임대 등 법인','아니요','선택',YN)]}
def revenue_limit(revenue):
 r=num(revenue)
 return min(r,D(10000000000))*D('.003')+min(max(D(0),r-10000000000),D(40000000000))*D('.002')+max(D(0),r-50000000000)*D('.0003')
def entertainment(revenue=5000000000,related=0,spent=50000000,invalid=0,culture=0,sme='예',months=12,small='아니요'):
 revenue,related,spent,invalid,culture=map(num,(revenue,related,spent,invalid,culture));months=period(months,12)
 if sme not in YN or small not in YN:raise ValueError('법인 자격을 확인하세요.')
 if related>revenue:raise ValueError('특수관계 거래는 총 수입 이하여야 합니다.')
 if invalid>spent or culture>spent-invalid:raise ValueError('문화비는 증빙 불인정액을 제외한 지출에 포함되어야 합니다.')
 basic=D(36000000 if sme=='예' else 12000000)*months/12
 ordinary=revenue_limit(revenue-related)
 special=(revenue_limit(revenue)-ordinary)*D('.1')
 standard=(basic+ordinary+special)*(D('.5') if small=='예' else D(1))
 extra=min(culture,standard*D('.2'));ceiling=standard+extra;eligible=spent-invalid
 allowed=min(eligible,ceiling);excess=max(D(0),eligible-ceiling)
 return FinanceResult({'손금 인정액':allowed,'손금불산입 합계':invalid+excess,'일반 한도':standard,'문화비 추가 한도':extra,
 '한도 합계':ceiling,'증빙 미충족 부인액':invalid,'한도 초과 부인액':excess},
 '기본한도+일반수입 누진한도+(총수입 누진한도−일반수입 누진한도)×10%. 소규모 해당 시50%. 적격 문화비와 일반한도20% 중 작은 금액 추가. 증빙 부인액을 먼저 제외한 지출과 비교.',
 [f'법령 대조 기준일 {AS_OF} · 법인세법25조, 시행령42조, 조세특례제한법136조3항, 2026년 별지23호서식(갑) 기준.',
 '기업업무추진비는 종전 접대비입니다. 일반법인 기본1200만원, 확인된 중소기업3600만원을 사업연도 월수로 안분합니다. 수입금액별 한도에는 월수를 다시 곱하지 않습니다.',
 '특수관계 거래는 총수입에 이미 포함된 금액입니다. 일반수입에 먼저 누진구간을 적용한 뒤 나머지 구간의10%를 계산합니다. 특수관계 거래만 별도 최저구간부터 계산하지 않습니다.',
 '문화비는 총 지출에 포함된 적격 금액이며 다시 지출에 더하지 않습니다. 증빙 미충족액은 세법상 예외를 검토한 금액을 입력합니다. 일반 지출3만원·경조20만원 초과 시 적격증빙 여부를 확인하며 단순 영수증 누락금액과 같지 않을 수 있습니다.',
 '소규모 해당은 지배주주 지분50% 초과, 부동산임대 주업 또는 임대·이자·배당 수입비중50% 이상, 상시근로자5명 미만 등의 모든 법정 요건을 확인한 경우입니다.',
 '전통시장·온누리·지역사랑상품권 별도 추가한도, 정부출자기관70% 특례, 금융업 수입특례 자동조정 및 자산계상 지출의 배부는 아직 미반영입니다. 해당 사례에 이 결과를 최종 한도로 사용하지 않습니다. 추가 법인세는 과세표준 없이 계산하지 않습니다.'],
 [{'항목':'기본한도 (축소 전)','금액':basic},{'항목':'일반수입 누진한도','금액':ordinary},{'항목':'특수관계 수입 추가한도','금액':special},
 {'항목':'증빙 적격 총 지출','금액':eligible}])
def calculate(name,values):
 if name!=NAME or len(values)!=len(FIELDS[NAME]):raise ValueError('입력 항목을 확인하세요.')
 return entertainment(*values)
